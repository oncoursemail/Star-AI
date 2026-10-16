"""No free-access claims or phantom agent launches in STAR's ecosystem catalog."""
import pytest

from star.agent_ecosystem import (
    AGENTS, AgentObservation, AgentSpec, catalog, plan_candidates,
)


def ready(agent_id, capabilities, *, no_charge=True):
    return AgentObservation(
        agent_id=agent_id, installed=True, model_access_verified=True,
        capabilities_verified=frozenset(capabilities.split()),
        no_charge_verified=no_charge,
    )


def test_catalog_is_curated_source_linked_not_model_entitlements():
    assert len(AGENTS) >= 21
    assert len({entry.id for entry in AGENTS}) == len(AGENTS)
    assert all(x.source.startswith("https://") for x in AGENTS)
    assert any(x.id == "gemini_cli" and x.access == "account_quota" for x in AGENTS)
    assert any(x.id == "qwen_code" and "discontinued" in x.notes for x in AGENTS)
    assert any(x.id == "opencode" and x.integration == "acp" for x in AGENTS)
    assert any(x.id == "pi" and x.integration == "rpc" for x in AGENTS)
    assert any(x.id == "ollama" and x.kind == "inference_runtime" for x in AGENTS)
    assert any(x.id == "comfyui" and x.kind == "media_runtime" for x in AGENTS)
    assert any(x.id == "hermes_agent" and "independent review" in x.notes for x in AGENTS)
    assert any(x.id == "plandex" and "WSL" in x.notes for x in AGENTS)
    assert any(x.id == "openclaw" and "default-off" in x.notes for x in AGENTS)


def test_catalog_capability_filter_and_fixed_limit():
    assert all(x.id in ("comfyui",) for x in catalog(required=frozenset({"image"})))
    assert len(catalog(limit=2)) == 2
    assert all({"code", "review"} <= x.capabilities
               for x in catalog(required=frozenset({"code", "review"})))


@pytest.mark.parametrize("required,limit", [
    (frozenset({"wrong"}), 3), (["code"], 3), (frozenset(), 0),
    (frozenset(), 33), (frozenset(), True),
])
def test_catalog_fails_closed_on_invalid_input(required, limit):
    with pytest.raises(ValueError):
        catalog(required=required, limit=limit)


def test_no_records_is_not_ready_even_if_approved():
    response = plan_candidates(required=frozenset({"code"}),
                               approved_ids=frozenset({"gemini_cli"}))
    assert next(row for row in response if row.id == "gemini_cli").status == "not_available"


def test_unapproved_agent_not_ready_even_with_real_model_observation():
    response = plan_candidates(
        required=frozenset({"code"}), observations=(ready("gemini_cli", "code"),),
        allow_external_data=True,
    )
    assert next(x for x in response if x.id == "gemini_cli").status == "not_authorized"


def test_model_is_not_free_just_because_harness_is_open_source():
    response = plan_candidates(
        required=frozenset({"code"}),
        observations=(ready("opencode", "code", no_charge=False),),
        approved_ids=frozenset({"opencode"}), allow_external_data=True,
    )
    result = next(x for x in response if x.id == "opencode")
    assert result.status == "not_authorized" and "No-charge" in result.reason


def test_free_account_quota_still_needs_observed_entitlement():
    response = plan_candidates(
        required=frozenset({"research"}),
        observations=(ready("gemini_cli", "research"),),
        approved_ids=frozenset({"gemini_cli"}), allow_external_data=True,
    )
    assert next(x for x in response if x.id == "gemini_cli").status == "ready_for_owner_review"
    assert "Candidate only" in next(x for x in response if x.id == "gemini_cli").reason


def test_local_provider_fails_closed_until_observed_no_charge():
    response = plan_candidates(
        required=frozenset({"local_inference"}),
        observations=(ready("ollama", "local_inference", no_charge=False),),
        approved_ids=frozenset({"ollama"}),
    )
    assert response[0].id == "ollama"
    assert response[0].status == "not_authorized"


def test_local_provider_never_needs_cloud_approval_but_needs_real_probe():
    response = plan_candidates(
        required=frozenset({"local_inference"}),
        observations=(ready("ollama", "local_inference"),),
        approved_ids=frozenset({"ollama"}),
    )
    assert next(x for x in response if x.id == "ollama").status == "ready_for_owner_review"


def test_cloud_transfer_requires_explicit_yes_even_if_provider_is_free():
    response = plan_candidates(
        required=frozenset({"research"}),
        observations=(ready("gemini_cli", "research"),),
        approved_ids=frozenset({"gemini_cli"}),
        allow_external_data=False,
    )
    assert next(x for x in response if x.id == "gemini_cli").status == "not_authorized"


def test_configured_model_cannot_self_report_untested_tool_capabilities():
    response = plan_candidates(
        required=frozenset({"code", "mcp"}),
        observations=(ready("opencode", "code"),),
        approved_ids=frozenset({"opencode"}),
        allow_external_data=True,
    )
    assert next(x for x in response if x.id == "opencode").status == "not_verified"


def test_unknown_agent_observation_and_unsupported_caps_rejected():
    with pytest.raises(ValueError):
        ready("pretend_agent", "code")
    with pytest.raises(ValueError):
        ready("ollama", "code")
    with pytest.raises(ValueError):
        AgentObservation("ollama", True, True, frozenset(), no_charge_verified=1)


def test_duplicate_and_non_typed_observations_fail():
    v = ready("ollama", "local_inference")
    with pytest.raises(ValueError):
        plan_candidates(required=frozenset({"local_inference"}), observations=(v, v))
    with pytest.raises(ValueError):
        plan_candidates(required=frozenset({"code"}), observations=({ "agent": "opencode" },))


@pytest.mark.parametrize("bad", [
    {"required": frozenset()}, {"required": frozenset({"super_power"})},
    {"approved_ids": frozenset({"arbitrary-unsafe"})},
    {"approved_ids": {"ollama"}}, {"allow_external_data": 1},
    {"require_zero_spend": 1}, {"limit": 0}, {"limit": 99},
    {"observations": []},
])
def test_candidate_policy_invalid_settings_refused(bad):
    with pytest.raises(ValueError):
        plan_candidates(required=frozenset({"code"}), **bad) if "required" not in bad else plan_candidates(**bad)


def test_agent_spec_disallows_unsupported_capability():
    good = next(a for a in AGENTS if a.id == "ollama")
    with pytest.raises(ValueError):
        AgentSpec(good.id, good.name, good.kind, good.integration, good.access,
                  frozenset({"automatic_paid_purchase"}), good.source, good.notes, True)
