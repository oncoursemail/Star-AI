# WebAssembly for STAR (research, checked 2026-10-13)

Status: verified on 2026-10-13: the Wasm 3.0 specification was announced on 2025-09-17 [1]; WASI 0.3.0 was released on 2026-06-11 [3][4]; latest releases on GitHub: Wasmtime v49.0.2 (2026-10-02), Wasmer v7.5.0 (2026-10-01), Emscripten 6.0.12 (2026-10-08), wasm-bindgen 0.2.129 (2026-09-25), jco 1.37.0 (2026-10-06), AssemblyScript 0.28.20 (2026-07-22), Binaryen version_133 (2026-09-21), Luau 0.742 (2026-10-10) [8]. Per-engine feature versions come from the WebAssembly website's `features.json` [2]. Unverified as of 2026-10-13: whether Safari stable has shipped Memory64 and relaxed SIMD (the data says Technology Preview / flag only), and the exact Node.js version where ESM integration of `.wasm` imports leaves its experimental flag.

---

## 1. Mental model

- **Wasm is a portable, sandboxed instruction set, not a language.** You write C, C++, Rust, Zig, Go, C#, Kotlin, Dart, AssemblyScript, etc., and a compiler emits a `.wasm` binary (or `.wat` text). The engine validates the module, compiles it (baseline then optimizing tiers), and runs it at near-native speed.
- **A stack machine with structured control flow.** Instructions push and pop typed values (`i32`, `i64`, `f32`, `f64`, `v128`, references). Control flow is `block`/`loop`/`if` with branches to labels; there is no arbitrary `goto`, which makes validation single-pass and fast.
- **Module vs instance.** A module is stateless compiled code with declared **imports** and **exports**. Instantiating it with an import object produces an instance with its own memories, tables and globals. The host (browser JS, Wasmtime, Node) supplies every capability through imports: Wasm can do nothing on its own (no I/O, no clock, no DOM) [5].
- **Linear memory is one big `ArrayBuffer`.** Classic Wasm (C/C++/Rust) gets a resizable byte array (64 KiB pages). Pointers are integer offsets into it. Out-of-bounds access **traps** (cannot escape the sandbox), but nothing stops a buggy program from corrupting its *own* memory (buffer overflows inside the sandbox are still possible).
- **Two worlds since Wasm 3.0.** (1) Linear-memory languages manage their own heap. (2) **WasmGC** languages (Kotlin, Dart, Java via J2Wasm, OCaml, Scheme, Scala) allocate `struct` and `array` objects on the engine's garbage-collected heap, so they ship no GC of their own and interoperate with JS objects through references [1].
- **Browser: Wasm is a guest of JavaScript.** JS loads, instantiates and calls it; Wasm calls back through imported JS functions. Crossing the boundary has a cost; strings and objects need glue (wasm-bindgen, Emscripten's embind, or JS string builtins).
- **Outside the browser: WASI + the Component Model.** WASI defines standard interfaces (files, clocks, random, sockets, HTTP) as WIT (Wasm Interface Type) packages; components are typed, composable modules that talk through high-level types (strings, records, lists, resources) via the Canonical ABI [3][6].

## 2. Type system

### 2.1 Core value types
`i32`, `i64`, `f32`, `f64` (IEEE 754), `v128` (SIMD), and reference types `funcref`, `externref` (an opaque host value, for example a JS object). Integers have no sign; operations decide (`i32.div_s` vs `i32.div_u`, `i32.lt_s` vs `lt_u`).

### 2.2 Wasm 3.0 additions [1]
- **Typed function references**: `(ref $sig)` and `(ref null $sig)`, `call_ref` for safe indirect calls without a table lookup.
- **GC types**: `(struct (field $x (mut f64)))`, `(array (mut i8))`, `i31ref` (unboxed 31-bit integers), subtyping with `sub`/`final`, recursive type groups `rec`. Casts (`ref.cast`, `br_on_cast`) are checked at run time.
- **Memory64**: memories and tables indexed by `i64`; address space beyond 4 GiB (browsers cap 64-bit memories at 16 GiB [1]).
- **Multiple memories**: a module can define/import several memories (for example an isolated scratch memory).
- **Exception handling with `exnref`**: tags with payloads, `throw`, `throw_ref`, `try_table` with `catch`/`catch_ref`/`catch_all`. The older (legacy, Phase 3) `try`/`catch`/`delegate` encoding shipped in browsers since 2021-2022; the final `exnref` form ships in Chrome 137, Firefox 131, Safari 18.4, Wasmtime 47, Node 24.15 [2].
- **Tail calls**: `return_call`, `return_call_indirect`, `return_call_ref`.
- **Relaxed SIMD**: faster SIMD ops whose edge cases may differ between hardware (`f32x4.relaxed_madd`, `i8x16.relaxed_swizzle`). A **deterministic profile** fixes NaN bits and relaxed results for platforms that need reproducibility (blockchains, lockstep games).
- **JS string builtins** (JS API, not core): imported `wasm:js-string` functions operate directly on JS strings held as `externref`, avoiding copies into linear memory.

### 2.3 Component Model types (WIT)
WIT is an IDL. Types: `bool`, `s8..s64`, `u8..u64`, `f32`, `f64`, `char`, `string`, `list<T>`, `option<T>`, `result<T, E>`, `tuple<...>`, `record`, `variant`, `enum`, `flags`, `resource` (handles with methods and destructors), and since WASI 0.3 `stream<T>`, `future<T>` and `async func` [3][6].

```wit
package game:scoring@0.1.0;

interface scoring {
  record hit { player: string, damage: u32, headshot: bool }
  score: func(hits: list<hit>) -> result<u64, string>;
}

world scorer {
  export scoring;
}
```

## 3. Runtime, concurrency and async model

### 3.1 Browser instantiation
```js
// Preferred: streaming compile while the bytes download (requires Content-Type: application/wasm)
const { instance } = await WebAssembly.instantiateStreaming(fetch("/game.wasm"), {
  env: { log_i32: (x) => console.log(x), now_ms: () => performance.now() },
});
instance.exports.update(16.6);
const mem = new Uint8Array(instance.exports.memory.buffer); // re-create views after memory.grow!
```
`WebAssembly.compileStreaming` + `WebAssembly.instantiate(module, imports)` lets you cache/compile once and instantiate many times (workers).

### 3.2 Threads
Wasm threads = **shared memory** (`(memory 1 100 shared)`, backed by `SharedArrayBuffer`) + **atomics** (`i32.atomic.rmw.add`, `memory.atomic.wait32`, `memory.atomic.notify`) + **Web Workers** (each worker instantiates the same module with the same shared memory). Emscripten's `-pthread` builds this for you. In browsers, `SharedArrayBuffer` is only available when the page is **cross-origin isolated** [7]:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp      (or: credentialless)
```
Check at run time with `self.crossOriginIsolated`. All cross-origin subresources (CDN scripts, images, ads, iframes) must then send CORP/CORS headers or be loaded with `credentialless`; this is why many web game portals cannot host threaded builds, and why engines offer single-threaded web exports. The main thread cannot `Atomics.wait` (blocking it would freeze the page); Emscripten busy-waits or proxies to workers.

### 3.3 Async: JSPI and the asyncify problem
Wasm code is synchronous; browser APIs (fetch, WebGPU map, IndexedDB) are async. Options:
- **JSPI (JavaScript Promise Integration)**: wrap an import with `new WebAssembly.Suspending(asyncFn)` and an export with `WebAssembly.promising(fn)`; the Wasm stack suspends while the promise is pending. Ships in Chrome 137, Firefox 153, Safari 27, Node 26 per `features.json` [2].
- **Asyncify** (Binaryen pass, Emscripten `-sASYNCIFY`): rewrites code to unwind/rewind the stack; works everywhere but grows code size and slows hot code.
- **Restructure**: run the main loop as a callback (`emscripten_set_main_loop`, `requestAnimationFrame`) and never block.

### 3.4 WASI 0.3 async
WASI 0.2 (Preview 2, January 2024) used `wasi:io` pollables and streams. WASI 0.3 (released 2026-06-11) moves async into the Component Model's Canonical ABI: `async func`, `stream<T>`, `future<T>`; `wasi:io` is gone and interfaces like `wasi:http` become simpler [3][4]. Wasmtime enables component-model async by default from version 46 (support existed behind a flag earlier) [3]. Guest toolchain support (Rust `wit-bindgen`, Go, Python, JS via `jco`/ComponentizeJS) is still maturing: the migration guide notes stable Rust's bundled `wasm-component-ld` was too old for some 0.3 outputs at the time of writing [6].

### 3.5 Server and embedded runtimes
- **Wasmtime** (Bytecode Alliance, Cranelift JIT/AOT, reference WASI/component implementation; monthly major versions, v49 in October 2026) [8].
- **Wasmer** (v7.5; multiple backends incl. LLVM, WASIX extensions) [8].
- **WAMR** (WebAssembly Micro Runtime, interpreter/AOT for microcontrollers), **wasm3** (tiny interpreter), **V8/Node/Deno/Bun** (Node exposes `WebAssembly` and `node:wasi`).
- Edge platforms (Fastly Compute, Cloudflare Workers, Fermyon Spin, wasmCloud) run components or modules per request with microsecond cold starts.

## 4. Tooling and package management

| Tool | Use |
|---|---|
| **Emscripten** (`emcc`, 6.0.x) | C/C++ to Wasm + JS glue, SDL2/SDL3, OpenGL ES to WebGL, pthreads, filesystem emulation (MEMFS, IDBFS). 6.0.0 (2026-06-04): native `.exe` launchers on Windows, minimum Chrome 85 / Firefox 79 / Safari 14.1 for generated code, `-m64` aliases `-sMEMORY64`, real dynamic libraries by default for `-shared` [9]. |
| **wasi-sdk** | Clang + wasi-libc for WASI targets without JS glue. |
| **Rust** | Targets `wasm32-unknown-unknown` (browser), `wasm32-wasip1`, `wasm32-wasip2`; `wasm-bindgen` (now in its own `wasm-bindgen` GitHub org after the `rustwasm` org was archived in 2025 [10]), `wasm-pack` (transferred to an individual maintainer), `trunk`, `cargo-component`, `wit-bindgen`. |
| **Binaryen** (`wasm-opt`) | Optimizer: `wasm-opt -O3 --enable-bulk-memory`, Asyncify, minification; most toolchains run it. |
| **WABT** | `wat2wasm`, `wasm2wat`, `wasm-objdump`, `wasm2c`. |
| **wasm-tools** | Component tooling: `wasm-tools component new/wit/validate/print`, `wasm-tools compose`. |
| **jco** | JS toolchain for components: transpile a component to an ES module + core Wasm for browsers/Node; supports WASI 0.3 [3]. |
| **AssemblyScript** | TypeScript-like language compiling straight to Wasm (`asc`); not TypeScript semantics (no `any`, value types `i32`/`f64`). |
| **Go / TinyGo** | `GOOS=wasip1 GOARCH=wasm`, `GOOS=js GOARCH=wasm`; TinyGo for small binaries and components. |
| **.NET** | Blazor WebAssembly, `wasi-experimental` workload. |
| **Kotlin/Wasm, Dart (Flutter web `--wasm`), J2Wasm** | WasmGC targets. |
| **Package registries** | npm (JS glue + `.wasm` asset), crates.io, OCI registries / `wkg` for WIT packages and components (warg registry protocol). |

Debugging: Chrome DevTools with the C/C++ DWARF extension, source maps (`-gsource-map`), `wasm-objdump -x`, `WASMTIME_BACKTRACE_DETAILS=1`, `twiggy` / `wasm-opt --metrics` for size profiling.

## 5. Testing

- **Unit tests in the source language**, compiled natively first (fast), then the same tests compiled to Wasm: `cargo test --target wasm32-wasip2` with Wasmtime as the runner (`CARGO_TARGET_WASM32_WASIP2_RUNNER=wasmtime`), `wasm-pack test --headless --chrome --firefox` for browser crates, Emscripten tests via Node (`node out.js`).
- **Host-side integration tests**: instantiate the module from Vitest/Jest/Node test runner, call exports, assert results; check memory after calls.
- **Spec conformance**: the WebAssembly spec test suite (`.wast` scripts) via `wast` runners (Wasmtime runs them).
- **Fuzzing**: `wasm-smith` generates valid modules; differential fuzzing across engines; `cargo fuzz` on the native build.
- **Determinism tests** for lockstep games: run the same inputs on x86 and ARM engines, compare state hashes; avoid relaxed SIMD or use the deterministic profile; canonicalize NaNs.
- **Size budgets in CI**: fail if `game.wasm` (after `wasm-opt` and Brotli) exceeds a limit.

## 6. Idiomatic patterns (code)

### 6.1 Hand-written WAT (to learn the machine)
```wat
(module
  (memory (export "memory") 1)                     ;; 1 page = 64 KiB
  (func $add (export "add") (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add)
  (func (export "sum") (param $ptr i32) (param $len i32) (result i32)
    (local $i i32) (local $acc i32)
    (block $done
      (loop $next
        (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
        (local.set $acc (i32.add (local.get $acc)
          (i32.load (i32.add (local.get $ptr) (i32.shl (local.get $i) (i32.const 2))))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $next)))
    (local.get $acc)))
```

### 6.2 Rust + wasm-bindgen for the browser
```rust
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub struct World { positions: Vec<f32>, velocities: Vec<f32> }

#[wasm_bindgen]
impl World {
    #[wasm_bindgen(constructor)]
    pub fn new(n: usize) -> World { World { positions: vec![0.0; n * 2], velocities: vec![1.0; n * 2] } }
    pub fn step(&mut self, dt: f32) {
        for (p, v) in self.positions.iter_mut().zip(&self.velocities) { *p += v * dt; }
    }
    /// Zero-copy view for the renderer: pointer + length into linear memory.
    pub fn positions_ptr(&self) -> *const f32 { self.positions.as_ptr() }
    pub fn len(&self) -> usize { self.positions.len() }
}
```
```js
import init, { World } from "./pkg/sim.js";
const wasm = await init();
const world = new World(10_000);
function frame(t) {
  world.step(1 / 60);
  // Re-create the view every frame: memory.grow detaches the old ArrayBuffer.
  const pos = new Float32Array(wasm.memory.buffer, world.positions_ptr(), world.len());
  draw(pos);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
// world.free() when done: wasm-bindgen objects are not collected by JS GC automatically
// (FinalizationRegistry helps, but call free() deterministically).
```
Build: `wasm-pack build --target web --release` (or `cargo build --target wasm32-unknown-unknown` + `wasm-bindgen --target web`).

### 6.3 C++ with Emscripten (game loop)
```cpp
#include <emscripten.h>
#include <emscripten/html5.h>
static void tick() { update(); render(); }
int main() {
  init();
  emscripten_set_main_loop(tick, 0, true);   // 0 = use requestAnimationFrame
}
```
```bash
emcc game.cpp -O3 -sUSE_SDL=2 -sALLOW_MEMORY_GROWTH=1 -sEXPORTED_FUNCTIONS=_main,_set_volume \
  -sEXPORTED_RUNTIME_METHODS=ccall,cwrap --preload-file assets -o index.html
# threads: add -pthread -sPTHREAD_POOL_SIZE=4 and serve with COOP/COEP headers
```

### 6.4 A WASI component (Rust, cargo-component / wit-bindgen)
```rust
wit_bindgen::generate!({ world: "scorer", path: "wit" });
struct Component;
impl exports::game::scoring::scoring::Guest for Component {
    fn score(hits: Vec<exports::game::scoring::scoring::Hit>) -> Result<u64, String> {
        hits.iter().try_fold(0u64, |acc, h| {
            let d = if h.headshot { h.damage as u64 * 2 } else { h.damage as u64 };
            acc.checked_add(d).ok_or_else(|| "overflow".to_string())
        })
    }
}
export!(Component);
```
Run or host: `wasmtime run --invoke 'score(...)'`, embed with the `wasmtime` crate's `component::bindgen!`, or `jco transpile scorer.wasm -o out/` to call it from JS.

### 6.5 Sandboxing a plugin or mod in a native game (host side, Rust + Wasmtime)
```rust
use wasmtime::*;
let mut config = Config::new();
config.consume_fuel(true);                       // deterministic instruction budget
let engine = Engine::new(&config)?;
let module = Module::from_file(&engine, "mod.wasm")?;
let mut store = Store::new(&engine, ());
store.set_fuel(5_000_000)?;                      // trap with OutOfFuel instead of hanging the game
let mut linker = Linker::new(&engine);
linker.func_wrap("host", "spawn", |x: f32, y: f32| { /* validate, then spawn */ })?;
let instance = linker.instantiate(&mut store, &module)?;
let on_tick = instance.get_typed_func::<f32, ()>(&mut store, "on_tick")?;
on_tick.call(&mut store, 0.016)?;
```
Also limit memory with `StoreLimitsBuilder::memory_size(...)`, use epoch interruption for cheaper timeouts, and expose only the host functions the mod needs (capability-based security).

### 6.6 Luau in the browser via Wasm
The Luau repository has a `LUAU_BUILD_WEB` CMake option that builds `Luau.Web` with Emscripten, exporting `executeScript` and `checkScript` (this is how the luau.org web demo runs) [11]:
```bash
emcmake cmake .. -DLUAU_BUILD_WEB=ON -DCMAKE_BUILD_TYPE=Release && cmake --build . --target Luau.Web
```
```js
const run = Module.cwrap("executeScript", "string", ["string"]); // returns an error string or empty
console.log(run('print("hello from Luau in Wasm")'));
```
This gives a sandboxed Luau VM in a web page for playgrounds, teaching tools or a level editor that previews gameplay scripts. It is the Luau VM only: no Roblox engine API.

### 6.7 Feature detection
```js
import { exceptions, gc, memory64, threads, simd, relaxedSimd } from "wasm-feature-detect";
const build = (await gc()) ? "game.gc.wasm" : "game.mvp.wasm";
```

## 7. Top pitfalls and error-message fixes

| Exact error text (typical) | Cause | Fix |
|---|---|---|
| `TypeError: Failed to execute 'compile' on 'WebAssembly': Incorrect response MIME type. Expected 'application/wasm'.` | Server sends wrong Content-Type for `instantiateStreaming` | Serve `.wasm` as `application/wasm`, or fall back to `instantiate(await res.arrayBuffer())` |
| `CompileError: WebAssembly.instantiate(): expected magic word 00 61 73 6d, found 3c 21 44 4f` | The fetch returned HTML (a 404 page, `<!DO...`), not Wasm | Fix the path / server rewrite rules |
| `LinkError: WebAssembly.Instance(): Import #0 module="env" function="foo": function import requires a callable` | Import object missing a function the module imports | Provide every import (`WebAssembly.Module.imports(mod)` lists them); use the generated JS glue |
| `RuntimeError: memory access out of bounds` | Bad pointer, use after free, stack overflow into data, or reading past a grown/shrunk view | Debug with `-sASSERTIONS=2 -sSAFE_HEAP=1` (Emscripten) or AddressSanitizer `-fsanitize=address`; check lengths |
| `RuntimeError: unreachable` / `unreachable executed` | A Rust `panic!`, C `abort()`, or `__builtin_unreachable` compiled to the `unreachable` trap | Install `console_error_panic_hook` (Rust) to see the message; build with debug info |
| `TypeError: Cannot perform %TypedArray%.prototype.set on a detached ArrayBuffer` (or reads return zeros) | `memory.grow` replaced the buffer; old `Uint8Array` views are detached | Re-create views from `memory.buffer` after any call that may allocate |
| `ReferenceError: SharedArrayBuffer is not defined` | Page not cross-origin isolated | Send `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` (or `credentialless`); check `crossOriginIsolated` |
| `RangeError: WebAssembly.Memory(): could not allocate memory` / `Cannot enlarge memory arrays` | Hit `MAXIMUM_MEMORY`, 4 GiB wasm32 limit, or the device is low on memory (mobile) | `-sALLOW_MEMORY_GROWTH=1`, lower initial memory, stream assets; Memory64 only where supported |
| `RuntimeError: call stack exhausted` / `Maximum call stack size exceeded` | Deep recursion; Wasm shares the JS stack limit in browsers | Make it iterative; increase `-sSTACK_SIZE` for the shadow stack (linear-memory stack) |
| `RuntimeError: null function or function signature mismatch` / `indirect call signature mismatch` | Calling a function pointer with the wrong type (C casts) or a null table entry | Fix the prototype; don't cast function pointers to different signatures |
| `CompileError: ... invalid opcode` / `Wasm SIMD unsupported` / `unknown type` | Module uses a feature the engine lacks (SIMD, GC, exnref, memory64) | Feature-detect and ship a fallback build; lower the target features in the toolchain |
| `RuntimeError: Aborted(Assertion failed: ...)` (Emscripten) | An assertion in the C/C++ code or the runtime | Read the message; rebuild with `-g -sASSERTIONS=2` |
| `wasm-bindgen: error: it looks like the Rust project used to create this wasm file was linked against version X of wasm-bindgen but this binary is version Y` | CLI and crate versions differ | Install the matching CLI: `cargo install wasm-bindgen-cli --version X` |
| `error: failed to run custom build command for ring/...` / `cc failed` for `wasm32-unknown-unknown` | C dependency with no Wasm support / no clang for wasm | Use a WASI target with wasi-sdk, or enable the crate's pure-Rust/Wasm feature (`getrandom` needs its `wasm_js` feature/cfg for browsers) |
| `Error: failed to find a `wasm32-unknown-unknown` target` / `can't find crate for core` | Rust target not installed | `rustup target add wasm32-unknown-unknown` (or `wasm32-wasip2`) |
| `wasmtime: failed to run main module ... unknown import: wasi_snapshot_preview1::fd_write` | Running a WASI 0.1 module in a host without WASI linked, or mixing core module and component expectations | Run with `wasmtime run` (links WASI), add `wasmtime_wasi` to the linker, or adapt the module into a component (`wasm-tools component new --adapt`) |
| `Atomics.wait cannot be called in this context` | Blocking wait on the browser main thread | Wait only in workers; use `Atomics.waitAsync` on the main thread |

## 8. Performance

- **Boundary crossings cost.** Call Wasm in batches (one `step(dt)` per frame, not one call per entity). Pass data through shared linear memory views, not by converting arrays to JS objects.
- **Strings are expensive** with linear memory (UTF-8 encode/decode each crossing); prefer integer IDs, or JS string builtins for WasmGC languages.
- **Startup**: `instantiateStreaming` overlaps download and compile; engines cache compiled code (V8 code caching for large modules). Smaller is faster: `wasm-opt -Oz`, `lto = true`, `opt-level = "z"`, `panic = "abort"`, `codegen-units = 1` in Rust; strip debug info; Brotli on the server.
- **SIMD** (`-msimd128`, `std::arch::wasm32`) gives 2-4x for math kernels; relaxed SIMD more where available (Firefox 145+, Chrome 114+; Safari behind a flag per [2]).
- **Memory growth** can copy or remap; reserve enough initial memory for the level to avoid growth stutter mid-game.
- **Threads** help physics/pathfinding but need cross-origin isolation; measure overhead of synchronization.
- **WasmGC** binaries are much smaller for GC languages (no shipped runtime) and integrate with the browser GC; cost is run-time casts.
- **Profile** with the browser Performance panel (Wasm frames are named when you keep the name section), `perf` with Wasmtime's `--profile=perfmap`, or Wasmtime's guest profiler.

## 9. Security

- **The sandbox guarantees**: a module cannot read host memory, call functions it did not import, or jump to arbitrary addresses (control-flow integrity via typed tables). This is why Wasm is used for untrusted plugins and mods.
- **What it does not guarantee**: memory safety *inside* the module (C buffer overflows still corrupt the module's own data and can subvert its logic), and safety of the **host functions** you expose (a `read_file(path)` import is a path traversal hole unless the host validates).
- **Capability-based WASI**: preopen only the directories you mean to share (`wasmtime run --dir ./saves::/saves`), no ambient authority; network/HTTP only if granted.
- **Resource exhaustion**: infinite loops and memory bombs. Use fuel or epoch interruption and store limits in Wasmtime, `Worker.terminate()` in browsers.
- **Spectre**: shared memory and high-resolution timers enabled Spectre-style side channels; that is why browsers require cross-origin isolation for `SharedArrayBuffer` [7].
- **Supply chain**: a `.wasm` from npm is opaque binary; pin versions, check integrity, prefer reproducible builds.
- **Never trust the client**: game logic compiled to Wasm and shipped to browsers is fully readable and modifiable (`wasm2wat`, memory editors); anti-cheat and authority belong on the server, exactly as with Roblox LocalScripts.

## 10. Game-dev usage

- **Web exports of engines**: Unity (Web platform, IL2CPP to Wasm via Emscripten), Godot 4 (Emscripten; since 4.3 a single-threaded export avoids the cross-origin isolation requirement), Unreal (community/third-party web paths), Defold, Bevy (Rust + wasm-bindgen + WebGPU/WebGL2), raylib, SDL-based C/C++ games, Flutter/Flame (`--wasm`).
- **Modding and scripting sandboxes**: Wasmtime/Wasmer/WAMR embed untrusted mods with fuel limits (see 6.5). Components give mods a typed API (WIT) independent of the mod's language.
- **Deterministic simulation** for lockstep/rollback netcode: integer or fixed-point math, no relaxed SIMD, canonical NaNs, same module on client and server.
- **Shared code between client and server**: compile the rules engine once, run it in the browser and on the server.
- **Graphics**: Wasm does not draw; it calls WebGL2/WebGPU through JS (Emscripten maps OpenGL ES, `wgpu` maps WebGPU). Keep draw calls batched.
- **Roblox**: Roblox does not run user Wasm; Luau is the only scripting language. Wasm is relevant for tools around Roblox (web playgrounds running Luau.Web, linters, asset processors) [11].

## 11. Cheat sheet vs Luau

| Concept | Luau | WebAssembly |
|---|---|---|
| What it is | A scripting language with a VM | A compilation target / instruction set; you write another language |
| Numbers | `number` (f64) for all arithmetic | `i32`, `i64`, `f32`, `f64`, `v128`; signedness per instruction |
| Memory | GC'd tables, strings, userdata | Linear memory (`ArrayBuffer`, manual or language-managed) or WasmGC structs/arrays |
| Tables / structs | `{x = 1}` dynamic tables | `(struct (field f64))` fixed layout (GC) or bytes at an offset |
| Errors | `error()` / `pcall` | Traps (fatal for the call), exceptions with tags (`throw` / `try_table`) |
| Sandbox | Roblox security contexts, no `io`/`os` | Imports only; WASI capabilities |
| Calling host APIs | `game:GetService(...)` | Imported functions provided by JS or the runtime |
| Modules | `require(ModuleScript)` | Module imports/exports; components with WIT worlds |
| Concurrency | Coroutines, `task.spawn`, Parallel Luau Actors | Web Workers + shared memory + atomics; WASI 0.3 async |
| Async waiting | `task.wait()` yields the coroutine | JSPI suspends the Wasm stack on a promise; else Asyncify |
| Types | Gradual types, `--!strict` checked at analysis time | Validated at load time; every instruction type-checked |
| Performance | Interpreted + optional native codegen (`--!native`) | JIT/AOT to machine code, near native |
| Debugging | Studio debugger, `print` | DevTools with DWARF, `wasm2wat`, source maps |
| Distribution | Place file / package (Wally) | `.wasm` + JS glue on npm, OCI registries for components |
| Determinism | Not guaranteed across devices for floats | Deterministic except NaN bits and relaxed SIMD (deterministic profile fixes both) |
| Running Luau itself | Native in Roblox | `Luau.Web` Emscripten build exports `executeScript`/`checkScript` |

## 12. Recent changes and version notes

- 2025-09-17: **Wasm 3.0** announced as the current spec: Memory64, multiple memories, GC, typed references, tail calls, exception handling (exnref), relaxed SIMD, deterministic profile, custom annotations, JS string builtins [1].
- Engine status per `features.json` (2026-10-13) [2]: GC in Chrome 119, Firefox 120, Safari 18.2, Wasmtime 47, Node 22; exnref in Chrome 137, Firefox 131, Safari 18.4, Wasmtime 47, Node 24.15; Memory64 in Chrome 133, Firefox 134, Wasmtime 30, Node 24 (Safari: Technology Preview only); tail calls in Chrome 112, Firefox 121, Safari 18.2; relaxed SIMD in Chrome 114, Firefox 145 (Safari flag); JS string builtins in Chrome 130, Firefox 134, Safari 26.2; JSPI in Chrome 137, Firefox 153, Safari 27, Node 26; ESM integration only listed for Deno 2.1.
- 2025-07: the `rustwasm` GitHub organization was sunset; `wasm-bindgen` moved to its own org, other repos archived or transferred [10].
- 2026-06-04: Emscripten 6.0.0 [9]. 2026-10-08: 6.0.12.
- 2026-06-11: **WASI 0.3.0** released: native async in the Component Model (`stream`, `future`, `async func`), `wasi:io` removed [3][4]. Wasmtime 46 enabled component-model async by default; Wasmtime 49.0.2 is current [8].

## Sources

1. https://webassembly.org/news/2025-09-17-wasm-3.0/ (accessed 2026-10-13)
2. https://webassembly.org/features/ and https://github.com/WebAssembly/website/blob/main/features.json (accessed 2026-10-13)
3. https://bytecodealliance.org/articles/WASI-0.3 (accessed 2026-10-13)
4. https://wasi.dev/releases/wasi-p3 (accessed 2026-10-13)
5. https://developer.mozilla.org/en-US/docs/WebAssembly (accessed 2026-10-13)
6. https://component-model.bytecodealliance.org/design/migrating-to-p3.html (accessed 2026-10-13)
7. https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer (security requirements section; accessed 2026-10-13)
8. GitHub latest releases, queried 2026-10-13: https://github.com/bytecodealliance/wasmtime/releases , https://github.com/wasmerio/wasmer/releases , https://github.com/emscripten-core/emscripten/releases , https://github.com/wasm-bindgen/wasm-bindgen/releases , https://github.com/bytecodealliance/jco/releases , https://github.com/AssemblyScript/assemblyscript/releases , https://github.com/WebAssembly/binaryen/releases , https://github.com/luau-lang/luau/releases
9. https://github.com/emscripten-core/emscripten/blob/main/ChangeLog.md (accessed 2026-10-13)
10. https://blog.rust-lang.org/inside-rust/2025/07/21/sunsetting-the-rustwasm-github-org (accessed 2026-10-13)
11. https://github.com/luau-lang/luau/blob/master/CMakeLists.txt (LUAU_BUILD_WEB target; accessed 2026-10-13)
12. https://docs.wasmtime.dev/ (accessed 2026-10-13)
13. https://emscripten.org/docs/porting/pthreads.html (accessed 2026-10-13)
14. https://v8.dev/blog/jspi (accessed 2026-10-13)
15. https://web.dev/articles/coop-coep (accessed 2026-10-13)
16. https://godotengine.org/article/progress-report-web-export-in-4-3/ (accessed 2026-10-13)
