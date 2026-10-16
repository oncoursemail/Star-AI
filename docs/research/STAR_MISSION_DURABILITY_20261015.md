# STAR Durable Missions: evidence, safe scope and open-source integration research (2026-10-15)

**Status:** `star/mission_checkpoint.py` and an opt-in hook in `star.agent_runtime.run_plan`
exist in this development PR. They have no default UI switch, no active deployment
and no write-operation replay. GitHub checks and independent device acceptance are
required before production. This is a small subsystem, not an autonomous workforce.

## Why the existing STAR architecture matters

The current STAR repository already has: `agent_runtime.run_plan`, validated DAG
ownership in `orchestration.TaskPlan`, `team_service`, a resource admission planner,
SQLite project memory, error/lesson feedback, Studio Lab and a review gate.
Do **not** install LangGraph + CrewAI + OpenHands as three competing execution
owners: that duplicates durable state, budgets and permissions.

Existing failure: when a read-only specialist finishes and the process stops
before its dependent specialist finishes, a new `run_plan` normally runs the
completed specialist again. On slow local hardware the wasted model work is
valuable. The new checkpoint is a narrow opt-in solution for that case.

## Source comparison (upstream primary docs)

| Project | Established capability | STAR adoption boundary |
| --- | --- | --- |
| LangGraph | Durable threads and checkpointers; replay and side-effect idempotency need deliberate design | Compare its recovery semantics against native STAR checkpoints before a runtime migration |
| OpenHands SDK | Workspace-backed autonomous software engineering, separate Agent Server and clients | Optional isolated coding backend; no unconditional desktop host-shell access |
| CrewAI | Role-defined team crews, stateful flows | Learn role contracts, do not duplicate STAR's existing TaskPlan scheduler |
| Pydantic AI | Deferred tool approval and integrations with durable execution engines | Borrow typed result/tool contracts and approval continuation semantics |
| Aider repo map | Source symbols and graph ranking compressed into a token budget | Measure incremental improvement over STAR's existing `workspace_search(mode=symbols)` |
| Mem0 | Memory extraction/search and hybrid retrieval | Benchmark against reviewed STAR memory, do not introduce a second authoritative memory |
| OpenTelemetry GenAI | Common trace attributes and metrics | Emit redacted timings and counts by default, never raw prompts/tool outputs without explicit consent |

References:
- https://langchain-ai.github.io/langgraph/concepts/durable_execution/
- https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/interrupts.mdx
- https://github.com/OpenHands/software-agent-sdk
- https://docs.crewai.com/en/concepts/flows
- https://pydantic.dev/docs/ai/durable-execution/overview/
- https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/
- https://aider.chat/docs/repomap.html
- https://github.com/mem0ai/mem0
- https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/

**Important source caveat:** upstream latency/benchmark claims are not STAR
hardware measurements. The Mem0 repository explicitly notes managed-platform
optimizations may be unavailable in its open-source SDK. The OpenTelemetry
semantic conventions flag prompts and model outputs as sensitive and not
collected by default.

## Implemented contract

- A trusted application constructs `MissionCheckpoint(private_db_path, project=...,
  mission_id=..., worker_revision=..., context_revision=...)`. It does not derive
  the path, permission grants or revisions from an agent's text response.
- `run_plan(..., checkpoint=checkpoint)` restores *completed* nodes only.
  Failed, blocked, timed out, cancelled and incomplete nodes must be run again.
- Task-plan fingerprint includes task IDs, roles, goals, dependencies,
  reads/writes/references/evidence, task order and max parallelism.
- Existing `mission_id` refuses a changed task fingerprint, worker revision or
  source-context revision; the operator deliberately starts a new mission.
- Result records carry a content hash to catch accidental corruption.
  SHA-256 is **not an authenticity signature** against a malicious process with
  write access to the local database.
- The entire plan MUST be read-only, whether or not the caller sets
  `allow_writes`. An external operation that edits a workspace, Studio place
  or GitHub branch must never be replayed or assumed complete using this cache.
- Data stays in one operator-chosen private SQLite file; results are limited to
  the existing bounded agent result size. Only the host chooses whether to open
  that file. No model, cloud account, source crawler or third-party package
  starts automatically.

### Example for a trusted application (not a default desktop feature)

```python
from pathlib import Path
from star.agent_runtime import run_plan
from star.mission_checkpoint import MissionCheckpoint

# project, plan, worker and immutable revisions are chosen by trusted code.
# Use a private location such as %APPDATA%/STAR/missions/ on Windows.
private_dir = Path("private-star-app-data/missions")  # example only
private_dir.mkdir(parents=True, exist_ok=True)

with MissionCheckpoint(
    private_dir / "missions.sqlite3",
    project="approved-project",
    mission_id="review-20261015-a",
    worker_revision="model-and-worker-sha256",
    context_revision="source-snapshot-sha256",
) as journal:
    report = await run_plan(plan, worker, checkpoint=journal)
```

The caller is responsible for deriving revisions from actual model settings,
worker code, prompts and approved source snapshots; inventing a constant
revision in production would make stale recovery possible. Never put the
checkpoint in a public Git repository. Follow OS ACLs and encrypt storage
where the user's threat model requires it.

## What is NOT solved

1. **Exactly-once external effects.** A filesystem/Studio/GitHub write may have
   succeeded just before a crash. Recover such operations through stable
   idempotency keys, read-after-write reconciliation, state attestation,
   explicit owner scopes and a separate independently reviewed implementation.
2. **Correctness verification.** A model worker reporting `completed` is not
   proof that its claims, citations or code pass real tests. Bind deterministic
   verifier receipts before enabling high-trust cached completion.
3. **Always-current knowledge.** Revision strings must be based on actual
   source/content snapshots. This store does not watch the external world.
4. **Shared runtime ownership.** Do not use the same writable checkpoint from
   independent processes as an agent-level distributed queue or task lease.
5. **Live resume UI.** No mission picker, automatic restarts or background
   worker scheduler has been enabled by this PR.

## Future ranked experiments (not implemented in this PR)

1. **Read-only mission recovery (implemented candidate):** crash/restart 100
   times at selected DAG boundaries; require zero replay of committed successes,
   no incorrect cross-project reuse, and correct source revision invalidation.
2. **Source-linked verifier receipts:** independent tool evidence with test IDs,
   timestamps, content SHA and scope. Refuse synthetic results.
3. **Reconciliation-first write ledger:** verify actual file/branch/Studio state
   before marking a side-effecting operation completed. No auto-repeat.
4. **Source code map:** benchmark symbol hit@10, retrieval latency and real
   Python/Luau edit-pass rate against existing symbol search, not only token use.
5. **Best-of-N gate:** compare 1/2/4 candidates using identical budgets and
   sealed evaluations; separate static check wins from genuine Studio tests.
6. **Typed tool validation:** fuzz JSON argument repair, hostile inputs and
   policy boundaries; agent output must never authorize its own tools.
7. **OpenHands sandbox pilot:** isolated, owner-authorized branch worker; prove
   credentials cannot be read from the execution sandbox.
8. **Agent tracing:** explicit local consent, redacted metadata by default,
   bounded disk storage and no telemetry by default.
9. **Memory tournament:** same project-scoped corpus, Recall@k/MRR,
   wrong-project rate, stale-source rate, refusal accuracy and p95 latency.
10. **Resource admission A/B:** real p95 time to first token, verified tasks/hour,
    prompt-cache behavior and contention while interactive chats continue.

Promotion standard: deterministic unit tests; a controlled live run where
hardware/Studio are relevant; measurable quality improvement on unseen tasks;
no unreviewed permission escalation; owner review before any deployment.
