---
name: lang-go
description: Go (1.27, August 2026) errors, goroutines and channels, data races, modules, testing and recent language changes. Use for Go code, go build/vet errors, deadlocks, nil map panics, go.mod questions, or Go game servers and Ebitengine.
---
# Go 1.27
- Check the `go` line in go.mod: features are gated by it. 1.22 per-iteration loop variables; 1.23 range-over-func iterators (`iter.Seq`); 1.24 generic type aliases, `tool` directives, `os.Root`, `b.Loop()`; 1.25 container-aware GOMAXPROCS, `sync.WaitGroup.Go`, `testing/synctest`; 1.26 `new(expr)`, `errors.AsType[T]`, Green Tea GC by default, `go fix` modernizers; 1.27 generic methods (not on interfaces) and `encoding/json/v2`.
- Errors are values: `if err != nil { return fmt.Errorf("loading %s: %w", name, err) }`; inspect with `errors.Is`, `errors.As` / `errors.AsType`; never compare error strings.
- Nil-interface trap: returning a typed nil pointer as `error` is non-nil. Return a literal `nil`.
- Maps: a nil map panics on write (`make(map[K]V)` first); maps are not safe for concurrent writes ("fatal error: concurrent map writes" cannot be recovered): guard with `sync.Mutex`.
- Every goroutine needs a way to stop: pass `context.Context`, `select` on `ctx.Done()`, close channels from the sender only, use `errgroup` (with `SetLimit`) or `wg.Go`. "all goroutines are asleep - deadlock!" means an unmatched send/receive or a missing `Done`.
- Run `go test -race ./...` in CI; races are bugs even when tests pass.
- Slices share backing arrays: `append` may or may not copy; use `slices.Clone` before handing out a slice you will mutate. `for _, v := range s` gives copies; mutate `s[i]`.
- `defer` runs at function exit, not loop iteration: wrap loop bodies that open files in a function. Check `Close()` errors on writes.
- HTTP: set client timeouts (`&http.Client{Timeout: 10 * time.Second}`), `defer resp.Body.Close()`, limit body sizes.
- Compile errors: "declared and not used", "imported and not used", explicit numeric conversions (`float64(n)`), "missing return", "import cycle not allowed" (move shared types down a level).
- Tools: `go mod tidy`, `go vet ./...`, `go fix ./...`, `gofmt`, `staticcheck`, `govulncheck ./...`, `go test -fuzz`, `pprof`.
- Security: SQL placeholders (`db.QueryContext(ctx, "... WHERE id = ?", id)`), `html/template` (never `text/template` for HTML), `exec.CommandContext(ctx, "git", arg)` without a shell, `os.Root` against path traversal.
- Games: Ebitengine (`Update`/`Draw`/`Layout`, `ebiten.RunGame`); Go is common for game servers and matchmaking.
