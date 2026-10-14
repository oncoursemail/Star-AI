# Swift (6.4, Swift 6 language mode) - STAR language research

> Status: checked on 2026-10-13 against swift.org/blog: **Swift 6.4 released 2026-09-15**, Swift 6.3 on 2026-03-24,
> Swift 6.2 in September 2025, Swift 6.0 in September 2024 (Swift 6 language mode with compile-time data-race
> safety). Use Swift for Apple platforms (iOS, macOS, visionOS, watchOS, tvOS), and increasingly for servers (Vapor,
> Hummingbird), Linux/Windows/Android tools, WebAssembly and embedded firmware (Embedded Swift).

## 0. Current version and what changed 2024-2026

- **Swift 6.0 (2024-09)**: Swift 6 **language mode** (opt in per target with `swiftLanguageModes: [.v6]` /
  `SWIFT_VERSION = 6`) makes data-race safety errors instead of warnings; typed throws (`throws(MyError)`);
  noncopyable generics (`~Copyable`); `Mutex` and `Atomic` in the `Synchronization` module; **Swift Testing**
  (`@Test`, `#expect`) ships with the toolchain; 128-bit integers; full Linux static SDK.
- **Swift 6.1 (2025-03)**: `nonisolated` on types and extensions, trailing commas in more lists, package traits,
  improvements to diagnostics groups.
- **Swift 6.2 (2025-09)** "approachable concurrency": opt-in **default main-actor isolation**
  (`-default-isolation MainActor`, ideal for apps/scripts), `nonisolated async` functions run in the **caller's**
  execution context (upcoming feature `NonisolatedNonsendingByDefault`), **`@concurrent`** to explicitly run on the
  concurrent pool, **`InlineArray`** (fixed-size inline storage: `var a: [40 of Sprite]`, i.e.
  `InlineArray<40, Sprite>`), **`Span`** (safe, non-escapable view of contiguous memory), opt-in **strict memory
  safety** mode (flags `unsafe` constructs), Embedded Swift with full `String`, Swift Testing exit tests and
  attachments, background indexing by default, typed `NotificationCenter` messages.
- **Swift 6.3 (2026-03-24)**: **`@c`** attribute to expose Swift functions/enums to C (and `@c @implementation` to
  implement a C header declaration in Swift), **module selectors** (`ModuleA::getValue()`, `Swift::Task`),
  `@specialize`, `@inline(always)`, `@export(implementation)`, Swift Build preview in SwiftPM, official Swift SDK for
  Android, Swift Testing warning issues, `Test.cancel()`, image attachments.
- **Swift 6.4 (2026-09-15)**: Swift Build is the **default** SwiftPM build system; **Subprocess 1.0**; `Span` bridges
  to C++20 `std::span`; `some P?` without parentheses (SE-0521); **`@diagnose`** attribute for per-source warning
  control (SE-0522); `await` allowed in `defer` (SE-0493); **`withTaskCancellationShield`** (SE-0504); borrow/mutate
  accessors (SE-0507); `Ref`/`MutableRef` (SE-0519); `UniqueBox` (SE-0517) and `UniqueArray` (SE-0527) for
  noncopyable values; noncopyable types can conform to `Equatable`/`Comparable`/`Hashable`; safe `RawSpan`
  load/store (SE-0525); `withTemporaryAllocation` initialized scratch buffers (SE-0524); XCTest and Swift Testing
  assertions interoperate (ST-0021); SBOM generation in SwiftPM (SE-0509); Embedded Swift supports existentials and
  `any Error`; Wasm SDK on swift.org.

Ask which Xcode/toolchain and which **language mode** (5 or 6) the project uses: the same code can compile cleanly in
Swift 5 mode and fail with concurrency errors in Swift 6 mode.

## 1. Mental model

- Safe by default: optionals instead of null, bounds-checked arrays, initialized variables, overflow traps, exclusive
  access enforcement.
- **Value types first**: `struct`, `enum`, tuples and standard collections (`Array`, `Dictionary`, `String`) have
  value semantics with **copy-on-write** storage. `class` and `actor` are reference types.
- Memory via **ARC** (automatic reference counting), not tracing GC: deterministic deinit, but reference cycles leak.
- Protocol-oriented: protocols with extensions, associated types, `some` (opaque) and `any` (existential) types.
- Structured concurrency with `async`/`await`, tasks and **actors**; the compiler proves data-race freedom in Swift 6
  mode via `Sendable` checking and isolation domains.
- Errors are thrown values marked at the call site with `try`.

## 2. Type system

- Integers `Int` (64-bit on 64-bit platforms), `Int8...Int128`, `UInt...`; `Double`, `Float`; `Bool`; `Character`
  (extended grapheme cluster); `String` (Unicode-correct, not integer-indexable).
- Arithmetic overflow **traps**; wrapping operators `&+`, `&-`, `&*`; `addingReportingOverflow`.
- No implicit numeric conversions: `Double(intValue)`.
- Optionals `T?` (`Optional<T>`): `if let x`, `guard let x else { return }`, `??`, optional chaining `a?.b`, force
  unwrap `!` (crashes on nil).
- `enum` with associated values and exhaustive `switch`; `indirect` for recursion.
- Protocols: requirements, default implementations in extensions, associated types, `some Protocol` (opaque, static
  dispatch), `any Protocol` (existential, boxed). Generic constraints `where T: Hashable`.
- `Sendable` marks types safe to share across concurrency domains; `@MainActor` and custom `actor` isolation;
  `nonisolated`; `@unchecked Sendable` is an escape hatch you must justify.
- Noncopyable types `~Copyable` with `consuming`/`borrowing` parameters; `~Escapable` (e.g. `Span`).
- Result builders (SwiftUI DSL), property wrappers (`@State`, `@Published`), macros (`@Observable`, `#Preview`,
  `#expect`).
- Typed throws `throws(ParseError)`.

## 3. Memory model and ownership

- ARC retains/releases class instances; when the count reaches zero, `deinit` runs immediately.
- **Retain cycles**: two objects holding strong references to each other, or a closure stored on `self` that captures
  `self` strongly, never deallocate. Fix with `weak` (optional, becomes nil) or `unowned` (non-optional, crashes if
  accessed after deallocation) captures: `{ [weak self] in guard let self else { return } ... }`.
- Delegates are usually `weak var delegate: Delegate?`.
- Value types copy on assignment, but standard collections share storage until mutated (copy-on-write). Large structs
  with class members behave partly like references: be careful.
- Exclusivity: overlapping access to the same variable (e.g. passing `&x` inout while reading `x`) is a compile-time
  or runtime error ("Overlapping accesses to 'x'").
- Unsafe pointers (`UnsafeMutablePointer`, `withUnsafeBytes`) bypass safety; 6.2's strict memory safety mode flags
  them; 6.4 adds safe alternatives (`Span`, `RawSpan` loads, `withTemporaryAllocation`).
- Noncopyable types and `consume` give unique ownership with no ARC traffic.

## 4. Concurrency

```swift
actor ScoreBoard {
    private var scores: [String: Int] = [:]
    func add(_ points: Int, for player: String) { scores[player, default: 0] += points }
    func top() -> [(String, Int)] { scores.sorted { $0.value > $1.value } }
}

@MainActor
final class GameModel: ObservableObject {
    @Published var leaders: [(String, Int)] = []
    let board = ScoreBoard()

    func refresh() async {
        leaders = await board.top()   // hop to the actor, back on the main actor for UI state
    }
}
```

- `async`/`await`; `Task { }` (inherits actor context), `Task.detached` (does not), `async let` for parallel child
  tasks, `withTaskGroup`/`withThrowingTaskGroup`, `AsyncSequence`/`AsyncStream`, `for await`.
- **Actors** serialize access to their state; calls from outside are `await`ed. Reentrancy: state can change across an
  `await` inside an actor method; re-check invariants after suspension.
- `@MainActor` for UI; with 6.2 default main-actor isolation, code is main-actor unless marked `nonisolated` or
  `@concurrent`.
- Cancellation is cooperative: `try Task.checkCancellation()`, `Task.isCancelled`; 6.4 adds
  `withTaskCancellationShield` for cleanup that must finish.
- Legacy GCD (`DispatchQueue`) and locks still exist; prefer actors, `Mutex` (Synchronization module, 6.0) for
  low-level shared state.
- Common Swift 6 diagnostics (quote exactly when helping):
  - "Sending 'x' risks causing data races" - a non-Sendable value crosses isolation; make it `Sendable`, keep it in one
    domain, or use `sending` parameters.
  - "Main actor-isolated property 'x' can not be mutated from a nonisolated context" / "Call to main actor-isolated
    instance method 'f()' in a synchronous nonisolated context" - mark the caller `@MainActor` or `await` it from an
    async context.
  - "Static property 'shared' is not concurrency-safe because it is nonisolated global shared mutable state" - make it
    `let` of a `Sendable` type, isolate it to `@MainActor`, or protect it (`nonisolated(unsafe)` only with a reason).
  - "Capture of 'x' with non-sendable type 'T' in a '@Sendable' closure" - make `T` Sendable or avoid the capture.
  - "Type 'X' does not conform to the 'Sendable' protocol" - make it a value type with Sendable members, an actor, or a
    final class with immutable Sendable state.

## 5. Error handling

```swift
enum SaveError: Error { case notFound(String), corrupt }

func loadSave(named name: String) throws(SaveError) -> SaveData {
    guard let url = Bundle.main.url(forResource: name, withExtension: "json") else {
        throw .notFound(name)
    }
    do {
        return try JSONDecoder().decode(SaveData.self, from: Data(contentsOf: url))
    } catch {
        throw .corrupt
    }
}

let data = try? loadSave(named: "slot1")      // nil on any error
```

- `throws` functions, `do { try ... } catch let e as MyError { } catch { }`; `try?` (to optional), `try!` (crash on
  error).
- Typed throws (Swift 6) for closed error sets; untyped `throws` remains the default for public APIs.
- `Result<Success, Failure>` for callbacks and storing outcomes.
- `precondition`, `assert` (debug only), `fatalError` for programmer errors.
- `defer` for cleanup (6.4 allows `await` inside `defer`).

## 6. Toolchain, build and package management

- Toolchains: Xcode on macOS (bundles Swift); **swiftly** to install/manage toolchains on Linux/macOS; Windows
  installer; static Linux SDK; Wasm and Android SDKs.
- **Swift Package Manager**: `swift package init --type executable`, `swift build`, `swift run`, `swift test`,
  `Package.swift` manifest:
  ```swift
  // swift-tools-version: 6.0
  import PackageDescription
  let package = Package(
      name: "Game",
      platforms: [.macOS(.v14)],
      dependencies: [.package(url: "https://github.com/apple/swift-collections", from: "1.1.0")],
      targets: [
          .executableTarget(name: "Game", dependencies: [.product(name: "Collections", package: "swift-collections")]),
          .testTarget(name: "GameTests", dependencies: ["Game"]),
      ]
  )
  ```
  `swift-tools-version: 6.0` enables the Swift 6 language mode by default for the package's targets.
- Swift Build is the default SwiftPM build engine in 6.4; SBOM generation (SE-0509).
- Xcode projects for apps; CocoaPods is in maintenance (read-only trunk announced for 2026); prefer SwiftPM.
- Linters/formatters: `swift format` (bundled since 6.0), SwiftLint. LSP: SourceKit-LSP; VS Code extension (Open VSX).

## 7. Testing

- **Swift Testing**: `import Testing`; `@Test func scoring() { #expect(score(3) == 30) }`; `#require` (throws, stops
  the test); parameterized tests `@Test(arguments: [1, 2, 3])`; `@Suite`; traits (`.tags`, `.disabled`, `.timeLimit`);
  exit tests (6.2); `Test.cancel()` and warning issues (6.3); repetition and attachments (6.4).
- **XCTest** (`XCTestCase`, `XCTAssertEqual`) still used for UI tests and older code; 6.4 lets `XCTAssert` and
  `#expect` be used across both.
- `swift test --parallel`; Xcode test plans; code coverage in Xcode or `swift test --enable-code-coverage`.
- Sanitizers: `-sanitize=address`, `-sanitize=thread` (`swift build -Xswiftc -sanitize=thread`), Xcode's Thread
  Sanitizer and Main Thread Checker.

## 8. Idiomatic patterns

- `guard let` early exits; value types for models; `final class` when reference identity is needed.
- Protocol-oriented design with extensions; prefer `some P` over `any P` for performance.
- `@Observable` (Observation framework) for SwiftUI models (iOS 17+); `@State`, `@Binding`, `@Environment`.
- Enums with associated values for state machines and results.
- Closures with `[weak self]` in long-lived callbacks.
- `Codable` for JSON/plist serialization.
- Actors for shared mutable state; `AsyncStream` to bridge callbacks to async.
- Access control: `private`, `fileprivate`, `internal` (default), `package` (5.9), `public`, `open`.

## 9. Top 30 pitfalls and compiler-error fixes

1. **`Value of optional type 'String?' must be unwrapped to a value of type 'String'`** - `if let`, `guard let`, `??`.
2. **`Fatal error: Unexpectedly found nil while unwrapping an Optional value`** - a `!` force unwrap or implicitly
   unwrapped optional (`@IBOutlet`) was nil.
3. **`Fatal error: Index out of range`** - check `indices.contains(i)` or use `first`/`last`.
4. **Retain cycles in closures** - `[weak self]`; Instruments' Leaks / Memory Graph Debugger.
5. **`unowned` crash after deallocation** - prefer `weak` unless lifetimes are guaranteed.
6. **`Cannot assign to property: 'self' is immutable`** - mutating a struct property in a non-`mutating` method.
7. **`Escaping closure captures mutating 'self' parameter`** - structs cannot be captured mutably by escaping
   closures; use a class or copy values.
8. **`Expression is 'async' but is not marked with 'await'`** - add `await` (and make the caller `async`).
9. **`Call can throw but is not marked with 'try'`** - `try`, inside `do/catch` or a throwing function.
10. **`'async' call in a function that does not support concurrency`** - wrap in `Task { }` or make the function
    `async`.
11. **"Sending 'x' risks causing data races"** (Swift 6 mode) - see section 4.
12. **"Main actor-isolated ... from a nonisolated context"** - add `@MainActor` or `await`.
13. **"... is not concurrency-safe because it is nonisolated global shared mutable state"** - global `var`s.
14. **`Type 'X' does not conform to protocol 'Sendable'`** - restructure or isolate.
15. **Actor reentrancy bugs** - state checked before an `await` is stale after it.
16. **Updating UI off the main thread** - "Publishing changes from background threads is not allowed"; use
    `@MainActor`.
17. **`Protocol 'P' can only be used as a generic constraint because it has Self or associated type requirements`**
    (old message) / need `any P` - write `any P` or use generics/`some P`.
18. **`Use of protocol 'P' as a type must be written 'any P'`** (Swift 6 with `ExistentialAny` upcoming feature).
19. **String indexing** - `s[0]` does not compile; use `s[s.index(s.startIndex, offsetBy: 3)]`, `s.prefix(3)`, or
    `Array(s)`.
20. **Integer overflow traps** - `Int8(200)` crashes; use `Int8(clamping:)`/`Int8(truncatingIfNeeded:)` or wrapping ops.
21. **`Reference to property 'x' in closure requires explicit use of 'self'`** - write `self.x` (or `[self]`
    capture list) for escaping closures in classes.
22. **Value vs reference confusion** - modifying a copied struct does not change the original; use `inout` or a class.
23. **Copy-on-write surprises with large arrays in structs** captured by closures (unexpected copies) - measure.
24. **`Missing return in a function expected to return 'T'`**.
25. **`Switch must be exhaustive`** - add cases or `@unknown default` for library enums.
26. **`Ambiguous use of 'x'`** across modules - 6.3 module selectors `ModuleA::x`.
27. **Swift 5 -> 6 mode migration floods of errors** - migrate target by target; enable upcoming features one at a
    time (`StrictConcurrency`, `NonisolatedNonsendingByDefault`), use 6.2 default MainActor isolation for app targets.
28. **`Task { }` captures `self` strongly** and outlives the view; store and cancel tasks, or use SwiftUI `.task {}`
    which cancels automatically.
29. **`Codable` key mismatch** - `keyNotFound` errors; use `CodingKeys` or `keyDecodingStrategy`.
30. **Floating point `==`** and `Double` money - use `Decimal` for currency.
31. **Forgetting `@Sendable`/`sending` on closures passed across tasks** in libraries.

## 10. Performance

- Measure with Instruments (Time Profiler, Allocations, Leaks, Swift Concurrency instrument), `swift build -c
  release`, `-Ounchecked` only for measured hot code.
- Prefer structs and `final` classes (static dispatch), generics over existentials (`some` over `any`),
  `ContiguousArray`, `reserveCapacity`, avoid repeated string concatenation in loops.
- Avoid ARC traffic in tight loops (noncopyable types, `borrowing`/`consuming`, `Span`, `InlineArray`, 6.4
  `UniqueArray`/`UniqueBox`).
- Whole-module optimization (default in release), `@inlinable` for cross-module generics, `@specialize` (6.3).
- SwiftUI: keep view bodies cheap, use `@Observable` for fine-grained invalidation.

## 11. Security

- Memory-safe by default; unsafe pointer APIs, `unowned(unsafe)`, `@unchecked Sendable`, and C interop are the
  exceptions; enable strict memory safety (6.2) in security-sensitive modules to audit them.
- Apple rewrote the TrueType hinting interpreter from C to Swift for memory safety (swift.org, June 2026): a model for
  parsing untrusted input in Swift.
- Injection: SQLite via bound parameters (`sqlite3_bind_*`, GRDB/SQLite.swift parameter APIs); `Process`/Subprocess
  with argument arrays, never shell strings; WebView JavaScript bridges need allowlists.
- Secrets: Keychain, not `UserDefaults`; App Transport Security (HTTPS by default); CryptoKit for crypto.
- Deserialization: `Codable` is data-only; avoid `NSKeyedUnarchiver` without `requiresSecureCoding`
  (`unarchivedObject(ofClass:from:)`).
- Supply chain: SwiftPM `Package.resolved` pins; review dependencies; SBOM generation (6.4).

## 12. Game-development usage

- **SpriteKit** (2D), **GameplayKit** (state machines, pathfinding, randomization), **RealityKit** (3D/AR, visionOS;
  Apple's recommended 3D framework), **Metal** (GPU API; Metal 4 announced 2025), **Game Controller** framework,
  **GameKit** (Game Center). **SceneKit** was deprecated by Apple at WWDC 2025 in favour of RealityKit (verify your
  target OS; existing apps still run).
- Cross-platform: **SwiftGodot** (Godot 4 GDExtension bindings in Swift), Swift + SDL/raylib via C interop, Swift on
  Windows/Linux/Android SDKs.
- Embedded Swift for microcontroller games/handhelds (Playdate examples exist from the Swift community).
- Embedding Lua: call the Lua or Luau C API directly via a C module map (Swift imports C headers natively); 6.3 `@c`
  helps expose Swift callbacks to C.
- Roblox mapping: `RunService.Heartbeat` -> `SKScene.update(_:)` / `CADisplayLink`; `TweenService` -> `SKAction` /
  SwiftUI animations; `ModuleScript` -> Swift module/type; `RemoteEvent` -> GameKit real-time matches or your own
  networking.

## 13. Cheat sheet: Swift vs Luau

| Concept | Luau | Swift |
|---|---|---|
| Variable | `local x = 1` | `var x = 1` / `let x = 1` (constant) |
| Nil | `nil` | `nil` only for optionals `T?` |
| Number | `number` | `Int`, `Double`, `Float`, explicit conversions |
| Integer division | `7 // 2` floored | `7 / 2 == 3` truncated (`-7 / 2 == -3`) |
| Overflow | float math, no overflow | traps; `&+` wraps |
| Indexing | 1-based | 0-based arrays; `String` uses `String.Index` |
| Array | `{1, 2, 3}` | `[1, 2, 3]` (`[Int]`), value semantics |
| Map | `{a = 1}` | `["a": 1]` (`[String: Int]`) |
| Length | `#t` | `array.count`, `string.count` (characters) |
| String concat | `a .. b` | `a + b`, `"\(a)\(b)"` interpolation |
| Format | `string.format("%.2f", x)` | `String(format: "%.2f", x)`, `x.formatted(.number.precision(.fractionLength(2)))` |
| Function | `local function f(a)` | `func f(_ a: Int) -> Int` (argument labels) |
| Closure | `function(x) return x + 1 end` | `{ x in x + 1 }`, `$0` shorthand |
| Multiple returns | `return a, b` | tuples `(Int, String)` |
| Module | `require` | `import Module` (module = target) |
| Class | metatable | `struct` (value) / `class` (reference) / `actor` |
| Method | `obj:M()` | `obj.m()` |
| Inheritance | metatable chain | single class inheritance + protocols |
| Error raise | `error("x")` | `throw MyError.x` |
| Error catch | `pcall` | `do { try f() } catch { }`, `try?` |
| Coroutine | `coroutine`, `task.spawn` | `Task { }`, `async let`, task groups |
| Wait | `task.wait(1)` | `try await Task.sleep(for: .seconds(1))` |
| Events | `:Connect` | closures, Combine, `AsyncStream`, NotificationCenter |
| Types | gradual | static, inferred, generics, protocols |
| Generics | `<T>` | `func f<T: Comparable>(_ x: T)` |
| Iteration | `for i, v in ipairs(t)` | `for (i, v) in array.enumerated()` |
| Equality | `==` | `==` via `Equatable`, `===` identity for classes |
| Memory | GC | ARC (reference counting) |
| Truthiness | `nil`/`false` falsy | only `Bool` |

## 14. Sources

Releases:
- https://www.swift.org/blog/swift-6.4-released/ - Swift 6.4 (2026-09-15)
- https://www.swift.org/blog/swift-6.3-released/ - Swift 6.3 (2026-03-24)
- https://www.swift.org/blog/swift-6.2-released/ - Swift 6.2 approachable concurrency, InlineArray, Span
- https://www.swift.org/blog/announcing-swift-6/ - Swift 6.0, language mode, Swift Testing
- https://www.swift.org/swift-evolution/ - evolution dashboard (SE proposals)
- https://www.swift.org/install/ - toolchains, swiftly

Language and concurrency:
- https://docs.swift.org/swift-book/documentation/the-swift-programming-language/ - The Swift Programming Language
- https://docs.swift.org/swift-book/documentation/the-swift-programming-language/automaticreferencecounting/ - ARC
- https://docs.swift.org/swift-book/documentation/the-swift-programming-language/concurrency/ - concurrency
- https://www.swift.org/migration/documentation/migrationguide/ - Swift 6 migration guide
- https://www.swift.org/documentation/concurrency/ - data-race safety
- https://github.com/swiftlang/swift-evolution/blob/main/proposals/0413-typed-throws.md - typed throws

Tooling, testing, security:
- https://www.swift.org/documentation/package-manager/ - SwiftPM
- https://developer.apple.com/documentation/testing - Swift Testing
- https://developer.apple.com/documentation/xctest - XCTest
- https://www.swift.org/blog/ - TrueType interpreter rewrite and other posts
- https://developer.apple.com/documentation/security/keychain_services - Keychain

Game development:
- https://developer.apple.com/documentation/spritekit - SpriteKit
- https://developer.apple.com/documentation/realitykit - RealityKit
- https://developer.apple.com/documentation/metal - Metal
- https://developer.apple.com/documentation/gameplaykit - GameplayKit
- https://github.com/migueldeicaza/SwiftGodot - SwiftGodot
