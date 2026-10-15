# Ruby for STAR (research, checked 2026-10-13)

Status: current stable line is **Ruby 4.0** (4.0.0 released 2025-12-25 [1]; latest patch found 4.0.6, 2026-07-14 [2]). Ruby 3.4 is the previous line and still maintained. A Ruby 4.1 preview was **unverified as of 2026-10-13** (none found on ruby-lang.org news). RBS 4.0 (inline annotations, experimental) and Steep 2.0 dates come from secondary sources and are marked unverified where used.

Ruby 4.0 is *not* a big-break release like Python 3: the version jump marks Ruby's 30th anniversary. Most 3.4 code runs unchanged. The breaking items are listed in section 12.

---

## 1. Mental model

- **Everything is an object, every operation is a method call.** `1 + 2` is `1.+(2)`; `nil` is the singleton instance of `NilClass`; classes are objects of class `Class`. There are no primitives (Integer is still an object, though small ints are tagged immediates internally).
- **Message passing, open classes.** Any class (including `String`, `Integer`) can be reopened and modified at runtime ("monkey patching"). Prefer **refinements** (`refine String do ... end` + `using`) to scope such changes lexically.
- **Blocks are the core abstraction.** Almost every iteration, resource management (`File.open { }`), transaction and DSL uses a block. A block is not an object until captured (`&blk`) or converted to a `Proc`/`lambda`.
- **Duck typing.** "If it responds to `#each`, it's enumerable." Type checks are usually `respond_to?` or pattern matching, not `is_a?`.
- **Implicit returns.** The last evaluated expression is the return value of a method or block. `return` inside a *proc/block* returns from the *enclosing method*; inside a *lambda* it returns from the lambda.
- **Truthiness:** only `nil` and `false` are falsy. `0`, `""`, `[]` are truthy (same as Luau).
- **Interpreter:** CRuby (MRI) is a bytecode VM (YARV) with a Global VM Lock (GVL): threads run Ruby code one at a time but release the lock on blocking I/O. Parallel Ruby code needs **Ractors** (experimental) or processes. JITs: **YJIT** (production, Rust, lazy basic-block versioning) and **ZJIT** (new method JIT in 4.0, not yet production) [1].
- **Parser:** **Prism** is the default parser since Ruby 3.4 (replaced parse.y-based compilation path); it is also the parser library used by tools (RuboCop, Sorbet, Ruby LSP) [3].

## 2. Type system

- Dynamically and strongly typed: `"1" + 1` raises `TypeError (no implicit conversion of Integer into String)`; no silent coercion except numeric tower (`1 + 1.5 => 2.5`).
- Implicit conversion protocols: `to_str`, `to_ary`, `to_hash`, `to_proc` (implicit, "I *am* a string") vs `to_s`, `to_a`, `to_h` (explicit, "I can be shown as"). Return a real `String` from `to_s` or interpolation breaks.
- **Static typing is optional and external**:
  - **RBS** (official signature language, ships with Ruby as a bundled gem). `.rbs` files in `sig/`. RBS 4.0 adds experimental *inline* annotations in Ruby comments (secondary source, 2026-03; unverified details) [4].
  - **Steep**: type checker for RBS. Steep 2.0 reportedly can check inline annotations with `check(inline: true)` in the Steepfile (secondary source, unverified) [4].
  - **Sorbet** (Stripe): `sig { params(x: Integer).returns(String) }` DSL plus `.rbi` files; gradual levels `# typed: false|true|strict|strong`. `tapioca` generates RBIs for gems. Sorbet also accepts RBS-style comment signatures (experimental).
  - **TypeProf**: inference-based, powers editor hints.
- Pattern matching (`case/in`, Ruby 3.0+) gives structural checks:

```ruby
case response
in {status: 200, body: String => body} then body
in {status: 404} then nil
in {status: Integer => code} if code >= 500 then raise ServerError, code
end
```

- `Data` (3.2+) defines immutable value objects: `Point = Data.define(:x, :y)`; `Struct` is the mutable counterpart (keyword_init by default since 3.2).
- Frozen string literals: in Ruby 3.4, mutating a string literal in a file *without* the `# frozen_string_literal: true` magic comment emits a deprecation warning when deprecation warnings are on ("chilled strings"). The plan is for literals to become frozen by default in a future version; keep the magic comment and use `+""` / `String.new` / `dup` for mutable buffers.

## 3. Runtime, concurrency and async model

| Mechanism | Parallel CPU? | Use for |
|---|---|---|
| `Thread` | No (GVL), yes for blocking I/O | I/O-bound work, background jobs inside one process |
| `Fiber` | No; cooperative | Generators (`Enumerator`), coroutine-style code |
| `Fiber::Scheduler` (3.0+) | No; non-blocking I/O | `async` gem, Falcon server. Blocking calls (`sleep`, `IO#read`, `Net::HTTP`) yield to the scheduler automatically |
| `Ractor` | Yes | CPU-parallel pure Ruby; objects must be shareable (deeply frozen) or moved |
| `Process.fork` / Puma workers | Yes | Web servers, job runners |

- **Ractor in 4.0** [1]: new `Ractor::Port` (`send`/`<<`, `receive`, `close`), every Ractor has `default_port`; `Ractor#join`, `Ractor#value`, `Ractor#monitor`; `Ractor.yield`, `Ractor#take`, `close_incoming/outgoing` were **removed**; `Ractor.shareable_proc`/`shareable_lambda`. Still experimental; the core team aims to drop the label in 2026.

```ruby
r = Ractor.new { (1..10_000_000).sum }   # runs in parallel
puts r.value                             # 4.0: #value (old #take removed)
```

- **Fibers vs Luau coroutines:** `Fiber.new { |x| y = Fiber.yield(x * 2); y }` / `fiber.resume(1)` mirrors `coroutine.create`/`resume`/`yield`. `Enumerator` wraps fibers: `e = Enumerator.new { |y| y << 1; y << 2 }; e.next`.
- **async gem** (Samuel Williams) is the de-facto structured concurrency library:

```ruby
require "async"
require "async/http/internet"
Async do |task|
  internet = Async::HTTP::Internet.new
  urls.map { |u| task.async { internet.get(u).read } }.map(&:wait)
ensure
  internet&.close
end
```

- Ruby 4.0 Fiber scheduler gains `fiber_interrupt`, `yield`, `io_close` hooks; `Thread#raise`/`Fiber#raise` accept `cause:` [1].
- **Ruby::Box** (4.0, experimental, `RUBY_BOX=1`): isolates monkey patches, globals, class definitions and loaded libraries per box [1].

## 4. Tooling and package management

- **Version managers:** `rbenv`, `asdf`/`mise`, `chruby`; on Windows **RubyInstaller** (with MSYS2 DevKit for native gems). Ruby 4.0 on Windows needs MSVC 14.0+ when built with MSVC [1].
- **RubyGems** (`gem install`) + **Bundler** (`Gemfile`, `Gemfile.lock`, `bundle install`, `bundle exec`). Ruby 4.0 ships RubyGems/Bundler 4.0.x [1]. Always run project commands via `bundle exec` (or binstubs `bin/rails`) so the locked versions load.
- Gemfile basics:

```ruby
source "https://rubygems.org"
ruby "~> 4.0"
gem "rails", "~> 8.0"
gem "puma"
group :development, :test do
  gem "rspec-rails"
  gem "rubocop", require: false
end
```

- Linters/formatters: **RuboCop** (+ `rubocop-rails`, `rubocop-rspec`), **Standard** (zero-config RuboCop), **Ruby LSP** (Shopify, Prism-based) for editors.
- Default vs bundled gems: since 3.4/4.0 many stdlib libraries became *bundled gems* (must be in the Gemfile under Bundler): in 4.0 `ostruct`, `pstore`, `benchmark`, `logger`, `rdoc`, `irb`, `reline`, `readline`, `fiddle`, `win32ole` [1]; in 3.4 `base64`, `bigdecimal`, `csv`, `drb`, `mutex_m`, `nkf`, `getoptlong`, `observer`, `racc`, `resolv-replace`, `rinda`, `syslog` [3]. If `require "csv"` fails under Bundler, add `gem "csv"`.
- `Set` is a core class in 4.0; `Pathname` promoted to core; `SortedSet` removed (use `sorted_set` gem) [1].
- Debugging: `debug` gem (`binding.break`, `rdbg`), `irb` with `binding.irb`; ErrorHighlight shows the exact failing call column.

## 5. Testing

- **Minitest** (bundled; 6.0 in Ruby 4.0 [1]) — xUnit and spec styles; Rails default.
- **RSpec** — BDD DSL (`describe`, `it`, `expect(x).to eq(y)`, `let`, `before`). Most popular in apps.
- **test-unit** (bundled) — classic.
- Doubles: `rspec-mocks`, Minitest `Mock`/`stub`; HTTP: `webmock`, `vcr`. Coverage: `simplecov`. Property-based: `prop_check`, `rantly`.

```ruby
# test/score_test.rb
require "minitest/autorun"
class ScoreTest < Minitest::Test
  def test_adds_points
    s = Score.new
    s.add(10)
    assert_equal 10, s.total
  end
end
```

```ruby
RSpec.describe Score do
  subject(:score) { described_class.new }
  it "adds points" do
    expect { score.add(10) }.to change(score, :total).by(10)
  end
end
```

## 6. Idiomatic patterns

```ruby
# Enumerable over loops
names = users.select(&:active?).map(&:name).sort
totals = orders.group_by(&:customer_id).transform_values { |os| os.sum(&:amount) }
first_admin = users.find { it.admin? }      # `it` = implicit block param (3.4+)

# Safe navigation and defaults
city = user&.address&.city || "unknown"
config = defaults.merge(overrides)          # Hash#merge, non-destructive
counts = Hash.new(0); words.each { counts[it] += 1 }   # or words.tally

# Keyword arguments with defaults, required keywords
def spawn(kind:, x: 0, y: 0, **opts) = Entity.new(kind, x, y, **opts)   # endless method (3.0+)

# Resource safety with blocks
File.open("save.json", "w") { |f| f.write(JSON.generate(state)) }

# Custom iterable
class Inventory
  include Enumerable
  def initialize = @items = []
  def each(&) = @items.each(&)              # anonymous block forwarding (3.1+)
  def <<(item) = (@items << item; self)
end

# Value object
Vec2 = Data.define(:x, :y) do
  def +(o) = with(x: x + o.x, y: y + o.y)
end

# Error handling with retry
attempts = 0
begin
  api.call
rescue Net::ReadTimeout => e
  attempts += 1
  retry if attempts < 3
  raise
ensure
  log.flush
end

# Comparable / spaceship
class Version
  include Comparable
  attr_reader :parts
  def initialize(s) = @parts = s.split(".").map(&:to_i)
  def <=>(o) = parts <=> o.parts
end
```

- Prefer `each_with_object`, `sum`, `tally`, `filter_map`, `each_slice`, `zip`, `partition`, `min_by`, `chunk_while`.
- Prefer `freeze`d constants: `DIRECTIONS = %i[n e s w].freeze`.
- Use `Comparable`, `Enumerable` mixins instead of re-implementing operators.

## 7. Top pitfalls and error-message fixes

| Exact error text | Cause | Fix |
|---|---|---|
| `undefined method 'foo' for nil (NoMethodError)` (3.4+ wording; older: `for nil:NilClass`) | A value you expected was `nil` (missing hash key, failed `find`, uninitialized `@ivar`) | Trace where nil came from; use `fetch` for required keys, `&.` only where nil is legitimate |
| `undefined local variable or method 'x' for main` / `for an instance of Foo` | Typo, variable defined in another scope (`def` opens a new scope; blocks see outer locals but methods do not) | Pass it as an argument or make it an ivar/constant |
| `wrong number of arguments (given 1, expected 2)` (4.0 backtrace also names the receiver class [1]) | Arity mismatch; often positional vs keyword confusion after Ruby 3.0 keyword separation | Pass `**opts` explicitly; call `m(**h)` not `m(h)` for keyword methods |
| `no implicit conversion of Integer into String (TypeError)` | `"Score: " + 5` | Interpolate: `"Score: #{5}"` or `5.to_s` |
| `can't modify frozen String: "abc" (FrozenError)` | Mutating a literal under `frozen_string_literal: true` or a frozen constant | `buf = +""` or `.dup` before `<<` |
| `warning: literal string will be frozen in the future` | 3.4+ chilled string mutated (warning shown with `-W:deprecated`) | Same as above; add the magic comment and fix mutations |
| `uninitialized constant Foo (NameError)` | Missing `require`, wrong file name for Zeitwerk autoload, or namespace typo | Match file path to constant (`app/models/game_state.rb` -> `GameState`); `require_relative` outside Rails |
| `cannot load such file -- csv (LoadError)` | Library became a bundled gem (3.4/4.0) and Bundler hides it | Add `gem "csv"` (or `ostruct`, `logger`, `benchmark`...) to Gemfile |
| `stack level too deep (SystemStackError)` | Unbounded recursion; often `method_missing` or a setter calling itself (`def name=(v); self.name = v; end`) | Use `@name = v`; add base case |
| `comparison of Integer with nil failed (ArgumentError)` | `sort`/`max` on arrays containing nil | `compact` first or `sort_by { it || 0 }` |
| `undefined method '[]' for nil` | Digging into nested hash with missing level | `h.dig(:a, :b, :c)` |
| `key not found: :name (KeyError)` | `fetch` on a missing key (good: fail fast) | Supply default `fetch(:name, "anon")` or fix the data; check string vs symbol keys (JSON gives string keys unless `symbolize_names: true`) |
| `LocalJumpError: no block given (yield)` | `yield` in a method called without a block | Guard with `block_given?` or return `enum_for(__method__)` |
| `Ractor::IsolationError: can not access non-shareable objects in constant` | Ractor body touches mutable constant/global | `Ractor.make_shareable(obj)` / freeze deeply, or pass data in via port |
| `ArgumentError: invalid byte sequence in UTF-8` | Binary/Windows-1252 data read as UTF-8 | `File.read(p, encoding: "bom|utf-8")`, `str.scrub` or `force_encoding` + `encode` |
| `Bundler::GemNotFound` / `Could not find gem 'x' in locally installed gems` | `bundle install` not run, or wrong Ruby version | `bundle install`; `bundle exec` everything |

Other classic mistakes:
- `=` vs `==` in conditions works silently (assignment is an expression). RuboCop flags it.
- `Array.new(3, [])` shares **one** array three times; use `Array.new(3) { [] }`. Same for `Hash.new([])` — use `Hash.new { |h, k| h[k] = [] }`.
- `and`/`or` have lower precedence than `=`: `x = true and false` sets x to true. Use `&&`/`||`.
- String keys vs symbol keys: `{"a" => 1}[:a]` is nil.
- Integer division: `7 / 2 == 3`; use `7.fdiv(2)` or `7 / 2.0`. Integers are arbitrary precision (no overflow).
- `puts nil` prints an empty line; `p` shows `nil` — use `p`/`pp` to debug.
- In Ruby 4.0 a line starting with `||`/`&&`/`and`/`or` continues the previous line [1] — code that relied on it being a syntax error is affected.

## 8. Performance

- Turn on **YJIT** in production: `RUBY_YJIT_ENABLE=1` or `--yjit` or `RubyVM::YJIT.enable` (Rails 7.2+ enables it by default via an initializer when available). Typical gains 15-30% on Rails apps. 4.0: `RubyVM::YJIT.enable(mem_size:, call_threshold:)`; `ratio_in_yjit` stats need a `--enable-yjit=stats` build [1].
- ZJIT (`--zjit`) is not production ready in 4.0; target for 4.1 is to beat YJIT [1].
- Object allocation is the main cost. Avoid building intermediate arrays in hot loops (`each` instead of `map` when you discard results; `sum` instead of `map.sum`); use `frozen_string_literal` to dedupe literals; symbols for keys.
- Ruby 4.0 makes `Class#new` faster (especially with kwargs), GC heaps per size pool grow independently [1].
- Profile with `stackprof`, `vernier` (multi-thread aware, GVL visualisation), `ruby-prof`, `memory_profiler`, `benchmark-ips`.
- N+1 queries dominate Rails performance: `includes`/`preload`, `bullet` gem, `strict_loading`.
- GC tuning: `RUBY_GC_HEAP_*` env vars; jemalloc reduces fragmentation for multi-threaded Puma.

## 9. Security

- **Never** `eval`, `instance_eval(string)`, `send(params[:method])`, `constantize` on user input. `public_send` with an allowlist only.
- `Kernel#open` with `|cmd` used to spawn processes; 4.0 **removed** this behaviour for `Kernel#open` and IO methods [1]. Still use `File.open` / `URI.open` explicitly.
- Shell: use the array form `system("convert", input, output)` — never interpolate into a single string. `Open3.capture3(*argv)`.
- YAML: `YAML.load` is safe-by-default since Psych 4 (it is `safe_load`); never use `YAML.unsafe_load` or `Marshal.load` on untrusted data (gadget-chain RCE).
- SQL (ActiveRecord): `where(name: params[:name])` or `where("name = ?", x)`; never `where("name = '#{x}'")`.
- Rails: strong parameters (`params.expect(user: [:name])` in Rails 8), CSRF tokens on by default, `html_safe`/`raw` disable escaping — avoid on user content.
- Regex: `^`/`$` match line boundaries; use `\A` and `\z` to validate whole strings (classic bypass). Ruby 3.2+ has regex timeouts (`Regexp.timeout = 1.0`) against ReDoS.
- Supply chain: `bundle audit` (`bundler-audit`), `gem cert`, commit `Gemfile.lock`, pin `source`.

## 10. Game-dev usage

- **DragonRuby Game Toolkit**: commercial 2D engine (mruby-based, runs on Windows/macOS/Linux/consoles/web). `def tick args; args.outputs.sprites << {x:, y:, w:, h:, path:}; end` — a single per-frame `tick` like a Heartbeat loop.
- **Ruby2D**, **Gosu** (C++ core with Ruby bindings; `Gosu::Window#update`/`#draw` at 60 Hz), **raylib-bindings**/`raylib-ruby`, **Taylor**.
- **RPG Maker XP/VX/VX Ace** used RGSS (embedded Ruby 1.8/1.9) — lots of legacy scripts; `mkxp-z` runs them on modern Ruby.
- **mruby**: embeddable lightweight Ruby (like Lua's niche) for scripting inside C/C++ engines.
- Typical real use: backend services (Rails/Hanami APIs for leaderboards, accounts, matchmaking admin), build/asset pipelines (Rake), Fastlane for mobile store automation.

## 11. Cheat sheet vs Luau

| Concept | Luau | Ruby |
|---|---|---|
| Indexing base | 1 (`t[1]`) | 0 (`a[0]`); `a[-1]` is last |
| Length | `#t` | `a.length` / `a.size` / `str.length` |
| Absent value | `nil` | `nil` (an object: `nil.to_a == []`) |
| Truthiness | only `nil`, `false` falsy | same: only `nil`, `false` |
| Not equal | `~=` | `!=` |
| String concat | `a .. b` | `a + b`, `"#{a}#{b}"`, `a << b` (mutates) |
| String format | `string.format("%d", n)` | `format("%d", n)`, `"%d" % n` |
| Array | table `{1,2,3}` | `[1, 2, 3]` |
| Map | table `{a = 1}` | `{a: 1}` (symbol keys) / `{"a" => 1}` |
| Missing key | `t.x` -> nil | `h[:x]` -> nil; `h.fetch(:x)` raises KeyError |
| Iterate list | `for i, v in ipairs(t)` | `a.each_with_index { \|v, i\| }` |
| Iterate map | `for k, v in pairs(t)` | `h.each { \|k, v\| }` (insertion-ordered) |
| Methods / self | `function Obj:move(dx)` uses `self` | `def move(dx)`; `self` implicit, ivars `@x` |
| Classes | metatables + `__index` | `class Foo < Base; def initialize; end; end` |
| Closures | `function() return x end` | `-> { x }`, `proc { x }`, blocks `{ \|v\| }` |
| Coroutines | `coroutine.create/resume/yield` | `Fiber.new`, `fiber.resume`, `Fiber.yield`; `Enumerator` |
| Async | `task.spawn`, `task.wait` (Roblox) | Threads, `async` gem tasks |
| Integer division | `7 // 2` -> 3 | `7 / 2` -> 3 (Integer operands); `7.fdiv(2)` -> 3.5 |
| Floor modulo | `-7 % 3` -> 2 | `-7 % 3` -> 2 (floored, same as Luau) |
| Numbers | double + (Luau) no int type | Integer (bignum) and Float distinct |
| Error raise | `error("msg")` | `raise ArgumentError, "msg"` |
| Error catch | `pcall(f)` / `xpcall` | `begin ... rescue E => e ... ensure ... end` |
| Modules | `require(script.Module)` returns table | `require "lib"` / `require_relative`; `module Name` namespaces |
| Constants | none (convention) | `UPPER = 1` (reassign warns) |
| Comments | `--`, `--[[ ]]` | `#`, `=begin ... =end` |
| Ternary | `if c then a else b` (expression) | `c ? a : b` |
| Nil-safe access | none (manual `x and x.y`) | `x&.y` |

## 12. Recent changes and version notes

- **Ruby 4.0 (2025-12-25)** [1]: Ruby::Box (experimental), ZJIT (experimental), Ractor::Port API (breaking for Ractor users), `Set` and `Pathname` core, `Array#rfind`, leading `||`/`&&` line continuation, `*nil` no longer calls `nil.to_a`, `Kernel#open("|cmd")` removed, `ObjectSpace._id2ref` deprecated, CGI library removed except `cgi/escape`, `Net::HTTP` stops auto-setting form Content-Type, Unicode 17, many stdlib gems moved to bundled gems, RJIT removed, minitest 6, RubyGems/Bundler 4.
- **Ruby 3.4 (2024-12-25)** [3]: `it` implicit block parameter; Prism default parser; chilled (soon-frozen) string literals; `Hash#inspect` new format (`{name: "x", "k" => 1}`); error messages use `'method'` quotes and "an instance of"; modular GC; YJIT improvements.
- **Ruby 3.3**: YJIT large speedups, M:N thread scheduler (opt-in `RUBY_MN_THREADS=1`), Prism added as a library.
- **Ruby 3.2**: `Data`, WASI/WebAssembly build support, regex ReDoS caching + `Regexp.timeout`.
- Release cadence: a new minor every 25 December; patch releases roughly every 2 months [2].

## Sources

1. https://www.ruby-lang.org/en/news/2025/12/25/ruby-4-0-0-released/
2. https://www.ruby-lang.org/en/news/2026/07/14/ruby-4-0-6-released/
3. https://www.ruby-lang.org/en/news/2024/12/25/ruby-3-4-0-released/
4. https://github.com/ruby/rbs (RBS repository; RBS 4 inline details from secondary coverage, unverified)
5. https://docs.ruby-lang.org/en/master/ (core and stdlib reference)
6. https://docs.ruby-lang.org/en/master/Ractor.html
7. https://docs.ruby-lang.org/en/master/Fiber/Scheduler.html
8. https://bundler.io/guides/getting_started.html
9. https://guides.rubygems.org/
10. https://sorbet.org/docs/overview
11. https://github.com/soutaro/steep
12. https://docs.ruby-lang.org/en/master/syntax/pattern_matching_rdoc.html
13. https://github.com/ruby/ruby/blob/master/doc/yjit/yjit.md
14. https://guides.rubyonrails.org/security.html
15. https://docs.dragonruby.org/
16. https://github.com/socketry/async
