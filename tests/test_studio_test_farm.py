"""Offline contracts for future multi-instance Studio scheduling.

No Roblox connection, credentials, model inference or game mutations.
"""
import pytest

from star.studio_test_farm import (
    StudioInstance, StudioScenario, StudioFarmPreview, preview_studio_farm,
)


def studio(studio_id="studio-a", universe=12, place=34, **changes):
    return StudioInstance(studio_id, universe, place, identity_verified=True, **changes)


def scenario(name="t1", studio_id="studio-a", universe=12, place=34,
             clients=2, timeout=120):
    return StudioScenario(name, studio_id, universe, place, clients, timeout)


def farm(instances, cases, approved=frozenset({(12, 34)}), **options):
    return preview_studio_farm(tuple(instances), tuple(cases),
                               approved_places=approved, **options)


def test_two_independent_studios_can_run_different_games_concurrently():
    result = farm(
        [studio(), studio("studio-b", universe=98, place=76)],
        [scenario(), scenario("t2", "studio-b", 98, 76, 4)],
        approved=frozenset({(12, 34), (98, 76)}),
        max_parallel_studios=2, max_total_clients=8,
    )
    assert result == StudioFarmPreview(("t1", "t2"), (), ())


def test_only_one_multiplayer_session_per_studio():
    result = farm(
        [studio()], [scenario("first"), scenario("second")],
        max_parallel_studios=2,
    )
    assert result.admitted == ("first",)
    assert result.waiting[0].reason == "studio_busy"


def test_studio_id_is_not_a_game_name_and_never_falls_back():
    result = farm([studio("same-title")], [scenario(studio_id="different-studio")])
    assert not result.admitted
    assert result.rejected[0].reason == "studio_unavailable"


def test_place_identity_must_match_exact_universe_and_place():
    result = farm([studio()], [scenario(place=35)])
    assert not result.admitted
    assert result.rejected[0].reason == "identity_mismatch"


def test_unverified_identity_does_not_admit_any_work():
    connected = StudioInstance("studio-a", 12, 34, identity_verified=False)
    result = farm([connected], [scenario()])
    assert result.rejected[0].reason == "identity_mismatch"


def test_approval_required_even_when_studio_identity_verified():
    result = farm([studio()], [scenario()], approved=frozenset())
    assert result.rejected[0].reason == "place_not_approved"


def test_unpublished_place_not_automatically_approved():
    result = farm(
        [studio(universe=0, place=0)],
        [scenario(universe=0, place=0)],
        approved=frozenset(),
    )
    assert result.rejected[0].reason == "place_not_approved"


def test_explicitly_approved_unpublished_test_may_be_planned_not_executed():
    result = farm(
        [studio(universe=0, place=0)],
        [scenario(universe=0, place=0)],
        approved=frozenset({(0, 0)}),
    )
    assert result.admitted == ("t1",)


def test_existing_multiplayer_test_is_not_overwritten():
    result = farm(
        [studio(active_test=True, active_test_clients=3)],
        [scenario()],
    )
    assert result.admitted == ()
    assert result.waiting[0].reason == "studio_busy"


def test_preexisting_tests_count_against_global_limits():
    result = farm(
        [studio(active_test=True, active_test_clients=5),
         studio("studio-b", universe=98, place=76)],
        [scenario("next", "studio-b", 98, 76, 4)],
        approved=frozenset({(12, 34), (98, 76)}),
        max_parallel_studios=2, max_total_clients=8,
    )
    assert result.waiting[0].reason == "client_capacity"


def test_unknown_active_client_count_conservatively_reserves_eight():
    result = farm(
        [studio(active_test=True),
         studio("studio-b", universe=98, place=76)],
        [scenario("next", "studio-b", 98, 76, 1)],
        approved=frozenset({(12, 34), (98, 76)}),
        max_parallel_studios=2, max_total_clients=8,
    )
    assert result.waiting[0].reason == "client_capacity"


def test_parallel_studio_limit_applies_to_currently_busy_instances():
    result = farm(
        [studio(active_test=True, active_test_clients=2),
         studio("studio-b", universe=98, place=76)],
        [scenario("next", "studio-b", 98, 76, 2)],
        approved=frozenset({(12, 34), (98, 76)}),
        max_parallel_studios=1,
    )
    assert result.waiting[0].reason == "studio_capacity"


def test_client_limit_applies_to_planned_new_tests():
    result = farm(
        [studio(), studio("studio-b", universe=98, place=76)],
        [scenario("one", clients=5),
         scenario("two", "studio-b", 98, 76, 4)],
        approved=frozenset({(12, 34), (98, 76)}),
        max_parallel_studios=2, max_total_clients=8,
    )
    assert result.admitted == ("one",)
    assert result.waiting[0].reason == "client_capacity"


@pytest.mark.parametrize("bad", [0, -1, 9, 8.0, True, "4"])
def test_client_count_range_and_type_enforced(bad):
    with pytest.raises(ValueError):
        scenario(clients=bad)


@pytest.mark.parametrize("bad", [0, -1, 601, 120.0, False])
def test_timeout_range_and_type_enforced(bad):
    with pytest.raises(ValueError):
        scenario(timeout=bad)


@pytest.mark.parametrize("bad", ["", "../x", "a/b", " x", "a\nb", "A" * 161])
def test_scenario_identifier_validation(bad):
    with pytest.raises(ValueError):
        scenario(name=bad)


def test_mixed_zero_and_published_place_id_rejected():
    with pytest.raises(ValueError):
        StudioInstance("studio-a", 0, 34)
    with pytest.raises(ValueError):
        StudioInstance("studio-a", 12, 0)


def test_duplicate_studio_and_scenario_ids_rejected():
    with pytest.raises(ValueError):
        farm([studio(), studio()], [scenario()])
    with pytest.raises(ValueError):
        farm([studio()], [scenario("t1"), scenario("t1")])


def test_invalid_approval_types_rejected():
    with pytest.raises(ValueError):
        preview_studio_farm((studio(),), (scenario(),),
                            approved_places={(12, 34)})
    with pytest.raises(ValueError):
        farm([studio()], [scenario()], approved=frozenset({(12, "34")}))


def test_mutable_or_unvalidated_inputs_rejected():
    with pytest.raises(ValueError):
        preview_studio_farm([studio()], (scenario(),))
    with pytest.raises(ValueError):
        preview_studio_farm((studio(),), [scenario()])


def test_planner_is_deterministic_and_has_no_side_effects():
    instances = (studio(),)
    scenarios = (scenario(),)
    kw = {"approved_places": frozenset({(12, 34)})}
    first = preview_studio_farm(instances, scenarios, **kw)
    second = preview_studio_farm(instances, scenarios, **kw)
    assert first == second
    assert first.admitted == ("t1",)
    assert instances[0].active_test is False
