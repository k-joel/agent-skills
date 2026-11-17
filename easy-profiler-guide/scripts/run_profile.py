#!/usr/bin/env python3
"""Run an instrumented application and write a timestamped profile report.

Runs any command that produces an easy_profiler .prof capture, then summarizes
it (prof_summary.py) and diffs it against the previous run (compare_profiles.py):

    artifacts/profile_<yy-mm-dd-hh-mm-ss>.prof   raw easy_profiler capture
    artifacts/profile_<yy-mm-dd-hh-mm-ss>.json   aggregated summary
    artifacts/profile_<yy-mm-dd-hh-mm-ss>.md     human-readable report (+ comparison)
    artifacts/profile_<yy-mm-dd-hh-mm-ss>.log    the run's captured stdout + stderr

Tell the script where the .prof lands, one of two ways:
  * put a {prof} placeholder in the command — it is replaced with the
    timestamped target path (the app must accept an output-path argument);
  * pass --prof PATH — the fixed path the app always dumps to; the file is
    moved into the output directory after the run.

Usage:
    python run_profile.py --out-dir artifacts -- ./app --profile {prof}
    python run_profile.py --out-dir artifacts --prof out.prof -- ./app
    python run_profile.py --out-dir artifacts --tag experiment -- ./app --profile {prof}
    python run_profile.py --out-dir artifacts --list

Build the instrumented configuration first — build systems are project-specific
and this script does not build. Standard library only, Python 3.8+.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prof_summary  # noqa: E402  (same directory)
import compare_profiles  # noqa: E402  (same directory)

SUMMARY_GLOB = 'profile_*.json'


def log(message):
    print(message, flush=True)


def list_profiles(out_dir):
    profiles = sorted(out_dir.glob(SUMMARY_GLOB))
    if not profiles:
        log(f'No profiles in {out_dir}')
        return
    log(f'Profiles in {out_dir} (oldest first):')
    for path in profiles:
        log(f'  {path.name}')


def run_capture(command, log_path):
    """Run the command; persist stdout+stderr before anything can fail."""
    log('Running: ' + ' '.join(command))
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, errors='replace')
    elapsed = time.perf_counter() - started
    output = (result.stdout or '') + (result.stderr or '')
    log_path.write_text(output, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        log(output)
        raise SystemExit(f'profiling run failed (exit {result.returncode}); log: {log_path}')
    return elapsed


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out-dir', default='artifacts', help='report output directory')
    parser.add_argument('--prof', help='fixed .prof path the app dumps to (when no {prof} placeholder)')
    parser.add_argument('--tag', help='suffix for the output stem (profile_<tag>_<ts>.*) '
                                      'and skip the previous-run comparison')
    parser.add_argument('--top', type=int, default=20, help='rows in the top-blocks table (default 20)')
    parser.add_argument('--list', action='store_true', help='list captured profiles and exit')
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='the app command after --, optionally containing {prof}')
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.list:
        list_profiles(out_dir)
        return 0

    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        raise SystemExit('No command given. Usage: run_profile.py [options] -- <command...> '
                         '(with a {prof} placeholder, or --prof PATH)')

    uses_placeholder = any('{prof}' in part for part in command)
    if not uses_placeholder and not args.prof:
        raise SystemExit('Tell the script where the .prof lands: put {prof} in the command '
                         'or pass --prof PATH.')

    # Resolve the previous profile before the new one is written. A tagged run is one arm of a
    # sweep, so it never diffs against an unrelated arm. Pick by mtime, not name: tagged stems
    # (profile_<tag>_<ts>) do not sort chronologically.
    previous = None
    if not args.tag:
        candidates = list(out_dir.glob(SUMMARY_GLOB))
        previous = max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None

    timestamp = datetime.now().strftime('%y-%m-%d-%H-%M-%S')
    stem = f'profile_{args.tag}_{timestamp}' if args.tag else f'profile_{timestamp}'
    prof_path = out_dir / f'{stem}.prof'
    json_path = out_dir / f'{stem}.json'
    md_path = out_dir / f'{stem}.md'
    log_path = out_dir / f'{stem}.log'

    if uses_placeholder:
        command = [part.replace('{prof}', str(prof_path)) for part in command]
        source_prof = prof_path
    else:
        source_prof = Path(args.prof)
    if source_prof.exists():
        source_prof.unlink()  # stale capture from an earlier run must not masquerade as this one

    wall_seconds = run_capture(command, log_path)

    if not source_prof.exists():
        raise SystemExit(
            f'No .prof produced at {source_prof}. Check that the executable is the instrumented '
            'build (BUILD_WITH_EASY_PROFILER), that capture was enabled before the outermost '
            'block opened, and that the dump ran after the frames closed. '
            f'Run output: {log_path}')
    if source_prof != prof_path:
        source_prof.replace(prof_path)

    try:
        h, threads = prof_summary.parse(prof_path)
    except prof_summary.ProfParseError as exc:
        raise SystemExit(str(exc))
    summary = prof_summary.summarize(h, threads, prof_path.name)
    total_blocks = sum(t['blocks_number'] for t in summary['threads'])
    if total_blocks == 0:
        raise SystemExit(
            f'{prof_path} contains 0 blocks. Usual causes: capture never enabled, dump called '
            'inside a still-open top-level block, or the TU was compiled without '
            'BUILD_WITH_EASY_PROFILER. See the skill pitfalls table.')

    json_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')

    meta = {
        'Timestamp': f'`{timestamp}`',
        'Command': '`' + ' '.join(command) + '`',
        'Run log': f'`{log_path.name}`',
        'Wall time (process)': f'{wall_seconds:,.2f} s',
    }
    report = prof_summary.render_report(summary, meta=meta, top=args.top)
    report += '\n## Comparison vs previous profile\n\n'
    if previous is None:
        report += ('No earlier `profile_*.json` was found in the output directory — this run '
                   'is the baseline. The next run will be diffed against it.\n')
    else:
        previous_summary = json.loads(previous.read_text(encoding='utf-8'))
        report += (f'Baseline: `{previous.name}`\n\n'
                   + compare_profiles.render(previous_summary, summary) + '\n')
    md_path.write_text(report, encoding='utf-8')

    log('')
    log(f'Wrote {prof_path}')
    log(f'Wrote {json_path}')
    log(f'Wrote {md_path}')
    log(f'Wrote {log_path}')
    if previous is not None:
        log(f'Compared against {previous.name}')
    else:
        log('No previous profile found — this run is the baseline.')
    log('')
    log(f"capture={summary['run']['duration_ms']:,.1f}ms wall={wall_seconds:,.2f}s "
        f"threads={len(summary['threads'])} blocks={total_blocks:,}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))