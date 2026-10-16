---
name: lang-ruby-php
description: Ruby 3.4/4.0 and PHP 8.4/8.5 coding rules: types, nil/null handling, common error messages and fixes, security defaults, tooling (Bundler, Composer, RSpec, PHPUnit, PHPStan). Use when writing, reviewing or debugging Ruby or PHP code.
---
# Ruby and PHP (Ruby 4.0, PHP 8.4/8.5)
## Ruby
- Current line is Ruby 4.0 (Dec 2025); 3.4 code mostly runs. Only nil and false are falsy (0, "", [] are truthy), like Luau. Arrays are 0-based; a[-1] is the last element.
- `undefined method 'x' for nil` means a value was nil: trace its origin. Use `fetch` for required hash keys, `dig` for nested data, `&.` only where nil is legitimate. JSON parses to string keys unless `symbolize_names: true`.
- Keyword arguments are separate from positional since 3.0: call `m(**opts)`, not `m(opts)`.
- Add `# frozen_string_literal: true`; build mutable strings with `+""` or `String.new`. 3.4 warns when a plain literal is mutated.
- `Array.new(3, [])` and `Hash.new([])` share one object; use the block forms `Array.new(3) { [] }` and `Hash.new { |h, k| h[k] = [] }`.
- `and`/`or` bind looser than `=`; use `&&`/`||`. Integer `/` truncates: `7 / 2 == 3`; use `fdiv` for floats.
- 4.0 changes: Set and Pathname are core; Ractor API is now Ractor::Port, `Ractor#value`, `#join` (`Ractor.yield` and `#take` are gone); `Kernel#open("|cmd")` no longer spawns processes; ostruct, logger, benchmark, irb moved to bundled gems, so under Bundler add them to the Gemfile (3.4 did the same for csv, base64, bigdecimal).
- Threads share one GVL: they help I/O, not CPU. CPU parallelism needs processes or Ractors (experimental). The async gem plus the Fiber scheduler gives non-blocking I/O.
- Turn on YJIT in production (`RUBY_YJIT_ENABLE=1`); ZJIT is experimental in 4.0.
- Run everything through `bundle exec`; RuboCop or Standard for lint; Minitest or RSpec for tests; RBS with Steep, or Sorbet, for optional static types.
- Security: never `eval`, `send`, or `constantize` user input; use the array form `system("cmd", arg)`; never `Marshal.load` or `YAML.unsafe_load` untrusted data; validate whole strings with `\A...\z`, not `^...$`; parameterised ActiveRecord queries only.
## PHP
- Start every file with `declare(strict_types=1);`. Compare with `===`; `==` is loose ("1" == "01" is true). Use `str_contains`, not `strpos(...) == false`.
- Write nullable parameters explicitly: `?Foo $x = null` (the implicit form is deprecated in 8.4).
- Arrays are ordered maps; numeric string keys become ints. `$a['k'] ?? $default` for optional keys; `isset` is false for null values, so use `array_key_exists` when null matters.
- Objects are handles: assignment does not copy, use `clone`. After `foreach ($a as &$v)` call `unset($v)`.
- `7 / 2` is 3.5; use `intdiv`. `%` truncates (`-7 % 3 === -1`), unlike Luau. Concatenate with `.`, not `+`.
- 8.4: property hooks (`public int $n { get => ... }`), asymmetric visibility (`public private(set)`), `array_find`/`array_any`/`array_all`, `new Foo()->bar()` without wrapping parentheses, lazy objects, `#[\Deprecated]`.
- 8.5: pipe operator `$x |> trim(...) |> strtolower(...)`, `clone($obj, ['prop' => $v])` for readonly with-ers, `#[\NoDiscard]` with `(void)` casts, `array_first`/`array_last`, URI extension; backtick shell operator and `(integer)`/`(boolean)` casts deprecated.
- Prefer enums, readonly classes, `match` (strict and exhaustive, throws UnhandledMatchError) over switch.
- Classic request model is shared-nothing: no state survives a request. In worker modes (FrankenPHP, RoadRunner, Swoole, Octane) static and singleton state leaks between requests, so reset it.
- `headers already sent` means output (often a BOM or whitespace) happened first; omit the closing `?>` in pure PHP files.
- Tooling: Composer with PSR-4 autoload (`composer dump-autoload` after mapping changes), PHPStan or Psalm, Rector for upgrades, PHPUnit 12 with attributes or Pest. Enable OPcache in production.
- Security: PDO prepared statements with emulated prepares off; `htmlspecialchars(..., ENT_QUOTES, 'UTF-8')` or auto-escaping templates on output; `password_hash`/`password_verify`; `random_int`/`random_bytes` for tokens; `hash_equals` for secrets; never `unserialize` untrusted input or `include` a user-chosen path.
