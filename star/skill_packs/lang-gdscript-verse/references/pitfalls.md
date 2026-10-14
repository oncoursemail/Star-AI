# GDScript and Verse: error messages and the Luau cheat sheet

Condensed from the STAR research notes (docs/research/languages). Error texts are representative; match on meaning.

# GDScript (Godot 4)

## Top pitfalls and error-message fixes

| Exact error text | Cause | Fix |
|---|---|---|
| `Invalid access to property or key 'x' on a base object of type 'null instance'.` (4.x; older: `Invalid get index 'x' (on base: 'null instance')`) | `$Node` path wrong, or used before `_ready`, or node freed | Use `@onready`, check the path / `%UniqueName`, `if node:` / `is_instance_valid(node)` |
| `Invalid call. Nonexistent function 'instance' in base 'PackedScene'.` | Godot 3 API | `instantiate()` |
| `Too many arguments for "move_and_slide()" call. Expected at most 0 but received 2.` | Godot 3 signature | Set `velocity` then call `move_and_slide()` |
| `"yield" was removed in Godot 4. Use "await" instead.` | Godot 3 coroutine syntax | `await signal_name` / `await obj.signal` |
| `Function "connect" ... ` / `Invalid argument for "connect()"` with string method names | Godot 3 `connect("sig", self, "_on")` | `sig.connect(_on)` / `obj.sig.connect(callable)` |
| `Node not found: "Sprite" (relative to "/root/Main/Player").` | Wrong node path or renamed node | Fix the path, mark as unique (`%`), or `get_node_or_null` |
| `Cannot infer the type of "x" variable because the value doesn't have a set type.` | `:=` on a Variant expression | Give an explicit type: `var x: int = d["k"]` |
| `Trying to assign an array of type "Array" to a variable of type "Array[int]".` | Untyped array assigned to typed | `var a: Array[int] = []; a.assign(src)` or `Array(src, TYPE_INT, "", null)` |
| `Can't change this state while flushing queries. Use call_deferred() or set_deferred() to change monitoring state instead.` | Modifying physics bodies/areas during a physics callback | `call_deferred("add_child", n)`, `set_deferred("monitoring", false)` |
| `Attempt to call function 'x' in base 'previously freed' on a null instance.` / `Invalid access ... 'previously freed'` | Using a node after `queue_free()` | `is_instance_valid()`; disconnect signals; avoid storing raw refs |
| `Parent node is busy setting up children, add_child() failed. Consider using add_child.call_deferred(child) instead.` | Adding children in `_ready` of a parent still being set up | `add_child.call_deferred(child)` |
| `Identifier "Foo" not declared in the current scope.` | Missing `class_name`, typo, or the class cache is stale | Add `class_name`, reload the project / reimport |
| `Could not find type "Enemy" in the current scope.` | Cyclic or unregistered `class_name` (often after a parse error in Enemy.gd) | Fix the parse error in the referenced script; restart the editor |
| `Unexpected "Indent" in class body.` / `Mixed use of tabs and spaces for indentation.` | Indentation | Use one style (the editor default is tabs) |
| `The method "cry" is abstract and must be implemented` (wording varies) | Subclass of an `@abstract` class missing an override (4.5+) | Implement the method |
| `Not all code paths return a value.` (4.7: overrides inherit typed returns) | A typed function with a path lacking `return` | Add the final `return` (4.7 migration guide suggests `return null` for Variant-returning overrides) [6] |
| `Integer division. Decimal part will be discarded.` (warning) | `5 / 2` with ints gives 2 | Use `5 / 2.0` or `float(a) / b` |

## Cheat sheet vs Luau

| Concept | Luau (Roblox) | GDScript (Godot 4) |
|---|---|---|
| Blocks | `then ... end`, `do ... end` | indentation + `:` |
| Indexing base | 1 | 0 |
| Null | `nil` | `null` |
| Truthiness | only `nil`/`false` falsy | `0`, `0.0`, `""`, empty Array/Dictionary, `null`, `false` are falsy |
| Not-equal | `~=` | `!=` |
| Logic | `and`/`or`/`not` | `and`/`or`/`not` or `&&`/`\|\|`/`!` |
| String concat | `..` | `+` (both Strings), `str(a, b)`, `"%s" % x` |
| Interpolation | `` `HP {hp}` `` | `"HP %d" % hp`, `"HP {hp}".format({"hp": hp})` |
| Tables/maps | `{}` table | `Array` `[]`, `Dictionary` `{}` (separate types) |
| Length | `#t` | `arr.size()` |
| Classes / self | metatables, `function T:m()` / `self` | one file = class; `self` implicit; `class_name` |
| Constructors | `T.new()` | `T.new()` calls `_init()`; scenes: `scene.instantiate()` |
| Closures | `function() end` | `func(): ...` lambdas (capture by value) |
| Events | `RBXScriptSignal:Connect(fn)` | `signal x` / `x.connect(fn)` / `x.emit()` |
| Wait | `task.wait(0.1)` | `await get_tree().create_timer(0.1).timeout` |
| Coroutines vs async | `task.spawn`, `coroutine` | `await` (function becomes a coroutine); `Thread`/`WorkerThreadPool` for parallelism |
| Integer division | `//` | `/` on two ints truncates (warning); `float(a)/b` for real division |
| Error handling | `pcall`, `error()` | no try/catch; `assert()`, `push_error()`, return error codes (`Error` enum, `OK`) |
| Modules | `require(ModuleScript)` | `preload("res://x.gd")`, `load()`, `class_name` global |
| Per-frame loop | `RunService.Heartbeat:Connect` | `_process(delta)` / `_physics_process(delta)` |
| Find child | `script.Parent:FindFirstChild("X")` | `$X`, `get_node_or_null("X")`, `%X` |
| Destroy | `inst:Destroy()` | `node.queue_free()` |
| Typing | `--!strict`, `x: number` | `var x: float`, `:=`, warnings as errors |
| Remotes | `RemoteEvent:FireServer` | `@rpc` functions + `rpc_id()` |
| Persistence | `DataStoreService` | `FileAccess` to `user://` (local), your own backend for online |

# Verse (UEFN)

## Top pitfalls and error-message fixes

Verse errors are reported with numeric codes (for example `3512`, `3510`). The texts below are representative, so match on meaning.

| Error (representative text / code) | Cause | Fix |
|---|---|---|
| `This invocation calls a function that has the 'decides' effect, which is not allowed by its context.` | Called a failable function/expression outside a failure context | Wrap in `if (...)`, use `or` fallback, or mark the caller `<decides>` |
| Calling `F()` on a `<decides>` function (wrong bracket) | `<decides>` functions are called with `[]` | `F[x]` inside a failure context |
| `This expression can fail, but ...` on `set M[K] = V` / `A[I]` (3512-style) | Map writes and array indexing are failable | `if (set M[K] = V) {}`; `if (X := A[I])` |
| `This invocation calls a function that has the 'suspends' effect, which is not allowed by its context.` | `Sleep`/`Await`/`sync` in an immediate function (e.g. a `Subscribe` handler) | Mark `<suspends>` or `spawn{ AsyncWork() }` from the handler |
| `<suspends>` and `<decides>` together rejected | The combination is illegal | Split: a `<suspends>` wrapper that calls a `<decides>` check in `if` |
| `spawn` of a `<decides>`/non-suspends function rejected (3511/3538) | `spawn` needs a `<suspends>` call | Wrap in a `<suspends>` function |
| `var Health := 100.0` rejected | `var` needs an explicit type | `var Health:float = 100.0` |
| Assigning without `set` / to a non-var | Immutability by default | Declare `var`, update with `set X = ...` |
| Integer `/` where an `int` is expected | `/` on ints yields failable `rational` | `if (R := A / B) { Q := Floor(R) }`, or use float math |
| `Floor(MyFloat)` rejected | Float→int conversion is failable | `if (I := Floor[MyFloat])` / `Int[MyFloat]` |
| Persistable class rejected (3662/3663/3664/3665) | `var` field, missing `<final>`, `<unique>`, superclass/interface | Follow the persistable rules above |
| Function in a field initializer rejected (3582) | Initializers must be literals/constants | Compute in `OnBegin` or a constructor function |
| `Unknown identifier` for a device class | Missing `using { /Fortnite.com/Devices }` | Add the right `using` |
| `@editable` device is `{}` default at runtime | Not assigned in the UEFN Details panel | Select the Verse device in the level and assign references |
| Runtime: `MathIntrinsicCallFailure` | 64-bit overflow on BPVM | Clamp values; avoid huge products |
| Runtime error from `Err()` kills the task | `Err` is not catchable | Use failure (`<decides>`) for expected conditions |

## Cheat sheet vs Luau

| Concept | Luau | Verse |
|---|---|---|
| Indexing base | 1 | 0; `A[I]` is failable |
| Null | `nil` | no null; option `?t` (`false` = empty, `option{x}`) |
| Truthiness | `nil`/`false` falsy | no truthiness: conditions are *success/failure*; `logic` must be queried `B?` |
| Equality | `==`, `~=` | `=`, `<>` (both failable comparisons) |
| Assignment | `x = 1` | `X := 1` (constant) / `var X:int = 1` + `set X = 2` |
| String concat | `..` | `+` on strings; interpolation `"{X}"` |
| Interpolation | `` `{x}` `` | `"Score: {X}"` |
| Tables/maps | `{}` | `array{}` (`[]t`), `map{K => V}` (`[k]v`), tuples, structs |
| Length | `#t` | `A.Length` |
| Methods/self | `function T:m()` + `self` | `m():void =` inside `class`; `Self` |
| Closures | anonymous functions | nested functions; lambdas limited (no general anonymous function literal in UEFN) |
| Coroutines vs async | `task.spawn`, `task.wait` | `<suspends>`, `Sleep`, `sync`/`race`/`rush`/`branch`, `spawn{}` |
| Integer division | `//` | `/` gives failable `rational`; `Floor(R)` |
| Error handling | `pcall`/`error` | failure (`<decides>`, `if`, `or`) for expected cases; `Err()` is uncatchable |
| Modules | `require(ModuleScript)` | `using { /Path/Module }`, `module:` |
| Events | `:Connect(fn)` | `.Subscribe(fn)`, `.Await()` |
| Types | gradual, `--!strict` | static, mandatory where not inferable; effects in signatures |
| Mutation | anything mutable | immutable by default; `var` + `set`; transactions roll back on failure |
| Persistence | DataStoreService (async, yields, can error) | module-scoped `weak_map(player, t)` of `<persistable>` types (auto loaded/saved) |
| Comments | `--` | `#` and `<# block #>` |
