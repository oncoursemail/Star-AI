# Software engineering fundamentals

Researched 2026-10-13. Language-independent. Sources at the end.

## 1. Design principles and patterns

- **Principles that pay off**: high cohesion / low coupling; information hiding (Parnas: hide decisions likely to
  change behind interfaces); make illegal states unrepresentable (types, enums, one source of truth); prefer
  composition over inheritance; explicit dependencies (pass them in) over globals; functional core / imperative shell
  (pure logic that is easy to test, thin I/O layer around it); YAGNI and "rule of three" before abstracting.
- **SOLID**, read pragmatically: single responsibility = one reason to change; open/closed = extend through data or
  new implementations rather than editing switch statements everywhere; Liskov = subtypes must honour the contract;
  interface segregation = small interfaces; dependency inversion = core logic depends on abstractions it owns.
- **Patterns worth recognising** (Gang of Four and game-specific):
  - Creational: factory (data-driven spawning), builder, object pool (reuse bullets/particles; reset state on reuse).
  - Structural: adapter (wrap third-party APIs), facade (one entry point to a subsystem), decorator, flyweight (shared
    intrinsic data such as mesh/stat definitions, per-instance extrinsic state), proxy.
  - Behavioural: observer/events, command (input, undo, replay, networking), state, strategy, template method,
    visitor (use sparingly), iterator, mediator.
  - Game-specific (Nystrom): game loop, update method, double buffer, component, event queue, service locator,
    dirty flag, spatial partition, type object, bytecode, subclass sandbox.
- **Anti-patterns**: god objects/managers that know everything, singletons as hidden globals, stringly-typed APIs,
  deep inheritance, premature generalisation, copy-paste divergence, boolean parameters that switch behaviour.

## 2. Testing strategy

- **Purpose**: tests are executable specifications and a safety net for change. Optimise for fast feedback,
  determinism and diagnosability.
- **Shape**: many fast unit tests of pure logic, fewer integration tests across real boundaries (database, network,
  engine), a few end-to-end/smoke tests of critical paths. ("Test pyramid"; "testing trophy" for UI-heavy apps:
  integration-weighted.) Google sizes tests by resources used: small (single process, no I/O), medium (localhost),
  large (anything).
- **Kinds**: example-based unit tests; **property-based tests** (generate inputs, assert invariants: sorting output is
  ordered and a permutation; serialization round-trips); **characterization / golden tests** (pin current behaviour
  before refactoring legacy code: Feathers); **snapshot tests** (cheap, but review diffs honestly); **fuzzing**
  (parsers, network messages; coverage-guided: libFuzzer, AFL++, OSS-Fuzz); **mutation testing** (measures whether tests
  detect injected bugs); **contract tests** between services; **performance/regression benchmarks** with thresholds;
  **soak tests** for leaks.
- **Game-specific testing**: separate simulation from presentation so logic runs headless; deterministic replays
  (record inputs + seed, replay and compare checksums) as regression tests; automated bots/playtest agents; debug
  cheats gated to test builds/servers; visual regression via screenshot comparison with tolerances; multi-client
  network tests with simulated latency and loss.
- **Good test properties**: one behaviour per test, arrange-act-assert, descriptive names, no sleeps (inject clocks,
  use fake timers), no order dependence, no shared mutable fixtures, hermetic (no network unless it is the point).
  **Flaky tests** are bugs: quarantine and fix, never retry silently.
- **Test-first / TDD**: write the failing test for the bug or behaviour first (red), make it pass (green), refactor.
  At minimum, every bug fix gets a regression test that fails without the fix.
- **Coverage** is a smell detector, not a goal: high coverage with weak assertions proves little.

## 3. Debugging methodology

1. **Reproduce** reliably (same input, seed, build); shrink to a minimal case. If it is intermittent, increase the
   odds (stress, loops, sanitizers, fixed seed, slowed timing) and log enough to catch it.
2. **Read the actual error** fully: message, stack trace, first error not the last, line numbers, the value that was
   nil/NaN.
3. **Form a hypothesis**, predict what you will observe if it is true, and test it with the cheapest experiment
   (print/log, breakpoint, assertion, watchpoint). Change one thing at a time.
4. **Bisect**: in code (comment out halves), in data (halve the input), in history (`git bisect run <test>`: log2(n)
   steps), in configuration.
5. **Find the root cause**: trace the bad value back to where it was first wrong ("5 whys"); fix the cause, not the
   symptom; check for the same bug elsewhere.
6. **Prove the fix**: the reproduction now passes, a regression test exists, nothing else changed.
- Tools: debugger (conditional breakpoints, data breakpoints), sanitizers (ASan, UBSan, TSan), valgrind, record/replay
  debuggers (rr, WinDbg Time Travel), structured logging with correlation ids, in-game debug draw/overlays, network
  conditioners.
- Heisenbugs (disappear under observation) are usually races, uninitialized memory or timing dependencies.
- "Works on my machine": diff environments (versions, config, data, locale, time zone, file system case sensitivity,
  line endings).

## 4. Profiling and performance

- **Measure before optimising; measure after.** Define the metric (frame time p50/p99, not average FPS; memory peak;
  load time; server tick time; bandwidth).
- Methodologies: Brendan Gregg's **USE method** (for every resource: Utilization, Saturation, Errors), **RED** for
  services (Rate, Errors, Duration), workload characterization, drill-down analysis.
- Tools: sampling profilers (low overhead, statistical: perf, VTune, Superluminal, Instruments, py-spy), instrumentation
  profilers with zones (Tracy, Unreal Insights, Unity Profiler, Roblox MicroProfiler), GPU capture tools (RenderDoc,
  PIX, Nsight), memory profilers, flame graphs.
- Typical wins in order: do less work (algorithmic complexity, culling, caching, early outs, lower update rates),
  do it less often (amortize, time-slice, event-driven instead of polling), do it in bulk (batching, SoA, data
  locality), avoid allocation in hot loops (GC spikes: pool, reuse buffers), parallelize (jobs), then micro-optimize.
- Amdahl's law: speedup is limited by the serial fraction. Latency vs throughput are different goals.
- Benchmarks: warm up, repeat, report variance, pin the build/config, beware dead-code elimination and caches.

## 5. Concurrency

- **Shared mutable state is the root problem.** Options: don't share (message passing, actors, per-thread data),
  don't mutate (immutable snapshots), or synchronize (locks, atomics).
- **Hazards**: data races (undefined behaviour in C/C++), race conditions (check-then-act, read-modify-write lost
  updates), deadlock (cycle of lock waits: Coffman conditions; fix with a global lock order or try-lock with
  back-off), livelock, starvation, priority inversion, false sharing (pad hot per-thread counters to cache lines).
- **Memory model**: atomics with acquire/release for publication; sequential consistency by default; lock-free code is
  hard to get right: prefer well-tested libraries.
- **Game engines**: job systems with dependency graphs (fork/join, work stealing: Naughty Dog fibers, Unity Job
  System, Unreal Task Graph), double-buffered state between simulation and render threads, read/write sets per system
  in ECS so the scheduler can parallelize safely.
- **Async/await and coroutines**: concurrency without threads; still racy across `await` points (state may change
  while suspended). Always handle cancellation and timeouts; avoid fire-and-forget without error handling.
- **Distributed systems**: networks fail partially; use idempotency keys, retries with exponential back-off and
  jitter, timeouts on every call, at-least-once delivery with deduplication, optimistic concurrency (version numbers /
  compare-and-swap, `UpdateAsync`-style transforms), and avoid distributed transactions where you can.
- Tools: ThreadSanitizer, deterministic schedulers/model checkers (loom, Relacy), stress tests.

## 6. Security

- **OWASP Top 10:2025** (released November 2025): A01 Broken Access Control (now including SSRF), A02 Security
  Misconfiguration, A03 Software Supply Chain Failures (new), A04 Cryptographic Failures, A05 Injection, A06 Insecure
  Design, A07 Authentication Failures, A08 Software or Data Integrity Failures, A09 Security Logging and Alerting
  Failures, A10 Mishandling of Exceptional Conditions (new).
- **OWASP ASVS 5.0** (May 2025, ~350 requirements in 17 chapters) is the checklist for verifying an application.
- Habits:
  - Validate input at trust boundaries with allowlists (type, length, range, format); encode output for its context
    (HTML, SQL, shell, URL). Use parameterized queries / prepared statements: never build SQL, shell commands or
    file paths by string concatenation with user data. Identifiers that cannot be parameterized (column names) must
    come from an allowlist.
  - Authorization on the server for every request (deny by default, check object ownership: IDOR is A01).
  - Secrets out of source control and clients; rotate; least privilege for tokens and service accounts.
  - Use vetted crypto libraries and modern defaults (TLS 1.3, AEAD, Argon2id/bcrypt/scrypt for passwords); never
    invent crypto.
  - Fail closed; handle exceptions without leaking internals (A10); log security events without logging secrets.
  - Supply chain: pin and verify dependencies (lockfiles, hashes), SBOMs, signed artifacts, provenance (SLSA levels),
    review new dependencies, watch for typosquatting; protect CI secrets and restrict workflow permissions.
  - Threat modelling (STRIDE: Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of
    privilege) at design time.
- **LLM/agent-specific** (relevant to STAR itself): treat tool output, web pages and documents as untrusted data
  (prompt injection); least-privilege tools; human approval for irreversible actions (OWASP Top 10 for LLM
  Applications 2025).

## 7. API design

- Design from the caller's use cases; name things for what they mean in the domain; keep the surface small; make the
  common case easy and the dangerous case explicit.
- Consistency beats cleverness: one naming style, one error model, one pagination style.
- **Contracts**: document preconditions, postconditions, errors, thread-safety, ownership/lifetime, units (seconds vs
  milliseconds, degrees vs radians) and nullability; encode them in types where possible.
- **Errors**: distinguish caller errors from transient failures; return structured errors with stable codes; make
  retries safe (idempotency).
- **Remote APIs**: resource-oriented design (Google AIP-121: nouns + standard methods + custom methods), REST/HTTP
  semantics (GET safe, PUT/DELETE idempotent), pagination tokens, field masks for partial updates, versioning
  strategy (additive changes; never repurpose a field; deprecate with a timeline), rate limits, authentication and
  authorization per method. gRPC/protobuf for typed internal services; GraphQL when clients need flexible shapes.
- **Libraries**: semantic versioning (MAJOR for breaking changes); Hyrum's law (every observable behaviour will be
  depended on); avoid leaking implementation types.

## 8. Version control

- Small, focused commits with messages that explain why; one logical change per commit; never commit secrets or
  generated binaries (Git LFS for large assets; game projects often use Perforce or Plastic/Unity Version Control
  because of binary assets and file locking).
- Branching: trunk-based development with short-lived branches and feature flags is associated with higher delivery
  performance (DORA); long-lived branches cause painful merges.
- Code review: review for correctness, design, tests and readability; small PRs get better reviews.
- Useful commands: `git bisect`, `git blame -w -C`, `git log -S` (pickaxe), `git worktree`, `git reflog` (recovery).
- Never rewrite shared history (force-push to shared branches); protect main; require CI to pass.

## 9. CI/CD and delivery

- Every change: build, static analysis/linters, unit tests, integration tests, packaging, security scanning
  (dependency audit, secret scanning, SAST), then deploy to staging; promote the same artifact to production.
- Reproducible builds: pinned toolchains and dependencies, hermetic build steps, caches keyed by inputs.
- Fast feedback: run the cheapest checks first, parallelize, shard tests, keep the main build under ~10 minutes.
- Release safely: feature flags, canary/staged rollouts, automatic rollback on health regression, database migrations
  that are backward-compatible (expand/contract).
- **DORA metrics** (2025 report "State of AI-assisted Software Development"): deployment frequency, lead time for
  changes, change failure rate, failed deployment recovery time, and the newly added rework rate. The 2025 report found
  AI adoption now correlates with higher throughput but still with more instability: AI "amplifies" existing practices,
  so strong testing and small batches matter more, not less.
- Game-specific: nightly builds per platform, automated smoke tests (boot, load each level, run a bot), asset
  validation in CI (naming, texture budgets, missing references), performance capture on reference hardware.

## Sources
- Robert Nystrom, *Game Programming Patterns* (free online): https://gameprogrammingpatterns.com/contents.html
- Refactoring.Guru, design patterns catalogue (secondary): https://refactoring.guru/design-patterns
- David Parnas, "On the Criteria To Be Used in Decomposing Systems into Modules" (1972): https://dl.acm.org/doi/10.1145/361598.361623
- Winters, Manshreck, Wright, *Software Engineering at Google* (free online): https://abseil.io/resources/swe-book
- Martin Fowler, "The Practical Test Pyramid" (Ham Vocke): https://martinfowler.com/articles/practical-test-pyramid.html
- Michael Feathers, *Working Effectively with Legacy Code* (characterization tests) summary: https://michaelfeathers.silvrback.com/characterization-testing
- Hypothesis (property-based testing) documentation: https://hypothesis.readthedocs.io/
- Google OSS-Fuzz: https://google.github.io/oss-fuzz/
- David J. Agans, *Debugging: The 9 Indispensable Rules*: https://debuggingrules.com/
- Git documentation, `git bisect`: https://git-scm.com/docs/git-bisect
- Brendan Gregg, "The USE Method": https://www.brendangregg.com/usemethod.html ; Flame graphs: https://www.brendangregg.com/flamegraphs.html
- Tracy profiler: https://github.com/wolfpld/tracy
- Christian Gyrling, "Parallelizing the Naughty Dog Engine Using Fibers" (GDC 2015): https://gdcvault.com/play/1022186/Parallelizing-the-Naughty-Dog-Engine
- Herb Sutter, "atomic<> Weapons" (C++ memory model talk): https://herbsutter.com/2013/02/11/atomic-weapons-the-c-memory-model-and-modern-hardware/
- Martin Kleppmann, *Designing Data-Intensive Applications* (book site): https://dataintensive.net/
- AWS Builders' Library, "Timeouts, retries and backoff with jitter": https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- OWASP Top 10:2025: https://owasp.org/Top10/2025/
- OWASP ASVS (5.0.0, May 2025): https://owasp.org/www-project-application-security-verification-standard/
- OWASP Cheat Sheet Series (SQL injection prevention, input validation, etc.): https://cheatsheetseries.owasp.org/
- OWASP Top 10 for LLM Applications 2025: https://genai.owasp.org/llm-top-10/
- SLSA supply-chain levels: https://slsa.dev/
- Microsoft, STRIDE threat modeling: https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats
- Google API Improvement Proposals (AIP-121 resource-oriented design): https://google.aip.dev/121
- Semantic Versioning 2.0.0: https://semver.org/
- Hyrum's Law: https://www.hyrumslaw.com/
- Trunk-based development: https://trunkbaseddevelopment.com/
- DORA research and metrics: https://dora.dev/ ; DORA 2025 year in review: https://dora.dev/insights/dora-2025-year-in-review/
- Martin Fowler, "Continuous Integration": https://martinfowler.com/articles/continuousIntegration.html
