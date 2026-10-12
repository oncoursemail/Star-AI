# STAR Workbench MCP connector

**Install ONLY in a fresh, separate LXD or Docker container. Never install this in
 the container that runs the model, STAR's brain, or any production service.**
The installer refuses `/opt/star/secrets`, an existing installation/workspace,
non-container hosts, and containers without systemd. The supported baseline is
Debian 13, Linux, with Python 3.13 and a distribution Node version compatible with
STAR's frontend (20.19+ or 22.12+).

This is a small, standalone MCP server for editing files, running programs and
reading their results on an owner's disposable server workspace. It uses the
**official `mcp` Python SDK**, Streamable HTTP and stateless JSON responses. No
ChatGPT SDK, model API, keyring, GPU, or GitHub credential is required. Any MCP
client supporting Streamable HTTP can use it.

## Read the risks first

This lets a cloud chat **run code in this container**. A malicious instruction in
a repository file, command output or web page can persuade a model to run an
unwanted command. Tool confirmations are useful but do not eliminate prompt
injection. Treat the **public URL plus token as a password**. Do not put that
combination in chat messages, issues, screenshots, command arguments, browser
history, or Git commits. Enter it only in the connector's private configuration.

The container must have **no secrets**, personal files, host directory mounts,
SSH agents, Docker socket, GPU access, cloud instance credentials, or access to
other services. Never use `--privileged` or host networking. Put an outer memory,
CPU, process and disk quota on the container (for example 4 GiB RAM, 2 CPUs and
20 GiB disk). File-size limits do NOT limit the total number of files a program
can create. Destroying and recreating the container is the normal recovery path.

The argv deny-list is an accident guard, **not a security sandbox**: Python and
build tools can themselves launch programs or make network requests. Every
production command additionally runs inside bubblewrap with a separate PID/mount/
user namespace, no capabilities, a small read-only operating-system view and only
`/work` writable/persistent. The connector token, server source, audit log and
control state are not mounted into that namespace. No unsandboxed CLI fallback
exists. Tests explicitly instantiate `sandbox=False` to exercise execution limits
without requiring namespaces; this is not a supported deployment mode.

The egress firewall, not URL parsing or DNS resolution checks, blocks private
networks. It applies to the service UID and all its descendants. New loopback
connections are blocked too, preventing jobs from calling the MCP server itself.
IPv6 is entirely blocked for jobs, including mapped/private/NAT64 bypasses. DNS
is restricted to two public resolvers; public TCP HTTPS remains available.
**Public HTTPS and DNS can exfiltrate workspace content.** Nothing confidential
belongs in this workspace. Container/kernel escape vulnerabilities remain a risk;
keep the host, container, bubblewrap and dependencies patched.

## Install

Use an **unprivileged LXD container** or an equivalently isolated Docker container
with systemd as PID 1, working unprivileged user namespaces, and a container-local
network namespace capable of installing nftables rules. Docker's ordinary default
container is not sufficient: its seccomp/AppArmor/cgroup setup must permit the
nested sandbox and systemd; `NET_ADMIN` is needed only inside its network namespace.
Do not weaken the host's profiles globally to make this work. An administrator
should review the container configuration and quotas first.

Copy this folder into that separate container. Review the files, then, as root
**inside the container**, run:

```sh
bash server/workbench/install.sh
bash /opt/star-workbench/tunnel.sh install
bash /opt/star-workbench/tunnel.sh url
```

`install.sh` creates a non-login service account, `/work`, a root-owned server
virtual environment, the firewall unit, and `star-workbench.service`. It generates
32 random bytes using `openssl rand -hex 32` in `/etc/star-workbench/token`, owned by
root and mode **0600**. It never prints the token, only the file path. systemd's
`LoadCredential` reads that root-only source and gives the unprivileged service a
private, read-only credential copy. The token is not passed through an environment
variable, command line or child-process file descriptor.

**Unprivileged LXD container without nesting** (`security.nesting=false`, the
recommended setting): two things do not work there as on a normal host, and the
installer handles both without turning nesting on.

- systemd cannot mount its credential store and silently provides none. The unit
  therefore also runs, as root before start, `install -m 400` of the token into the
  service's own runtime directory `/run/star-workbench` (mode 0700, removed when the
  service stops). The server uses the systemd credential when present, else that copy.
- bubblewrap cannot mount a fresh `/proc` for a command, because the container's own
  `/proc` has files mounted over it. `star-workbench-proc.service` keeps one clean
  procfs mounted at `/run/star-workbench-proc`, which satisfies the kernel's check.

The secret path is accepted with or without its final slash (`/mcp/<token>/` or
`/mcp/<token>`); anything else under `/mcp/` is refused.

Preparation uses the **real sandboxed runner** to fetch `star/next` from the fixed
public repository, create `/work/.venv`, install the project's Python requirements
plus pytest, and install the frontend's packages in `/work/Star-AI/frontend` (`npm ci`
when a `package-lock.json` exists, otherwise `npm install --no-package-lock`: the
project commits no npm lock file). Dependency installation
needs public networking; test execution itself does not. Source/build lifecycle
scripts are untrusted and run unprivileged. A failing sandbox, firewall, dependency
installation or Node version check aborts installation. Inspect retained job logs
as root in `/var/lib/star-workbench/` when preparation fails. Do not bypass the
sandbox to resolve a failure.

The service binds **127.0.0.1:8765 only**. There is no public listener and no open
inbound container port to publish. `WORKBENCH_ROOT` can select a different absolute
workspace root in a reviewed systemd override; the command sandbox still maps it
to `/work`. The default installer is intentionally fresh-install-only, not an
in-place upgrade or token-rotation script.

## Connect from ChatGPT or another MCP client

In ChatGPT web, obtain the necessary administrator permission and enable
**Developer mode** under Settings → Apps → Advanced Settings, or through Workspace
settings → Apps → Create. Create a custom MCP app/connector, enter its name and
server URL, scan the tools, then create it. Select the app in a chat and review
write/run confirmations. UI labels and access depend on the plan and workspace.
As of the official documentation checked on **2026-10-11**, full write-capable MCP
is available for Business and Enterprise/Edu; Pro developer-mode access is described
as read/fetch only. This server cannot grant a ChatGPT plan additional permissions.
See the [official developer-mode guide](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt).

For clients that cannot add request headers, configure:

```text
https://<tunnel-host>/mcp/<token>/
```

Read the token through an administrator-only local session and paste it directly
into that private connector field. Do not ask the model to retrieve it. Select
“No authentication” **in the client's OAuth setting** when using this URL form:
the server still enforces the secret path on every request; this is not anonymous
access and is not OAuth.

Clients supporting headers can instead use `/mcp/` and send:

```text
Authorization: Bearer <token>
```

Either method is sufficient. When both are supplied, both must be valid. Unknown,
missing and incorrect tokens receive **404 with a 200 ms delay**, without redirects.
Comparisons use constant-time digest comparison. Rate limiting is global for this
single-owner connector, rather than trusting a client-supplied forwarded address.
Authenticated cross-origin browser requests are rejected unless Origin matches
Host. There is no permissive CORS endpoint. Local SDK object calls are not an
unauthenticated tool backdoor; tool wrappers require the HTTP authentication context.

Start with an innocuous loop: `info`, `ws_write` a small Python file, `run` it,
then `ws_read` it. Use `job_start` and polling for long tests: a tunnel/client can
time out before a 900-second synchronous `run` completes.

## Tools and boundaries

| Tools | Behavior |
| --- | --- |
| `ws_list(path, depth)` | Relative paths or absolute paths within the configured workspace; 0–8 levels, 4000-entry limit. |
| `ws_read(path, start_line, max_lines)` | UTF-8 text; one-based lines, 1–2000 lines, 1 MiB file limit and 60 KiB excerpt. |
| `ws_write(path, content)` | Atomic UTF-8 replacement; creates parents. No symlinks, hardlinks or special files. |
| `ws_apply_patch(unified_diff)` | Strict text hunks, exact context, creation/deletion and no-final-newline markers. No rename/binary/mode patches. All hunks validate first; each replacement is atomic, but a multi-file patch is **not a filesystem transaction** against concurrent writers. |
| `ws_delete(path)` | A single regular file or empty directory; never recursive and never the workspace root. |
| `ws_search(pattern, path, max_results)` | Literal, not regex. Reports skipped files and depth/byte/result limits instead of claiming complete coverage. |
| `run(argv, cwd, timeout_s, env)` | No shell interpolation. Default 120 s, maximum 900 s. Scrubbed environment; only CI, TERM, NO_COLOR and PYTHONHASHSEED overrides. |
| `job_start`, `job_status`, `job_output`, `job_stop` | Three shared slots for all sync/background runs. Stop/timeout kills the process group; production PID namespaces also contain daemonized descendants. |
| `repo_sync(branch)` | Fetches **only** `https://github.com/oncoursemail/Star-AI` into `Star-AI/`; refuses dirty worktrees or active jobs. Conservative branch characters: letters, digits, underscore, hyphen and slash. |
| `repo_status`, `repo_diff` | Porcelain status and tracked-file diff using protected metadata outside `/work`. Untracked content is read separately. |
| `test_python(path_or_k)` | Prepared `/work/.venv/bin/python -m pytest -q`, with a relative test path or `-k` expression, 900 s maximum. |
| `test_frontend()` | Prepared frontend's `npm test -- --reporter=dot`, 900 s maximum. |
| `info()` | Python/SDK versions, disk free, active jobs and limits, including when all three slots are occupied. |

File tools walk directory descriptors using `O_NOFOLLOW`; `..`, symlinks (even
internal ones), hardlinks and special files are rejected. Edits are expected to be
sequenced by the client, not issued concurrently with commands that rewrite the
same files. A read/write tool is not a substitute for a Git commit or a backup.

All launches use `prlimit`: 8 GiB virtual address space, CPU seconds equal to the
rounded-up timeout, 64 MiB per file, 128 processes per service UID, 1024 descriptors,
and no core dumps. systemd additionally caps aggregate memory at 4 GiB, tasks at
384, and CPU at 200%; outer container quotas are still required. Node's heap is
limited to 1 GiB and its large WebAssembly trap reservation is disabled. Resource
usage is Linux `wait4` user/system CPU and maximum RSS, not an exact simultaneous
sum of every descendant's memory.

Combined stdout/stderr goes to a file, not an unbounded memory buffer. Responses
return the last **60 KiB**, full **captured** size, truncation note, exit code,
duration and resource usage. Output reaching the file limit is marked; bytes never
successfully written beyond that limit cannot be counted. Completed output is
retained for at most 32 jobs (at most 2 GiB of captured output) and is cleared on
restart; job IDs are not persistent.
Tool argument payloads are capped at 1 MiB and serialized tool results at 256 KiB.
HTTP request bodies are capped even without Content-Length; incomplete uploads
have a 10-second deadline. The shared HTTP limit is 120 requests per minute.

Direct shell entry points, privilege/network-administration tools, SSH/scp/netcat,
and `curl`/`wget` are denied. The last two are **deliberately denied for all targets**,
not just private URLs, to avoid option/proxy/redirect/DNS ambiguities. Python public
HTTPS downloads remain possible under the kernel firewall.

There is **no push tool and no GitHub token** here. Return patches/results to chat
and use ChatGPT's separately authorized GitHub connector for commits and draft PRs.
Git metadata is kept outside the mutable worktree; helper commands disable hooks,
credentials, submodules, external diff/textconv and redirects. `repo_sync` has no
repository URL argument. Its allow-list constrains that helper, not arbitrary
network programs: general code execution plus public HTTPS cannot guarantee that
someone will never implement their own Git/network client.

## Pause, revoke, inspect and remove

As root inside the separate container:

```sh
touch /etc/star-workbench/PAUSED
```

Every tool, including read/status/stop tools, now refuses. The supervisor also
stops already running jobs when it notices the marker (normally within its 20 ms
poll interval, subject to scheduling). Removing the marker resumes new tool calls:

```sh
rm /etc/star-workbench/PAUSED
```

For immediate revocation or a suspected leak, **stop the tunnel and service**:

```sh
systemctl stop star-workbench-tunnel.service star-workbench.service
```

Rotate the token only while stopped, in a private root session with shell tracing
disabled; preserve 0600 ownership/permissions, update the private connector
configuration, then restart. Recreating the container is safer after compromise.
Do not print a new token in a script or send it to the model.

The audit log is `/var/log/star-workbench/audit.jsonl`, readable by root. Example:

```sh
tail -n 30 /var/log/star-workbench/audit.jsonl
```

Each request has start/finish records: timestamp, tool, argument metadata and exit
code; background completion has its own record. **All strings are replaced with
byte counts and SHA-256 hashes**, including paths, inline Python, environment values
and dictionary keys, so contents/secrets are not logged. This intentionally trades
human-readable arguments for privacy. The server opens the root-owned file only
with `O_APPEND`, never truncates/rotates it, and jobs cannot mount it. It is not a
cryptographically tamper-proof log against container root. At 128 MiB it fails
closed; archive/reset it as root while the service is stopped.

Server access/error logs are disabled to avoid URL/body leakage. The tunnel wrapper
forwards **only the first public hostname** into journald and suppresses everything
else, including cloudflared request-error logs. Other reverse proxies or clients
can still log a path credential: review their logging before adding them.

The simplest uninstall is to disable both services and destroy the dedicated
container. To keep the container, stop/disable the workbench and tunnel first,
remove their unit files, run `systemctl daemon-reload`, and remove `/opt/star-workbench`,
`/etc/star-workbench`, `/var/lib/star-workbench`, `/var/log/star-workbench` and `/work`
only after exporting needed code/audits. Remove the two dedicated service accounts.
Only after **all their processes are gone** should root remove the dedicated
`inet star_workbench` nftables table and its firewall unit. Never flush unrelated
firewall tables. Disabling the firewall service alone intentionally leaves its
rules installed, so stopping a unit cannot silently open LAN access.

## Tunnel lifecycle and a stable hostname

`tunnel.sh` downloads Cloudflare's official **2026.10.0** amd64/arm64 binary and
checks its hard-coded SHA-256 before installation. It disables auto-update so a
reviewed version is not silently replaced. To update, review a new official release,
update its pinned hash, and rerun the tests/review; do not bypass the checksum.

A Quick Tunnel hostname changes on restart and has no uptime guarantee. Its URL
command reads only the current systemd invocation, not historical journal entries.
Run `bash /opt/star-workbench/tunnel.sh url` again once the new tunnel has announced
its hostname and update the connector's private URL. Quick Tunnels do not support
SSE; this server uses stateless JSON instead.

For ongoing use, create a **named Cloudflare Tunnel**, route an owned hostname to
`http://127.0.0.1:8765`, and replace the quick-tunnel unit with Cloudflare's reviewed
named-tunnel setup. Keep tunnel credentials outside `/work`, readable only by the
separate tunnel account. Retain the workbench token gate and request-log suppression;
never enable unauthenticated origin access or log the full MCP path. The hostname
can then remain stable through restarts. Follow [Cloudflare's named-tunnel guide](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-local-tunnel/).

## Tests and deployment acceptance

From the repository root, with the project's declared dependencies installed:

```sh
pytest -q tests/test_workbench_*.py
pytest -q
bash -n server/workbench/install.sh
bash -n server/workbench/tunnel.sh
```

Tests do not install packages, contact the network, need root, use a real keyring,
or start a tunnel. They execute file operations, twenty traversal attempts, a
parent-directory swap, hardlink/FIFO rejection, actual prlimit timeout/output/memory
limits, jobs, patch hunks, audit redaction/capacity, every-tool kill refusal, HTTP
authentication and request bounds. The Git lifecycle test redirects the fixed fetch
call to a temporary local fixture, explicitly asserting its original URL.
The MCP test initializes the **real SDK server**, lists tools, and calls
`ws_write`, `run`, `ws_read` through the authenticated ASGI Streamable HTTP endpoint.
It skips only when the declared SDK is absent; a skip is **not** protocol verification.

Installer/firewall/unit/pin tests are offline contract tests, not proof that a
particular host kernel enforces a policy. Before exposing a deployment, an operator
must actually verify systemd credentials, namespace isolation (including denied
access to connector state), DNS/public HTTPS connectivity, private-network and IPv6
rejection, hard resource limits, quota behavior, kill-switch cancellation, a
successful prepared Python/frontend test run, and an authenticated remote MCP
roundtrip. Do not call an unexecuted acceptance checklist a passing test.

References: [official MCP v1 maintenance-line SDK](https://pypi.org/project/mcp/1.30.0/),
[Cloudflare release and checksums](https://github.com/cloudflare/cloudflared/releases/tag/2026.10.0),
[Quick Tunnel limitations](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/),
[systemd credentials](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#LoadCredential=ID:PATH).
