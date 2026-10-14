# Lua and LuaJIT: error messages and the Luau cheat sheet

Condensed from the STAR research notes (docs/research/languages). Error texts are representative; match on meaning.

# Lua 5.4/5.5 and LuaJIT

## Top pitfalls and error-message fixes

| Exact error text (5.4 wording) | Cause | Fix |
|---|---|---|
| `attempt to index a nil value (global 'foo')` | Misspelled global or module not required; 5.4 names the variable | `local foo = require("foo")`; enable luacheck/LuaLS undefined-global checks |
| `attempt to index a nil value (field 'x')` | Intermediate table missing | Guard with `if t.x then`, or initialize `t.x = t.x or {}` |
| `attempt to call a nil value (method 'Foo')` | Method misspelled, or called `obj:Foo` on a table whose metatable `__index` is not set | Set `Class.__index = Class`; check spelling/case |
| `attempt to call a nil value (global 'continue')` / `'=' expected near 'continue'` | Luau syntax pasted into Lua | Use `goto continue` with a `::continue::` label (5.2+/LuaJIT) |
| `syntax error near '+='` / `'=' expected near '+'` | Compound assignment is Luau-only | `x = x + 1` |
| `unexpected symbol near '`'` | Luau string interpolation | `("x=%d"):format(x)` or `"x=" .. x` |
| `unexpected symbol near '//'` (LuaJIT/5.1) | `//` needs Lua 5.3+ | `math.floor(a / b)` |
| `attempt to perform arithmetic on a nil value (local 'n')` | Missing argument or nil field | Validate inputs; default `n = n or 0` |
| `attempt to compare number with nil` / `attempt to compare number with string` | No coercion in comparisons | `tonumber(s)` first; check for nil |
| `attempt to concatenate a nil value (local 'name')` / `... a table value` | `..` only works on strings and numbers | `tostring(x)`; check for nil |
| `bad argument #1 to 'ipairs' (table expected, got nil)` | Iterating a nil | Fix the source; `for _, v in ipairs(t or {}) do` |
| `number has no integer representation` | Float with a fraction passed to an integer-only operation (`%d`, bitwise, `string.rep` count) | `math.floor(x)` or `math.tointeger(x)` |
| `attempt to assign to const variable 'x'` | Writing a `<const>` local (and, in 5.5, a for-loop control variable) | Use a new local: `local i = i` inside the loop |
| `variable 'x' got a non-closable value` | `<close>` value lacks `__close` and is not nil/false | Give the value a metatable with `__close` |
| `stack overflow` | Unbounded recursion or `__index` loop | Use iteration or a proper tail call `return f(x)`; fix the metatable cycle |
| `attempt to yield across a C-call boundary` | Yield inside `pcall`/metamethod/C iterator on 5.1 | Use LuaJIT or 5.2+, or restructure so the yield happens in Lua code |
| `table index is nil` / `table index is NaN` | `t[nil] = v` or `t[0/0] = v` | Validate keys |
| `module 'x' not found:` (followed by the search list) | `package.path` does not cover the file | Fix the path (`?/init.lua`), use luarocks, run from the project root |
| `#t` returns an unexpected number | `t` has holes (nil inside) | Track the count yourself or use `table.pack` with `.n` |
| LuaJIT: `cannot convert 'nil' to 'int'` | Passing nil where FFI expects a C type | Convert explicitly; check the arguments |
| LuaJIT: `NYI: ...` in `-jv` output | Not-yet-implemented bytecode aborts the trace (falls back to the interpreter) | Avoid `pairs`/`next` in hot loops on older 2.0, string patterns in hot paths, `unpack` with many values |

## Cheat sheet vs Luau

| Concept | Luau | Lua 5.4/5.5 | LuaJIT 2.1 |
|---|---|---|---|
| Array indexing base | 1 | 1 | 1 for tables; **0** for FFI arrays |
| Null | `nil` | `nil` | `nil` (FFI `NULL` cdata is not `nil`, though `ptr == nil` is true) |
| Truthiness | only `nil`/`false` falsy | same | same |
| String concat | `..`, `` `{a}{b}` `` | `..` only | `..` only |
| Interpolation | `` `hp={hp}` `` | `("hp=%d"):format(hp)` | same as 5.4 |
| Compound assign | `x += 1` | `x = x + 1` | `x = x + 1` |
| continue | `continue` | `goto continue` + `::continue::` | same as 5.4 |
| Integer division | `//` (float result) | `//` (integer if both ints) | `math.floor(a/b)` |
| Integers | double only | int64 + float subtypes | double; `LL` cdata for int64 |
| Bitwise | `bit32.band(a,b)` | `a & b`, `a \| b`, `~a`, `a << n` | `bit.band(a,b)` |
| Maps / tables | `{}` with `table.create`, `table.find`, `table.clear`, `table.freeze` | `{}`, no `create/find/clear/freeze` | `table.new`, `table.clear` via require |
| Methods / self | `function T:m()` / `obj:m()` | same | same |
| Closures | same | same | same |
| Coroutines | `coroutine.*` + `task.spawn/wait/defer` | `coroutine.*` only; host provides scheduling | `coroutine.*`; yield across pcall OK |
| Error handling | `pcall`, `xpcall`, `error`; `error` tables OK | same; 5.5 turns a nil error object into a string | same |
| Modules | `require(instance)` / string paths (new solver) | `require("a.b")` via `package.path` | same |
| Globals / env | `getfenv/setfenv` (deprecated) | `_ENV` upvalue; 5.5 `global` declarations | `setfenv/getfenv` |
| Constants | none (`table.freeze` for tables) | `local X <const> = 1` | none |
| Deterministic cleanup | none | `local h <close> = ...` | none |
| Types | `--!strict`, annotations | none (LuaLS comments, Teal) | none |
| Generalized iteration | `for k, v in t do` | must use `pairs(t)`/`ipairs(t)` | must use `pairs`/`ipairs` |
| `if` expression | `if c then a else b` | `c and a or b` (pitfall with false `a`) | same |
| Length | `#t` | `#t` (`__len` honoured on tables) | `#t` (`__len` ignored on tables in 5.1 mode) |
| String library | `string.split` exists | no `split`: use `gmatch("[^,]+")` | same |
