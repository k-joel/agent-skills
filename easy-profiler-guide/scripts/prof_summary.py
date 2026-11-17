#!/usr/bin/env python3
"""Summarize an easy_profiler v2.1.x .prof capture into aggregated JSON + Markdown.

Parses the binary .prof format directly (no profiler_converter needed) and
aggregates one row per (thread, block descriptor) — the same grouping the
official C++ reader uses — so the output stays in the kilobyte range regardless
of capture length.

Usage:
    python prof_summary.py INPUT.prof                          # report to stdout
    python prof_summary.py INPUT.prof --json OUT.json --md OUT.md [--top N]

Importable API: parse(path), summarize(header, threads, prof_name),
render_report(summary, meta=None, top=20).

Standard library only, Python 3.8+. See references/summary-schema.md for the
output schema and references/easy-profiler-overview.md section 6 for the format.
"""

import argparse
import json
import statistics
import struct
import sys
from pathlib import Path

SIGNATURE = 0x45617379
VALUE_TYPES = {0: '?', 1: 'c', 2: 'b', 3: 'B', 4: 'h', 5: 'H', 6: 'i',
               7: 'I', 8: 'q', 9: 'Q', 10: 'f', 11: 'd'}  # 12 = string
TYPE_EVENT, TYPE_BLOCK, TYPE_VALUE = 0, 1, 2


class ProfParseError(Exception):
    pass


class _Cursor:
    def __init__(self, data):
        self.d, self.o = data, 0

    def take(self, fmt):
        fmt = '<' + fmt
        if self.o + struct.calcsize(fmt) > len(self.d):
            raise ProfParseError(f"truncated file at offset {self.o} (reading '{fmt}')")
        v = struct.unpack_from(fmt, self.d, self.o)
        self.o += struct.calcsize(fmt)
        return v if len(v) > 1 else v[0]

    def raw(self, n):
        if n < 0 or self.o + n > len(self.d):
            raise ProfParseError(f"bad record size {n} at offset {self.o}")
        b = self.d[self.o:self.o + n]
        self.o += n
        return b


def _cstr(b):
    return b.split(b'\0', 1)[0].decode('utf-8', 'replace')


def _decode_value(payload):
    """payload = bytes after the 20 fixed block fields (Value records only)."""
    size, vtype, is_array = struct.unpack_from('<HBB', payload, 2)
    vin, = struct.unpack_from('<Q', payload, 6)
    data = payload[14:14 + size]
    if vtype == 12:
        text = data[:-1] if data.endswith(b'\0') else data
        return {'vin': vin, 'value': text.decode('utf-8', 'replace')}
    code = VALUE_TYPES.get(vtype)
    if code is None:
        return {'vin': vin, 'value': data.hex()}
    n = size // struct.calcsize(code)
    vals = struct.unpack('<%d%s' % (n, code), data)
    vals = [v.decode('utf-8', 'replace') if isinstance(v, bytes) else v for v in vals]
    return {'vin': vin, 'value': vals if is_array else vals[0]}


def parse(path):
    """Read a v2.x .prof file. Returns (header, threads).

    header: dict with version, pid, freq, begin, end, blocks, ndesc, nthreads,
            nbookmarks, bookmarks, to_ns (tick -> ns callable).
    threads: list of dicts {tid, name, cswitches, roots}; each tree node has
            begin/end (ticks), dur (ns), desc, name, children, and optionally
            value (decoded payload) or runtime_name.
    """
    r = _Cursor(Path(path).read_bytes())
    if r.take('I') != SIGNATURE:
        raise ProfParseError(f"{path}: not an easy_profiler .prof file (bad signature)")
    version = r.take('I')
    if version < 0x02010000 or version >> 24 != 2:
        raise ProfParseError(
            f"{path}: unsupported file version 0x{version:08x}; "
            "this parser reads the v2.1.x format (easy_profiler v2.1.0+)")
    h = dict(version=version, pid=r.take('Q'), freq=r.take('q'), begin=r.take('Q'),
             end=r.take('Q'), mem=r.take('Q'), dmem=r.take('Q'), blocks=r.take('I'),
             ndesc=r.take('I'), nthreads=r.take('I'), nbookmarks=r.take('H'))
    if r.take('H') != 0:
        raise ProfParseError(f"{path}: header padding is not zero (corrupt file?)")

    freq = h['freq']
    to_ns = (lambda t: t * 1_000_000_000 // freq) if freq else (lambda t: t)
    h['to_ns'] = to_ns

    descs = {}
    for _ in range(h['ndesc']):
        size = r.take('H')
        end = r.o + size
        if size == 0:
            continue  # null placeholder descriptor
        did, line, color, typ, status = r.take('IiIBB')
        nlen = r.take('H')
        name = _cstr(r.raw(nlen))
        file = _cstr(r.raw(end - r.o))
        descs[did] = dict(id=did, name=name, file=file, line=line, color=color,
                          type=typ, status=status)

    threads = []
    for _ in range(h['nthreads']):
        tid = r.take('Q')
        name = _cstr(r.raw(r.take('H')))
        cswitches = []
        for _ in range(r.take('I')):
            size = r.take('H')
            end = r.o + size
            b, e, who = r.take('QQQ')
            cswitches.append(dict(begin=b, end=e, tid=who,
                                  process=_cstr(r.raw(end - r.o))))
        stack = []  # records are in completion order: children before parents
        for _ in range(r.take('I')):
            size = r.take('H')
            end = r.o + size
            b, e, did = r.take('QQI')
            if did not in descs:
                raise ProfParseError(f"{path}: block references unknown descriptor {did}")
            d = descs[did]
            rest = r.raw(end - r.o)
            node = dict(begin=b, end=e, dur=to_ns(e - b), desc=d, children=[])
            if d['type'] == TYPE_VALUE:
                node['value'] = _decode_value(rest)
                node['name'] = d['name']
            else:
                node['runtime_name'] = _cstr(rest)
                node['name'] = node['runtime_name'] or d['name']
            while stack and stack[-1]['begin'] >= b:
                node['children'].insert(0, stack.pop())
            stack.append(node)
        threads.append(dict(tid=tid, name=name, cswitches=cswitches, roots=stack))

    if r.take('I') != SIGNATURE:
        raise ProfParseError(f"{path}: bad trailer signature (corrupt or truncated file)")
    h['bookmarks'] = []
    for _ in range(h['nbookmarks']):
        size = r.take('H')
        end = r.o + size
        pos, color = r.take('QI')
        h['bookmarks'].append(dict(pos=pos, color=color, text=_cstr(r.raw(end - r.o))))
    return h, threads


def _ms(ns):
    return round(ns / 1_000_000.0, 3)


def summarize(h, threads, prof_name):
    """Aggregate parsed trees into the summary schema (see summary-schema.md)."""
    out_threads = []
    for t in threads:
        rows = {}
        blocks_number = 0

        def walk(node):
            nonlocal blocks_number
            blocks_number += 1
            children_ns = 0
            for c in node['children']:
                children_ns += c['dur']
                walk(c)
            d = node['desc']
            if d['type'] == TYPE_BLOCK:
                row = rows.get(d['id'])
                if row is None:
                    row = rows[d['id']] = dict(
                        name=node['name'], file=d['file'], line=d['line'],
                        calls=0, total_ns=0, self_ns=0, durations=[])
                row['calls'] += 1
                row['total_ns'] += node['dur']
                row['self_ns'] += node['dur'] - children_ns
                row['durations'].append(node['dur'])

        for root in t['roots']:
            walk(root)
        profiled_ns = sum(root['dur'] for root in t['roots'])
        blocks = []
        for row in rows.values():
            blocks.append(dict(
                name=row['name'], file=row['file'], line=row['line'],
                calls=row['calls'],
                total_ms=_ms(row['total_ns']),
                avg_ms=_ms(row['total_ns'] // row['calls']),
                median_ms=_ms(int(statistics.median(row['durations']))),
                self_ms=_ms(row['self_ns']),
                pct_of_thread=round(100.0 * row['total_ns'] / profiled_ns, 1)
                if profiled_ns else 0.0))
        blocks.sort(key=lambda b: b['total_ms'], reverse=True)
        out_threads.append(dict(id=t['tid'], name=t['name'],
                                profiled_ms=_ms(profiled_ns),
                                blocks_number=blocks_number, blocks=blocks))
    out_threads.sort(key=lambda t: t['profiled_ms'], reverse=True)
    return dict(run=dict(prof_file=str(prof_name),
                         duration_ms=_ms(h['to_ns'](h['end'] - h['begin'])),
                         pid=h['pid']),
                threads=out_threads)


def _aggregate_by_name(summary):
    rows = {}
    for thread in summary.get('threads', []):
        for block in thread.get('blocks', []):
            key = (thread.get('name', '?'), block['name'])
            row = rows.setdefault(key, {'calls': 0, 'total_ms': 0.0,
                                        'self_ms': 0.0, 'max_pct': 0.0})
            row['calls'] += block.get('calls', 0)
            row['total_ms'] += block.get('total_ms', 0.0)
            row['self_ms'] += block.get('self_ms', 0.0)
            row['max_pct'] = max(row['max_pct'], block.get('pct_of_thread', 0.0))
    return rows


def render_report(summary, meta=None, top=20):
    """Markdown report: run metadata, threads table, top blocks, reading notes."""
    run = summary.get('run', {})
    threads = summary.get('threads', [])
    lines = [f"# Profile report — {run.get('prof_file', '?')}", '']
    lines += ['| Field | Value |', '| --- | --- |',
              f"| Profile file | `{run.get('prof_file', '?')}` |",
              f"| Capture duration | {run.get('duration_ms', 0.0):,.1f} ms |",
              f"| Process id | {run.get('pid', '?')} |",
              f"| Profiled threads | {len(threads)} |"]
    for key, value in (meta or {}).items():
        lines.append(f"| {key} | {value} |")
    lines.append('')

    lines += ['## Threads', '',
              '| Thread | Profiled (ms) | Blocks | Hot block (self ms) |',
              '| --- | ---: | ---: | --- |']
    for thread in threads:
        blocks = thread.get('blocks', [])
        hot = max(blocks, key=lambda b: b.get('self_ms', 0.0)) if blocks else None
        hot_text = f"{hot['name']} ({hot['self_ms']:,.1f})" if hot else '-'
        lines.append(f"| `{thread.get('name') or thread.get('id', '?')}` | "
                     f"{thread.get('profiled_ms', 0.0):,.1f} | "
                     f"{thread.get('blocks_number', 0):,} | {hot_text} |")
    lines.append('')

    lines += [f'## Top {top} blocks by total time', '',
              '| Thread | Block | Calls | Total (ms) | Self (ms) | % of thread |',
              '| --- | --- | ---: | ---: | ---: | ---: |']
    rows = _aggregate_by_name(summary)
    ordered = sorted(rows.items(), key=lambda kv: kv[1]['total_ms'], reverse=True)
    for (thread_name, block_name), row in ordered[:top]:
        lines.append(f"| `{thread_name}` | `{block_name}` | {row['calls']:,} | "
                     f"{row['total_ms']:,.1f} | {row['self_ms']:,.1f} | "
                     f"{row['max_pct']:.1f} |")
    lines.append('')

    lines += ['## Reading notes', '',
              '- `Self (ms)` excludes children on the *same* thread: a block that waits '
              'on another thread reports that wait as self time.',
              '- `% of thread` is per-thread and is not comparable across rows from '
              'different threads.',
              '- Rows are aggregated per (thread, block descriptor): blocks created at '
              'the same source line share one row, even with different run-time names.',
              '- Events and values are counted in `Blocks` but not ranked.', '']
    return '\n'.join(lines)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input', help='.prof capture file (easy_profiler v2.1.x)')
    parser.add_argument('--json', dest='json_path', help='write the aggregated summary JSON here')
    parser.add_argument('--md', dest='md_path', help='write the Markdown report here')
    parser.add_argument('--top', type=int, default=20, help='rows in the top-blocks table (default 20)')
    args = parser.parse_args(argv)

    try:
        h, threads = parse(args.input)
    except (ProfParseError, OSError) as exc:
        raise SystemExit(str(exc))
    summary = summarize(h, threads, args.input)

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(summary, indent=2) + '\n',
                                        encoding='utf-8')
        print(f"Wrote {args.json_path}")
    report = render_report(summary, top=args.top)
    if args.md_path:
        Path(args.md_path).write_text(report + '\n', encoding='utf-8')
        print(f"Wrote {args.md_path}")
    if not args.json_path and not args.md_path:
        print(report)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))