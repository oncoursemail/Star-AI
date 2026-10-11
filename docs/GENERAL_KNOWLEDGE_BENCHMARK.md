# General-foundation development response checker

This is an offline checker for ten authored math, logic, fixed-offset time,
structured-information, correction and abstention tasks. It has no provider,
desktop, Roblox or evaluation-runner import and cannot call a model or enable one.
The public fixtures are development examples. They establish no unseen,
broad-knowledge, native, training or model-gain result.

Codex root independently reviewed all ten expected objects using math/datetime
stdlib checks and manual reasoning for logical and abstention cases, including
the UTC tie order `E4, E2, E3, E1`. This source change supplies the checker and fake-data
controls. It supplies no actual model responses or measured model comparison.

## Offline commands

```text
python -m star.general_knowledge_benchmark
python -m star.general_knowledge_benchmark list
python -m star.general_knowledge_benchmark prepare --repeats 1
python -m star.general_knowledge_benchmark score --run raw.json
python -m star.general_knowledge_benchmark compare --baseline before.json --candidate after.json
```

Invoking without a command prints help without opening a suite or writing files.
`list` and `prepare` read only
the public suite and this module's own source. Preparation allowlists exactly one
system and one user message per task. It never opens the oracle file or includes
oracle expected values, derivations or hashes in messages. The oracle sidecar is
loaded only for `score` and `compare`.

Output defaults to stdout. `--out destination.json` exclusively creates a new file
and refuses an existing output, including an input file. No directories or app
settings are created. `--suite` and `--oracles` explicitly select bounded files;
there is no automatic search through profiles or model caches.

## Raw artifact contract

A raw run is one JSON object with exactly these fields:

| Field | Required meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `kind` | `general_foundation_raw_run` |
| `suite_id`, `suite_sha256` | Current public suite ID and exact file-byte SHA256 |
| `oracle_sha256`, `grader_sha256` | Current oracle file bytes and actual grader module bytes |
| `identity` | Complete operator-declared identity below |
| `repeats` | Integer 1 through 3 |
| `rows` | Exact task order GF-01 through GF-10, with attempts 1 through repeats for each task |

`identity` has exactly `app_commit` (40 lowercase hex), `source_sha256`,
`request_builder_sha256`, `adapter_sha256` (64 lowercase hex each), `backend_build`,
`model`, `mode` and `options`. Labels are bounded, with no whitespace, URI scheme
or arbitrary profile fields. `model` has exactly `model_id`, `revision`,
`weights_sha256`, `tokenizer_sha256` and `quantization`. `options` has exactly
`temperature` (finite 0..2), `top_p` (finite 0..1), `max_output_tokens` (16..512),
`seed` (null or integer 0..4294967295), `stop` (at most four bounded strings), and
`tools` (the empty list).

Every supplied model, source, backend and options field is **operator declared,
not authenticated**. Matching hashes and labels do not prove which weights were
loaded, which request was sent or which model produced a response. The checker
does not accept `verified=true` or other extra fields, discover actual weights,
look up an endpoint or claim secure attestation. An operator must provide required
identities; omitted, blank or malformed identities are rejected.

Each raw row has exactly `task_id`, `attempt`, `request_sha256`, `response_sha256`,
`outcome`, `response` and `error_code`. The request digest comes from `prepare`:
SHA256 of canonical JSON containing the exact task ID and system/user messages.
The response digest is SHA256 of the exact raw reply's UTF-8 bytes. A completed
row has outcome `completed`, raw response text, and error code null. A transport
failure has outcome `transport_error`, empty response, and one fixed code:
`timeout`, `connection_failed`, `cancelled`, or `unavailable`. No raw exception,
credential, endpoint or host path is an error field.

There must be exactly 10 times repeats rows. Missing, extra, duplicated, reordered
or mismatched requests/attempts refuse the artifact. A saved score report is not
a raw run and cannot be used as comparison input. Extra declared pass flags are
also rejected. Comparisons recompute both sides from raw text under the current
grader and oracle bytes.

## Deterministic grading and comparison

Files are read with a byte limit: 100 KB for suite/oracles, 1 MiB for raw runs.
Raw replies are limited to 8 KiB, JSON nesting to 16 and nodes to 20,000. Duplicate
object keys, non-finite numbers, oversized integers, trailing text and invalid
UTF-8 are rejected. Exact key sets and value types prevent `true` or `79.0` from
passing as integer 79. Whitespace and object-key order do not affect correctness.
Required array order, reduced fractions and exact valid date formats do.

Rows retain separate `pass`, `incorrect`, `invalid_format`, `empty` and
`transport_error` statuses. A natural-language refusal is retained as an invalid
response format, not classified by an unreliable keyword heuristic. No row is
discarded from totals. Reports contain hashes/statuses rather than raw answers.

Default comparison requires identical declared app/source/adapter/backend/model,
mode, options, repeats, suite/oracles/grader and every task request. It rejects
drift instead of treating it as a warning. To compare different declared models,
the operator must select `--axis model` and supply `--baseline-model` and
`--candidate-model` as exact complete model-identity JSON objects. Only that
explicit expected pair may differ; all other controls must still match.

`artifact_consistent` means these artifact identities match; it does not approve
the candidate or show that it is better. Any transport-error row gives
`incomplete_transport`, with all results still visible. Invalid artifacts return
exit code 2 with a fixed refusal; a successfully parsed/scored report returns 0
even when answers fail. There is no `allowed`, `enable` or promotion decision.
Changes to suite, oracle, grader, options or source require fresh matching raw
artifacts; existing runs are never silently rescored under new pins.

## Validation scope

The focused tests use authored fake replies, temporary files and declared fixture
identities. They cover the ten reviewed answers, corrections/unknown facts,
typing/format/calendar/order traps, identity and coverage drift, stale raw hashes,
regrading, explicit model axes, bounded input, oracle isolation, inert defaults
and exclusive output. These controls validate this checker. Actual STAR task-path
or candidate-model testing remains the separate open general-knowledge item.
