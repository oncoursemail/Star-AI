# Pitfalls when changing a codebase you do not understand

| Pitfall | Why it hurts | Instead |
|---|---|---|
| Full rewrite of an unknown system | Hidden behaviour (edge cases, compensating bugs) is lost; months without a working build | Strangler: replace one path at a time behind a working whole |
| Refactor and behaviour change in one commit | A regression cannot be attributed; review is impossible | Refactor-only commits checked against characterization tests; behaviour changes separate |
| Deleting "dead" or odd code on sight | It may be load-bearing (called by name, by a remote, by a timer, by saved data) | Search all references, read history, then remove behind a test |
| Guessing names for unknown code | Wrong names mislead every later reader | Placeholder names until a trace or test confirms meaning |
| Tests that assert what the code should do, written before knowing what it does | They fail on day one and get deleted | First characterization tests (what it does), then intended-behaviour tests |
| Nondeterministic tests (time, random, ordering) | Flaky oracle, nobody trusts it | Seed randomness, inject clocks, sort outputs |
| Changing the saved-data shape without a version | Old players lose data or crash on load | Schema version + migration on load, tested on copied real records |
| Testing migrations in the live game | Irreversible data damage | Copy records to a test place or test universe |
| One giant "cleanup" PR | Unreviewable | Many small PRs, each with its own check |
| Trusting an AI summary of the code | It may be plausible and wrong | Mark claims observed / inferred / unknown; verify by reading or running |

## Roblox-specific traps
- `_G` and `shared` writes from many scripts: order of script start is not guaranteed, so behaviour may depend on load timing. Move to ModuleScripts and require them.
- Remotes created at runtime by name: search for the name strings as well as the instance.
- `wait()` loops and connections never disconnected: list them before refactoring; they are where leaks and timing bugs hide.
- DataStore keys built from string concatenation: list every key pattern before changing any.
