# STAR Autonomous Evolution — Research, Implementation, and Release Gates

**Audited October 11, 2026. Implementation status:** This development branch
adds a local, candidate-only official documentation watcher and a native React
Research Watch interface. These changes are not foundation-model retraining,
automatic PR merging, unattended public publishing, or production signing.

## Repository reality

The inspected integration branch has:
- A short-lived GitHub App token and limited draft skill PR creator in
  star/github_app.py and star/selfbuild.py.
- Project-scoped approved lessons and FTS5 knowledge in star/knowledge.py,
  star/learning.py and star/lessons.py.
- Offline evaluators and held-out comparison in star/eval_gate.py.
- Windows packaging, packaged smoke checks, SHA256SUMS and GitHub Releases
  in .github/workflows/windows-desktop.yml.
- A public release updater in star/updates.py.

As independently checked through GitHub on October 11, main did **not**
report branch protection and the repository had no configured rulesets.
GitHub permissions and environment protection must be configured in the
repository UI by its owner. Source v0.9.0 was not the latest public installer:
the observed public release was v0.8.1.

## What this PR really implements

The new star/evolution_research.py source watcher:
1. Looks up documentation ONLY in a fixed reviewed catalog: Roblox Studio
   MCP, Roblox external tools, Luau typechecking, GitHub Actions security,
   and official GitHub build attestation guidance.
2. Makes sequential HTTPS GET requests with no proxy, redirects, credentials,
   or model-defined destination. It never changes the source URL.
3. Uses ETag and Last-Modified when a baseline revision exists.
4. Refuses unexpected status, media type, oversized payloads and empty docs;
   caps each response at one million decoded bytes.
5. Normalizes HTML text after removing scripts and navigation; fingerprints
   all normalized text, not just the retained excerpt.
6. Stores immutable observations and prior-revision digests in SQLite.
   All observations have status candidate and can never grant permission.
7. Exposes on-demand checks, status, and source excerpts in the desktop
   Tools -> Research Watch panel. No website-preview requests or silent
   background polling are made.
8. Provides an explicit Send candidate to Learning review action: it takes
   the inspected source revision and creates a project-scoped, unreviewed
   fact candidate through STAR's existing LessonStore, where safety checks
   reject permission/secret-like instructions. Only the owner's separate
   Projects -> Learning approval can make it trusted.
9. Uses Roblox's official agent-readable Markdown documentation where
   available and the canonical Luau /types/ URL to avoid redirects.
10. Offers opt-in daily automatic checks inside STAR Desktop Tools. A
    persistent research_auto_check setting defaults off. A Qt timer checks
    the local research ledger at startup and hourly, fetching an approved
    source only if its last check was at least 24 hours ago (including
    failed checks). It does nothing when STAR is closed, the checkbox
    is disabled or a chat task is active. Source change observations
    remain candidates, never trusted instructions or published code.

The candidate research ledger lives at
%APPDATA%/STAR/research-watch.sqlite3 on Windows.
Automatic checks need an explicit owner opt-in in the local desktop;
no remote servers, hidden background daemon or scheduled publishing
is created.

### Commands

Status without fetching any web page:

    python -m star.evolution_research status

Explicitly check all approved sources:

    python -m star.evolution_research check

Check one official source by ID:

    python -m star.evolution_research check --sources roblox-studio-mcp

Inspect a candidate excerpt:

    python -m star.evolution_research evidence --observation 1

Use --database path/to/private.sqlite3 to isolate tests or environments.
No command writes GitHub, changes trusted lessons, runs model code or
publishes updates.

## Next architecture: separate untrusted data from privileged deployment

### Knowledge engine

Use scheduled, owner-approved source checks plus optional signed webhook
deliveries. Poll with ETags only when needed, handle Retry-After responses,
and cap daily requests. GitHub prefers webhooks over excessive polling and
serializes API requests to avoid secondary rate limits.

Archive each source ID, canonical URL, timestamp, digest, license, prior
revision and textual excerpt. Route a changed source to a candidate queue,
not the trusted memory reader. Contradictory claims remain unresolved until
independently checked and approved.

The next useful feature is a citation-to-code dependency map: track which
Luau modules, tool recipes, interface components and regression fixtures
refer to an API section so that research changes trigger targeted tests.

### Verified improvement jobs

An idempotent SQLite-backed job records source revision, frozen base SHA,
candidate branch, task digest, owner/scopes, tool budget, independent
evaluation artifact IDs, and rollback plan. Jobs have renewable leases
and cancel/reconcile a remote mutation rather than retrying blindly after
a timeout. Never let two workers write the same file or Studio place.

An independent evaluator, not the coding model, controls hidden tests.
Candidate fixes are only accepted if frozen baseline comparisons show
measured improvement without protected regressions. Result status must
distinguish passed, failed, errored, skipped, and never executed.

A success produces a draft PR with reproducer, diff, exact CI links and
evidence. STAR's existing GitHub App must remain unable to merge, alter
security workflows or issue release tags. Model-generated source, PR
comments and web docs are always data, never authority.

### Production release plane

Public releases should be delivered only from independently reviewed
source through a distinct trusted publisher:

- Configure GitHub branch rulesets for required PRs, recognized CI checks,
  reviewer approval, and blocking forced pushes/deletion. Prefer a separate
  trusted source for required checks.
- Configure a GitHub production-release Environment requiring an authorized
  independent reviewer. When configured to prevent self-approvals, the
  initiating account cannot approve its own deployment.
- Lock Python/React dependencies, include a reviewed npm lockfile and
  deterministic npm ci builds. Pin external Actions to reviewed commit SHAs.
- Run Python/React/evaluation/security checks and packaged Windows doctor,
  UI doctor and clean upgrade acceptance.
- Produce verifiable build provenance using actions/attest (current major
  version 4). Verify the exact expected GitHub repo and workflow identity.
- Sign installers and binaries with genuine Windows code-signing credentials.
  SHA256 checks alone prove downloaded integrity, not publisher identity.
- Verify published Setup, portable ZIP, SHA256SUMS and anonymous access
  before claiming a live version was shipped.
- Keep a verified rollback path that preserves local conversations, models
  and workspaces under the STAR user profile.

A GitHub Actions GITHUB_TOKEN commit does not necessarily trigger follow-up
workflow runs; use explicitly supported dispatch or an appropriately scoped
GitHub App token for approved workflow handoffs.

**Release blockers today:** server-side branch protection, independent
release authorization, actual Authenticode signing, provenance verification,
and real native Windows upgrade acceptance. None is silently assumed passed.

## What counts as self-learning

Distinguish three levels:
- Retrieved knowledge and approved project lessons: no weight training.
- Tested skill/prompt/model routing/code changes: measurable behavioral
  improvement, not changed model weights.
- Optional offline model fine-tuning: separate data licensing, privacy,
  GPU-training and independent evaluation program.

STAR should optimize correctly completed tasks per minute, not token volume,
the number of agents, or unsupported benchmark claims. Baseline and candidate
must use matched holdout cases and equivalent time/tool budgets. Track
p50/p95 latency, VRAM peak, code regressions, Studio playtest outcomes,
source precision, invalid tool calls and recovery errors.

## Threat model and test requirements

| Threat or failure | Required behavior |
| --- | --- |
| Official docs contain prompt-injection instructions | Keep as untrusted text; never change policy or launch a tool |
| 302 redirect, unexpected host, proxy or credential request | Refuse before following redirect or sending credentials |
| Huge HTML, corrupt media, 304 without a baseline | Sanitize error, retain prior digest and history |
| Content only changes in HTML nav | No false revision from navigation-only text |
| Main content changes | New candidate observation with earlier SHA256 |
| Multiple overlapping checks | Serialize successful commit and reconcile current digest |
| Tool call times out after a remote write | Inspect external state before retry |
| Agent wants to edit grader or authentication | Route to independent review; deny autonomous write |
| Passing PR build but no Windows QA | Keep release unapproved |
| Invalid signature or provenance | Block deployment and provide verifiable incident evidence |
| Lost network / unavailable Roblox Studio | Report incomplete, never imply a passing test |
| Release upgrade affects local data | Preserve backups; explicit rollback and schema review |

Offline coverage: tests/test_evolution_research.py and
frontend/src/ResearchWatchPanel.test.tsx. Real network availability, native
Windows installer behavior and GitHub rule enforcement require separate
acceptance evidence.

## Primary research sources verified in October 2026

- GitHub REST rate limits, conditional requests and queueing:
  https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
- Webhooks, HMAC validation and delivery idempotency:
  https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks
  https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- Branch rulesets and required checks:
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- Actions workflow security and GITHUB_TOKEN limitations:
  https://docs.github.com/en/actions/reference/security/secure-use
  https://docs.github.com/en/actions/concepts/security/github_token
- Artifact attestations and verification:
  https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations
  https://github.com/actions/attest
  https://cli.github.com/manual/gh_attestation_verify
- Environment reviewers:
  https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments
- Local search with SQLite FTS5:
  https://www.sqlite.org/fts5.html
- Roblox and Luau references:
  https://create.roblox.com/docs/studio/mcp
  https://create.roblox.com/docs/projects/external-tools
  https://luau.org/typecheck
- MCP authorization boundaries:
  https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization

## Review process

This is a DRAFT PR against star/claude-integration-20261010, never main.
Run all offline Python tests, Vitest, typecheck, React build, native build
doctor and independent Windows acceptance. No merge, release, auto-ready or
force-push is authorized by this implementation.
