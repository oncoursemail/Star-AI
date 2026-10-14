# Rust (stable 1.99, 2024 edition) - STAR language research

> Status: versions checked on 2026-10-13 against the official Rust blog release list (latest stable **1.99.0, 2026-10-01**;
> 1.98.1 on 2026-09-03), the Edition Guide and the rustc error index. The **2024 edition** has been stable since
> **Rust 1.85 (2025-02-20)** and is what `cargo new` uses. Use Rust when you need C/C++-class performance and control
> with compile-time memory and data-race safety: engines, servers, CLIs, WASM, embedded, tooling (Luau's own ecosystem
> tools such as StyLua, Selene, Rojo, Lune and Wally are written in Rust).

## 0. Current version and what changed 2024-2026

Rust ships a stable release every six weeks. Always ask which toolchain the user has (`rustc --version`,
`rust-toolchain.toml`) and which edition (`edition = "2024"` in `Cargo.toml`). Editions change *syntax and lints*,
not the ABI; crates of different editions link together freely.

| Release | Date | Headline changes (from the official announcements) |
|---|---|---|
| 1.85 | 2025-02-20 | **Rust 2024 edition**; async closures (`async || {}`, `AsyncFn*` traits); `#[diagnostic::do_not_recommend]` |
| 1.86 | 2025-04-03 | Trait upcasting (`&dyn Sub` -> `&dyn Super`); `get_disjoint_mut` for slices and `HashMap` |
| 1.87 | 2025-05-15 | Anonymous pipes `std::io::pipe()`; 10 years of Rust |
| 1.88 | 2025-06-26 | **let chains** (`if let A = x && let B = y && cond`) in the 2024 edition; naked functions `#[unsafe(naked)]` |
| 1.89 | 2025-08-07 | `_` for inferred const generic args (`[false; _]`); `mismatched_lifetime_syntaxes` lint |
| 1.90 | 2025-09-18 | LLD default linker on x86_64-unknown-linux-gnu; `cargo publish --workspace` |
| 1.91 | 2025-10-30 | aarch64-pc-windows-msvc becomes Tier 1 |
| 1.92 | 2025-12-11 | never-type lints deny-by-default; `unused_must_use` ignores `Result<(), Infallible>` |
| 1.93 | 2026-01-22 | bundled musl 1.2.5; global allocator may use thread-locals; `#[cfg]` on `asm!` lines |
| 1.94 | 2026-03-05 | `array_windows`; Cargo config `include` |
| 1.95 | 2026-04-16 | `cfg_select!` (built-in replacement for the `cfg-if` crate) |
| 1.96 | 2026-05-28 | new `core::range::{Range, RangeFrom, RangeInclusive}` types (Copy, `IntoIterator`); `assert_matches!` |
| 1.97 | 2026-07-09 | v0 symbol mangling on by default |
| 1.98 | 2026-08-20 | algebraic float methods; buffered integer formatting; `ManuallyDrop<Box<_>>` aliasing fix |
| 1.99 | 2026-10-01 | define C-variadic functions: `unsafe extern "C" fn f(mut args: ...)` |

What the **2024 edition** changed (edition guide):
- `impl Trait` in return position captures **all** in-scope generic params and lifetimes by default; use
  `impl Trait + use<'a, T>` to capture less (precise capturing, 1.82).
- `if let` temporaries are dropped before the `else` block; tail-expression temporaries drop before locals. This fixes
  classic `RefCell`/`Mutex` guard deadlocks in `if let x = m.lock().unwrap().get() {..} else {..}`.
- `unsafe extern "C" { ... }` blocks are required; items inside can be marked `safe`/`unsafe`.
- Attributes that can cause UB must be written `#[unsafe(no_mangle)]`, `#[unsafe(export_name)]`, `#[unsafe(link_section)]`.
- `unsafe_op_in_unsafe_fn` warns: inside an `unsafe fn` you still need an `unsafe {}` block for unsafe operations.
- `static mut` references: taking `&STATIC_MUT` / `&mut STATIC_MUT` is denied (`static_mut_refs`); use atomics,
  `Mutex`, `OnceLock`/`LazyLock`, or `&raw const`/`&raw mut` raw pointers.
- `gen` is a reserved keyword (use `r#gen` for identifiers, e.g. `rand::Rng::gen` became `random`/`r#gen`).
- `Future` and `IntoFuture` are in the prelude; `Box<[T]>` implements `IntoIterator` by value.
- `std::env::set_var` / `remove_var` are `unsafe fn` (unsound with concurrent readers).
- Never-type fallback changes toward `!`; `expr` macro fragment now matches `const {}` and `_`.
- Cargo: resolver `"3"` is the default for 2024 crates (MSRV-aware: prefers dependency versions compatible with your
  `rust-version`).
- Rustfmt "style edition 2024" (sorting changes).

Migrating: `cargo fix --edition`, then set `edition = "2024"`, then `cargo build && cargo test && cargo clippy`.

## 1. Mental model

- Every value has **one owner**. When the owner goes out of scope, the value is dropped (RAII, deterministic, no GC).
- Assignment and pass-by-value **move** non-`Copy` values. After a move the source is unusable (compile error E0382).
- You can **borrow**: any number of shared references `&T` **or** exactly one mutable reference `&mut T`, never both
  at the same time ("aliasing XOR mutation"). References must not outlive what they point to (lifetimes).
- The borrow checker (NLL, non-lexical lifetimes) reasons about where references are *used*, not where blocks end.
- No null: `Option<T>`. No exceptions: `Result<T, E>` + `?`. Panics are for bugs, not control flow.
- Traits are interfaces + type classes; generics are monomorphised (zero-cost, bigger binaries); `dyn Trait` is the
  opt-in vtable form.
- Thread safety is in the type system: `Send` (can move to another thread), `Sync` (`&T` can be shared across
  threads). A data race in safe Rust is a compile error.
- `unsafe` does not turn off the borrow checker; it unlocks five extra powers (deref raw pointers, call unsafe fns,
  access `static mut`, implement unsafe traits, access union fields). You promise the invariants.

## 2. Type system

- Scalars: `i8..i128, isize, u8..u128, usize, f32, f64, bool, char` (a Unicode scalar value, 4 bytes).
- Integer overflow: **panics in debug**, wraps in release (unless `overflow-checks = true`). Be explicit:
  `checked_add`, `wrapping_add`, `saturating_add`, `overflowing_add`, `strict_add` (stabilized 2025).
- Casts with `as` truncate/saturate silently (`300i32 as u8 == 44`, `f64::NAN as i32 == 0`); prefer
  `u8::try_from(x)?`.
- Compound: tuples, arrays `[T; N]` (stack, fixed), slices `[T]` (unsized, used via `&[T]`), `str` (UTF-8, via `&str`),
  `String`, `Vec<T>`, `Box<T>`.
- ADTs: `struct`, `enum` (tagged unions; with `match` exhaustiveness), `union` (unsafe).
- Generics with trait bounds: `fn f<T: Display + Clone>(x: T)` or `where` clauses; `impl Trait` in argument and
  return position; associated types (`Iterator::Item`); const generics (`[T; N]`); GATs (1.65).
- Trait objects `dyn Trait` need object safety ("dyn compatibility"): no generic methods, no `Self: Sized` returns.
- Auto traits: `Send`, `Sync`, `Unpin`, `UnwindSafe`. Marker: `Copy`, `Sized` (implicit bound; opt out `?Sized`).
- Lifetimes: `'a` annotations relate input and output borrows; elision rules cover most functions; `'static` means
  "can live for the whole program" (owned data or string literals), not "lives forever".
- Type inference is local (function bodies); signatures are always explicit.
- Never type `!` (diverging), unit `()`.
- Pattern matching: `match`, `if let`, `let else`, let chains (2024), `matches!`, `assert_matches!` (1.96), bindings
  `x @ 1..=5`, slice patterns `[first, .., last]`.

## 3. Memory model and ownership

- Stack by default; heap via `Box`, `Vec`, `String`, `Rc`, `Arc`.
- `Clone` is explicit deep copy; `Copy` is implicit bitwise copy for plain data (`i32`, `&T`, small structs that
  derive it). A type with `Drop` cannot be `Copy`.
- Smart pointers:
  - `Box<T>` unique heap ownership; recursive types (`enum List { Cons(i32, Box<List>), Nil }`).
  - `Rc<T>` single-threaded shared ownership; `Arc<T>` atomic, thread-safe.
  - `Weak<T>` breaks cycles (parent pointers, observers). `Rc` cycles leak (leaks are *safe* in Rust).
  - Interior mutability: `Cell<T>` (Copy values), `RefCell<T>` (runtime borrow checking; panics with
    `already borrowed: BorrowMutError`), `Mutex<T>`/`RwLock<T>` (threads), atomics, `OnceCell`/`OnceLock`/`LazyLock`.
  - Common combos: `Rc<RefCell<T>>` (single thread graph), `Arc<Mutex<T>>` (shared mutable across threads).
- Moves are memcpy of the stack part; the heap buffer is not copied.
- `Drop` order: locals in reverse declaration order; struct fields in declaration order.
- `std::mem::take`, `replace`, `swap` move values out of `&mut` places without cloning (fix for E0507).
- `Cow<'a, T>` borrows when possible, owns when needed.
- `Pin<P>` guarantees a value will not move (self-referential futures).
- Arenas / indices instead of references for graphs and game entities (`Vec<Node>` + `usize` ids, `slotmap`,
  generational indices; ECS does this).

## 4. Concurrency

- `std::thread::spawn(move || ...)` needs `'static + Send` closures; `std::thread::scope(|s| s.spawn(|| ...))`
  (1.63) lets threads borrow locals safely.
- Channels: `std::sync::mpsc` (multi-producer single-consumer), `crossbeam-channel`, `flume`.
- `Mutex::lock()` returns `LockResult` (poisoning after a panic): `.lock().unwrap()` is idiomatic, or
  `parking_lot::Mutex` (no poisoning). Keep guards short-lived; never hold a `std::sync::MutexGuard` across `.await`.
- Data parallelism: `rayon` (`par_iter()`).
- Atomics: `AtomicUsize` etc. with explicit `Ordering` (`Relaxed` for counters, `Acquire`/`Release` pairs for
  publication, `SeqCst` when in doubt).
- Async: `async fn` returns a `Future` that does nothing until polled; you need a runtime (`tokio` is the de facto
  standard; also `smol`, `embassy` for embedded). `#[tokio::main]`, `tokio::spawn` (needs `Send + 'static`
  futures), `tokio::select!`, `tokio::sync::Mutex` only when the guard must live across `.await`.
- Async fn in traits is stable (1.75) but `dyn`-incompatible; use `async-trait` or boxed futures for `dyn`. Async
  closures stable since 1.85.
- Blocking inside async (CPU work, `std::fs`, `thread::sleep`) stalls the executor: use `spawn_blocking` or
  `tokio::fs`/`tokio::time::sleep`.
- Cancellation = dropping the future; code after an `.await` may never run. Make `select!` branches cancel-safe.

## 5. Error handling

- `Result<T, E>` for recoverable errors; `?` propagates and converts via `From<E>`.
- `Option<T>` + `?` in functions returning `Option`. Convert with `.ok_or(err)?`, `.ok()`.
- Libraries: define an error `enum` (often with `thiserror` derive). Applications: `anyhow::Result<T>` with
  `.context("reading config")?`. `Box<dyn std::error::Error + Send + Sync>` works without crates.
- `main` can return `Result<(), E>` where `E: Debug`; or `std::process::ExitCode`.
- `unwrap()` / `expect("why")` panic; fine in tests, prototypes and for true invariants. Prefer `expect` with a reason.
- Panics unwind by default (`panic = "abort"` in profile to shrink binaries); `catch_unwind` exists for FFI
  boundaries, not for normal errors. Unwinding across `extern "C"` aborts; use `extern "C-unwind"` deliberately.
- `#[must_use]` on `Result` means ignoring it warns.

```rust
use std::{fs, path::Path};
use anyhow::{Context, Result};

fn load_level(path: &Path) -> Result<Level> {
    let text = fs::read_to_string(path)
        .with_context(|| format!("reading {}", path.display()))?;
    let level: Level = serde_json::from_str(&text).context("parsing level JSON")?;
    Ok(level)
}
```

## 6. Toolchain, build and package management

- Install and manage with **rustup** (`rustup update`, `rustup target add wasm32-unknown-unknown`,
  `rustup component add clippy rustfmt rust-src miri`). Pin per project with `rust-toolchain.toml`.
- **Cargo**: `cargo new app`, `cargo new --lib lib`, `cargo build [--release]`, `cargo run`, `cargo test`,
  `cargo check` (fast, no codegen), `cargo clippy -- -D warnings`, `cargo fmt`, `cargo doc --open`, `cargo add serde
  --features derive`, `cargo update`, `cargo tree -d` (duplicate deps), `cargo publish --workspace` (1.90).
- `Cargo.toml`: `[package] edition = "2024"`, `rust-version = "1.85"` (MSRV), `[dependencies]`,
  `[dev-dependencies]`, `[features]`, `[profile.release] lto = true, codegen-units = 1, panic = "abort"`,
  `[workspace]` with `[workspace.dependencies]` and `[workspace.lints]`.
- `Cargo.lock`: commit it for binaries *and* (current guidance) for libraries too.
- crates.io is the registry; docs.rs hosts docs. Semver: `serde = "1"` means `^1`.
- Build scripts `build.rs` (code generation, linking C); `cc` crate to compile C; `bindgen` for C headers;
  `cxx` for C++.
- Cross-compile: `rustup target add`, `cross` tool, `cargo zigbuild`.
- Lints: `clippy::pedantic`, `#![deny(unsafe_op_in_unsafe_fn)]`, `#![forbid(unsafe_code)]` in safe crates.
- IDE: rust-analyzer.

## 7. Testing

- Unit tests in the same file: `#[cfg(test)] mod tests { use super::*; #[test] fn it_works() { assert_eq!(2+2, 4); } }`.
- Integration tests in `tests/*.rs` (each is its own crate using the public API).
- Doc tests: code blocks in `///` comments run with `cargo test`.
- `#[should_panic(expected = "...")]`, `#[ignore]`, tests returning `Result<(), E>`.
- Filter: `cargo test name_substring -- --nocapture --test-threads=1`.
- `cargo nextest run` (faster runner), `proptest`/`quickcheck` (property tests), `cargo fuzz` (libFuzzer),
  `insta` (snapshots), `criterion`/`divan` (benchmarks; `#[bench]` is nightly only), `mockall`.
- **Miri** (`cargo +nightly miri test`) interprets MIR and detects UB in unsafe code (out-of-bounds, use-after-free,
  invalid aliasing under Stacked/Tree Borrows, data races).
- Async tests: `#[tokio::test]`.

## 8. Idiomatic patterns

- Newtype pattern: `struct Meters(f64);` for type safety and to implement foreign traits.
- Builder pattern for many optional params; `Default` + struct update `..Default::default()`.
- `From`/`Into`/`TryFrom` for conversions; `AsRef<str>`/`impl Into<String>` for flexible params.
- Accept borrowed, return owned: `fn f(s: &str) -> String`; take `&[T]` not `&Vec<T>`, `&str` not `&String`.
- Iterators over index loops: `iter().map().filter().collect::<Vec<_>>()`; `iter_mut`, `into_iter`, `enumerate`,
  `zip`, `windows`, `chunks`, `array_windows` (1.94).
- Typestate pattern (states as types) to make illegal states unrepresentable.
- `impl Display` for user-facing text, `#[derive(Debug)]` for debugging.
- Enums + `match` for state machines (game states, AI).
- RAII guards for cleanup instead of manual `close()`.
- `let else` for early return: `let Some(x) = opt else { return Err(...) };`.
- Prefer `&mut self` methods on a struct over global mutable state; use `OnceLock`/`LazyLock` for globals.

## 9. Top 30 pitfalls and compiler-error fixes

(Error codes and titles from the official rustc error index.)

1. **E0382 use of moved value** - you moved a `String`/`Vec` then used it. Fix: borrow (`&s`), `clone()` if you need
   two owners, or restructure.
   ```rust
   let s = String::from("hi"); let t = s; println!("{s}"); // E0382
   let s = String::from("hi"); let t = &s; println!("{s} {t}"); // ok
   ```
2. **E0499 cannot borrow as mutable more than once at a time** - two live `&mut`. Fix: shorten the first borrow,
   split borrows (`split_at_mut`, `get_disjoint_mut`), or borrow fields separately.
3. **E0502 cannot borrow as mutable because it is also borrowed as immutable** - e.g. pushing to a `Vec` while
   holding `&v[0]`, or `v.push(v.len())` in old code. Fix: copy the value out first (`let x = v[0];`), end the shared
   borrow before mutating, or clone.
   ```rust
   let first = &v[0]; v.push(4); println!("{first}"); // E0502
   let first = v[0]; v.push(4); println!("{first}");  // ok for Copy types
   ```
4. **E0505 cannot move out of value because it is borrowed** - moving while a reference is alive. Fix: end the borrow
   first or clone.
5. **E0506 cannot assign to borrowed value**.
6. **E0507 cannot move out of a shared reference / of index** - `let s = v[0];` for `Vec<String>`, or
   `self.field` behind `&self`. Fix: borrow (`&v[0]`), `.clone()`, or `std::mem::take(&mut self.field)` /
   `Option::take()` when you have `&mut`.
7. **E0515 cannot return reference to local variable** - returning `&String` built inside the fn. Fix: return the
   owned `String`.
8. **E0597 borrowed value does not live long enough** - reference stored somewhere outliving the value. Fix: move
   ownership in, or declare the value in an outer scope.
9. **E0716 temporary value dropped while borrowed** - `let r = &String::from("x");` used later via a method chain
   like `let s = foo().as_str();`. Fix: bind the temporary to a `let` first.
10. **E0106 missing lifetime specifier** - a function returns a reference with two reference params, or a struct
   holds `&str`. Fix: add `<'a>` and tie output to the right input, or store `String`.
11. **E0373 closure may outlive the current function, but it borrows** - `thread::spawn(|| use(x))`. Fix: `move ||`,
   or use `thread::scope`.
12. **E0277 the trait bound `X: Y` is not satisfied** - missing derive/impl (`Debug`, `Clone`, `Hash`, `Eq`,
   `Send`), or `?` on a mismatched error type (`From` not implemented). Fix: derive/impl, add a bound, map the error
   (`.map_err(...)`), or use `anyhow`.
13. **E0308 mismatched types** - `String` vs `&str` (`.to_string()`/`&s`), `i32` vs `usize` (`as usize` /
   `try_from`), missing `Ok(...)` wrapping, a trailing `;` turning the tail expression into `()`.
14. **E0599 no method named `x` found** - trait not in scope (`use std::io::Write;`, `use rand::Rng;`), method on
   `Option` not the inner value (`.unwrap()`/`.as_ref()`), or a missing derive.
15. **E0425 cannot find value** / **E0433 failed to resolve** / **E0432 unresolved import** - module paths:
   `crate::`, `super::`, `mod foo;` must be declared in `lib.rs`/`main.rs`; dependency missing in `Cargo.toml`.
16. **E0596 cannot borrow as mutable, as it is not declared as mutable** - add `mut` to the binding or take
   `&mut self`.
17. **E0384 cannot assign twice to immutable variable** - add `mut`.
18. **E0004 non-exhaustive patterns** - add the missing arms or `_ =>`.
19. **E0282 / E0283 type annotations needed** - `collect()`, `parse()`, `into()`: write `collect::<Vec<_>>()`,
   `parse::<i32>()`.
20. **E0053 / E0046** - trait impl signature mismatch / missing trait items.
21. **E0038 the trait cannot be made into an object** - generic method or `Self` return in a trait used as `dyn`.
   Fix: `where Self: Sized` on that method, or use generics instead of `dyn`.
22. **E0061 wrong number of arguments**; **E0023** wrong number of fields in a pattern.
23. **E0614 / E0608** - dereferencing or indexing a type that does not support it.
24. **RefCell `already borrowed: BorrowMutError` panic** (runtime) - nested `borrow_mut()`; drop the first guard
   before the second call, or restructure.
25. **Deadlock with `Mutex`** - locking twice in one thread (std Mutex is not reentrant); holding a guard across
   `.await` (and future is not `Send`: "future cannot be sent between threads safely"). Fix: scope the guard
   `{ let g = m.lock().unwrap(); ... }` before `.await`.
26. **`Rc<T>` cannot be sent between threads safely** (E0277 Send) - use `Arc`, and `Mutex` instead of `RefCell`.
27. **Integer overflow panics only in debug** - tests pass in release builds with wrong numbers; use `checked_*` or
   `wrapping_*` explicitly.
28. **Indexing `&str` by byte** - `s[0]` does not compile; slicing in the middle of a UTF-8 char panics. Use
   `s.chars()`, `char_indices()`, or `s.get(a..b)`.
29. **`static mut` in 2024 edition** - `&STATE` is denied (`static_mut_refs`). Fix: `static STATE: Mutex<T>` /
   `LazyLock`, atomics, or `&raw mut STATE` inside `unsafe`.
30. **`gen` is a keyword in 2024** - `rng.gen()` fails to parse; rand 0.9 renamed it to `rng.random()`; or write
   `r#gen`.
31. **Unused `Result`** warning (`unused_must_use`) - handle it with `?` or `let _ =` deliberately.

## 10. Performance

- Always measure with `--release` (debug can be 10-100x slower). `opt-level = 3`, `lto = "fat"`,
  `codegen-units = 1`, `panic = "abort"`, `-C target-cpu=native` (local only).
- Profilers: `cargo flamegraph`, `perf`, `samply`, Tracy (`tracy-client`, common in games), `criterion` for
  micro-benchmarks, `cargo bloat` for binary size, `dhat` for heap profiling.
- Avoid needless `clone()`, `to_string()`, `collect()` into temporary `Vec`s; reuse buffers (`clear()` keeps capacity);
  `Vec::with_capacity`.
- Iterators compile to tight loops and often auto-vectorize; bounds checks can be hoisted with slicing (`&a[..n]`)
  or iterators. `get_unchecked` only after profiling, with a SAFETY comment.
- `Box<dyn Trait>` costs an indirection + no inlining; generics cost compile time and binary size.
- Data-oriented design: struct-of-arrays, contiguous `Vec`s, ECS (Bevy) for cache-friendly game loops.
- Small-vector / arena allocators: `smallvec`, `bumpalo`; alternative global allocators: `mimalloc`.
- HashMap uses SipHash (DoS-resistant, slower): `FxHashMap`/`ahash` for trusted keys.
- SIMD: `std::arch` intrinsics (stable), portable `std::simd` is still nightly.

## 11. Security

- Safe Rust prevents use-after-free, double free, buffer overflow (bounds-checked indexing panics), data races and
  null derefs. It does **not** prevent logic bugs, panics (DoS), integer overflow in release, deadlocks, leaks, or
  vulnerabilities in `unsafe` code and C dependencies.
- `unsafe` rules: every block gets a `// SAFETY:` comment stating the invariant; keep it small and wrapped in a safe
  API; run Miri and sanitizers (`RUSTFLAGS=-Zsanitizer=address` on nightly).
- UB in unsafe code includes: creating two `&mut` to the same data, dangling references (even unused), invalid
  values (`bool` other than 0/1, invalid `char`, null `&T`), reading uninitialized memory (use `MaybeUninit`),
  misaligned access, data races, unwinding across `extern "C"`. `mem::transmute` is the most dangerous API.
- FFI: validate pointers and lengths from C; `CStr::from_ptr` needs a valid NUL-terminated string.
- Injection: SQL via `sqlx`/`diesel` with bind parameters (`sqlx::query!("... WHERE id = $1", id)`), never
  `format!` into SQL. Shell: `std::process::Command::new("git").arg(user_input)` passes args without a shell; never
  `sh -c` with user input. Path traversal: canonicalize and check `starts_with(base)`.
- Deserialization: `serde` is data-only (no code execution), but bound sizes (`serde_json` with limits) to avoid
  memory DoS.
- Supply chain: `cargo audit` (RustSec advisory DB), `cargo deny check` (licenses, bans, sources),
  `cargo vet`, pin with `Cargo.lock`, review `build.rs` and proc macros (they run code at build time).
- Secrets: `zeroize`, `secrecy` crates. Crypto: `rustls`, `ring`/`aws-lc-rs`, RustCrypto; never roll your own.
- Time-of-check races on files; use `OpenOptions::create_new(true)`.

## 12. Game-development usage

- **Bevy** (ECS engine; latest **0.20.0, released 2026-10-08** on GitHub). Breaking changes every release: always
  check the Bevy version in `Cargo.toml` and read the migration guide. Core API (stable for several versions):
  `App::new().add_plugins(DefaultPlugins).add_systems(Startup, setup).add_systems(Update, movement).run()`;
  systems are plain functions taking `Commands`, `Query<(&mut Transform, &Velocity), With<Player>>`, `Res<Time>`,
  `ResMut<T>`; components are `#[derive(Component)]` structs; `add_system` (singular) was removed in 0.11;
  bundles like `SpriteBundle` were replaced by required components in 0.15 (`commands.spawn((Sprite::from_image(h),
  Transform::default()))`). Events were reworked into messages/observers in recent versions: verify for the user's
  version.
- **macroquad** (simple immediate-mode 2D, `#[macroquad::main("Game")] async fn main()` with `next_frame().await`),
  **ggez**, **Fyrox** (editor-based 3D), **wgpu** (WebGPU API for custom renderers), **winit** (windowing),
  **rapier** (physics), **kira** (audio), **raylib-rs**/**sdl3** bindings.
- Embedding Lua/Luau: **mlua** supports Lua 5.1-5.4, LuaJIT and **Luau** (feature `luau`); used for modding and
  scripting. Rust tools for the Roblox workflow: Rojo, StyLua, Selene, Lune, Wally, Darklua.
- WASM: `wasm32-unknown-unknown` + `wasm-bindgen`/`trunk`; Bevy and macroquad run in browsers.
- Game-loop concerns: avoid allocation per frame, use fixed timestep for physics (`Time<Fixed>` in Bevy), entity ids
  instead of references.

## 13. Cheat sheet: Rust vs Luau

| Concept | Luau | Rust |
|---|---|---|
| Variable | `local x = 1` | `let x = 1;` (immutable) / `let mut x = 1;` |
| Constant | `local MAX = 10` (convention) | `const MAX: u32 = 10;` / `static` |
| Nil | `nil` | `Option<T>`: `None` / `Some(v)`; no null |
| Number | one `number` (f64) | `i32`, `u64`, `usize`, `f32`, `f64`... explicit casts |
| Integer division | `7 // 2 == 3` | `7 / 2 == 3` (ints), `7.0 / 2.0 == 3.5` |
| Indexing | 1-based `t[1]` | 0-based `v[0]`, panics out of bounds; `v.get(i)` -> `Option` |
| Array | `{1, 2, 3}` | `vec![1, 2, 3]` (`Vec<i32>`), `[1, 2, 3]` fixed array |
| Map | `{a = 1}` / `t[k] = v` | `HashMap<String, i32>`; `map.insert(k, v)`, `map.get(&k)` |
| Length | `#t` | `v.len()` |
| String concat | `a .. b` | `format!("{a}{b}")`, `a + &b`, `s.push_str(b)` |
| String format | `string.format("%d", n)` | `format!("{n}")`, `println!("{:.2}", x)` |
| Interpolation | `` `hi {name}` `` | `format!("hi {name}")` |
| Function | `local function f(a: number): number` | `fn f(a: f64) -> f64 { a * 2.0 }` |
| Closure | `function(x) return x + 1 end` | `|x| x + 1`, `move |x| ...` |
| Multiple returns | `return a, b` | return a tuple `(a, b)` |
| Varargs | `...` | slices `&[T]`, macros; C variadics only via FFI |
| Module | `require(script.Parent.Mod)` | `mod m;` + `use crate::m::Thing;` |
| Class | metatable + `__index` | `struct` + `impl` block; traits for polymorphism |
| Method call | `obj:Method()` | `obj.method()` (`&self`/`&mut self`) |
| Inheritance | metatable chain | none; composition + traits (default methods) |
| Error raise | `error("msg")` | `return Err(MyError::...)` / `panic!` for bugs |
| Error catch | `pcall(f)` / `xpcall` | `match result { Ok(v) => .., Err(e) => .. }`, `?` |
| Coroutine | `coroutine.wrap`, `task.spawn` | threads, `async`/`.await` with tokio, channels |
| Wait | `task.wait(1)` | `std::thread::sleep(Duration::from_secs(1))` / `tokio::time::sleep(..).await` |
| Type annotations | optional, `--!strict` | mandatory in signatures, inferred in bodies |
| Generics | `<T>` in type functions | `fn f<T: Trait>(x: T)`, monomorphised |
| Iteration | `for i, v in ipairs(t)` | `for (i, v) in v.iter().enumerate()` |
| Equality | `==` (reference for tables) | `==` via `PartialEq` (value), `std::ptr::eq` for identity |
| Memory | GC | ownership + RAII, no GC |
| Enum/union | string tags or tables | `enum Shape { Circle(f32), Rect { w: f32, h: f32 } }` + `match` |
| Truthiness | only `nil`/`false` are falsy | only `bool`; no implicit truthiness |
| Globals | `_G` (avoid) | `static` + `OnceLock`/`Mutex`; avoid |

## 14. Sources

Releases and editions:
- https://blog.rust-lang.org/releases/ - official release list and dates
- https://blog.rust-lang.org/2025/02/20/Rust-1.85.0/ - 2024 edition, async closures
- https://blog.rust-lang.org/2025/04/03/Rust-1.86.0/ - trait upcasting, get_disjoint_mut
- https://blog.rust-lang.org/2025/06/26/Rust-1.88.0/ - let chains, naked functions
- https://blog.rust-lang.org/2025/08/07/Rust-1.89.0/ - inferred const args, lifetime lint
- https://blog.rust-lang.org/2025/09/18/Rust-1.90.0/ - LLD default, workspace publish
- https://blog.rust-lang.org/2026/04/16/Rust-1.95.0/ - cfg_select!
- https://blog.rust-lang.org/2026/05/28/Rust-1.96.0/ - new Range types, assert_matches
- https://blog.rust-lang.org/2026/07/09/Rust-1.97.0/ - v0 mangling default
- https://blog.rust-lang.org/2026/08/20/Rust-1.98.0/ - algebraic floats, ManuallyDrop fix
- https://blog.rust-lang.org/2026/10/01/Rust-1.99.0/ - C variadic definitions
- https://doc.rust-lang.org/edition-guide/rust-2024/index.html - all 2024 edition changes
- https://doc.rust-lang.org/edition-guide/rust-2024/static-mut-references.html - static mut refs denied
- https://doc.rust-lang.org/edition-guide/rust-2024/gen-keyword.html - gen reserved

Language and errors:
- https://doc.rust-lang.org/book/ - ownership, borrowing, lifetimes, error handling
- https://doc.rust-lang.org/reference/ - language reference, behavior considered undefined
- https://doc.rust-lang.org/reference/behavior-considered-undefined.html - UB list
- https://doc.rust-lang.org/error_codes/error-index.html - rustc error code index
- https://doc.rust-lang.org/nomicon/ - unsafe Rust
- https://doc.rust-lang.org/std/sync/index.html - Mutex, Arc, atomics, OnceLock
- https://doc.rust-lang.org/std/cell/index.html - Cell, RefCell interior mutability

Tooling and testing:
- https://doc.rust-lang.org/cargo/ - Cargo manifest, profiles, workspaces, resolver
- https://doc.rust-lang.org/cargo/reference/resolver.html - resolver v3, MSRV-aware
- https://doc.rust-lang.org/clippy/ - lints
- https://github.com/rust-lang/miri - UB detection
- https://doc.rust-lang.org/rustc/tests/index.html - test harness options

Async, security, ecosystem:
- https://tokio.rs/tokio/tutorial - async runtime, spawn, select
- https://rustsec.org/ - advisory database, cargo-audit
- https://embarkstudios.github.io/cargo-deny/ - supply-chain policy
- https://github.com/launchbadge/sqlx - bind parameters
- https://bevy.org/news/ - Bevy releases and migration guides
- https://github.com/bevyengine/bevy/releases - Bevy 0.20.0 (2026-10-08)
- https://github.com/mlua-rs/mlua - Lua/Luau embedding from Rust
