# Sources for roblox-multi-agent-studio

Written 2026-10-13. The field evidence comes from the owner's private Paintball port project, where Claude and Codex
agents shared one Roblox Studio place from 2026-09-20 to 2026-10-08. It was read only and rewritten as general lessons.
The official pages are from the Roblox Creator Documentation (CC-BY-4.0), found through the STAR Knowledge index.

| Label | Evidence |
|---|---|
| F1 | Project AGENTS.md and CLAUDE.md: claim files before editing, never release stale claims automatically, the newest handoff block wins, verify files before trusting notes, the Studio lock and the user-idle rule |
| F2 | Project INTEGRATOR_RUNBOOK.md: exactly one integrator installs and saves; the others post ready lists; the role is handed over in writing when usage limits hit |
| F3 | Project handoff log CONTINUE_IMMEDIATELY.md: the Studio session mutex; a usage limit left partial, uncommitted edits and held claims; starting a match from an extra client froze that client, so a Studio-only server hook replaced it |
| F4 | Project SWARM_REVIEW_20261008.md: the shared git index race (stage only your own paths, then a plain commit takes everything staged); the reviewer agent's method; whole-file diffs caused by line-ending changes |
| F5 | Project QA_SCENARIOS.md, the play-QA skill and the CLAUDE.md hard rules: PASS/FAIL/INCOMPLETE/PENDING verdicts, time-boxed steps, observers that disconnect themselves, and scripted shortcuts never counting as normal-play acceptance |
| S1 | https://create.roblox.com/docs/studio/testing-modes |
| S2 | https://create.roblox.com/docs/reference/engine/classes/BindableFunction |
| S3 | https://create.roblox.com/docs/reference/engine/classes/RunService |
| S4 | https://create.roblox.com/docs/reference/engine/classes/ServerStorage |
| S5 | https://create.roblox.com/docs/reference/engine/classes/Players |
| S6 | https://create.roblox.com/docs/reference/engine/classes/HttpService |

API names verified with the knowledge service /api-lookup on 2026-10-13: RunService:IsStudio, BindableFunction,
BindableFunction.OnInvoke, ServerStorage, Instance.Archivable, Players.PlayerAdded, HttpService:JSONEncode,
RBXScriptConnection:Disconnect.
