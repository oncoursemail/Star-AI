# Go (1.27) - STAR language research

> Status: checked on 2026-10-13 against go.dev/doc/devel/release: **Go 1.27.0 released 2026-08-19** (1.27.2 on
> 2026-10-08); Go 1.26 (February 2026) and 1.25 (August 2025) notes read in full. Each major release is supported until
> two newer majors exist, so 1.26 and 1.27 are the supported lines. Use Go for network services, CLIs, cloud
> infrastructure, dev tooling and game servers: simple language, fast compiles, static binaries, excellent concurrency.

## 0. Current version and what changed 2024-2026

| Version | Highlights (official release notes) |
|---|---|
| 1.22 (2024-02) | **per-iteration loop variables** (closures in loops no longer share one variable), `for i := range 10`, enhanced `net/http` routing patterns (`mux.HandleFunc("GET /items/{id}", h)`, `r.PathValue("id")`), `math/rand/v2` |
| 1.23 (2024-08) | **range-over-func iterators** (`iter.Seq[V]`, `iter.Seq2[K,V]`), `slices`/`maps` iterator helpers (`slices.Collect`, `maps.Keys`), `unique` package, timers garbage-collectable and unbuffered channels |
| 1.24 (2025-02) | **generic type aliases**, Swiss-table maps, `tool` directives in go.mod (`go get -tool`), `testing.B.Loop`, `os.Root` (directory-confined file access), `weak` pointers, `runtime.AddCleanup`, `crypto/mlkem`, FIPS 140-3 module, `encoding/json` `omitzero` |
| 1.25 (2025-08) | **container-aware GOMAXPROCS** (cgroup CPU limit, updated periodically), `testing/synctest` GA, `sync.WaitGroup.Go`, `runtime/trace.FlightRecorder`, experimental Green Tea GC (`GOEXPERIMENT=greenteagc`), experimental `encoding/json/v2` (`GOEXPERIMENT=jsonv2`), `go.mod` `ignore` directive, `go doc -http`, vet `waitgroup` and `hostport` analyzers, spec drops "core types" |
| 1.26 (2026-02) | **`new(expr)`** (`p := new(42)`; handy for optional pointer fields), generic types may reference themselves in constraints, **`go fix` rewritten as the home of modernizers**, **Green Tea GC on by default** (10-40% less GC overhead; opt out `GOEXPERIMENT=nogreenteagc` until 1.27), cgo call overhead about 30% lower, **`errors.AsType[T]`** (generic, type-safe `errors.As`), `crypto/hpke`, experimental `simd/archsimd`, `runtime/secret` and goroutine-leak profile, `go mod init` writes `go 1.(N-1).0`, pprof web UI defaults to flame graph |
| 1.27 (2026-08) | **generic methods** (methods may declare their own type parameters; interface methods may not), function type inference in more assignment contexts, **`encoding/json/v2` and `encoding/json/jsontext` released** (opt out with `GOEXPERIMENT=nojsonv2`), experimental portable **`simd`** package, goroutine-leak profile graduates, `asynctimerchan` GODEBUG removed, `go test` runs the `stdversion` vet check, `go mod tidy` merges require blocks, new go fix modernizers, bzr VCS support removed |

Answer rule: check the `go` line in `go.mod`. Language features are gated by it (e.g. per-iteration loop vars need
`go 1.22`+, generic methods need `go 1.27`+). The `toolchain` line (1.21+) can auto-download a newer toolchain.

## 1. Mental model

- Small language, explicit code, composition over inheritance, "a little copying is better than a little dependency".
- Garbage-collected with value semantics: structs and arrays are copied on assignment; slices, maps, channels,
  pointers, functions and interfaces are reference-like headers.
- Concurrency built in: goroutines (cheap green threads scheduled M:N) + channels; "share memory by communicating".
- Errors are values (`error` interface), returned as the last result; `panic` is for programmer errors.
- Interfaces are satisfied implicitly (structural typing).
- One formatting style (`gofmt`), one build tool (`go`), fast compilation to a static binary.
- Zero values are useful: `var mu sync.Mutex`, `var b bytes.Buffer`, empty slices work without initialization (but a
  nil map panics on write).

## 2. Type system

- Basic: `bool`, `string` (immutable bytes, UTF-8 by convention), `int`/`uint` (64-bit on 64-bit platforms),
  `int8..int64`, `uint8 (byte)`, `rune (int32)`, `float32/64`, `complex64/128`, `uintptr`.
- No implicit numeric conversions: `float64(i)`. Integer overflow wraps silently (defined behaviour).
- Composite: arrays `[4]int` (values), slices `[]int` (pointer, len, cap), maps `map[string]int`, structs, pointers
  (no pointer arithmetic outside `unsafe`), functions, channels `chan T`, `<-chan T`, `chan<- T`.
- Methods on any named type; pointer receivers `func (p *Player) Move()` vs value receivers.
- Interfaces: method sets; `any` = `interface{}`; type assertions `v, ok := x.(T)` and type switches.
- Embedding: struct embedding promotes fields/methods (not inheritance).
- Generics (1.18+): `func Map[T, U any](s []T, f func(T) U) []U`; constraints are interfaces
  (`cmp.Ordered`, `comparable`, `~int | ~float64`); generic types `type Stack[T any] struct{ items []T }`; generic
  type aliases (1.24); generic methods (1.27).
- Constants are untyped and arbitrary precision until used; `iota` for enums.
- No sum types: use interfaces with a sealed method, or a `switch` on concrete types.

## 3. Memory model and ownership

- Garbage collected (concurrent mark-sweep; Green Tea default since 1.26). Tune with `GOGC` and `GOMEMLIMIT`.
- Escape analysis decides stack vs heap; returning a pointer to a local is safe (`go build -gcflags=-m` shows
  escapes).
- **Slice aliasing**: slicing shares the backing array; `append` may or may not reallocate. Two slices from the same
  array can overwrite each other's data. Use `slices.Clone` or full slice expressions `s[a:b:b]` to force copies.
- Maps are reference types; iteration order is randomized; a nil map reads as empty but panics on assignment.
- Strings are immutable; `[]byte(s)` copies; `strings.Builder` for concatenation in loops.
- Finalizers are legacy; use `runtime.AddCleanup` (1.24) and explicit `Close()` with `defer`.
- `sync.Pool` for reusable buffers in hot paths.
- The Go memory model: a data race is a bug with undefined-ish results (can corrupt maps, tear interfaces); use `-race`.

## 4. Concurrency

```go
func fetchAll(ctx context.Context, urls []string) ([]string, error) {
    g, ctx := errgroup.WithContext(ctx) // golang.org/x/sync/errgroup
    g.SetLimit(8)
    results := make([]string, len(urls))
    for i, u := range urls { // per-iteration i and u since Go 1.22
        g.Go(func() error {
            body, err := fetch(ctx, u)
            if err != nil {
                return fmt.Errorf("fetch %s: %w", u, err)
            }
            results[i] = body // each goroutine writes its own index: no race
            return nil
        })
    }
    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}
```

- `go f()` starts a goroutine; always know how it stops (leaks are the #1 concurrency bug; 1.26/1.27 add a goroutine
  leak profile).
- Channels: unbuffered (synchronous hand-off) or buffered; `close(ch)` by the sender only; receiving from a closed
  channel yields the zero value (`v, ok := <-ch`); sending on a closed channel panics; nil channels block forever
  (useful in `select`).
- `select` with `ctx.Done()` for cancellation and `time.After`/timers for timeouts.
- `context.Context` is the first parameter of request-scoped functions; carry deadlines/cancellation, not optional
  parameters.
- `sync.Mutex`/`RWMutex` (do not copy after first use; `go vet` copylocks), `sync.Once`, `sync.OnceValue` (1.21),
  `sync.WaitGroup` with `wg.Go(func(){...})` (1.25), `sync/atomic` typed values (`atomic.Int64`), `errgroup`.
- Maps are **not** safe for concurrent writes ("fatal error: concurrent map writes" is unrecoverable); use a mutex or
  `sync.Map` for append-only caches.
- `testing/synctest` (1.25) tests concurrent code with a fake clock.

## 5. Error handling

- Return `error` last; check immediately: `if err != nil { return fmt.Errorf("loading %s: %w", name, err) }`.
- Wrap with `%w`; inspect with `errors.Is(err, fs.ErrNotExist)`, `errors.As(err, &target)` or
  `target, ok := errors.AsType[*MyErr](err)` (1.26); combine with `errors.Join`.
- Sentinel errors: `var ErrNotFound = errors.New("not found")`; custom types implementing `Error() string`.
- **Nil-interface trap**: returning a typed nil pointer as `error` makes `err != nil` true. Return a literal `nil`.
- `panic`/`recover`: recover only inside a deferred function; use at goroutine or request boundaries (net/http
  recovers handler panics). A panic in any goroutine without recover crashes the whole program.
- `defer f.Close()` for cleanup; for writes, check the `Close` error.

## 6. Toolchain, build and package management

- `go mod init example.com/app`, `go get pkg@version`, `go mod tidy`, `go build ./...`, `go run .`, `go test ./...`,
  `go vet ./...`, `go fix ./...` (1.26 modernizers), `gofmt -w .`, `go doc`, `go generate`, `go work init` (multi-module
  workspaces), `go install pkg@latest`.
- `go.mod`: `module`, `go 1.27`, `toolchain`, `require`, `replace`, `exclude`, `retract`, `tool` (1.24), `ignore`
  (1.25), `godebug`. `go.sum` holds checksums verified against the checksum database (sum.golang.org).
- Module proxy `GOPROXY=https://proxy.golang.org,direct`; private modules via `GOPRIVATE`.
- Semantic import versioning: v2+ modules have `/v2` in the import path.
- Cross-compile: `GOOS=windows GOARCH=amd64 go build`; `CGO_ENABLED=0` for fully static binaries.
- Build tags `//go:build linux && amd64`; embed files with `//go:embed static/*` into `embed.FS`.
- Linters: `go vet`, staticcheck, golangci-lint; security: **govulncheck** (reachability-aware vulnerability scan).
- PGO: put a CPU profile at `default.pgo` in the main package (2-14% typical gains).

## 7. Testing

- `xxx_test.go` files; `func TestX(t *testing.T)`, `t.Errorf`, `t.Fatalf`, `t.Run` subtests, `t.Parallel()`,
  `t.Cleanup`, `t.TempDir`, `t.Context()` (1.24).
- Table-driven tests are idiomatic.
- Benchmarks: `func BenchmarkX(b *testing.B) { for b.Loop() { ... } }` (1.24 `b.Loop` replaces `for i := 0; i < b.N;
  i++`); `go test -bench=. -benchmem`; compare with `benchstat`.
- Fuzzing: `func FuzzParse(f *testing.F) { f.Add("seed"); f.Fuzz(func(t *testing.T, s string) {...}) }`;
  `go test -fuzz=FuzzParse`.
- Examples `func ExampleX()` with `// Output:` comments are tests and docs.
- **Race detector**: `go test -race ./...` (needs cgo-capable toolchain); run it in CI.
- `httptest.NewServer` / `httptest.NewRecorder` for HTTP handlers; `testing/synctest` for time-dependent code.
- Coverage: `go test -cover -coverprofile=c.out` and `go tool cover -html=c.out`.

## 8. Idiomatic patterns

- Accept interfaces, return concrete types; keep interfaces small and defined by the consumer (`io.Reader`).
- Constructor functions `NewServer(cfg Config) *Server`; functional options `NewServer(WithPort(8080))`.
- Guard clauses and early returns instead of `else` nesting.
- `defer mu.Unlock()` right after `mu.Lock()`.
- Worker pools with a buffered job channel and `WaitGroup`; pipelines of channels; `errgroup` with `SetLimit`.
- `context` cancellation propagated to every blocking call.
- Iterators (1.23): `func (l *List[T]) All() iter.Seq[T]` and `for v := range l.All()`.
- `slices`, `maps`, `cmp`, `strings`, `bytes` helpers instead of hand-written loops (`slices.SortFunc`,
  `slices.Contains`, `min`/`max` builtins since 1.21, `clear` builtin).
- Package names short, lower-case, no `util`; exported identifiers are Capitalized.
- `log/slog` (1.21) for structured logging.

## 9. Top 30 pitfalls and compiler-error fixes

1. **`declared and not used: x`** - compile error. Use it or `_ = x`.
2. **`"pkg" imported and not used`** - remove the import (goimports does it).
3. **Nil map write**: `panic: assignment to entry in nil map` - initialize with `make(map[K]V)` or a literal.
4. **Nil-interface error trap** - `func f() error { var p *MyErr; return p }` returns non-nil. Return `nil` explicitly.
5. **Loop variable capture before 1.22** - all goroutines see the last value. Fixed by per-iteration semantics when
   `go.mod` says `go 1.22`+; old modules still behave the old way.
6. **`fatal error: concurrent map writes`** - guard maps with a mutex or use per-goroutine maps; cannot be recovered.
7. **Data races** - detect with `-race`; fix with mutexes, channels or atomics.
8. **Goroutine leaks** - goroutines blocked forever on a channel nobody reads. Fix: buffered channel of the right
   size, `select` on `ctx.Done()`, close channels, errgroup.
9. **`all goroutines are asleep - deadlock!`** - unbuffered send without a receiver, or `wg.Wait()` with a missing
   `Done()`. Fix: start the receiver first, use buffered channels, `wg.Go` (1.25).
10. **`send on closed channel` panic** - only the sender closes, exactly once.
11. **Slice aliasing with append** - two slices share a backing array and clobber each other. Fix: `slices.Clone`,
    `append(s[:len(s):len(s)], x)`.
12. **Modifying a copy in `for _, v := range items`** - `v` is a copy; mutate `items[i]` or range over indices or
    pointers.
13. **`cannot use x (variable of type int) as float64 value`** - explicit conversion `float64(x)`.
14. **`invalid operation: mismatched types`** - e.g. `time.Duration * int`: convert `time.Duration(n) * time.Second`.
15. **`X does not implement Y (method M has pointer receiver)`** - pass `&x`, or use value receivers consistently.
16. **`missing return`** - add a final return or `panic("unreachable")`.
17. **`import cycle not allowed`** - restructure packages; move shared types into a lower package or define
    interfaces at the consumer.
18. **`undefined: X`** - unexported (lower-case) identifier from another package, or file excluded by build tags.
19. **`defer` in a loop** - defers run at function end, holding files open. Fix: wrap the loop body in a function.
20. **`defer` argument evaluation** - arguments are evaluated when `defer` is executed, not when it runs.
21. **Ignoring `Close` error on writes** - data loss unnoticed. Check `err := f.Close()`.
22. **`time.After` in a long-running `select` loop** - allocates a timer each iteration (garbage-collectable since
    1.23 but still wasteful). Use one `time.NewTimer`/`Ticker`.
23. **Copying a `sync.Mutex`** (passing structs by value) - `go vet` copylocks; use pointers.
24. **HTTP client without timeout** - `http.Get` with the default client can hang forever. Use `&http.Client{Timeout:
    10 * time.Second}` or request contexts. Always `defer resp.Body.Close()`.
25. **String iteration** - `for i, r := range s` yields runes and byte offsets; `s[i]` is a byte; `len(s)` is bytes.
    Use `utf8.RuneCountInString`.
26. **Integer overflow wraps silently** - check bounds; `math.MaxInt64`.
27. **Shadowing with `:=`** - `err` re-declared in an inner scope; outer `err` stays nil. Use `=` or vet's shadow.
28. **JSON field tags and unexported fields** - unexported fields are ignored by `encoding/json`; tags
    `json:"name,omitempty"`. With json/v2 (1.27) some defaults differ (case-sensitive matching, nil slice as `[]`):
    check `GOEXPERIMENT=nojsonv2` if behaviour changed after upgrading.
29. **`for` over a channel never ends** if nobody closes it.
30. **Panics in goroutines crash the process** - recover inside the goroutine if it handles untrusted work.
31. **Generic method mistakes on older toolchains** - `methods cannot have type parameters` before 1.27; in 1.27
    interface methods still cannot.

## 10. Performance

- Profile first: `net/http/pprof` or `go test -cpuprofile`/`-memprofile`; `go tool pprof -http=:8080` (flame graph
  default in 1.26); `runtime/trace` and the FlightRecorder (1.25).
- Reduce allocations: preallocate slices (`make([]T, 0, n)`), reuse buffers, `strings.Builder`, `sync.Pool`, avoid
  `interface{}` boxing in hot paths, check escape analysis (`-gcflags=-m`).
- GC tuning: `GOGC` (default 100), `GOMEMLIMIT` for container memory limits; container-aware GOMAXPROCS (1.25).
- PGO (`default.pgo`), Green Tea GC (default 1.26), experimental SIMD packages (1.26/1.27 behind `GOEXPERIMENT=simd`).
- cgo calls cost far more than Go calls (lower since 1.26, still significant); batch work across the boundary.
- Benchmark with `b.Loop()` and `benchstat`.

## 11. Security

- Memory-safe (bounds-checked, GC) except `unsafe`, cgo and data races (a racy program can corrupt memory).
- **SQL injection**: always use placeholders: `db.QueryContext(ctx, "SELECT name FROM users WHERE id = ?", id)`
  (`$1` for PostgreSQL drivers). Never `fmt.Sprintf` user input into SQL.
- **XSS**: `html/template` escapes context-aware; `text/template` does not. Never convert user input to
  `template.HTML`.
- **Command injection**: `exec.CommandContext(ctx, "git", "log", userArg)` passes argv without a shell; never
  `exec.Command("sh", "-c", userInput)`. Since 1.19, `exec` does not run binaries found relative to the current
  directory via PATH (`exec.ErrDot`).
- **Path traversal**: use `os.Root` (1.24) / `os.OpenInRoot` to confine file access, or `filepath.IsLocal`.
- SSRF and timeouts: restrict outbound HTTP, set timeouts and size limits (`http.MaxBytesReader`, `io.LimitReader`).
- TLS: `crypto/tls` secure defaults; post-quantum hybrid key exchange on by default in recent releases; FIPS 140-3
  mode (1.24).
- Supply chain: `go.sum` + checksum DB, **govulncheck** in CI, minimal dependencies, `GOFLAGS=-mod=readonly`.
- Secrets: `runtime/secret` is experimental (1.26); otherwise avoid copies of key material.

## 12. Game-development usage

- **Ebitengine** (2D; latest v2.10.5, 2026-10-09 on GitHub): implement `ebiten.Game` (`Update() error`,
  `Draw(screen *ebiten.Image)`, `Layout(w, h int) (int, int)`) and call `ebiten.RunGame(g)`; fixed 60 TPS update by
  default; runs on desktop, mobile, web (WASM) and Nintendo Switch.
- **raylib-go**, **Pixel**, **G3N** (3D), **Oak**; Go is more common for **game servers**, matchmaking, lobby and
  backend services (gRPC, WebSockets with `nhooyr.io/websocket`/`coder/websocket`, Nakama's runtime supports Go
  plugins), tooling and asset pipelines.
- Embedding Lua: **gopher-lua** (Lua 5.1 VM in pure Go), **go-lua**; no maintained pure-Go Luau VM is known
  (unverified); cgo bindings to the Luau C API are possible.
- GC pauses are short (sub-millisecond typical) but allocation in per-frame code still matters: reuse slices and
  images.

## 13. Cheat sheet: Go vs Luau

| Concept | Luau | Go |
|---|---|---|
| Variable | `local x = 1` | `x := 1` / `var x int = 1` |
| Constant | `local MAX = 10` | `const Max = 10` |
| Nil | `nil` | `nil` for pointers, slices, maps, channels, funcs, interfaces; zero values otherwise |
| Number | `number` | `int`, `int64`, `float64`, explicit conversions |
| Integer division | `7 // 2 == 3` floored | `7 / 2 == 3` truncated (`-7 / 2 == -3`) |
| Indexing | 1-based | 0-based, bounds-checked (panic) |
| Array | `{1, 2, 3}` | `[]int{1, 2, 3}` slice |
| Map | `{a = 1}` | `map[string]int{"a": 1}` |
| Length | `#t` | `len(s)` |
| Append | `table.insert(t, v)` | `s = append(s, v)` (must reassign) |
| String concat | `a .. b` | `a + b`, `strings.Builder` |
| Format | `string.format("%d", n)` | `fmt.Sprintf("%d", n)` |
| Function | `local function f(a)` | `func f(a int) int` |
| Closure | upvalues | closures capture variables by reference |
| Multiple returns | `return a, b` | `return a, b` (same idea) |
| Module | `require` | `import "example.com/pkg"` |
| Class | metatable | struct + methods; interfaces |
| Method | `obj:M()` | `obj.M()` |
| Error raise | `error("x")` | `return fmt.Errorf("x")` |
| Error catch | `pcall` | `if err != nil`; `recover()` for panics |
| Coroutine | `coroutine`, `task.spawn` | `go f()`, channels |
| Wait | `task.wait(1)` | `time.Sleep(time.Second)` |
| Types | gradual | static, inferred locally |
| Generics | `<T>` | `[T any]` type parameters |
| Iteration | `for k, v in pairs(t)` | `for k, v := range m` (random order) |
| Equality | `==` | `==` for comparable types; `reflect.DeepEqual`/`slices.Equal` |
| Memory | GC | GC |
| Truthiness | `nil`/`false` falsy | only `bool` in conditions |

## 14. Sources

Releases:
- https://go.dev/doc/devel/release - release history (1.27.0 on 2026-08-19, 1.27.2 on 2026-10-08)
- https://go.dev/doc/go1.27 - generic methods, json/v2, simd
- https://go.dev/doc/go1.26 - new(expr), Green Tea default, go fix, errors.AsType
- https://go.dev/doc/go1.25 - GOMAXPROCS, synctest, WaitGroup.Go
- https://go.dev/doc/go1.24 - generic aliases, tool directives, os.Root, b.Loop
- https://go.dev/doc/go1.23 - range-over-func iterators
- https://go.dev/doc/go1.22 - per-iteration loop variables
- https://go.dev/blog/loopvar-preview - loop variable change explained

Language and stdlib:
- https://go.dev/ref/spec - language specification
- https://go.dev/ref/mem - memory model
- https://go.dev/doc/effective_go - idioms
- https://go.dev/blog/go1.13-errors - error wrapping
- https://pkg.go.dev/errors - errors.Is/As/AsType/Join
- https://pkg.go.dev/context - context
- https://pkg.go.dev/golang.org/x/sync/errgroup - errgroup
- https://go.dev/doc/faq#nil_error - nil error interface trap

Tooling, testing, security:
- https://go.dev/ref/mod - modules reference
- https://go.dev/doc/tutorial/fuzz - fuzzing
- https://go.dev/doc/articles/race_detector - race detector
- https://go.dev/doc/pgo - profile-guided optimization
- https://go.dev/doc/security/best-practices - security best practices
- https://go.dev/doc/security/vuln/ - govulncheck
- https://go.dev/doc/database/sql-injection - SQL injection
- https://pkg.go.dev/html/template - contextual escaping
- https://go.dev/blog/osroot - os.Root traversal-resistant file APIs

Game development:
- https://ebitengine.org/ - Ebitengine
- https://github.com/hajimehoshi/ebiten/releases - v2.10.5
- https://github.com/yuin/gopher-lua - Lua VM in Go
