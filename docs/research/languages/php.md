# PHP for STAR (research, checked 2026-10-13)

Status: **PHP 8.5** is the newest stable line (GA 2025-11-20 [2]); **PHP 8.4** (GA 2024-11-21 [1]) is fully supported and is the version most projects target in 2026. **PHP 8.6** is in release candidates with GA scheduled for 2026-11-19 (secondary sources; RC status and exact feature set unverified as of 2026-10-13) — partial function application (`?` / `...` placeholders) was reported accepted for 8.6 [11]. Everything below marked 8.4/8.5 is from php.net release pages.

---

## 1. Mental model

- **Shared-nothing request model.** Classic PHP (PHP-FPM, Apache mod_php) boots the script for every HTTP request, runs top to bottom, and throws away all state at the end. No in-memory globals survive between requests; persistence lives in the database, Redis, sessions, or the OPcache (compiled bytecode only).
- **Long-running servers changed this**: FrankenPHP worker mode, RoadRunner, Swoole/OpenSwoole and ReactPHP/AMPHP keep the app booted across requests. Then static properties and singletons *do* leak state between requests — reset them.
- **Variables start with `$`**, are function-scoped (no block scope), and are copied on assignment for arrays/strings (copy-on-write) but **objects are handles** (assignment copies the handle; use `clone` to copy).
- **Arrays are ordered hash maps** (`array`): one type serves as list, dict, set, stack and queue. Keys are int or string; numeric strings like `"5"` become int keys `5`.
- Modern PHP (8.x) is a *typed, class-based* language: strict types per file, enums, readonly classes, match expressions, attributes, first-class callables, property hooks (8.4), pipe operator (8.5).
- Execution: Zend Engine compiles to opcodes, cached by **OPcache**; optional **JIT** (tracing JIT; 8.4 rewrote the JIT on the IR framework [1]).

## 2. Type system

- Gradual, runtime-enforced type declarations on parameters, returns and properties: scalar (`int`, `float`, `string`, `bool`), `array`, `iterable`, `callable`, `object`, `mixed`, class/interface names, `self`/`static`/`parent`, `null`, `void`, `never`, `true`/`false`, nullable `?T`, unions `A|B`, intersections `A&B`, DNF `(A&B)|null` (8.2).
- **Coercive by default**: `function f(int $x)` called with `"5"` silently converts. Put `declare(strict_types=1);` as the first statement in every file to make scalar types strict for calls *made from that file*. Return types and property types follow the file where they are declared.
- Implicitly nullable parameters (`Foo $x = null`) are **deprecated in 8.4**: write `?Foo $x = null` [1].
- Enums (8.1): pure `enum Suit { case Hearts; }` and backed `enum Status: string { case Active = 'active'; }` with `::from()` (throws `ValueError`) and `::tryFrom()` (returns null).
- `readonly` properties (8.1) and `readonly class` (8.2); 8.5 `clone($obj, ['prop' => $v])` ("clone with") makes with-ers on readonly classes easy [2].
- **Property hooks (8.4)**: `get`/`set` bodies on properties, virtual properties, hooks in interfaces [1].
- **Asymmetric visibility (8.4)**: `public private(set) string $version`; 8.5 extends it to static properties [1][2].
- Generics do **not** exist at runtime; use PHPDoc generics (`@template T`, `@param list<T>`, `array{id: int, name: string}` shapes) checked by **PHPStan** or **Psalm**.
- Comparison: `==` is loose (PHP 8 changed `0 == "abc"` to false, but `"1" == "01"` and `"10" == "1e1"` are still true). Always use `===` / `!==`.

## 3. Runtime, concurrency and async model

- One request = one process/thread worker in FPM; concurrency comes from many workers (`pm.max_children`). Within a request, code is synchronous.
- **Fibers (8.1)**: low-level stackful coroutines (`new Fiber(fn)`, `$fiber->start()`, `Fiber::suspend($v)`, `$fiber->resume($v)`) — the same shape as Luau coroutines. Applications rarely use them directly; event-loop libraries do:
  - **AMPHP v3** and **ReactPHP** (`react/async` `await()`), **Revolt** event loop: write sequential-looking async code built on fibers.
  - **Swoole/OpenSwoole**: C-extension coroutine runtime with hooked I/O.
- **FrankenPHP** (Caddy-based app server written in Go, now under the PHP Foundation umbrella): worker mode keeps the app in memory, supports early hints, HTTP/3, and can build standalone binaries [8].
- Parallelism: `pcntl_fork` (CLI), `ext-parallel` (ZTS builds), queues (Laravel Horizon, Symfony Messenger) and multiple workers.
- Timeouts: `max_execution_time` (8.5 includes a backtrace on fatal errors like this [2]), `set_time_limit()`.

```php
$fiber = new Fiber(function (int $x): int {
    $y = Fiber::suspend($x * 2);   // like coroutine.yield
    return $x + $y;
});
$first = $fiber->start(5);         // 10
$fiber->resume(1);
echo $fiber->getReturn();          // 6
```

## 4. Tooling and package management

- **Composer** is the package manager: `composer.json`, `composer.lock` (commit it for apps), `vendor/` (do not commit), PSR-4 autoload mapping namespaces to folders; registry **Packagist**.

```json
{
  "require": { "php": ">=8.4", "monolog/monolog": "^3.7" },
  "require-dev": { "phpunit/phpunit": "^12.0", "phpstan/phpstan": "^2.1" },
  "autoload": { "psr-4": { "App\\": "src/" } }
}
```

  `composer dump-autoload` after changing autoload; `composer audit` checks advisories.
- Static analysis: **PHPStan** (levels 0-10; 2.x added level 10 "mixed is strict") and **Psalm**; **Rector** for automated upgrades (e.g. to 8.4 syntax); formatting with **PHP-CS-Fixer** or **PHP_CodeSniffer** (PSR-12 / PER Coding Style).
- Version managers: Docker official images, `phpenv`, Laravel Herd, `brew install php`, `ondrej/php` PPA, on Windows `php.exe` zips from windows.php.net or **Herd**; `static-php-cli` / FrankenPHP for single binaries.
- Frameworks: **Laravel** (12.x/13.x), **Symfony** (7.x/8.x), Slim, Laminas; CMS: WordPress, Drupal.
- Debugging: Xdebug (step debugger, profiler), `var_dump`, `dd()` in Laravel, `error_log`.
- Config: `php.ini` (`display_errors=Off` in production, `error_reporting=E_ALL`, `opcache.enable=1`).

## 5. Testing

- **PHPUnit** (11.x/12.x): attributes `#[Test]`, `#[DataProvider('cases')]` replace docblock annotations (annotations removed in 12).
- **Pest** (built on PHPUnit): `it('adds', fn () => expect(add(1, 2))->toBe(3));`, architecture tests, type coverage.
- Mutation testing: **Infection**. Browser: Laravel Dusk, Symfony Panther, Pest browser plugin.

```php
use PHPUnit\Framework\TestCase;
use PHPUnit\Framework\Attributes\{Test, DataProvider};

final class ScoreTest extends TestCase
{
    public static function cases(): array { return [[1, 2, 3], [0, 0, 0]]; }

    #[Test, DataProvider('cases')]
    public function adds(int $a, int $b, int $sum): void
    {
        self::assertSame($sum, Score::add($a, $b));   // assertSame = ===, prefer over assertEquals
    }
}
```

## 6. Idiomatic patterns

```php
<?php
declare(strict_types=1);

namespace App\Game;

enum Team: string
{
    case Red = 'red';
    case Blue = 'blue';

    public function opponent(): self
    {
        return match ($this) {         // match is strict (===) and exhaustive (UnhandledMatchError)
            self::Red => self::Blue,
            self::Blue => self::Red,
        };
    }
}

final readonly class Player                 // constructor promotion + readonly class
{
    public function __construct(
        public string $id,
        public Team $team,
        public int $score = 0,
    ) {}

    public function withScore(int $score): self
    {
        return clone($this, ['score' => $score]);    // PHP 8.5 clone-with [2]
    }
}

final class Inventory
{
    /** @var array<string, int> */
    private array $items = [];

    public int $count { get => array_sum($this->items); }   // 8.4 virtual property hook

    public private(set) int $capacity = 20;                  // 8.4 asymmetric visibility

    public function add(string $item, int $qty = 1): void
    {
        if ($this->count + $qty > $this->capacity) {
            throw new \OverflowException("Inventory full");
        }
        $this->items[$item] = ($this->items[$item] ?? 0) + $qty;   // null coalescing
    }
}

// First-class callables, arrow functions, array helpers
$names  = array_map(fn(Player $p) => $p->id, $players);
$top    = array_find($players, fn(Player $p) => $p->score > 100);  // 8.4
$hasRed = array_any($players, fn(Player $p) => $p->team === Team::Red); // 8.4
$last   = array_last($events);                                       // 8.5

// Pipe operator (8.5)
$slug = $title |> trim(...) |> strtolower(...) |> (fn($s) => str_replace(' ', '-', $s));

// new without parentheses in chains (8.4)
$v = new Version('1.2')->bump();

// Generators for lazy iteration
function lines(string $path): \Generator {
    $h = fopen($path, 'r');
    try { while (($line = fgets($h)) !== false) yield rtrim($line, "\n"); }
    finally { fclose($h); }
}

// Prepared statements always
$stmt = $pdo->prepare('SELECT score FROM players WHERE id = :id');
$stmt->execute(['id' => $id]);
$score = $stmt->fetchColumn();
```

- Lazy objects (8.4): `ReflectionClass::newLazyGhost()` / `newLazyProxy()` — mostly for DI containers and ORMs [1].
- `#[\Override]` (8.3; on properties 8.5), `#[\Deprecated]` (8.4), `#[\NoDiscard]` (8.5) attributes [1][2].
- Use `sprintf`/interpolation `"{$obj->prop}"`; heredoc/nowdoc for templates.

## 7. Top pitfalls and error-message fixes

| Exact error text | Cause | Fix |
|---|---|---|
| `Warning: Undefined variable $x` | Variable not set in this function scope (functions do not see outer variables) | Pass it in, `use ($x)` for closures (arrow `fn` captures automatically), initialise it |
| `Warning: Undefined array key "name"` | Reading a missing key | `$a['name'] ?? 'default'`, `array_key_exists`, validate input |
| `Fatal error: Uncaught TypeError: f(): Argument #1 ($x) must be of type int, string given` | Strict types or non-numeric string | Cast/validate at the boundary (`(int)` after `ctype_digit`, `filter_var`) |
| `Fatal error: Uncaught Error: Call to a member function foo() on null` | Method on null (failed lookup, `find()` returned null) | Check the result; `?->` nullsafe operator only where null is legitimate |
| `Fatal error: Uncaught Error: Class "App\Foo" not found` | PSR-4 path mismatch, missing `use`, or autoload not regenerated | Match namespace to folder, add `use App\Foo;`, run `composer dump-autoload` |
| `Fatal error: Allowed memory size of 134217728 bytes exhausted (tried to allocate N bytes)` | Loading whole result set/file into memory, infinite recursion | Stream with generators/cursors (`chunk`, `lazy()`), fix recursion; raise `memory_limit` only last |
| `Fatal error: Maximum execution time of 30 seconds exceeded` | Long loop, slow external call in a web request | Move work to a queue/CLI worker; add timeouts to HTTP clients |
| `Cannot modify header information - headers already sent by (output started at file.php:1)` | Output (BOM, whitespace before `<?php`, `echo`) before `header()`/`setcookie()` | Remove BOM/trailing `?>` in pure PHP files; send headers first |
| `Fatal error: Uncaught Error: Cannot modify readonly property Player::$score` | Assigning to readonly after init | Return a modified copy (`clone` with, 8.5) or drop readonly |
| `Deprecated: Implicitly marking parameter $x as nullable is deprecated, the explicit nullable type must be used instead` (8.4) | `Foo $x = null` | `?Foo $x = null` |
| `UnhandledMatchError: Unhandled match case 5` | `match` has no arm for the value | Add arm or `default =>` |
| `ValueError: "x" is not a valid backing value for enum Status` | `Status::from()` with unknown value | `Status::tryFrom($v) ?? Status::Default` |
| `Fatal error: Uncaught ArgumentCountError: Too few arguments to function f(), 1 passed and exactly 2 expected` | Missing argument | Pass it or give a default; named args `f(b: 2, a: 1)` |
| `Deprecated: Creation of dynamic property Foo::$bar is deprecated` (8.2) | Assigning undeclared property | Declare the property, or `#[\AllowDynamicProperties]` |
| `Warning: The return value of function f() should either be used or intentionally ignored by casting it as (void)` (8.5) | Ignored result of `#[\NoDiscard]` function [2] | Use the value or `(void) f();` |
| `SQLSTATE[HY093]: Invalid parameter number` | Placeholder/parameter mismatch in PDO | Same names/count; no `:` mismatch |

Other classic mistakes:
- `foreach ($arr as &$v)` leaves `$v` as a reference; a later `foreach ($arr as $v)` overwrites the last element. `unset($v)` after a by-reference loop.
- `strpos($h, $n) == false` is wrong when the match is at index 0; use `str_contains` (8.0) or `=== false`.
- `array_merge` renumbers int keys; `+` keeps left keys. `in_array` is loose unless third arg `true`.
- `empty("0")` is true. `isset($a['k'])` is false when the value is null — use `array_key_exists`.
- Floats: `0.1 + 0.2 != 0.3`; use `bcmath` / `BcMath\Number` (8.4 object API) for money [1].
- Integer division: `7 / 2` is `3.5` (float); use `intdiv(7, 2)` for 3. `%` truncates toward zero (`-7 % 3 === -1`), unlike Luau.
- String concatenation is `.`, not `+` (`"1" + "1"` is `2`).

## 8. Performance

- Enable **OPcache** in production (`opcache.enable=1`, `opcache.validate_timestamps=0` with deploy-time reset, preload for frameworks).
- JIT (`opcache.jit=tracing`, `opcache.jit_buffer_size=64M`) helps CPU-bound code (math, image work) much more than typical I/O-bound web apps.
- Long-running workers (FrankenPHP worker mode, RoadRunner, Swoole, Laravel Octane) remove per-request boot cost (often 2-5x throughput for frameworks) but require stateless services.
- Avoid N+1 queries (Eloquent `with()`), use generators for large data, `SplFixedArray`/packed arrays for numeric lists, string building with arrays + `implode`.
- Profilers: Xdebug profiler, **Blackfire**, **SPX**, Tideways; benchmarking with **PHPBench**.
- 8.5 persistent cURL share handles reuse DNS/connections across requests [2].

## 9. Security

- **SQL injection**: always PDO/mysqli prepared statements; never interpolate. Set `PDO::ATTR_EMULATE_PREPARES => false` and `ERRMODE_EXCEPTION`.
- **XSS**: escape on output with `htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')` or a templating engine with auto-escaping (Twig, Blade `{{ }}`; `{!! !!}` is raw).
- **Passwords**: `password_hash($pw, PASSWORD_DEFAULT)` / `password_verify` / `password_needs_rehash`. Never md5/sha1.
- **Randomness**: `random_bytes`, `random_int`, `Random\Randomizer` (8.2); never `rand()`/`mt_rand()` for tokens.
- **Deserialization**: never `unserialize()` untrusted input (POP-chain RCE); use `json_decode(..., flags: JSON_THROW_ON_ERROR)`. `__sleep/__wakeup` soft-deprecated in 8.5 in favour of `__serialize/__unserialize` [2].
- **File inclusion**: never `include $_GET['page']`; allowlist.
- **Command execution**: `escapeshellarg`, or better `proc_open` with an argument array (7.4+) or Symfony Process. Backtick operator deprecated in 8.5 [2].
- **Comparison bugs**: `==` with hashes (`"0e123" == "0e456"` is true — "magic hashes"); use `hash_equals` for secrets.
- **Sessions/CSRF**: `session_regenerate_id(true)` on login, `SameSite` cookies (8.5 adds `partitioned` cookie option [2]), framework CSRF tokens.
- Keep `display_errors=Off` in production; `composer audit` in CI.

## 10. Game-dev usage

- PHP is not used for engines or clients. Real-world use: **backends** for browser and mobile games (account systems, leaderboards, shops, matchmaking lobbies via Laravel/Symfony), admin dashboards, payment webhooks, Discord bots, and classic browser MMOs/text RPGs (many 2000s web games were PHP+MySQL).
- Real-time: Laravel Reverb / Ratchet / Swoole WebSockets for lobby chat and turn-based games; for fast-twitch action use a dedicated server (Node, Go, C#, Elixir) and keep PHP for HTTP APIs.
- Pattern for a Roblox/Unity game backend: signed requests (HMAC with `hash_hmac` + `hash_equals`), idempotency keys for purchases, rate limiting, prepared statements, JSON APIs.

## 11. Cheat sheet vs Luau

| Concept | Luau | PHP |
|---|---|---|
| Indexing base | 1 | 0 for lists (`$a[0]`); arrays are ordered maps |
| Length | `#t` | `count($a)`, `strlen($s)` (bytes), `mb_strlen` (chars) |
| Absent value | `nil` | `null` |
| Truthiness | only `nil`/`false` falsy | falsy: `false`, `null`, `0`, `0.0`, `""`, `"0"`, `[]` |
| Equality | `==` (no coercion between types) | `===` strict; `==` loose (avoid) |
| Not equal | `~=` | `!==` (strict), `!=` |
| String concat | `a .. b` | `$a . $b`, `"{$a}{$b}"` |
| Variables | `local x = 1` | `$x = 1;` (function scope, no `local`) |
| Array | `{1, 2, 3}` | `[1, 2, 3]` |
| Map | `{a = 1}` | `['a' => 1]` |
| Iterate | `for i, v in ipairs(t)` | `foreach ($a as $i => $v)` |
| Append | `table.insert(t, v)` | `$a[] = $v;` |
| Methods / self | `obj:method()` with `self` | `$obj->method()`, `$this` inside; statics `Cls::m()` |
| Classes | metatables | `class Foo extends Base implements I` |
| Closures | `function() return x end` captures | `function () use ($x) { }` (by value) or `fn() => $x` (auto capture) |
| Coroutines | `coroutine.create/resume/yield` | `Fiber` (`start/resume/Fiber::suspend`), generators `yield` |
| Async | `task.spawn/wait` | AMPHP/ReactPHP on Fibers; normally none (per request) |
| Integer division | `7 // 2` -> 3 | `intdiv(7, 2)` -> 3; `7 / 2` -> 3.5 |
| Modulo sign | floored (`-7 % 3 == 2`) | truncated (`-7 % 3 === -1`); `fmod` for floats |
| Error raise | `error("msg")` | `throw new \RuntimeException("msg");` |
| Error catch | `pcall(f)` | `try { } catch (\Throwable $e) { } finally { }` |
| Modules | `require(module)` | namespaces + Composer PSR-4 autoload; `require_once` legacy |
| Pattern / switch | `if/elseif` | `match (true) { ... }`, `switch` (loose) |
| Nil-safe access | `x and x.y` | `$x?->y`, `$a['k'] ?? $default` |

## 12. Recent changes and version notes

- **PHP 8.5 (2025-11-20)** [2]: URI extension (`Uri\Rfc3986\Uri`, WHATWG URL), pipe operator `|>`, `clone($obj, [...])`, `#[\NoDiscard]` + `(void)` cast, closures and first-class callables in constant expressions, persistent cURL share handles, `array_first()`/`array_last()`, fatal error backtraces, `#[\Override]` on properties, final promoted properties, `Closure::getCurrent()`. Deprecations: backtick operator, non-canonical casts `(integer)`/`(boolean)`/`(double)`/`(binary)`, `case ...;` with semicolon, null as array offset, `__sleep/__wakeup` (soft); warnings for casting NAN and out-of-range floats to int, destructuring non-arrays.
- **PHP 8.4 (2024-11-21)** [1]: property hooks, asymmetric visibility, `#[\Deprecated]`, new `Dom\HTMLDocument` HTML5 API, `BcMath\Number` object API with operators, `array_find`/`array_find_key`/`array_any`/`array_all`, PDO driver subclasses (`PDO::connect()`), `new Foo()->bar()` without wrapping parentheses, lazy objects, IR-based JIT, `mb_trim`/`mb_ucfirst`, `RoundingMode` enum. Deprecated: implicitly nullable params, `E_STRICT`, `trigger_error(E_USER_ERROR)`; IMAP/OCI8/pspell moved to PECL.
- **PHP 8.6** (GA scheduled 2026-11-19, unverified): partial function application `f(?, 2, ...)` reported accepted; other items such as `clamp()` reported by secondary sources only [11].
- Support: each version gets 2 years active + 2 years security support (policy extended in 2024). PHP 8.1 security support ended 2025-12-31; check php.net/supported-versions.

## Sources

1. https://www.php.net/releases/8.4/en.php
2. https://www.php.net/releases/8.5/en.php
3. https://www.php.net/manual/en/migration84.php
4. https://www.php.net/manual/en/migration85.php
5. https://www.php.net/manual/en/language.types.declarations.php
6. https://www.php.net/manual/en/language.fibers.php
7. https://www.php.net/supported-versions.php
8. https://frankenphp.dev/docs/
9. https://getcomposer.org/doc/
10. https://phpstan.org/user-guide/getting-started
11. https://wiki.php.net/rfc/partial_function_application_v2 (PHP 8.6 status from secondary coverage, unverified)
12. https://www.php.net/manual/en/pdo.prepared-statements.php
13. https://www.php.net/manual/en/function.password-hash.php
14. https://docs.phpunit.de/
15. https://cheatsheetseries.owasp.org/cheatsheets/PHP_Configuration_Cheat_Sheet.html
16. https://www.php.net/manual/en/language.oop5.property-hooks.php
