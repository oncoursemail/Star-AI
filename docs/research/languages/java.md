# Java (JDK 27 current, JDK 25 LTS) - STAR language research

> Status: checked on 2026-10-13 against openjdk.org/projects/jdk: **JDK 27 GA 2026-09-15**, JDK 26 GA 2026-03-17,
> **JDK 25 GA 2025-09-16 (current LTS)**, JDK 21 (previous LTS, 2023-09-19); JDK 28 in development. LTS releases
> come every two years (21, 25; next expected 29 in 2027). Most production code targets **17, 21 or 25**. Use Java for
> large backend systems, Android (via Kotlin/Java), big-data tooling, enterprise apps and Minecraft Java Edition
> modding.

## 0. Current version and what changed 2024-2026

Final (non-preview) features by release (JEP numbers from the OpenJDK project pages):
- **JDK 21 (LTS)**: virtual threads (JEP 444), record patterns (440), pattern matching for `switch` (441), sequenced
  collections (431: `getFirst()`, `getLast()`, `reversed()`), generational ZGC (439), key encapsulation API.
- **JDK 22**: unnamed variables and patterns `_` (456), Foreign Function & Memory API final (454), launch multi-file
  source programs (458), region pinning for G1.
- **JDK 23**: Markdown documentation comments `///` (467), ZGC generational mode by default (474).
- **JDK 24**: **synchronize virtual threads without pinning** (491), stream gatherers final (485), class-file API
  final (484), Security Manager permanently disabled (486), quantum-resistant ML-KEM (496) and ML-DSA (497),
  compact object headers experimental (450), AOT class loading and linking (483).
- **JDK 25 (LTS)**: **scoped values** final (506), **module import declarations** `import module java.base;` (511),
  **compact source files and instance main methods** (512: `void main() { IO.println("hi"); }`), **flexible constructor
  bodies** (513: statements before `super(...)`), compact object headers as a product feature (519), generational
  Shenandoah (521), AOT command-line ergonomics and method profiling (514, 515), key derivation function API (510),
  JFR CPU-time profiling (509), 32-bit x86 port removed (503). Previews: structured concurrency (505, fifth), stable
  values (502), primitive types in patterns (507), Vector API (508, incubator).
- **JDK 26**: "Prepare to make final mean final" (500: warnings when deep reflection mutates `final` fields), Applet
  API removed (504), AOT object caching with any GC (516), **HTTP/3 for `HttpClient`** (517), G1 throughput
  improvement (522); previews: PEM encodings (524), structured concurrency (525, sixth), lazy constants (526, renamed
  from stable values), primitive types in patterns (530); Vector API (529, incubator).
- **JDK 27**: **G1 the default GC in all environments** (523), post-quantum hybrid key exchange for TLS 1.3 (527),
  **compact object headers by default** (534), JFR in-process data redaction (536); previews: lazy constants (531,
  third), primitive types in patterns (532), structured concurrency (533, seventh), PEM encodings (538, third); Vector
  API (537, twelfth incubator).

Preview features need `--enable-preview --release N` at compile and run time; do not present them as standard Java.

## 1. Mental model

- Statically typed, class-based OOP on the JVM: source compiles to bytecode (`.class`), run by HotSpot with a JIT
  (C1/C2), optional AOT caches (Leyden work, JDK 24-26) and GraalVM Native Image for native binaries.
- Everything except primitives is an object reference; references are passed by value.
- Garbage collected; choose a collector (G1 default, ZGC for low latency, Shenandoah, Parallel for throughput).
- Strong backward compatibility; huge ecosystem (Maven Central).
- Checked exceptions are part of method signatures.
- Modern Java is much more concise than 2014 Java: `var`, records, sealed types, pattern matching, text blocks,
  switch expressions, virtual threads.

## 2. Type system

- Primitives: `byte`, `short`, `int` (32-bit), `long`, `float`, `double`, `char` (UTF-16 unit), `boolean`; wrappers
  (`Integer`...) with autoboxing (`null` unboxing throws `NullPointerException`).
- Integer overflow wraps silently; `Math.addExact` throws on overflow.
- Reference types: classes, interfaces (default/static/private methods), enums (full classes), records (immutable
  data carriers with generated `equals/hashCode/toString`), arrays (covariant, runtime-checked), annotations.
- **Sealed** classes/interfaces (`sealed interface Shape permits Circle, Square`) + records + pattern matching give
  algebraic data types with exhaustive `switch`:
  ```java
  sealed interface Shape permits Circle, Rect {}
  record Circle(double r) implements Shape {}
  record Rect(double w, double h) implements Shape {}
  static double area(Shape s) {
      return switch (s) {
          case Circle c -> Math.PI * c.r() * c.r();
          case Rect(double w, double h) -> w * h;   // record pattern
      };                                             // exhaustive: no default needed
  }
  ```
- Generics with **type erasure**: no `new T()`, no `T[]`, no primitive type arguments (`List<int>` invalid until
  Valhalla); wildcards `? extends T` (producer) and `? super T` (consumer) - "PECS".
- `var` for local variable inference (Java 10); diamond `new ArrayList<>()`.
- No operator overloading; `==` on references compares identity.
- Nullability is not in the type system (JSpecify annotations `@Nullable`/`@NonNull` are the emerging standard;
  `Optional<T>` for return values).

## 3. Memory model and ownership

- Heap objects managed by the GC; stack holds primitives and references. Escape analysis can scalar-replace
  short-lived objects.
- GC choice: G1 (default; balanced), ZGC (`-XX:+UseZGC`, generational by default since 23, sub-millisecond pauses),
  Shenandoah (generational in 25), Parallel (batch), Serial (tiny heaps). Size with `-Xmx`, or
  `-XX:MaxRAMPercentage` in containers.
- Resources are not memory: close files/sockets with **try-with-resources** (`AutoCloseable`).
- Leaks: static collections, listeners never removed, `ThreadLocal`s on pooled threads, caches without eviction
  (use Caffeine), classloader leaks in app servers.
- **Java Memory Model**: happens-before via `synchronized`, `volatile`, `java.util.concurrent` classes,
  `Thread.start/join`, final-field semantics. Without them, other threads may see stale or reordered values.
- Off-heap: FFM API `Arena`/`MemorySegment` (JDK 22) replaces `sun.misc.Unsafe` and `ByteBuffer` hacks.
- Compact object headers (default in JDK 27) shrink object headers to 8 bytes on 64-bit.

## 4. Concurrency

- **Virtual threads** (21+): `Thread.ofVirtual().start(r)`, `Executors.newVirtualThreadPerTaskExecutor()`; write
  blocking code that scales to millions of threads. Since **JDK 24**, `synchronized` no longer pins the carrier
  thread (JEP 491); native calls and some class initialization can still pin. Do not pool virtual threads; limit
  concurrency with a `Semaphore`.
- **Structured concurrency** (`StructuredTaskScope`) is still **preview** in JDK 27 (seventh preview); the API changed
  between previews (`StructuredTaskScope.open(...)` with joiners since JDK 25). Check before using.
- **Scoped values** (final in 25): immutable, inheritable per-thread context, preferred over `ThreadLocal` with virtual
  threads.
- `ExecutorService` (try-with-resources closes and waits since 19), `CompletableFuture` composition,
  `ConcurrentHashMap`, `AtomicLong`, `LongAdder`, `ReentrantLock`, `ReadWriteLock`, `CountDownLatch`, `Phaser`.
- `volatile` gives visibility, not atomicity (`count++` is still racy).
- Parallel streams use the common ForkJoinPool; avoid for blocking I/O.

## 5. Error handling

- **Checked exceptions** (`IOException`, `SQLException`) must be caught or declared (`throws`); unchecked
  (`RuntimeException`: `NullPointerException`, `IllegalArgumentException`, `IllegalStateException`) need not.
  `Error`s (`OutOfMemoryError`) are not meant to be caught.
- **try-with-resources** closes in reverse order and records suppressed exceptions:
  ```java
  try (var in = Files.newBufferedReader(path); var out = Files.newBufferedWriter(target)) {
      in.transferTo(out);
  } catch (IOException e) {
      throw new UncheckedIOException("copy failed: " + path, e); // keep the cause
  }
  ```
- Multi-catch `catch (IOException | SQLException e)`; always chain causes; do not swallow exceptions (`catch (Exception
  e) {}`).
- Checked exceptions do not work with lambdas/streams: wrap into `UncheckedIOException` or use a helper.
- `Optional<T>` for "maybe absent" return values (not for fields or parameters); `orElseThrow()`, `map`, `orElse`.
- Helpful NullPointerException messages (JDK 14+) name the null variable.

## 6. Toolchain, build and package management

- JDK distributions: Oracle JDK, Eclipse Temurin, Amazon Corretto, Azul Zulu, Microsoft Build of OpenJDK, GraalVM.
  Manage with SDKMAN!, jEnv or toolchains in the build tool.
- `javac --release 21 -d out src/...`, `java -cp out app.Main`, single-file `java Main.java`, multi-file source
  launch (22+), `jshell` REPL, `jar`, `jlink` (custom runtime images), `jpackage` (installers).
- **Gradle** (Kotlin DSL `build.gradle.kts`; Gradle 9.x current major) and **Maven** (`pom.xml`; 3.9.x widely used,
  Maven 4 newer) - both pull from Maven Central. Use dependency lock files / Maven Enforcer; Gradle version catalogs
  (`libs.versions.toml`); Java toolchains (`java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }`).
- Static analysis: `javac -Xlint:all`, Error Prone, SpotBugs, PMD, Checkstyle, NullAway; formatters
  google-java-format, Spotless.
- JPMS modules (`module-info.java`) are optional for apps; libraries increasingly ship them.
- Observability: JFR (`-XX:StartFlightRecording`), JDK Mission Control, `jcmd`, `jstack`, async-profiler.

## 7. Testing

- **JUnit 5 (Jupiter)** is standard; **JUnit 6** (released 2025, requires Java 17) continues the Jupiter API.
  `@Test`, `@ParameterizedTest` + `@ValueSource`/`@CsvSource`, `@BeforeEach`, `@Nested`, `assertThrows`,
  `assertAll`.
- Assertions: AssertJ (`assertThat(x).isEqualTo(y)`), Hamcrest. Mocking: Mockito. Containers: Testcontainers.
  Property testing: jqwik. Mutation testing: PIT. Benchmarks: **JMH** (never hand-roll microbenchmarks: JIT warmup and
  dead-code elimination fool you).
- `mvn test` / `gradle test`; coverage with JaCoCo.

## 8. Idiomatic patterns

- Records for DTOs and value objects; sealed interfaces + records + pattern matching for domain states.
- Immutability: `List.of`, `Map.of`, `Collections.unmodifiableList`, `final` fields; builder pattern for many
  optional fields.
- Composition over inheritance; program to interfaces (`List` not `ArrayList`).
- Streams for transformations (`stream().filter().map().toList()` (16+)); simple loops when clearer.
- Dependency injection (Spring, Micronaut, Quarkus, Dagger/Guice).
- `equals` and `hashCode` together (records do it for you); `Comparator.comparing(Person::age).thenComparing(...)`.
- Text blocks `"""` for multi-line strings; `String.formatted(...)`.
- Virtual threads + plain blocking I/O for request-per-thread servers.
- Instance main and compact source files (25) for scripts and teaching.

## 9. Top 30 pitfalls and compiler-error fixes

1. **`error: cannot find symbol`** - typo, missing import, missing dependency, wrong scope.
2. **`error: incompatible types: possible lossy conversion from double to int`** - explicit cast `(int)`.
3. **`error: unreported exception IOException; must be caught or declared to be thrown`** - catch it or add `throws`.
4. **`error: variable x might not have been initialized`** - assign on all paths.
5. **`error: missing return statement`**.
6. **`error: non-static method m() cannot be referenced from a static context`** - create an instance (or use an
   instance main in 25+).
7. **`error: local variables referenced from a lambda expression must be final or effectively final`** - copy to a
   final local, or use an `AtomicInteger`/array holder, or restructure with streams.
8. **`error: class X is public, should be declared in a file named X.java`**.
9. **`error: the switch expression does not cover all possible input values`** - add cases or `default`, or seal the
   hierarchy.
10. **`NullPointerException`** - unboxing `null` (`int x = map.get(k);`), uninitialized fields; use `Optional`,
    `Objects.requireNonNull`, JSpecify + NullAway.
11. **`==` on strings/boxed numbers** compares identity: `Integer` cache makes `127 == 127` true and `128 == 128`
    false. Use `.equals`.
12. **Overriding `equals` without `hashCode`** breaks `HashMap`/`HashSet`.
13. **Mutable keys in `HashMap`** - mutating a key after insertion loses the entry.
14. **`ConcurrentModificationException`** - removing from a list inside for-each. Use `removeIf` or an `Iterator`.
15. **`UnsupportedOperationException`** - mutating `List.of(...)` or `Arrays.asList(...).add`.
16. **Integer overflow** silent; `Math.multiplyExact`.
17. **Floating point money** - use `BigDecimal` (constructed from `String`, not `double`).
18. **Resource leaks** - forgetting to close streams; use try-with-resources (`Files.lines` too).
19. **Swallowed exceptions / lost cause** - always pass the cause.
20. **Thread-safety of `SimpleDateFormat`, `HashMap`** - use `java.time` (`DateTimeFormatter` is immutable),
    `ConcurrentHashMap`.
21. **Double-checked locking without `volatile`** - broken; use a holder class or `volatile`, or lazy constants
    (preview).
22. **Virtual-thread pinning** on JDK 21-23 with `synchronized` blocking I/O - upgrade to 24+ or use `ReentrantLock`.
23. **Pooling virtual threads** or using `ThreadLocal` caches with millions of them - use scoped values and
    semaphores.
24. **Streams reused** - `IllegalStateException: stream has already been operated upon or closed`.
25. **Side effects in parallel streams** - races; use collectors.
26. **`Optional.get()` without check** - `NoSuchElementException`; use `orElseThrow()` with a message.
27. **Generic array creation / erasure errors** - `error: generic array creation`; use `List<T>` or pass `Class<T>`.
28. **`ClassCastException` from raw types** - never use raw `List`; heed unchecked warnings.
29. **`java.lang.UnsupportedClassVersionError ... class file version 69.0`** - compiled for a newer JDK than the
    runtime (class file 69 = Java 25). Fix: run on the newer JDK or compile with `--release` for the target.
30. **Module errors** `package x is not visible` / `IllegalAccessError` under JPMS - add `requires`/`opens`, or use
    the classpath.
31. **Preview feature used without flags** - `error: ... is a preview feature and is disabled by default`; add
    `--enable-preview --release N` or avoid it.

## 10. Performance

- Warm up before measuring (JIT); use JMH; profile with async-profiler, JFR, VisualVM.
- Allocation is cheap but not free; reduce garbage in hot loops; prefer primitive arrays and specialized collections
  (fastutil, Eclipse Collections) to boxed `List<Integer>`.
- `StringBuilder` in loops; `String.join`; avoid regex compilation in loops (precompile `Pattern`).
- GC tuning: choose ZGC for latency; set heap from container limits; compact object headers (default in 27) save
  memory.
- Startup: AppCDS / AOT cache (JDK 24-26 JEPs 483/514/515/516), GraalVM Native Image, CRaC.
- Vector API is still incubating; use only behind `--add-modules jdk.incubator.vector`.

## 11. Security

- Memory-safe JVM, but: injection, deserialization and dependency vulnerabilities dominate.
- **SQL injection**: `PreparedStatement` with `?` placeholders (`ps.setString(1, name)`), JPA named parameters; never
  string-concatenate SQL.
- **Deserialization**: never `ObjectInputStream.readObject()` on untrusted data; if unavoidable, use serialization
  filters (`ObjectInputFilter`, JEP 290/415). Prefer JSON with explicit types (Jackson without default typing).
- **Log injection / JNDI**: Log4Shell (CVE-2021-44228) came from message lookups in Log4j 2 < 2.15/2.17; keep logging
  libraries updated and never evaluate user input in templates.
- **Command injection**: `ProcessBuilder(List.of("git", "log", arg))`, no shell.
- **XXE**: disable external entities in XML parsers (`XMLConstants.FEATURE_SECURE_PROCESSING`, disallow DOCTYPE).
- **Path traversal**: `path.normalize()` and `startsWith(base)` checks.
- Security Manager is gone (JDK 24): sandbox untrusted code with separate processes/containers, not in-JVM.
- Crypto: `SecureRandom`, AES-GCM, PBKDF2/Argon2 via libraries, post-quantum ML-KEM/ML-DSA (24), hybrid TLS key
  exchange (27).
- Supply chain: dependency scanning (OWASP Dependency-Check, GitHub Dependabot), verify checksums/signatures, Gradle
  dependency verification.

## 12. Game-development usage

- **Minecraft: Java Edition** modding is the biggest Java game ecosystem: **Fabric** (lightweight, mixins) and
  **NeoForge** (fork of Forge, the main successor since 2023); Minecraft 1.20.5+ requires Java 21 (verify current
  requirement for the latest Minecraft version). Paper/Spigot for server plugins.
- **libGDX** (cross-platform 2D/3D, desktop via LWJGL3, Android, iOS via RoboVM, web via TeaVM/GWT), **jMonkeyEngine**
  (3D), **LWJGL** (OpenGL/Vulkan/GLFW/OpenAL bindings), **FXGL** (JavaFX-based).
- Android games mostly use Kotlin/Java for glue and C++ or engines (Unity, Godot) for the core.
- Embedding Lua: **LuaJ** (Lua 5.2 in Java; old), **party.iroiro.luajava** (binds native Lua/LuaJIT). No mainstream
  Luau binding for Java (unverified).
- GC pauses matter for frame times: ZGC or careful allocation (object pools for bullets/particles).

## 13. Cheat sheet: Java vs Luau

| Concept | Luau | Java |
|---|---|---|
| Variable | `local x = 1` | `var x = 1;` / `int x = 1;` |
| Constant | `local MAX = 10` | `static final int MAX = 10;` |
| Nil | `nil` | `null` (references only); `Optional<T>` |
| Number | `number` | `int`, `long`, `double`, `BigDecimal` |
| Integer division | `7 // 2 == 3` floored | `7 / 2 == 3` truncated; `Math.floorDiv(-7, 2) == -4` |
| Modulo | `-7 % 2 == 1` | `-7 % 2 == -1`; `Math.floorMod` |
| Indexing | 1-based | 0-based, bounds-checked (`ArrayIndexOutOfBoundsException`) |
| Array | `{1, 2, 3}` | `int[] a = {1, 2, 3};` / `List<Integer> l = List.of(1, 2, 3);` |
| Map | `{a = 1}` | `Map<String, Integer> m = new HashMap<>(); m.put("a", 1);` |
| Length | `#t` | `a.length`, `list.size()`, `s.length()` |
| String concat | `a .. b` | `a + b`, `StringBuilder` |
| Format | `string.format` | `String.format("%.2f", x)`, `"%d".formatted(n)` |
| Function | `local function f(a)` | `static int f(int a) { return a; }` |
| Closure | upvalues | lambdas capture effectively final locals |
| Multiple returns | `return a, b` | return a `record Pair(int a, int b)` |
| Module | `require` | `import pkg.Class;` / `import module java.base;` (25) |
| Class | metatable | `class` / `record` / `enum` |
| Inheritance | metatable chain | `extends` (single) + `implements` interfaces |
| Error raise | `error("x")` | `throw new IllegalStateException("x");` |
| Error catch | `pcall` | `try/catch/finally` |
| Coroutine | `coroutine`, `task.spawn` | virtual threads, `CompletableFuture` |
| Wait | `task.wait(1)` | `Thread.sleep(1000)` (cheap on virtual threads) |
| Types | gradual | static, generics erased |
| Generics | `<T>` | `<T extends Comparable<T>>` |
| Iteration | `for _, v in ipairs(t)` | `for (var v : list)` |
| Equality | `==` | `.equals()` for values, `==` identity |
| Memory | GC | GC (G1/ZGC) |
| Truthiness | `nil`/`false` falsy | only `boolean` |

## 14. Sources

Releases and JEPs:
- https://openjdk.org/projects/jdk/ - release list with GA dates (21, 25, 26, 27)
- https://openjdk.org/projects/jdk/27/ - JDK 27 JEPs
- https://openjdk.org/projects/jdk/26/ - JDK 26 JEPs
- https://openjdk.org/projects/jdk/25/ - JDK 25 JEPs
- https://openjdk.org/projects/jdk/24/ - JDK 24 JEPs
- https://openjdk.org/jeps/491 - virtual threads without pinning
- https://openjdk.org/jeps/506 - scoped values
- https://openjdk.org/jeps/512 - compact source files and instance main
- https://openjdk.org/jeps/513 - flexible constructor bodies
- https://openjdk.org/jeps/444 - virtual threads
- https://openjdk.org/jeps/441 - pattern matching for switch
- https://openjdk.org/jeps/523 - G1 default everywhere
- https://www.oracle.com/java/technologies/java-se-support-roadmap.html - LTS roadmap

Language, runtime, testing:
- https://docs.oracle.com/javase/specs/ - JLS and JVMS
- https://docs.oracle.com/en/java/javase/25/ - JDK 25 documentation
- https://docs.oracle.com/javase/specs/jls/se25/html/jls-17.html#jls-17.4 - Java memory model
- https://docs.oracle.com/javase/tutorial/essential/exceptions/tryResourceClose.html - try-with-resources
- https://junit.org/ - JUnit 5/6
- https://github.com/openjdk/jmh - JMH
- https://docs.gradle.org/current/userguide/toolchains.html - Gradle toolchains
- https://maven.apache.org/ - Maven

Security:
- https://cheatsheetseries.owasp.org/cheatsheets/Java_Security_Cheat_Sheet.html - OWASP Java
- https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html - deserialization
- https://docs.oracle.com/en/java/javase/25/core/serialization-filtering1.html - serialization filters
- https://logging.apache.org/log4j/2.x/security.html - Log4Shell advisories

Game development:
- https://libgdx.com/ - libGDX
- https://jmonkeyengine.org/ - jMonkeyEngine
- https://www.lwjgl.org/ - LWJGL
- https://neoforged.net/ - NeoForge
- https://fabricmc.net/ - Fabric
