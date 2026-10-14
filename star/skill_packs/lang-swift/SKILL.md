---
name: lang-swift
description: Swift 6.4 and the Swift 6 language mode: optionals, ARC and retain cycles, async/await, actors, Sendable data-race errors, SwiftPM and Swift Testing. Use for Swift code, Xcode/swiftc errors, concurrency diagnostics, SwiftUI state, or SpriteKit/RealityKit games.
---
# Swift 6.4 (Swift 6 language mode)
- Current: Swift 6.4 (2026-09-15); 6.3 (2026-03) added `@c` and module selectors (`ModuleA::name`); 6.2 added opt-in default MainActor isolation, `@concurrent`, `InlineArray`, `Span`. Ask whether the target uses language mode 5 or 6: Swift 6 mode turns data-race warnings into errors.
- Concurrency errors and fixes: "Sending 'x' risks causing data races" - keep the value in one isolation domain or make it Sendable; "Main actor-isolated ... from a nonisolated context" - mark the caller `@MainActor` or `await` it; "... is not concurrency-safe because it is nonisolated global shared mutable state" - make it `let` of a Sendable type or isolate it to an actor. `@unchecked Sendable` and `nonisolated(unsafe)` need a written reason.
- Actors serialize their state, but state can change across an `await` inside an actor method: re-check after suspension.
- Optionals: use `if let`, `guard let ... else { return }`, `??`; `!` crashes with "Unexpectedly found nil".
- ARC: closures stored on `self` that capture `self` strongly leak; use `[weak self]` and `guard let self`. Delegates are `weak`. Prefer `weak` over `unowned`.
- Value types: structs, arrays, dictionaries and strings copy (copy-on-write); mutate in `mutating` methods ("Cannot assign to property: 'self' is immutable").
- Errors: `throws`, `try`, `do/catch`, `try?`; typed throws `throws(MyError)`; "Call can throw but is not marked with 'try'"; "Expression is 'async' but is not marked with 'await'".
- Tasks: `Task {}` inherits the actor; store and cancel long-lived tasks (SwiftUI `.task {}` cancels automatically); check `Task.isCancelled`; 6.4 has `withTaskCancellationShield` for cleanup.
- Strings are not integer-indexed: use `prefix`, `String.Index`, or `Array(s)`. Integer overflow traps; use `&+` to wrap.
- Tooling: SwiftPM (`swift build`, `swift test`, `swift-tools-version: 6.0` enables Swift 6 mode), Swift Testing (`@Test`, `#expect`, `#require`), XCTest for UI tests, `swift format`, Thread Sanitizer.
- Security: Keychain for secrets, bound SQLite parameters, Subprocess or `Process` with argument arrays, `NSKeyedUnarchiver` only with secure coding; strict memory safety mode (6.2) audits unsafe pointers.
- Games: SpriteKit, GameplayKit, RealityKit, Metal; SceneKit is deprecated in favour of RealityKit.
