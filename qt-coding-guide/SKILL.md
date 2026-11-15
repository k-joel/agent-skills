---
name: qt-coding-guide
description: Modern Qt 6 and QML coding guide and MSBuild Windows tooling reference. Must be loaded whenever Qt/QML code is being created, edited, refactored, or reviewed, or when Qt C++ projects are being built with MSBuild on Windows.
---

# Qt 6 & QML Modern Coding Guide (Windows & MSBuild)

A distilled, comprehensive guide for developing modern, high-performance Qt 6 and QML desktop applications on Windows using Visual Studio and native MSBuild (`.vcxproj`).

## When to Load This Skill

> [!IMPORTANT]
> **Load this skill whenever:**
> - Writing, editing, refactoring, or reviewing Qt 6 C++ or QML code.
> - Integrating C++ backend models, services, or value types with QML.
> - Building, configuring, or troubleshooting Qt projects using Visual Studio / MSBuild (`.vcxproj`) on Windows.
> - Wiring or diagnosing Qt tooling (`qmllint`, `qmlcachegen`, `qmltyperegistrar`, `moc`, `windeployqt`).

---

## 1. Core Architectural Principles

### Strict MVVM & Separation of Concerns
- **QML is strictly presentation**: Visual layout, animations, states, and user interaction capture only.
- **C++ owns all business logic**: Algorithms, data validation, domain state, file I/O, networking, and worker threads belong in C++ classes.
- **No business logic in JavaScript**: Inline JavaScript in QML cannot be unit-tested with C++ harnesses (`QTest`/`GoogleTest`), slows the V4 engine, breaks type analysis, and degrades maintainability.

### Qt 6 Pragmas (Mandatory at Top of Documents)
Always place relevant pragmas before imports:
- `pragma ComponentBehavior: Bound`: Strongly binds components (e.g. delegate scopes in `ListView`), preventing expensive upward lookups and enabling static compilation.
- `pragma ValueTypeBehavior: Addressable`: Enables direct, in-place mutation of structured value type properties.
- `pragma Singleton`: Declares a QML singleton (pair with a `singleton <Type> <Type>.qml` entry in `qmldir`; never double-register in C++).

### Strict Typing & Static Safety
- **Ban `property var` for concrete types**: Always declare explicit types (`property string`, `property int`, `property Item`, `property MyCustomType`). Reserve `var` strictly for truly polymorphic payloads.
- **Type-annotate JavaScript functions**:
  ```qml
  // ✅ Fast, fully compiled to bytecode/native C++
  function calculateArea(rect: Item): real { return rect.width * rect.height; }
  ```
- **Lookup by explicit `id`**: Avoid climbing the visual tree via `parent.parent`. Use explicit IDs to resolve bindings at compile time.
- **Use `required property`**: When components need data from external parents or loaders, require them explicitly rather than relying on dynamic scope lookups.

### Lightweight Value Types (`Q_GADGET` / `QML_VALUE_TYPE`)
For data transfer objects (DTOs), records, and settings structs, avoid heap-allocated `QObject` instances. Declare stack-allocated structs with `Q_GADGET`:
```cpp
struct ItemRecord {
    Q_GADGET
    QML_VALUE_TYPE(itemRecord)
    Q_PROPERTY(int width MEMBER width)
    Q_PROPERTY(int height MEMBER height)
    Q_PROPERTY(double durationSec MEMBER durationSec)
public:
    int width = 0;
    int height = 0;
    double durationSec = 0.0;
};
```

---

## 2. Modern C++ & QML Integration

### Dependency Injection over Context Properties
- **Never use `rootContext()->setContextProperty()` in Qt 6**: It breaks compile-time type verification, confuses `qmllint`, and impairs tool refactoring.
- **Inject via `setInitialProperties()`**:
  ```cpp
  QQmlApplicationEngine engine;
  engine.setInitialProperties({
      { "backendController", QVariant::fromValue(&myController) }
  });
  engine.loadFromModule("MyProject.Module", "Main");
  ```
  In QML: `required property MyController backendController`

### Header Registration Macros
Register C++ types in headers using native macros (requires `#include <QtQmlIntegration>`):
- `QML_ELEMENT`: Standard instantiable QML item.
- `QML_SINGLETON`: Shared global manager.
- `QML_UNCREATABLE`: For enums or abstract interfaces.
- `QML_NAMED_ELEMENT(Name)`: Custom QML type name.
- `QML_VALUE_TYPE(name)`: For `Q_GADGET` value structs.

### Mandatory Setter Equality Guards
Every `Q_PROPERTY` setter must check for value changes before updating state and emitting change signals:
```cpp
void setStatus(const QString& status) {
    if (_status == status) return;
    _status = status;
    emit statusChanged();
}
```
*Missing guards cause cascading event loops, high CPU utilization, and infinite binding loops.*

### Memory Management & Thread Safety
- **Explicit QObject Ownership**: When returning a `QObject*` to QML from C++, ensure it has a C++ parent (`new MyController(this)`) or call `QQmlEngine::setObjectOwnership(obj, QQmlEngine::CppOwnership)`. Unparented objects are collected by QML garbage collection, producing dangling pointers and crashes.
- **Lifecycle Protection with `QPointer<T>`**: Store C++ references to QML-instantiated objects in `QPointer<T>` to automatically null pointers if QML destroys the item.
- **Thread Safety**: Never touch GUI/QML objects from worker threads. Communicate across threads exclusively via Qt signals/slots (`Qt::QueuedConnection`) or `QMetaObject::invokeMethod()`.
- **Model Exposure**: Inherit from `QAbstractListModel` with granular notifications (`beginInsertRows()`/`endInsertRows()`, `dataChanged()`). Never pass raw `QList<QObject*>` or untyped `QVariantList` for collections.

---

## 3. Layouts & Visual Performance

### Proper Layout Strategy
- **Top-level / Window Views**: Use `QtQuick.Layouts` (`RowLayout`, `ColumnLayout`, `GridLayout`) with `Layout.fillWidth: true` and `Layout.preferredWidth` for fluid, DPI-adaptive interfaces.
- **Virtualized Views (`ListView`, `TableView`)**: Avoid heavy `QtQuick.Layouts` inside delegates due to overhead during scrolling. Use lightweight **Positioners** (`Row`, `Column`) or **explicit anchors**.
- **Never anchor immediate children of a Layout**: Do not set `anchors` or bind `x`/`y`/`width`/`height` directly on layout children.
- **Animations in Layouts**:
  - *Rendering animations* (`opacity`, `scale`, `rotation`) can be applied directly to layout children.
  - *Geometry animations* must animate an inner child wrapped inside an outer `Item` that provides `Layout.preferredHeight: innerContent.implicitHeight`.

### Resource & Scene Graph Optimization
- **Eliminate Superfluous Visual Nodes**: Use a plain `Item` instead of `Rectangle` for non-rendering containers, wrappers, or spacers to avoid unnecessary scene graph nodes in `QRhi`.
- **Asynchronous Image Loading**: Set `asynchronous: true` and `cache: true` on `Image`. Always specify `sourceSize.width` and `sourceSize.height` for raster assets to prevent allocating massive textures in GPU VRAM.
- **Deferred Loading**: Wrap heavy popups, dialogs, or subpages in `Loader` or `StackLayout` to preserve instantaneous application startup.
- **Style Customization**: Set `qputenv("QT_QUICK_CONTROLS_STYLE", "Basic");` or `"Fusion"` before creating `QGuiApplication` if custom styling is needed on Windows (native styles reject `background`/`contentItem` customization).

---

## 4. QML Coding Conventions

- **Order of Members**:
  1. `id` (must always be first line)
  2. Property declarations (`property int ...`)
  3. Signal declarations (`signal ...`)
  4. JavaScript helper functions
  5. Object properties (geometry, appearance, states)
  6. Child visual objects
- **Identifier Naming**:
  - `PascalCase` for QML files/types (`CustomButton.qml`).
  - `camelCase` for properties, IDs, signals, and functions.
  - **CRITICAL**: **NEVER use `on` + Uppercase for property names** (e.g. `property color onPrimary`). The parser interprets this as a signal handler for `signal Primary()` and throws `Cannot assign a value to a signal`. Use `colorOnPrimary` or `textPrimary` instead.
- **Signal Handlers in Qt 6**: Use arrow function syntax with explicit parameter names:
  ```qml
  MouseArea {
      onClicked: mouse => { console.log(mouse.x, mouse.y); }
  }
  ```
- **Modern `Connections` Syntax**:
  ```qml
  Connections {
      target: backendService
      function onErrorOccurred(code: int, message: string) {
          notification.show(message);
      }
  }
  ```
- **Localization**: Wrap every user-visible string in `qsTr()` as it is written.

---

## 5. Windows MSBuild & Qt Tooling Architecture

### The MSBuild Division of Labor
- **Qt Visual Studio Tools** ships MSBuild rules for `moc`, `uic`, and `rcc` only.
- **There is NO built-in QML Compiler switch** in Visual Studio Qt Project Settings. All QML tooling (`qmllint`, `qmlcachegen`, `qmltyperegistrar`) must be driven via custom MSBuild targets.

### The Recommended Target Pipeline (`QtQml.targets`)
Import `QtQml.targets` as the **last** item in your `.vcxproj`:
```
QmlPrepareItems ──► QmlTypeInfo ──► QmlLint              (BeforeTargets=PrepareForBuild)
                              └───► QmlCacheGen ──► QmlCacheLoader ──► QmlCompileGenerated
                                                                      (BeforeTargets=ClCompile)
```

1. **`QmlPrepareItems`**: Runs every build; globs QML and C++ model headers and derives `.cpp` output and resource paths.
2. **`QmlTypeInfo`**: Runs `moc --output-json` per model header + `qmltyperegistrar` to generate `.qmltypes` and `qmldir`. Feeds `-I <IntDir>qmltypes` to both `qmllint` and `qmlcachegen` so C++ types are recognized at build time.
3. **`QmlLint`**: Executes `qmllint` across all QML files before compilation (`BeforeTargets="PrepareForBuild"`). Errors fail the build. Configure severities in `.qmllint.ini` (e.g., `UnqualifiedAccess=disable` for migrating legacy scopes).
4. **`QmlCacheGen` (AOT)**: Ahead-of-Time compiles QML documents into C++ units (`<file>_qml.cpp`).
   - Default: `QmlAotEnabled=false` in Debug (fast incremental developer workflow) and `true` in Release (~3.6x cold-cache startup speedup).
5. **`QmlCacheLoader`**: Generates `qmlcache_loader.cpp` using a response file (`@file.rsp`). **Contract**: The loader response file entries must match the exact `qrc:` resource paths loaded by the engine (not filesystem paths), or lookups silently miss.
6. **`QmlCompileGenerated`**: Injects generated `.cpp` units into `ClCompile` before compilation.

### Critical MSBuild Flags for Generated QML Sources
Generated `.cpp` units require specific compilation metadata:
- **`AdditionalOptions=/Zc:__cplusplus /utf-8`**: Required by MSVC so `__cplusplus` matches C++17/20; without it Qt's `qcompilerdetection.h` fails with `#error: Qt requires a C++17 compiler`.
- **`PrecompiledHeader=NotUsing`**: Generated units do not include project `pch.h`.
- **`AdditionalIncludeDirectories=$(QmlQtIncludeDir)`**: Points to `<Qt>/include` so module-prefixed headers (`<QtQml/qqmlprivate.h>`) resolve.
- **`Condition="'$(DesignTimeBuild)' != 'true'"`**: Prevents running slow tooling passes during Visual Studio IntelliSense design-time background builds.
- **Build the `.sln`**: Always build the solution or pass `/p:SolutionDir=<dir>\` to prevent sibling project include paths from breaking.

---

## 6. Anti-Patterns & Pitfalls Checklist

| Pitfall | Symptom / Consequence | Required Fix |
| --- | --- | --- |
| `Component.onCompleted` property assignments | Double-evaluation, breaks reactivity, delayed runtime errors | Use declarative property bindings instead |
| `target: parent` in animation elements | `ReferenceError: parent is not defined` | Animations inherit `QObject`, not `QQuickItem`. Set target by explicit `id` |
| Role lookup by hardcoded number (`0x0106`) | Silent data corruption when roles are inserted | Expose roles with `Q_ENUM` and reference `TypeName.RoleName` |
| Accessing GUI QObjects from worker thread | Intermittent memory corruption / crash | Transfer data via Qt signals/slots or `QMetaObject::invokeMethod(..., Qt::QueuedConnection)` |
| Omitting setter equality guards | Infinite binding loops, CPU spikes | Guard every setter with `if (_field == value) return;` |
| Passing unparented `QObject*` to QML | Crash via premature garbage collection | Ensure C++ parent exists or set explicit C++ ownership |
| Capturing QML visual items in JS closures | Memory leak; crash on asynchronous access | Avoid item capture in long-lived timers or callbacks |
| `qmllint` missing type cascade | Hundreds of `[import]`/`[unresolved-type]` warnings | Generate `.qmltypes` via `moc --output-json` + `qmltyperegistrar` |
| Cache loader keyed by source path | Silent AOT failure (engine loads bytecode) | Pass `qrc:` resource paths in the loader response file |

---

## 7. Deep Reference Documentation

For in-depth explanations, command-line arguments, empirical benchmarks, and configuration templates, consult the reference documents in this skill's `references/` directory:

- [Modern Qt 6 QML Best Practices](references/qt-best-practices.md): Full architectural guide covering typing pragmas, MVVM separation, layouts, responsive design, styling, and memory models.
- [Qt Tooling in an MSBuild Project](references/qt-tooling-msbuild.md): Full technical manual for driving `qmllint`, `qmlcachegen`, `qmltyperegistrar`, and `moc` from Visual Studio MSBuild without CMake, including upgrade checklists and troubleshooting gotchas.
