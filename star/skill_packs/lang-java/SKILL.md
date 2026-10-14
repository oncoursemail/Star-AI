---
name: lang-java
description: Java (JDK 27 current, JDK 25 LTS) modern syntax, virtual threads, exceptions, collections pitfalls, javac errors, Maven/Gradle and security. Use for Java code, javac errors, NullPointerException or ConcurrentModificationException, JDK upgrades, or Minecraft/libGDX modding.
---
# Java (JDK 25 LTS, JDK 27 current)
- Ask which JDK the project targets (17, 21, 25 are the common LTS lines; 27 GA 2026-09-15). Final features: records, sealed types, pattern matching `switch` and record patterns (21), virtual threads (21), unnamed `_` (22), scoped values, module imports, compact source files with `void main()`, statements before `super(...)` (25). Structured concurrency and lazy constants are still preview in 27: they need `--enable-preview`.
- Virtual threads: `Executors.newVirtualThreadPerTaskExecutor()`; do not pool them; limit concurrency with a `Semaphore`; `synchronized` no longer pins carrier threads since JDK 24. Prefer scoped values to `ThreadLocal`.
- Exceptions: checked ones must be caught or declared ("unreported exception ...; must be caught or declared to be thrown"); always keep the cause (`new RuntimeException("msg", e)`); never empty `catch`. Close resources with try-with-resources.
- Equality: `==` on objects is identity; use `.equals` for strings and boxed numbers (`Integer` cache makes `128 == 128` false). Override `equals` and `hashCode` together (records do it).
- Collections: removing inside for-each throws `ConcurrentModificationException` (use `removeIf` or an Iterator); `List.of(...)` is immutable (`UnsupportedOperationException`); mutable `HashMap` keys break lookups.
- Nulls: unboxing `null` throws NPE; return `Optional` for maybe-absent values and use `orElseThrow()`; do not call `Optional.get()` blindly.
- Lambdas capture only effectively final locals ("local variables referenced from a lambda expression must be final or effectively final").
- Concurrency: `ConcurrentHashMap`, `AtomicLong`, `ReentrantLock`; `volatile` is visibility only (`count++` is still racy); `java.time` instead of `SimpleDateFormat`.
- `UnsupportedClassVersionError` (class file version 69.0 = Java 25): run on a newer JDK or compile with `--release N`.
- Security: `PreparedStatement` with `?` placeholders, no `ObjectInputStream` on untrusted data (or use serialization filters), `ProcessBuilder(List.of(...))` without a shell, disable XML external entities, keep logging libraries patched (Log4Shell).
- Build and test: Maven or Gradle (Kotlin DSL, toolchains), JUnit 5/6 with AssertJ and Mockito, JMH for benchmarks, JFR/async-profiler for profiling.
