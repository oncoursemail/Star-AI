---
name: lang-rust
description: Rust (stable 1.99, 2024 edition) ownership, borrow-checker errors, error handling, async and Cargo. Use for Rust code, rustc errors such as E0382/E0499/E0502/E0597, Cargo, tokio, Bevy or porting Luau to Rust.
---
# Rust (2024 edition, stable 1.99 in October 2026)
- Check `edition` in Cargo.toml and `rustc --version`. The 2024 edition (Rust 1.85+) adds let chains (1.88), `unsafe extern` blocks, `#[unsafe(no_mangle)]`, denies `&STATIC_MUT` references, reserves `gen` (rand 0.9 renamed `gen()` to `random()`), and makes `std::env::set_var` unsafe.
- One owner per value; moves invalidate the source. Many `&T` OR one `&mut T`, never both at once.
- E0382 use of moved value: borrow (`&s`) or `clone()` only if two owners are really needed.
- E0499/E0502 conflicting borrows: end the first borrow before mutating (copy the value out, shorter scope), split borrows (`split_at_mut`, `get_disjoint_mut`).
- E0507 cannot move out of a reference: borrow it, `clone()`, or `std::mem::take`/`Option::take` when you hold `&mut`.
- E0515/E0597/E0716 dangling references: return owned data (`String`, `Vec`), bind temporaries with `let` first.
- E0373 closure may outlive the function: `move ||`, or `std::thread::scope` to borrow locals.
- E0277 trait bound not satisfied: derive/impl the trait, add a bound, or map the error type for `?` (`map_err`, `From`, anyhow).
- Never suggest `unsafe` to silence the borrow checker. Shared mutable state: `Rc<RefCell<T>>` (one thread) or `Arc<Mutex<T>>` (threads); `static` + `LazyLock`/`OnceLock`/atomics instead of `static mut`.
- Errors: `Result<T, E>` + `?`; libraries define error enums (thiserror), apps use `anyhow::Result` + `.context(...)`. `unwrap` only for true invariants and tests.
- Async: needs a runtime (tokio). Do not hold a `std::sync::MutexGuard` across `.await`; use `spawn_blocking` for blocking work; `tokio::spawn` needs `Send + 'static` futures.
- Integer overflow panics in debug and wraps in release: use `checked_*`, `wrapping_*`, `saturating_*`; `u8::try_from(x)?` instead of `as`.
- Build and check: `cargo check`, `cargo clippy -- -D warnings`, `cargo fmt`, `cargo test`, `cargo build --release`; Miri (`cargo +nightly miri test`) for unsafe code; `cargo audit`/`cargo deny` for dependencies.
- SQL with bind parameters (`sqlx::query!("... WHERE id = $1", id)`), processes with `Command::new(bin).arg(x)` (no shell).
- Bevy changes APIs every release (0.20 in October 2026): check the version; systems are `add_systems(Update, f)`, bundles became required components.
