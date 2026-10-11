"""Deterministic, offline build plans for the shipped Roblox starters.

A check ID is a verification *target*, not evidence that a build passed.
The Studio catalogs describe an older layout in places, so their check IDs
must be treated as requirements to reconcile, not assumed to match source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from star.studio_milestones import GAMES, load_milestones


@dataclass(frozen=True)
class BuildStep:
    id: str
    description: str
    depends_on: tuple[str, ...]
    create: tuple[str, ...]
    template_module: str
    check_ids: tuple[str, ...]
    token_budget: int


@dataclass(frozen=True)
class BuildPlan:
    brief: str
    template: str
    milestones: tuple[BuildStep, ...]
    unsupported: tuple[str, ...]
    max_failed_repairs: int


@dataclass(frozen=True)
class NextStep:
    kind: str  # build, repair, stopped, complete, or unsupported
    milestone: BuildStep | None = None
    failed_check: str | None = None
    reason: str = ""


# Every file below exists in the corresponding source template. Generated
# Workspace instances are not claimed to exist before the server runs.
_MODULES: dict[str, tuple[tuple[str, str, tuple[str, ...], int], ...]] = {
    "obby": (
        ("course", "Create course and spawn", ("ServerScriptService/CourseBuilder.luau",), 1400),
        ("checkpoints", "Connect checkpoint progression", ("ServerScriptService/CheckpointService.luau", "ReplicatedStorage/Shared/StageProgression.luau"), 2000),
        ("hazards", "Connect server-controlled hazards", ("ServerScriptService/KillService.luau",), 1300),
        ("finish", "Connect finish and HUD", ("ServerScriptService/FinishService.luau", "StarterPlayer/StarterPlayerScripts/StageHud.client.luau"), 1500),
    ),
    "tycoon": (
        ("plots", "Create plots and claim ownership", ("ServerScriptService/Plots.luau",), 1600),
        ("economy", "Add server-validated purchases and production", ("ReplicatedStorage/Shared/Economy.luau", "ServerScriptService/Tycoon.server.luau"), 2300),
        ("hud", "Display owned upgrades and wallet", ("StarterPlayer/StarterPlayerScripts/Hud.client.luau",), 1100),
        ("saves", "Persist ownership and cash", ("ServerScriptService/PlayerData.luau",), 1700),
    ),
    "simulator": (
        ("economy", "Define costs, rewards and multipliers", ("ReplicatedStorage/Shared/CostCurve.luau", "ReplicatedStorage/Shared/MultiplierMath.luau"), 1800),
        ("service", "Validate progression and rate limits on server", ("ServerScriptService/SimulatorService.luau", "ReplicatedStorage/Shared/RateLimiter.luau"), 2500),
        ("saving", "Save server-owned player state", ("ServerScriptService/ProfileStore.luau",), 1500),
        ("hud", "Connect read-only interface", ("StarterPlayer/StarterPlayerScripts/Simulator.client.luau",), 1100),
    ),
    "rounds": (
        ("state", "Define phase transitions", ("ReplicatedStorage/Shared/RoundState.luau",), 1500),
        ("arena", "Create lobby and disposable arena", ("ServerScriptService/ArenaFactory.luau",), 1700),
        ("controller", "Run server-owned phases and scoring", ("ServerScriptService/RoundServer.server.luau", "ReplicatedStorage/Shared/WinnerRules.luau"), 2300),
        ("hud", "Display round progress", ("StarterPlayer/StarterPlayerScripts/RoundHud.client.luau",), 1200),
    ),
}
_CHECKS = {
    "obby": (("obby.checkpoints",), ("obby.checkpoints",), ("obby.kill_handlers",), ("obby.finish",)),
    "tycoon": (("tycoon.plots",), ("tycoon.purchase_server",), ("tycoon.buy_buttons",), ("tycoon.upgrade_assets",)),
    "simulator": ((), (), (), ()),
    "rounds": (("rounds.state",), ("rounds.spawns",), ("rounds.phase_controller",), ("rounds.timer",)),
}
# Explicit capability boundaries. These are *not* secretly added as imaginary
# features by selecting a vaguely similar template.
_UNSUPPORTED = {
    "multiplayer trading": ("trade", "trading"),
    "procedural world generation": ("procedural", "random terrain", "world generation"),
    "combat weapons": ("gun", "weapon", "fps", "shooter"),
    "vehicle physics": ("vehicle", "driving", "car racing"),
    "pet system": ("pet", "pets"),
}
# The simulator starter genuinely has buyable pets.
_SUPPORTED_EXCEPTIONS = {"simulator": frozenset({"pet system"})}


def build_plan(brief: str, template: str, *, max_failed_repairs: int = 3) -> BuildPlan:
    """Plan template modules in dependency order, without models or Studio.

    Unknown requested capabilities are surfaced as unsupported, not generated.
    'results' accepted by next_step maps check IDs to booleans; no check runs here.
    """
    if not isinstance(brief, str) or not brief.strip():
        raise ValueError("brief must be nonempty")
    if template not in _MODULES:
        raise ValueError("unknown template")
    if type(max_failed_repairs) is not int or max_failed_repairs < 0:
        raise ValueError("max_failed_repairs must be a nonnegative integer")
    lower = brief.casefold()
    unsupported = tuple(name for name, keywords in _UNSUPPORTED.items()
                        if name not in _SUPPORTED_EXCEPTIONS.get(template, ())
                        and any(word in lower for word in keywords))
    # Validate references against the shipped Studio catalog. The simulator
    # intentionally has no Studio manifest, therefore has no check IDs.
    available = {m.id for m in load_milestones(template)} if template in GAMES else set()
    steps = []
    for index, ((identifier, description, files, budget), checks) in enumerate(
            zip(_MODULES[template], _CHECKS[template])):
        if not set(checks) <= available:
            raise ValueError("build plan references unknown Studio check")
        steps.append(BuildStep(
            id=identifier,
            description=description,
            depends_on=(steps[-1].id,) if steps else (),
            create=tuple("examples/roblox-templates/" + template + "/" + f for f in files),
            template_module=files[0],
            check_ids=checks,
            token_budget=budget,
        ))
    return BuildPlan(brief.strip(), template, tuple(steps), unsupported, max_failed_repairs)


def next_step(plan: BuildPlan, results: Mapping[str, bool] | None = None,
              *, failed_repairs: Mapping[str, int] | None = None) -> NextStep:
    """Return the first unverified step or bounded repair target.

    A missing check result is never treated as passed. A failed check is
    retried until its per-check failure count reaches the plan's limit.
    Record counts from actual failed repair attempts, not from check polling.
    """
    results = {} if results is None else results
    failed_repairs = {} if failed_repairs is None else failed_repairs
    if plan.unsupported:
        return NextStep("unsupported", reason="Unsupported capabilities: " + ", ".join(plan.unsupported))
    for step in plan.milestones:
        for check in step.check_ids:
            if check in results and results[check] is False:
                if failed_repairs.get(check, 0) >= plan.max_failed_repairs:
                    return NextStep("stopped", step, check, "Repair attempt limit reached")
                return NextStep("repair", step, check, "Repair failing Studio check")
        if not step.check_ids or any(results.get(check) is not True for check in step.check_ids):
            return NextStep("build", step, reason="Build or verify this milestone")
    return NextStep("complete", reason="All available Studio checks passed")
