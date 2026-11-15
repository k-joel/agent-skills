# Modern Qt 6 QML Best Practices for Visual Studio (MSBuild)

This guide adapts modern Qt 6 and QML best practices specifically for developers using Visual Studio with the native MSBuild engine (`.vcxproj`) and the Qt Visual Studio Tools extension. It has been structured for high performance, strict compile-time safety, seamless C++/QML integration, and clean declarative architecture.

---

## 1. Project Architecture & Code Generation
While Qt 6 heavily promotes CMake, you can achieve the exact same performance and compilation benefits in Visual Studio using Qt Visual Studio Tools.

- **Ahead-of-Time QML Compilation (`qmlcachegen`), wired explicitly**: Qt VS Tools ships MSBuild rules for moc, uic, and rcc only — there is **no** "QML Compiler" switch in **Qt Project Settings**, and `qmlcachegen` is an internal tool whose CLI carries no stability guarantee. In an MSBuild project, drive it from a dedicated targets file (e.g., `QtQml.targets`: `QmlTypeInfo` → `QmlCacheGen` → `QmlCacheLoader` → `QmlCompileGenerated`), with command lines captured from Qt's own `qt_add_qml_module` build and re-captured after a Qt upgrade. Empirical benchmarks on 64-bit desktop Release builds with a cold QML disk cache show substantial startup improvements (e.g., reducing `engine.load()` latency from 211 ms → 58 ms, over 3.6× faster). Disable in debug configurations with `/p:QmlAotEnabled=false`. Two things that look plausible but do not work in Qt 6: a loose `.qmlc` placed in a `.qrc` is ignored (AOT output is C++ compiled directly into the binary), and generating the unit-cache loader from *source* paths produces a loader that never matches the `qrc:` URLs the engine loads.
- **Give the linter/compiler type info for C++-registered types**: Types registered from C++ at runtime (such as with `qmlRegisterUncreatableType()`) have no metadata on disk, so `qmllint` and `qmlcachegen` warn about them (reporting hundreds of `[import]`/`[unresolved-type]` findings) and bindings touching them fall back to interpreted bytecode. Run `moc --output-json` + `qmltyperegistrar` during the build to generate a `.qmltypes` file (+ a companion `qmldir`) that is supplied to both tools via `-I`. Ensure model and backend headers carry `QML_ELEMENT`, `QML_UNCREATABLE`, or `QML_SINGLETON` macros.
- **Modern QML Module Registration**: Do not manually create legacy `.qrc` files in text editors. Right-click your project, select **Qt**, and use the **Add QML Module…** wizard, or declare proper module structures. This ensures QML types are properly registered into a named module URI with automated resource tracking.
- **Avoid Implicit File Imports**: Always import components using their module URI rather than relying on relative directory lookups (e.g., `import MyProject.Controls` instead of `import "../controls"`).
- **Use Versionless QML Imports in Qt 6**: Omit legacy version numbers in import statements (use `import QtQuick`, `import QtQuick.Controls`, `import MyProject.Module`). Versioned imports (`2.15`, `6.0`, etc.) are a Qt 5 legacy pattern and interfere with Qt 6's module versioning system.
- **Bundle Application Resources via QML Modules**: Bundle application resources through the module's resource system rather than relying on loose files on disk. Qt's resource system embeds images, icons, and QML files into the application binary under standardized namespaces (e.g., `qrc:/qt/qml/ModuleName/`). Keep resource files in the same directory structure as the module to prevent "component not found" errors from mismatched implicit imports.
- **Use Modern QML Tooling (`qmllint`) as a Build Gate**: Wire a `QmlLint` target into your build pipeline before compilation (`BeforeTargets="PrepareForBuild"`), running `qmllint` over all project QML files so QML errors fail the build instead of surfacing at runtime. Errors fail and warnings print by default; add `-W 0` to gate on warnings as well. Manage per-category severities in a project-level `.qmllint.ini` file (e.g., selectively disabling `UnqualifiedAccess` if migrating legacy QML hierarchies). Full reference: [qt-tooling-msbuild.md](qt-tooling-msbuild.md).
- **Automate Windows Deployment with `windeployqt`**: Running standalone `.exe` binaries outside Visual Studio fails with missing DLL errors (`0xC0000135`). Run `<QtBinDir>\windeployqt.exe --qmldir <project_dir> <path_to_exe>` as a post-build step to copy all required Qt DLLs, plugins, and QML engine modules next to the executable.

---

## 2. Strict Typing, Pragmas & Compilation Optimization
Qt 6 introduces a strict type system and compiler infrastructure (`qmlsc` and `qmltc`) to optimize the runtime pipeline.

- **Adopt Modern Qt 6 QML Pragmas**: Place modern pragmas at the very top of your QML documents to enable compiler optimizations and strict scoping:
  - `pragma ComponentBehavior: Bound` — Strongly binds components (like delegates in a `ListView`) to their declared scope, preventing expensive runtime lookups of properties outside the delegate and allowing `qmlsc` to fully compile the component.
  - `pragma ValueTypeBehavior: Addressable` — Allows direct in-place mutation of structured value type properties.
  - `pragma Singleton` — Designates standalone QML-defined style/constants singletons. Ensure that:
    1. The QML file begins with `pragma Singleton` (before imports).
    2. The `qmldir` module file declares `singleton <Type> <Type>.qml`.
    3. **Never double-register**: Do NOT register a QML singleton in `qmldir` and simultaneously call `qmlRegisterSingletonType()` in C++ (this causes conflicting registration errors).
- **Ban `property var` for Concrete Types**: Always declare explicit, strongly typed properties (`property string`, `property int`, `property MyCustomType`). Avoid `var` unless the property truly holds polymorphic arbitrary data.
- **Type-Annotate Functions**: Declare parameter and return types for your internal QML JavaScript functions to enable the compiler to optimize the logic paths:
  ```qml
  // ❌ Bad practice (slow, evaluated dynamically at runtime)
  function calculateArea(rect) { return rect.width * rect.height }

  // ✅ Good practice (fast, fully compiled to C++ bytecode)
  function calculateArea(rect: Item): real { return rect.width * rect.height }
  ```
- **Resolve Lookups via ID**: Avoid climbing the visual tree using fragile pointers like `parent.parent`. Use explicit visual item `id` references so the compiler can instantly resolve the bindings at build time.
- **Prefer Required Properties over Unqualified Upward Lookups**: Referencing a parent's property implicitly is fragile and slower to resolve. When a component needs data supplied from *outside* itself, declare it as a `required` property:
  ```qml
  Item {
      id: root
      property int rectangleWidth: 50
      Rectangle {
          width: root.rectangleWidth // Explicit ID reference
      }
  }
  ```
- **Leverage Lightweight Qt 6 Value Types (`Q_GADGET` / `QML_VALUE_TYPE`)**: For data transfer objects (DTOs), records, and settings structs, do not create heap-allocated `QObject` instances. Declare them as `Q_GADGET` with `QML_VALUE_TYPE`:
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
  Value types are stored on the stack, avoid heap allocation and garbage collection overhead, and provide compile-time type safety with full IDE auto-completion in QML.

---

## 3. Declarative Architecture over Imperative Logic

- **Strict Separation: Zero Business / Behavioral Logic in QML**:
  - Keep QML strictly for presentation (visual layouts, view states, animations, transitions, and user interaction capture).
  - Move all domain/business logic, controller actions, data validation, algorithms, state machines, file operations, and backend transactions into C++ Model/Util/Service `.hpp`/`.cpp` classes.
  - *Why:* Embedded JavaScript in QML cannot be unit-tested with standard C++ testing harnesses (`QTest`, `GoogleTest`), degrades V4 engine performance, breaks type safety, and clutters declarative UI definitions.
- **Prefer Declarative Bindings**: Bind properties declaratively to maintain reactivity and compile-time safety. Avoid imperative assignments inside signal handlers or `Component.onCompleted`.
- **Adopt MVVM/MVP**: Let your C++ backend expose pure data properties via `QAbstractListModel` or `Q_PROPERTY`, while your QML UI simply binds to and displays them.
- **Don't Store State in Delegates**: A delegate instance is created and destroyed repeatedly as items scroll in and out of view. Any state stored as a plain property on the delegate itself will be silently lost or reset. Store mutable state in the underlying C++ model.

---

## 4. Modern C++ Integration Standards
The legacy method of passing data via `rootContext()->setContextProperty()` is heavily discouraged in Qt 6 as it breaks compile-time safety and tool-assisted refactoring.

- **Inject Dependencies via `setInitialProperties`**: Expose root-level C++ backend objects to QML by declaring `required property` on the root QML component and populating them using `QQmlApplicationEngine::setInitialProperties()`:
  ```cpp
  QQmlApplicationEngine engine;
  engine.setInitialProperties({
      { "backendController", QVariant::fromValue(&my_controller) }
  });
  engine.loadFromModule("MyModule", "Main");
  ```
- **Use Registration Macros in C++ Headers**: Expose your C++ classes to QML globally using native macros directly inside your header files:
  - `QML_ELEMENT` for standard instantiable objects.
  - `QML_SINGLETON` for shared global managers.
  - `QML_UNCREATABLE` for enums or abstract base classes.
  - `QML_NAMED_ELEMENT(Name)` for custom QML naming.
  - `QML_VALUE_TYPE(name)` for lightweight `Q_GADGET` structs.
- **Guard All C++ Property Setters Against Redundant Emissions**: Every `Q_PROPERTY` setter in C++ must implement an equality guard before assigning state and emitting change signals:
  ```cpp
  auto set_status(const QString& status) -> void {
      if (_status == status) {
          return;
      }
      _status = status;
      emit status_changed();
  }
  ```
  *Why:* Emitting change signals when values have not changed triggers event cascades, high CPU usage, and infinite binding loops between C++ and QML.
- **Explicit QObject Ownership Between C++ and QML**: When returning a `QObject*` from a C++ method or invokable to QML, always ensure the object has a C++ `QObject` parent or explicitly assign ownership:
  ```cpp
  auto get_controller() -> MyController* {
      auto* ctrl = new MyController(this); // Explicit C++ parent prevents premature GC
      return ctrl;
  }
  ```
  *Why:* If a `QObject` without a parent is returned to QML, the QML engine assumes `JavaScriptOwnership` and deletes the C++ instance during garbage collection, causing dangling pointers and access violation crashes.
- **Use `Q_PROPERTY` for State, `Q_INVOKABLE` for Actions**: Expose state parameters via standard `Q_PROPERTY` with matching change notification signals to keep elements natively reactive. Reserve `Q_INVOKABLE` methods or C++ slots for triggering discrete commands, network requests, or complex transactions (e.g., `Backend.submitOrder()`). Do not use invokables merely to update simple state values.
- **Implement Robust C++ Models**: When exposing lists of data to QML, inherit from `QAbstractListModel` instead of passing `QList<QObject*>` or raw `QVariantList`. Expose your data safely to delegates using `roleNames()` and ensure you use `beginInsertRows()`/`endInsertRows()` to give the QML engine the lifecycle signals it needs to animate UI updates efficiently without resetting delegate state.
- **Modern `Connections` Syntax**: In Qt 6, avoid string-based or legacy syntax in `Connections`. Always use the function syntax with explicit parameter names:
  ```qml
  Connections {
      target: backendService
      function onErrorOccurred(errorCode: int, message: string) {
          notificationBanner.show(message);
      }
  }
  ```
- **Thread Safety Across GUI and Worker Threads**: Never manipulate QObjects created on or living in the main GUI/QML thread directly from background worker threads. Transfer data using Qt signals and slots across thread boundaries (`Qt::QueuedConnection`) or post execution via `QMetaObject::invokeMethod(targetObject, [=]() { ... }, Qt::QueuedConnection)`.
- **Use `QPointer<T>` for C++ Lifecycle Safety**: When C++ code stores references to `QObject` instances managed or dynamically destroyed by QML (such as items inside a `Loader` or dynamic delegates), wrap them in `QPointer<T>`. This automatically nulls the pointer if QML deletes the object, preventing use-after-free crashes.
- **Isolate Business Logic**: Ensure your C++ implementation remains entirely unaware of layout structures, element IDs, or visual nesting inside the QML tree.
- **Prefer Explicit Interaction Signals over `*Changed` Signals**: Where a control offers both a `valueChanged` signal and an explicit interaction signal (e.g., a Slider's `moved` or a TextField's `textEdited`), prefer the interaction signal for pushing updates back to the backend to avoid event cascades caused by programmatic updates, clamping, or rounding.
- **Make User-Facing Strings Translatable from the Start**: Wrap every user-visible string in `qsTr()` as you write it.

---

## 5. Layouts, Positioning & Visual Performance

- **Avoid Manual Coordinate & Size Arithmetic**:
  - Never position sibling items by chaining arithmetic expressions (e.g., `x: myElement.leftPadding + 23 + 55` or `x: prevItem.x + prevItem.width + 12`).
  - Rely on declarative **Positioners** (`Row`, `Column`, `Grid`, `Flow`), **Anchors**, or **Layouts** (`RowLayout`, `ColumnLayout`, `GridLayout`).
  - *Why:* Manual coordinate math is brittle, breaks upon refactoring or font scaling, and frequently triggers geometry binding loops.
- **Use the Right Layout Tool for the Job**:
  - **Top-level / Window Views**: Use `QtQuick.Layouts` (`RowLayout`, `ColumnLayout`, `GridLayout`) for fluid, responsive user interfaces that must resize children with window geometry. Use anchors to position the layout itself within its non-layout parent.
  - **Virtualized Delegates (`ListView`, `TableView`)**: Avoid heavy `QtQuick.Layouts` due to layout calculation overhead. Instead, use lightweight **Positioners** (`Row`, `Column`) or **explicit anchors** (`anchors.left: parent.left`, `anchors.verticalCenter: parent.verticalCenter`).
- **Geometry vs. Rendering Animations on Layout-Managed Items**:
  - Animating geometry properties (`x`, `y`, `width`, `height`) directly on children of a `RowLayout`/`ColumnLayout` fails because the layout actively overrides item geometry on each frame.
  - *Rendering animations* (`opacity`, `scale`, `rotation`) do not affect layout calculations and can be animated directly on layout children.
  - *Geometry animations* require wrapping the content in a plain `Item` that provides `Layout.preferredHeight: innerContent.implicitHeight` and animating geometry on the inner item inside the wrapper:
    ```qml
    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: innerColumn.implicitHeight
        ColumnLayout {
            id: innerColumn
            anchors.left: parent.left
            anchors.right: parent.right
            // Geometry-animated content here
        }
    }
    ```
- **Avoid Hardcoded Sizing**: Stop using static dimensions like `width: 400`. Rely on layouts combined with standard properties like `Layout.fillWidth: true` and `Layout.preferredWidth` to ensure clean responsiveness.
- **Respect Implicit Sizes**: Do not define preferred sizes for items that already provide `implicitWidth` and `implicitHeight`, unless their implicit sizes are unsatisfactory.
- **Eliminate Superfluous Visual Nodes**: Use plain `Item` instead of `Rectangle` when creating container wrappers, spacers, or logical groupings that do not render backgrounds or borders. An empty `Rectangle` creates unnecessary scene graph geometry nodes and shader switches in the `QRhi` pipeline.
- **Asynchronous Image & Media Loading**: Set `asynchronous: true` and `cache: true` on `Image` elements, and specify `sourceSize.width` / `sourceSize.height` for raster images to prevent decoding massive textures into GPU VRAM:
  ```qml
  Image {
      source: "qrc:/qt/qml/MyModule/images/large_photo.png"
      asynchronous: true
      sourceSize { width: 120; height: 120 } // Allocates GPU texture only for thumbnail size
  }
  ```
- **Throttle Heavy Visual Components**: Wrap heavy elements, popups, or multi-page systems inside a `Loader` component or a structured `StackLayout` to prevent cold application startup bottlenecks.
- **Be Careful with Rendering Clips**: Avoid overusing `clip: true` and extreme layer opacity masks unless critically necessary, as they force separate render passes that impact GPU pipelines.
- **Prefer Built-in Controls over Custom Ones**: Base custom controls on cross-platform styles like Basic, Fusion, Imagine, Material, or Universal.
- **Configure Portable Styles in C++ Initialization**: Windows and macOS native styles render using platform APIs and do not support standard `background:` / `contentItem:` customization (producing runtime warnings: `The current style does not support customization of this control`). Set the style to `Basic` or `Fusion` in C++ before initializing `QGuiApplication`:
  ```cpp
  qputenv("QT_QUICK_CONTROLS_STYLE", "Basic");
  QGuiApplication app(argc, argv);
  ```
- **Separate UI Logic from Visual Definitions**: When using Qt Design Studio, edit `.ui.qml` files only in the 2D view for visual parts, and move unsupported logic code to standard `.qml` files.

---

## 6. Resource, Asset & Engine Management

- **Standardize on Module-Relative Resource Paths**: Utilize the modern Qt 6 QML module resource namespace (`qrc:/qt/qml/ModuleName/...`) or module-relative paths (`"images/icon.png"`). Avoid scattered calls to `Qt.resolvedUrl()`.
- **Centralize Styling Singletons**: Group your color schemas, padding constants, and custom font assets inside a dedicated, globally accessible style singleton component:
  ```qml
  // Constants.qml
  pragma Singleton
  import QtQuick

  QtObject {
      readonly property color primaryColor: "#0066CC"
      readonly property int spacingMedium: 12
      readonly property int defaultRadius: 6
  }
  ```

---

## 7. QML Coding Conventions

- **Consistent Member Ordering**: Structure every QML object declaration in the exact order recommended by Qt, separated by blank lines:
  1. `id` (must always be the first line)
  2. property declarations
  3. signal declarations
  4. JavaScript helper functions
  5. object properties (grouped logically: geometry, appearance, states)
  6. child objects
- **Naming Conventions**: Use `PascalCase` for QML type names (e.g., `CustomButton.qml`) and `camelCase` for properties, signals, and function names.
- **NEVER Use `on` + Uppercase for Property Names**: The QML engine parses ANY property starting with `on` followed by an uppercase letter (e.g., `property color onSurface`, `property color onPrimary`, `property color onError`) as a signal handler for a signal named `Surface`/`Primary`. Assigning a value to it fails with:
  ```
  Cannot assign a value to a signal (expecting a script to be run)
  ```
  Use non-colliding prefixes instead: `contentSurface`, `textPrimary`, `fgError`, or `colorOnSurface`.
- **Use Grouped Property Notation**: When setting several properties from the same group, group notation is more readable than repeating the dotted prefix:
  ```qml
  Text {
      text: "Title"
      font { bold: true; italic: true; pixelSize: 20 }
  }
  ```
- **`Text` Styling vs. Typography Effects**: `Text.style` is strictly for dropshadow and 3D outlines (`Text.Outline`, `Text.Raised`, `Text.Sunken`). For strikethrough or underline, use `font.strikeout: true` or `font.underline: true`, not `Text.style`.
- **Omit Brackets for Single List Elements**: If a list property (like `states` or `transitions`) only contains a single element, omit the square brackets `[]` to improve readability:
  ```qml
  states: State { name: "active" }
  ```
- **Name Signal Handler Parameters Explicitly**: In Qt 6, use arrow function syntax with explicitly named arguments rather than relying on the implicit-parameter form:
  ```qml
  MouseArea {
      onClicked: mouse => { console.log(mouse.x, mouse.y); }
  }
  ```
- **One Property per Line**: Even for short expressions, declare each property assignment on its own line to keep diffs clean and make bindings easy to scan.
- **Avoid Large JavaScript Files (`.js`) for Shared Logic**: Multi-line `.js` files bypass static type analysis and C++ optimization. Use C++ helper singletons (`QML_SINGLETON`) for shared business logic and algorithmic parsing, keeping inline JavaScript strictly to simple 1-2 line UI expressions.

---

## 8. Scalability, Responsiveness & High-DPI Support

- **Rely on Qt 6 Engine High-DPI Scaling**: Modern Qt 6 handles high-DPI scaling automatically via `devicePixelRatio` and native OS integration. Do not use legacy manual scaling formulas (such as `scaleRatio = width / referenceWidth`), which distort desktop multi-windowing and dynamic resizing.
- **Design Responsive Breakpoints & Adaptive Layouts**: Build responsive UIs that adapt to container dimensions using dynamic layout properties or states:
  ```qml
  GridLayout {
      anchors.fill: parent
      anchors.margins: 16
      rowSpacing: 12
      columnSpacing: 12
      // Automatically reshapes from a row to a column based on aspect ratio
      flow: width > height ? GridLayout.LeftToRight : GridLayout.TopToBottom
  }
  ```
- **Preserve Anchor Containment for Orientation & Layout Transitions**: Keep anchor and layout definitions within the same containing component and animate them using `State` and `AnchorChanges`. Avoid destroying and recreating views via `Loader` during orientation/resize changes, which causes UI stutter, latency, and lost view states.
- **Provide High-DPI Image Variants**: Supply `@2x`, `@3x`, and `@4x` raster variants of icons and images alongside the base asset. Prefer SVG for small icons, or font-based icon sets (e.g., Font Awesome) for UI iconography.
- **Be Mindful of `BorderImage` 9-Slice on High-DPI**: `BorderImage` scales the 8 central grid regions but keeps the 4 corner patches at their exact pixel sizes. On high-DPI displays (e.g., 200% scaling), corners will appear unscaled and disproportionate unless multi-resolution assets (`@2x`, `@3x`) or vector-rendered shapes are supplied.
- **Guard Against Binding Overhead During Resizing**: Avoid complex JavaScript expressions in layout geometry bindings that re-evaluate on every resize frame. Rely on declarative static layout constraints (`Layout.fillWidth: true`, `Layout.preferredWidth`).
- **Load Platform- and Density-Specific Assets**: Use `QQmlFileSelector` to load alternate QML files or assets based on the runtime platform (e.g., an `+android` subfolder), rather than branching on platform checks scattered through application code.
- **Leverage ApplicationWindow Sizing**: When using `ApplicationWindow`, let it automatically calculate the effective size constraints of the actual window based on the size constraints of its content items.

---

## 9. Warnings, Common Pitfalls & Anti-Patterns

- **`Component.onCompleted` Misuse**: Do not use `Component.onCompleted` to assign a property that should instead be a declarative binding. An imperative assignment evaluates the property twice, delays type errors from build time to run time, and silently overwrites any declarative binding already in place. Reserve `Component.onCompleted` for genuine one-time imperative setup.
- **`target: parent` Inside Animations is `undefined`**: Animation elements (`NumberAnimation`, `PropertyAnimation`, `ParallelAnimation`, etc.) inherit from `QObject` (`QAbstractAnimation`), not `QQuickItem`. Because they are not visual items in the scene graph, they do not possess a visual `parent` property. Using `target: parent` throws `ReferenceError: parent is not defined`. Always assign an explicit `id` to the target visual item (`target: myTargetItem`).
- **Mixing Anchors and Layouts**: Do not anchor an item that is an immediate child of a layout. Use `Layout.preferredWidth` / `Layout.preferredHeight` there instead. Furthermore, **do not create bindings to the `x`, `y`, `width`, or `height` properties of items inside a Layout**, as this conflicts with the Layout's goals and causes binding loops.
- **Font Sizing and Accessibility**: Avoid mixing `font.pointSize` and `font.pixelSize` in the same container. Note that while `pixelSize` is easier for rigid UI layouts, `pointSize` natively respects user OS accessibility settings (like text scaling for visually impaired users). Choose one strategy for your app. If using `pointSize`, ensure UI containers use dynamic scaling or anchors rather than fixed pixel dimensions so text doesn't clip on high-DPI or scaled displays.
- **Avoid Missing Setter Guards in C++**: Never emit a `Q_PROPERTY` notify signal in C++ without verifying that the value has actually changed (`if (_value == newValue) return;`).
- **JavaScript Closures and Asynchronous Retainment**: Avoid capturing QML visual item references inside long-lived JavaScript timers or asynchronous network callbacks. This prevents the V4 garbage collector from releasing scene graph resources when views are unloaded, causing memory leaks and crashes if an asynchronous callback attempts to mutate an item after its C++ peer is deleted.
- **Dynamic Object Creation in Hot Paths**: Avoid calling `Qt.createQmlObject()` or `Component.createObject()` inside frequently evaluated loops, animations, or scroll handlers. Rely on declarative virtualized views (`ListView`, `TableView`) or `Loader` to avoid heap fragmentation and frame drops.
- **Two-Way Binding Loops with Form Inputs**: Synchronizing C++ state with interactive QML controls (such as `TextField` or `SpinBox`) via continuous `*Changed` signals causes infinite feedback loops and cursor-jumping glitches. Always pair C++ setter equality guards with explicit user-commit signals (`textEdited` or `editingFinished`) rather than raw property change signals.

