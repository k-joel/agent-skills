# Summary JSON schema and script reference

I/O contract for the bundled analysis scripts. All scripts are Python 3.8+,
standard library only, and read the easy_profiler **v2.1.x** `.prof` format
directly — no `profiler_converter` or other external tool is required.

- [Summary JSON schema](#summary-json-schema)
- [Aggregation rules and limitations](#aggregation-rules-and-limitations)
- [Comparison table semantics](#comparison-table-semantics)
- [prof_summary.py](#prof_summarypy)
- [compare_profiles.py](#compare_profilespy)
- [run_profile.py](#run_profilepy)

---

## Summary JSON schema

Written by `prof_summary.py --json` (and by `run_profile.py`). One record per
(thread, block descriptor) — not per block instance — so the file stays in the
kilobyte range regardless of run length.

```json
{
  "run": {
    "prof_file": "capture.prof",
    "duration_ms": 41230.512,
    "pid": 12345
  },
  "threads": [
    {
      "id": 41208,
      "name": "Worker",
      "profiled_ms": 39800.206,
      "blocks_number": 2401,
      "blocks": [
        {
          "name": "process",
          "file": "pipeline.cpp",
          "line": 297,
          "calls": 1187,
          "total_ms": 36100.441,
          "avg_ms": 30.413,
          "median_ms": 29.100,
          "self_ms": 35900.100,
          "pct_of_thread": 90.7
        }
      ]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `run.prof_file` | file name of the parsed capture |
| `run.duration_ms` | wall time of the capture (`end_time − begin_time` from the file header), ms |
| `run.pid` | process id recorded in the file |
| `threads[].id` / `.name` | OS thread id; name registered via `EASY_THREAD` / `EASY_MAIN_THREAD` (empty string if never named) |
| `threads[].profiled_ms` | sum of the thread's **top-level** block durations |
| `threads[].blocks_number` | total records on the thread, including children, events and values |
| `blocks[].name` | effective block name: run-time name if non-empty, else the descriptor name |
| `blocks[].file` / `.line` | descriptor source location |
| `blocks[].calls` | number of times the block was entered |
| `blocks[].total_ms` | sum of all call durations (**inclusive** of children) |
| `blocks[].avg_ms` | `total / calls` |
| `blocks[].median_ms` | median call duration |
| `blocks[].self_ms` | `total − sum of direct children durations` — the block's own cost |
| `blocks[].pct_of_thread` | `total_ms / profiled_ms × 100` — share of the thread |

Sorting: threads by `profiled_ms` descending, blocks by `total_ms` descending —
the first entries of each list are the hottest. Times are milliseconds rounded
to three decimals; `pct_of_thread` to one.

For analysis, **`pct_of_thread` plus `self_ms` is the key pair**: it separates
"this block is expensive in its own right" from "this block is expensive
because its children are".

## Aggregation rules and limitations

- **Grouping key is (thread, descriptor id)** — the same grouping the official
  C++ reader uses. The descriptor key is source `file:line`, so two blocks
  written on one source line share a row (and the first one's name wins).
  Run-time-named blocks created at the same line also aggregate into one row,
  named after the first-seen run-time name.
- Only **Block** records (type 1) are aggregated and ranked. Events (type 0,
  e.g. `ThreadFinished`) and values (type 2) count towards `blocks_number` but
  produce no rows. Value payloads are decoded by the parser API
  (`prof_summary.parse`) but not exported to the summary.
- Context-switch records are parsed but excluded from all statistics.
- `self_ms` excludes children **on the same thread only**: a block waiting on
  another thread reports the wait as self time.
- `pct_of_thread` is per-thread; rows from different threads are not comparable
  through it.
- Timestamps are converted from CPU ticks with the file's `cpu_frequency`
  (`ticks × 1e9 / freq`; `freq == 0` means already nanoseconds). Python integer
  arithmetic — no overflow.
- The parser reads the **v2.1.x layout** (version ≥ `0x02010000`, major 2) —
  what easy_profiler v2.1.0 writes. Older layouts (v1.x, v2.0), bad signatures,
  truncation and unknown descriptor ids are rejected with a clear error and
  non-zero exit.

## Comparison table semantics

`compare_profiles.py` renders a Markdown before/after table:

- Block rows are **aggregated across all threads by block name** (a block that
  ran on 4 workers becomes one row). This differs from the summary's
  per-thread rows — intentional, for change-level readability.
- Run-level rows come first: `run.duration_ms` and thread count.
- Columns: Block | Before (ms) | After (ms) | Delta (ms) | Change | Before calls
  | After calls; with `--self`, two extra columns Before/After self (ms).
- `Change` is the relative delta of `total_ms`; a zero baseline renders `new`
  (after > 0) or `n/a` (both 0).
- Blocks below `--min-ms` (default 1.0 ms) in **both** runs are hidden as noise.
- Blocks present in only one run are marked **(NEW)** / **(REMOVED)**.
- Ordering: before-`total_ms` descending (new blocks sort last).

Caveat: comparisons are only meaningful between runs of the **same workload**;
differing call counts usually mean the input changed, not the code.

## prof_summary.py

Parse a `.prof` and write the aggregated summary and/or a Markdown report.

```
python prof_summary.py INPUT.prof [--json OUT.json] [--md OUT.md] [--top N]
```

| Option | Default | Meaning |
|---|---|---|
| `--json` | — | write the summary JSON to this path |
| `--md` | — | write the Markdown report to this path |
| `--top` | 20 | rows in the report's top-blocks table |

With neither `--json` nor `--md`, the report is printed to stdout. Exit code 0
on success; non-zero with a diagnostic on parse errors.

Importable API:

```python
import prof_summary
header, threads = prof_summary.parse("capture.prof")   # raw trees, ns durations
summary = prof_summary.summarize(header, threads, "capture.prof")
report  = prof_summary.render_report(summary, meta=None, top=20)
```

`parse` returns the full tree (including events, decoded values and context
switches) for custom analysis; each node has `begin`/`end` (ticks), `dur` (ns),
`desc`, `name`, `children`, and optionally `value` or `runtime_name`.
`ProfParseError` is raised on malformed input.

## compare_profiles.py

Diff two summary JSONs (before / after) into a Markdown table.

```
python compare_profiles.py BEFORE.json AFTER.json [--out report.md] [--min-ms 1.0] [--self]
```

| Option | Default | Meaning |
|---|---|---|
| `--out` | stdout | write the Markdown table to this path |
| `--min-ms` | 1.0 | hide blocks below this total in both runs |
| `--self` | off | add before/after self-time columns |

Importable API: `render(before_summary, after_summary, min_ms=1.0, self_time=False) -> str`.

## run_profile.py

Run an instrumented application, then summarize and auto-compare against the
previous run. Produces four timestamped artifacts per run in `--out-dir`:

```
profile_<yy-mm-dd-hh-mm-ss>.prof   raw capture
profile_<yy-mm-dd-hh-mm-ss>.json   aggregated summary
profile_<yy-mm-dd-hh-mm-ss>.md     report (+ comparison vs previous run)
profile_<yy-mm-dd-hh-mm-ss>.log    the run's stdout + stderr (written even on failure)
```

```
python run_profile.py [--out-dir artifacts] [--tag NAME] [--top N] [--prof PATH] -- <command...>
python run_profile.py --out-dir artifacts --list
```

| Option | Default | Meaning |
|---|---|---|
| `--out-dir` | `artifacts` | artifact directory (created if missing) |
| `--prof` | — | fixed `.prof` path the app always dumps to; moved into `--out-dir` after the run |
| `--tag` | — | stem becomes `profile_<tag>_<ts>`; **skips** the previous-run comparison (for sweep arms) |
| `--top` | 20 | rows in the top-blocks table |
| `--list` | — | list captured profiles and exit |

Locating the capture — exactly one of:

- **`{prof}` placeholder** in the command: replaced with the timestamped target
  path. Use when the app accepts an output-path argument:
  `-- ./app --profile {prof}`
- **`--prof PATH`**: use when the app dumps to a hardcoded path:
  `--prof out.prof -- ./app`

Behaviour details:

- The previous baseline is the most recent `profile_*.json` by mtime, resolved
  **before** the new run; tagged runs never diff.
- A stale `.prof` at the target path is deleted before the run so an old
  capture cannot masquerade as a new one.
- The `.log` is written before any failure check — a crashed run keeps its
  output.
- Failure modes exit non-zero with guidance: app exit ≠ 0; no `.prof` produced;
  0 blocks captured (instrumentation/frame-rule checklist in the message).
- The script does **not build** — build the instrumented configuration first
  (build systems are project-specific).