# Qt Tooling in an MSBuild Project — Reference Manual

How to drive Qt's QML tooling (`qmllint`, `qmlcachegen`, `qmltyperegistrar`, `moc`, …) from a
Visual Studio **MSBuild** (`.vcxproj` + Qt VS Tools) project, without CMake.

This reference documents the build mechanisms, tool contracts, and MSBuild rules required to integrate Qt 6 QML tooling into native Visual Studio C++ projects.

- **Audience:** anyone (human or LLM) adding or debugging QML tooling in an MSBuild Qt project.
- **Reference implementation pattern:** `QtQml.targets`, imported by `MyProject.UI.vcxproj`,
  with lint severities in `.qmllint.ini`.
- **Related reading:** [`qt-best-practices.md`](qt-best-practices.md) (code style /
  QML idioms and architecture).

## 1. Division of labour: what Qt VS Tools does, and what you must wire yourself

Qt VS Tools "includes MSBuild rules and targets specific to moc, uic and rcc"
([Qt VS Tools — Building](https://doc.qt.io/qtvstools/qtvstools-explanation-building.html)).
That is the whole pipeline: item types `QtMoc`, `QtRcc`, `QtUic`, and the generated sources are
added to the C++ compilation for you ("source files that the Qt tools generate are added to the
C++ compilation during the build process, so you do not need to include generated files in
projects").

**There is no QML pipeline and no "QML Compiler" switch.** In particular there is no such thing as
a QML Compiler checkbox under *Project ▸ Properties ▸ Qt Project Settings* — advice to look for one
circulates widely and is wrong. Everything QML-related (`qmllint`, `qmlcachegen`,
`qmltyperegistrar`) has to be wired by hand.

### How the Qt/MSBuild files are located

- Qt VS Tools resolves its rules into `$(QtMsBuild)` (typically `%LOCALAPPDATA%\QtMsBuild`).
- The extension's *Qt/MSBuild* option "corresponds to setting the value of the `QTMSBUILDS`
  environment variable"
  ([Qt VS Tools — Building](https://doc.qt.io/qtvstools/qtvstools-explanation-building.html)).
- The project file falls back to `$(MSBuildProjectDirectory)\QtMsBuild` when `$(QtMsBuild)` is
  unset *or* `qt.targets` is not found there. If that local directory is not committed to the
  repository, a build requires the Qt VS Tools extension or user environment to supply `QtMsBuild`.
  If a build fails with *"The imported project … Qt.props was not found"*, ensure `QtMsBuild` is
  properly installed or defined via the `QTMSBUILDS` environment variable.

### Properties you can rely on (probed, not assumed)

Run the `QmlToolingInfo` target to inspect resolved properties:

```bat
msbuild MyProject.UI\MyProject.UI.vcxproj /p:Configuration=Debug /p:Platform=x64 /t:QmlToolingInfo
```

| Property | Typical Value | Note |
| --- | --- | --- |
| `$(QtDir)`, `$(QTDIR)`, `$(QtInstallDir)` | `<QtPath>` (e.g. `C:\Qt\<version>\<toolchain>`) | Resolves the root Qt directory; `QTDIR` is set by Qt VS Tools |
| `$(QtInstall)` | `<version>_<toolchain>` | An install **name** (e.g. `6.8.0_msvc2022_64`), not a path |
| `$(QtMsBuild)` | `%LOCALAPPDATA%\QtMsBuild` | Location of Qt/MSBuild build rules |
| `$(QtBinDir)`, `$(QtIncludePath)`, `$(QtQmlIncludePath)` | *(varies / unset)* | Exist in some Qt VS Tools versions; do not assume them unconditionally |

Because the QML tooling must work even when those extra properties are absent, `QtQml.targets`
resolves its tool directory as `$(QmlToolDir)` → `$(QtDir)\bin` → `$(QTDIR)\bin` →
`$(QtInstallDir)\bin` → a verified hard-coded fallback.

### Command-line builds

Build the **solution**; building a project file directly does not define `$(SolutionDir)`, so sibling
projects' include paths (`$(SolutionDir)MyProject.Core\include`) break with
`error C1083: Cannot open include file: 'pch.h'`. That failure looks like a broken toolbar/import
but has nothing to do with your changes. Workarounds: build the solution, or pass
`/p:SolutionDir=<repo>\` explicitly when building a single project.

> **Tip (Diagnostic Logging):** When diagnosing target evaluation order or skipped targets in MSBuild,
> run with binary logging: `msbuild MySolution.sln /bl:build.binlog`. Inspect the `.binlog` using
> [MSBuild Structured Log Viewer](https://msbuildlog.com) to view exact command-line invocations,
> environment variables, task execution timings, and target dependencies.

## 2. Tool inventory in `<Qt>/bin` (verified listing)

| Group | Tools | Notes |
| --- | --- | --- |
| Build-system tools | `moc`, `rcc`, `uic` | driven by Qt VS Tools |
| QML compiler | `qmlcachegen`, `qmltc` | both present in the open-source install |
| Type info | `qmltyperegistrar`, `qmldom`, `qmljsrootgen` | |
| Linting / tooling | `qmllint`, `qmlls`, `qmlformat` | |
| Stats / profiling | `qmlaotstats`, `qmlprofiler`, `qmlpreview`, `qmlplugindump` | |
| Other | `qmlimportscanner`, `qmlcontextpropertydump`, `qmltestrunner`, `qmltime`, `qml` | |
| **Absent** | **`qmlsc`** | not shipped by open-source Qt. `qmlsc` is part of the commercial *Qt Quick Compiler Extensions* ([QML script compiler](https://doc.qt.io/qt-6/qtqml-qml-script-compiler.html)) |

The absence of `qmlsc.exe` is the practical ceiling: its **Static** and **Direct** modes are
unavailable, and `qmlcachegen` (Indirect mode) is the best AOT you can get on an open-source Qt.

Tools Qt explicitly calls internal — *"qmltc, qmlsc and qmlcachegen are internal build tools. If
you need to care about their invocation, you are either writing a build system, or you are doing
something wrong."* ([Qt Quick Compiler](https://doc.qt.io/qt-6/qtqml-qtquick-compiler-tech.html)) —
and *"qmlcachegen is an internal build tool … Users should not invoke it manually."*
([qmlcachegen](https://doc.qt.io/qt-6/qtqml-tool-qmlcachegen.html)). In an MSBuild project you are
that build system, so you do care. Treat their CLI as internal build tools: while flags remain
consistent across minor Qt 6 releases, always verify or re-derive tool invocation flags after major Qt
upgrades (§6).

## 3. Tool reference

### 3.1 `qmllint` — syntax/type verification

Docs: [qmllint](https://doc.qt.io/qt-6/qtqml-tooling-qmllint.html),
[QML lint warnings and errors](https://doc.qt.io/qt-6/qmllint-warnings-and-errors.html).

```
qmllint [options] files
```

Options that matter in a build integration (from `qmllint --help` in Qt 6):

| Option | Meaning / why you care |
| --- | --- |
| `-I, --qmldirs <dir>` | Look for QML modules in `dir`. This is how the linter finds a module whose types you generated (`-I <IntDir>qmltypes`). |
| `-i, --qmltypes <qmldir>` | Import *specific* `qmldir` files instead of the one found in the current directory. Note the confusing names: `-I` is a directory search path, `-i` names files. |
| `--bare` | Do not include default import dirs or the current directory (use when linting against a different Qt). |
| `-W, --max-warnings <count>` | Exit non-zero if more than `count` warnings occur. `-1` (default) = warnings never affect the exit code. |
| `--json <file>` | Machine-readable output (`-` = stdout). Useful for CI parsing. |
| `--write-defaults` | Writes a `.qmllint.ini` and exits (**overwrites** an existing settings file, comments included). |
| `-M, --module` | Lint modules instead of files. |
| `-f, --fix`, `--dry-run` | Apply / preview fix suggestions. |
| `-s, --silent` | Suppress syntax errors. |
| `--access-singleton-via-object <level>`, `--unqualified <level>`, `--missing-type <level>`, `--unresolved-type <level>`, … | Per-category severity overrides. The CLI spelling is *not* always the `.qmllint.ini` key (`UnqualifiedAccess` on the command line is `--unqualified`); check `qmllint --help`. |

**Severity levels and exit codes** (from `--help`, confirmed by observation): every category can be
`disable`, `info` (never affects the exit code), `warning` (counts toward `--max-warnings`) or
`error` (non-zero immediately). With the default `MaxWarnings=-1`, **warnings never fail a build —
only errors do**. That is what makes "errors fail, warnings print" the right default for a build
gate: syntax errors and real type errors break the build, while advisory findings are visible but
non-blocking.

**Settings discovery:** `qmllint` looks for `.qmllint.ini` next to each linted file and walks up the
directory tree; `--ignore-settings` disables that. So a single `.qmllint.ini` at the project (or
repo) root applies to every file. Command-line options override the file — which makes
`--unqualified warning` a convenient way to see what a disabled category *would* have reported.

**Project lint settings file:** `.qmllint.ini`.
A common reason to configure this file is `UnqualifiedAccess=disable`. In many UI hierarchies where child components access root window or parent model properties unqualified (e.g. `sessionModel`, `fileLoaderModel`), qmllint flags every occurrence:

```
View/HeaderBar.qml:120:25: Unqualified access [unqualified]
                              ? sessionModel.search_items(text)
Info: sessionModel is a member of a parent element.
      You can qualify the access with its id to avoid this warning.
```

Measured on a real-world multi-view UI: with the category enabled, the build reported **240** such warnings, which buried actionable diagnostics; disabling it removed the noise and isolated true syntax/type issues.

Granularity, because it matters before you reach for this: qmllint can only disable the **whole
category** here. The finer-grained `.contextProperties.ini` (`disableUnqualifiedAccess = "name,name"`)
applies to *context properties* only, and these are `required property` members of the root element.
If you want to keep the category enabled elsewhere, use the inline directive
`// qmllint disable unqualified` in the affected file/block, or do what the warning suggests and
qualify the access (`headerBar.sessionModel.…`) — semantically identical, but it is a change to a lot
of QML. Also note the category covers *all* unqualified accesses, not just the model ones, so a
future genuine unqualified-access mistakes in the codebase will no longer be flagged.

**Worth knowing when you read its output:**
- Findings are printed as `path/to/file.qml:line:col: <message> [category]` with a source excerpt.
  MSBuild's `Exec` task parses the matching lines, so in a build log they appear as
  `EXEC : warning : …` and land in the error list — verified. They are not clickable
  (`file(line,col): error CODE:` is what Visual Studio's navigator wants), which is a cosmetic
  limitation only; the build still fails correctly on errors.
- The unresolved-import cascade is the thing to watch for: if a module the QML imports is not
  resolvable, you get `[import]` + `[unresolved-type]` + `[missing-type]` warnings for *every* use of
  those types. Measured across sample application QML files (category counts, every level):

  | configuration | total | breakdown |
  | --- | --- | --- |
  | no type info (baseline) | 325 | 260 unqualified, 22 import, 21 unresolved-type, 11 missing-type, 7 Quick.layout-positioning, 3 missing-property, 1 unused-imports |
  | + generated type info (§3.3) | 251 | 240 unqualified, 7 Quick.layout-positioning, 3 missing-property, 1 unused-imports |
  | + `.qmllint.ini` | 11 | 7 Quick.layout-positioning, 3 missing-property, 1 unused-imports |

  So the type info fixes the cascade, and the settings file removes the deliberate-style noise. If
  your lint output explodes, fix the import paths first (see §3.3).
- **A `pragma Singleton` is only a singleton from a directory whose own `qmldir` declares it.**
  Modern Qt 6 resolves the implicit import of a QML document against that directory's registry; a
  singleton declared only in the module-root `qmldir` (with a path into a subdirectory) is treated
  as a plain type there. Every member access then reports `[missing-property]`, and the singleton
  file itself reports "Type X not declared as singleton in qmldir but using pragma Singleton".
  Keep a `qmldir` beside the components (`qml/View/Common/qmldir`) listing the
  singleton **and every sibling type** — an unlisted sibling stops resolving. Modern Qt 6
  also flags `[incompatible-type]` for an `int`-typed model property bound to a
  `real` property (wrap it in `Number(...)`) and has no `.length` on a `QString` (compare to `""`).
- `info`-level findings never reach the build log: MSBuild's `Exec` only turns matching lines into
  diagnostics and qmllint labels these `info:` rather than `warning:`. The `unused-imports` line in
  the table above is visible when running qmllint by hand but absent from the MSBuild output.
- Count categories carefully when scripting this: `[Quick.layout-positioning]` (and any
  `Quick.*` / `QtDesignStudio.*`) contains uppercase and dots, and MSBuild appends its own
  `[<project path>]` bracket to every line — a naive `\[[a-z-]+\]` pattern silently undercounts.
- **Lint depends on the type info.** `QmlLint` is `BeforeTargets="PrepareForBuild"` and now lists
  `QmlTypeInfo` in its `DependsOnTargets`, so a model-header change is linted against the `.qmltypes`
  generated in the same build (§3.3). That dependency is required, not cosmetic: `QmlTypeInfo` used
  to be reachable only through `QmlCacheGen`, so a Debug build (`QmlAotEnabled=false`) never
  regenerated the metadata and every new model member was reported as `missing-property` forever.
  Keep it when reordering the targets.
- **Never reference a role by number in QML.** `missing-property` is the only gate that catches a bad
  enum member, and it cannot catch a *stale number*: `data(index, 0x0106)` type-checks fine whatever
  `0x0106` currently means. Give the enum `Q_ENUM(...)` and write `TypeName.MemberName`; the value is
  then resolved from the meta-object at runtime and cannot drift when a member is inserted. (Real-world
  pitfall: a view's delegate used a hardcoded integer `0x0106`, which stopped matching `ItemOffsetRole`
  after two roles were inserted ahead of it in C++ and silently resolved to `ConfidenceRole`, breaking
  runtime playback with zero build errors.)

#### 3.1.1 Common qmllint backlog resolutions

Common findings and their architectural resolutions:

| finding | example pattern | resolution |
| --- | --- | --- |
| `missing-property` — `Member "focusSource" not found on type "QObject"` | Calling child page methods through `pageLoader.item`, which Qt types as `QObject`. | Replace with a statically-typed `property ContentPage contentPage`, assigned from the page's `Component.onCompleted` and nulled in `Component.onDestruction`. |
| `unused-imports` — `import QtQuick.Controls` | Unused module import in a view. | Remove dead import to reduce engine lookup overhead. |
| `Quick.layout-positioning` — `Detected height on an item that is managed by a layout` | `height: 40` inside a `RowLayout`/`ColumnLayout`. | Replace with `Layout.preferredHeight: 40` or respect `implicitHeight`. |

On the layout rewrite being behaviour-preserving: so long as an item declares no `implicitHeight`,
it still ends up at its explicit height, so both spellings give the same geometry today. Verified by
running a probe in which `height: 40`, `Layout.preferredHeight: 40` and `implicitHeight: 40` on
managed children all rendered 40px (the layout fell back to the explicit value for the children
whose `implicitHeight` was 0). The rewrite matters anyway, because `height` is the
undefined-behaviour path and the fallback is not a documented contract.

Three key lessons:

- **`Quick.layout-positioning` has a blind spot: `default property alias`.** An item that is the
  target of a component's `default property alias` is *not* flagged for `height`/`anchors` inside a
  layout (e.g., a custom `FormField` where `default property alias content: fieldContainer.data`).
  Probes isolating the variables: a plain managed `Rectangle` with `height` is flagged; the same
  with an `id` is flagged; the same behind a `default property alias` is not. Do not read a clean
  `qmllint` run as proof of zero layout-positioning bugs — also search for `height:` within a few
  lines of a `Layout.*` line.
- **The inline directive works for `missing-property` too**, not just `unqualified`:
  `// qmllint disable missing-property` … `// qmllint enable missing-property`. In a file with one
  suppressed and one unsuppressed call, only the unsuppressed call is reported. Useful when a member
  is genuinely untypeable and extracting a typed reference is not worth the boilerplate.
- **Do not "fix" the `Loader.item` case by passing the request down as a page property.** Handing
  a focus or state request to the page as a `required property` and clearing it from the owner via a
  signal produces a Qt **binding loop** (the write-back travels through the child's own binding) and
  the request is consumed twice. Related trap: a `required property` on a page instantiated by a
  `Loader` is not inherited from the enclosing scope — without an explicit binding inside the
  `Component` block the page fails at runtime with *"Required property … was not initialized"*.

### 3.2 `qmlcachegen` — ahead-of-time compilation

Docs: [qmlcachegen](https://doc.qt.io/qt-6/qtqml-tool-qmlcachegen.html),
[Qt Quick Compiler](https://doc.qt.io/qt-6/qtqml-qtquick-compiler-tech.html),
[QML script compiler](https://doc.qt.io/qt-6/qtqml-qml-script-compiler.html).

What the output actually is *(documented)*: *"At compile time, for each QML or JavaScript document
a corresponding C++ file is created and built into the application. The C++ file then contains a
QML compilation unit …"* — document structure, bytecode for every function/binding, and native C++
for the parts it fully understands. At runtime *"the QML engine then refrains from compiling the
QML or JavaScript source code at run time and instead uses the pre-built compilation unit"*.

Two things that are **not** true, and cost time to rediscover:

- **`.qmlc` files dropped into a `.qrc` are inert.** `rcc` stores file contents as byte arrays and
  the engine has no sidecar lookup for `qrc:` URLs. You compile to C++ and link it.
  *(The docs confirm the other half: `.qmlc`/`.jsc`/`.mjsc` output exists but "Neither the CMake nor
  the qmake build system offered by Qt expose this functionality", and cache files cannot contain
  the C++-compiled bindings anyway.)*
- **`qt_add_qml_module` is not required.** It is a CMake *wrapper*; its steps are reproducible from
  MSBuild, which is what §4 does.

#### Invocation A — one document (exactly one input file)

```
qmlcachegen --bare \
  --resource-path /qt/qml/myproject.ui/qml/main.qml \
  -I <IntDir>qmltypes \
  -I <QtInstallDir>/qml \
  -i <ProjectDir>/qml/qmldir \
  --resource <ProjectDir>/qml.qrc \
  --dump-aot-stats "--module-id=myproject.ui(MyProject.UI)" \
  -o <IntDir>qmlcache/main_qml.cpp \
  <ProjectDir>/qml/main.qml
```

Captured behaviour (all verified):

- **Only one input file is accepted.** Two or more give
  `Too many input files specified: '<file1>' '<file2>' …`. Options and the output file can appear in
  any order; the input document always goes last.
- `--bare` switches off the default import directories, so you must pass `-I` for Qt's own QML
  modules (`<Qt>/qml`) — this is exactly what CMake does, and it makes the compile deterministic.
- `--resource` takes the **`.qrc` file** that will contain the document; `--resource-path` is the
  document's path **inside** that resource tree (the qrc prefix plus the source path).
- `-i <qmldir>` points at the module's `qmldir` (the `qml/qmldir` module definition).
- `--dump-aot-stats` writes `<output>.aotstats` (JSON, see §3.4); `--module-id` labels the stats and
  accepts parentheses **when quoted** (cmd/PowerShell will otherwise parse `myproject.ui(MyProject.UI)`
  as a subexpression).
- `--verbose` prints a warning for every binding/function that could not be compiled to C++ — the
  fastest way to see whether the AOT is actually paying off.
- `--only-bytecode` gives up the native C++ and keeps bytecode only.

#### Invocation B — the unit-cache loader (this is the part people get wrong)

```
qmlcachegen --resource-name qmlcache_<ProjectName> \
  -o <IntDir>qmlcache/qmlcache_loader.cpp \
  @<IntDir>qmlcache/qml_loader_file_list.rsp
```

where the response file contains:

```
--resource
<ProjectDir>\qml.qrc
/qt/qml/myproject.ui/qml/main.qml
/qt/qml/myproject.ui/qml/View/Common/AppButton.qml
…
```

- **The file list is mandatory** — there is no way to pass the documents as positional arguments
  (that is what produced `Too many input files specified`), and running with `--resource <qrc>` and
  no input produces just the usage banner.
- **The entries after the `--resource` line are *resource* paths, not source paths.** Generated from
  source paths, the loader compiles fine but its registry is keyed by
  `<ProjectDir>\qml\main.qml`, while the engine asks about `/qt/qml/myproject.ui/qml/main.qml` — every
  lookup silently misses and you get **no AOT at all**, with no error anywhere.
- `--resource-name` only names the generated resource: it becomes
  `qInitResources_qmlcache_<ProjectName>` and influences nothing about the lookup keys.
- **The loader is not optional.** The per-file `.cpp` files contain only the unit data; the
  registration lives in the loader:

  ```cpp
  // qmlcache_loader.cpp (generated)
  const QQmlPrivate::CachedQmlUnit *Registry::lookupCachedUnit(const QUrl &url) {
      if (url.scheme() != QLatin1String("qrc"))
          return nullptr;
      QString resourcePath = QDir::cleanPath(url.path());
      …
      return unitRegistry()->resourcePathToCachedUnit.value(resourcePath, nullptr);
  }
  QQmlPrivate::RegisterQmlUnitCacheHook registration;
  registration.lookupCachedQmlUnit = &lookupCachedUnit;
  QQmlPrivate::qmlregister(QQmlPrivate::QmlUnitCacheHookRegistration, &registration);
  // registered through a Q_CONSTRUCTOR_FUNCTION — no explicit call needed
  ```

  So the engine's key is `QDir::cleanPath(url.path())` of the `qrc:` URL, i.e. your **qrc prefix +
  file path**. Verify the two match; that single string is the whole contract.
- The response file is accepted only as `@path`, **unquoted** (`@"path"` fails with
  `Cannot open options file specified with @`), which also means a project path containing a space
  cannot be supported — the targets file fails with an explicit message instead of producing a
  silently unit-less binary.

### 3.3 Type information: `moc --output-json` + `qmltyperegistrar`

Docs: [qmltyperegistrar](https://doc.qt.io/qt-6/qtqml-tooling-qmltyperegistrar.html),
[qmldir files / type description files](https://doc.qt.io/qt-6/qtqml-modules-qmldir.html).

**Why this is needed:** types registered from C++ at runtime (`qmlRegisterUncreatableType()`) are
invisible to `qmllint` and `qmlcachegen`. Without type info they only warn about the import, treat
every property access on those objects as unknown, and leave those bindings in bytecode.

```
moc --output-json -o <IntDir>qmltypes/metatypes/_moc_<Name>.cpp -I <includes…> <Header>.hpp
    # writes <output>.json next to the .cpp
qmltyperegistrar \
  --generate-qmltypes <IntDir>qmltypes/MyProject/Models/MyProject.Models.qmltypes \
  --import-name MyProject.Models --major-version 1 \
  -o <IntDir>qmltypes/registration.cpp \
  <the .json files>
```

Practical notes (verified):

- The headers must actually contain the registration macros **and** be able to expand them:
  `<qqmlintegration.h>` is often included as a bare name, so moc needs
  `-I <Qt>/include/QtQmlIntegration` (plus QtCore/QtGui/QtQuick/QtNetwork and the project's own
  include dirs). Without it moc only warns *"Potential QML registration macro was found, but no
  header containing it was included"* and the resulting `.qmltypes` is empty.
- `--output-json` writes the JSON next to the `-o` output with an extra `.json` suffix; `moc
  --collect-json` merges several JSONs into one. `qmltyperegistrar` accepts the JSON files as
  multiple arguments.
- The import name must match the QML `import` statement (`MyProject.Models` in this example).
- **Do not compile the generated `registration.cpp` if registering manually.** If your project
  registers types at runtime (e.g. via `qmlRegisterUncreatableType()`), linking `registration.cpp`
  will double-register and fail at startup. The registrar is used here for its metadata only.
- To make the import resolvable, the `.qmltypes` must sit in a module directory with a `qmldir` that
  names it:

  ```
  <IntDir>qmltypes/MyProject/Models/qmldir
      module MyProject.Models
      typeinfo MyProject.Models.qmltypes
  ```

  and both tools get `-I <IntDir>qmltypes`.
- Payoff: `[import]`/`[unresolved-type]`/`[missing-type]` lint findings disappear and bindings
  touching the models can be compiled to native C++.

### 3.4 `qmlaotstats` — what actually got compiled

`qmlcachegen --dump-aot-stats` writes a JSON file per unit (`<unit.cpp>.aotstats`) with one record
per binding/function: `codegenResult`, `functionName`, `line`, `column`, `message`. Aggregated across
documents:

| `codegenResult` | count | meaning |
| --- | --- | --- |
| 0 | 1565 | compiled to native C++ |
| 2 | 356 | fell back to bytecode; see `message` |
| 1 | 47 | fell back to bytecode |

Top fallback reasons: `Cannot access value for name settingsModel` / `sessionModel` /
`itemMemberModel` (reads of the root's `required property` model instances — the class of thing
`qmlsc`'s *Direct* mode removes), plus font/`QVariant` conversions
(`Cannot generate efficient code for internal conversion … QVariant -> QFont stored as QVariant`).

`qmlaotstats aggregate|format <in> <out>` turns these into a readable report (CMake wires the report
up as `all_aotstats`; in MSBuild just collect the files yourself).

### 3.5 `qmltc` — QML type compiler (not used here)

Docs: [QML type compiler](https://doc.qt.io/qt-6/qtqml-qml-type-compiler.html). Compiles QML *types*
into C++ classes, which the C++ side then instantiates instead of using `QQmlComponent`. It is
available in open-source Qt, but:
- *"qmltc-compiled apps using Qt's QML modules will require linking against private Qt API"* and it
  *"does not guarantee that the generated C++ stays API-, source- or binary-compatible between past
  or future versions, even patch versions"* ([Qt Quick Compiler](https://doc.qt.io/qt-6/qtqml-qtquick-compiler-tech.html)).
- It requires reworking `main.cpp` to create the generated classes.
Not wired up here: the cost/benefit is poor for a small UI, and the version coupling is exactly what
we avoid elsewhere.

### 3.6 Other tools present (not wired up)

| Tool | What it would give you |
| --- | --- |
| `qmlls` | QML language server — live linting/diagnostics in an editor. Qt VS Tools 3.2+ advertises experimental QML LSP support; the QML-vs-MSBuild integration here is manual. Docs: [QML Language Server](https://doc.qt.io/qt-6/qtqml-tooling-qmlls.html). |
| `qmlformat` | Rewrites QML to the coding conventions. Could become a `BeforeTargets` formatting gate; not enabled (reformatting churn). |
| `qmlimportscanner` | Scans QML for imports — used by deployment tooling to decide which QML modules to ship with `windeployqt`. |
| `qmlcontextpropertydump` | Produces the context-property dump `qmllint` uses to warn about context properties (CMake does this via `dump_qml_context_properties`). |
| `qmlprofiler`, `qmlpreview` | Runtime profiling / live preview; see [Qt Qml Tooling](https://doc.qt.io/qt-6/qtqml-tooling.html). |

## 4. The recommended MSBuild pipeline pattern

`QtQml.targets` (imported as the **last** element of the `.vcxproj`, so it reads Qt
properties that Qt VS Tools has already defined, and so the extension's own rewriting of the Qt
settings sections cannot drop it):

```
QmlPrepareItems ──► QmlTypeInfo ──► QmlLint              (BeforeTargets=PrepareForBuild)
                              └───► QmlCacheGen ──► QmlCacheLoader ──► QmlCompileGenerated
                                                                      (BeforeTargets=ClCompile)
```

| Target | Hook | Responsibility |
| --- | --- | --- |
| `QmlPrepareItems` | every build | Globs `qml/**/*.qml` + the model headers and derives each file's resource path and output `.cpp` path in a **second** metadata pass (§5.1). Must run unconditionally: the generation targets below are incremental, and a skipped target does not execute its `ItemGroup`s (§5.8). |
| `QmlLint` | `BeforeTargets="PrepareForBuild"`, depends on `QmlTypeInfo` | One `qmllint` invocation for all QML sources (`-I <IntDir>qmltypes`). Errors fail the build; warnings print. Severities come from `.qmllint.ini` (§3.1). Also fails loudly if `qmllint.exe` is missing — a gate that silently disappears is worse than no gate. |
| `QmlTypeInfo` | before lint and cachegen | `moc --output-json` per model header + `qmltyperegistrar` → `MyProject.Models.qmltypes` + the module `qmldir` (§3.3). Being a dependency of `QmlLint` is what keeps Debug builds (no AOT) from linting against stale metadata. |
| `QmlCacheGen` | before `ClCompile` | One `qmlcachegen` per QML document → `$(IntDir)qmlcache/<name>_qml.cpp` + `.aotstats`. `Inputs`/`Outputs` make it incremental and invalidate it when the `qmlcachegen` binary changes (units are tied to the Qt version that produced them). |
| `QmlCacheLoader` | after cachegen | One `qmlcachegen` run for `qmlcache_loader.cpp`, response file written by `WriteLinesToFile` (§3.2). |
| `QmlCompileGenerated` | `BeforeTargets="ClCompile"` | Adds the generated `.cpp` files to `ClCompile` — the same pattern Qt VS Tools uses for its `moc_*.cpp` — with `PrecompiledHeader=NotUsing`, `AdditionalIncludeDirectories=$(QmlQtIncludeDir)`, `AdditionalOptions=/Zc:__cplusplus /utf-8` (§5.5, §5.6, §5.7). |
| `QmlToolingInfo` | on demand | Prints resolved tool paths/properties for troubleshooting. |

Switches (command line, e.g. `/p:QmlAotEnabled=false`): `QmlEnabled`, `QmlLintEnabled`,
`QmlAotEnabled`, `QmlTypeInfoEnabled`, `QmlToolDir`.

**`QmlAotEnabled` defaults to `false` in Debug and `true` otherwise.** Debug therefore loads the
`qml.qrc` sources and compiles them at run time, so a QML edit costs only `rcc` +
`qrc_qml.cpp` + link instead of repetitive `qmlcachegen` runs and the compile of their units. Release is
unaffected — it still generates and links the units and the loader (verified: the Debug build log
has no `qmlcachegen:` line, Release prints one per batch). `QmlTypeInfoEnabled` deliberately
follows `QmlEnabled`, **not** `QmlAotEnabled`: `qmllint` needs the `.qmltypes` in Debug as well, or
the model import cascade returns (§3.1). Pass `/p:QmlAotEnabled=true` to A/B the
Debug behaviour. Turning AOT off also prunes the generated artifacts from the build tree (§5.10),
so a measurement needs a full rebuild between arms.

Generated output lives under `$(IntDir)qmlcache` (units, loader, response file, stats) and
`$(IntDir)qmltypes` (moc JSON, `.qmltypes`, module `qmldir`, a `registration.cpp` that is never
compiled) — both inside the project's temp directory, so `Clean` and the incremental machinery treat
them as ordinary build output.

## 5. MSBuild gotchas (all of these cost real time)

### 5.1 Well-known metadata is empty inside the same `ItemGroup`

```xml
<!-- WRONG: MocCpp becomes "..._moc_.cpp" — %(Filename) is not attached yet -->
<_QmlHeader Include="$(Dir)\*.hpp">
  <MocCpp>$(Out)\_moc_%(Filename).cpp</MocCpp>
</_QmlHeader>
```

Well-known metadata (`%(Filename)`, `%(RecursiveDir)`, …) is not available while an item is being
created. Set derived metadata in a **second** `ItemGroup` over the existing item type (this works,
and is what `QmlPrepareItems` does), or compute values with a transform at use time
(`@(Items->'%(Filename)')`), which also expands correctly. Symptom to recognise: filenames that
collapse to `_moc_.cpp` / identical output paths for every file.

### 5.2 A trailing separator before a closing quote escapes the quote

`-I "$(QmlTypesRootDir)"` where the property ends in `\` produces
`-I "C:\Path\To\qmltypes\"`, and the C runtime reads `\"` as an escaped quote: the tool receives one
garbled argument and dies with **exit code -1** and no message. Keep directory properties **without**
a trailing separator and add `\` where you concatenate a filename.

### 5.3 Response files need a literal `@` that cannot come from an item reference

`@(_QmlRsp)` expands to the path *without* the `@`, so the tool treats it as a document
(`Cannot open options file specified with @` / `Too many input files specified`). Define the path as
a **property** and write `@$(QmlLoaderResponseFile)`; `"@…"` quoted fails too (the tool takes the
quotes literally).

### 5.4 `%(Metadata)` self-reference on target-created items → MSB4096

Trying to inherit the project's value while setting your own:

```xml
<ClCompile Include="@(_Generated)">
  <AdditionalIncludeDirectories>$(QtInclude);%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
</ClCompile>
```

fails with `error MSB4096: The item "…" in item list "_Generated" does not define a value for
metadata "AdditionalIncludeDirectories"`. Set the complete value explicitly (the generated sources
only need the Qt root include dir), or read the inherited value into a property
before the `ItemGroup`.

### 5.5 Item definitions apply *partially* — the `/Zc:__cplusplus` trap

Items added to `ClCompile` from a target do inherit most project settings (verified in
`Cl.command.1.tlog`: `/ZI /Od /MDd /W3 /sdl /std:c++20 /permissive- /utf-8` all arrived), **but not
everything the toolchain injects for the project's own translation units.** The project's TUs end
with a batch of options the QML-generated TUs did not receive:

```
… /permissive- … -Zc:rvalueCast -Zc:strictStrings -Zc:throwingNew -Zc:__cplusplus -Zc:externConstexpr /utf-8 /utf-8
```

Without `-Zc:__cplusplus`, MSVC reports `__cplusplus == 199711L` and Qt's
`qcompilerdetection.h` rejects the translation unit:

```
error C1189: #error: "Qt requires a C++17 compiler, and a suitable value for __cplusplus.
                    On MSVC, you must pass the /Zc:__cplusplus option to the compiler."
```

Reproduced standalone: `cl /c /std:c++20 /permissive- /I <Qt>\include x.cpp` (with
`#include <QtCore/qobject.h>`) fails; adding `/Zc:__cplusplus` compiles. So `/permissive-` and
`/std:c++20` alone are **not** enough. `QmlCompileGenerated` therefore sets
`AdditionalOptions=/Zc:__cplusplus /utf-8` explicitly.

> *(Note: Visual Studio automatically injects `-Zc:*` conformant flags for project translation units,
> but generated sources injected dynamically by custom MSBuild targets do not inherit them automatically.
> Setting `/Zc:__cplusplus` and `/utf-8` on generated items guarantees conformance.)*

### 5.6 Generated sources need `PrecompiledHeader=NotUsing`

When projects compile with `PrecompiledHeader=Use` (or `/FI"pch.h"`), generated QML units do
not include `pch.h`, so without the opt-out (`PrecompiledHeader=NotUsing`) MSVC fails with
**C1010** ("unexpected end of file while looking for precompiled header").

### 5.7 Generated code needs the Qt *root* include directory

The generated units include module-prefixed headers (`<QtQml/qqmlprivate.h>`, `<QtCore/qobject.h>`).
Standard project include paths usually use per-module directories (`<Qt>/include/QtCore`, …), which do not
resolve root-prefixed includes, so `QmlCompileGenerated` sets `AdditionalIncludeDirectories=$(QmlQtIncludeDir)`
(`<Qt>/include`). Generated units require root-prefixed includes (`QtCore/…`, `QtQml/…`) plus the C++ standard library.
If a future Qt emits versioned private includes (`<QtQml/<version>/private/…>`), that directory belongs here as well.

### 5.8 Items created inside an incremental target do not exist when it is skipped

When `Inputs`/`Outputs` report up-to-date, MSBuild skips the whole target body — including its
`ItemGroup`s and therefore the item lists other targets (or the same target's `Outputs`) rely on.
Derive items in a small always-running target (`QmlPrepareItems`) and have the incremental targets
depend on it.

### 5.9 Guard against design-time builds

Add `Condition="'$(DesignTimeBuild)' != 'true'"` to every target that shells out, otherwise Visual
Studio's IntelliSense/design-time builds run `qmllint`/`qmlcachegen` constantly. A one-line guard is
the difference between a fast IDE and a sluggish one.

### 5.10 Toggling AOT off prunes its outputs

MSBuild's C++ build cleans up "orphaned" outputs: after a build with `QmlEnabled=false`, the
previously generated units/`.aotstats` were gone from `$(IntDir)`. Harmless, but it means an A/B
measurement needs a full rebuild between arms (and it explains "my stats files vanished").

### 5.11 XML comments cannot contain `--`

An innocent `<!-- … --resource lines … -->` in the targets file fails the whole import with
`error MSB4024: An XML comment cannot contain '--'`. Reword (`the resource option lines`).

### 5.12 Misc, useful to know

- `qmllint`'s findings already look like MSBuild diagnostics after `Exec`, so they show up as
  warnings in the build output without extra work.
- MSBuild batches several sources into **one** `cl` invocation (the tlog shows
  `MOC_SETTINGSMODEL.CPP` and `MAIN.CPP` on a single command line) — do not assume one command
  per source.
- `$(ProjectName)` may contain dots; the loader's resource symbol becomes
  `qInitResources_qmlcache_MyProject.UI` / mangled `…_MyProject` as appropriate. Only affects
  naming.
- A per-file `<Exec>` with `%(Metadata)` batching is the idiomatic way to run a tool once per item;
  it is what CMake effectively does too (one process per document).
- **Clean target integration:** To ensure `Clean` removes all generated artifacts and metadata,
  register the output files or folders in `FileWrites`:
  ```xml
  <ItemGroup>
    <FileWrites Include="$(IntDir)qmlcache\**\*" />
    <FileWrites Include="$(IntDir)qmltypes\**\*" />
  </ItemGroup>
  ```

## 6. Re-capturing Qt's own invocations after a Qt upgrade

To verify or re-derive tool invocation flags across Qt upgrades without hand-guessing:

1. Create a throwaway CMake project that mirrors the module — same `qml/` layout, same imports —
   and declare it with `qt_add_qml_module(<t> URI <uri> RESOURCE_PREFIX /qt/qml QML_FILES …)`.
   ([qt_add_qml_module](https://doc.qt.io/qt-6/qt-add-qml-module.html)).
2. Configure it with the **Visual Studio generator** (`-G "Visual Studio 17 2022" -A x64
   -DCMAKE_PREFIX_PATH=<Qt>/<ver>/<toolchain>`). It needs no compilation.
3. Read the generated project file: Qt's commands are embedded as custom-build steps, e.g.

   ```
   call .qt\bin\qt_setup_tool_path.bat <Qt>/bin/qmlcachegen.exe --bare --resource-path … \
        -I <build> -I <Qt>/qml -i <build>/<uri>/qmldir \
        --resource <build>/.qt/rcc/qmake_<uri>.qrc --dump-aot-stats --module-id=<uri>(<t>) \
        -o <build>/.rcc/qmlcache/<t>_qml/<file>_qml.cpp <src>/<file>.qml
   ```

   and inspect the generated `<t>_qml_loader_file_list.rsp` — that file is where the
   resource-vs-source-path distinction becomes obvious.
4. Copy the flags into `QtQml.targets`, adjust paths to the project's own qrc prefix, and record the
   Qt version in the file's header comment.

This "let Qt generate its own build files and read them" trick works for any internal Qt tool and
avoids trusting prose documentation (or a model's memory) for an unstable CLI.

## 7. Verifying that AOT is actually in effect

Do all four; each catches a different failure mode.

1. **Static:** the loader's keys must equal your `qrc:` paths.
   `Select-String qmlcache_loader.cpp -Pattern 'resourcePathToCachedUnit.insert'` → the strings must
   be `/qt/qml/…/qml/main.qml`-shaped resource paths. Source-path keys = silent no-op.
2. **Link:** per-file units contain no registration hook, so a successful link proves the loader's
   `extern` unit references resolved — i.e. both halves are in the binary.
3. **Runtime (decisive):** temporarily instrument the generated loader:

   ```cpp
   const QQmlPrivate::CachedQmlUnit *res
       = unitRegistry()->resourcePathToCachedUnit.value(resourcePath, nullptr);
   fprintf(stderr, "[QML_UNIT] %s %s\n", res ? "HIT " : "MISS", qPrintable(resourcePath));
   return res;
   ```

   Temporarily editing a generated file works because the generation targets are timestamp-based and
   will not overwrite it. Expect `HIT` for your documents and `MISS` for Qt's own
   `QtQuick/Controls` modules — then rebuild cleanly (delete the file) so the instrumentation does
   not ship.
4. **Measurement:** see §8. **Trap:** `QML_DISABLE_DISK_CACHE=1` also disables the AOT unit hook —
   with it set, *no* lookups occur at all and both A/B arms look identical, which reads as "AOT does
   nothing". If you want cold-cache numbers, clear the runtime cache directory instead
   (`%LOCALAPPDATA%\<AppName>\cache\qmlcache`), or drop the variable and measure with `QmlAotEnabled`
   toggled.

## 8. Empirical Performance Measurements

Method: Release x64 (Debug has QML debugging enabled), runtime QML disk cache cleared before each run,
3 runs, offscreen platform (`QT_QPA_PLATFORM=offscreen` + `QT_PLUGIN_PATH=<Qt>/plugins` because `windeployqt`
does not deploy `qoffscreen.dll` by default).

| | `engine.load()` (parse + compile + instantiate) | pre-engine (backend initialization) |
| --- | --- | --- |
| AOT off | 202 / 211 / 239 ms (median **211**) | 26–28 ms |
| AOT on | 58 / 58 / 60 ms (median **58**) | 24–26 ms |

≈ **153 ms (3.6×) off QML startup**; the C++ side is untouched by AOT (~26 ms), so the QML path
was the dominant startup cost (mostly Qt Quick Controls' own QML, which is why the win is large
even on small document counts).

Lint: 325 findings with an unresolved import → 251 once `MyProject.Models` became resolvable →
11 with the project's `.qmllint.ini` → **0** after clearing the backlog (§3.1.1). Compilation
statistics: 1565/1968 bindings compiled to native C++.

Remaining limits and what would remove them *(documented)*:

| Limit | Consequence | Removed by |
| --- | --- | --- |
| Indirect mode only | property reads through `required property` model references stay bytecode | `qmlsc` **Direct mode** (commercial add-on) |
| Shadow checking always on | fewer bindings compilable | `qmlsc` **Static mode** (commercial; invalid if properties are shadowed) |
| No `qmltc` here | document instantiation still goes through `QQmlComponent` | `qmltc` + private Qt API + `main.cpp` rewiring |

## 9. Checklist after a Qt or Qt VS Tools upgrade

1. `msbuild … /t:QmlToolingInfo` — tool paths still resolve, all three compilers exist.
2. `--help` each of `qmlcachegen`, `qmltyperegistrar`, `qmllint`, `moc`; diff against §3 and §6.
3. Full clean Debug + Release build; confirm `qmllint:`/`qmlcachegen:` messages appear.
4. Re-run §7 step 3 (loader HIT) — cheap insurance that the resource-path contract did not change.
5. Re-measure (§8) if startup matters.
6. Update this file and your project's build & tooling documentation.

## 10. Documentation links

**Qt QML tooling**
- [Qt Qml Tooling (index)](https://doc.qt.io/qt-6/qtqml-tooling.html)
- [qmllint](https://doc.qt.io/qt-6/qtqml-tooling-qmllint.html) · [QML lint warnings and errors](https://doc.qt.io/qt-6/qmllint-warnings-and-errors.html)
- [qmlcachegen](https://doc.qt.io/qt-6/qtqml-tool-qmlcachegen.html) · [Qt Quick Compiler](https://doc.qt.io/qt-6/qtqml-qtquick-compiler-tech.html) · [QML script compiler (`qmlsc`)](https://doc.qt.io/qt-6/qtqml-qml-script-compiler.html)
- [QML type compiler (`qmltc`)](https://doc.qt.io/qt-6/qtqml-qml-type-compiler.html)
- [qmltyperegistrar](https://doc.qt.io/qt-6/qtqml-tooling-qmltyperegistrar.html) · [Module definition qmldir files](https://doc.qt.io/qt-6/qtqml-modules-qmldir.html)
- [QML Language Server (`qmlls`)](https://doc.qt.io/qt-6/qtqml-tooling-qmlls.html)
- [`qt_add_qml_module` (the CMake equivalent we deliberately do not use)](https://doc.qt.io/qt-6/qt-add-qml-module.html)

**Qt VS Tools (MSBuild integration)**
- [Building (moc/uic/rcc rules, `QTMSBUILDS`)](https://doc.qt.io/qtvstools/qtvstools-explanation-building.html)
- [Configuring builds (Qt settings as MSBuild properties)](https://doc.qt.io/qtvstools/qtvstools-explanation-configuring-builds.html)
