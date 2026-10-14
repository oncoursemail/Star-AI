"""Concurrent coding specialists are actually run, but never mutate source."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from star.agent import execute
from star.candidate_code_team import definitions, run_candidate_code_team
from star.workspace import Workspace


class Responses:
    def __init__(self):
        self.requests = []
        self.active = 0
        self.peak = 0

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(.035)
        self.active -= 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="Proposed change only: add a validated function. Tests needed.",
            tool_calls=None))])


def setup_workspace(root: Path) -> Workspace:
    root.mkdir(exist_ok=True)
    (root / "game.luau").write_text("local Round = {}\nreturn Round", encoding="utf-8")
    (root / "ui.tsx").write_text("export function View(){return null}", encoding="utf-8")
    (root / ".env").write_text("NOT_A_REAL_SECRET=redacted", encoding="utf-8")
    return Workspace(root)


def test_candidate_team_runs_parallel_four_stages_with_no_tools_or_writes(tmp_path):
    async def scenario():
        workspace = setup_workspace(tmp_path / "game")
        model = Responses()
        client = SimpleNamespace(chat=SimpleNamespace(completions=model))
        events = []
        result = await run_candidate_code_team(
            client=client, model="local", project="Game", workspace=workspace,
            goal="Improve the game round handler and UI accessibility",
            paths=["game.luau", "ui.tsx"], parallel=2, on_event=events.append)
        assert result["status"] == "candidate"
        assert result["peak_concurrency"] == model.peak == 2
        assert len(result["stages"]) == len(model.requests) == 4
        assert all(not request.get("tools") for request in model.requests)
        assert all([line["role"] for line in r["messages"]] == ["system", "user"]
                   for r in model.requests)
        assert "no code was changed" in result["verification"].lower()
        assert "never-mutated" not in result["proposal"]
        assert (tmp_path / "game/game.luau").read_text() == "local Round = {}\nreturn Round"
        assert sum(e["event"] == "agent_finished" for e in events) == 4

    asyncio.run(scenario())


def test_code_team_rejects_private_paths_and_unapproved_extensions(tmp_path):
    async def scenario(path):
        workspace = setup_workspace(tmp_path / "root")
        model = Responses()
        client = SimpleNamespace(chat=SimpleNamespace(completions=model))
        return await run_candidate_code_team(
            client=client, model="local", project="Game", workspace=workspace,
            goal="Review the game for opportunities to improve readability",
            paths=[path])
    for path in ("../outside.py", ".env", "secrets.json", "image.png"):
        with pytest.raises((PermissionError, ValueError, OSError)):
            asyncio.run(scenario(path))
    assert not definitions("just say hello", enabled=True)
    assert not definitions("Use multiple coding agents", enabled=False)
    assert definitions("Use multiple coding agents", enabled=True)
    assert not definitions("Team deathmatch code", enabled=True)
    assert not definitions("Implement multiple checkpoints", enabled=True)


def test_code_team_requires_bounded_parallelism_and_paths(tmp_path):
    async def scenario(paths, parallel):
        return await run_candidate_code_team(
            client=SimpleNamespace(chat=None), model="local", project="Game",
            workspace=setup_workspace(tmp_path / "game"),
            goal="Review the Roblox game code for scalability",
            paths=paths, parallel=parallel)
    with pytest.raises(ValueError):
        asyncio.run(scenario(["game.luau"], 99))
    with pytest.raises(Exception):
        asyncio.run(scenario([], 1))


class RequestsTeam:
    def __init__(self):
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            call = SimpleNamespace(id="code-team",
                function=SimpleNamespace(name="star_candidate_code_team",
                    arguments=json.dumps({
                        "goal": "Improve Roblox code quality with a review",
                        "paths": ["game.luau"]})))
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=[call]))])
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="Read-only candidate; no edits performed.",
                                    tool_calls=None))])


def test_code_team_cannot_be_invoked_without_agent_permission(tmp_path, monkeypatch):
    async def scenario(authorized):
        workspace = setup_workspace(tmp_path / "work")
        invoked = []

        async def fake_team(**kwargs):
            invoked.append(kwargs["goal"])
            return {"status": "candidate", "proposal": "Only a proposal."}

        monkeypatch.setattr("star.candidate_code_team.run_candidate_code_team", fake_team)
        model = RequestsTeam()
        client = SimpleNamespace(chat=SimpleNamespace(completions=model))
        answer, transcript, _ = await execute(
            client=client, model="local",
            prompt="Use parallel coding agents for my Roblox game",
            image_paths=[], workspace=workspace,
            subagents_enabled=authorized,
            candidate_code_team_enabled=True)
        assert "no edits" in answer.lower()
        available = {row["function"]["name"]
                     for row in model.requests[0].get("tools", [])}
        assert ("star_candidate_code_team" in available) == authorized
        if authorized:
            assert invoked == ["Improve Roblox code quality with a review"]
            assert "Only a proposal" in str(transcript)
        else:
            assert not invoked
            assert "Tool request rejected" in str(transcript)
    asyncio.run(scenario(False))
    asyncio.run(scenario(True))


def test_code_team_remains_off_by_default_even_for_matching_agent_requests(tmp_path):
    async def scenario():
        model = RequestsTeam()
        client = SimpleNamespace(chat=SimpleNamespace(completions=model))
        workspace = setup_workspace(tmp_path / "default-off")
        answer, transcript, _ = await execute(
            client=client, model="local",
            prompt="Use parallel coding agents for my Roblox game",
            image_paths=[], workspace=workspace, subagents_enabled=True)
        offered = {row["function"]["name"] for row in model.requests[0].get("tools", [])}
        assert "star_candidate_code_team" not in offered
        assert "Tool request rejected" in str(transcript)
        assert "no edits" in answer.lower()
    asyncio.run(scenario())
