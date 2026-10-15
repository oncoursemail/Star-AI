# JavaScript and TypeScript for STAR (research, checked 2026-10-13)

Status, verified on official pages:
- **ECMAScript:** ES2025 is the 16th edition. ES2026 was approved by the Ecma General Assembly in June 2026, and TC39's finished-proposals list assigns 8 proposals to 2026 [1][2].
- **Temporal and `using`:** both are Stage 4 but slated for **ES2027** [2].
- **TypeScript:** **7.0 GA on 2026-07-08**. It is the Go-native compiler and still ships as `tsc` in the `typescript` package. 6.0 (2026-03-23) was the last JavaScript-based compiler [3][4].
- **Node.js:** Node **24 "Krypton" is LTS** (v24.21.0), Node **26 is Current** (v26.11.1) and is due to enter LTS in late October 2026, and Node 22 is in maintenance LTS [5].
- **Deno and Bun:** Deno 2.7.x (2.7.12 seen, April 2026) and Bun 1.3.x (1.3.14 seen, May 2026) [12][13].

Unverified as of 2026-10-13: whether newer Deno or Bun minors have shipped since those dates.

## 1. Mental model

- JavaScript is a single-threaded, event-loop-driven, prototype-based, dynamically typed language. Functions are first-class closures. Objects are mutable hash maps with a prototype chain (`obj.__proto__`), and `class` is syntax over prototypes.
- **Run to completion:** one task runs until it returns to the event loop. Nothing preempts it. A long loop freezes the page or server.
- **Two module systems:** ES modules (ESM: `import`/`export`, static, async-loaded, strict mode, top-level `await`) and CommonJS (CJS: `require`/`module.exports`, synchronous, Node only). ESM is the standard. In Node, a file is ESM when it ends in `.mjs`/`.mts`, or ends in `.js` with `"type": "module"` in the nearest `package.json` [6].
- **TypeScript** is JavaScript plus a static type layer that is erased at compile time. Types do not exist at runtime: no runtime checks, no reflection, and no overloading by type. Runtime validation needs code (Zod, Valibot, ArkType, or hand-written guards).
- **Hosts differ:** browsers give the DOM, `window`, and `fetch`. Node, Deno and Bun give file, network and process APIs. All three now implement web-standard APIs (`fetch`, `URL`, `Request`/`Response`, `WebSocket`, `structuredClone`, Web Streams, `AbortController`), so prefer those for portable code.

## 2. Type system

### JavaScript values

There are 7 primitives (`undefined`, `null`, `boolean`, `number` (an IEEE double), `bigint`, `string` (UTF-16), `symbol`) plus objects. `typeof null === "object"` is a historical bug. Equality: `===` is strict, while `==` coerces (`0 == ""` is true), so always use `===`. `NaN !== NaN`, so use `Number.isNaN`. Integer-safe range is ±(2^53 - 1) (`Number.MAX_SAFE_INTEGER`). Use `bigint` (`123n`) beyond that.

### TypeScript essentials

```ts
// Structural typing: shape matters, not the declared name
interface Vec2 { x: number; y: number }
type Team = "red" | "blue";                       // string literal union (prefer it over enum)

type Msg =                                        // discriminated union
  | { kind: "move"; x: number; y: number }
  | { kind: "chat"; text: string };

function handle(m: Msg): string {
  switch (m.kind) {
    case "move": return `move ${m.x},${m.y}`;
    case "chat": return m.text;
    default: { const never: never = m; return never; }   // exhaustiveness check
  }
}

function first<T>(xs: readonly T[]): T | undefined { return xs[0]; }

const config = { tickRate: 60, teams: ["red", "blue"] } as const satisfies {
  tickRate: number; teams: readonly Team[];
};                                                // satisfies checks without widening

function isVec2(v: unknown): v is Vec2 {         // user-defined type guard
  return typeof v === "object" && v !== null && "x" in v && "y" in v;
}

type Readonlyify<T> = { readonly [K in keyof T]: T[K] };      // mapped type
type ElementOf<T> = T extends readonly (infer E)[] ? E : never; // conditional + infer
```

- `unknown` is the safe "any" (you must narrow it before use). `any` disables checking and spreads. `never` is the empty type.
- **Strictness flags.** `strict` turns on `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes` and others. It is the default in TS 7 [4]. Also enable `noUncheckedIndexedAccess` (`arr[i]` becomes `T | undefined`, much like Luau table indexing), `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, and `verbatimModuleSyntax` (forces `import type` for types).
- **`erasableSyntaxOnly` (TS 5.8):** errors on TS syntax that emits runtime code: `enum`, value-bearing `namespace`, parameter properties (`constructor(private x: number)`), and `import x = require()`. Turn it on for code run through Node, Deno or Bun type stripping [6][7].
- **`isolatedDeclarations` (TS 5.5):** requires explicit return types on exports so other tools can generate `.d.ts` files without type inference. Use it in libraries that need fast parallel builds.
- **`isolatedModules`:** each file must be transpilable on its own (required by esbuild, swc and Babel).
- **Enums:** prefer `as const` objects plus a union type. Enums are not erasable and numeric enums are unsound in reverse mapping.
- **TS 7 defaults changed** [4]: `strict: true`, `module: esnext`, `target` = the ES version just before `esnext`, `noUncheckedSideEffectImports: true`, `types: []` (globals from `@types/*` are no longer auto-included, so list `"types": ["node"]` or use `["*"]`), and `rootDir: "./"`. **Removed:** `target: es5`, `downlevelIteration`, `moduleResolution: node`/`node10`/`classic`, `module: amd`/`umd`/`systemjs`/`none`, `baseUrl` (make `paths` relative to the project), `esModuleInterop: false`, `allowSyntheticDefaultImports: false`, `alwaysStrict: false`, the `module Foo {}` namespace keyword, and `asserts` on imports (use `with { type: "json" }`).

## 3. Runtime, concurrency and async model

**Event loop.** It takes one macrotask (timer, I/O callback, message), then drains **all microtasks** (promise reactions, `queueMicrotask`), and in browsers then renders. `await x` splits the async function, and the rest runs as a microtask. Node adds `process.nextTick`, which runs before promise microtasks.

```js
console.log("A");
setTimeout(() => console.log("timeout"), 0);
Promise.resolve().then(() => console.log("micro"));
console.log("B");
// A, B, micro, timeout
```

**Promises and async/await:**

```ts
async function loadAll(ids: string[], signal?: AbortSignal) {
  // parallel; one rejection rejects the whole thing
  const results = await Promise.all(ids.map(id => fetch(`/api/item/${id}`, { signal }).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status} for ${id}`);
    return r.json();
  })));
  return results;
}
// Promise.allSettled for partial failure, Promise.any for the first success, Promise.race for timeouts
const ctrl = new AbortController();
setTimeout(() => ctrl.abort(), 5000);       // or AbortSignal.timeout(5000)
```

- Always `await` or `return` promises. A floating promise loses its errors, and Node exits on an unhandled rejection (default `--unhandled-rejections=throw`).
- `forEach` does not await `async` callbacks. Use `for...of` with `await` (sequential) or `Promise.all(map)` (parallel).
- `Array.fromAsync(asyncIterable)` (ES2026) collects async iterables [2].
- **Parallelism:** Web Workers (browser), `worker_threads` (Node), `Worker` (Deno, Bun). They share memory only through `SharedArrayBuffer` plus `Atomics`. Everything else is copied by structured clone.
- **Generators** (`function*`, `yield`) are the closest analogue to Luau coroutines, and async generators (`async function*`) stream data. Iterator helpers (ES2025: `iter.map().filter().take()`) work lazily on any iterator [1].

**Runtimes compared:**

| | Node 24/26 | Deno 2.x | Bun 1.3 |
|---|---|---|---|
| Engine | V8 | V8 | JavaScriptCore |
| TypeScript | strips types natively (stable since 24.12/25.2), no type check, ignores tsconfig [6] | runs TS natively and type-checks with `deno check` (Deno 2.6 can use tsgo) [12] | transpiles TS natively, no type check |
| Package manager | npm, pnpm, Yarn | `deno add npm:pkg` / `jsr:`, reads `package.json` | `bun install` (fast, `bun.lock` text lockfile) |
| Security model | full access by default; experimental `--permission` model | **deny by default**: `--allow-net`, `--allow-read` and others | full access |
| Test runner | `node --test` (`node:test`) | `deno test` | `bun test` (Jest-compatible) |
| Notes | `node --watch`, `--env-file=.env`, built-in `node:sqlite`, `--run` for scripts | `deno fmt`, `deno lint`, `deno compile` single binaries, `dx` (npx-like) | `Bun.serve`, `bun:sqlite`, bundler, `bun build --compile` |

**Node ESM/CJS interop:**
- `import cjs from "./x.cjs"` gives `module.exports` as the default export.
- **`require(esm)` is enabled by default** (unflagged in 22.12/23, marked stable in 25.4 and backported to 24.15 per release notes [6][8]). It works only if the ES module graph has **no top-level `await`**. Otherwise it fails with `ERR_REQUIRE_ASYNC_MODULE`. It returns the module namespace object, or the `"module.exports"` named export if the module provides one.
- **Node 26 removed the extensionless-CJS exception for `"type": "module"` packages.** Such files now need `.cjs`/`.mjs` [8].
- ESM in Node requires **full relative specifiers with extensions** (`import "./util.js"`). For Node type stripping, write `./util.ts` (and set `allowImportingTsExtensions` + `rewriteRelativeImportExtensions` in tsconfig if you also emit JS).
- ESM has no `__dirname`. Use `import.meta.dirname` / `import.meta.filename` (Node 20.11+) or `fileURLToPath(import.meta.url)`.

**Node type stripping details** [6]: the following raise `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX`: enums, namespaces with runtime code, parameter properties, import aliases, and decorators (still Stage 3). `tsconfig` `paths` are not honoured. `--experimental-transform-types` was **removed in Node 26**. Type-only imports must use `import type`. Disable stripping with `--no-strip-types`.

## 4. Tooling and package management

| Need | Default choice in 2026 |
|---|---|
| Package manager | npm (bundled), **pnpm** (strict, disk-efficient, workspaces), Yarn 4, `bun install`; Deno uses `npm:`/`jsr:` specifiers |
| Type check | `tsc --noEmit` (TS 7: about 10x faster; `tsgo` was the preview name, now nightly builds are `typescript@next`) [3][4] |
| Tools that need the compiler API on TS 7 | TS 7.0 has **no programmatic API** (planned for 7.1). typescript-eslint, Vue/Svelte/Astro/MDX tooling need TS 6. Alias it: `"typescript": "npm:@typescript/typescript6@^6.0.2"` and `"@typescript/native": "npm:typescript@^7.0.2"` [4] |
| Lint | ESLint 9+ flat config (`eslint.config.js`) + typescript-eslint; or **Biome** (Rust lint + format); or **oxlint** (Rust) |
| Format | Prettier or Biome |
| Bundle | **Vite** (dev server, Rollup/Rolldown for builds), esbuild, Rspack, `bun build` |
| Run TS directly | Node (strip types), `tsx`, Deno, Bun |
| Monorepo | pnpm workspaces, Turborepo, Nx |
| Package registries | npm registry; **JSR** (TS-first, publishes source, works with Deno/Node/Bun) |

Minimal Node + TS 7 `tsconfig.json` for a type-stripped project:

```jsonc
{
  "compilerOptions": {
    "target": "es2024",
    "module": "nodenext",
    "noEmit": true,
    "erasableSyntaxOnly": true,
    "verbatimModuleSyntax": true,
    "allowImportingTsExtensions": true,
    "noUncheckedIndexedAccess": true,
    "types": ["node"],
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

`package.json` essentials: `"type": "module"`, an `"exports"` map (it controls what consumers can import; with an exports map, deep imports not listed are blocked), `"engines": {"node": ">=22"}`, and `"packageManager"` (Corepack). Commit the lockfile and run `npm ci` in CI.

## 5. Testing

- **Vitest** (Vite-native, Jest-compatible API, fast, TS out of the box) is the default for front-end and many Node projects. **Jest** is still common but needs a transform for ESM/TS.
- Built-in runners: `node --test` (`import { test } from "node:test"; import assert from "node:assert/strict"`), `deno test`, `bun test`.
- Browser/E2E: **Playwright** (`@playwright/test`), Cypress. Component tests: Testing Library.
- Type tests: `expectTypeOf` (Vitest), `tsd`, or `// @ts-expect-error` lines.

```ts
import { describe, it, expect, vi } from "vitest";
import { damage } from "./combat.ts";

describe("damage", () => {
  it.each([[10, 0, 10], [10, 5, 5], [3, 9, 1]])("atk %i arm %i -> %i", (a, r, want) => {
    expect(damage(a, r)).toBe(want);
  });
  it("rejects negative attack", () => {
    expect(() => damage(-1, 0)).toThrow(/attack/);
  });
  it("debounces", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    // ...
    vi.advanceTimersByTime(300);
    expect(fn).toHaveBeenCalledOnce();
  });
});
```

## 6. Idiomatic patterns

```ts
// const by default, let when reassigned, never var
const players = new Map<string, Player>();          // Map for dynamic keys, not plain objects
const seen = new Set<string>();

// Optional chaining and nullish coalescing (?? keeps 0 and "")
const hp = player?.stats?.hp ?? 100;

// Destructuring and spread (shallow copies)
const { name, team = "red", ...rest } = input;
const next = { ...state, score: state.score + 1 };
const copy = structuredClone(state);                 // deep copy

// Immutable array methods (ES2023)
const sorted = scores.toSorted((a, b) => b - a);     // sort() mutates and sorts as strings by default
const groups = Object.groupBy(players, p => p.team); // ES2024; Map.groupBy for Map

// Set methods (ES2025)
const both = setA.intersection(setB);

// Upsert (ES2026): Map.prototype.getOrInsert / getOrInsertComputed
const list = byTeam.getOrInsertComputed(team, () => []);

// Errors: throw Error objects; use cause
try { await save(data); }
catch (err) {
  if (Error.isError(err)) throw new Error("save failed", { cause: err });   // Error.isError ES2026
  throw err;
}

// Classes with real private fields
class Ticker {
  #handlers = new Set<(dt: number) => void>();
  on(fn: (dt: number) => void) { this.#handlers.add(fn); return () => this.#handlers.delete(fn); }
  tick(dt: number) { for (const fn of this.#handlers) fn(dt); }
}
```

ES2025 additions [1]: iterator helpers, new `Set` methods (`union`, `intersection`, `difference`, `symmetricDifference`, `isSubsetOf`), `Promise.try`, `RegExp` modifiers `(?i:...)`, duplicate named capture groups, JSON modules / import attributes (`import data from "./d.json" with { type: "json" }`), `Float16Array`/`Math.f16round`.

ES2026 additions [2]: `Array.fromAsync`, `Error.isError`, `Math.sumPrecise`, `Uint8Array` `toBase64`/`fromBase64`/`toHex`/`fromHex`, `Iterator.concat`, JSON.parse source text access, `Map`/`WeakMap` `getOrInsert`/`getOrInsertComputed`, and `RegExp.escape`.

ES2027-bound (Stage 4, available in some engines already, so check them before use): **Temporal** (replace `Date`) and **explicit resource management** (`using` / `await using` with `Symbol.dispose`) [2]. TypeScript has supported `using` since 5.2.

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

## 8. Performance

- V8 optimises monomorphic code. Keep object shapes stable: initialise all fields in the constructor, do not add or delete properties later, and do not mix types in one array.
- Avoid allocations in hot loops (per-frame closures and temporary arrays). Pool objects in games. TypedArrays (`Float32Array`) for numeric buffers.
- `Map`/`Set` beat object-as-hashmap for frequent inserts and deletes. Do not `delete obj.prop` in hot code.
- Batch DOM reads and writes (layout thrashing). Use `requestAnimationFrame` for rendering, and move heavy work to Workers. `OffscreenCanvas` for rendering in workers.
- Profile with Chrome DevTools Performance, `node --cpu-prof`, `node --inspect`, and clinic.js. For bundle size, tree-shake ESM, use `import()` code splitting, and check with `vite build --report`/source-map-explorer.
- Bun and Deno have faster start-up for scripts, while Node has the broadest compatibility. Benchmark your own workload.
- WebAssembly for hot numeric kernels (see `webassembly.md`), WebGPU for GPU compute.

## 9. Security

- **XSS:** never put untrusted strings into `innerHTML`, `outerHTML`, `document.write`, `eval`, `new Function`, `setTimeout(string)`. Use `textContent`, framework escaping (React escapes by default; `dangerouslySetInnerHTML` is the escape hatch), DOMPurify for HTML, and the Trusted Types API plus a strict Content Security Policy.
- **Prototype pollution:** merging untrusted JSON into objects (`__proto__`, `constructor.prototype`). Use `Object.create(null)` or `Map`, validate keys, and freeze prototypes in sensitive code.
- **Injection:** parameterised SQL. `child_process.execFile`/`spawn` with argument arrays, never `exec` with interpolated strings.
- **ReDoS:** catastrophic regex backtracking on user input. Keep regexes linear or use the `v`/RE2 options. Use `RegExp.escape` (ES2026) for literal user text inside a regex.
- **Validate at the boundary:** TS types do not validate runtime input, so use a schema validator (Zod, Valibot) for request bodies, `JSON.parse` output and messages from the network.
- **Supply chain:** lockfiles, `npm ci`, `npm audit`/`pnpm audit`, pin and review postinstall scripts (pnpm and Bun do not run dependency lifecycle scripts by default). Prefer Deno's permission flags for untrusted scripts.
- Keep secrets out of client bundles. Anything in front-end code (including `VITE_*` env vars) is public.
- Node: use `crypto.randomUUID()`/`crypto.getRandomValues()`, never `Math.random()`, for tokens. Use `crypto.timingSafeEqual` for comparisons.

## 10. Game-dev usage

- Browser engines and frameworks: **Phaser** (2D), **PixiJS** (2D WebGL/WebGPU renderer), **Three.js** (3D; WebGPURenderer with TSL node materials), **Babylon.js** (full 3D engine, WebGPU), **PlayCanvas** (editor + engine), Excalibur, Kaplay. Physics: Rapier (WASM), cannon-es, matter.js.
- **Roblox-adjacent:** `roblox-ts` compiles TypeScript to Luau. Its idioms differ (0-based arrays become 1-based in the emitted Luau, `undefined` maps to `nil`, and no `null`).
- Multiplayer servers: Node/Bun with WebSocket (`ws`, `uWebSockets.js`), Colyseus, authoritative server loops, and WebTransport for unreliable datagrams.
- Desktop/mobile wrappers: Electron, Tauri (Rust shell + web UI), Capacitor.
- Fixed-timestep loop with `requestAnimationFrame`:

```ts
const STEP = 1000 / 60;
let acc = 0, last = performance.now();
function frame(now: number) {
  acc += Math.min(now - last, 250);     // clamp after tab switch
  last = now;
  while (acc >= STEP) { update(STEP / 1000); acc -= STEP; }
  render(acc / STEP);                   // interpolation alpha
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
```

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

## 12. Recent changes and version notes

- **ES2025** (June 2025): iterator helpers, Set methods, `Promise.try`, JSON modules + import attributes, RegExp modifiers, duplicate named groups, Float16 [1][2].
- **ES2026** (approved June 2026): Upsert, JSON.parse source text access, `Iterator.concat`, Uint8Array base64/hex, `Math.sumPrecise`, `Error.isError`, `Array.fromAsync`, `RegExp.escape` [2].
- **ES2027 (expected):** Temporal, explicit resource management (`using`), iterator chunking, `Iterator.prototype.includes`/`join`, joint iteration, `Atomics.pause` [2].
- **TypeScript 5.5 to 5.9:** inferred type predicates, `isolatedDeclarations` (5.5); `--noCheck`, `--rewriteRelativeImportExtensions` (5.7); `erasableSyntaxOnly`, granular return checks (5.8); `import defer`, `--module node20`, new `tsc --init` defaults (5.9) [7].
- **TypeScript 6.0 (2026-03-23):** the last JS-based compiler, a transition release that deprecates what 7.0 removes. **TypeScript 7.0 (2026-07-08):** the Go-native compiler (Project Corsa, `tsgo` during preview), with shared-memory parallel type checking about 10x faster. Same `tsc` command. New defaults and removals as listed in section 2. No programmatic API until 7.1, and `@typescript/typescript6` provides the 6.0 API and a `tsc6` binary for tools [3][4].
- **Node:** type stripping on by default (22.18/23.6) and stable (24.12/25.2). require(esm) unflagged (22.12) and stable (25.4, backported to 24.15). Node 26 removed `--experimental-transform-types` and the extensionless-CJS exception. **From Node 27 the release cycle is annual** [5][6][8].
- **Deno 2.6** (Dec 2025): `dx`, granular permissions, `deno audit`, tsgo-based type checking. Deno 2.7 line since Feb 2026 [12].
- **Bun 1.3** line: `bun.lock`, built-in SQL/Redis clients, `Bun.WebView`, `Bun.cron`, test sharding and isolation (1.3.12 to 1.3.14) [13].

## Sources

1. ECMAScript 2025 language specification: https://tc39.es/ecma262/2025/
2. TC39 finished proposals (with expected publication year): https://github.com/tc39/proposals/blob/main/finished-proposals.md
3. TypeScript blog (release posts for 6.0, 7.0 RC and 7.0): https://devblogs.microsoft.com/typescript/
4. Announcing TypeScript 7.0: https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/
5. Node.js previous releases and release schedule: https://nodejs.org/en/about/previous-releases
6. Node.js TypeScript (type stripping) documentation: https://nodejs.org/api/typescript.html
7. TypeScript 5.8 release notes (erasableSyntaxOnly): https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-8.html
8. Node.js modules: loading ECMAScript modules using require(): https://nodejs.org/api/modules.html#loading-ecmascript-modules-using-require
9. Node.js ECMAScript modules: https://nodejs.org/api/esm.html
10. Node.js packages (exports, type): https://nodejs.org/api/packages.html
11. TypeScript TSConfig reference: https://www.typescriptlang.org/tsconfig/
12. Deno 2.6 release post: https://deno.com/blog/v2.6
13. Bun blog and release notes: https://bun.com/blog
14. MDN JavaScript event loop: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Event_loop
15. MDN Iterator helpers: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Iterator
16. MDN Temporal: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Temporal
17. Vitest documentation: https://vitest.dev/guide/
18. Node.js test runner: https://nodejs.org/api/test.html
19. OWASP Cross Site Scripting Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
20. OWASP Prototype Pollution Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Prototype_Pollution_Prevention_Cheat_Sheet.html
21. typescript-eslint getting started: https://typescript-eslint.io/getting-started/
22. Three.js documentation: https://threejs.org/docs/
23. Phaser documentation: https://docs.phaser.io/
24. roblox-ts documentation: https://roblox-ts.com/docs/
