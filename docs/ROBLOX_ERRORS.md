# Local Roblox output explanations

`star/roblox_errors.py` is a deterministic, standard-library-only reference source.
It never calls Studio, a model, the network, the filesystem, or a credential store.
It contains 74 diagnostic patterns covering Luau runtime/syntax/types, instance
APIs, replication/remotes, DataStore/HTTP, and common asset/tween/path errors.

## Entry points

- `parse_output(text)` returns immutable `StudioRecord` values: severity, optional
  script path and line, message, and ordered `StackFrame` values. Each frame has
  a script path, line and optional function name.
- `match_error(message)` matches an entire diagnostic, not words inside prose.
- `explain_output(text)` pairs known records with catalogue entries. Unknown
  diagnostics remain available through the parser without invented explanations.
- `reference_context(text, max_chars=6000)` renders bounded, delimited reference
  data. Each match includes causes in heuristic likelihood order, a distinguishing
  check, a fix pattern and exactly three lines of illustrative Luau.

The causes are troubleshooting hypotheses, not measured probabilities or a
confirmed diagnosis. The examples are sketches, not patches or complete scripts:
inputs such as `part`, `store`, and `requestOnce` must be supplied by the caller's
code. Examples are not automatically compiled or executed. Observe the client/
server placement and validation described by each fix; do not enable production
API access merely to silence a diagnostic.

## Parsing and limits

Recognized forms include timestamps, explicit Error/Warning labels, full-path
`Script:line: message` diagnostics, Studio channel/source suffixes, Luau analysis
`file(line,column): TypeError: ...`, and Stack Begin/End with script frames. A
stack's first frame fills a missing primary location. Unknown severity defaults
to error only for explicitly labelled/located diagnostics or an attached stack.
A timestamp or print source suffix alone does not prove an error. If Studio
colour/severity metadata was lost, an arbitrary custom `warn()` without a label
cannot reliably be distinguished from `print()` and is deliberately ignored.

Parsing processes at most 96,000 input characters, 600 complete lines, 64 records
and 24 frames per record. Lines longer than 2,048 characters and incomplete
truncated lines are ignored. Full parser results preserve repeats; reference
rendering deduplicates by diagnostic kind and location, includes at most six
explanations within 6,000 characters, and marks budget omissions. A budget too
small for one complete entry returns no block, never a cut fence or marker.
Pasted fields are quoted and delimiter characters escaped; they are untrusted
reference data and never executable instructions.

## Chat integration

`desktop_core.run_task` computes this block from the current prompt only, in
Fast, Auto and Agent modes. It adds one `(heading, text)` pair to `turn_sections`,
after official documentation and before other reference material, and accounts
for its bounded size in the per-turn budget. The existing `learning.guard_sections`
and `agent.volatile_context` path handles it just like documentation passages.
The original user message and history are untouched. No extra system message,
system-prompt content, persistent lesson or permission is introduced. The global
model request budget still applies. Local explanations do not depend on the
optional documentation service being available.

## Regression coverage

`tests/test_roblox_errors.py` contains a separate, real-looking sample for every
catalogue entry, parser tables, stack association, ordinary-prose/print negatives,
message variants, input bounds, reference budgets and delimiter-injection cases.
`tests/test_roblox_error_context.py` drives the real `run_task` and `execute` path
with a fake model and fake documentation client. It checks all three chat modes,
documentation present/off/unavailable, byte-identical system prompts, original
stored history, and that a subsequent turn does not inherit the explanations.
Network and credential operations are forbidden in these integration tests.

Run `python -m pytest -q tests/test_roblox_errors.py tests/test_roblox_error_context.py`,
then the full repository `python -m pytest -q`. These are offline Python tests,
not Roblox Studio runtime verification of the example snippets.

## Primary references for reviewing fixes

- [Roblox DataStore errors and limits](https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits)
- [Roblox DataStore best practices](https://create.roblox.com/docs/cloud-services/data-stores/best-practices)
- [Roblox RemoteEvent](https://create.roblox.com/docs/reference/engine/classes/RemoteEvent)
- [Roblox Instance](https://create.roblox.com/docs/reference/engine/classes/Instance)
- [Luau standard library](https://luau.org/library/)
- [Luau syntax](https://luau.org/syntax/)
- [Luau type checking](https://luau.org/typecheck)

The catalogue is authored troubleshooting guidance informed by these references;
the diagnostic fixtures are illustrative, not captured live Studio evidence.
