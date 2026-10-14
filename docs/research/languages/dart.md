# Dart for STAR (research, checked 2026-10-13)

Status: latest stable verified is **Dart 3.13** (2026-08-12 [1]); earlier 2026 releases 3.12 (2026-05, private named parameters, primary constructors preview) and 3.11 (2026-02-11) [2]. Dart 3.10 (2025-11-12) added dot shorthands [3]. Flutter versions are tied to Dart releases (Flutter 3.41+ ships Dart 3.11+ per pub.dev listings; exact current Flutter version unverified as of 2026-10-13). Flame latest seen: 1.37.x (secondary listing, unverified).

---

## 1. Mental model

- **Class-based, single-inheritance OOP with mixins**, garbage-collected, single-threaded event loop per **isolate** (an isolate = its own heap + event loop; isolates share no memory and talk via messages).
- **Everything is an object** including `int`, `null` (instance of `Null`), functions.
- **Sound null safety** (mandatory since Dart 3.0): types are non-nullable by default; `String?` admits null. The compiler refuses to call methods on a nullable without a check. Flow analysis promotes `String?` to `String` after `if (x != null)` — but only for *local variables and private final fields* (3.2+), not public fields or getters.
- **Compilation targets**: JIT VM (development, hot reload), AOT native (ARM/x64/RISC-V, `dart compile exe`), JavaScript (`dart2js`, DDC for dev), WebAssembly (`dart2wasm`, Flutter web Wasm).
- Primary audience: **Flutter** UI apps (mobile, desktop, web), plus CLI tools and servers (Shelf, Dart Frog, Serverpod).
- **Language versioning**: each package's SDK constraint lower bound selects the language version, so new syntax (e.g. dot shorthands need `sdk: ^3.10.0`) is enabled per package [3][2].

## 2. Type system

- Static, sound, with type inference (`var`, `final`, `const`). `dynamic` opts out of static checks (avoid); `Object?` is the top type that still requires casts.
- `final` = assigned once at runtime; `const` = compile-time constant, canonicalised (`const []` is deeply immutable). `late` = non-nullable but initialised later (throws `LateInitializationError` if read first).
- Generics are **reified** (`List<int>` knows it's `List<int>` at runtime; `is List<int>` works), unlike Java/TS.
- **Records** (3.0): `(int, String)` positional, `({int x, int y})` named; value equality; multiple returns: `(int, int) minMax(List<int> xs)`.
- **Patterns** (3.0): destructuring in `var (a, b) = pair;`, `switch` expressions, `if (json case {'name': String name})`, object patterns `Point(:var x, :var y)`, guards `when`.
- **Class modifiers** (3.0): `sealed` (exhaustive switching over subtypes in same library), `final`, `base`, `interface`, `mixin class`.
- **Extension methods** and **extension types** (3.3, zero-cost wrappers: `extension type UserId(int id) {}`).
- **Dot shorthands** (3.10): `.center` instead of `MainAxisAlignment.center` when the context type is known [3].
- **Private named parameters** (3.12): `Point({required this._x})` — callers write `x:` [2].
- **Primary constructors** (stable in 3.13): `class Point(final int x, final int y);` plus empty bodies ending with `;` [1].
- **Macros were cancelled** (announced January 2025): static metaprogramming via macros will not ship; use `build_runner` code generation (json_serializable, freezed) and augmentations work continues separately.

```dart
sealed class Shape {}
class Circle extends Shape { Circle(this.r); final double r; }
class Rect extends Shape { Rect(this.w, this.h); final double w, h; }

double area(Shape s) => switch (s) {      // exhaustive: compiler errors if a subtype is missing
  Circle(:final r) => 3.14159 * r * r,
  Rect(:final w, :final h) => w * h,
};
```

## 3. Runtime, concurrency and async model

- **Event loop** per isolate with two queues: microtasks (scheduled by completing Futures, `scheduleMicrotask`) run before the next event (I/O, timers, UI frames).
- **`Future<T>`** (one value) and **`Stream<T>`** (many values); `async`/`await`, `async*`/`yield` for streams, `await for` to consume.
- **Isolates** for CPU parallelism: `Isolate.run(() => heavy(data))` (2.19+) returns a Future; in Flutter `compute()`. Messages are copied (except `TransferableTypedData` and immutable objects within an isolate group).
- An `async` function runs synchronously until its first `await`.
- Unawaited futures swallow nothing — errors become *unhandled errors* in the zone; lint `unawaited_futures` / `discarded_futures`.

```dart
Future<String> loadProfile(String id) async {
  final res = await http.get(Uri.parse('https://api.example.com/u/$id'))
      .timeout(const Duration(seconds: 5));
  if (res.statusCode != 200) throw HttpException('status ${res.statusCode}');
  return res.body;
}

Stream<int> countdown(int from) async* {
  for (var i = from; i >= 0; i--) {
    await Future.delayed(const Duration(seconds: 1));
    yield i;
  }
}

final results = await Future.wait([loadProfile('a'), loadProfile('b')]);
final parsed = await Isolate.run(() => jsonDecode(bigJson));   // off the UI isolate
```

## 4. Tooling and package management

- `dart` CLI: `dart create`, `dart run`, `dart test`, `dart analyze`, `dart format`, `dart fix --apply`, `dart compile exe|js|wasm`, `dart pub get|add|upgrade|outdated`, `dart build` / `dart install` (3.10) [2]. Flutter: `flutter create|run|test|build`, `flutter pub ...`.
- **pub** package manager, registry **pub.dev**; `pubspec.yaml` + `pubspec.lock` (commit the lock for apps, not for libraries). **Pub workspaces** (3.6+) for monorepos.

```yaml
name: tank_game
environment:
  sdk: ^3.13.0
dependencies:
  flame: ^1.37.0
dev_dependencies:
  test: ^1.25.0
  lints: ^6.0.0
```

- Lints: `package:lints` / `flutter_lints` in `analysis_options.yaml`; 3.10 added analyzer plugins for custom rules [3].
- Code generation: `dart run build_runner build --delete-conflicting-outputs` (json_serializable, freezed, riverpod_generator).
- Build hooks (stable 3.10) compile native assets; 3.13 adds `@RecordUse()` tree-shaking of native libraries [1].
- FFI: `dart:ffi` + `package:ffigen`; JS interop: `dart:js_interop` + `package:web` (`dart:html`/`package:js` deprecated since 3.7 and unsupported on Wasm [1]).
- Dart MCP server for AI tooling (3.9 docs) [2].

## 5. Testing

- `package:test`: `test()`, `group()`, `expect(actual, matcher)`, `setUp`, async tests return Futures; `expectLater(stream, emitsInOrder([...]))`.
- Flutter: `flutter_test` widget tests (`testWidgets`, `WidgetTester.pumpWidget`, `find.text`), golden tests, `integration_test`.
- Mocks: `mocktail` (no codegen) or `mockito` (codegen). Flame: `flame_test` (`testWithFlameGame`).

```dart
import 'package:test/test.dart';

void main() {
  group('Inventory', () {
    test('adds stacks', () {
      final inv = Inventory()..add('potion', 2)..add('potion', 3);
      expect(inv.count('potion'), equals(5));
    });
    test('rejects overflow', () {
      expect(() => Inventory(capacity: 1).add('sword', 2), throwsA(isA<StateError>()));
    });
  });
}
```

## 6. Idiomatic patterns

```dart
// Immutable data class with value equality (or freezed / records)
class Vec2 {
  const Vec2(this.x, this.y);
  final double x, y;
  Vec2 operator +(Vec2 o) => Vec2(x + o.x, y + o.y);
  @override bool operator ==(Object o) => o is Vec2 && o.x == x && o.y == y;
  @override int get hashCode => Object.hash(x, y);
}

// Primary constructor (3.13)
class Enemy(final String name, final int hp);

// Named parameters with required
void spawn({required String kind, double x = 0, double y = 0}) {}

// Null-aware operators
final city = user?.address?.city ?? 'unknown';
cache[key] ??= compute(key);
items?.forEach(print);

// Cascades
final paint = Paint()
  ..color = const Color(0xFFFF0000)
  ..strokeWidth = 2;

// Collection if/for and spreads
final widgets = [
  const Header(),
  if (isLoggedIn) const Profile(),
  for (final m in messages) MessageTile(m),
  ...?extra,
];

// Pattern matching on JSON
void handle(Map<String, Object?> json) {
  if (json case {'type': 'move', 'x': num x, 'y': num y}) {
    move(x.toDouble(), y.toDouble());
  }
}

// Enhanced enums
enum Weapon {
  sword(damage: 10), bow(damage: 6);
  const Weapon({required this.damage});
  final int damage;
}

// Dot shorthand (3.10)
Weapon pick() => .sword;
```

Flame game skeleton:

```dart
class MyGame extends FlameGame with HasCollisionDetection {
  @override
  Future<void> onLoad() async {
    await images.load('player.png');
    add(Player()..position = Vector2(100, 100));
  }
}

class Player extends SpriteComponent with HasGameReference<MyGame>, CollisionCallbacks {
  final velocity = Vector2.zero();
  @override
  Future<void> onLoad() async {
    sprite = Sprite(game.images.fromCache('player.png'));
    add(RectangleHitbox());
  }
  @override
  void update(double dt) {            // dt in seconds, like Heartbeat's deltaTime
    position += velocity * dt;
  }
}

void main() => runApp(GameWidget(game: MyGame()));
```

## 7. Top pitfalls and error-message fixes

| Exact error text | Cause | Fix |
|---|---|---|
| `The property 'length' can't be unconditionally accessed because the receiver can be 'null'.` | Using a nullable without check | `if (s != null)`, `s?.length`, `s!.length` only if proven |
| `A value of type 'String?' can't be assigned to a variable of type 'String'.` | Nullable flowing into non-nullable | `?? default`, early return, or make the target nullable |
| `The getter 'x' isn't defined for the type 'Object'.` / `for the type 'dynamic'` hides it until runtime `NoSuchMethodError` | Lost static type (from `jsonDecode`, `Map<String, dynamic>`) | Cast/pattern-match: `if (j case {'x': int x})`, or generate models |
| `'field' can't be promoted to 'int' because 'field' is a public field` (wording varies; see "why not promoted" docs) | Promotion only works on locals and private final fields | Copy to a local: `final f = field; if (f != null) use(f);` |
| `Null check operator used on a null value` | `!` on null at runtime | Remove `!`; handle null |
| `LateInitializationError: Field 'controller' has not been initialized.` | `late` read before assignment | Initialise in `initState`/constructor or make nullable |
| `type 'List<dynamic>' is not a subtype of type 'List<String>'` | `jsonDecode` returns `List<dynamic>` | `(json as List).cast<String>()` or `List<String>.from(...)`, or map with types |
| `type '_Map<String, dynamic>' is not a subtype of type 'Map<String, String>' in type cast` | Same, for maps | `Map<String, String>.from(m)` |
| `The non-nullable variable 'x' must be initialized.` | Non-nullable top-level/field with no initializer | Initialise, mark `late`, or `?` |
| `The method 'setState' isn't defined for the type 'MyWidget'` | Using `StatelessWidget` | Convert to `StatefulWidget` or use a state manager |
| `setState() called after dispose()` | Async callback finishing after the widget left the tree | Check `if (!mounted) return;` after `await` |
| `Bad state: Stream has already been listened to.` | Single-subscription stream listened twice | `.asBroadcastStream()` or a `StreamController.broadcast()` |
| `Unhandled Exception: ... (unawaited Future)` | Future errors without `await`/`catchError` | `await` it or `unawaited(f.catchError(...))`; enable `unawaited_futures` lint |
| `Invalid argument(s): Illegal argument in isolate message: (object is a Closure ...)` | Sending non-sendable objects (closures capturing state, sockets) to an isolate | Send plain data; use `Isolate.run` with top-level/static functions |
| `This requires the 'dot-shorthands' language feature to be enabled.` (or similar language-version error) | Package SDK lower bound below 3.10 | Raise `environment: sdk: ^3.10.0` [3] |
| `RenderFlex overflowed by 42 pixels on the right.` | Flutter row content too wide | `Expanded`/`Flexible`, `SingleChildScrollView`, `Wrap` |

Other mistakes:
- Integer division: `7 / 2` is `3.5` (double); use `7 ~/ 2` for 3. `%` is Euclidean-like: result always non-negative for positive divisor (`-7 % 3 == 2`, like Luau); `remainder()` truncates.
- `int` is 64-bit on native but **JS numbers on the web** (53-bit safe integers) — overflow behaviour differs by platform.
- `==` on lists compares identity; use `listEquals` (Flutter) or `const DeepCollectionEquality().equals` (package:collection).
- String interpolation `'$name'` / `'${obj.prop}'` — `'$obj.prop'` interpolates only `obj`.
- `forEach` with an `async` callback does not wait; use `for (final x in xs) { await f(x); }` or `Future.wait`.

## 8. Performance

- Release builds are AOT; profile with **DevTools** (CPU profiler, memory, timeline) in profile mode, never debug mode (JIT + asserts are much slower).
- Flutter: keep `build()` cheap, use `const` widgets, `ListView.builder` for long lists, `RepaintBoundary`, avoid `Opacity` animation (use `FadeTransition`), precache images; Impeller renderer is default on iOS/Android.
- Move parsing and heavy math off the UI isolate (`Isolate.run`).
- Use typed data (`Float32List`, `Int32List`) for numeric arrays; avoid boxing `dynamic`.
- Flame: object pooling for bullets/particles, sprite batching (`SpriteBatch`), avoid allocating `Vector2` per frame (reuse and `setFrom`).
- Web: dart2wasm (Flutter web `--wasm`) usually beats dart2js for compute; 3.13 adds deferred loading preview for Wasm [1].

## 9. Security

- Do not embed secrets in Flutter apps: AOT binaries can be decompiled/stringified; keep credentials on a backend.
- Use `flutter_secure_storage` (Keychain/Keystore) not `SharedPreferences` for tokens.
- TLS: never set `badCertificateCallback = (_, __, ___) => true` in release.
- Validate deep links and `Uri` inputs; parse with `Uri.parse` and check scheme/host allowlists.
- Server side (Shelf/Dart Frog): parameterised SQL (`package:postgres` uses `Sql.named('... @id')` with parameters), validate JSON with patterns.
- `dart pub outdated` and pub.dev's package scores; pin and review transitive dependencies; check publisher verification on pub.dev.
- Obfuscate release builds (`--obfuscate --split-debug-info=...`) — reduces, not prevents, reverse engineering.

## 10. Game-dev usage

- **Flame** (Flutter 2D engine): component system (`FlameGame`, `Component`, `PositionComponent`, `SpriteComponent`), game loop `update(dt)`/`render(canvas)`, collision detection (`HasCollisionDetection`, hitboxes), effects (`MoveEffect`, `ScaleEffect`), input mixins (`TapCallbacks`, `DragCallbacks`, `KeyboardHandler`), cameras (`CameraComponent`, `World`), bridges: `flame_forge2d` (Box2D physics), `flame_tiled` (Tiled maps), `flame_audio`, `flame_rive`, `flame_bloc`. `flame_3d` is experimental [6].
- Google's **Flutter Casual Games Toolkit** (ads, in-app purchases, Play Games Services, leaderboards templates).
- Flutter is common for game companion apps, menus/UI and turn-based/puzzle games; high-end 3D action is not its niche (Impeller + `flutter_gpu` experiments exist).
- Dart for servers: Serverpod (full-stack Dart backend with codegen), Dart Frog, Shelf — viable for small multiplayer backends with WebSockets.

## 11. Cheat sheet vs Luau

| Concept | Luau | Dart |
|---|---|---|
| Indexing base | 1 | 0 (`list[0]`, `list.last`) |
| Length | `#t` | `list.length`, `str.length` (UTF-16 units) |
| Absent value | `nil` | `null` (only in `T?` types) |
| Truthiness | `nil`/`false` falsy, rest truthy | Conditions must be `bool`; `if (0)` is a compile error |
| Not equal | `~=` | `!=` |
| String concat | `a .. b` | `'$a$b'`, `a + b` (both Strings) |
| Array | `{1, 2}` | `[1, 2]` (`List<int>`) |
| Map | `{a = 1}` | `{'a': 1}` (`Map<String, int>`), sets `{1, 2}` |
| Missing key | nil | `map['x']` -> `null` (type `V?`) |
| Iterate | `for i, v in ipairs(t)` | `for (final v in list)`, `list.indexed` (3.0) gives `(i, v)` records |
| Methods / self | `obj:m()` and `self` | `obj.m()`; `this` implicit |
| Classes | metatables | `class A extends B with M implements I` |
| Closures | `function() end` | `() => x`, `(a) { ... }` |
| Coroutines | `coroutine.*` | generators `sync*`/`async*` + `yield`; no general coroutines |
| Async | `task.spawn`/`task.wait` | `Future`, `async/await`, `Stream`, `Future.delayed` |
| Integer division | `7 // 2` | `7 ~/ 2` |
| Float division | `7 / 2` | `7 / 2` -> `3.5` |
| Error raise | `error("x")` | `throw StateError('x')` (`Exception` for recoverable, `Error` for bugs) |
| Error catch | `pcall` | `try {} on FormatException catch (e, st) {} finally {}` |
| Modules | `require(m)` | `import 'package:x/x.dart';`, `show`/`hide`/`as`; `_name` is library-private |
| Typing | optional (`--!strict`) | always static, sound null safety |
| Frame callback | `RunService.Heartbeat:Connect(fn(dt))` | Flame `update(double dt)`; Flutter `Ticker`/`AnimationController` |

## 12. Recent changes and version notes

- **Dart 3.13 (2026-08-12)** [1]: primary constructors stable (`class Point(final int x, final int y);`), migration lints and refactorings, dart2wasm deferred loading (experimental flag), formatter changes (import sections, chain splitting), `@RecordUse()` native tree-shaking, heap memory cage.
- **Dart 3.12 (2026-05)** [2]: private named parameters, primary constructors (experimental), language versioning docs.
- **Dart 3.11 (2026-02-11)** [2]: no new language features; dot-shorthand tooling improvements, build hook env vars.
- **Dart 3.10 (2025-11-12)** [3]: dot shorthands, analyzer plugins, build hooks stable, `dart build`/`dart install`.
- **Dart 3.9/3.8 (2025)**: null-aware elements (`?x` in collections, 3.8), cross-compilation to ARM/RISC-V64, Dart MCP server.
- **Macros cancelled** (2025-01) — use build_runner.
- Dart 3.0 (2023) removed non-null-safe code entirely; records, patterns, class modifiers.

## Sources

1. https://dart.dev/blog/announcing-dart-3-13
2. https://dart.dev/guides/whats-new
3. https://dart.cn/blog/announcing-dart-3-10 (mirror of the official Dart 3.10 announcement)
4. https://dart.dev/language
5. https://dart.dev/null-safety/understanding-null-safety
6. https://docs.flame-engine.org/latest/
7. https://dart.dev/language/patterns
8. https://dart.dev/language/records
9. https://dart.dev/language/class-modifiers
10. https://dart.dev/language/concurrency
11. https://dart.dev/tools/pub/workspaces
12. https://dart.dev/tools/non-promotion-reasons
13. https://medium.com/dartlang/an-update-on-dart-macros-data-serialization-06d3037d4f12
14. https://docs.flutter.dev/perf/best-practices
15. https://pub.dev/packages/test
16. https://github.com/dart-lang/sdk/blob/main/CHANGELOG.md
