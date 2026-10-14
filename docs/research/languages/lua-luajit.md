# Lua 5.4 / 5.5 and LuaJIT 2.1 for STAR (research, checked 2026-10-13)

Status: verified on lua.org on 2026-10-13. **Lua 5.5** was released on 22 Dec 2025 and **5.5.1** (3 Aug 2026) is the current release. **Lua 5.4.9** (25 Aug 2026) is the last 5.4 release, and no further 5.4 releases are planned [1]. **LuaJIT** has no tarball releases. It uses a rolling-release model: v2.1 is the maintained production branch, v2.0 gets bugfixes only, and a new development branch is "TBA" [2]. Defold runs LuaJIT on most platforms and Lua 5.1.4 on HTML5 [11]. LÖVE 11.5 is the latest stable release and 12.0 has not been released [12].
Unverified as of 2026-10-13: an exact date for LÖVE 12.0, and any LuaJIT branch beyond 2.1.

This document covers two languages that STAR users often confuse with Luau:

- **PUC Lua** (reference implementation, "Lua 5.4/5.5"): integers + floats, `//`, native bitwise operators, `goto`, `<const>`/`<close>`, `_ENV`.
- **LuaJIT** (Mike Pall's tracing JIT): Lua **5.1** semantics plus a few 5.2 extensions, `bit` library, the **FFI**, very fast, used by LÖVE, Defold, OpenResty, Neovim.

Luau (Roblox) is derived from Lua 5.1, so it is closest to LuaJIT in core semantics. It has since added many features of its own: types, `continue`, compound assignment, string interpolation, `if` expressions, `//`, and generalized iteration.

---

## 1. Mental model

- Lua is a small embeddable language. The host program (C/C++/game engine) owns the process; Lua code runs inside a `lua_State` and sees only what the host exposes. "What library functions exist" depends on the host. `io`/`os` may be missing in sandboxes, and LÖVE adds `love.*`.
- Everything is built from **tables** (the only data structure: arrays, maps, objects, modules, namespaces), **functions** (first-class closures with upvalues), **metatables** (operator overloading, inheritance, proxies) and **coroutines** (asymmetric, stackful).
- Values: `nil`, `boolean`, `number` (5.3+: subtypes **integer** and **float**), `string` (immutable byte strings, not Unicode-aware), `table`, `function`, `userdata` (full/light), `thread` (coroutine).
- Only `nil` and `false` are falsy. `0` and `""` are truthy.
- Globals live in a table. In 5.2+ every chunk has an upvalue `_ENV`, and a free name `x` means `_ENV.x`. In 5.1/LuaJIT/Luau, globals live in the function environment (`getfenv`/`setfenv`).
- 1-based arrays by convention. The length operator `#t` is only well defined for a **sequence** (no holes).
- Version map (what a coding model most often gets wrong):

| Feature | Lua 5.1 | LuaJIT 2.1 | Lua 5.3 | Lua 5.4 | Lua 5.5 | Luau |
|---|---|---|---|---|---|---|
| integer subtype | no | no (doubles; 64-bit ints only via FFI `LL`/`ULL`) | yes | yes | yes | no (double) |
| `//` floor division | no | no | yes | yes | yes | yes |
| `& \| ~ << >> ~x` operators | no | no (`bit.band` ...) | yes | yes | yes | no (`bit32`) |
| `goto` / `::label::` | no | **yes** (5.2 extension) | yes | yes | yes | no |
| `<const>` / `<close>` | no | no | no | yes | yes | no |
| `global` declarations | no | no | no | no | **yes** (reserved word) | no |
| `_ENV` | no | no | yes | yes | yes | no |
| `setfenv/getfenv` | yes | yes | no | no | no | yes (deprecated, deoptimizes) |
| `continue` | no | no | no | no | no | yes |
| `+=` etc. | no | no | no | no | no | yes |
| string interpolation | no | no | no | no | no | `` `x={x}` `` |
| `utf8` library | no | no | yes | yes | yes | yes |
| `table.move` | no | yes (5.2 ext) | yes | yes | yes | yes |
| `table.unpack` | `unpack` | `unpack` (+ `table.unpack` with 5.2 compat build) | yes | yes | yes | yes (and `unpack`) |
| type annotations | no | no | no | no | no | yes |

## 2. Type system

Lua is dynamically typed with no annotations. `type(v)` returns one of 8 names. `math.type(v)` (5.3+) returns `"integer"`, `"float"` or `nil` (not a number).

**Integer/float subtypes (5.3+)** [1][3]:
- Literals: `3` is an integer, while `3.0` and `1e2` are floats. Integers are 64-bit two's-complement by default and **wrap around** on overflow (`math.maxinteger + 1 == math.mininteger`).
- `/` always yields a float: `4/2 == 2.0`. `//` is floor division. It yields an integer when both operands are integers (`7//2 == 3`, `-7//2 == -4`) and a float otherwise (`7.0//2 == 3.0`).
- `%` is floored modulo: `-7 % 3 == 2`.
- `3 == 3.0` is true, and the two are the same table key (floats with exact integer values are normalized to integer keys).
- `math.tointeger(3.0) == 3`, `math.tointeger(3.5) == nil`. `string.format("%d", 3.5)` errors with "number has no integer representation".
- Bitwise operators convert operands to integers and error if a float has a fractional part.
- `for i = 1, 3 do` with integer bounds loops over integers. If any bound is a float, the loop is a float loop.
- String/number coercion: arithmetic on a numeric string still converts (`"10" + 1 == 11`). In 5.4 this happens through string metamethods and `"10" + 1` returns an integer. Concatenating numbers (`1 .. ""`) yields `"1"`. **Comparison does not coerce**: `1 < "2"` raises an error.

**LuaJIT / Lua 5.1**: every number is an IEEE double. `2^53+1` loses precision. `5 // 2` is a **syntax error**. FFI cdata can hold `int64_t` (`10LL`), and arithmetic on such cdata stays 64-bit.

**Luau** has static type annotations checked by its own analyzer (`--!strict`). No Lua version has them. Tools like LuaLS (`---@param` EmmyLua annotations) and Teal (a typed dialect that compiles to Lua) add checking on top.

## 3. Runtime, concurrency and async model

- Single-threaded per `lua_State`. **Coroutines** are cooperative: `coroutine.create(f)`, `coroutine.resume(co, ...)` → `true, ...` or `false, err`, `coroutine.yield(...)`, `coroutine.status`, `coroutine.wrap` (propagates errors), `coroutine.isyieldable`, `coroutine.running`, `coroutine.close` (5.4: closes pending to-be-closed variables of a suspended/dead coroutine).
- Lua 5.1 cannot yield across a C call boundary (`pcall`, metamethods, iterators implemented in C). LuaJIT allows yield across `pcall` and metamethods. 5.2+ supports it via continuations (`lua_callk`).
- There is no event loop in the language. "Async" is host-provided: LÖVE has a frame loop (`love.update(dt)`), OpenResty has a cosocket-based scheduler, Luvit/luv wrap libuv, Neovim has `vim.loop`/`vim.uv`. Game code often builds a tiny scheduler on coroutines:

```lua
-- minimal wait() scheduler on top of coroutines (works in 5.1/LuaJIT/5.4)
local tasks = {}
local function spawn(fn, ...)
  local co = coroutine.create(fn)
  tasks[#tasks + 1] = { co = co, wake = 0 }
  local ok, err = coroutine.resume(co, ...)
  if not ok then error(err, 0) end
end
local function wait(seconds)
  local co = coroutine.running()
  for _, t in ipairs(tasks) do
    if t.co == co then t.wake = os.clock() + seconds end
  end
  coroutine.yield()
end
local function update()
  local now = os.clock()
  for i = #tasks, 1, -1 do
    local t = tasks[i]
    if coroutine.status(t.co) == "dead" then
      table.remove(tasks, i)
    elseif now >= t.wake then
      local ok, err = coroutine.resume(t.co)
      if not ok then print("task error: " .. tostring(err)) end
    end
  end
end
```

- Lua's own preemptive threads: none. True parallelism needs separate states (LÖVE `love.thread` with Channels, Lanes, effil).
- **Garbage collection**: incremental mark-and-sweep. 5.4 adds a **generational** mode (`collectgarbage("generational")` / `"incremental"`). In 5.5, major collections are done incrementally and GC parameters are set through the new `"param"` option [1][4]. `__gc` finalizers work on tables (5.2+). `__close` (5.4) gives deterministic cleanup.
- Weak tables: `setmetatable(t, {__mode = "k"})` (weak keys), `"v"`, `"kv"`. Ephemeron semantics in 5.2+.

## 4. Tooling and package management

| Need | Tool |
|---|---|
| Interpreter | `lua` (5.4/5.5 from lua.org; build with `make`), `luajit` |
| Packages | **LuaRocks** (`luarocks install busted`, rockspec files; `--lua-version=5.4`; `luarocks init` for per-project trees) [8] |
| Language server | **LuaLS / lua-language-server** (sumneko); `.luarc.json` with `"runtime.version": "Lua 5.4"` or `"LuaJIT"`; EmmyLua annotations `---@class`, `---@param`, `---@return` |
| Linting | **luacheck** (`.luacheckrc`, `std = "lua54"` / `"luajit"` / `"love"`), **selene** (Rust; std libraries incl. `lua51`, `lua52`, `lua53`, `lua54`, `luau`/`roblox`) |
| Formatting | **StyLua** (supports Lua 5.1-5.4, LuaJIT and Luau syntax via `syntax = "Lua54"`/`"LuaJIT"`) |
| Typed dialect | **Teal** (`tl`), compiles to Lua 5.1-5.4 |
| Bundling | `luacc`, `amalg`, LÖVE `.love` zip |
| Debugging | ZeroBrane Studio, `local-lua-debugger-vscode`, `mobdebug`; LuaJIT `-jv` (JIT trace verbose), `-jdump`, `-jp` (profiler) |

Module resolution: `require("a.b")` searches `package.path` (`./?.lua;./?/init.lua;...`) and `package.cpath` for C modules, and caches the result in `package.loaded`. A module returns one value, usually a table:

```lua
-- mymod.lua
local M = {}
local function helper(x) return x * 2 end   -- private
function M.double(x) return helper(x) end
return M
```

## 5. Testing

- **busted** (most common; BDD style: `describe`, `it`, `assert.are.same`, spies/stubs/mocks; `busted --lua=luajit`).
- **luaunit** (xUnit style, single file, good for embedded environments).
- **telescope**, **lust** (tiny), **testy**; Neovim plugins use `plenary.nvim` busted harness.
- Coverage: **luacov** (`busted --coverage`).

```lua
-- spec/inventory_spec.lua
local inv = require("inventory")
describe("inventory", function()
  it("adds stacks", function()
    local bag = inv.new(10)
    bag:add("ore", 3); bag:add("ore", 2)
    assert.are.equal(5, bag:count("ore"))
  end)
  it("rejects negative counts", function()
    local bag = inv.new(10)
    assert.has_error(function() bag:add("ore", -1) end)
  end)
end)
```

## 6. Idiomatic patterns

**Classes with metatables** (works in every Lua):

```lua
local Vec = {}
Vec.__index = Vec

function Vec.new(x, y) return setmetatable({ x = x, y = y }, Vec) end
function Vec.__add(a, b) return Vec.new(a.x + b.x, a.y + b.y) end
function Vec.__eq(a, b) return a.x == b.x and a.y == b.y end
function Vec.__tostring(v) return ("(%g, %g)"):format(v.x, v.y) end
function Vec:len() return math.sqrt(self.x * self.x + self.y * self.y) end

-- inheritance
local Vec3 = setmetatable({}, { __index = Vec })
Vec3.__index = Vec3
function Vec3.new(x, y, z)
  local v = Vec.new(x, y); v.z = z
  return setmetatable(v, Vec3)
end
```

Note that `__index`, `__add` and the other metamethods must live on the **metatable**, not on the instance. Also, `__eq` is consulted only when both operands are tables or both are full userdata.

**To-be-closed variables and constants (5.4+)** [3]:

```lua
local function open_locked(path)
  local f = assert(io.open(path, "rb"))
  return setmetatable({ f = f }, {
    __close = function(self, err) self.f:close() end,
  })
end

do
  local h <close> = open_locked("save.dat")   -- closed at end of block, even on error
  local MAX <const> = 64                       -- compile-time constant; assignment is a compile error
  local data = h.f:read(MAX)
end
```

**Lua 5.5 global declarations** [4]:

```lua
global print, string          -- once any global decl appears, undeclared free names are compile errors
global<const> *               -- all other globals read-only in this scope
local function f() return string.upper("x") end
-- Y = 1  --> compile error: Y is read-only
```

**`goto continue`** (5.2+ and LuaJIT; Luau uses `continue` instead):

```lua
for i, item in ipairs(items) do
  if not item.active then goto continue end
  process(item)
  ::continue::
end
```

**Varargs safely**: `select("#", ...)` counts nils, while `#{...}` does not. `table.pack(...)` (5.2+) returns a table with an `.n` field. In 5.5 a vararg can be named: `function f(...args)`, where `args` is a read-only local holding the vararg table [4].

**String building**: collect pieces in a table and call `table.concat(parts)` once. Repeated `s = s .. x` in a loop is O(n²).

**String patterns** are Lua patterns, not regex: `%d`, `%a`, `%s`, `%w`, `%p`, `-` (lazy `*`), `%b()`, `%f[%w]` frontier. They have no alternation `|` and no `{m,n}`. Escape magic characters `( ) . % + - * ? [ ^ $` with `%`. Use `string.find(s, sub, 1, true)` for a plain find.

**LuaJIT FFI** [6]:

```lua
local ffi = require("ffi")
ffi.cdef[[
typedef struct { float x, y; } vec2;
int printf(const char *fmt, ...);
]]
local v = ffi.new("vec2", 1, 2)          -- zero-initialized C struct, GC-managed
local arr = ffi.new("vec2[?]", 1000)     -- VLA: 0-based indexing!
arr[0].x = 5
ffi.C.printf("%f\n", v.x)
local mt = { __add = function(a, b) return ffi.new("vec2", a.x + b.x, a.y + b.y) end }
local vec2 = ffi.metatype("vec2", mt)    -- methods/operators on a C type
```

FFI arrays are **0-based** and unchecked: writing out of bounds is memory corruption, not an error. `ffi.string(ptr, len)` copies a C buffer into a Lua string. Keep a Lua reference to every buffer whose pointer you pass to C, or the GC can free it.

**bit library (LuaJIT)**: `local bit = require("bit")`, `bit.band(a, b)`, `bit.bor`, `bit.bxor`, `bit.lshift`, `bit.rshift`, `bit.arshift`, `bit.tohex`. All functions operate on 32-bit signed ints, so `bit.tobit(0xffffffff) == -1`.

**Proxy / read-only table**:

```lua
local function readonly(t)
  return setmetatable({}, {
    __index = t,
    __newindex = function() error("attempt to modify read-only table", 2) end,
    __len = function() return #t end,      -- 5.2+: # on proxy; 5.1/LuaJIT ignore __len for tables
    __pairs = function() return next, t, nil end, -- 5.2/5.3; deprecated in 5.4 docs but still honoured
  })
end
```

## 7. Top pitfalls and error-message fixes

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

## 8. Performance

- Cache globals and module functions in locals inside hot code: `local sin, insert = math.sin, table.insert`. Locals are register accesses, while globals are table lookups (and `_ENV` lookups in 5.2+).
- Preallocate with `table.create` (not in PUC Lua; Luau has it) or with constructors `{0,0,0}`. LuaJIT has `require("table.new")(narr, nhash)`. Prefer `t[#t+1] = v` over `table.insert(t, v)` in hot loops.
- Avoid creating closures/tables per frame. Reuse vectors (or FFI structs in LuaJIT).
- LuaJIT specifics [7]: performance comes from **traces**. Keep hot loops type-stable and avoid NYI operations, `pcall` in very hot inner loops (2.0), varargs-heavy code and frequent C API calls (classic `lua_*` API calls break traces; FFI calls are JIT-compiled). `-jv` shows trace aborts. FFI arrays of structs are far faster and smaller than tables of tables.
- PUC 5.4 has no JIT. Generational GC often reduces pause time for games that allocate many short-lived objects. 5.5 adds more compact arrays [1].
- Strings are interned (5.4: short strings ≤40 bytes), so equality comparison is pointer-cheap for short strings and hashing long strings is lazy.
- Profilers: LuaJIT `-jp`, the LÖVE profiler libs, and `debug.sethook`-based samplers (slow).

## 9. Security

- **Sandboxing**: never run untrusted code with the full global table. In 5.2+, use `load(chunk, name, "t", env)`. The `"t"` mode rejects precompiled **bytecode**, which can crash or exploit the VM (bytecode is not verified). In 5.1/LuaJIT, use `loadstring` plus `setfenv(fn, env)`. LuaJIT `load` also accepts a mode argument.
- Whitelist the environment. Do not pass through `os`, `io`, `debug`, `package`, `require`, `load`, `loadstring`, `dofile`, `loadfile`, `collectgarbage`, `string.dump`, `rawset/rawget` (these can bypass proxies), `getmetatable` on strings (shared string metatable), or `ffi` (in LuaJIT, FFI = arbitrary native memory access).
- Bound CPU with `debug.sethook(fn, "", 1e6)` count hooks (not airtight; LuaJIT-compiled traces ignore hooks unless you disable the JIT) and bound memory with a custom `lua_Alloc`.
- `string.rep`/pattern matching can be used for CPU and memory DoS (`string.rep("x", 2^31)`, catastrophic `%b` patterns). Cap the input length.
- `os.execute`/`io.popen` with concatenated strings means shell injection.
- `require` of user-controlled module names leads to path traversal and loading of arbitrary `.so`/`.dll` through `package.cpath`.

## 10. Game-dev usage

- **LÖVE (love2d)**: LuaJIT, callbacks `love.load`, `love.update(dt)`, `love.draw`, `love.keypressed`. 11.5 is stable and 12.0 is not yet released (nightlies exist) [12]. Use `dt` for frame-independent movement.
- **Defold**: LuaJIT on desktop/Android, Lua 5.1.4 on HTML5, and no JIT on iOS/Switch. The Defold manual recommends writing only Lua 5.1 features [11]. Script lifecycle: `init(self)`, `update(self, dt)`, `on_message(self, message_id, message, sender)`, `on_input`, `final`. Addressing uses `msg.post(url, id, data)`. `go.property("speed", 100)` declares an inspector-exposed property.
- **Solar2D (Corona)**: Lua 5.1. **PICO-8**: a Lua dialect with `+=`, `!=` and fixed-point numbers. **Playdate SDK**: Lua 5.4. **Neovim**: LuaJIT (`vim.api`). **World of Warcraft**: Lua 5.1, sandboxed. **Garry's Mod**: LuaJIT (GLua with `continue`, `!=`, C-style comments). **OpenResty/Nginx**: LuaJIT.
- **Porting Luau → Lua**: remove type annotations, `continue` → `goto continue`, `+=` → expanded form, interpolation → `string.format`, `task.wait` → engine scheduler, `if a then b else c` expressions → `(a and b or c)` (pitfall: fails when `b` is false/nil), `bit32` → native operators (5.3+) or `bit` (LuaJIT), and Roblox globals (`game`, `Instance`, `Vector3`) do not exist.

## 11. Cheat sheet vs Luau

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

## 12. Recent changes and version notes

- **Lua 5.5 (Dec 2025; 5.5.1 Aug 2026)** [1][4]:
  - Adds `global` declarations (`global x`, `global<const> *`). `global` is now a reserved word, and `LUA_COMPAT_GLOBAL` restores it as a name.
  - Varargs can be named (`...name`).
  - Arrays are more compact and major GC collections are incremental.
  - The `for` control variable is now read-only. To modify it, copy it into a new local.
  - A chain of `__call` metamethods can have at most 15 objects.
  - A `nil` error object is replaced by a string message.
  - GC parameters are set through the new `"param"` option.
  - C API: `lua_newstate` takes a seed argument, `lua_resetthread` and `lua_setcstacklimit` are deprecated, and `nresults` is capped at 250.
- **Lua 5.4 (2020; 5.4.9 final, Aug 2026)** [1][3]: `<const>`/`<close>`, generational GC, `warn()`, `coroutine.close`, `math.random` using xoshiro256**, string→number coercion moved to string metamethods, and `__lt` is no longer used to emulate `__le`.
- **LuaJIT**: rolling releases on the v2.1 branch (version = commit timestamp). Build from git; distros and engines bundle snapshots. No 3.0 announcement [2]. Supports ARM64 (incl. Apple Silicon) and RISC-V via forks/upstream progress. Note that LuaJIT will **not** add 5.3/5.4 integer semantics.
- **LÖVE** 11.5 stable; 12.0 unreleased [12]. **Defold** keeps LuaJIT/Lua 5.1 [11].

## Sources

1. Lua versions and release dates, https://www.lua.org/versions.html (accessed 2026-10-13)
2. LuaJIT status and rolling releases, https://luajit.org/status.html
3. Lua 5.4 Reference Manual, https://www.lua.org/manual/5.4/manual.html
4. Lua 5.5 Reference Manual (global declarations §3.3.7, varargs §3.4.11, incompatibilities §8), https://www.lua.org/manual/5.5/manual.html
5. LuaJIT extensions (goto, bit, table.new, yield across pcall), https://luajit.org/extensions.html
6. LuaJIT FFI library, https://luajit.org/ext_ffi.html and semantics https://luajit.org/ext_ffi_semantics.html
7. LuaJIT running/JIT options (-jv, -jdump, -jp), https://luajit.org/running.html
8. LuaRocks, https://luarocks.org/ and docs https://github.com/luarocks/luarocks/wiki
9. Luau syntax and differences from Lua, https://luau.org/syntax and https://luau.org/compatibility
10. Programming in Lua (first edition, 5.0 era, free), https://www.lua.org/pil/contents.html
11. Defold Lua manual, https://defold.com/manuals/lua/
12. LÖVE 12.0 wiki status, https://love2d.org/wiki/12.0
13. busted test framework, https://lunarmodules.github.io/busted/
14. lua-language-server, https://luals.github.io/
15. StyLua, https://github.com/JohnnyMorganz/StyLua ; selene https://kampfkarren.github.io/selene/
