---
name: cpp-easy-profiler-guide
description: Comprehensive guide for integrating and instrumenting the easy_profiler C++ library (v2.1.0) and analyzing its captures, cross-platform (Windows/Linux/macOS). Use when adding, editing, or reviewing EASY_* instrumentation macros or easy/profiler.h includes, linking or configuring easy_profiler builds (CMake, vcpkg, MSBuild), setting up profiling build configurations, capturing, parsing, or summarizing .prof files, debugging empty or missing captures, or comparing C++ performance before/after a change. Bundled stdlib-only Python scripts summarize .prof captures and diff runs.
---

# easy_profiler C++ Integration & Instrumentation Guide

Guide an application through the full profiling loop: **integrate → instrument →
capture → analyze → optimize**. Targets **easy_profiler v2.1.0** (the version
pinned by the vcpkg port `easy-profiler`). The deep reference is
[references/easy-profiler-overview.md](references/easy-profiler-overview.md) —
consult the sections cited below instead of guessing; every claim there was
validated against the v2.1.0 source and real captures.

## When to Load This Skill

> [!IMPORTANT]
> **Load this skill whenever:**
> - Writing, editing, or reviewing C++ code that contains `EASY_BLOCK`,
>   `EASY_FUNCTION`, `EASY_THREAD`, `EASY_EVENT`, `EASY_VALUE`,
>   `EASY_PROFILER_ENABLE`, or `#include <easy/...>` headers.
> - Adding profiling to a C++ project, or configuring a build that mentions
>   `easy_profiler`, `BUILD_WITH_EASY_PROFILER`, `profiler_gui`, or
>   `profiler_converter` (CMake, vcpkg, MSBuild, or manual).
> - A `.prof` capture needs parsing, summarizing, or comparing — use the bundled
>   scripts rather than writing a parser.
> - The task is to profile or optimize C++ performance with easy_profiler, set
>   up a Profile build configuration, or measure a change before/after.
> - Debugging an empty capture, missing blocks, or profiler-related compile or
>   link errors.
>
> **Do NOT load for:** other profilers (Tracy, VTune, perf, gprof, sampling
> profilers) unless migrating to easy_profiler; general C++ questions with no
> profiling component; non-C++ projects; `.prof` files from unrelated tools.

**Version gate.** Everything here describes **v2.1.0**. Upstream `develop`
(3.x line) renames API (`now()`→`timeNow()`, `version*()`→`apiVersion*()`) and
fixes a `toNanoseconds()` bug; the macros and `.prof` format are unchanged.
Detect which line a checkout uses via `profiler::versionName()` vs
`apiVersionName()` in `easy/profiler.h`, then apply overview §9 before writing
code against develop.

## Workflow A — Integrate the library

Pick the integration path for the project's build system (details and verified
snippets: overview §2):

| Build system | Approach |
|---|---|
| CMake | `find_package(easy_profiler CONFIG REQUIRED)` + `target_link_libraries(app PRIVATE easy_profiler)` — the target carries `BUILD_WITH_EASY_PROFILER` and all options. Preferred. |
| vcpkg | Port `easy-profiler` pins v2.1.0; the CMake toolchain wires the target automatically. |
| MSBuild / `.vcxproj` | No propagation: add `BUILD_WITH_EASY_PROFILER` to `<PreprocessorDefinitions>`, the include dir, and the link library **by hand**, per configuration. |
| Manual / other | Include path + `BUILD_WITH_EASY_PROFILER` define + link the lib; replicate header-affecting `EASY_OPTION_*` defines (overview §2.4). |

Rules that prevent the most common integration failures:

1. **`BUILD_WITH_EASY_PROFILER` is per translation unit.** A TU compiled without
   it records nothing even when the library is linked. If code is mysteriously
   absent from a profile, check that TU's defines first.
2. **Gate the link, keep the headers.** To make profiling optional per
   configuration, link `easy_profiler` only in the profiling config but keep its
   include directory in all configs — the macros still need `easy/profiler.h`
   to compile away (overview §2.4 has the verified CMake pattern and a
   wrapper-header alternative).
3. **Windows static builds** need `EASY_PROFILER_STATIC` defined in every
   consumer, or `__declspec(dllimport)` link errors follow.
4. **Profile an optimized build** (Release/RelWithDebInfo with debug info, or a
   dedicated Profile configuration). Debug timings are not representative.
5. Building the library itself: `cmake -B build -DEASY_PROFILER_NO_GUI=ON
   -DEASY_PROFILER_NO_SAMPLES=ON` for a headless build; GUI needs Qt5. CMake
   option table: overview §2.3. CMake ≥ 4 requires
   `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` for the v2.1.0 tag.

## Workflow B — Instrument the code

Apply this checklist (full API: overview §3; minimal verified program: §3.7):

1. `EASY_MAIN_THREAD;` in `main`; `EASY_THREAD("Name");` at the top of every
   worker thread's entry function.
2. Wrap each unit of work (frame, request, job) in one named **top-level**
   block: `{ EASY_BLOCK("Frame"); ... }`. Add `EASY_FUNCTION()` /
   `EASY_BLOCK("...")` below it.
3. `EASY_PROFILER_ENABLE;` **before the outermost block opens** (see the frame
   rule below).
4. Let the outermost blocks **close** (leave their scope or `EASY_END_BLOCK;`).
5. `profiler::dumpBlocksToFile("capture.prof");` — once, after all interesting
   work including destructors has run. Returns block count; **0 = failure or
   nothing captured**.
6. Analyze the file (Workflow C).

**The frame rule — the #1 source of empty captures** (overview §1.3):
capture state is honoured only at *top-level block boundaries*, and only
*completed* top-level frames are dumped. A block opened before
`EASY_PROFILER_ENABLE` suppresses everything nested inside it; a block still
open at dump time is lost **together with its closed children**. Classic trap:
`EASY_FUNCTION()` in `main` + dump inside `main` → 0 blocks. Enable first, put
the work in a closed inner block, dump after it closes.

Granularity and naming rules:

- Instrument functions taking microseconds or more; prune noisy subtrees with
  `profiler::OFF_RECURSIVE` / `ON_WITHOUT_CHILDREN`, keep essentials with
  `FORCE_ON` (flag table: overview §3.3).
- Prefer **string literals** for block names; run-time names are copied into
  every record. **One block per source line** — two blocks on one line share a
  descriptor and the second silently takes the first's name (overview §3.2).
- Colors: `profiler::colors::Red` (**plural** namespace), or raw `0xAARRGGBB`.
- Data goes in `EASY_VALUE` / `EASY_ARRAY` / `EASY_TEXT` (compile-time names
  only, ≤ 2816 bytes; `#include <easy/arbitrary_value.h>`), never formatted
  into run-time block names (overview §3.5).
- Repeated captures: enable → work → dump per window; the dump **disables
  capture and clears the buffers** (overview §4.2).
- Live GUI capture instead of files: `profiler::startListen()` (port 28077),
  connect from `profiler_gui` (overview §4.3).

## Workflow C — Capture and analyze

Choose the tool by the question being answered:

| Question | Tool |
|---|---|
| "Which blocks are hot? How did my change affect them?" | `prof_summary.py` — aggregated summary JSON + Markdown report, kilobyte-sized regardless of capture length |
| "What happened when? Why was this frame slow?" | `profiler_gui` — per-thread timeline, call tree, value tracks (overview §5.1) |
| "I need every block instance for custom tooling" | `profiler_converter INPUT.prof [OUT.json]` — full event-level JSON, can reach gigabytes; **exits 0 even when the input is missing** — check the output exists (overview §5.2) |
| "I need custom aggregation in C++" | `easy/reader.h` `fillTreesFromFile(..., gather_statistics=true, ...)` (overview §5.3) |

Summarize a capture (no external tools needed — the script parses the binary
format directly):

```bash
python "<skill-dir>/scripts/prof_summary.py" capture.prof --json summary.json --md report.md
```

Read the report by **`self_ms` + `pct_of_thread`**: high self time = the block
is expensive in its own right; high total with low self = its children are the
cost. Schema and aggregation semantics:
[references/summary-schema.md](references/summary-schema.md).

## Workflow D — Optimize loop

1. **Baseline:** build the instrumented configuration, then run the workload
   through the orchestrator:

   ```bash
   python "<skill-dir>/scripts/run_profile.py" --out-dir artifacts -- ./app --profile {prof}
   ```

   `{prof}` is replaced with a timestamped target path; for apps that dump to a
   fixed path use `--prof out.prof` instead. Each run writes
   `profile_<ts>.prof/.json/.md/.log` into `--out-dir`.
2. **Change the code**, rebuild, re-run the same command with the **same
   workload**. The report automatically embeds a before/after comparison
   against the most recent previous run.
3. **Judge the diff:** look at Δself and call counts. Changed call counts
   usually mean the workload changed, not the code. Use `--tag NAME` for sweep
   arms (skips the auto-diff), then compare arms explicitly:

   ```bash
   python "<skill-dir>/scripts/compare_profiles.py" before.json after.json --self
   ```
4. Repeat until the hot rows are flat. Keep the `.log` files — they carry the
   app's own telemetry that the summary does not.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Dump returns 0 / empty capture | Frame rule: block opened before enable, or dump inside a still-open top-level block | Enable before the outermost block; dump after frames close (overview §1.3, §8.1) |
| Second capture is empty | Dump disables capture and clears buffers | `EASY_PROFILER_ENABLE` again before the next window |
| Whole file/TU missing from profile | TU compiled without `BUILD_WITH_EASY_PROFILER` | Fix that TU's defines (per-TU switch) |
| `'profiler::color' has not been declared` | Singular namespace | `profiler::colors::Red` (plural) |
| `'else' without a previous 'if'` | `EASY_PROFILER_ENABLE`/`EASY_END_BLOCK`/`EASY_SET_*` already end in `;` | Wrap in braces: `if (c) { EASY_PROFILER_ENABLE; } else ...` |
| Reader/converter fails on a valid capture | Nesting deeper than **254** levels | Prune deep recursion with `OFF_RECURSIVE` |
| Crash with long dynamic names or big values | Run-time names / value payloads > **2816** bytes | Short literals; split arrays; or build with the truncate/check options (overview §2.3) |
| `toNanoseconds()` wrong by 10⁶ on Linux/macOS | v2.1.0 bug (runtime helper only; files are fine) | `toMicroseconds(t) * 1000` (overview §7.2) |
| Two blocks share one name | Both on one source line | One block per line |
| ETW/context-switch errors on Windows | Event tracing needs Administrator | `EASY_SET_EVENT_TRACING_ENABLED(false);` **before** `EASY_PROFILER_ENABLE` |

Full troubleshooting matrices: overview §8.

## Scripts

Python 3.8+, **standard library only**. `<skill-dir>` is the directory
containing this SKILL.md. Full CLI reference and schemas:
[references/summary-schema.md](references/summary-schema.md).

- **`scripts/prof_summary.py`** — parse a `.prof` into an aggregated summary
  JSON + Markdown report (one row per thread/block, self/total/median/pct).
  Also importable (`parse`, `summarize`, `render_report`) for custom analysis.

  ```bash
  python "<skill-dir>/scripts/prof_summary.py" capture.prof --json s.json --md r.md [--top N]
  ```
- **`scripts/compare_profiles.py`** — Markdown before/after table of two
  summary JSONs; run-level rows first, noise filter, NEW/REMOVED markers,
  optional self-time columns.

  ```bash
  python "<skill-dir>/scripts/compare_profiles.py" before.json after.json [--out diff.md] [--min-ms 1.0] [--self]
  ```
- **`scripts/run_profile.py`** — run any instrumented app, persist its log,
  summarize the capture, and auto-embed the comparison vs the previous run.
  Does not build — build the instrumented configuration first.

  ```bash
  python "<skill-dir>/scripts/run_profile.py" --out-dir artifacts [--tag NAME] -- <command with {prof}>
  python "<skill-dir>/scripts/run_profile.py" --out-dir artifacts --prof fixed.prof -- <command>
  python "<skill-dir>/scripts/run_profile.py" --out-dir artifacts --list
  ```

## References

- **[references/easy-profiler-overview.md](references/easy-profiler-overview.md)** —
  the authoritative deep reference (validated against v2.1.0 source and real
  runs). Section map:

  | § | Topic |
  |---|---|
  | 1 | Mental model, **frame rule**, cost when disabled |
  | 2 | Building, CMake options, consumption patterns, compile-time on/off |
  | 3 | Full instrumentation API: blocks, names, colors, flags, events, values, threads |
  | 4 | Capture control, dump semantics, network mode, startup profiling, FPS queries, context switches |
  | 5 | Analysis: GUI, converter JSON schema, C++ reader/writer APIs |
  | 6 | `.prof` binary format spec + tested Python reference parser |
  | 7 | Platform/timing notes (timers, `toNanoseconds` bug, symbol clashes, memory) |
  | 8 | Pitfalls, troubleshooting matrices, practical guidance |
  | 9 | v2.1.0 vs develop (3.x) API differences |
  | 10 | Quick reference: all macros, functions, defines, checklist |

  Load only the needed section, e.g. `grep -n "^## " references/easy-profiler-overview.md`
  to locate line ranges, then read that range.
- **[references/summary-schema.md](references/summary-schema.md)** — summary
  JSON field semantics, aggregation rules and limitations, comparison-table
  semantics, full script CLI reference.