# easy_profiler — Research Notes

Research for integrating the [easy_profiler](https://github.com/yse/easy_profiler) instrumentation
profiler into **VideoDeduper.Lib**.

- **Library version in use: v2.1.0** (the version pinned by the vcpkg port `easy-profiler`).
- Upstream `develop` is now 3.x, which **renames and removes** API (e.g. the `now()` /
  `toNanoseconds()` clashes). **Do not follow the develop-branch documentation** — everything in
  this document describes v2.1.0, which is what is compiled into this repository.

---

## 1. Overview

easy_profiler is a lightweight cross-platform instrumentation profiler for C++. You do not sample;
you explicitly mark up the code with scoped macros, the library records begin/end timestamps
per thread, and you later either stream the data to a GUI or **dump it to a `.prof` file**.

Upstream claims (v2.1.0 `README.md`):

| Property | Value |
|---|---|
| Overhead per block | ~15 ns/block (Intel i7-5930K 3.5 GHz, Win7) |
| Working overhead | 1–2 % of execution when capturing |
| Memory per block | ~25 bytes (12 M blocks ≈ 300 MB) |
| Overhead when disabled | none — macros short-circuit, capture is a runtime flag |
| Context-switch capture | ETW on Windows (requires **Administrator**); systemtap on Linux |
| License | Dual MIT / Apache-2.0 |

Two independent collection modes:

1. **Streaming over network** — profiled app calls `profiler::startListen()`; the GUI connects to
   TCP port `28077`, presses *Start capture* / *Stop capture*.
2. **Dump to file** — profiled app calls `EASY_PROFILER_ENABLE` and later
   `profiler::dumpBlocksToFile("test_profile.prof")`. **This is the mode VideoDeduper uses.**

Because capture is a runtime flag, the macros are safe to leave compiled in: a build with
`BUILD_WITH_EASY_PROFILER` defined but capture never enabled behaves like a no-op build.

---

## 2. Usage

### 2.1 Enabling the instrumentation at compile time

The macros only exist if **`BUILD_WITH_EASY_PROFILER` is defined for the translation unit** that
uses them. When it is not defined, every macro in this section expands to nothing (see
`easy/profiler.h`, the `#else` branch), and the `profiler::*` functions become inline no-ops.

- With **CMake**, `find_package(easy_profiler CONFIG REQUIRED)` + `target_link_libraries(... easy_profiler)`
  is enough: the imported target carries `BUILD_WITH_EASY_PROFILER=1` in its
  `INTERFACE_COMPILE_DEFINITIONS` (along with the `EASY_OPTION_*` configuration).
- With **MSBuild** there is no such propagation. The macro must be added to
  `<PreprocessorDefinitions>` by hand, together with the include directory and the link library.

In this repo the macro is defined **only in the `Profile|x64` configuration**, so Debug and Release
builds contain no instrumentation at all.

### 2.2 Inserting blocks

```cpp
#include <easy/profiler.h>

void foo()
{
    EASY_FUNCTION(profiler::colors::Magenta);   // block named "foo"
    // ...
}

void bar()
{
    EASY_BLOCK("Calculating sum");              // block with default color (Amber100)
    int sum = 0;
    for (int i = 0; i < 10; ++i) {
        EASY_BLOCK("Addition", profiler::colors::Red);   // scoped; no EASY_END_BLOCK needed
        sum += i;
    }
    EASY_END_BLOCK;                             // end of "Calculating sum"

    EASY_BLOCK("Calculating multiplication", profiler::colors::Blue500);
    int mul = 1;
    for (int i = 1; i < 11; ++i) mul *= i;
    // EASY_END_BLOCK not needed: blocks end in their destructor at the closing brace
}

void baz() { EASY_FUNCTION(0xfff080aa); }       // custom ARGB colour
```

Key points:

- **`EASY_FUNCTION(...)`** creates a block automatically named after the function. It must be the
  **first statement** of the function. An optional colour may be passed.
- **`EASY_BLOCK(name, ...)`** is a scoped block — it ends when the enclosing scope ends. `name` may
  be a compile-time string or a run-time `const char*` (a run-time name is copied into the block
  record and costs a little more).
- **`EASY_END_BLOCK`** ends the most recently opened block explicitly. Only needed when the block
  does not end at a closing brace (or with the non-scoped form).
- **`EASY_NONSCOPED_BLOCK(name, ...)`** begins a block that is not tied to a scope; it *must* be
  ended manually with `EASY_END_BLOCK`, possibly in another function.
- Colours come from the Google Material palette in `profiler::colors::` (e.g. `Red`, `Blue500`,
  `Amber`, `BlueGrey`, `DeepOrange`), or as a raw ARGB `uint32_t`. Default is `Amber100`.

### 2.3 Enable flags

The last variadic arguments of `EASY_FUNCTION` / `EASY_BLOCK` / `EASY_EVENT` control whether the
block is recorded:

| Flag | Meaning |
|---|---|
| `profiler::ON` | enabled (default) |
| `profiler::OFF` | disabled now, but can be toggled later from the GUI |
| `profiler::FORCE_ON` | recorded even if the parent is disabled |
| `profiler::ON_WITHOUT_CHILDREN` | this block is recorded, its children are not |
| `profiler::OFF_RECURSIVE` | this block *and* all its children are disabled |

### 2.4 Events and values

```cpp
#include <easy/profiler.h>
#include <easy/arbitrary_value.h>   // EASY_VALUE / EASY_ARRAY

EASY_EVENT("Cache miss");                       // zero-duration marker

EASY_VALUE("id", m_id);                         // attach a scalar to the current block
EASY_VALUE("N", N, EASY_VIN("N"));              // EASY_VIN keeps the value id stable
constexpr auto Size = sizeof(Vector3) / sizeof(float);
EASY_ARRAY("position", &m_position.x, Size, profiler::color::Red);
```

### 2.5 Thread naming

Threads appear in the GUI/filesystem by OS thread id; naming them makes a multi-threaded profile
readable. This is essential for VideoDeduper, whose pipeline spans several thread kinds.

```cpp
EASY_THREAD("VD.Decode");        // register + name the current thread (once)
EASY_THREAD_SCOPE("Worker");     // same, plus a guard that emits "ThreadFinished" on scope exit
EASY_MAIN_THREAD;                // EASY_THREAD("Main")
```

### 2.6 Capture control and dumping

```cpp
EASY_PROFILER_ENABLE;                                  // == profiler::setEnabled(true)
EASY_PROFILER_DISABLE;                                 // == profiler::setEnabled(false)

EASY_SET_EVENT_TRACING_ENABLED(false);                 // skip ETW context-switch capture

profiler::dumpBlocksToFile("VideoDeduper.prof");       // returns uint32_t blocks written
```

Semantics of **`profiler::dumpBlocksToFile(path)`** (from `profile_manager.cpp`):

1. If capture is running it is **stopped** (`setEnabled(false)`) and `end_time` is stamped.
2. It **sleeps 20 ms** to let in-flight `storeBlock()` calls on other threads finish.
3. It takes the internal spin locks, computes the total block count, and writes the whole file.
4. It **clears the accumulated blocks** for every thread (the capture buffer is emptied).
5. Returns the number of blocks written; **`0` means nothing was profiled or the file could not be
   opened**.

Consequences for integration: call it **once, at the very end of the process**, after all
interesting work (including destructors) has run, and do not expect a second dump to contain the
first run's data.

---

## 3. The `.prof` binary format (v2.1.0)

All multi-byte integers are little-endian, written with `std::ostream::write` of the raw struct.
Everything is naturally packed for x64 (`#pragma pack(push,1)` is used around the record structs),
so the layouts below are byte-exact.

### 3.1 Signature and version

| Field | Type | Notes |
|---|---|---|
| `signature` | `uint32` | `0x45617379` — ASCII `"Easy"` (`'E'<<24 \| 'a'<<16 \| 's'<<8 \| 'y'`) |
| `version` | `uint32` | `(major<<24) \| (minor<<16) \| patch`; v2.1.0 writes `0x02010000` |

The reader requires `version >= 0x00010000`; the version selects which header layout follows.

### 3.2 Header

Because `version >= 2.1.0`, the `readHeader_v2_1` layout applies:

| # | Field | Type | Notes |
|---|---|---|---|
| 1 | `pid` | `uint64` | process id |
| 2 | `cpu_frequency` | `int64` | QPC frequency on Windows; `0` means timestamps are already ns |
| 3 | `begin_time` | `uint64` | capture start, in ticks |
| 4 | `end_time` | `uint64` | capture end, in ticks |
| 5 | `memory_size` | `uint64` | total bytes of the block records that follow |
| 6 | `descriptors_memory_size` | `uint64` | total bytes of the descriptor records |
| 7 | `blocks_count` | `uint32` | total blocks + context switches |
| 8 | `descriptors_count` | `uint32` | number of descriptors |
| 9 | `threads_count` | `uint32` | number of thread sections |
| 10 | `bookmarks_count` | `uint16` | GUI-created bookmarks (dump writes `0`) |
| 11 | `padding` | `uint16` | must be `0` |

> Historical layouts: `< 2.0.0` moves `pid` after `version` and orders the block/memory fields
> differently (`readHeader_v1`); `< 1.3.0` uses a 32-bit thread id. Only the v2.1 layout is needed
> here.

### 3.3 Descriptors

Written one after another, exactly `descriptors_count` of them:

| Field | Type | Notes |
|---|---|---|
| `sz` | `uint16` | size of the descriptor payload below, in bytes |
| `id` | `uint32` | block id used by block records |
| `line` | `int32` | source line |
| `color` | `uint32` | ARGB |
| `type` | `uint8` | `0` = Event, `1` = Block, `2` = Value |
| `status` | `uint8` | enable flag |
| `name_len` | `uint16` | length of the name **including** the trailing `'\0'` |
| `name` | `char[name_len]` | zero-terminated block name |
| `file` | `char[…]` | zero-terminated source filename (takes the remaining bytes: `sz - 12 - name_len`) |

A descriptor id maps a block record to its name/file/line. `sz` is a convenient way to skip a
descriptor without knowing the filename length up-front.

### 3.4 Threads

Repeated `threads_count` times:

| Field | Type | Notes |
|---|---|---|
| `thread_id` | `uint64` | OS thread id |
| `name_size` | `uint16` | thread name length including `'\0'` (minimum `1` for the empty name) |
| `name` | `char[name_size]` | zero-terminated thread name |
| `cs_count` | `uint32` | number of context-switch records |
| — `cs` records | | `cs_count` × (`uint16 sz`, then `sz` bytes of `{uint64 begin; uint64 end; uint64 tid}` + name) |
| `blocks_count` | `uint32` | number of block records in this thread |
| — block records | | `blocks_count` × (`uint16 sz`, then `sz` bytes of `{uint64 begin; uint64 end; uint32 id}` + zero-terminated run-time name) |

Note that the **run-time name** appended to each block is empty for `EASY_FUNCTION` /
`EASY_BLOCK` with a compile-time literal; the real name then comes from the descriptor. It is
non-empty only when a run-time name was supplied.

Context-switch records are absent in this integration — event tracing is explicitly disabled.

### 3.5 Trailer

| Field | Type | Notes |
|---|---|---|
| `signature` | `uint32` | `0x45617379` again, marks the end of the thread sections |
| bookmarks | | only if `bookmarks_count != 0`; the dumper writes `0`, so normally absent |

### 3.6 Timestamp conversion

Durations and timestamps in the file are in **CPU ticks** (QPC on Windows). Convert with:

```
nanoseconds = ticks * 1'000'000'000 / cpu_frequency
```

The `easy/reader.h` API performs this conversion **in place** while loading, so values obtained
from the reader are already in nanoseconds. If `cpu_frequency == 0` the ticks are already
nanoseconds.

---

## 4. Local tooling

The v2.1.0 Windows release is checked into this repo under `tools/`:

```
tools/easy_profiler-v2.1.0-msvc15-win64/
├── bin/
│   ├── profiler_gui.exe            # timeline GUI (Qt5) — opens .prof files
│   ├── profiler_converter.exe      # .prof -> JSON converter
│   ├── profiler_sample.exe         # tiny demo app that writes a .prof
│   ├── profiler_sample_network.exe # demo app using the network mode
│   ├── easy_profiler.dll
│   ├── easy_profiler.lib
│   └── Qt5*.dll, platforms/, imageformats/, iconengines/   # GUI runtime
├── include/easy/                   # profiler.h, reader.h, writer.h, arbitrary_value.h, ...
├── lib/easy_profiler.lib
└── lib/cmake/easy_profiler/        # CMake package
```

The `vcpkg`-installed copy (used by the build) lives under
`VideoDeduper.Lib/vcpkg_installed/x64-windows/x64-windows/`.

---

## 5. Parsing a `.prof` file

### 5.1 GUI (human)

```
tools\easy_profiler-v2.1.0-msvc15-win64\bin\profiler_gui.exe
```

`File → Open` the `.prof`. The GUI shows a per-thread timeline, a hierarchical call tree with
inclusive/self times, call counts, min/median/max durations, and per-block statistics. It can also
connect live to a running process via `profiler::startListen()`.

### 5.2 Converter CLI (raw dump)

`profiler_converter.exe` takes **positional** arguments:

```
profiler_converter.exe INPUT_PROF_FILE [OUTPUT_JSON_FILE]
```

- `INPUT_PROF_FILE` — required.
- `OUTPUT_JSON_FILE` — optional; **if omitted the JSON is printed to stdout**.

Example:

```
tools\easy_profiler-v2.1.0-msvc15-win64\bin\profiler_converter.exe VideoDeduper.prof VideoDeduper.json
```

Output schema (from `easy_profiler_converter/converter.cpp`):

```json
{
  "version": "2.1.0",
  "timeUnits": "ns",
  "blockDescriptors": [
    { "id": 3, "name": "vd::VideoStream::next", "type": 1,
      "color": "0xff4caf50", "sourceFile": "VideoStream.cpp", "sourceLine": 297 }
  ],
  "threads": [
    { "threadId": 41208, "threadName": "VD.Decode",
      "children": [
        { "id": 87, "name": "vd::VideoStream::next", "start": 40213, "stop": 40241,
          "descriptor": 3,
          "children": [ /* nested blocks */ ] }
      ] }
  ],
  "bookmarks": []
}
```

**Important limitation:** this is a *full event-level dump*. Every single block **instance** is
emitted, with no aggregation. VideoDeduper's per-frame instrumentation produces hundreds of
thousands of records for a real video, so the JSON can reach tens of megabytes. It is excellent for
tooling and for full-fidelity inspection, but it is **not** directly consumable by an LLM — which is
why `--json` writes the aggregated summary described in §6 instead.

### 5.3 Programmatic (C++)

`easy/reader.h` is the public API:

```cpp
#include <easy/reader.h>

std::atomic<int> progress(0);
profiler::BeginEndTime begin_end;
profiler::SerializedData serialized_blocks, serialized_descriptors;
profiler::descriptors_list_t descriptors;
profiler::blocks_t blocks;
profiler::thread_blocks_tree_t trees;
profiler::bookmarks_t bookmarks;
uint32_t descriptors_count = 0, version = 0;
profiler::processid_t pid = 0;
std::stringstream log;

auto count = fillTreesFromFile(progress, "in.prof", begin_end, serialized_blocks,
                               serialized_descriptors, descriptors, blocks, trees, bookmarks,
                               descriptors_count, version, pid,
                               /*gather_statistics=*/true, log);
```

What you get back:

- `trees` : `unordered_map<thread_id_t, BlocksTreeRoot>` — one root per thread with `thread_name`,
  `profiled_time` (sum of top-level block durations), `wait_time`, `blocks_number`, `frames_number`,
  `depth`, plus `children` (indices into `blocks`).
- `blocks` : flat `vector<BlocksTree>`; `node` points at the `SerializedBlock` —
  `node->name()`, `node->begin()`, `node->end()`, `node->duration()`, `node->id()`.
- `descriptors` : `vector<SerializedBlockDescriptor*>` — `name()`, `file()`, `line()`, `type()`,
  `color()`; indexed by block id.
- Per-block statistics, present when `gather_statistics == true`:
  - `per_thread_stats` — aggregated over all calls on that thread, keyed by block id
    (**same-name blocks share one `BlockStatistics` instance**).
  - `per_parent_stats`, `per_frame_stats` — aggregated within the parent / the top-level frame.

  `BlockStatistics` (`easy/reader.h`) carries `total_duration`, `median_duration`,
  `total_children_duration`, `calls_number`, `min_duration_block`, `max_duration_block`, and the
  helper `average_duration()`.

`gather_statistics=true` is exactly what an aggregated summary needs — no manual aggregation
required. The official `reader/main.cpp` sample is the minimal usage reference.

### 5.4 Raw

§3 is a complete specification; a third-party parser is a straightforward sequential reader of the
sections above.

---

## 6. Aggregated summary JSON (LLM-facing)

Written by `vd::profiling::write_summary()` (`--json`). It deliberately trades fidelity for
**size and analyzability**: one record per (thread, block name), not one per block instance, so the
file stays in the kilobyte range regardless of run length.

```json
{
  "run": {
    "prof_file": "VideoDeduper.prof",
    "duration_ms": 41230.512,
    "pid": 12345
  },
  "threads": [
    {
      "id": 41208,
      "name": "VD.Decode",
      "profiled_ms": 39800.206,
      "blocks_number": 2401,
      "blocks": [
        {
          "name": "vd::VideoStream::next",
          "file": "VideoStream.cpp",
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

Field reference:

| Field | Meaning |
|---|---|
| `run.duration_ms` | wall time of the capture (`end_time - begin_time`), ms |
| `run.pid` | process id recorded in the file |
| `threads[].id` / `.name` | OS thread id and the name registered via `EASY_THREAD` / `EASY_MAIN_THREAD` |
| `threads[].profiled_ms` | sum of the thread's top-level block durations |
| `threads[].blocks_number` | total blocks recorded on the thread (including children) |
| `blocks[].name` / `.file` / `.line` | descriptor identity of the block |
| `blocks[].calls` | number of times the block was entered |
| `blocks[].total_ms` | sum of all call durations (inclusive of children) |
| `blocks[].avg_ms` / `.median_ms` | `total / calls`, and the median call duration |
| `blocks[].self_ms` | `total_ms - total_children_duration` — the block's own cost |
| `blocks[].pct_of_thread` | `total_ms / threads[].profiled_ms × 100` — share of the thread |

Sorting: threads by `profiled_ms` descending, blocks by `total_ms` descending, so the first entries
of each list are the hottest. Times are milliseconds with three decimals.

For analysis, `pct_of_thread` plus `self_ms` is the key pair: it separates "this block is expensive
in its own right" from "this block is expensive because its children are".

---

## 7. Gotchas

- **`BUILD_WITH_EASY_PROFILER` is mandatory** for the macros to do anything, and it does not
  propagate from vcpkg to MSBuild. In this repo it is set **only for `Profile|x64`**; Debug and
  Release builds compile all instrumentation away. Pass `-DConfiguration=Profile` to profile.
- **One dump per capture.** `dumpBlocksToFile()` clears the accumulated blocks, so capture must be
  re-enabled for a second run.
- **Dump last.** Stop capture (which the dump does) only after destructors that you care about have
  run. All work must also happen *after* `EASY_PROFILER_ENABLE`, otherwise the blocks are dropped.
- **Stack depth limit is 254** levels below the thread root; exceeding it aborts the dump with a
  "Stack depth exceeded" error.
- **Run-time block names** are limited to `MAX_BLOCK_DATA_SIZE` (`2816` bytes); long names are
  truncated/faulted depending on `EASY_OPTION_TRUNCATE_LONG_RUNTIME_NAMES`. Prefer compile-time
  literals.
- **ETW context-switch tracing is on by default on Windows and requires Administrator.** It is
  disabled in this integration (`EASY_SET_EVENT_TRACING_ENABLED(false)`) — VTune covers
  context-switch analysis. If it is ever enabled, the `.prof` grows the `cs` sections described in
  §3.4.
- **`profiler::now()` is `now()` at global scope** in 2.x, which can clash with system/3rd-party
  headers; 3.x renamed it. Irrelevant for v2.1.0 as used here, but do not upgrade casually.
- **The file header version governs the layout.** A parser must branch on `version` before reading
  the header (see the note in §3.2) — v1.x files are not laid out like v2.1 files.
- **The GUI must match the file version.** `profiler_gui.exe` from the v2.1.0 release reads the
  v2.1.0 files produced here.
