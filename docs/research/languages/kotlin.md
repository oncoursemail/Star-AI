# Kotlin (2.4.x, K2 compiler) - STAR language research

> Status: checked on 2026-10-13 against kotlinlang.org: **Kotlin 2.4.0 released 2026-07-14** (current bug-fix line
> 2.4.21 per the release-process page), 2.3.0 on 2025-12-16, 2.2.0 on 2025-06-23; **2.5.0 planned for December 2026**.
> Language releases (2.x.0) come every six months, tooling releases (2.x.20) three months later. The **K2 compiler**
> is the default since 2.0 (May 2024). Use Kotlin for Android (Google's preferred language), JVM backends (Spring,
> Ktor), Kotlin Multiplatform (shared code for Android/iOS/desktop/web) and Gradle build scripts.

## 0. Current version and what changed 2024-2026

- **2.0 (2024-05)**: K2 compiler stable and default (faster, smarter smart casts), Compose compiler moved into the
  Kotlin repo.
- **2.1 (2024-11)**: previews of guard conditions in `when`, non-local `break`/`continue`, multi-dollar string
  interpolation (`$$"..."`).
- **2.2 (2025-06-23)**: guard conditions (`when (x) { is A if x.ok -> ... }`), non-local break/continue and multi-dollar
  interpolation **stable**; **context parameters** in preview (`-Xcontext-parameters`), replacing the old context
  receivers.
- **2.3 (2025-12-16)**: nested type aliases and data-flow-based exhaustiveness for `when` stable; `return` in
  expression bodies with explicit return types enabled by default; **unused return value checker** (experimental);
  explicit backing fields (experimental); stable time tracking API and improved `Uuid`; Kotlin/Native C/Objective-C
  import in Beta; Swift export improvements.
- **2.4 (2026-07-14)**: **context parameters stable** (except explicit context arguments and callable references),
  **explicit backing fields stable**, `@all` annotation meta-target and new use-site defaulting rules stable, stable
  common `Uuid` API, sorted-order checks; experimental **collection literals** (`[1, 2, 3]`), explicit context
  arguments, improved compile-time constants, `returnsResultOf()` contract, `@IntroducedAt` for binary-compatible
  optional parameters; Kotlin/JVM supports Java 26; Kotlin/Native CMS GC by default and Swift packages as
  dependencies; Wasm incremental compilation by default; Gradle 9.5 compatibility.

Experimental features need opt-in compiler flags; do not present them as standard Kotlin.

## 1. Mental model

- Statically typed, concise, null-safe language compiling to JVM bytecode, JavaScript, WebAssembly and native
  (LLVM). 100% Java interop on the JVM.
- Everything is an expression where reasonable (`if`, `when`, `try` return values).
- Immutability by default encouraged: `val` vs `var`, read-only collection interfaces (`List` vs `MutableList`).
- Null safety in the type system: `String` cannot be null, `String?` can.
- Coroutines for asynchronous code with **structured concurrency**: every coroutine lives in a scope that waits for
  its children and propagates cancellation.
- Extension functions and lambdas with receivers enable DSLs (Gradle Kotlin DSL, Compose UI, Ktor routing).

## 2. Type system

- Types: `Int`, `Long`, `Double`, `Float`, `Boolean`, `Char`, `String`, unsigned `UInt`..., `Unit`, `Nothing`,
  `Any`/`Any?`. Primitives are optimized to JVM primitives where possible.
- No implicit widening: `val l: Long = intValue` fails; use `.toLong()`.
- Classes are `final` by default (`open` to allow inheritance); `data class` (equals/hashCode/toString/copy/component
  functions), `sealed class`/`sealed interface` (exhaustive `when`), `enum class`, `object` (singleton), `companion
  object`, `value class` (inline wrapper), `fun interface` (SAM).
- Generics with declaration-site variance (`out T`, `in T`), use-site projections, reified type parameters in
  `inline` functions (`inline fun <reified T> parse(): T`), type erasure on the JVM otherwise.
- Smart casts after `is` checks and null checks (K2 handles more cases: local `val`s, `&&` chains).
- Nullability operators: `?.`, `?:` (Elvis), `!!` (throws `NullPointerException`), `let`, `requireNotNull`.
- **Platform types** `String!` from Java: nullability unknown; annotate Java with `@Nullable`/JSpecify or treat as
  nullable.
- Context parameters (stable in 2.4): `context(logger: Logger) fun process() { logger.info("...") }`.

## 3. Memory model and ownership

- JVM/Android: garbage collected like Java (see java.md). Kotlin/Native: its own tracing GC (CMS default in 2.4),
  shared-memory model with no freezing (since 1.7.20).
- Resources: `use {}` closes `Closeable`/`AutoCloseable` (`File("x").bufferedReader().use { it.readText() }`).
- Leaks on Android: holding `Activity`/`Context`/`View` in long-lived objects or coroutines (use `viewModelScope`,
  `lifecycleScope`, weak references), forgetting to cancel jobs.
- Collections: `listOf` returns a read-only view, not necessarily immutable; `toList()` copies.

## 4. Concurrency

```kotlin
suspend fun loadDashboard(api: Api): Dashboard = coroutineScope {
    val user = async { api.user() }          // runs concurrently
    val stats = async { api.stats() }
    Dashboard(user.await(), stats.await())   // if one fails, the other is cancelled
}

class GameViewModel(private val repo: Repo) : ViewModel() {
    val state: StateFlow<UiState> = repo.scores()
        .map { UiState(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), UiState.Loading)
}
```

- `kotlinx.coroutines`: `launch` (fire and forget within a scope, returns `Job`), `async`/`await` (`Deferred`),
  `coroutineScope`/`supervisorScope`, `withContext(Dispatchers.IO)` for blocking I/O, `Dispatchers.Default` for CPU,
  `Dispatchers.Main` for UI.
- **Do not use `GlobalScope`** (no structured lifetime); use lifecycle scopes or an injected `CoroutineScope`.
- Cancellation is cooperative: suspending functions check it; long CPU loops call `ensureActive()`/`yield()`; never
  swallow `CancellationException` (catching `Exception` in a coroutine does that; rethrow it).
- `runBlocking` only in `main` and tests, never on Android main thread or inside coroutines.
- **Flow**: cold streams (`flow {}`, `map`, `filter`, `collect`); `StateFlow`/`SharedFlow` hot streams; `flowOn`
  changes upstream context; collect UI flows with `repeatOnLifecycle`.
- Shared mutable state: `Mutex` (`withLock`), atomics (`kotlin.concurrent.atomics` or `java.util.concurrent`),
  confinement to one dispatcher, `Channel`s.

## 5. Error handling

- Exceptions are all unchecked (no `throws` clauses); `@Throws` only for Java/Swift interop.
- `try` is an expression: `val n = try { s.toInt() } catch (e: NumberFormatException) { 0 }`; prefer
  `s.toIntOrNull() ?: 0`.
- Preconditions: `require(arg > 0) { "..." }` (IllegalArgumentException), `check(state)` (IllegalStateException),
  `error("msg")`.
- `Result<T>` and `runCatching {}` for wrapping; careful: `runCatching` also catches `CancellationException` in
  coroutines.
- Sealed result hierarchies (`sealed interface LoadResult { data class Ok(...); data class Err(...) }`) for domain
  errors.
- `CoroutineExceptionHandler` for uncaught errors in `launch`; `async` errors surface at `await()`.

## 6. Toolchain, build and package management

- **Gradle with the Kotlin DSL** (`build.gradle.kts`) is standard; Maven supported; Amper is JetBrains' experimental
  build tool.
  ```kotlin
  plugins { kotlin("jvm") version "2.4.21" }
  kotlin { jvmToolchain(21) }
  dependencies {
      implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:<version>")
      testImplementation(kotlin("test"))
  }
  ```
  Version catalogs (`gradle/libs.versions.toml`) for dependency versions.
- Kotlin Multiplatform (KMP): `kotlin("multiplatform")` with `commonMain`, `androidMain`, `iosMain`; `expect`/`actual`
  declarations; Compose Multiplatform for shared UI.
- Compiler options: `kotlin { compilerOptions { allWarningsAsErrors.set(true); freeCompilerArgs.add("-Xcontext-
  parameters") } }` (only for preview features in older versions).
- Linters/formatters: ktlint, detekt, IntelliJ inspections. kotlinx.serialization (compiler plugin) for JSON.
- Scripts: `.main.kts` scripts; Kotlin notebooks.

## 7. Testing

- `kotlin.test` (multiplatform asserts), JUnit 5 on the JVM, **Kotest** (specs, property testing), **MockK** (mocks
  for Kotlin, including `coEvery` for suspend functions), Turbine for Flow testing.
- `kotlinx-coroutines-test`: `runTest { }` with virtual time, `StandardTestDispatcher`, `advanceUntilIdle()`;
  `Dispatchers.setMain` for Android ViewModels.
- Android: JUnit + Robolectric, instrumented tests, Compose UI tests.

## 8. Idiomatic patterns

- Data classes + `copy()` for immutable state; sealed interfaces for UI state and events (MVI/MVVM).
- Scope functions: `let` (null-safe transform), `apply` (configure an object), `also` (side effects), `run`, `with`;
  do not nest them deeply.
- Extension functions to add helpers without inheritance; keep them discoverable.
- `when` as an exhaustive expression over sealed types and enums.
- Collections API: `map`, `filter`, `associateBy`, `groupBy`, `fold`, `sumOf`, `firstOrNull`; `asSequence()` for long
  lazy pipelines.
- Delegation: `by lazy {}`, `by Delegates.observable`, class delegation `class X(list: List<T>) : List<T> by list`.
- Named and default arguments instead of overloads/builders.
- Dependency injection: Hilt/Dagger (Android), Koin, Spring.

## 9. Top 30 pitfalls and compiler-error fixes

1. **`Only safe (?.) or non-null asserted (!!.) calls are allowed on a nullable receiver of type 'String?'`** -
   handle null with `?.`, `?:`, `if (x != null)`, or `let`.
2. **`Type mismatch: inferred type is String? but String was expected`** - provide a default (`?: ""`) or change the
   parameter type.
3. **Overusing `!!`** - crashes with NPE; replace with real null handling.
4. **`Smart cast to 'X' is impossible, because 'y' is a mutable property that could have been changed by this
   time`** - copy to a local `val` first.
5. **`Val cannot be reassigned`** - use `var` or rethink.
6. **`'when' expression must be exhaustive, add necessary 'else' branch`** - add branches or seal the hierarchy.
7. **`Unresolved reference: X`** - missing import, dependency, or extension import.
8. **`Suspend function 'x' should be called only from a coroutine or another suspend function`** - mark the caller
   `suspend` or launch in a scope.
9. **Platform types from Java** - unexpected NPE when Java returns null into a non-null Kotlin type.
10. **`lateinit property x has not been initialized`** - initialize before use or use nullable/`lazy`.
11. **Catching `Exception` in coroutines swallows `CancellationException`** - rethrow it or catch specific types.
12. **`GlobalScope.launch`** - leaks and no cancellation; use a lifecycle scope.
13. **Blocking calls on `Dispatchers.Main`** - ANRs on Android; `withContext(Dispatchers.IO)`.
14. **`runBlocking` inside a coroutine or on the main thread** - deadlocks/freezes.
15. **Flow collected in `onCreate` without lifecycle awareness** - keeps collecting in background; use
    `repeatOnLifecycle(Lifecycle.State.STARTED)` or `collectAsStateWithLifecycle()`.
16. **`data class` with mutable `var` properties used as map keys** - hash changes.
17. **`==` vs `===`** - `==` calls `equals`; `===` is identity.
18. **Integer division** - `7 / 2 == 3`; `-7 / 2 == -3`; use `floorDiv`/`mod` for floored semantics.
19. **`listOf` is read-only but not immutable** if the underlying list is mutable elsewhere.
20. **Extension functions are resolved statically** - no polymorphism on the receiver's runtime type.
21. **Companion object vs top-level functions** - Java callers need `@JvmStatic`/`@JvmOverloads`/`@JvmField`.
22. **Default arguments and Java callers** - need `@JvmOverloads`.
23. **`Cannot access 'x': it is private in 'Y'`** - visibility (`internal` is module-wide).
24. **Kotlin/Java version mismatch** - "Module was compiled with an incompatible version of Kotlin. The binary
    version of its metadata is X, expected version is Y" - align the Kotlin Gradle plugin and dependencies.
25. **JVM target mismatch** - "Inconsistent JVM-target compatibility detected for tasks 'compileJava' and
    'compileKotlin'" - set `jvmToolchain(N)`.
26. **kapt slowness / deprecation** - migrate annotation processors to KSP.
27. **Context receivers removed** - old `context(Logger)` syntax replaced by named context parameters
    `context(logger: Logger)` (stable in 2.4).
28. **Experimental API without opt-in** - `This declaration needs opt-in` - add `@OptIn(...)` deliberately.
29. **Sequence vs List confusion** - sequences are lazy; side effects run only on terminal operations.
30. **Shared mutable state across coroutines** on `Dispatchers.Default` - races; use `Mutex` or confinement.
31. **Unused return values** (2.3+ checker) - e.g. calling `list.plus(x)` without using the result; use `+=` on a
    `MutableList` or assign.

## 10. Performance

- Same JVM tooling as Java (JFR, async-profiler, JMH via kotlinx-benchmark).
- `inline` higher-order functions avoid lambda allocations; `value class` avoids wrapper allocation; prefer
  primitive arrays (`IntArray`) over `Array<Int>`/`List<Int>` in hot loops.
- Sequences for long chained operations on large collections; lists for small ones.
- Coroutines are cheap, but `Dispatchers.IO` threads are not unlimited (64 by default, elastic).
- Android: Baseline Profiles, R8 shrinking, avoid allocations in `onDraw`/game loops.

## 11. Security

- JVM security applies (see java.md): parameterized SQL (`PreparedStatement`, Exposed/jOOQ/Room bind parameters),
  no Java deserialization of untrusted data, keep dependencies updated.
- Android: do not store secrets in the APK; use the Android Keystore; validate `Intent` extras; `exported=false` for
  internal components; network security config (no cleartext); WebView `setJavaScriptEnabled` only when needed.
- kotlinx.serialization is data-only and safe from gadget chains; still validate inputs and sizes.
- Ktor: install authentication, CORS and rate limiting plugins; validate request bodies.
- Gradle supply chain: dependency verification (`verification-metadata.xml`), version catalogs, avoid dynamic versions
  (`+`).

## 12. Game-development usage

- **libGDX** works fully from Kotlin (KTX extensions add Kotlin idioms); **KorGE** is a Kotlin Multiplatform game engine
  (desktop, Android, iOS, web) with coroutine-based game loops; **LWJGL** bindings; Android games using
  `SurfaceView`/OpenGL ES or Compose for simple 2D.
- Minecraft modding: Fabric Language Kotlin and Kotlin for Forge/NeoForge adapters.
- Server side: Ktor for game backends and matchmaking; coroutines handle many WebSocket connections.
- Embedding Lua: via Java libraries (LuaJ, luajava); no mainstream Luau binding (unverified).
- Roblox to Kotlin mapping: `task.spawn` -> `launch`, `task.wait` -> `delay`, `RemoteEvent` -> WebSocket messages,
  `ModuleScript` -> `object` or class, `BindableEvent` -> `SharedFlow`.

## 13. Cheat sheet: Kotlin vs Luau

| Concept | Luau | Kotlin |
|---|---|---|
| Variable | `local x = 1` | `var x = 1` / `val x = 1` (read-only) |
| Constant | `local MAX = 10` | `const val MAX = 10` (top level / object) |
| Nil | `nil` | `null` only for `T?` types |
| Number | `number` | `Int`, `Long`, `Double`, `Float` |
| Integer division | `7 // 2` floored | `7 / 2 == 3` truncated; `floorDiv` |
| Indexing | 1-based | 0-based; `list[0]`, `getOrNull(i)` |
| Array | `{1, 2, 3}` | `listOf(1, 2, 3)`, `mutableListOf(...)`, `intArrayOf(...)` |
| Map | `{a = 1}` | `mapOf("a" to 1)`, `mutableMapOf()` |
| Length | `#t` | `list.size`, `s.length` |
| String concat | `a .. b` | `a + b`, `"$a$b"` templates |
| Format | `string.format("%.2f", x)` | `"%.2f".format(x)` |
| Function | `local function f(a)` | `fun f(a: Int): Int = a * 2` |
| Closure | upvalues | lambdas `{ x -> x + 1 }`, capture variables |
| Multiple returns | `return a, b` | `Pair`/`data class` + destructuring `val (a, b) = f()` |
| Module | `require` | `import pkg.name`; files/packages |
| Class | metatable | `class`, `data class`, `object` |
| Method | `obj:M()` | `obj.m()` |
| Inheritance | metatable chain | `open class` + `: Base()`; interfaces |
| Error raise | `error("x")` | `throw IllegalStateException("x")`, `error("x")` |
| Error catch | `pcall` | `try/catch` expression, `runCatching` |
| Coroutine | `coroutine.wrap` | `suspend fun`, `launch`, `async`, `Flow` |
| Wait | `task.wait(1)` | `delay(1000)` (in a coroutine) |
| Types | gradual | static, inferred, null-safe |
| Generics | `<T>` | `fun <T> f(x: T)`, `reified` in inline functions |
| Iteration | `for i, v in ipairs(t)` | `for ((i, v) in list.withIndex())` |
| Equality | `==` | `==` structural (`equals`), `===` identity |
| Memory | GC | GC (JVM/Native) |
| Truthiness | `nil`/`false` falsy | only `Boolean` |

## 14. Sources

Releases:
- https://kotlinlang.org/docs/releases.html - release cadence, 2.4.21 current, 2.5.0 planned
- https://kotlinlang.org/docs/whatsnew24.html - 2.4.0 (2026-07-14) features
- https://kotlinlang.org/docs/whatsnew23.html - 2.3.0 (2025-12-16) features
- https://kotlinlang.org/docs/whatsnew22.html - 2.2.0 features, context parameters preview
- https://kotlinlang.org/docs/whatsnew20.html - K2 compiler
- https://blog.jetbrains.com/kotlin/2025/06/kotlin-2-2-0-released/ - 2.2 announcement

Language and libraries:
- https://kotlinlang.org/docs/null-safety.html - null safety
- https://kotlinlang.org/docs/java-interop.html#null-safety-and-platform-types - platform types
- https://kotlinlang.org/docs/context-parameters.html - context parameters
- https://kotlinlang.org/docs/coroutines-guide.html - coroutines guide
- https://kotlinlang.org/docs/exception-handling.html - coroutine exceptions
- https://kotlinlang.org/docs/cancellation-and-timeouts.html - cancellation
- https://kotlinlang.org/docs/flow.html - Flow
- https://kotlinlang.org/docs/scope-functions.html - scope functions
- https://developer.android.com/kotlin/coroutines/coroutines-best-practices - Android coroutine practices

Tooling, testing, security:
- https://kotlinlang.org/docs/gradle.html - Gradle plugin
- https://kotlinlang.org/docs/multiplatform.html - Kotlin Multiplatform
- https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/ - coroutine testing
- https://mockk.io/ - MockK
- https://developer.android.com/privacy-and-security/security-tips - Android security
- https://docs.gradle.org/current/userguide/dependency_verification.html - dependency verification

Game development:
- https://korge.org/ - KorGE
- https://libktx.github.io/ - KTX for libGDX
