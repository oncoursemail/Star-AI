---
name: lang-kotlin
description: Kotlin 2.4 (K2 compiler) null safety, coroutines and Flow, structured concurrency, Gradle Kotlin DSL and common compiler errors. Use for Kotlin code, Android/Compose, kotlinx.coroutines, KMP, or errors about nullable receivers, suspend calls or smart casts.
---
# Kotlin 2.4 (K2)
- Current: 2.4.0 (2026-07-14), bug-fix 2.4.21; 2.5.0 planned for December 2026. Context parameters (`context(logger: Logger) fun f()`) and explicit backing fields are stable in 2.4; collection literals and explicit context arguments are experimental. Old context receivers syntax is gone.
- Null safety: "Only safe (?.) or non-null asserted (!!.) calls are allowed on a nullable receiver" - use `?.`, `?:`, `if (x != null)`, `let`; avoid `!!`. Java platform types (`String!`) can still be null.
- "Smart cast to 'X' is impossible, because 'y' is a mutable property" - copy to a local `val` first.
- "Suspend function 'x' should be called only from a coroutine or another suspend function" - make the caller `suspend` or launch it in a scope.
- Structured concurrency: launch in `viewModelScope`/`lifecycleScope` or an injected scope, never `GlobalScope`; `coroutineScope { async {}; async {} }` for parallel work; `withContext(Dispatchers.IO)` for blocking calls; never `runBlocking` on the main thread or inside coroutines.
- Cancellation is cooperative: do not swallow `CancellationException` (catching `Exception` or `runCatching` inside a coroutine does); call `ensureActive()` in long loops.
- Flow is cold; `StateFlow`/`SharedFlow` are hot; collect UI flows with `repeatOnLifecycle` or `collectAsStateWithLifecycle()`.
- Shared state across coroutines needs `Mutex.withLock`, atomics or confinement.
- `when` over sealed types must be exhaustive; `data class` keys should be immutable; `==` is `equals`, `===` is identity; `7 / 2 == 3` and `-7 / 2 == -3` (use `floorDiv`/`mod` for floored math).
- Gradle: Kotlin DSL, `kotlin { jvmToolchain(21) }` to fix "Inconsistent JVM-target compatibility"; align the Kotlin plugin with libraries ("incompatible version of Kotlin" metadata errors); KSP instead of kapt.
- Testing: `kotlinx-coroutines-test` `runTest`, MockK (`coEvery` for suspend functions), Turbine for Flow, Kotest or JUnit.
- Security: same as JVM (bind SQL parameters, no Java deserialization of untrusted data); on Android keep secrets in the Keystore and set `exported=false` on internal components.
