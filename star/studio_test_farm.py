"""Pure admission preview for concurrent, explicitly selected Roblox Studio tests.

Roblox Studio's MCP selects an open instance by studio_id. StudioTestService
supports one multiplayer test per Studio process and 1..8 simulated clients.
Open Cloud Luau Execution is a *separate* headless API and does not implement
Studio multiplayer tests.

This module never starts Studio, connects to MCP or executes Luau. The caller
MUST obtain fresh trusted place identities/approval via the existing guarded
studio_loop logic, then recheck both immediately before real execution.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

STUDIO_MAX_CLIENTS = 8
MAX_INSTANCES = 32
MAX_SCENARIOS = 64

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


def _id(value: str) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _place(universe_id: int, place_id: int) -> bool:
    return (type(universe_id) is int and type(place_id) is int
            and ((universe_id == 0 and place_id == 0)
                 or (0 < universe_id < 2**64 and 0 < place_id < 2**64)))


@dataclass(frozen=True)
class StudioInstance:
    studio_id: str
    universe_id: int
    place_id: int
    identity_verified: bool = False
    active_test: bool = False
    active_test_clients: int | None = None

    def __post_init__(self) -> None:
        if not _id(self.studio_id) or not _place(self.universe_id, self.place_id):
            raise ValueError("Invalid Studio instance identity")
        if type(self.identity_verified) is not bool or type(self.active_test) is not bool:
            raise ValueError("Studio evidence must be an explicit boolean")
        if self.active_test_clients is not None and (
            type(self.active_test_clients) is not int
            or not 1 <= self.active_test_clients <= STUDIO_MAX_CLIENTS
            or not self.active_test
        ):
            raise ValueError("Invalid active Studio client count")


@dataclass(frozen=True)
class StudioScenario:
    scenario_id: str
    studio_id: str
    universe_id: int
    place_id: int
    simulated_clients: int
    timeout_seconds: int = 120

    def __post_init__(self) -> None:
        if not _id(self.scenario_id) or not _id(self.studio_id):
            raise ValueError("Invalid scenario or target id")
        if not _place(self.universe_id, self.place_id):
            raise ValueError("Invalid expected place identity")
        if (type(self.simulated_clients) is not int
                or not 1 <= self.simulated_clients <= STUDIO_MAX_CLIENTS):
            raise ValueError("A multiplayer test requires 1 to 8 clients")
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 600:
            raise ValueError("Invalid test timeout")


@dataclass(frozen=True)
class TestDecision:
    scenario_id: str
    reason: str


@dataclass(frozen=True)
class StudioFarmPreview:
    admitted: tuple[str, ...]
    waiting: tuple[TestDecision, ...]
    rejected: tuple[TestDecision, ...]


def preview_studio_farm(
    instances: tuple[StudioInstance, ...],
    scenarios: tuple[StudioScenario, ...],
    *,
    approved_places: frozenset[tuple[int, int]] = frozenset(),
    max_parallel_studios: int = 2,
    max_total_clients: int = 8,
) -> StudioFarmPreview:
    """Select non-conflicting tests without connecting or modifying Studio.

    Place approval comes from trusted host configuration, not a worker report.
    The host must still enforce studio_loop's protected-place/unsaved-place
    checks, service permissions and run-scoped instance locks at dispatch time.
    """
    if (type(instances) is not tuple or type(scenarios) is not tuple
            or len(instances) > MAX_INSTANCES or len(scenarios) > MAX_SCENARIOS
            or any(type(x) is not StudioInstance for x in instances)
            or any(type(x) is not StudioScenario for x in scenarios)):
        raise ValueError("Invalid Studio farm inputs")
    if (type(max_parallel_studios) is not int
            or not 1 <= max_parallel_studios <= MAX_INSTANCES
            or type(max_total_clients) is not int
            or not 1 <= max_total_clients <= 128):
        raise ValueError("Invalid farm capacity")
    if (type(approved_places) is not frozenset
            or any(type(x) is not tuple or len(x) != 2
                   or not _place(x[0], x[1]) for x in approved_places)):
        raise ValueError("Invalid operator approval snapshot")
    if len({x.studio_id for x in instances}) != len(instances):
        raise ValueError("Duplicate Studio connection ids")
    if len({x.scenario_id for x in scenarios}) != len(scenarios):
        raise ValueError("Duplicate test scenario ids")

    by_id = {x.studio_id: x for x in instances}
    busy = {x.studio_id for x in instances if x.active_test}
    # Unknown active-client counts conservatively reserve all eight clients.
    used_clients = sum(
        (x.active_test_clients or STUDIO_MAX_CLIENTS)
        for x in instances if x.active_test
    )
    used_studios = len(busy)
    accepted: list[str] = []
    waiting: list[TestDecision] = []
    rejected: list[TestDecision] = []

    for test in scenarios:
        studio = by_id.get(test.studio_id)
        if studio is None:
            rejected.append(TestDecision(test.scenario_id, "studio_unavailable"))
            continue
        if (not studio.identity_verified
                or (studio.universe_id, studio.place_id)
                != (test.universe_id, test.place_id)):
            rejected.append(TestDecision(test.scenario_id, "identity_mismatch"))
            continue
        if (test.universe_id, test.place_id) not in approved_places:
            rejected.append(TestDecision(test.scenario_id, "place_not_approved"))
            continue
        if test.studio_id in busy:
            waiting.append(TestDecision(test.scenario_id, "studio_busy"))
            continue
        if used_studios >= max_parallel_studios:
            waiting.append(TestDecision(test.scenario_id, "studio_capacity"))
            continue
        if used_clients + test.simulated_clients > max_total_clients:
            waiting.append(TestDecision(test.scenario_id, "client_capacity"))
            continue
        accepted.append(test.scenario_id)
        busy.add(test.studio_id)
        used_studios += 1
        used_clients += test.simulated_clients

    return StudioFarmPreview(tuple(accepted), tuple(waiting), tuple(rejected))
