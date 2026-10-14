import hashlib
import json
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from star.shared_brain.protocol import SharedBrainTools
from star.shared_brain.store import SharedBrain


@pytest.fixture
def brain(tmp_path):
    (tmp_path / "star").mkdir()
    source = tmp_path / "star/source.py"
    source.write_text("def lookup():\n    return 1\n")
    (tmp_path / "graphify-out").mkdir()
    graph = {"nodes": [{"id": "lookup", "label": "lookup()", "source_file": "star/source.py",
                         "source_location": "L1", "_origin": "ast"}], "links": []}
    (tmp_path / "graphify-out/graph.json").write_text(json.dumps(graph))
    value = SharedBrain(tmp_path)
    value.sync()
    yield value
    value.close()


def test_model_dispatch_query_and_candidate_feedback(brain):
    tools = SharedBrainTools(brain, actor="codex-test")
    result = tools.call("shared_brain_query", {"question": "lookup"})
    assert result["matches"][0]["node"]["source_location"] == "L1"
    outcome = tools.call("shared_brain_feedback", {"query_id": result["query_id"], "outcome": "useful"})
    assert not outcome["promoted"] and outcome["trust"] == "candidate"
    assert tools.call("shared_brain_lessons", {})["outcomes"][0]["actor"] == "codex-test"


@pytest.mark.parametrize("name", ["activate", "review", "rollback", "refresh", "execute_python", "write_fixture"])
def test_model_cannot_call_operator_actions(brain, name):
    with pytest.raises(PermissionError):
        SharedBrainTools(brain, actor="test").call(name, {})


def test_unknown_args_or_budget_cannot_expand_scope(brain):
    tools = SharedBrainTools(brain, actor="test")
    with pytest.raises(ValidationError):
        tools.call("shared_brain_query", {"question": "lookup", "workspace": "another-project"})
    with pytest.raises(ValidationError):
        tools.call("shared_brain_query", {"question": "lookup", "budget_chars": 6001})
    schemas = tools.definitions()
    schemas[0]["name"] = "activate"
    assert tools.definitions()[0]["name"] == "shared_brain_query"


def test_proposal_projection_does_not_leak_source_snapshot_or_accept_approval(brain):
    record = {"id": "a", "kind": "knowledge_alias", "state": "candidate", "config_digest": "c", "base_version": "b",
              "source_snapshot": {"private_local_path": "omitted"}}
    loop = SimpleNamespace(propose_aliases=lambda _: record, root=brain.workspace,
                           limits=SimpleNamespace(context_chars=3000))
    tools = SharedBrainTools(brain, actor="test", improvement_loop=loop)
    assert "source_snapshot" not in tools.call("shared_brain_propose_aliases", {"aliases": {"find": ["lookup"]}})
    with pytest.raises(ValidationError):
        tools.call("shared_brain_propose_aliases", {"aliases": {"find": ["lookup"]}, "human_approved": True})


def test_active_query_uses_only_injected_reviewed_controller_and_tool_budget(brain):
    from star.shared_brain.store import serialize
    loop = SimpleNamespace(root=brain.workspace, limits=SimpleNamespace(context_chars=3000),
                           retrieve=lambda q: {"query": q, "active_version": "reviewed-fixture",
                           "records": [{"identifier": str(i), "source": "star/source.py", "text": "x"*900}
                                       for i in range(2)], "context_chars": 0})
    result = SharedBrainTools(brain, actor="test", improvement_loop=loop).call(
        "shared_brain_active_query", {"question": "lookup"})
    assert result["active_version"] == "reviewed-fixture" and len(result["records"]) == 2
    assert len(serialize(result)) <= 3000
    with pytest.raises(ValueError, match="cannot be trimmed"):
        SharedBrainTools(brain, actor="test", improvement_loop=loop).call(
            "shared_brain_active_query", {"question": "lookup", "budget_chars": 1500})


def test_controller_cannot_expose_another_project_or_unmeasured_budget(brain):
    loop = SimpleNamespace(root=brain.workspace / "other", limits=SimpleNamespace(context_chars=3000))
    with pytest.raises(ValueError, match="selected project"):
        SharedBrainTools(brain, actor="test", improvement_loop=loop)
    loop.root = brain.workspace
    loop.limits.context_chars = 8000
    with pytest.raises(ValueError, match="context budget"):
        SharedBrainTools(brain, actor="test", improvement_loop=loop)
