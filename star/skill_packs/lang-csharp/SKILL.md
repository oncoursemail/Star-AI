---
name: lang-csharp
description: C# 14 on .NET 10 LTS (C# 15 / .NET 11 in preview) nullability, async/await, IDisposable, LINQ, compiler errors, Unity and Godot C#. Use for C# code, CS#### errors, async deadlocks, NuGet/dotnet CLI, Unity scripts or Godot .NET.
---
# C# 14 / .NET 10 (LTS)
- .NET 10 is the current LTS (C# 14: extension members, the `field` keyword, null-conditional assignment `a?.B = x`, implicit span conversions, `dotnet run app.cs`). .NET 11 / C# 15 (unions, `closed` classes, labeled break) is preview/RC: only with `net11.0`. Unity does not use the latest C#: Unity 6.0 scripts compile at C# 9; CoreCLR with .NET 10 / C# 14 is planned for Unity 6.8. Check the engine version before using new syntax.
- Nullable reference types: CS8618 (non-nullable member not initialized: initialize, `required`, or `T?`), CS8602 (possible null dereference: check, `?.`, `??`). Do not silence with `!` without proof.
- Async: `async Task`, never `async void` except event handlers; never block on async with `.Result`/`.Wait()` (deadlocks, thread-pool starvation); pass `CancellationToken`; CS4014 means a call was not awaited; no `await` inside `lock` (CS1996): use `SemaphoreSlim`.
- `IDisposable`: `using var x = ...;` / `await using`; unsubscribe events (`-=`) to avoid leaks.
- LINQ is lazy: enumerate once (`ToList()`), and do not modify a collection while iterating ("Collection was modified": use `RemoveAll` or a copy).
- Value vs reference: structs copy; `list[i].X = 1` on a `List<struct>` is CS1612.
- Common errors: CS0103 name not in context, CS0246 type not found (missing `using`/package), CS1061 no member (missing `using System.Linq;` or wrong type), CS0029/CS0266 conversion needs a cast, CS0120 instance member from static code, CS0165 unassigned local.
- Unity: destroyed objects compare `== null` true but `?.`, `??` and `is null` skip Unity's check; use `if (obj != null)`. Cache `GetComponent` results; no Unity API calls off the main thread; reset statics when domain reload is disabled.
- Godot 4: `public partial class Player : CharacterBody2D`, `[Export]`, `_PhysicsProcess(double delta)`.
- Security: parameterized SQL (`@id` parameters, EF Core LINQ or `FromSql($"...{id}")`; never `FromSqlRaw` with concatenation); `BinaryFormatter` is removed in .NET 9+; `ProcessStartInfo.ArgumentList` without a shell; `RandomNumberGenerator` for tokens.
- Tooling: `dotnet new`, `dotnet build`, `dotnet test` (xUnit/NUnit/MSTest), `dotnet add package`, Central Package Management, `<Nullable>enable</Nullable>`, `<TreatWarningsAsErrors>`, BenchmarkDotNet, `dotnet list package --vulnerable`.
