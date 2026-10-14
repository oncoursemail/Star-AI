# Ruby and PHP: error messages, fixes, and a Luau cheat sheet

Condensed from docs/research/languages/ruby.md and php.md (checked 2026-10-13).

## Ruby errors

| Error text | Cause | Fix |
|---|---|---|
| `undefined method 'foo' for nil` | Value was nil (missing key, failed find, unset ivar) | Find where nil came from; `fetch`, `dig`, `&.` only where nil is valid |
| `undefined local variable or method 'x'` | `def` opens a new scope; typo | Pass as argument, ivar or constant |
| `wrong number of arguments (given 1, expected 2)` | Arity or keyword/positional confusion | `m(**opts)`; check signature |
| `no implicit conversion of Integer into String` | `"a" + 1` | `"a#{1}"` or `to_s` |
| `can't modify frozen String` (FrozenError) | Mutating a frozen literal or constant | `+""`, `dup`, `String.new` |
| `uninitialized constant Foo` | Missing require or Zeitwerk path mismatch | File path must match constant name |
| `cannot load such file -- csv` | Library became a bundled gem | Add `gem "csv"` (or ostruct, logger, benchmark) |
| `stack level too deep` | Recursion; setter calling itself | Assign `@x` directly; base case |
| `comparison of Integer with nil failed` | nil in sort/max | `compact` or `sort_by { it \|\| 0 }` |
| `key not found: :name` (KeyError) | `fetch` on missing key; string vs symbol keys | Default value; `symbolize_names: true` |
| `no block given (yield)` | yield without a block | `block_given?` or `enum_for` |
| `Ractor::IsolationError` | Ractor touches non-shareable object | `Ractor.make_shareable`, pass data via ports |
| `invalid byte sequence in UTF-8` | Wrong encoding | `scrub`, `encode`, read with `bom\|utf-8` |

## PHP errors

| Error text | Cause | Fix |
|---|---|---|
| `Warning: Undefined variable $x` | No outer scope in functions | Parameter, `use ($x)`, or `fn` arrow |
| `Warning: Undefined array key "k"` | Missing key | `$a['k'] ?? $d` |
| `TypeError: f(): Argument #1 ($x) must be of type int, string given` | Strict types | Validate and cast at boundary |
| `Error: Call to a member function foo() on null` | Method on null | Check result; `?->` |
| `Error: Class "App\Foo" not found` | PSR-4 mismatch or missing `use` | Fix namespace/folder; `composer dump-autoload` |
| `Allowed memory size of N bytes exhausted` | Loading everything into memory | Generators, chunked queries |
| `Maximum execution time of 30 seconds exceeded` | Long work in request | Queue or CLI worker |
| `Cannot modify header information - headers already sent` | Output before header() | Remove BOM/whitespace; drop `?>` |
| `Cannot modify readonly property` | Writing readonly | `clone($o, [...])` (8.5) |
| `Implicitly marking parameter $x as nullable is deprecated` | `Foo $x = null` | `?Foo $x = null` |
| `UnhandledMatchError` | No match arm | Add arm or `default` |
| `"x" is not a valid backing value for enum` | `Enum::from` | `tryFrom` |
| `Creation of dynamic property is deprecated` | Undeclared property | Declare it |
| `The return value of function f() should either be used or intentionally ignored by casting it as (void)` | `#[\NoDiscard]` (8.5) | Use it or `(void) f()` |
| `SQLSTATE[HY093]: Invalid parameter number` | Placeholder mismatch | Match names and counts |

## Luau cheat sheet

| Concept | Luau | Ruby | PHP |
|---|---|---|---|
| Index base | 1 | 0 | 0 (ordered map) |
| Length | `#t` | `a.size` | `count($a)`, `strlen` |
| Null | `nil` | `nil` | `null` |
| Falsy | nil, false | nil, false | false, null, 0, 0.0, "", "0", [] |
| Not equal | `~=` | `!=` | `!==` |
| Concat | `..` | `+`, `"#{x}"` | `.`, `"{$x}"` |
| Map | `{a = 1}` | `{a: 1}` | `['a' => 1]` |
| Method call | `obj:m()` | `obj.m` | `$obj->m()` |
| self | `self` | `self` (implicit), `@ivar` | `$this` |
| Closure | `function() end` | `-> { }`, blocks | `fn() =>`, `function () use ($x)` |
| Coroutine | `coroutine.*` | `Fiber` | `Fiber` |
| Int division | `7 // 2` | `7 / 2` | `intdiv(7, 2)` |
| Modulo of -7 by 3 | 2 | 2 | -1 |
| Raise | `error()` | `raise` | `throw` |
| Catch | `pcall` | `begin/rescue/ensure` | `try/catch/finally` |
| Modules | `require` | `require`, `module` | namespaces + Composer autoload |
