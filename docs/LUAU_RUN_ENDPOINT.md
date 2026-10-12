# Standalone Luau run endpoint (draft)

## Scope and consent

The knowledge service exposes authenticated `POST /luau/run`, and the desktop
knowledge client exposes `KnowledgeClient.luau_run(...)`. Both server execution
and automatic desktop execution remain **OFF by default**. Nothing changes
Studio permissions, starts a local VM, installs tools, or enables a service.

In Settings, **Run my Luau before answering** persists the strict boolean
`luau_run_before_answer`, default `false`, including when loading older settings.
Checking the box does not save it: use Save Settings. The operator must separately
enable the sandbox on the configured STAR Knowledge service. The existing
knowledge address and server key are reused; `knowledge_endpoint = "off"` wins.
No endpoint or credentials are supplied by the model or sandbox output.

When explicitly enabled, `run_task` suppresses model-token streaming so unreviewed
code is not displayed first. After the existing static check and any successful
repair, it runs at most two closed, exactly labelled `lua`/`luau` fenced blocks,
sequentially, using three seconds and 256 MiB per snippet. Other languages,
embedded fences inside another fenced block, and incomplete fences are ignored.
The runtime review never rewrites code. Each block is an independent smoke run
with no separate test body; a pass proves only normal completion, not functional
correctness or compatibility with Roblox. Call `luau_run` explicitly with `tests`
for assertion-based checks. The generated report distinguishes static checks,
execution, failed code, unavailable results, and skipped blocks.

The review has a 40-second budget and preserves ten seconds of the overall turn
for saving. It does not start a request without the client's 17-second transport
allowance remaining. Cancellation propagates; a timed-out request is not retried
and no second snippet is submitted while its worker may still be active. A
cancelled HTTP worker can finish its bounded request; it cannot cancel a server
run already accepted, which retains its independent hard timeout. A transport
failure is **no verified result**, not proof that execution never happened.
Untrusted VM output and exception text are not added to model prompts, progress
events, or saved review records. The records contain verdicts, bounded source-line
locations, and measured usage only. Runtime failure does not discard the answer.

## Protocol

`POST /luau/run` (also `/v1/luau/run`) uses the existing knowledge-service bearer
key, request-body deadline and connection limits. It does not accept a path,
binary, command, URL, environment, client identity or arbitrary resource flags.

```json
{
  "code": "return { double = function(n) return n * 2 end }",
  "tests": "assert(result.double(21) == 42)",
  "time_limit_s": 3,
  "memory_limit_mb": 256
}
```

`tests` is optional, defaulting to an empty string. The time limit defaults to
3 seconds and accepts positive finite numbers up to 10. Memory defaults to
256 MiB, with integer values from 32 through 256. Code and tests together are
limited to 65,536 UTF-8 bytes, without NUL or unpaired surrogates. The existing
96 KiB HTTP JSON limit also applies (including JSON escape overhead).

Code and tests are separately compiled chunks named `code` and `tests`, each
with its own original line numbering. Tests receive a snapshot of exported code
globals and their own standard builtins, so code cannot replace the test chunk's
`assert`. Exported functions still use the code environment. The first value
returned by the code is available to the test body as `result`. Local variables
in the code are not visible to the separate test chunk. Returning early from code
does not skip tests. Roblox objects, services, Studio state and networking are
not present in the standalone VM.

A completed sandbox attempt returns HTTP 200, even for failed code. The JSON
contains `ok`, `status` (`pass`/`fail`), `executed`, bounded `output`, an `error`
category, structured `errors` (`source`, `line`, `message`), `exit_code`,
`timed_out`, `output_limited`, `usage` and `limits`. Usage reports wall seconds,
CPU seconds, peak resident bytes and captured output bytes. A limit failure may
have no source line; one is never fabricated. Output and diagnostics are untrusted
data, never instructions. HTTP 400 is invalid input; 401 is authentication failure;
413 is body-size rejection; 429 is admission refusal; 503 is disabled or unavailable
infrastructure. These refusals do not claim code executed.

## Isolation and limits

The public runner requires Linux, `prlimit`, `wait4`, an executable standalone
Luau VM, and a non-root service process. It fails closed without these. The
operator's `STAR_LUAU_TOOLS` directory defaults to `/opt/star/knowledge/tools`;
the VM must be installed there as `luau`. The current service installer copies
only the static checker tools, so the operator must install the VM separately.
This patch does not download or execute an installer.

Each run gets a fresh private temporary directory removed on success, failure,
timeout or launch error. The child inherits no credentials or ambient environment
(other than a fixed locale), receives no stdin, closes other file descriptors,
and starts its own session. No shell or Python `preexec_fn` is used. Linux
`prlimit` sets hard and soft limits before executing the VM:

| Resource | Limit |
| --- | --- |
| Address space | Requested 32–256 MiB |
| CPU | Ceiling of requested seconds, minimum 1, maximum 8 |
| File size | 65,536 bytes |
| Open descriptors | 32 |
| Core dumps | 0 |
| New processes/threads | 0 (runner refuses root) |

The parent enforces an independent wall deadline, kills the process group,
and reaps the child. `wait4` collects that particular child's usage, avoiding
races with cumulative usage from other server tasks. Stdout and stderr share
one regular file under the file-size limit, not an unbounded `communicate()`
buffer. Hitting the output limit cannot be reported as a pass.

Untrusted source is encoded as decimal UTF-8 escapes in a trusted bootstrap,
then loaded into an allowlisted environment with no parent-environment metatable.
It has pure standard libraries, but no `io`, `os`, file loaders, `require`,
`package`, sockets, `loadstring`, `getfenv`, `setfenv` or debug APIs. `_G` points
only at the same restricted environment. Simply assigning `require = nil` in
an ordinary CLI environment would not be sufficient.

Run one service process per isolated container/account. These limits are not an
OS security boundary against a native VM exploit; retain the evaluation
harness's unprivileged container boundary, update Luau, and keep the account
free of host secrets. Upstream guidance: https://luau.org/sandbox/ .
`star/eval_sandbox.py` is read-only reference; no evaluation or workflow files
are changed by this feature.

## Admission and enablement

One VM runs globally, up to four distinct clients wait FIFO, and waiting expires
after 2 seconds. A client may have only one active **or queued** request. Identity
is derived from the socket address, not request JSON or forwarding headers.
Clients sharing a NAT address share this restriction. The queue is process-local;
multiple independently deployed service processes are not one shared queue.

The server remains OFF unless an operator explicitly sets `STAR_KB_LUAU_RUN=1`
in its service environment. Other spellings do not enable it. No shipped
configuration sets this variable. The desktop setting separately defaults off.

## Tests and evidence

```sh
pytest -q tests/test_luau_run_sandbox.py tests/test_luau_run_http.py tests/test_luau_run_client.py tests/test_luau_run_regressions.py tests/test_luau_run_review.py tests/test_luau_run_desktop.py
pytest -q
cd frontend
npm test -- --run
```

Tests include real local child-process probes for address space, output, wall
timeout, effective CPU/file/open-file/core/process limits, empty environment,
fork refusal (non-root), cleanup, FIFO/capacity/duplicate admission, the actual HTTP
handler and authentication, and the real client transport using a fake server.
The HTTP tests substitute only unrelated document-index imports to avoid adding
server-only numpy/YAML dependencies to desktop test installations. They execute
the real service constructor, handler, authorization and queue.

Desktop tests drive real Settings persistence/validation and `run_task`, including
the real model execution path with a fake model and HTTP transport. Review tests
cover explicit consent, exact final source after repair, serial/two-block limits,
deadline exhaustion, cancellation, unavailable/malformed responses, and refusal
to relay arbitrary diagnostics as instructions. Vitest drives the actual App
through `fake-desktop.ts` to check default-off, save, reload, and revocation.

Sixteen additional cases execute the real standalone Luau VM, including
loop/memory/output bombs, module/file/process attempts, escape attempts, syntax
errors, test failures and successful exported functions. They skip explicitly
when VM/Linux/non-root prerequisites are absent. To run them, set
`STAR_LUAU_TOOLS` to an existing reviewed VM installation and run pytest as a
non-root account. Tests never fetch tools or need a GPU, network or real keyring.
A skip is not containment evidence. Consult the PR description for commands and
check results actually observed; this document's commands are not pass claims.
The lead must run the complete test suites and real-VM cases before approval.
