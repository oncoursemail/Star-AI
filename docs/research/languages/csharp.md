# C# 14 / .NET 10 LTS (C# 15 / .NET 11 in RC) - STAR language research

> Status: checked on 2026-10-13 against dotnet.microsoft.com/download/dotnet and Microsoft Learn. **.NET 10 is the
> current LTS** (latest patch 10.0.13 on 2026-10-13, supported until 2028-11-14) with **C# 14**. **.NET 9** (STS) is
> in maintenance. **.NET 11 is at RC2** (2026-10-13, "go-live") with **C# 15 preview**; GA is expected in November
> 2026 (Microsoft's usual cadence; verify). Use C# for Windows/desktop apps, web APIs (ASP.NET Core), cloud services,
> tools, and games (**Unity**, **Godot 4 .NET**, MonoGame/FNA, Stride). C# is the closest mainstream language to what
> Roblox developers will meet when moving to Unity.

## 0. Current version and what changed 2024-2026

- **C# 13 / .NET 9 (Nov 2024)**: `params` collections (`params ReadOnlySpan<T>`), new `System.Threading.Lock` type
  (`lock` statement uses it), `\e` escape, implicit index `^` in object initializers, `ref`/`unsafe` in iterators and
  async methods, `allows ref struct` anti-constraint, partial properties, `OverloadResolutionPriority`.
- **C# 14 / .NET 10 (Nov 2025, LTS)** (Microsoft Learn "What's new in C# 14"):
  - **Extension members**: `extension(Receiver r) { ... }` blocks inside a static class declare extension
    **properties**, methods, static extension members and operators; compatible with classic `this` extension methods.
  - **`field` keyword**: access the compiler-generated backing field in property accessors
    (`public string Name { get; set => field = value ?? throw new ArgumentNullException(); }`). A member named
    `field` now needs `@field` or `this.field`.
  - **Null-conditional assignment**: `customer?.Order = GetOrder();` (right side only evaluated if not null).
  - First-class **implicit span conversions** between `T[]`, `Span<T>`, `ReadOnlySpan<T>`.
  - `nameof(List<>)` with unbound generics; modifiers on simple lambda parameters (`(out x) => ...`); partial
    constructors and events; user-defined compound assignment (`+=`) and `++`/`--` operators; `#:` directives for
    **file-based apps** (`dotnet run app.cs`, with `#:package Name@1.2.3`).
  - .NET 10: JIT devirtualization and stack allocation improvements, AVX10.2, Native AOT improvements, JSON options
    to disallow duplicate properties, Microsoft.Testing.Platform support in `dotnet test`, EF Core 10 named query
    filters.
- **C# 15 / .NET 11 (preview/RC)**: collection expression arguments (`List<string> l = [with(capacity: 10), ..xs];`),
  **union types** (`public union Pet(Cat, Dog, Bird);` with exhaustive `switch`), **`closed` classes** (closed
  hierarchies, exhaustive switches), extension indexers, labeled `break`/`continue`, and the first step of a new
  memory-safety model for `unsafe` (requires-unsafe members). Only use when the user targets `net11.0` with
  `<LangVersion>preview</LangVersion>` or after GA.
- Language version follows the target framework by default (`net10.0` -> C# 14). Unity uses its own compiler version
  (below), so do not assume C# 14 in Unity.

## 1. Mental model

- Managed, garbage-collected, statically typed, object-oriented with strong functional features (LINQ, lambdas,
  pattern matching, records).
- Code compiles to IL; the CoreCLR JIT (tiered compilation, PGO) or **Native AOT** compiles to machine code.
- **Value types** (`struct`, `enum`, primitives) are copied; **reference types** (`class`, `record`, arrays, strings,
  delegates) are references to heap objects. This difference drives most bugs and performance work.
- Deterministic cleanup for unmanaged resources via `IDisposable` + `using`, because the GC frees memory, not files or
  sockets.
- `async`/`await` is pervasive in I/O APIs (Task-based asynchronous pattern).
- Nullable reference types (NRT) make null-safety a compile-time warning system (enabled by default in new projects).

## 2. Type system

- Built-ins: `int` (32-bit), `long`, `float`, `double`, `decimal` (base-10, money), `bool`, `char` (UTF-16 code unit),
  `string` (immutable UTF-16), `object`, `nint`/`nuint`.
- Integer overflow wraps unless in a `checked` context (`checked(a + b)` or `<CheckForOverflowUnderflow>`).
- `class` (reference), `struct` (value), `record class` / `record struct` (value equality, `with` expressions),
  `readonly struct`, `ref struct` (stack-only, e.g. `Span<T>`), `interface` (with default and static abstract members),
  `enum`, delegates, tuples `(int X, int Y)`.
- Generics are reified (real at runtime, no type erasure) with constraints: `where T : class, new()`, `struct`,
  `notnull`, `unmanaged`, `INumber<T>` (generic math).
- Nullable value types `int?` (`Nullable<T>`); nullable reference types `string?` with flow analysis and annotations
  (`[NotNullWhen(true)]`).
- Pattern matching: type, property, positional, relational, logical (`and`/`or`/`not`), list patterns
  (`[1, .., var last]`), `switch` expressions.
- `var` for local inference; target-typed `new()`; collection expressions `[1, 2, 3]` (C# 12).
- Properties, indexers, events, operators, primary constructors (C# 12 classes/structs), `required` members,
  `init` accessors.

## 3. Memory model and ownership

- Generational GC (gen0/1/2, LOH for objects >= 85,000 bytes, POH); workstation vs server GC; `DOTNET_gcServer`,
  `GCSettings.LatencyMode`. Allocations are fast; collections cost pauses proportional to live data.
- Avoid allocations in hot paths: `Span<T>`, `stackalloc`, `ArrayPool<T>.Shared`, `StringBuilder`, struct
  enumerators, `ValueTask`, object pooling.
- `IDisposable`: call `Dispose` deterministically with `using var stream = File.OpenRead(path);` (C# 8 using
  declaration) or `using (...) { }`; `IAsyncDisposable` with `await using`. Finalizers only for direct unmanaged
  handles (prefer `SafeHandle`).
- Boxing: converting a value type to `object` or a non-generic interface allocates.
- Struct copies: large mutable structs copied by value lead to "my change did not stick" bugs; prefer `readonly
  struct` and `in`/`ref` parameters.
- Memory leaks still happen: event handlers keeping subscribers alive, static caches, timers.
- Unity: Mono/IL2CPP uses the Boehm-based incremental GC; allocation-free `Update()` code matters more there.

## 4. Concurrency

- `Task`/`Task<T>`, `async`/`await`, `Task.WhenAll`, `Task.WhenAny`, `Parallel.ForEachAsync`, `Channel<T>`
  (`System.Threading.Channels`), `IAsyncEnumerable<T>` with `await foreach`.
- `CancellationToken` passed through every async API; `cts.CancelAfter(TimeSpan)`.
- `lock` statement (C# 13 uses `System.Threading.Lock` when the field is that type), `SemaphoreSlim` for async
  locking (`await sem.WaitAsync()`), `Interlocked`, `ConcurrentDictionary`, `ImmutableArray`.
- Never `await` inside a `lock` (compile error CS1996); use `SemaphoreSlim`.
- Thread pool starvation from blocking on async code (`.Result`, `.Wait()`, `GetAwaiter().GetResult()`).
- UI and Unity main thread: UI objects must be touched from the main thread; Unity APIs are not thread-safe.
  Unity offers `Awaitable` (Unity 6) and coroutines (`IEnumerator` + `yield return`), plus the C# Job System + Burst.

## 5. Error handling

- Exceptions: `throw new InvalidOperationException("...")`; `try/catch/finally`; exception filters
  `catch (HttpRequestException e) when (e.StatusCode == HttpStatusCode.NotFound)`. Rethrow with `throw;` (keeps the
  stack), not `throw e;`.
- Guard clauses: `ArgumentNullException.ThrowIfNull(x)`, `ArgumentOutOfRangeException.ThrowIfNegative(n)`.
- `TryParse` pattern instead of exceptions for expected failures: `if (int.TryParse(s, out var n))`.
- Do not use exceptions for control flow in hot paths (expensive). Result types are a library pattern
  (`OneOf`, custom `Result<T>`); C# 15 unions will make this native.
- `async void` exceptions crash the process (cannot be awaited/caught); use `async Task` except for event handlers.
- Unobserved task exceptions: always await tasks.

```csharp
public sealed class SaveService(ILogger<SaveService> log)
{
    public async Task<PlayerData?> LoadAsync(string path, CancellationToken ct)
    {
        if (!File.Exists(path)) return null;
        try
        {
            await using var stream = File.OpenRead(path);
            return await JsonSerializer.DeserializeAsync<PlayerData>(stream, cancellationToken: ct);
        }
        catch (JsonException e)
        {
            log.LogWarning(e, "Corrupt save file {Path}", path);
            return null;
        }
    }
}
```

## 6. Toolchain, build and package management

- .NET SDK CLI: `dotnet new console|classlib|webapi|xunit`, `dotnet build`, `dotnet run`, `dotnet test`,
  `dotnet add package Serilog`, `dotnet publish -c Release -r linux-x64 --self-contained`, `dotnet format`,
  `dotnet tool install -g`, `dotnet run app.cs` (file-based apps, .NET 10).
- Project files: SDK-style `.csproj` (`<TargetFramework>net10.0</TargetFramework>`, `<Nullable>enable</Nullable>`,
  `<ImplicitUsings>enable</ImplicitUsings>`, `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`); solutions
  `.sln` or the new XML `.slnx`.
- NuGet packages; **Central Package Management** (`Directory.Packages.props` with
  `<ManagePackageVersionsCentrally>true`); `Directory.Build.props` for shared settings; lock files
  (`RestorePackagesWithLockFile`); `dotnet list package --vulnerable`.
- `global.json` pins the SDK version.
- Analyzers: built-in Roslyn analyzers (`<AnalysisLevel>latest-recommended</AnalysisLevel>`), StyleCop, SonarAnalyzer;
  `.editorconfig` severities.
- Native AOT: `<PublishAot>true</PublishAot>` (no runtime JIT, trimming required; reflection-heavy code and dynamic
  loading break; use source generators, e.g. `System.Text.Json` source generation).
- IDEs: Visual Studio 2026, JetBrains Rider, VS Code C# Dev Kit.

## 7. Testing

- Frameworks: **xUnit** (v3), **NUnit**, **MSTest**; `dotnet test` (VSTest or Microsoft.Testing.Platform in .NET 10).
- xUnit: `[Fact]`, `[Theory]` + `[InlineData]`; NUnit: `[Test]`, `[TestCase]`; MSTest: `[TestMethod]`.
- Assertions: built-in or FluentAssertions/Shouldly (check licensing changes of FluentAssertions v8: commercial
  license for some uses; verify before recommending).
- Mocking: NSubstitute, Moq, FakeItEasy. Integration: `WebApplicationFactory<T>`, Testcontainers.
- Coverage: `coverlet`, `dotnet-coverage`. Benchmarks: **BenchmarkDotNet** (`[MemoryDiagnoser]`).
- Unity: Unity Test Framework (NUnit-based, Edit Mode and Play Mode tests). Godot: GdUnit4 (C# support).

## 8. Idiomatic patterns

- Dependency injection via `Microsoft.Extensions.DependencyInjection` (ASP.NET Core, generic host), options pattern,
  `ILogger<T>` structured logging.
- Records for immutable data/DTOs; `with` to copy-and-modify.
- LINQ for queries (`Where`, `Select`, `GroupBy`, `ToDictionary`), but materialize once (`ToList()`) when enumerating
  repeatedly.
- `async` all the way down; pass `CancellationToken`; `ConfigureAwait(false)` in library code (not needed in ASP.NET
  Core apps).
- Pattern matching `switch` expressions for state machines.
- `IEnumerable<T>` iterators with `yield return`.
- Span-based parsing (`ReadOnlySpan<char>`, `int.Parse(span)`), `string.Create`, interpolated string handlers.
- Source generators (JSON, regex `[GeneratedRegex]`, logging `[LoggerMessage]`).
- Primary constructors for DI-style classes.

## 9. Top 30 pitfalls and compiler-error fixes

(Error texts from the C# compiler messages documentation.)

1. **CS0103 The name 'x' does not exist in the current context** - typo, out of scope, missing `using`.
2. **CS0246 The type or namespace name 'X' could not be found** - missing `using` or package reference.
3. **CS1061 'T' does not contain a definition for 'M'** - wrong type, missing extension `using` (e.g.
   `using System.Linq;`), or Unity API name mismatch.
4. **CS0029 Cannot implicitly convert type 'A' to 'B'** / **CS0266 ... An explicit conversion exists (are you
   missing a cast?)** - `int i = 3.5;` needs `(int)`, `long` to `int` needs a cast.
5. **CS0120 An object reference is required for the non-static field, method, or property** - calling an instance
   member from `static` code (e.g. `Main`). Create an instance or make it static.
6. **CS0165 Use of unassigned local variable** - assign on all paths.
7. **CS0161 not all code paths return a value**.
8. **CS4014 Because this call is not awaited, execution continues** - fire-and-forget by accident; `await` it.
9. **CS8618 Non-nullable property 'X' must contain a non-null value when exiting constructor** - initialize, mark
   `required`, or make it `string?`.
10. **CS8600/CS8602/CS8604 possible null** - check for null, use `?.`/`??`, or annotate. Do not silence with `!`
    unless proven.
11. **CS0019 Operator cannot be applied** - e.g. `string * int`; generic math needs `INumber<T>`.
12. **CS1996 Cannot await in the body of a lock statement** - use `SemaphoreSlim`.
13. **CS0122 inaccessible due to its protection level** - make it `public`/`internal`, or use a public API.
14. **CS0535 does not implement interface member**.
15. **CS0108/CS0114 hides inherited member** - add `override` or `new` deliberately.
16. **CS0234 namespace does not exist in namespace** - missing package or wrong target framework.
17. **NullReferenceException at runtime** - unassigned Unity `[SerializeField]` field, `GetComponent` returning null,
    uninitialized collections.
18. **Unity "fake null"** - destroyed `UnityEngine.Object`s compare `== null` as true but `?.`/`??` and `is null`
    bypass Unity's overload. Use `if (obj != null)` or `if (obj)` for Unity objects.
19. **`async void`** - exceptions crash the app; only for event handlers.
20. **`.Result` / `.Wait()` deadlocks** in UI/sync-context code and thread-pool starvation in servers.
21. **Multiple enumeration of `IEnumerable`** - re-runs queries or DB calls; materialize with `ToList()`.
22. **LINQ deferred execution captured variables** - query reads the variable when enumerated, not when declared.
23. **Modifying a collection while iterating** - `InvalidOperationException: Collection was modified`. Iterate a copy
    or use `RemoveAll`.
24. **Struct mutation through a copy** - `list[0].X = 5` on `List<MyStruct>` is CS1612; properties returning structs
    return copies.
25. **String concatenation in loops** - quadratic; `StringBuilder` or `string.Join`.
26. **`==` on strings is value equality, on other reference types identity** unless overloaded; records compare by
    value.
27. **DateTime pitfalls** - `DateTime.Now` local vs `DateTime.UtcNow`; use `DateTimeOffset`/`TimeProvider` (.NET 8+)
    for testable time.
28. **Floating point equality and `decimal` for money**.
29. **Event handler leaks** - unsubscribe (`-=`) in `Dispose`/`OnDisable`.
30. **Static mutable state with domain reload disabled in Unity** - statics keep values between Play sessions when
    "Enter Play Mode Options" skip domain reload (becoming the default in Unity 6.6 for new projects); reset them with
    `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]`.
31. **Native AOT trimming warnings (IL2026/IL3050)** - reflection-based serialization; use source generators.
32. **`field` keyword clash in C# 14** - a class member named `field` used inside property accessors now means the
    backing field; write `this.field` or `@field`.

## 10. Performance

- Measure with BenchmarkDotNet, `dotnet-counters`, `dotnet-trace`, PerfView, Visual Studio profiler, Unity Profiler.
- Reduce allocations: `Span<T>`/`Memory<T>`, `ArrayPool<T>`, `stackalloc`, avoid LINQ and closures in hot paths,
  avoid boxing (`IEquatable<T>` on structs), `StringBuilder`, `string.Create`, `FrozenDictionary` for read-mostly
  lookups (.NET 8+), `CollectionsMarshal.AsSpan(list)`.
- Use `ValueTask` for frequently synchronous async methods; `IAsyncEnumerable` for streaming.
- Server GC for throughput services; tiered PGO is on by default; ReadyToRun or Native AOT for startup.
- SIMD: `Vector<T>`, `Vector128/256/512`, hardware intrinsics.
- Unity: Burst + Jobs + `NativeArray`, avoid `GetComponent` and `Find` in `Update`, cache references, object pooling
  (`UnityEngine.Pool.ObjectPool<T>`).

## 11. Security

- Memory-safe by default; `unsafe` code and P/Invoke are the exceptions (C# 15 starts tightening `unsafe` rules).
- **SQL injection**: parameterized queries (`command.Parameters.AddWithValue("@id", id)`, Dapper parameters, EF Core
  LINQ). EF Core `FromSqlInterpolated`/`FromSql($"... {id}")` parameterize interpolations; `FromSqlRaw` with string
  concatenation does not.
- **Deserialization**: `BinaryFormatter` is removed from .NET 9+ (throws); never deserialize untrusted data with
  type-name handling (`Newtonsoft.Json TypeNameHandling.All`). Use `System.Text.Json` with known types.
- **Command injection**: `ProcessStartInfo` with `ArgumentList` (no shell), `UseShellExecute = false`.
- **Path traversal**: `Path.GetFullPath` then verify the prefix; never trust file names from clients.
- **XSS/CSRF** in ASP.NET Core: Razor encodes by default; antiforgery tokens; `[ValidateAntiForgeryToken]`.
- Secrets: User Secrets in development, Key Vault/environment in production; never commit `appsettings` secrets.
- Crypto: `System.Security.Cryptography` (AES-GCM, `RandomNumberGenerator`, PBKDF2 `Rfc2898DeriveBytes.Pbkdf2`);
  never `System.Random` for tokens.
- Supply chain: NuGet package source mapping, lock files, `dotnet list package --vulnerable --include-transitive`,
  signed packages.
- Games: never trust the client; Unity client code is easily decompiled (IL2CPP only raises the bar).

## 12. Game-development usage

- **Unity**: C# scripts derive from `MonoBehaviour` (`Awake`, `Start`, `Update`, `FixedUpdate`, `OnDestroy`),
  `ScriptableObject` for data, `[SerializeField] private` fields in the Inspector. Unity 6.0 docs list the Roslyn
  **C# 9.0** language level for scripts; Unity is migrating from Mono to **CoreCLR**: CoreCLR player experimental in
  Unity 6.7, full CoreCLR editor targeted for **Unity 6.8 with .NET 10 / C# 14** (Unity forum status updates,
  March/June 2026). Until then, newer C# syntax may not compile in Unity; check the project's Unity version.
  IL2CPP for consoles/iOS (AOT: no `System.Reflection.Emit`, generic virtual methods need care).
- **Godot 4 .NET**: `public partial class Player : CharacterBody2D` with `[Export]` properties, `_Ready()`,
  `_PhysicsProcess(double delta)`; signals as C# events (`[Signal] public delegate void HitEventHandler();`); targets
  modern .NET (Godot 4.4+ uses .NET 8). No web export for C# in Godot 4 (verify per version).
- **MonoGame** (XNA-style `Game` with `Update(GameTime)`/`Draw(GameTime)`), **FNA**, **Stride** (C# 3D engine),
  **Raylib-cs**, **Silk.NET** (graphics bindings), **Bepu Physics**.
- Embedding Lua: **MoonSharp** (Lua 5.2 interpreter in C#), **NLua** (binds native Lua/KeraLua); Luau via
  P/Invoke to the Luau C API is possible but uncommon (unverified mature bindings).
- Roblox-to-Unity mapping: `Script` -> `MonoBehaviour`, `ModuleScript` -> plain C# class, `RemoteEvent` -> Netcode for
  GameObjects RPCs / Mirror / Fish-Net, `DataStore` -> your own backend or Unity Cloud Save, `task.wait` -> coroutine
  `yield return new WaitForSeconds(1)` or `await Awaitable.WaitForSecondsAsync(1)`.

## 13. Cheat sheet: C# vs Luau

| Concept | Luau | C# |
|---|---|---|
| Variable | `local x = 1` | `var x = 1;` / `int x = 1;` |
| Constant | `local MAX = 10` | `const int Max = 10;` / `static readonly` |
| Nil | `nil` | `null` (reference types, `T?`), NRT warnings |
| Number | `number` | `int`, `long`, `float`, `double`, `decimal` |
| Integer division | `7 // 2 == 3` floored | `7 / 2 == 3` truncated; `Math.Floor` or `int.DivRem` |
| Indexing | 1-based | 0-based; `^1` is last (Index from end) |
| Array | `{1, 2, 3}` | `int[] a = [1, 2, 3];` / `List<int>` |
| Map | `{a = 1}` | `Dictionary<string, int> d = new() { ["a"] = 1 };` |
| Length | `#t` | `array.Length`, `list.Count` |
| String concat | `a .. b` | `a + b`, `$"{a}{b}"` |
| Format | `string.format("%.2f", x)` | `$"{x:F2}"`, `string.Format` |
| Function | `local function f(a)` | `static int F(int a) => a;` |
| Closure | upvalues | lambdas `x => x + 1` capture variables |
| Multiple returns | `return a, b` | tuples `(int, string) F()` / `out` params |
| Module | `require` | `using Namespace;` + project/package references |
| Class | metatable | `class` with fields, properties, methods |
| Method | `obj:M()` | `obj.M()` |
| Inheritance | metatable chain | `class B : A` with `virtual`/`override`; interfaces |
| Error raise | `error("x")` | `throw new Exception("x")` |
| Error catch | `pcall` | `try { } catch (Exception e) { }` |
| Coroutine | `coroutine`, `task.spawn` | `async`/`await`, `IEnumerator` coroutines in Unity |
| Wait | `task.wait(1)` | `await Task.Delay(1000)` / Unity `yield return new WaitForSeconds(1)` |
| Events | `BindableEvent`, `:Connect` | `event Action<T>`, `+=`/`-=` |
| Types | gradual | static, generics, nullable annotations |
| Generics | `<T>` | `class Box<T> where T : new()` |
| Iteration | `for k, v in pairs(t)` | `foreach (var (k, v) in dict)` |
| Equality | `==` | `==` (value for primitives/strings/records), `Equals`, `ReferenceEquals` |
| Memory | GC | GC + `IDisposable` |
| Truthiness | `nil`/`false` falsy | only `bool` (Unity objects have an implicit bool) |

## 14. Sources

Versions and releases:
- https://dotnet.microsoft.com/en-us/download/dotnet - supported versions, .NET 10 LTS, .NET 11 RC2
- https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-10/overview - .NET 10 overview
- https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-14 - C# 14 features
- https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-15 - C# 15 preview features
- https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-13 - C# 13 features
- https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/configure-language-version - language versioning
- https://devblogs.microsoft.com/dotnet/introducing-csharp-14/ - C# 14 announcement

Language and runtime:
- https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-messages/ - compiler errors
- https://learn.microsoft.com/en-us/dotnet/csharp/nullable-references - nullable reference types
- https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/fundamentals - GC
- https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/implementing-dispose - Dispose pattern
- https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/ - async
- https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/ - Native AOT

Tooling, testing, security:
- https://learn.microsoft.com/en-us/nuget/consume-packages/central-package-management - central package management
- https://learn.microsoft.com/en-us/dotnet/core/testing/ - testing overview
- https://benchmarkdotnet.org/ - benchmarks
- https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide - BinaryFormatter removal
- https://learn.microsoft.com/en-us/ef/core/querying/sql-queries - EF Core raw SQL parameterization
- https://cheatsheetseries.owasp.org/cheatsheets/DotNet_Security_Cheat_Sheet.html - OWASP .NET

Game development:
- https://docs.unity3d.com/6000.0/Documentation/Manual/csharp-compiler.html - Unity C# compiler level
- https://discussions.unity.com/t/coreclr-scripting-and-ecs-status-update-march-2026/1711852 - CoreCLR plan
- https://discussions.unity.com/t/coreclr-scripting-and-serialization-update-june-2026/1723299 - CoreCLR June 2026
- https://docs.godotengine.org/en/stable/tutorials/scripting/c_sharp/index.html - Godot C#
- https://docs.monogame.net/ - MonoGame
