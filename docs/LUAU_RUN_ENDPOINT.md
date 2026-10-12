# Standalone Luau run endpoint (draft)

## Scope of this patch

This patch adds the authenticated knowledge-service route and explicit desktop
`KnowledgeClient.luau_run(...)` call. It does **not** yet add the persisted
**Run my Luau before answering** desktop setting, its React toggle, or the
before-answer integration. Those are outstanding work, not enabled behavior.
No existing chat path calls the new method. No evaluation or workflow files are
changed. Do not merge this draft as completion of the full feature.

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
returned by the code is available to the test body as `result`.
Local variables in the code are not visible to the separate test chunk. Returning
early from code does not skip tests. This is the standalone VM: Roblox engine
objects, services, Studio state and networking are **not** present.

A completed sandbox attempt returns HTTP 200, even for failed code. The JSON
contains `ok`, `status` (`pass`/`fail`), `executed`, bounded `output`, an `error`
category, structured `errors` (`source`, `line`, `message`), `exit_code`,
`timed_out`, `output_limited`, `usage` and `limits`. Usage reports wall seconds,
CPU seconds, peak resident bytes and captured output bytes. A limit failure may
have no source line; one is never fabricated. A passing run means only that the
snippet and supplied tests returned normally, not that a Roblox game is correct.
Output and diagnostics are untrusted data, never instructions.

HTTP 400 is invalid input; 401 is the existing authentication failure; 413 is the
existing body-size rejection; 429 is admission refusal; 503 is disabled or
unavailable infrastructure. These refusals do not claim code executed.

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
free of host secrets. Luau's upstream sandbox guidance is at
https://luau.org/sandbox/ . The evaluation harness is read-only reference here;
its files were not modified.

## Admission and enablement

One VM runs globally, up to four distinct clients wait FIFO, and waiting expires
after 2 seconds. A client may have only one active **or queued** request. Identity
is derived from the socket address, not request JSON or forwarding headers.
Clients sharing a NAT address share this restriction. The queue is process-local;
multiple independently deployed service processes are not one shared queue.

The server remains OFF unless an operator explicitly sets `STAR_KB_LUAU_RUN=1`
in its service environment. Other spellings do not enable it. No shipped
configuration sets this variable. The desktop client makes no automatic calls.

## Tests and evidence

```sh
pytest -q tests/test_luau_run_sandbox.py tests/test_luau_run_http.py tests/test_luau_run_client.py tests/test_luau_run_regressions.py
```

The tests include real local child-process probes for address space, output,
wall timeout, effective CPU/file/open-file/core/process limits, empty environment,
fork refusal (non-root), cleanup, FIFO/capacity/duplicate admission, the actual HTTP
handler and authentication, and the real client transport using a fake server.
The HTTP tests substitute only the unrelated document-index imports so they do
not add server-only numpy/YAML dependencies to desktop test installations.
They execute the real service constructor, handler, authorization and queue.

Sixteen additional cases execute the **real standalone Luau VM**, including
loop/memory/output bombs, module/file/process attempts, escape attempts, syntax
errors, test failures and successful exported functions. They skip explicitly
when the VM/Linux/non-root prerequisites are absent. To run them, set
`STAR_LUAU_TOOLS` to an existing reviewed VM installation and run pytest as a
non-root account. Tests never fetch tools or need a GPU, network or real keyring.
A skip is not containment evidence. The lead must run the complete test suites
and real-VM cases before approving this feature.
