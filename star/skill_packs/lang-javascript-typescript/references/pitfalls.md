# JavaScript and TypeScript: errors, fixes and Luau cheat sheet

Condensed from docs/research/languages/javascript-typescript.md (checked 2026-10-13). Bracketed numbers refer to that file's source list.

## 7. Top pitfalls and error-message fixes

| Exact error text (or symptom) | Cause | Fix |
|---|---|---|
| `TypeError: Cannot read properties of undefined (reading 'x')` | Accessing a field of `undefined`/`null` | Find why the value is missing; `obj?.x`, guard, or enable `strictNullChecks`/`noUncheckedIndexedAccess` |
| `TypeError: x is not a function` | Wrong import shape (default vs named), a shadowed name, or a method called on the wrong type | `import { x }` vs `import x`; log `typeof x` |
| `ReferenceError: Cannot access 'x' before initialization` | Temporal dead zone (`let`/`const` used before the declaration line) or a circular ESM import | Reorder, or break the import cycle |
| `SyntaxError: Cannot use import statement outside a module` | ESM syntax in a file Node treats as CJS | `"type": "module"` in package.json or a `.mjs` extension |
| `ReferenceError: require is not defined in ES module scope` | `require` in ESM | `import`, or `createRequire(import.meta.url)` |
| `Error [ERR_REQUIRE_ESM]` / `ERR_REQUIRE_ASYNC_MODULE` | Old Node without require(esm), or the ESM graph uses top-level `await` | Upgrade to Node 22.12+/24, use `await import()`, or remove TLA |
| `Error [ERR_MODULE_NOT_FOUND]: Cannot find module '/app/src/util'` | ESM needs the file extension | `import "./util.js"` (or `.ts` under type stripping) |
| `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX` (Node) | `enum`, runtime `namespace`, parameter properties under type stripping | Use `as const` objects and explicit fields; enable `erasableSyntaxOnly` |
| `TS2307: Cannot find module 'x' or its corresponding type declarations` | Missing `@types/x`, wrong `moduleResolution`, or TS 7 `types: []` default for globals | Install types, use `moduleResolution: nodenext`/`bundler`, set `"types": ["node"]` |
| `TS2532: Object is possibly 'undefined'` / `TS18048` | Strict null checks | Narrow with `if`, `??`, or `!` only when proven |
| `TS2345: Argument of type 'string' is not assignable to parameter of type '"red" \| "blue"'` | Literal widening | `as const`, or annotate the variable with the union |
| `TS7006: Parameter 'x' implicitly has an 'any' type` | `noImplicitAny` | Annotate the parameter |
| `TS5101` / `TS5107` option deprecated or removed (`baseUrl`, `moduleResolution: node`) on TS 6/7 | Options removed in TS 7 | Make `paths` relative, use `nodenext`/`bundler` [4] |
| `[1, 10, 2].sort()` gives `[1, 10, 2]` | Default sort compares strings | `.sort((a, b) => a - b)` or `.toSorted(...)` |
| `this` is `undefined` in a callback | Method passed unbound | Arrow function or `.bind(this)`; class field arrows |
| `0.1 + 0.2 !== 0.3` | IEEE doubles | Compare with epsilon; integers of cents; `Math.sumPrecise` for sums |
| `UnhandledPromiseRejection` / process exits | A promise rejected with no handler | `await` it inside `try`, or `.catch`; never leave floating promises (lint: `no-floating-promises`) |
| `Uncaught RangeError: Maximum call stack size exceeded` | Unbounded recursion, or a setter calling itself | Iterate; fix the accessor |
| CORS: `blocked by CORS policy: No 'Access-Control-Allow-Origin' header` | Browser cross-origin request | The **server** must send CORS headers; proxy in dev |

## 11. Cheat sheet vs Luau

| Concept | Luau | JavaScript / TypeScript |
|---|---|---|
| Indexing | 1-based | 0-based; `arr.at(-1)` for the last element |
| Length | `#t` | `arr.length`, `map.size`, `str.length` (UTF-16 units) |
| Absent value | `nil` | `undefined` (missing) and `null` (explicit); `x == null` matches both; `??` |
| Falsy values | `nil`, `false` | `undefined`, `null`, `false`, `0`, `-0`, `0n`, `NaN`, `""` |
| Equality | `==`, `~=` | `===`, `!==` (never `==`) |
| String concat | `..` | `+` or a template literal `` `hp ${hp}` `` |
| Interpolation | `` `hp {hp}` `` | `` `hp ${hp}` `` (note the `$`) |
| Array | `{1, 2, 3}` | `[1, 2, 3]` |
| Map | table with string keys | `Map` (any key type) or a plain object (string/symbol keys) |
| Missing key | `nil` | `undefined` (no error) |
| Iterate array | `for i, v in ipairs(t)` | `for (const v of arr)`, `arr.forEach((v, i) => ...)`, `arr.entries()` |
| Iterate map | `for k, v in pairs(t)` | `for (const [k, v] of map)`, `Object.entries(obj)` |
| Numeric for | `for i = 1, n do` | `for (let i = 0; i < n; i++)` |
| Integer division | `a // b` | `Math.floor(a / b)` (or `Math.trunc`); `bigint` `/` truncates |
| Numbers | double | double (`number`) plus `bigint` |
| Methods / self | `obj:m()` passes self | `obj.m()` sets `this` dynamically; arrow functions capture lexical `this` |
| Classes | metatables | `class` with `#private` fields, `extends`, `super` |
| Closures | upvalues | closures (`let` in a loop gives a fresh binding per iteration; `var` does not) |
| Coroutines | `coroutine`, `task.spawn`, `task.wait` | generators; `async`/`await` + promises; `await new Promise(r => setTimeout(r, ms))` is the analogue of `task.wait` |
| Errors | `error()`, `pcall` | `throw new Error()`, `try/catch/finally`; promise `.catch` |
| Modules | `require(script.Parent.M)` returns a value | `import { x } from "./m.js"` (ESM), `require` (CJS) |
| Type annotations | `local x: number` | `let x: number` (TS); erased at runtime |
| Optional type | `string?` | `string \| undefined`, optional property `name?: string` |
| Varargs | `...` | rest `...args`, spread `f(...arr)` |
| Ternary | `if c then a else b` | `c ? a : b` |
