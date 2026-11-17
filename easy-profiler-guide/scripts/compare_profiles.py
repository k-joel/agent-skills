#!/usr/bin/env python3
"""Compare two easy_profiler summary JSONs (before / after) and render a Markdown table.

Usage:
    python compare_profiles.py BEFORE.json AFTER.json [--out report.md]
                               [--min-ms 1.0] [--self]

Aggregates per-block metrics across all threads (block names are stable in the
summary schema; see references/summary-schema.md). Standard library only.

Importable API: render(before_summary, after_summary, min_ms=1.0, self_time=False).
"""

import argparse
import json
import sys


def load_summary(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def aggregate_blocks(summary):
    """Collapse (thread, block) records into one row per block name."""
    blocks = {}
    for thread in summary.get('threads', []):
        for block in thread.get('blocks', []):
            name = block['name']
            row = blocks.setdefault(name, {'calls': 0, 'total_ms': 0.0, 'self_ms': 0.0})
            row['calls'] += block.get('calls', 0)
            row['total_ms'] += block.get('total_ms', 0.0)
            row['self_ms'] += block.get('self_ms', 0.0)
    return blocks


def pct(before, after):
    if before == 0.0:
        return 'n/a' if after == 0.0 else 'new'
    return f'{100.0 * (after - before) / before:+.1f}%'


def fmt(value):
    return f'{value:,.1f}'


def render(before_summary, after_summary, min_ms=1.0, self_time=False):
    before_blocks = aggregate_blocks(before_summary)
    after_blocks = aggregate_blocks(after_summary)

    before_run = before_summary['run']['duration_ms']
    after_run = after_summary['run']['duration_ms']

    lines = []
    header = '| Block | Before (ms) | After (ms) | Delta (ms) | Change | Before calls | After calls |'
    align = '|---|---:|---:|---:|---:|---:|---:|'
    if self_time:
        header = header[:-1] + '| Before self (ms) | After self (ms) |'
        align = align[:-1] + '|---:|---:|'
    lines.append(header)
    lines.append(align)

    extra = ' - | - |' if self_time else ''
    lines.append(
        f"| **run.duration_ms** | {fmt(before_run)} | {fmt(after_run)} | "
        f"{fmt(after_run - before_run)} | {pct(before_run, after_run)} | - | - |{extra}"
    )
    before_threads = len(before_summary.get('threads', []))
    after_threads = len(after_summary.get('threads', []))
    lines.append(
        f"| **thread count** | {before_threads} | {after_threads} | "
        f"{after_threads - before_threads} | {pct(float(before_threads), float(after_threads))} | - | - |{extra}"
    )

    names = set(before_blocks) | set(after_blocks)
    ordered = sorted(
        names, key=lambda n: before_blocks.get(n, {}).get('total_ms', 0.0), reverse=True
    )

    zero = {'calls': 0, 'total_ms': 0.0, 'self_ms': 0.0}
    for name in ordered:
        b = before_blocks.get(name, zero)
        a = after_blocks.get(name, zero)
        # Skip blocks that are negligible before and after to keep the table readable.
        if b['total_ms'] < min_ms and a['total_ms'] < min_ms:
            continue
        label = f'`{name}`'
        if name not in before_blocks:
            label += ' **(NEW)**'
        elif name not in after_blocks:
            label += ' **(REMOVED)**'
        row = (
            f"| {label} | {fmt(b['total_ms'])} | {fmt(a['total_ms'])} | "
            f"{fmt(a['total_ms'] - b['total_ms'])} | {pct(b['total_ms'], a['total_ms'])} | "
            f"{b['calls']:,} | {a['calls']:,} |"
        )
        if self_time:
            row += f" {fmt(b['self_ms'])} | {fmt(a['self_ms'])} |"
        lines.append(row)

    return '\n'.join(lines)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('before', help='baseline summary JSON')
    parser.add_argument('after', help='new summary JSON')
    parser.add_argument('--out', help='write the Markdown report to this path')
    parser.add_argument('--min-ms', type=float, default=1.0,
                        help='hide blocks below this total in both runs (default 1.0)')
    parser.add_argument('--self', dest='self_time', action='store_true',
                        help='add before/after self-time columns')
    args = parser.parse_args(argv)

    try:
        before = load_summary(args.before)
        after = load_summary(args.after)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc))
    table = render(before, after, min_ms=args.min_ms, self_time=args.self_time)

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as handle:
            handle.write(table + '\n')
        print(f'Wrote {args.out}')
    else:
        print(table)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))