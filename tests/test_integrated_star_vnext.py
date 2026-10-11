"""Cross-branch contracts: new chat, models, MCP, Teams and reviewed memory coexist.

These offline regressions validate integration points; they do not fake GPU
inference, hosted credentials, web search, a Windows installer or Studio tests.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from star.desktop_core import Conversations, Settings, needs_project_tools, run_task
from star.react_shell import ALLOWED_ACTIONS
from star.knowledge import KnowledgeStore
from star.learning import approve_learning, learned_context


ROOT = Path(__file__).resolve().parents[1]


def test_all_native_actions_share_one_allowlisted_react_shell():
    for action in (
        "sendMessage","newChat","switchChat","generateImage","cancelMessage",
        "saveProviderKey","clearProviderKey","testMcpConnection","runTeam",
        "rememberDecision","listLearning","discoverStudio","installUpdate",
    ):
        assert action in ALLOWED_ACTIONS
    assert "runShell" not in ALLOWED_ACTIONS
    assert "deleteAllChats" not in ALLOWED_ACTIONS
    assert "publishRobloxGame" not in ALLOWED_ACTIONS


def test_hosted_fast_agent_mcp_and_threads_are_one_settings_model(tmp_path):
    settings = Settings(
        endpoint="http://127.0.0.1:8080/v1", provider="local",
        project="My Roblox Game",model="local-test",
        mcp_graphify_docs=True,mcp_graphify_local=False,
        mcp_obsidian_live=False,mcp_graphify_port=8931,
        comfy_prompt_node="6",comfy_port=8188,
    )
    settings.save(tmp_path/"settings.json")
    restored=Settings.load(tmp_path/"settings.json")
    assert restored.project=="My Roblox Game"
    assert restored.provider=="local"
    assert restored.mcp_graphify_docs
    assert not restored.mcp_obsidian_live
    assert "chat_id" in inspect.signature(run_task).parameters
    for argument in ("mode","research","cancel_event","github_enabled"):
        assert argument in inspect.signature(run_task).parameters
    with pytest.raises(ValueError):
        Settings(endpoint="http://127.0.0.1:8080/v1",provider="not-approved").validate()
    with pytest.raises(ValueError):
        Settings(endpoint="http://127.0.0.1:8080/v1",mcp_graphify_port=1).validate()


def test_new_thread_context_isolated_but_reviewed_decision_shared(tmp_path):
    store=Conversations(tmp_path/"conversations.sqlite3")
    try:
        first=store.new_chat("My Roblox Game")
        store.add("My Roblox Game","user","This thread uses a red car",chat_id=first)
        other=store.new_chat("My Roblox Game")
        store.add("My Roblox Game","user","This thread uses a blue car",chat_id=other)
        assert "red" in store.recent("My Roblox Game",chat_id=first)[0][1]
        assert "blue" in store.recent("My Roblox Game",chat_id=other)[0][1]
        assert "blue" not in str(store.recent("My Roblox Game",chat_id=first))
        assert first!=other
        assert store.active_chat("My Roblox Game")==other
    finally:store.close()

    approve_learning(tmp_path,project="My Roblox Game",
                     text="Use warm antique gold for selected navigation",
                     human_approved=True)
    assert "antique gold" in learned_context(tmp_path,"My Roblox Game","selected navigation")
    assert not learned_context(tmp_path,"Other Roblox Game","selected navigation")


def test_auto_fast_path_does_not_hide_explicit_mcp_research():
    assert not needs_project_tools("Explain gravity in simple words")
    assert needs_project_tools("Use MCP to search Graphify documentation")
    assert needs_project_tools("Inspect my Roblox Studio sandbox and report scripts")


def test_integrated_react_wires_modes_to_native_actions():
    frontend=(ROOT/"frontend/src/Desktop.tsx").read_text(encoding="utf-8")
    native=(ROOT/"star/react_shell.py").read_text(encoding="utf-8")
    agent=(ROOT/"star/agent.py").read_text(encoding="utf-8")
    for token in (
        "chatMode","teamMode","research","githubSource","runTeam",
        "newChat","switchChat","LearningPanel","McpPanel","ProviderPanel",
        "generateImage",
    ):
        assert token in frontend
    for token in ("chat_id=active_chat","mcp", "runTeam","rememberDecision","saveProviderKey"):
        assert token in native
    assert "mcp_gateway" in agent
    assert "subagents_enabled" in agent
