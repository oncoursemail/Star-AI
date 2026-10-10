"""Tests for actual STAR specialist model calls, FTS memory, and model-authored tools.

All tests run offline. They establish bounded code behavior, not live
hardware, quality of a chosen local model, or remote MCP interoperability.
"""
import asyncio
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest
from jsonschema.exceptions import ValidationError

from star.agent import execute
from star.desktop_core import Settings
from star.intelligence import LocalIntelligence
from star.knowledge import KnowledgeStore
from star.specialist_agents import ResearchTeam, DELEGATE_TOOL
from star.tool_workshop import ToolWorkshop, _validate_recipe
from star.workspace import Workspace


def _resources(tmp_path: Path, project: str = "VALEN"):
    root = tmp_path / "project"
    root.mkdir(exist_ok=True)
    (root / "inventory.luau").write_text("local InventoryController = {}\nreturn InventoryController")
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    (vault / "VALEN.md").write_text("VALEN map evergreen forest procedural seeds")
    data = tmp_path / "profile"
    knowledge = KnowledgeStore(data / "knowledge")
    note_id = knowledge.add_note(project=project, kind="decision",
                                  text="Evergreen forests use procedural seeds",
                                  source="review:design", revision="v1")
    knowledge.review_note(project=project, note_id=note_id, evidence="approved by project owner")
    workshop = ToolWorkshop(home=data, project=project, knowledge=knowledge,
                            workspace=Workspace(root),
                            intelligence=LocalIntelligence(
                                home=data, workspace=root, obsidian_vault=vault))
    return workshop, knowledge, data


def test_tool_workshop_project_scoped_proposal_requires_preview_and_human_approval(tmp_path):
    tool, notes, home = _resources(tmp_path)
    try:
        result = tool.propose(
            "valen-research", "Search approved VALEN project information",
            [{"source": "knowledge", "limit": 3}, {"source": "obsidian", "limit": 3}])
        ident = result["id"]
        assert result["status"] == "pending"
        assert tool.status()["pending"] == 1
        with pytest.raises(PermissionError):
            tool.approve(ident)
        with pytest.raises(PermissionError):
            tool.run(ident, "evergreen forest")
        preview = tool.run(ident, "evergreen forest", preview=True)
        assert preview["ok"] and preview["preview"]
        assert "evergreen" in str(preview).lower()
        assert all(x["ok"] for x in preview["results"])
        approved = tool.approve(ident)
        assert approved["status"] == "approved"
        assert tool.status()["approved"] == 1
        output = tool.run(ident, "evergreen forest")
        assert output["ok"] and not output["preview"] and output["read_only"]
        with pytest.raises(PermissionError):
            tool.run(ident, "new test", preview=True)
        tool.disable(ident)
        with pytest.raises(PermissionError):
            tool.run(ident, "evergreen forest")
    finally:
        tool.close()
        notes.close()


def test_self_creation_cannot_grant_shell_write_mcp_or_repeated_sources(tmp_path):
    for invalid in [
        [{"source": "shell", "limit": 1}],
        [{"source": "mcp", "limit": 1}],
        [{"source": "workspace", "limit": 1}, {"source": "workspace", "limit": 3}],
        [{"source": "workspace", "limit": 999}],
    ]:
        with pytest.raises((ValueError, ValidationError)):
            _validate_recipe("unsafe-tool", "Should never perform unchecked writes", invalid)
    for bad_name in ["../secret", "evil_tool", "Create Python", "a--b", ".env"]:
        with pytest.raises((ValueError, ValidationError)):
            _validate_recipe(bad_name, "A restricted read-only composition", [{"source": "skills"}])
    tool, notes, _ = _resources(tmp_path)
    try:
        with pytest.raises((ValidationError, ValueError)):
            tool.call("star_toolforge_propose", {
                "name": "unsafe-tool", "description": "Run dynamic shell commands",
                "steps": [{"source": "shell"}]
            }, enabled={"star_toolforge_propose"})
        with pytest.raises(PermissionError):
            tool.call("star_toolforge_list", {}, enabled=set())
        assert tool.definitions("Hi, how are you?") == []
        assert {x["name"] for x in tool.definitions("Please create your own research tools")} >= {
            "star_toolforge_list", "star_toolforge_propose"}
    finally:
        tool.close()
        notes.close()


def test_custom_tool_isolation_persistence_and_no_cross_project_promotion(tmp_path):
    tool, notes, home = _resources(tmp_path)
    candidate = tool.propose("valen-overview", "Find the current VALEN design requirements",
                             [{"source": "knowledge"}])
    ident = candidate["id"]
    tool.run(ident, "evergreen", preview=True)
    tool.close()
    # Switching projects retains stored rows but never makes the other
    # project's candidate or approved tool accessible.
    other = ToolWorkshop(home=home, project="BOOBOUND", knowledge=notes)
    try:
        assert other.catalog()["tools"] == []
        with pytest.raises(ValueError):
            other.approve(ident)
        with pytest.raises(ValueError):
            other.run(ident, "evergreen", preview=True)
    finally:
        other.close()
    reopened = ToolWorkshop(home=home, project="VALEN", knowledge=notes)
    try:
        assert reopened.catalog()["tools"][0]["tests"] == 1
        assert reopened.approve(ident)["status"] == "approved"
    finally:
        reopened.close()
        notes.close()


def test_failure_preview_does_not_unlock_approval(tmp_path):
    data = tmp_path / "data"
    tool = ToolWorkshop(home=data, project="STAR")
    try:
        row = tool.propose("missing-vault", "Search the not yet enabled vault",
                           [{"source": "obsidian"}])
        out = tool.run(row["id"], "test query", preview=True)
        assert not out["ok"] and out["results"][0]["error"] == "RuntimeError"
        with pytest.raises(PermissionError):
            tool.approve(row["id"])
    finally:
        tool.close()


def test_model_tools_cannot_approve_their_own_candidates(tmp_path):
    tool = ToolWorkshop(home=tmp_path, project="STAR")
    try:
        assert not tool.owns("approve_tool")
        assert not any("approve" in x["name"] for x in tool.definitions("Create tools"))
        with pytest.raises(PermissionError):
            tool.call("star_toolforge_approve", {"id": 1},
                      enabled={"star_toolforge_approve"})
    finally:
        tool.close()


def test_fts5_ranked_search_finds_reviewed_source_and_excludes_candidates(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge")
    try:
        good = store.add_note(project="VALEN", kind="decision",
                              text="evergreen evergreen procedural forest",
                              source="design-review", revision="v2")
        store.review_note(project="VALEN", note_id=good, evidence="human acceptance")
        store.add_note(project="VALEN", kind="unknown", text="evergreen toxic leaked prompt",
                       source="model-guess")
        other = store.add_note(project="BOOBOUND", kind="decision", text="evergreen unrelated project",
                               source="wrong-project")
        store.review_note(project="BOOBOUND", note_id=other, evidence="human acceptance")
        results = store.find_ranked("VALEN", "evergreen forest")
        assert results and all(x.project == "VALEN" and x.reviewed for x in results)
        assert any(x.id == good and x.source == "design-review" for x in results)
        assert all("toxic" not in x.text for x in results)
        assert store.find_ranked("VALEN", "nothingsimilarhere") == []
        assert store.find_ranked("BOOBOUND", "evergreen")[0].id == other
    finally:
        store.close()


def test_fts5_migration_existing_notes_are_indexed(tmp_path):
    root = tmp_path / "legacy"
    root.mkdir()
    conn = sqlite3.connect(root / "knowledge.sqlite3")
    conn.execute("""CREATE TABLE notes (
         id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL,
         kind TEXT NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL,
         revision TEXT NOT NULL, reviewed INTEGER NOT NULL, created TEXT NOT NULL)""")
    conn.execute("""INSERT INTO notes(project,kind,text,source,revision,reviewed,created)
                    VALUES ('STAR','decision','compaction futurecache restored',
                    'legacy','v1',1,'2026-01-01')""")
    conn.commit()
    conn.close()
    store = KnowledgeStore(root)
    try:
        assert any("futurecache" in n.text for n in store.find_ranked("STAR", "futurecache"))
    finally:
        store.close()


class Answers:
    def __init__(self, content="Specialist analysis based on provided excerpts"):
        self.content = content
        self.requests = []
        self.active = 0
        self.peak = 0

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.01)
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=self.content, tool_calls=None))])
        finally:
            self.active -= 1


def fake_client(model):
    return SimpleNamespace(chat=SimpleNamespace(completions=model))


def test_readonly_agents_run_real_model_calls_and_dependencies():
    async def run():
        model = Answers()
        team = ResearchTeam(client=fake_client(model), model="local-qwen",
                            project="VALEN", parallelism=2)
        result = await team.run([
            {"id": "architecture", "role": "research", "goal": "Analyze system architecture requirements"},
            {"id": "interface", "role": "ui", "goal": "Evaluate interface quality and consistency"},
            {"id": "review", "role": "review", "goal": "Evaluate combined limitations and risks",
             "dependencies": ["architecture", "interface"]},
        ])
        assert len(model.requests) == 3
        assert model.peak == 2
        assert result["model_calls"] == 3
        assert [x["status"] for x in result["reports"]] == ["completed"] * 3
        assert "dependent_analyses" in model.requests[-1]["messages"][1]["content"]
        assert all("tools" not in q for q in model.requests)
        assert all(q["messages"][0]["role"] == "system" for q in model.requests)
    asyncio.run(run())


def test_serial_default_preserves_small_gpu_capacity_and_permissions():
    async def run():
        model = Answers()
        team = ResearchTeam(client=fake_client(model), model="local",
                            project="STAR")
        out = await team.run([
            {"id": "one", "role": "research", "goal": "Inspect existing retrieval capabilities"},
            {"id": "two", "role": "integration", "goal": "Describe safe tool registration constraints"},
        ])
        assert out["parallelism"] == 1
        assert model.peak == 1
        assert len(out["reports"]) == 2
        with pytest.raises(ValidationError):
            await team.run([{"id": "bad", "role": "research",
                             "goal": "Try to delete a file",
                             "writes": ["workspace/data"]}])
    asyncio.run(run())


def test_delegation_rejects_cycles_unknown_dependencies_and_unbounded_calls():
    async def run():
        team = ResearchTeam(client=fake_client(Answers()), model="local", project="STAR")
        with pytest.raises(ValueError):
            await team.run([
                {"id": "a", "role": "research", "goal": "Check graph topology validity",
                 "dependencies": ["b"]},
                {"id": "b", "role": "review", "goal": "Verify full task graph safety",
                 "dependencies": ["a"]}])
        with pytest.raises(ValueError):
            await team.run([{"id": "a", "role": "research",
                             "goal": "Check dependencies and scopes",
                             "dependencies": ["not-here"]}])
        assert team.definitions("just say hello") == []
        assert team.definitions("use two subagents")[0]["name"] == DELEGATE_TOOL["name"]
    asyncio.run(run())


def test_live_agent_routes_to_specialist_without_granting_worker_tools():
    class ToolThenText:
        def __init__(self):
            self.count = 0
            self.requests = []
        async def create(self, **kwargs):
            self.requests.append(kwargs)
            self.count += 1
            if self.count == 1:
                call = SimpleNamespace(id="first",
                    function=SimpleNamespace(name="star_delegate_research",
                    arguments=json.dumps({"tasks": [{
                        "id": "check", "role": "research",
                        "goal": "Research source quality for a Roblox UI design"}]})))
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content="", tool_calls=[call]))])
            if self.count == 2:
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content="Candidate research result", tool_calls=None))])
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="I used a read-only research specialist", tool_calls=None))])
    async def run():
        model = ToolThenText()
        client = fake_client(model)
        team = ResearchTeam(client=client, model="local", project="STAR")
        answer, messages, _ = await execute(
            client=client, model="local", prompt="Delegate to subagents for Roblox UI research",
            image_paths=[], specialists=team)
        assert "research specialist" in answer
        assert any(m["role"] == "tool" and "Candidate research" in m["content"] for m in messages)
        assert len(model.requests) == 3
        assert "tools" not in model.requests[1]
    asyncio.run(run())


def test_desktop_settings_retain_safe_agent_and_tool_limits(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings()
    assert settings.tool_workshop_enabled
    assert settings.specialists_enabled
    assert settings.specialist_parallelism == 1
    settings.save(path)
    saved = Settings.load(path)
    assert saved.specialist_parallelism == 1
    saved.specialist_parallelism = 50
    with pytest.raises(ValueError):
        saved.validate()
