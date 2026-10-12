# Brain 2: persistent Roblox practice, real test evidence, and cumulative learning

**Research date:** October 11, 2026  
**Implementation branch:** star/chatgpt-AP-BMYPMV-refresh-20261011  
**Stage:** Host-controlled private Open Cloud practice runner + offline tests. The separately hosted Brain 2 implementation and real Roblox account credentials are not accessible in this repository or this review environment.

## What "Brain 2 already has my Roblox account" changes

An existing authenticated account and Open Cloud key can give Brain 2 meaningful development capabilities **beyond** the Studio MCP toolset. Access is never assumed solely from an account login: Roblox APIs have individual scopes, resource selectors, and per-operation limits. A broad key may authorize resources across the owner's account, including additional experiences when the user grants those scopes. A model still should not be able to transfer the key, buy assets, spend Robux, publish production places, alter unrelated account settings, or modify player data just because testing is authorized.

Current official Roblox building blocks:

| Plane | Capabilities | Boundary |
|---|---|---|
| **Studio MCP** | Inspect native DataModel, scripts, screenshots, construct/edit approved scene, execute Studio Luau in authorized disposable project, start/stop a playtest | Host-selected instance and guarded edit identity. Existing STAR local MCP owns it; arbitrary play-input and high-risk generation remain restricted |
| **Open Cloud** | Read authorized account/experience/place metadata; build place source; publish a **Saved** version of a selected private test place; run Luau task against exactly that version; receive assertion results/logs | Test-target verification on every write, key scopes, rate budgets and unknown-outcome blocking |
| **StudioTestService** | Plugin-driven multi-client simulated players, join/leave, scripted server/client test flow | Native Studio-only path; not a replacement for Cloud headless tests |
| **Studio command line** | Run a Luau script on a local .rbxl/.rbxlx file or specific place with output and exit options | A separate OS-run Studio process; needs explicitly controlled process ownership and profile isolation |
| **Learning** | Record test hashes, confirmed saved versions, passing/failing cases; detect a case passing after a prior failure on changed source; propose a reviewed lesson | Never mark an inferred rule as trusted, update model weights, edit golden tests, or modify production automatically |

### Official research

- [Roblox Open Cloud API keys and account/resource scopes](https://create.roblox.com/docs/cloud/auth/api-keys)
- [Roblox Open Cloud API scope reference](https://create.roblox.com/docs/cloud/reference/scopes)
- [Roblox Cloud API overview](https://create.roblox.com/docs/cloud)
- [Headless Luau execution](https://create.roblox.com/docs/cloud/reference/features/luau-execution) — one task may run up to five minutes, up to ten concurrent tasks per place (rate limits can change); it can run with access to a place's DataModel
- [Official Studio scripted testing modes](https://create.roblox.com/docs/studio/testing-modes)
- [StudioTestService](https://create.roblox.com/docs/reference/engine/classes/StudioTestService)
- [Studio command-line interface](https://create.roblox.com/docs/studio/command-line-interface)
- [Roblox place CI/CD demonstration](https://github.com/Roblox/place-ci-cd-demo) — archived example, not guaranteed current production configuration
- [STAR's existing Roblox guard and Cloud procedures](ROBLOX_ACCESS.md)
- [STAR's existing lesson trust rules](STAR_LEARNING.md)

## Next: Brain 2's broader account capability matrix

The owner's existing Roblox account authorization should be presented to Brain 2 as a **verified capability inventory**, derived from key introspection or properly authorized OAuth—not as an imagined unrestricted account master key. Support the following separately reviewed capabilities as their exact scopes and owners permit:

| Account surface | Valuable agent activity | Authorization boundary |
|---|---|---|
| Experience/places | Read metadata, enumerate specifically authorized targets, inspect versions, manage test access | Read broadly where granted; modifications must select the exact universe/place, and live publish is a distinct high-impact grant |
| Assets API | Inspect assets/versions, upload meshes, models, images and audio created by a verified pipeline, attach metadata | Asset read can be routine; write/upload may consume quotas and must validate target creator, license, type and file size |
| Analytics/experiments | Measure retention, game performance, conversion and controlled experiment results | Read-only reports with provenance; changing live experiment allocation requires a separately approved operation |
| Data/memory stores | Understand schema and test persistence, exercise test inventories/economy | Isolate a test datastore; do not use live player profiles or economy balances as training material |
| Live servers / messaging | Observe permitted server health and operational outcomes | Restart/announce/ban actions are production-changing operations, never implicit side effects of a test |
| Developer knowledge | Official API dumps, Luau symbols, engine docs, annotated source revisions and unit test results | Reference code is data, not authority to expand permissions or run downloaded scripts |

Roblox's official [Assets API](https://create.roblox.com/docs/cloud/reference/features/assets) includes asset creation, versions and metadata (some endpoints are beta). The [Universe endpoints](https://create.roblox.com/docs/cloud/reference/features/universes) expose updates, playtesters and live-server operations. The [Data Stores APIs](https://create.roblox.com/docs/cloud/reference/features/storage) can reach player profiles and inventories, so testing must use separate private test data. Roblox warns that Studio API Services access can affect **the same** data stores used by the live game: see [Studio Data Stores](https://create.roblox.com/docs/cloud-services/data-stores).

An eventual Brain 2 account adapter should enumerate the actual scopes and resource selectors of its installed credentials, redact secrets and account details in model context, and expose tool schemas only for explicitly activated operations. Broad account access enables *more possibilities*; it must not make every account-mutating operation an automatic step of the code learning loop.

## Concrete feature included in this draft

New module: star/brain2_practice.py

It uses the **existing tested** star.roblox_pipeline.run_pipeline and star.roblox_cloud.RobloxCloud APIs. It deliberately does not alter their core authentication or authorization code and does not add any new model-facing network or shell tool.

The operator authors a **local private configuration file outside the source project**, for example C:\STAR-Private\brain2-practice.json:

\`\`\`json
{
  "project": "my-roblox-game",
  "source": "C:\\Projects\\MyGame",
  "universe_id": 123456789,
  "place_id": 987654321,
  "builder": "rojo",
  "interval_seconds": 1800,
  "daily_limit": 24
}
\`\`\`

Replace the IDs with the **actual** private test experience IDs already selected in STAR. The source folder must contain a valid place project and a nonempty ServerScriptService.Tests test suite. No credential goes in this file. The owner selects the test experience in STAR as described in ROBLOX_ACCESS.md; the practice runner independently confirms the selected place and account ownership at the beginning of every cycle and before Cloud writes.

Dry run, with no Roblox calls or mutation:

\`\`\`powershell
python -m star.brain2_practice --plan "C:\STAR-Private\brain2-practice.json" --home "$env:APPDATA\STAR"
\`\`\`

Run **one** authorized Saved-version build and verified Cloud Luau test:

\`\`\`powershell
python -m star.brain2_practice --plan "C:\STAR-Private\brain2-practice.json" --home "$env:APPDATA\STAR" --run
\`\`\`

Run up to four spaced practice cycles **from an explicitly operator-started process**:

\`\`\`powershell
python -m star.brain2_practice --plan "C:\STAR-Private\brain2-practice.json" --home "$env:APPDATA\STAR" --run --cycles 4
\`\`\`

For ongoing operation, the operator can schedule **the one-cycle command** at the configured interval using Windows Task Scheduler. Use a single task instance, no concurrent copies, a dedicated test account where practicable, and a host-managed persistent data directory. The SQLite gate rejects overlapping attempts and enforces a minimum five-minute cadence plus the configured daily budget. This branch **does not install a Windows service, schedule tasks on your PC, or automatically run in the background**.

The directory passed to --home must be the actual local STAR configuration/state directory, not a Git working directory or the game's source folder. If the desktop uses a custom data home, specify that exact location. For the Rojo builder, install the pinned reviewed Rojo executable as documented in ROBLOX_ACCESS.md.

### What the run returns

A concise JSON receipt, never the entire account, key, output log or raw source:

\`\`\`json
{
  "cycle_id": 1,
  "status": "passed",
  "project": "my-roblox-game",
  "source_sha256": "actual_64_character_sha256_from_build",
  "saved_version": 4,
  "passed": 12,
  "failed": 0,
  "learning_candidates": 0
}
\`\`\`

The numbers above are **illustrative**, not a real Brain 2 or Roblox test. The real runner accepts a pass only when the source hash, saved version, returned test version/target and internally consistent nonempty Luau assertion report agree. A report without evidence is unknown, not "passed".

The local SQLite record stores the tested source hash, selected experience IDs, saved version, real assertion pass/fail counts and bounded test names. It does not store raw console errors, execution code, account secrets or large untrusted tool responses.

### Real learning, not invented competence

After two different tested source revisions, if the **immediately previous verified failed test case** is now an actual passing test, the runner can submit up to five candidate "verified-fix" lessons to STAR's existing local Lessons review queue. The note says this is a change in observed test outcome, **not proof that a specific patch caused it**. No candidate is auto-approved.

This already gives Brain 2 the beginnings of genuine outcome-driven experience:
1. Source revision A has a recorded failing Luau case.
2. Brain 2 or a developer makes a source change in the owner-controlled workspace (outside this helper).
3. Source revision B is saved and tested against the selected private Roblox test place.
4. The same test passes; an evidence-backed candidate is recorded, linked to both source digests and the saved version.
5. The owner reviews the code diff and approves a reusable lesson, or rejects it.

STAR does not train new model weights through this loop. Real fine-tuning would be a separate reviewed process with rights-confirmed data, held-out task sets, rollback and evaluation gating. A passed test is one signal, not a blanket code-quality guarantee.

### When a test is interrupted

The ledger writes a durable "running" marker **before** a possible Saved-version upload. If the process crashes, a Roblox request times out or the result is incomplete, that marker becomes "unknown" or remains "running"; subsequent calls refuse to send more writes until an operator checks Roblox's version history and acknowledges that run.

After inspecting the exact target and any pending task, the operator may use:

\`\`\`powershell
python -m star.brain2_practice --plan "C:\STAR-Private\brain2-practice.json" --home "$env:APPDATA\STAR" --acknowledge 17
\`\`\`

17 here is an example local cycle ID, not an actual run. Acknowledgement records the operator's manual reconciliation and does **not** declare a previously unknown publish successful. The assistant/model is not offered this command as a tool.

## What remains before Brain 2 can autonomously build and learn in Studio

1. **Integrate the privately hosted Brain 2 runtime** with STAR's reviewed local MCP. The private Brain 2 source/service is not in this public repository. Verify real tool catalogs, Studio instance identity, safe serialized operations, cancellation, unknown-outcome journal and process teardown.
2. **Studio practice lane**: Build an independently reviewed host-controlled native test harness using StudioTestService for multiplayer and StudioDeviceSimulatorService / VirtualInput for device/UI test scenarios. Do not assume that merely having a Studio ID safely binds simulated input to the correct play session.
3. **Asset and UI evaluation**: record real Studio screenshots; run bounds/alignment/contrast/responsive checks; compare to approved design references and mesh/material budgets. Cloud headless tests cannot prove visual quality.
4. **Code repair loop**: preserve source snapshots and per-test provenance; propose small changes; run local static checks; isolate edits; run regression suite; retry only idempotent reads; promote code only after independent test and rollback checks.
5. **Learning engine**: build an indexed, project-scoped evidence graph of source symbols, API docs, behavior fixtures and verified fixes. Version candidate strategies and score them on held-out tasks rather than trusting model confidence.
6. **Owner-selected grants**: separate Roblox account read scopes, private test-place write scopes, and high-impact actions (Live Publish, asset uploads/quota, social/account operations, moderation, purchasing or player data). The broad API key is a credential, not a standing instruction to use every operation.

## Acceptance gates

- Unit tests: no network, no GPU, no keyring, no Studio; exercise bad manifests, wrong target, invalid reports, duplicate/budgeted runs, interruptions, spoofed successes and review-only learning.
- Repository CI: full Python regression suite and frontend tests; no unreviewed policy changes.
- Real device: owner authorizes **one** private Cloud Saved publish and Luau test, checks that it matched the exact place/version and did not change the published live game.
- Interrupted write: deliberately simulate a response drop and prove the ledger prevents automatic retry.
- Candidate lesson: controlled failing spec, changed source, then passing same spec; prove the resulting candidate is not automatically trusted.
- Studio: separate disposable PC native test, screenshots, player testing, and preserved unsaved independent places; requires Brain 2 service operator and explicit approval.

**Do not claim:** Brain 2 is running continually, its account key was inspected, it trained a neural network, it performed native Studio multiplayer playtests, or it has audited account-wide action permission merely because this source-level practice feature exists.

## Review delivery gate: refreshed replacement for PR #103

Task AP-BMYPMV-M1 confirmed that the original PR #103 branch was 121 commits behind `star/next`. Its latest Offline Python job (run 38172407607, job 114567589343) reported `2 failed, 2807 passed, 32 skipped`; both failures were the stale source expectations in `tests/test_shared_brain_variants.py`. That file is absent from the refreshed integration base. No tests were removed or weakened by this repair.

The initial replacement, PR #160, started from `0f489dcfe18b5db78a5a159d41d91a03f432838b`. While its CI ran, `star/next` advanced by 88 commits. This refreshed replacement starts directly from `64708aa425cd1e755f287c44a3271ee7c7080d8a`, without merging or rebasing any old branch. The superseded drafts are left for the owner; this task does not merge or close any PR.

The original runtime is retained byte-for-byte. All original practice tests are retained, including `test_full_existing_cloud_pipeline_runs_with_fake_roblox_not_network`. The added `test_cli_run_uses_current_cloud_pipeline_and_persists_evidence` exercises the real CLI, builder, Cloud guard, pipeline and SQLite ledger with the repository's fake transport. Its four cases cover a verified pass, an assertion failure, an empty report and a task error. They check the exact source hash and Saved version, durable outcomes and refusal to send another write after a CLI restart. Unknown outcomes are also checked after the interval expires. Together with the original eleven tests, this provides fifteen practice cases.

### Duplicate delivery status and owner gate

The three original files in PR #103 at `2a8cf51ac5d194afdd2f82adaa18534d257cc7ea` and PR #104 at `4419a6571042271ddd2e7003f1949cbf559a385d` have identical Git blob SHAs:

| Original file | Shared blob SHA |
|---|---|
| `star/brain2_practice.py` | `6388fc31e6d9e7b189d360f8be05178441c8c9c4` |
| `tests/test_brain2_practice.py` | `ee0d3dc126c20420e60c562a9efc716144636b1f` |
| `docs/BRAIN2_CONTINUOUS_PRACTICE_20261011.md` | `739024fb388245aad21d881b05fd5753013b4a0d` |

The overlap was real at review time. During final verification, GitHub reported PR #104 **closed without merging**, with `closed_at` equal to `2026-10-12T03:07:39Z`. This task did not close or modify #104. It is therefore not an active competing delivery at that observation; the earlier note saying both original PRs remained open is superseded.

Only the owner may land the latest refreshed replacement. Do not independently land the original #103 or the stale replacement #160 as additional Brain 2 deliveries. If #104 is reopened or another integration reintroduces its payload, reconcile the duplicate files first and retain the added regression coverage. No unit test can choose the owner's landing order: the blob comparison and PR state establish this finding.

Verification uses GitHub Actions on the refreshed replacement draft, with exact observed commands, commit and results recorded in its description. Results from the earlier base are historical, not proof for the refreshed head. Nothing was run locally. No real Roblox request, native Studio test or live Brain 2 acceptance is claimed by the offline fixtures.
