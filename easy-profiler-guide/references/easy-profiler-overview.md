# easy_profiler — Comprehensive C++ Guide

A practical, project-independent reference for **easy_profiler** (`yse/easy_profiler`): a lightweight, block-based, instrumenting profiler for C++ with a Qt GUI, a JSON converter, and a programmatic reader/writer API.

- Upstream: <https://github.com/yse/easy_profiler>
- Covers: the **v2.1.0** release (latest tagged release), with notes on differences in the current `develop` branch (the "3.x" line).
- Licence: dual **MIT / Apache-2.0** (pick either).

> **How this guide was validated.** Every claim was checked against the v2.1.0 source. Where a claim concerns observable behaviour, v2.1.0 was built (core library + converter, GCC 13, x86-64 Linux) and exercised with test programs; the binary file format was parsed with an independent Python parser. Items that could **not** be exercised on Linux (Windows ETW context switches, Windows QPC timing, the Qt GUI) are taken from source and the upstream README, and are labelled *(source-read)* where it matters. Statements marked **Verified** were reproduced by running code.

---

## Table of contents

1. [What it is and how it works](#1-what-it-is-and-how-it-works)
2. [Building and integrating](#2-building-and-integrating)
3. [Instrumentation API](#3-instrumentation-api)
4. [Controlling capture and getting data out](#4-controlling-capture-and-getting-data-out)
5. [Analysing results](#5-analysing-results)
6. [The `.prof` binary format](#6-the-prof-binary-format)
7. [Platform and timing notes](#7-platform-and-timing-notes)
8. [Pitfalls and troubleshooting](#8-pitfalls-and-troubleshooting)
9. [v2.1.0 vs `develop` (3.x) differences](#9-v210-vs-develop-3x-differences)
10. [Quick reference](#10-quick-reference)

---

## 1. What it is and how it works

### 1.1 Key properties

| Property | Detail |
|---|---|
| Kind | Instrumenting profiler: you place macros; it records begin/end timestamps per block. |
| Cost | Upstream reports on the order of ~15 ns per block on a desktop CPU (an upstream figure, not measured here). Memory is allocated in chunks per thread. |
| Output | A binary `.prof` file (via `dumpBlocksToFile`) **or** a live stream to the GUI over TCP (default port **28077**). |
| Threads | Per-thread lock-free storage; threads are recorded independently and can be named. |
| Extras | Arbitrary values (`EASY_VALUE`), events/markers, per-block colours, per-block enable flags, frame-time (FPS) queries, optional OS context-switch capture. |
| Tooling | `profiler_gui` (Qt), `profiler_converter` (`.prof` → JSON), C++ `reader.h`/`writer.h` APIs. |
| Language | C++11. Thread-local storage is used where the compiler supports it. |

### 1.2 The mental model: blocks, frames, capture

- A **block** is a named time interval (`EASY_BLOCK`, `EASY_FUNCTION`, …). Blocks nest per thread, forming a tree.
- An **event** is a zero-duration marker (`EASY_EVENT`). A **value** is a timestamped piece of data (`EASY_VALUE`).
- A **frame** is a **top-level block**: the outermost open block on a thread. *Frames are the unit of capture* (see below).
- **Capture** is a global runtime switch. While it is off, instrumentation is skipped (but not entirely free — see §1.4).

### 1.3 The frame rule (the most important behaviour to understand)

Capture state is only honoured at **top-level block boundaries**, and data only becomes dumpable when its top-level block **closes**. Two consequences, both **Verified** by test:

1. **A top-level block opened *before* capture was enabled suppresses everything nested inside it** until it closes — even blocks that begin after capture was enabled.
   ```cpp
   {
       EASY_BLOCK("outer");        // top-level, opened while capture is OFF
       EASY_PROFILER_ENABLE;
       A();                        // NOT recorded (child of a pre-enable frame)
   }
   B();                            // recorded (new top-level frame after enable)
   ```
2. **A block that is still open when you dump is lost, together with its already-closed children.** Only *completed* top-level frames are written.
   ```cpp
   EASY_PROFILER_ENABLE;
   A();                            // completed frame  -> in the file
   {
       EASY_BLOCK("outer");
       B();                        // closed child of a still-open frame -> LOST
       profiler::dumpBlocksToFile("x.prof");   // "outer" and B() absent
   }
   ```

Practical rule: **enable capture before opening your outermost blocks, and dump after they have closed** (see §8 for the classic `EASY_FUNCTION()`-in-`main()` trap).

### 1.4 Cost when not capturing

- **Macro not enabled at all** (`BUILD_WITH_EASY_PROFILER` undefined, or `DISABLE_EASY_PROFILER` defined): every macro expands to nothing and the `profiler::` functions become inline no-ops. **No library is needed at link time** (**Verified**: such a build linked nothing and `profiler::versionName()` returned `"v0.0.0_disabled"`). The **headers are still required** to compile, unless you hide them behind your own wrapper (§2.4).
- **Compiled in but capture off:** blocks still pass through the begin/end path (thread registration, nesting bookkeeping, frame timing for the FPS API). Overhead is small but **not zero**.

---

## 2. Building and integrating

### 2.1 Requirements

- A C++11 compiler. CMake checks `thread_local` support: it is considered unavailable below GCC 4.8, Clang 3.3 or AppleClang 8.0. On such compilers CMake warns that implicit thread registration combined with `EASY_THREAD` (instead of `EASY_THREAD_SCOPE`) may leak memory or crash — use `EASY_THREAD_SCOPE` there.
- CMake ≥ 3.0 (the project declares 3.0; see note below).
- Qt 5 for the GUI only, for v2.1.0 (check the `develop` branch's README for its current Qt requirement).
- Windows: Visual Studio / MSVC, or MinGW. Linux/macOS: GCC / Clang.

> **CMake 4.x note.** v2.1.0 declares `cmake_minimum_required(VERSION 3.0)`. CMake 4 dropped compatibility with versions below 3.5 — **Verified**: configuring v2.1.0 on CMake 4.4 without a flag stops with "Compatibility with CMake < 3.5 has been removed". Add `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` to the configure command (this flag was used for the build that backed this guide; `develop` raises its minimum to 3.5, see §9).

### 2.2 Build commands

```bash
git clone https://github.com/yse/easy_profiler.git
cd easy_profiler
git checkout v2.1.0        # the tagged release; `develop` is newer (see §9)

# GUI and samples are optional; skip them for a headless build (no Qt needed)
cmake -B build -DCMAKE_BUILD_TYPE=Release -DEASY_PROFILER_NO_GUI=ON -DEASY_PROFILER_NO_SAMPLES=ON
cmake --build build -j
cmake --install build --prefix /opt/easy_profiler    # optional
```

Outputs land in `build/bin/`: `libeasy_profiler.so` (`easy_profiler.dll` on Windows), `profiler_converter`, and — if the GUI was not disabled — `profiler_gui`.

By default the core builds as a **shared** library (`BUILD_SHARED_LIBS=ON`).

### 2.3 CMake options

Top-level switches:

| Option | Default | Effect |
|---|---|---|
| `EASY_PROFILER_NO_GUI` | OFF | Do not build `profiler_gui` (no Qt required). |
| `EASY_PROFILER_NO_SAMPLES` | OFF | Do not build the sample applications. |
| `BUILD_SHARED_LIBS` | ON | Shared vs static core library. |
| `EASY_DEFAULT_PORT` | `28077` | Default TCP port for `startListen()` / GUI. |

Core-library behaviour options (each becomes an `EASY_OPTION_*` define):

| CMake option | Default | Resulting define | Meaning |
|---|---|---|---|
| `EASY_OPTION_LISTEN` | OFF | `EASY_OPTION_START_LISTEN_ON_STARTUP` | Start the network listener automatically at startup, so a GUI can connect without code changes. |
| `EASY_OPTION_PROFILE_SELF` | OFF | `EASY_OPTION_MEASURE_STORAGE_EXPAND` | Profile the profiler's own storage growth (adds `EasyProfiler.ExpandStorage` blocks). |
| `EASY_OPTION_PROFILE_SELF_BLOCKS_ON` | OFF | `EASY_OPTION_STORAGE_EXPAND_BLOCKS_ON` | Whether those self-profiling blocks are enabled by default. |
| `EASY_OPTION_TRUNCATE_RUNTIME_NAMES` | OFF | `EASY_OPTION_TRUNCATE_LONG_RUNTIME_NAMES` | Truncate over-long run-time block names to fit a storage chunk (slightly slower). With this OFF, a run-time name longer than 2816 characters (`EASY_MAX_SIZE_VALUE`) may crash; prefer `EASY_VALUE` for long text. |
| `EASY_OPTION_CHECK_MAX_VALUE_SIZE` | OFF | `EASY_OPTION_CHECK_MAX_VALUE_DATA_SIZE` | Silently **drop** `EASY_VALUE`/`EASY_ARRAY`/`EASY_STRING`/`EASY_TEXT` payloads larger than the chunk limit (slightly slower). With this OFF, payloads over 2816 bytes may crash; split big arrays instead. |
| `EASY_OPTION_LOG` | OFF | `EASY_OPTION_LOG_ENABLED` | Print profiler errors to stderr. |
| `EASY_OPTION_PRETTY_PRINT` | OFF | `EASY_OPTION_PRETTY_PRINT_FUNCTIONS` | `EASY_FUNCTION` uses the full signature (`__PRETTY_FUNCTION__`/`__FUNCSIG__`) as its name. |
| `EASY_OPTION_PREDEFINED_COLORS` | ON | `EASY_OPTION_BUILTIN_COLORS` | Provide the `profiler::colors::*` palette. |
| `EASY_OPTION_IMPLICIT_THREAD_REGISTRATION` | ON (OFF if no `thread_local`) | same | Register new threads when collecting context-switch events. |
| `EASY_OPTION_EVENT_TRACING` *(Windows)* | ON | `EASY_OPTION_EVENT_TRACING_ENABLED` | Default state of OS context-switch tracing. |
| `EASY_OPTION_LOW_PRIORITY_EVENT_TRACING` *(Windows)* | ON | `EASY_OPTION_LOW_PRIORITY_EVENT_TRACING` | Run the ETW tracing thread at low priority. |
| `EASY_OPTION_REMOVE_EMPTY_UNGUARDED_THREADS` *(Unix without `thread_local`)* | OFF | same | Remove empty unguarded thread records. Fixes a possible memory leak on such systems but **may crash the application**. |
| `BUILD_WITH_CHRONO_STEADY_CLOCK` / `BUILD_WITH_CHRONO_HIGH_RESOLUTION_CLOCK` | OFF | same | Use `std::chrono` instead of the native timer (see §7.1). |

### 2.4 Consuming the library

#### CMake (recommended)

```cmake
find_package(easy_profiler CONFIG REQUIRED)       # set CMAKE_PREFIX_PATH to the install prefix
target_link_libraries(my_app PRIVATE easy_profiler)
```

The imported target carries (**Verified** by querying an installed target), as **`INTERFACE_COMPILE_DEFINITIONS`**: `BUILD_WITH_EASY_PROFILER=1`, the version macros, `EASY_DEFAULT_PORT`, and (for static builds) `EASY_PROFILER_STATIC=1`. The `EASY_OPTION_*` settings that affect headers are exported as **`INTERFACE_COMPILE_OPTIONS`** (`-D…` flags). This matters: `EASY_OPTION_PRETTY_PRINT_FUNCTIONS` and `EASY_OPTION_BUILTIN_COLORS` change what the *headers* do in your translation units, so a manual setup must replicate them.

To make profiling optional per configuration, gate the **link** but keep the **headers** available — the macros you wrote in your sources still need `easy/profiler.h` to compile away:

```cmake
option(ENABLE_PROFILING "Link easy_profiler" OFF)

find_package(easy_profiler CONFIG REQUIRED)          # always: provides the headers
add_executable(my_app main.cpp)
if(ENABLE_PROFILING)
    target_link_libraries(my_app PRIVATE easy_profiler)       # defines BUILD_WITH_EASY_PROFILER
else()
    get_target_property(EP_INCLUDE easy_profiler INTERFACE_INCLUDE_DIRECTORIES)
    target_include_directories(my_app PRIVATE ${EP_INCLUDE})  # headers only: macros expand to nothing
endif()
```

**Verified** with an installed v2.1.0: the `ON` build links `libeasy_profiler` and records; the `OFF` build links nothing, `dumpBlocksToFile` returns `0`, and `versionName()` returns `v0.0.0_disabled`. (Skipping the `else()` branch makes the `OFF` build fail with `fatal error: easy/profiler.h: No such file or directory`.)

If you would rather not depend on the headers at all when profiling is off, route every include through a **wrapper header** and define the handful of macros you use:

```cpp
// profiling.h
#pragma once
#ifdef BUILD_WITH_EASY_PROFILER
#  include <easy/profiler.h>
#else
#  define EASY_FUNCTION(...)
#  define EASY_BLOCK(...)
#  define EASY_END_BLOCK
#  define EASY_EVENT(...)
#  define EASY_THREAD(...)
#  define EASY_MAIN_THREAD
#  define EASY_PROFILER_ENABLE
#  define EASY_PROFILER_DISABLE
#endif
```

(**Verified**: compiles and runs with no profiler headers or library present. Calls to `profiler::…` functions need their own guards in this approach.)

#### Manual (any build system)

1. Add the directory containing the `easy/` header folder to the include path (`…/easy_profiler_core/include`).
2. Define `BUILD_WITH_EASY_PROFILER` for translation units that should be instrumented.
3. Link `easy_profiler` (and make the shared library discoverable at run time: rpath on Linux/macOS, `PATH`/next to the exe on Windows).
4. **Windows only:** if you built easy_profiler as a *static* library, define `EASY_PROFILER_STATIC` in your project; otherwise the headers declare `__declspec(dllimport)` and linking fails.

#### Compile-time on/off

| Define | Effect |
|---|---|
| `BUILD_WITH_EASY_PROFILER` | Master "profiling is compiled in" switch (set by the CMake target). |
| `DISABLE_EASY_PROFILER` | Force-disable in a specific TU even if the master switch is set. **Verified.** |
| *(neither)* | Macros expand to nothing; API functions are inline no-ops. The headers must still be on the include path. |

Internally the header keys everything off `USING_EASY_PROFILER`, which is defined only when `BUILD_WITH_EASY_PROFILER` is defined and `DISABLE_EASY_PROFILER` is not.

> A translation unit built **without** the master switch records nothing even if the library is linked into the same binary. If part of your code is mysteriously absent from a profile, check that TU's defines.

---

## 3. Instrumentation API

Everything below lives in `#include <easy/profiler.h>`; values additionally need `#include <easy/arbitrary_value.h>`.

### 3.1 Blocks

```cpp
#include <easy/profiler.h>

void update()
{
    EASY_FUNCTION();                          // block named after the function, lives to end of scope

    {
        EASY_BLOCK("physics");                // scoped block: ends at the closing brace
        stepPhysics();
    }

    EASY_BLOCK("render", profiler::colors::Blue);   // optional colour
    drawScene();
    EASY_END_BLOCK;                           // end the most recently opened block early

    present();                                // not part of "render"
}
```

| Macro | What it does |
|---|---|
| `EASY_BLOCK(name, …)` | Opens a scoped block named `name`. Ends at end of scope or at `EASY_END_BLOCK`. Optional arguments: a colour and/or an enable flag, **in any order** (**Verified**). |
| `EASY_FUNCTION(…)` | `EASY_BLOCK` with the function name; accepts the same optional colour/flag. It does **not** have to be the first statement — time is measured from where you place it. |
| `EASY_END_BLOCK` | Ends the most recently opened block of the current thread before its scope ends. Safe even if that block was disabled: it never closes some other block. |
| `EASY_NONSCOPED_BLOCK(name, …)` | Opens a block that does **not** end automatically — it must be closed with `EASY_END_BLOCK`, possibly in a different function. |

Non-scoped blocks (**Verified** across two functions):

```cpp
void begin_phase() { EASY_NONSCOPED_BLOCK("Phase"); /* ... */ }
void end_phase()   { /* ... */ EASY_END_BLOCK; }
```

Prefer literals for non-scoped block names. Always pair every `EASY_NONSCOPED_BLOCK` with an `EASY_END_BLOCK`, on every code path (including early returns and exceptions) — unlike scoped blocks nothing closes it for you, and an unbalanced block distorts every block nested after it.

> `EASY_PROFILER_ENABLE`, `EASY_END_BLOCK`, `EASY_SET_EVENT_TRACING_ENABLED` and a few other macros already contain their own trailing `;`. See the `if`/`else` pitfall in §8.

### 3.2 Block names: compile-time vs run-time

How you spell the name decides how it is stored. **Verified** by decoding the file:

| You write | Treated as | Stored as |
|---|---|---|
| A string **literal** (`"physics"`) | **Compile-time** name | Name lives once in the block *descriptor*; per-block record carries no name (just a 1-byte terminator). |
| Any **non-literal**: `const char*` variable, `std::string::c_str()`, function return value | **Run-time** name | Descriptor name is auto-generated as `file.cpp:LINE`; the actual string is **copied into every block record**. |

```cpp
EASY_BLOCK("fixed");                       // compile-time name
EASY_BLOCK(name.c_str());                  // run-time name; descriptor is "file.cpp:LINE"
EASY_BLOCK(::profiler::ForceConstStr(p));  // force "compile-time" for a non-literal pointer
```

Rules and consequences:

- **One descriptor per source line.** The descriptor key is `__FILE__` + `__LINE__`. The first block to register at a given line fixes the descriptor's name, colour and flag. **Two blocks on the *same line* therefore share one descriptor, and the second silently takes the first one's name** (**Verified**: `{ EASY_BLOCK("first"); } { EASY_BLOCK("second"); }` on one line produced two blocks both called `first`). Put each block on its own line. This also affects blocks generated by a multi-line macro (one `__LINE__` for the whole expansion).
- Because the descriptor is registered once, `ForceConstStr` with a string that later changes only ever shows the *first* value. Use it only for strings that never change.
- Run-time names cost record size and copying; for hot paths use literals.
- A run-time name is limited to **2816 characters** (`EASY_MAX_SIZE_VALUE`). Longer names can crash unless the library was built with `EASY_OPTION_TRUNCATE_RUNTIME_NAMES` (§2.3).
- `EASY_FUNCTION` names come from the compiler: MSVC's `__FUNCTION__` includes the class/namespace qualifier (`ns::Class::method`), whereas GCC/Clang's `__func__` is the bare function name (`method`). With `EASY_OPTION_PRETTY_PRINT` you get the full signature instead. Expect different names for the same function on different compilers.

### 3.3 Colours and enable flags

**Colours** are 32-bit ARGB (`profiler::color_t`). A Material-design palette is built in (`profiler::colors::Red`, `Blue`, `Amber100`, `DarkRed`, …); note the namespace is **`colors`**, plural — `profiler::color::Red` does not exist and will not compile. You may pass your own value, e.g. `0xff336699`. The default colour is `profiler::colors::Default`, which equals `Wheat` = `Amber100` = `0xffffecb3` (**Verified** in the descriptors of a real file). If you build with `EASY_OPTION_PREDEFINED_COLORS=OFF` (see §2.3) the palette is not defined and you must supply your own constants.

**Enable flags** set a block's *initial* status:

| Flag | Behaviour (all **Verified** unless noted) |
|---|---|
| `profiler::ON` | Default. Block is recorded; children follow their own flags. |
| `profiler::OFF` | This block is **not** recorded; its children still are. |
| `profiler::OFF_RECURSIVE` | Neither this block nor its descendants are recorded… |
| `profiler::FORCE_ON` | …except a descendant marked `FORCE_ON`, which is recorded even under an `OFF_RECURSIVE` ancestor. |
| `profiler::ON_WITHOUT_CHILDREN` | This block is recorded; its descendants are not. |
| `profiler::FORCE_ON_WITHOUT_CHILDREN` | `FORCE_ON` and `ON_WITHOUT_CHILDREN` combined: always recorded, descendants not *(source-read)*. |

```cpp
EASY_BLOCK("noisy_loop", profiler::OFF_RECURSIVE);   // silence this subtree by default
{
    EASY_BLOCK("important", profiler::FORCE_ON);       // ...but keep this one
}
```

Blocks marked `OFF` are **still registered**: their descriptor appears in the file with status 0. That is what lets the GUI flip a block's status while connected (status changes are not allowed during an active capture). The numeric status values stored in the file are listed in §6.3.

### 3.4 Events

```cpp
EASY_EVENT("cache miss");                           // zero-duration marker on this thread
EASY_EVENT("checkpoint", profiler::colors::Green);
EASY_EVENT("muted", profiler::OFF);                 // not recorded (Verified)
```

An event is a block of type *Event* with begin time = end time. It appears in the GUI as a marker and in the converter's JSON with equal `start`/`stop`.

### 3.5 Arbitrary values

`EASY_VALUE` records a **timestamped data point** (shown as a value track in the GUI). It is *not* "attached" to the enclosing block as a field; it is its own record that happens to occur while a block is open, and in the reader's tree it appears as a child of that block.

```cpp
#include <easy/arbitrary_value.h>

struct Body { float pos[3]; unsigned id; };

void tick(const Body& b, uint32_t N)
{
    EASY_FUNCTION();
    EASY_VALUE("id", b.id);                                // scalar
    EASY_ARRAY("position", b.pos, 3, profiler::colors::Red);  // fixed-size array
    EASY_VALUE("N", N, EASY_VIN("N"));                     // explicit Value ID
    EASY_TEXT("state", "running");                         // NUL-terminated text
    EASY_STRING("tag", buffer, length);                    // text with explicit length
}
```

| Macro | Purpose |
|---|---|
| `EASY_VALUE(name, v, …)` | One scalar. |
| `EASY_ARRAY(name, ptr, count, …)` | Array of scalars. |
| `EASY_TEXT(name, text, …)` | NUL-terminated string. |
| `EASY_STRING(name, text, size, …)` | String of a given length. |

Rules:

- Supported scalar types: `bool`, `char`, `int8_t`…`int64_t`, `uint8_t`…`uint64_t`, `float`, `double` (a `static_assert` rejects others). **Passing a pointer as the value is rejected at compile time.**
- The value **name must be a compile-time string** — run-time names are not supported for values.
- Optional trailing arguments: colour, enable flag, and a Value ID.
- **Value ID (VIN).** The GUI groups points that share an ID into one series. The default is the **address of the variable you passed** (so the same object changed from several places forms one series). Override with `EASY_VIN(x)` (any value or string, e.g. `EASY_VIN(EASY_FUNC_NAME)`), `EASY_GLOBAL_VIN` (identified by name, across the program) or `EASY_UNIQUE_VIN` (unique per source line).
- Maximum payload per value is **2816 bytes** (`MAX_BLOCK_DATA_SIZE`). Fixed-size cases fail a `static_assert`; run-time-sized `EASY_STRING`/`EASY_ARRAY` beyond the limit are only guarded if the library was built with `EASY_OPTION_CHECK_MAX_VALUE_SIZE` (which then silently drops them).
- Value descriptors have type *Value* (2); the payload layout in the file is described in §6.5. In the reader/converter tree a value (like an event) appears as a **child of the block that was open when it was recorded**, with `start == stop` (**Verified**).
- `EASY_VALUE`/`EASY_ARRAY`/… are in a separate header and compile to nothing when profiling is disabled, exactly like the other macros. **v2.1.0 quirk (Verified):** with profiling disabled, `#include <easy/arbitrary_value.h>` fails with `'string' in namespace 'std' does not name a type` unless `<string>` was included before it. Include `<string>` first (or include the header only under `BUILD_WITH_EASY_PROFILER`).

### 3.6 Threads

| Macro | Behaviour |
|---|---|
| `EASY_THREAD(name)` | Registers and names the **current thread**, once per thread (a per-site thread-local guard makes repeat executions no-ops; the first name wins). Call it at the top of the thread's entry function. |
| `EASY_THREAD_SCOPE(name)` | Like `EASY_THREAD` but with an explicit scope guard — use it on compilers without `thread_local`, or when you need deterministic unregistration. |
| `EASY_MAIN_THREAD` | Shorthand for `EASY_THREAD("Main")`. The thread named `"Main"` is what the *main-thread* frame-time API reports on (§4.5). |

```cpp
int main()
{
    EASY_MAIN_THREAD;
    std::thread t([] {
        EASY_THREAD("Worker");        // appears as "Worker" in the profile
        run();
    });
    t.join();
}
```

Behaviours worth knowing (**Verified**):

- A thread that never calls `EASY_THREAD` is still recorded the moment it opens its first block; it just has an **empty name**.
- When a registered thread exits, a **`ThreadFinished` event** is written to that thread's data (with `thread_local` support this happens for `EASY_THREAD` too, not only `EASY_THREAD_SCOPE`). It counts towards the dump's block total and appears in readers — don't be surprised by one extra block per exited thread.
- The thread ID stored in the file is the OS thread ID (`gettid()` on Linux, `GetCurrentThreadId()` on Windows, `pthread_self()` on macOS), stored as 64-bit. On Linux the main thread's ID equals the process ID.
- `EASY_THREAD`/`EASY_THREAD_SCOPE` expand to several statements (a thread-local variable plus an `if`), keyed on `__LINE__`: put each on its own line, and wrap it in braces if you use it as the body of an `if`.

### 3.7 Complete minimal program

```cpp
#include <easy/profiler.h>
#include <iostream>

void work()
{
    EASY_FUNCTION(profiler::colors::Magenta);
    for (int i = 0; i < 3; ++i)
    {
        EASY_BLOCK("iteration");
        /* ... real work ... */
    }
}

int main()
{
    EASY_MAIN_THREAD;
    EASY_PROFILER_ENABLE;                       // before the outermost block opens (see §1.3)

    work();                                     // completed top-level frame

    const auto blocks = profiler::dumpBlocksToFile("capture.prof");
    std::cout << "wrote " << blocks << " blocks\n";
}
```

Build with `-DBUILD_WITH_EASY_PROFILER`, link `easy_profiler`, run, and open `capture.prof` in `profiler_gui` or convert it (§5).

---

## 4. Controlling capture and getting data out

### 4.1 Starting and stopping capture

| Macro | Function | Notes |
|---|---|---|
| `EASY_PROFILER_ENABLE` | `profiler::setEnabled(true)` | Starts capture; stamps the capture begin time. |
| `EASY_PROFILER_DISABLE` | `profiler::setEnabled(false)` | Stops capture. |
| `EASY_START_CAPTURE` / `EASY_STOP_CAPTURE` | aliases of the two above | |
| — | `profiler::isEnabled()` | Current state. |
| — | `profiler::startCapture()` / `stopCapture()` / `isCapturing()` | Function-style aliases (**Verified** to compile and behave identically). |

When the profiler is compiled out, `isEnabled()` is a constexpr `false` and every setter is a no-op.

Capture is **global** (all threads) and **runtime**. Remember the frame rule (§1.3): the switch is honoured at top-level block boundaries.

### 4.2 Dumping to a file

```cpp
uint32_t n = profiler::dumpBlocksToFile("capture.prof");   // 0 = nothing written / failure
```

What the call does, in order (source plus **Verified** observations):

1. Opens the output file. If it cannot be opened it returns `0` immediately *(source-read)*.
2. If capture is on, **turns it off** and stamps the capture end time. Afterwards `isEnabled()` is `false` (**Verified**).
3. Sleeps ~**20 ms** to let in-flight blocks on other threads settle.
4. Locks each thread's storage, drops empty expired threads, and on Linux/macOS (when event tracing is enabled) reads the context-switch log file.
5. On Linux/macOS with the native timer, **re-calibrates the CPU frequency with a busy loop** (§7.1). Measured here: a trivial dump took ≈ 59 ms wall-clock in total.
6. Writes the header, block descriptors, per-thread data and trailer (§6). **Only blocks belonging to completed top-level frames are written** (§1.3).
7. **Clears** the written blocks from every thread's storage (block *descriptors* are kept).
8. Returns the number of blocks written: real blocks + context-switch records + synthetic events such as `ThreadFinished` (**Verified**: 10 recorded blocks + 10 on a worker + 1 `ThreadFinished` = 21).

Consequences (all **Verified**):

- **Dumping stops capture.** To record again, call `EASY_PROFILER_ENABLE` again.
- **A second dump without re-enabling** returns `0` and writes an essentially empty (but structurally valid) file.
- **Re-enable → work → dump** can be repeated indefinitely, each cycle producing an independent file.
- Blocks cleared by the first dump are gone; the next file only contains what happened afterwards.

Pattern for repeated captures:

```cpp
void capture_scenario(const char* path)
{
    EASY_PROFILER_ENABLE;                 // enable *before* the outermost block opens
    {
        EASY_BLOCK("scenario");
        run_scenario();
    }                                     // frame closes here...
    profiler::dumpBlocksToFile(path);     // ...so it is included in the file
}
```

> Don't call `dumpBlocksToFile` from inside the very function whose top-level `EASY_FUNCTION()` you want in the result: that block is still open and will be lost (see §8).

### 4.3 Live capture with the GUI (network mode)

```cpp
profiler::startListen();            // default port 28077; call stopListen() to end
// profiler::startListen(30000);    // custom port
// profiler::isListening();
```

- `startListen` launches a background listener thread. The library also stops it automatically at shutdown.
- To start listening automatically at program startup with no code change, build the library with `-DEASY_OPTION_LISTEN=ON` (`EASY_OPTION_START_LISTEN_ON_STARTUP`).
- **Verified:** after `startListen()`, a plain TCP connect to `127.0.0.1:28077` succeeded and the server immediately sent a small (8-byte) status message; `isListening()` flipped to `false` after `stopListen()`.
- Workflow in `profiler_gui`: enter `host:port` → **Connect** → **Capture** → **Stop** → the collected data is transferred and displayed → optionally **save** it as a `.prof` file.
- In this mode the *GUI* starts and stops capture remotely, so the application does not need to call `EASY_PROFILER_ENABLE` itself. Capture state is global, so avoid also toggling it from application code in the same session.
- Remember the frame rule: a GUI capture started while a long top-level block is already open will not see that block's contents until it closes. Prefer instrumenting a per-iteration/per-frame loop rather than one giant block that spans the whole process lifetime.
- For remote targets, make sure the TCP port is reachable (firewall, container port mapping).

### 4.4 Profiling application startup

Capture must be on *before* the code you want to measure runs, and a block opened earlier hides its children (§1.3). Two options:

1. **Local capture:** call `EASY_PROFILER_ENABLE` as the first statement in `main`, **before** any `EASY_FUNCTION()` in `main`, run the startup phase inside closed blocks, then dump.
2. **GUI capture of startup:** build with `EASY_OPTION_LISTEN=ON`, enable capture from the GUI as soon as it connects. Anything that finished before you connected is not recorded, so to capture startup itself use option 1, or make the application wait briefly for a connection before starting its work.

### 4.5 Frame-time (FPS) queries

The library tracks time per top-level frame and exposes it at run time, **even while capture is off** (the frame bookkeeping runs on the not-capturing path too):

```cpp
auto us   = profiler::this_thread::frameTime();                // last frame, microseconds
auto maxT = profiler::main_thread::frameTimeLocalMax();        // local max since last query
auto avg  = profiler::main_thread::frameTimeLocalAvg(profiler::TICKS);  // raw CPU ticks
bool is_main = profiler::this_thread::isMain();
```

`Duration` is `profiler::MICROSECONDS` (default) or `profiler::TICKS`. `main_thread::*` refers to the thread registered with the name `"Main"` (`EASY_MAIN_THREAD`). **Verified:** a 2 ms frame reported ≈ 2267 µs.

### 4.6 OS context switches (optional)

Records when threads are scheduled on/off a CPU core, shown as extra rows in the GUI. Appears in the file as the per-thread "context switch" list (§6.4).

| Platform | How |
|---|---|
| Windows | Uses ETW (Event Tracing for Windows). **The application must run as Administrator.** Enabled by default (`EASY_OPTION_EVENT_TRACING`). |
| Linux | Needs the SystemTap logger script shipped in the repo (`scripts/context_switch_logger.stp`, run as root), which writes a log file (default `/tmp/cs_profiling_info.log`) that the profiler reads **at dump time**. If the file does not exist nothing happens. *(source-read; no systemtap in the test environment)* |
| macOS | No built-in collector (the non-Windows mechanism is the SystemTap-based log). |

Controls:

```cpp
EASY_SET_EVENT_TRACING_ENABLED(false);        // turn off context-switch capture
EASY_SET_LOW_PRIORITY_EVENT_TRACING(true);    // Windows: lower priority tracing thread
EASY_EVENT_TRACING_SET_LOG("/path/log.txt");  // non-Windows: log file location
```

**Order matters:** per the header, a change made with `EASY_SET_EVENT_TRACING_ENABLED` takes effect at the **next** `EASY_PROFILER_ENABLE`. Call it *before* enabling, not after:

```cpp
EASY_SET_EVENT_TRACING_ENABLED(false);   // 1. configure
EASY_PROFILER_ENABLE;                    // 2. then start capture
```

### 4.7 Changing block status at run time

`setBlockStatus` (used by the GUI) changes a descriptor's enable status. It is **not permitted while capture is active**; set statuses between sessions. Source-level flags (§3.3) are the initial values.

---

## 5. Analysing results

### 5.1 The GUI (`profiler_gui`)

Qt application (built unless `EASY_PROFILER_NO_GUI`). Open a `.prof` file or connect to a running application. Main views *(per upstream README / source-read; the GUI was not run here)*:

- **Diagram** — per-thread timeline of nested blocks, zoom/pan, event markers, context-switch rows, value tracks.
- **Hierarchy / tree** — the frame/block tree with durations, % of parent/frame, calls count.
- **Statistics** — per-block-name aggregates (calls, total, min/max/average).
- **Bookmarks** — user annotations saved into the file (§6.6).
- **FPS monitor** — live frame-time display for the main thread (works over the network even when not capturing).
- Block enable/disable by descriptor (while not capturing), and selected-region snapshots saved as new `.prof` files.

### 5.2 Command-line converter (`profiler_converter`)

Converts a `.prof` file to JSON — the easiest way to analyse results in scripts.

```bash
profiler_converter INPUT.prof OUTPUT.json     # write to a file
profiler_converter INPUT.prof > OUTPUT.json   # or write to stdout
```

Behaviours (**Verified**):

- With no arguments it prints the usage text and exits with status 1.
- **A missing/unreadable input file produces no output and exit status 0** — check for the output yourself in scripts; do not rely on the exit code.
- JSON keys are sorted alphabetically; times are **nanoseconds**; timestamps are absolute values on the profiler's clock (not Unix epoch and not relative to capture start) — subtract the earliest `start` if you want relative times.

Schema (real output, abbreviated):

```json
{
  "version": "2.1.0",
  "timeUnits": "ns",
  "bookmarks": [],
  "blockDescriptors": [
    { "id": 0, "name": "work", "type": 1, "color": "0xffffecb3",
      "sourceFile": "app.cpp", "sourceLine": 11 },
    { "id": 3, "name": "app.cpp:14", "type": 1, "color": "0xffffecb3",
      "sourceFile": "app.cpp", "sourceLine": 14 },
    { "id": 6, "name": "dyn_7", "parentId": 3, "type": 1, "color": "0xffffecb3",
      "sourceFile": "app.cpp", "sourceLine": 14 }
  ],
  "threads": [
    { "threadId": 922, "threadName": "",
      "children": [
        { "id": 9, "descriptor": 0, "name": "work", "start": 106182258525, "stop": 106189736696,
          "children": [ { "id": 6, "descriptor": 6, "name": "dyn_7", "start": 106188635547, "stop": 106189723455 } ] }
      ] }
  ]
}
```

Reading it correctly:

- `type`: `0` event, `1` block, `2` value.
- **Block `id` is the converter's own sequential index** (assigned in the order records were completed — children before parents), *not* a descriptor id. `descriptor` is the descriptor id.
- For **run-time-named** blocks the descriptor's own name is just `file:line`; the converter **synthesizes an extra descriptor per distinct run-time name** with a `parentId` pointing back at the original descriptor (see ids 3 and 6 above). Use the block's `name`.
- Events and values have `start == stop`.
- **Value payloads are not exported** — a value appears only as a named zero-duration block. If you need the numbers, use the C++ reader (§5.3) or parse the file yourself (§6.5).
- **Context-switch records are not exported** (the converter's JSON writer has no field for them *(source-read)*), and `bookmarks` was empty in all tests.
- The converter has a known limit on stack depth (254 nested blocks, §8).

### 5.3 The C++ reader API (`easy/reader.h`)

Read and analyse `.prof` files programmatically. The reader lives in the same `easy_profiler` library you already link. This program was compiled and run against real captures (**Verified**); it prints each thread and its top-level blocks with per-block statistics:

```cpp
#include <easy/reader.h>
#include <atomic>
#include <cstdio>
#include <sstream>

int main(int, char** argv)
{
    std::atomic<int> progress(0);                 // updated 0..100 while reading
    profiler::BeginEndTime       begin_end;       // capture begin/end (ns)
    profiler::SerializedData     serialized_blocks, serialized_descriptors; // OWN the raw bytes
    profiler::descriptors_list_t descriptors;     // index = descriptor id
    profiler::blocks_t           blocks;          // flat storage of every block
    profiler::thread_blocks_tree_t trees;         // thread id -> root of that thread's tree
    profiler::bookmarks_t        bookmarks;
    uint32_t descriptors_count = 0, version = 0;
    profiler::processid_t pid = 0;
    std::stringstream log;                        // error/diagnostic text

    const auto count = fillTreesFromFile(progress, argv[1], begin_end,
        serialized_blocks, serialized_descriptors, descriptors, blocks, trees,
        bookmarks, descriptors_count, version, pid,
        /*gather_statistics=*/true, log);

    if (count == 0) { std::fprintf(stderr, "read failed: %s\n", log.str().c_str()); return 1; }

    std::printf("version=0x%08x pid=%llu duration_ns=%llu blocks=%u\n", version,
        (unsigned long long)pid,
        (unsigned long long)(begin_end.endTime - begin_end.beginTime), count);

    for (const auto& kv : trees)
    {
        const profiler::BlocksTreeRoot& root = kv.second;
        std::printf("thread %llu '%s' frames=%u blocks=%u depth=%u\n",
            (unsigned long long)root.thread_id, root.name(),
            root.frames_number, root.blocks_number, root.depth);

        for (auto idx : root.children)            // top-level blocks (frames)
        {
            const profiler::BlocksTree& b = blocks[idx];
            const auto* desc = descriptors[b.node->id()];
            // node->name() is the RUN-TIME name ("" for ordinary blocks): fall back to the descriptor
            const char* name = *b.node->name() ? b.node->name() : desc->name();
            const auto* st = b.per_thread_stats;
            std::printf("  %-12s dur=%llu ns  calls=%u  self=%llu ns\n", name,
                (unsigned long long)b.node->duration(),
                st ? st->calls_number : 0u,
                st ? (unsigned long long)(st->total_duration - st->total_children_duration) : 0ull);
        }
    }
}
```

Key facts about the API:

- `fillTreesFromFile` is a free function declared `extern "C"`; it returns the **number of blocks read, or `0` on failure** (details in the `log` stream).
- All times it returns (`duration()`, `begin()`, `end()`, `profiled_time`, statistics) are **already converted to nanoseconds**.
- **Ownership/lifetime:** `blocks[i].node` points *into* `serialized_blocks`, and descriptors point into `serialized_descriptors`. Keep those `SerializedData` objects, `blocks` and `trees` alive for as long as you use any pointer from them.
- `trees` maps thread id → `BlocksTreeRoot`: `thread_name`/`name()`, `thread_id`, `children` (indices of top-level blocks into `blocks`), `sync` (indices of context-switch events), `events` (indices of events), `profiled_time` (sum of top-level durations), `wait_time` (sum of context-switch durations), `frames_number`, `blocks_number`, `depth`.
- `BlocksTree` has `node` (the serialized record: `begin()`, `end()`, `duration()`, `id()`, `name()`), `children` (indices into `blocks`), and the statistics pointers `per_thread_stats`, `per_parent_stats`, `per_frame_stats` (may be `nullptr` where not applicable, e.g. for top-level blocks).
- `BlockStatistics` has `total_duration`, `median_duration`, `total_children_duration`, `calls_number`, `min/max_duration_block`, and `average_duration()`. **Self time = `total_duration − total_children_duration`.**
- **Statistics are shared per descriptor id.** All blocks created at the same source line share one statistics object (so the three `iteration` calls below are a single row with `calls = 3`). That also means different run-time names created at one line aggregate together.
- Pass `gather_statistics = false` to skip statistics when you only need the tree.
- Version handling: files from v0.1.0 onwards are readable; older-layout files are converted on load (§6.7).
- Depth limit: the reader tracks depth in a `uint8_t`; a tree deeper than **254** nested levels makes the read fail (returns `0`, with a log message).

#### Aggregating a whole capture per block (generic recipe)

This walks every thread's tree once and builds one row per distinct statistics object. It was compiled and run against a real capture (**Verified**):

```cpp
#include <easy/reader.h>
#include <unordered_set>
#include <vector>
#include <algorithm>

struct Row { const char* name; const char* file; int line;
             uint32_t calls; uint64_t total, self, median; };

static void walk(const profiler::blocks_t& blocks, const profiler::descriptors_list_t& descs,
                 const profiler::BlocksTree::children_t& kids,
                 std::unordered_set<const profiler::BlockStatistics*>& seen,
                 std::vector<Row>& out)
{
    for (auto idx : kids)
    {
        const profiler::BlocksTree& b = blocks[idx];
        const auto* d = descs[b.node->id()];
        if (d->type() == profiler::BlockType::Block && b.per_thread_stats &&
            seen.insert(b.per_thread_stats).second)         // one row per shared stats object
        {
            const auto* s = b.per_thread_stats;
            out.push_back({ *b.node->name() ? b.node->name() : d->name(), d->file(), d->line(),
                            s->calls_number, s->total_duration,
                            s->total_duration - s->total_children_duration,
                            s->median_duration });
        }
        walk(blocks, descs, b.children, seen, out);
    }
}
// For each thread:  walk(blocks, descriptors, root.children, seen, rows);
//                   std::sort(rows.begin(), rows.end(),
//                             [](const Row& a, const Row& b){ return a.total > b.total; });
```

Sample output for a function with three `iteration` blocks each calling a `leaf`, plus a run-time-named block:

```
work     calls=1 total_us=7478 self_us=42   median_us=7478
iteration calls=3 total_us=6348 self_us=4    median_us=2100
leaf     calls=3 total_us=6344 self_us=6344 median_us=2098
dyn_7    calls=1 total_us=1087 self_us=1087 median_us=1087
```

Ranking by **self time** finds where time is actually spent; ranking by **total** finds the heaviest call trees. Heavy self time with few calls means a slow function; modest self time with huge call counts means call overhead or a loop that should be restructured.

### 5.4 Writing `.prof` files (`easy/writer.h`)

`writer.h` declares the counterparts of the reader functions, both `extern "C"`:

```cpp
profiler::block_index_t writeTreesToFile(std::atomic<int>& progress, const char* filename,
        const profiler::SerializedData& serialized_descriptors,
        const profiler::descriptors_list_t& descriptors, profiler::block_id_t descriptors_count,
        const profiler::thread_blocks_tree_t& trees, const profiler::bookmarks_t& bookmarks,
        profiler::block_getter_fn block_getter,
        profiler::timestamp_t begin_time, profiler::timestamp_t end_time,
        profiler::processid_t pid, std::ostream& log);
// plus writeTreesToStream(...) taking a std::ostream&, and a convenience inline overload
```

It writes a (possibly filtered) set of already-loaded trees back out as a `.prof` file — the mechanism behind GUI "snapshots" of a selected region. Typical uses: trimming a capture to chosen threads or a time window, or re-saving after adding bookmarks. `block_getter` maps a block index to the `BlocksTree` to write, which is how you select which blocks to keep. It returns the number of blocks written, `0` on failure. *(Signature verified against `writer.h`; not exercised in tests.)*

### 5.5 Parsing the file yourself

For tools in other languages (Python, Rust, …), the format is simple and stable within v2.1.x. See §6, which includes a complete, tested Python reference parser.

---

## 6. The `.prof` binary format

Everything below was decoded from real files with an independent parser and cross-checked against the official converter (§6.8). All integers are **little-endian** and **packed** (no padding). All strings are **NUL-terminated**. Timestamps are in **CPU ticks** (see §6.9). This describes format version **2.1** (`version` = `0x02010000`).

```
 ┌──────────────────────────────┐
 │ Header (72 bytes)            │
 ├──────────────────────────────┤
 │ Block descriptors × N        │   (shared by all threads)
 ├──────────────────────────────┤
 │ Thread section × T           │   each: id, name, context switches, blocks
 ├──────────────────────────────┤
 │ Trailer: signature (4 bytes) │
 ├──────────────────────────────┤
 │ Bookmarks (optional, GUI)    │   only present in files saved by the GUI
 └──────────────────────────────┘
```

### 6.1 Header — 72 bytes

| Offset | Type | Field | Notes |
|---:|---|---|---|
| 0 | u32 | `signature` | Magic `0x45617379`. |
| 4 | u32 | `version` | `(major << 24) \| (minor << 16) \| patch` → v2.1.0 = `0x02010000`. |
| 8 | u64 | `pid` | Process ID of the profiled process. |
| 16 | i64 | `cpu_frequency` | **Ticks per second.** Windows: QPC frequency. Linux/macOS native timer: the calibrated CPU/TSC frequency in Hz (e.g. ≈ 2 099 964 000 on a 2.1 GHz machine). `std::chrono` builds: the clock's tick rate (1e9 for nanosecond clocks) *(source-read)*. A value of `0` is interpreted by the reader as "timestamps are already nanoseconds" *(source-read)*. |
| 24 | u64 | `begin_time` | Capture start, in ticks. |
| 32 | u64 | `end_time` | Capture end, in ticks. |
| 40 | u64 | `memory_size` | **Sum of all block record payload sizes** (the `sz` values below, excluding the 2-byte `sz` prefixes) — **Verified**: a file with ten blocks reported 232 = Σ payloads. It is a preallocation hint for readers. |
| 48 | u64 | `descriptors_memory_size` | Preallocation hint for descriptors (non-zero even when no blocks were captured). |
| 56 | u32 | `blocks_count` | Total records across all threads: blocks + context switches + synthetic events (`ThreadFinished` etc.). A reader should check this against what it actually read. |
| 60 | u32 | `descriptors_count` | Number of descriptor records. |
| 64 | u32 | `threads_count` | Number of thread sections. |
| 68 | u16 | `bookmarks_count` | `0` in files written by `dumpBlocksToFile`. |
| 70 | u16 | padding | `0`. |

### 6.2 Layout notes

- Descriptors come **before** threads, so block records can be resolved by id while reading.
- Descriptors are **not cleared by a dump**: a later file may list descriptors for blocks that never occur in it (**Verified**: a zero-block file still listed all 6 descriptors).

### 6.3 Block descriptor record (× `descriptors_count`)

| Type | Field | Notes |
|---|---|---|
| u16 | `sz` | Size of the rest of this record (excludes these 2 bytes). |
| u32 | `id` | Descriptor id — referenced by block records. |
| i32 | `line` | Source line. |
| u32 | `color` | `0xAARRGGBB`. |
| u8 | `type` | `0` Event, `1` Block, `2` Value. |
| u8 | `status` | Enable-flag bits: `0` OFF, `1` ON, `3` FORCE_ON, `4` OFF_RECURSIVE, `5` ON_WITHOUT_CHILDREN, `7` FORCE_ON_WITHOUT_CHILDREN (§3.3). |
| u16 | `name_len` | Length of `name` **including** its NUL. |
| char[`name_len`] | `name` | Compile-time name — or `file.cpp:LINE` for blocks that use run-time names. |
| char[…] | `file` | Source file path, NUL-terminated; its length is **the remainder of the record**: `sz − 16 − name_len`. |

The fixed part after `sz` is **16 bytes** (4+4+4+1+1+2). Example (**Verified**): `sz = 28` for name `"work\0"` (5) and file `"t1.cpp\0"` (7) → 16 + 5 + 7 = 28.

### 6.4 Thread section (× `threads_count`)

| Type | Field | Notes |
|---|---|---|
| u64 | `thread_id` | OS thread id. |
| u16 | `name_size` | Including NUL. An **unnamed thread has `name_size = 1`** and a single `0` byte. |
| char[`name_size`] | `name` | |
| u32 | `cs_count` | Number of context-switch records (0 unless context-switch capture was active). |
| … | context-switch records × `cs_count` | Each: `u16 sz`, `u64 begin`, `u64 end`, `u64 tid`, then the NUL-terminated process name filling the rest of `sz` *(source-read)*. |
| u32 | `blocks_count` | Number of block records for this thread. |
| … | block records × `blocks_count` | See §6.5. |

### 6.5 Block record

| Type | Field | Notes |
|---|---|---|
| u16 | `sz` | Size of the rest of this record. |
| u64 | `begin` | Ticks. |
| u64 | `end` | Ticks (for events and values: equal to `begin`). |
| u32 | `descriptor_id` | Index into the descriptor table. |
| … | payload | **Depends on the descriptor's `type`** (below). |

**Events and blocks (types 0 and 1):** the payload is a NUL-terminated **run-time name**; just a single `0` byte for compile-time-named blocks. A plain block therefore has `sz = 21` (8+8+4+1) — **Verified**. The effective name is the run-time name if non-empty, otherwise the descriptor's `name`.

**Values (type 2):** the payload is:

| Type | Field | Notes |
|---|---|---|
| u8 | `name_stub` | Always `0` (looks like an empty run-time name to generic code). |
| u8 | reserved | |
| u16 | `size` | Data size in **bytes**. |
| u8 | `data_type` | `0` bool, `1` char, `2` int8, `3` uint8, `4` int16, `5` uint16, `6` int32, `7` uint32, `8` int64, `9` uint64, `10` float, `11` double, `12` string. |
| u8 | `is_array` | `1` for `EASY_ARRAY`, `EASY_TEXT`, `EASY_STRING`. |
| u64 | `value_id` | The VIN (default: address of the variable; see §3.5). |
| bytes[`size`] | data | Little-endian elements. `EASY_TEXT` data includes its trailing NUL; `EASY_STRING` data does **not**. |

All of these were decoded from real files: `int32 42` → `size 4, type 6`; `float[3]` → `size 12, type 10, is_array 1`; `"hello"` → `size 6, type 12`; `bool` → `size 1, type 0`.

**Ordering — important for tree reconstruction.** Within a thread, records are stored in **completion order** (a parent is written *after* its children), not start order. To rebuild nesting, walk the records in file order keeping a stack: for each new block, pop every stack entry whose `begin ≥` the new block's `begin` and make them its children, then push the new block. What remains on the stack at the end are the top-level blocks (frames). The reference parser in §6.8 does exactly this.

### 6.6 Trailer and bookmarks

After the last thread, a 4-byte `signature` repeats as an end marker (**Verified**). Files saved by the GUI with user bookmarks append them **after** this marker, `bookmarks_count` times:

| Type | Field |
|---|---|
| u16 | `size` (= 12 + length of text including NUL) |
| u64 | `pos` (timestamp, ticks) |
| u32 | `color` |
| char[] | text, NUL-terminated |

*(Source-read from `reader.cpp`; files produced by `dumpBlocksToFile` contain no bookmarks.)*

### 6.7 Format versions and compatibility

The reader accepts files from **v0.1.0** onward and adapts to older layouts:

| File version | Difference |
|---|---|
| < 1.3.0 | Thread ids are 32-bit instead of 64-bit. |
| < 2.0.0 | Older header arrangement. |
| < 2.1.0 | Header without `threads_count` / bookmarks, no trailer marker. |
| ≥ 2.1.0 | Layout described above. |

Always check `version` first and reject unknown major versions in your own tools. The `develop` branch still stamps `2.1.0` (§9), so its files are expected to be readable by 2.1-format tools.

### 6.8 Reference parser (Python 3, tested)

A complete reader: header, descriptors, threads, context switches, value decoding and tree reconstruction. **Verified** against `profiler_converter` on a multi-thread capture: identical thread names, identical tree shapes and block names, durations equal to within 1 ns (rounding).

```python
#!/usr/bin/env python3
"""Minimal reader for easy_profiler .prof files (format 2.1.x, little-endian)."""
import struct, sys

SIGNATURE = 0x45617379
VALUE_TYPES = {0: '?', 1: 'c', 2: 'b', 3: 'B', 4: 'h', 5: 'H', 6: 'i',
               7: 'I', 8: 'q', 9: 'Q', 10: 'f', 11: 'd'}   # 12 = string

class Reader:
    def __init__(self, data): self.d, self.o = data, 0
    def take(self, fmt):
        v = struct.unpack_from('<' + fmt, self.d, self.o)
        self.o += struct.calcsize('<' + fmt)
        return v if len(v) > 1 else v[0]
    def raw(self, n):
        b = self.d[self.o:self.o + n]; self.o += n; return b

def cstr(b): return b.split(b'\0', 1)[0].decode('utf-8', 'replace')

def decode_value(payload, desc_type):
    """payload = bytes after the 20-byte fixed block fields (value blocks only)."""
    size, vtype, is_array = struct.unpack_from('<HBB', payload, 2)
    vin, = struct.unpack_from('<Q', payload, 6)
    data = payload[14:14 + size]
    if vtype == 12:                       # string (EASY_TEXT includes the NUL; EASY_STRING does not)
        return {'vin': vin, 'value': cstr(data) if data.endswith(b'\0') else data.decode('utf-8', 'replace')}
    code = VALUE_TYPES[vtype]
    n = size // struct.calcsize(code)
    vals = struct.unpack('<%d%s' % (n, code), data)
    return {'vin': vin, 'value': list(vals) if is_array else vals[0]}

def parse(path):
    r = Reader(open(path, 'rb').read())
    assert r.take('I') == SIGNATURE, 'not an easy_profiler file'
    version = r.take('I')
    h = dict(version=version, pid=r.take('Q'), freq=r.take('q'), begin=r.take('Q'),
             end=r.take('Q'), mem=r.take('Q'), dmem=r.take('Q'), blocks=r.take('I'),
             ndesc=r.take('I'), nthreads=r.take('I'), nbookmarks=r.take('H'))
    r.take('H')                                           # padding
    to_ns = (lambda t: t * 1_000_000_000 // h['freq']) if h['freq'] else (lambda t: t)

    descs = {}
    for _ in range(h['ndesc']):
        size = r.take('H'); end = r.o + size              # size excludes itself
        did, line, color, typ, status = r.take('IiIBB')
        nlen = r.take('H')
        name = cstr(r.raw(nlen))
        file = cstr(r.raw(end - r.o))                     # remainder = source file
        descs[did] = dict(id=did, name=name, file=file, line=line, color=color,
                          type=typ, status=status)

    threads = []
    for _ in range(h['nthreads']):
        tid = r.take('Q'); name = cstr(r.raw(r.take('H')))
        cswitches = []
        for _ in range(r.take('I')):                      # context switches
            size = r.take('H'); end = r.o + size
            b, e, who = r.take('QQQ')
            cswitches.append(dict(begin=b, end=e, tid=who, process=cstr(r.raw(end - r.o))))
        stack = []                                        # rebuild tree: records are in completion order
        for _ in range(r.take('I')):
            size = r.take('H'); end = r.o + size
            b, e, did = r.take('QQI')
            d = descs[did]; rest = r.raw(end - r.o)
            node = dict(begin=b, end=e, desc=d, children=[])
            if d['type'] == 2: node['value'] = decode_value(rest, d['type'])
            else:              node['runtime_name'] = cstr(rest)
            node['name'] = node.get('runtime_name') or d['name']
            while stack and stack[-1]['begin'] >= b:      # everything inside [b, e] is a child
                node['children'].insert(0, stack.pop())
            stack.append(node)
        threads.append(dict(tid=tid, name=name, cswitches=cswitches, roots=stack))
    assert r.take('I') == SIGNATURE, 'bad trailer'
    h['to_ns'] = to_ns
    return h, descs, threads

def dump(n, to_ns, depth=0):
    dur = to_ns(n['end'] - n['begin'])
    extra = ' = %r' % (n['value']['value'],) if 'value' in n else ''
    print('%s%s  %d ns%s' % ('  ' * depth, n['name'], dur, extra))
    for c in n['children']: dump(c, to_ns, depth + 1)

if __name__ == '__main__':
    h, descs, threads = parse(sys.argv[1])
    print('version 0x%08x  pid %d  freq %d Hz  %d blocks' % (h['version'], h['pid'], h['freq'], h['blocks']))
    for t in threads:
        print('thread %d %r' % (t['tid'], t['name']))
        for root in t['roots']: dump(root, h['to_ns'], 1)
```

### 6.9 Converting ticks to time

- seconds = `ticks / cpu_frequency`; nanoseconds = `ticks × 1_000_000_000 / cpu_frequency`.
- Use wide arithmetic: in C, `ticks × 1e9` can overflow 64 bits for large tick counts (use `unsigned __int128` or `double`). Python integers are unbounded.
- Absolute tick values are only meaningful relative to each other (same clock); subtract `begin_time` for time since capture start.
- If `cpu_frequency` is `0`, treat timestamps as nanoseconds already (what the official reader does).

---

## 7. Platform and timing notes

### 7.1 Timers

| Platform / build | Clock | `cpu_frequency` in file |
|---|---|---|
| Windows | `QueryPerformanceCounter` | `QueryPerformanceFrequency` |
| Linux/macOS (GCC/Clang), x86/x86-64 | `rdtsc` cycle counter | Calibrated frequency in Hz |
| Linux/macOS, AArch64 | `cntvct_el0` virtual counter | Calibrated |
| Linux, other CPUs (ARMv6+, PowerPC, SPARC, IA-64) | CPU cycle counter | Calibrated |
| MIPS, unknown compilers | `std::chrono::high_resolution_clock` | Clock period |
| `BUILD_WITH_CHRONO_STEADY_CLOCK` / `…_HIGH_RESOLUTION_CLOCK` | `std::chrono` clock | Clock period |

*(From `current_time.h`; only x86-64 Linux was run.)*

Consequences of the native timer on Linux/macOS (**Verified** on x86-64 Linux):

- The tick frequency is **measured at runtime with a busy loop** (100 million iterations) when the library initialises and again on each `dumpBlocksToFile`. This costs tens of milliseconds of CPU: here a dump took ≈ 59 ms wall-clock, of which 20 ms is the deliberate settle delay. Don't call it on a latency-critical thread.
- `rdtsc` is only a reliable wall clock on CPUs with an invariant TSC; where in doubt, consider a chrono clock option (portable and needs no calibration; it may cost more per block, which was not measured here).

### 7.2 Run-time tick conversion: `toNanoseconds` is wrong on Linux/macOS in v2.1.0

`profiler::toMicroseconds()` is correct, but on non-Windows, non-chrono builds **`profiler::toNanoseconds()` returns a value 10⁶ too small** in v2.1.0 (it effectively returns milliseconds). **Verified:** a 100 ms sleep gave `toMicroseconds ≈ 100214` (correct) and `toNanoseconds = 100` (should be ≈ 100 000 000). The `develop` branch fixes the formula. Workaround on 2.1.0: use `toMicroseconds(t) * 1000`.

This affects only the run-time helper functions. **The `.prof` file and the reader/converter are unaffected** — they convert from the stored `cpu_frequency` and produced correct nanoseconds in all tests.

### 7.3 Exported symbol names

In v2.1.0 the runtime functions are declared in `extern "C"` blocks inside `namespace profiler`, so they are exported with **plain, unmangled global names** (**Verified** with `nm`: `now`, `version`, `versionName`, `isEnabled`, `setEnabled`, `dumpBlocksToFile`, `startListen`, `fillTreesFromFile`, …). `profiler::now()` is therefore the global symbol `now`. Short generic names like `now` and `version` can collide with symbols from other libraries or your own code at link time; this is why 3.x renames them (§9).

### 7.4 Windows

- Context switches require **Administrator** (ETW).
- Shared build: your code is compiled against `__declspec(dllimport)`. A **static** build needs `EASY_PROFILER_STATIC` defined in every consumer (the CMake target does this).
- The reader/writer API exposes STL types (`std::vector`, `std::string`, `std::ostream`) across the library boundary, so build the library and any code that uses those APIs with the same compiler generation and runtime, as with any C++ DLL.

### 7.5 Linux

- Context switches: root + SystemTap logger (§4.6).
- Thread ids come from `gettid()` (§3.6). Name your threads with `EASY_THREAD`.

### 7.6 Memory

Blocks accumulate in per-thread chunked storage until you dump. A plain block costs about 21 bytes in the file (more with run-time names or values) — upstream reports ~12 million blocks in under 300 MB. For long-running programs, capture short windows (enable → work → dump) rather than leaving capture on indefinitely.

---

## 8. Pitfalls and troubleshooting

### 8.1 "My capture is empty / missing blocks"

| Symptom | Cause | Fix |
|---|---|---|
| `dumpBlocksToFile` returns `0` | Capture never enabled, already dumped (dump disables capture), file can't be opened, or only **open** frames existed | Call `EASY_PROFILER_ENABLE` before the work; dump after top-level blocks close; check the path. |
| Everything inside `main()` missing | `EASY_FUNCTION()` (or any block) opened in `main` **before** `EASY_PROFILER_ENABLE`, or `dump` called while it is still open | Enable first; put the work in a closed inner block (`{ EASY_BLOCK("run"); … }`); dump after it closes. |
| Last scenario missing | Dumped inside the scope of the outermost block | End the block (`EASY_END_BLOCK`) or leave its scope first. |
| Second file is empty | Dump disables capture | Re-enable before the next window. |
| A whole file/TU never shows up | TU compiled without `BUILD_WITH_EASY_PROFILER` (or with `DISABLE_EASY_PROFILER`) | Check that TU's compile definitions. |
| A block never shows up | Its flag is `OFF`/`OFF_RECURSIVE`, or an ancestor is `OFF_RECURSIVE`/`ON_WITHOUT_CHILDREN` | Use `profiler::ON` / `FORCE_ON`, or change the status in the GUI between sessions. |
| Two blocks have the same name | Both on one source line (shared descriptor) | One block per line. |
| Thread appears with an empty name | Thread never called `EASY_THREAD` | Add `EASY_THREAD("name")` at the thread's entry. |

### 8.2 "It doesn't compile"

| Symptom | Cause | Fix |
|---|---|---|
| `'profiler::color' has not been declared` | Wrong namespace | `profiler::colors::Red` (plural). |
| `'else' without a previous 'if'` | `EASY_PROFILER_ENABLE`/`DISABLE`, `EASY_END_BLOCK`, `EASY_SET_*` macros already end in `;`, so `if (c) EASY_PROFILER_ENABLE; else …` has an empty statement before `else` (**Verified**) | Use braces: `if (c) { EASY_PROFILER_ENABLE; } else { … }`, or call `profiler::setEnabled(true)`. |
| Pointer rejected in `EASY_VALUE` | Pointers aren't allowed (`static_assert`) | Dereference, or use `EASY_TEXT`/`EASY_STRING`/`EASY_ARRAY`. |
| `__declspec(dllimport)` link errors (Windows) | Static library without `EASY_PROFILER_STATIC` | Define it, or use the CMake target. |
| `EASY_VALUE` with a run-time name fails | Value names must be compile-time strings | Use a literal. |
| `'string' in namespace 'std' does not name a type` in `arbitrary_value.h` (profiling **disabled** builds) | v2.1.0's disabled branch of that header uses `std::string` without including `<string>` (**Verified**) | `#include <string>` before it, or include it only when `BUILD_WITH_EASY_PROFILER` is defined. |
| `easy/profiler.h: No such file or directory` in a profiling-off build | Headers are still needed when the macros are compiled out | Keep the include directory (§2.4) or use a wrapper header. |

### 8.3 Behavioural gotchas

- **`EASY_SET_EVENT_TRACING_ENABLED` order:** set it *before* `EASY_PROFILER_ENABLE` (§4.6).
- **Unbalanced `EASY_NONSCOPED_BLOCK`:** every path needs a matching `EASY_END_BLOCK`.
- **Over-long run-time names or values** can crash unless the library was built with the truncate/check options (§2.3). Keep names short; use values for data.
- **One extra block per thread** (`ThreadFinished`) is normal.
- **Reader depth limit:** trees nested deeper than **254** levels cannot be read (`fillTreesFromFile` returns `0`; the converter uses the same reader, so it fails on such files too — check its output). Avoid unbounded recursion under instrumentation, or disable deep subtrees with `OFF_RECURSIVE`.
- **Converter exit code:** `profiler_converter` returns `0` even if the input file is missing or unreadable. Check that the output exists and is non-empty.
- **Mixing profiled and unprofiled TUs** is fine, but only profiled TUs record anything.
- **Unmangled symbol names** (`now`, `version`, …) can collide with other libraries (§7.3).
- **Dump cost** (≈ tens of ms on Linux/macOS, §7.1): don't dump on a real-time or UI thread.

### 8.4 Practical guidance

- **Granularity.** Per-block overhead is small but not free: instrument functions that take microseconds or more, and loops at the *iteration* level only when they are not trivial. Don't instrument tiny inline functions called millions of times per frame — use `OFF_RECURSIVE` or `ON_WITHOUT_CHILDREN` to prune.
- **Frames.** Wrap each unit of work (a frame, a request, a job) in one named top-level block. It gives the GUI and the statistics meaningful "frames", and it makes capture windows well-defined.
- **Names.** Use stable, searchable literal names. Prefer `EASY_VALUE` for numbers and dynamic data rather than formatting them into run-time names.
- **Threads.** Name every thread you own (`EASY_THREAD`), and `EASY_MAIN_THREAD` on the main one.
- **Build configurations.** Profile an optimised build (Release or RelWithDebInfo); Debug timings are not representative. Gate the link behind a CMake option so shipping builds contain no profiler code.
- **Pick your analysis tool by question:** GUI for "what happened when and why was this frame slow", the converter/JSON for scripting, the reader API for custom aggregation, a raw parser for non-C++ tooling.

---

## 9. v2.1.0 vs `develop` (3.x) differences

At the time of this review `develop` was **68 commits** ahead of v2.1.0, and its README refers to a 3.x line, while its top-level CMake project version still reads **2.1.0** — so files it writes are still stamped `0x02010000` and the **`.prof` format is unchanged** (the core diff contains no format-writing changes). Differences found by diffing v2.1.0 against `develop` (outside the Qt GUI, which also changed in ~27 files):

| Area | v2.1.0 | `develop` |
|---|---|---|
| `profiler::now()` | exported as global `now` | renamed **`timeNow()`**; `currentTime()` now calls it |
| Version functions | `version`, `versionMajor/Minor/Patch`, `versionName` | renamed **`apiVersion`**, `apiVersionMajor/Minor/Patch`, `apiVersionName` |
| Ticks → ns on non-Windows | wrong by 10⁶ (§7.2) | fixed (`ticks * 1000000LL / frequency`) |
| CMake minimum | `cmake_minimum_required(VERSION 3.0)` (rejected by CMake 4 without a policy flag) | `3.5...${CMAKE_VERSION}` |
| Platforms / build systems | — | Emscripten thread-id support; QNX CMake toolchain files; Bazel `BUILD` files |
| `arbitrary_value.h` with profiling off | needs `<string>` included first (§8.2) | value headers now include `<string>` (from the diff) |
| Network listener | socket timeout 500 µs | socket timeout 500 ms |
| Licence files | `LICENSE.MIT`, `LICENSE.APACHE` | renamed `mit.lic`, `apache.lic` |
| Everything else in the public API | — | unchanged in the diff: all `EASY_*` macros, `setEnabled`, `dumpBlocksToFile`, `startListen`, `reader.h`, `writer.h` |

*(Derived from a diff only; the `develop` branch was not built or run.)*

Practical advice: pin a tagged release (v2.1.0) for reproducibility. If you must support both lines, either avoid calling the two renamed API families (rarely needed — the macros and `dumpBlocksToFile` are identical) or hide them behind a tiny wrapper selected by a compile-time check.

---

## 10. Quick reference

### Macros (`easy/profiler.h`, `easy/arbitrary_value.h`)

| Macro | Purpose |
|---|---|
| `EASY_BLOCK(name, [color], [flag])` | Scoped block. |
| `EASY_FUNCTION([color], [flag])` | Scoped block named after the function. |
| `EASY_NONSCOPED_BLOCK(name, …)` / `EASY_END_BLOCK` | Manual begin / end. |
| `EASY_EVENT(name, [color], [flag])` | Zero-duration marker. |
| `EASY_VALUE(name, v, …)`, `EASY_ARRAY(name, p, n, …)`, `EASY_TEXT(name, s, …)`, `EASY_STRING(name, s, n, …)` | Data points. |
| `EASY_VIN(x)`, `EASY_GLOBAL_VIN`, `EASY_UNIQUE_VIN` | Value-series identity. |
| `EASY_THREAD(name)`, `EASY_THREAD_SCOPE(name)`, `EASY_MAIN_THREAD` | Thread registration. |
| `EASY_PROFILER_ENABLE` / `EASY_PROFILER_DISABLE` (`EASY_START_CAPTURE` / `EASY_STOP_CAPTURE`) | Capture on/off. |
| `EASY_SET_EVENT_TRACING_ENABLED(b)`, `EASY_SET_LOW_PRIORITY_EVENT_TRACING(b)`, `EASY_EVENT_TRACING_SET_LOG(path)` | Context-switch settings. |
| `EASY_FUNC_NAME` | Compiler-specific function name. |

### Functions (`namespace profiler`)

| Function | Purpose |
|---|---|
| `setEnabled(bool)`, `isEnabled()`, `startCapture()`, `stopCapture()`, `isCapturing()` | Capture control. |
| `uint32_t dumpBlocksToFile(const char*)` | Stop capture and write a `.prof`; returns block count (0 = nothing/failure). |
| `startListen(port = 28077)`, `stopListen()`, `isListening()` | GUI network mode. |
| `registerThread(name)`, `registerThreadScoped(name, guard)` | What the thread macros call. |
| `setEventTracingEnabled(bool)`, `setLowPriorityEventTracing(bool)`, `setContextSwitchLogFilename(path)` (+ getters) | Context-switch controls. |
| `this_thread::frameTime / frameTimeLocalMax / frameTimeLocalAvg(Duration)`, `main_thread::…`, `this_thread::isMain()` | Frame-time queries. |
| `now()`, `toMicroseconds()`, `toNanoseconds()` | Raw clock and conversions (see §7.2 caveat). |
| `versionName()`, `version()`, `versionMajor/Minor/Patch()` | Library version (renamed in `develop`). `versionName()` returns `"v0.0.0_disabled"` when compiled out. |
| `fillTreesFromFile(...)` (`easy/reader.h`) | Read a `.prof` into trees + statistics. |
| `writeTreesToFile(...)` (`easy/writer.h`) | Write trees back to a `.prof`. |

### Enable flags / colours

`profiler::ON`, `OFF`, `FORCE_ON`, `OFF_RECURSIVE`, `ON_WITHOUT_CHILDREN`, `FORCE_ON_WITHOUT_CHILDREN`; colours `profiler::colors::<Name>` or a raw `0xAARRGGBB`.

### Common defines

`BUILD_WITH_EASY_PROFILER`, `DISABLE_EASY_PROFILER`, `EASY_PROFILER_STATIC` (Windows static), `EASY_DEFAULT_PORT`, `EASY_OPTION_*` (see §2.3).

### Command lines

```bash
# build
cmake -B build -DCMAKE_BUILD_TYPE=Release -DEASY_PROFILER_NO_GUI=ON -DEASY_PROFILER_NO_SAMPLES=ON
cmake --build build -j
# analyse
profiler_converter capture.prof capture.json
```

### Minimal checklist when adding profiling to an application

1. Link `easy_profiler`; define `BUILD_WITH_EASY_PROFILER` (the CMake target does both).
2. `EASY_MAIN_THREAD;` in `main`; `EASY_THREAD("…")` in every worker.
3. Wrap each frame/job/request in a named top-level block; add `EASY_BLOCK`/`EASY_FUNCTION` below it.
4. `EASY_PROFILER_ENABLE` **before** the outermost block opens.
5. Let the outermost block close, then `profiler::dumpBlocksToFile("x.prof")` (or use `startListen()` and the GUI).
6. Open `x.prof` in `profiler_gui`, or run `profiler_converter` / the reader API.

---

## Appendix — What was verified

| Area | How | Result |
|---|---|---|
| Build | v2.1.0, GCC 13, CMake 4 (policy flag), core + converter | Builds; outputs `libeasy_profiler.so`, `profiler_converter`. |
| Frame rule (enable inside, dump inside) | Four scenario programs | 0 blocks when dumping inside an open frame; children of a pre-enable frame dropped. |
| Dump semantics | Dump twice, re-enable, check `isEnabled` | Dump disables capture; second dump → 0 blocks, valid file. |
| Flags | One block per line, all flag combinations | Matches §3.3. |
| Same-line descriptors | Two blocks on one line | Share the first name. |
| Naming | Literal vs `c_str()` vs `ForceConstStr` | Run-time names → `file:line` descriptor + per-record name. |
| Values | Scalars, array, text, string | Layout in §6.5. |
| File format | Independent Python parser; cross-check with converter | Identical trees; ≤ 1 ns difference. |
| Descriptor size arithmetic | Hex dump | `sz = 16 + name + file` (not 12). |
| Reader API | Two C++ programs compiled and run | Statistics shared per descriptor. |
| Converter | CLI behaviours, JSON schema | As described in §5.2. |
| `toNanoseconds` | 100 ms sleep | Returned 100 (bug). |
| Network listener | TCP connect to 28077 | 8-byte status message; `isListening` toggles. |
| Compile errors | `profiler::color::`, `if/else` macro, `arbitrary_value.h` with profiling off | Reproduced. |
| Doc code blocks | 18 of the 20 C++ blocks were extracted from this file and compiled with profiling on (the other two are a one-line call and a declaration copied from `writer.h`); several also compiled with profiling off. The minimal program, the reader program, the aggregation recipe and the Python parser were run on real captures | Pass. |
| CMake integration | Installed v2.1.0; consumer project with the §2.4 snippet, ON and OFF | Imported target exports as described; OFF build links nothing. |
| Symbols | `nm -D` | Unmangled `now`, `version`, … |
| **Not tested here** | Windows (ETW, QPC, DLL linking), Qt GUI, SystemTap context switches, macOS, `develop` runtime behaviour (diffed only) | Taken from source/README; labelled *(source-read)*. |
