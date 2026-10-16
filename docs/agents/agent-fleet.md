# Agent fleet (Star-AI #406), first slice

Branch `star/agent-fleet-20261016`, PR to `star/next`, "Refs #406".

## Shipped in this slice
`star/agent_fleet.py` (opt-in, off unless `STAR_AGENT_FLEET=1` or `enabled=True`):
- `sample_resources()` / `plan_slots()`: live free RAM + CPU busy (via `resource_probes`) decide the slot count (cap 4);
  unmeasurable or busy machine gives 0 slots and an honest reason.
- `run_fleet()`: one git worktree + branch `star/fleet-<id>` per task, runs the task's CLI agent command (no shell),
  then the fleet itself runs the task's test command. Status `proposed` only if the agent made changes AND tests exit 0.
  Other statuses: disabled, cancelled, agent_failed, no_changes, tests_failed, error. No test command = never a pass.
- Cancel via a `threading.Event` (kills the running agent/test process). Exceptions in one worker become an `error` receipt.
- Never merges, pushes or publishes. Protected paths (Paintball, %APPDATA%\STAR) are refused.

Tests: `tests/test_agent_fleet.py` (8, offline, real git + python subprocesses).

## Left of #406
- Real ACP/CLI adapters (OpenCode, Codex, Claude Code) with capability tests; today the caller passes a raw command.
- Per-agent enable UI + "Run all enabled agents"; pause/resume; crash recovery of orphaned worktrees on restart.
- Leases through `agent_resource_planner` (this slice only does a one-shot sizing), VRAM budget, UI of budgets/blocked states.
- Diff review step, receipts persisted to disk, integration with `orchestration.TaskPlan` dependencies.
- Acceptance items: real Windows packaged test, latency/load evidence, protected-project refusal in the packaged app.
