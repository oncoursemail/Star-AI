# Security review 2 — released v0.9.0 (main)

Scope: source review of selected high-risk call paths on the released `main` revision, independently of the earlier review. Fixes are proposed against `star/next`. This is **not** a penetration test or a claim of exhaustive coverage.

## CONFIRMED BY A TEST (regression committed; CI result must also be checked)

**Medium — legacy update ZIP extraction follows pre-existing destination symlinks.**
- Released source: `star/updates.py:284-287` (`_extract_update`).
- Input: a valid ZIP containing `bundle/STAR.exe` and a target directory with `bundle` already symlinked to an outside directory. The pre-fix `dst.open('wb')` traverses that link and creates/overwrites an outside `STAR.exe`; a pre-existing `STAR.exe` symlink behaves similarly.
- Smallest fix: reject symlinks in the destination and any component, refuse overwriting existing files and create output exclusively. Implemented in `star/updates.py`. `tests/test_security_review_2.py` invokes `_extract_update` with both symlink layouts and a normal ZIP (including overwrite refusal).
- Exposure: **legacy-only** helper; the current release installer path uses `stage_installer` with SHA-256 and does not call this helper. The test demonstrates the defended execution path, not a reachable remote exploit.
- Residual: path pre-checks are not atomic against concurrent directory replacement; if legacy extraction becomes production-reachable, extract into a new private empty directory with platform-specific no-follow file creation and atomic promotion.

## SUSPECTED / design issues requiring further verification

**Low — unauthenticated single-instance activation** (`star/single_instance.py:49-54,69-79`). A process that can reach the predictable per-user Qt local-server name can send the literal bytes `activate` and cause the window to focus. This does not execute arbitrary commands and no privilege escalation was demonstrated. Smallest fix if cross-user access is possible: enforce same-user socket permissions and verify peer identity using supported OS facilities; preserve second-launch activation.

**Medium — manually selected installer authenticity depends on user consent** (`star/updates.py:192-224,227-250`). Input: a renamed, valid-MZ executable `STAR-Setup-v9.9.9.exe` of accepted size, without an adjacent checksum manifest. The selector returns `checksum_verified=False`; attended `launch_installer` permits it, intentionally. It is user-selected execution, not an automatic updater compromise. Smallest hardening: require a trusted signed/release-verified installer or surface a strong unverified warning immediately before execution. Do not interpret an adjacent untrusted SHA256SUMS file as publisher authentication.

**Medium — WebChannel is a high-value local trust boundary** (`star/react_shell.py:497-510,740-765,~800-875`). The page allows non-main-frame navigations; bridge dispatch includes actions accepting settings and file-selection-adjacent inputs. No proof that untrusted subframes can invoke the channel was obtained. Input for an adversarial integration test: embed a remote iframe that attempts `qt.webChannelTransport` calls to a side-effecting bridge action. Smallest fix if reachable: deny external subframes and bind bridge to the packaged local main frame only; authorize sensitive operations independently of page-supplied booleans.

## Reviewed protections, without an exploit demonstrated

- Roblox Open Cloud: `star/roblox_cloud.py:273-325,674-749` uses fixed known endpoint host/paths, disables environment proxies/redirect following, and rechecks the selected owner-owned test experience before writes. Review did not prove all API operations or approval UX.
- Studio edits: `star/studio_loop.py:650-705,429-489` checks Studio ID and Edit DataModel, durable target identity, unconfirmed edit journals, and compare-and-swap undo checks. Live Studio MCP/rollback behavior was not exercised.
- Tool workshop: `star/tool_workshop.py:264-282` requires successful preview before approval and contains no dynamic Python/shell execution in the reviewed workflow. Full command/skill routing is not covered.
- Documents: `star/documents.py:245-262` checks ZIP member count, path traversal, encryption, macro project, declared size and compression ratio; no real parser bomb was run. Office readers and PDF parser internals need separate fuzzing.
- Installer: `installer/STAR.iss` and `star/updates.py:135-185,227-250` were inspected; verified automatic downloads require SHA-256 and a fixed release source.

## Not covered / limits

- Exhaustive enumeration of every Open Cloud operation/scope and dynamic API responses; Roblox production credentials were deliberately not used.
- Live Roblox Studio approval clicks, playtest transport, failed/partial writes, journal recovery and undo against Studio.
- Malicious Office document/PDF corpus, ZIP race attacks, content-type smuggling and filesystem-specific symlink behavior on Windows.
- Real PySide6 cross-origin iframe experiment, cross-user named-pipe ACL inspection, local privilege-separated processes.
- Native Windows Inno Setup installation, rollback, executable signing and upstream dependency supply chain.
- Full frontend Vitest, Python full suite, native Qt UI and real Windows packaging: see pull request check history for what actually ran. No security guarantee follows from source inspection alone.
