"""The tool catalogue STAR offers the model in Agent mode, through the app's own `run_task`.

Why this file exists: the real-window acceptance run asks the model, in Agent mode, to call
`star_skill_catalog`. When that step fails, the first question is whether STAR offered the tool at
all. These tests answer it offline: they run `desktop_core.run_task` (the function the window
calls) against a scripted fake model and read the `tools` field of the request it built.

The expected names are written out, one list per source, so a tool that stops being offered (or a
new one that appears) fails a test here and has to be changed on purpose. The lists were produced by
running these same scenarios against the settings-ui branch at a7a36a3 (integration round 4 plus
Settings); every name offered there is still offered, and round 5 added the three workspace_game tools.
Roblox Studio tools are not built in: they come from the connected Studio server's own catalogue and
pass star/policy.py (covered in tests/test_policy.py and tests/test_policy_schema_security.py).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import star.desktop_core as core
from star import providers, server_roles, turn_memory
from star.desktop_core import Conversations, Settings, run_task

LAN = "http://192.168.1.20:8080/v1"          # documentation placeholder, not a real machine (star:allow)
KEY = "test-server-key-0123456789"           # synthetic (star:allow)
# The prompt of the acceptance step (scripts/shell_acceptance.py, PROMPT_AGENT).
ACCEPTANCE_PROMPT = ("Call the star_skill_catalog tool once, then tell me in one short sentence "
                     "how many Agent Skills it returned.")

# Attached to every Agent-mode request (star/agent.py).
ALWAYS = ["star_delegate"]
# Agent Skills (star/intelligence.py SKILL_TOOLS): on by default (Settings.skills_enabled).
SKILLS = ["star_skill_catalog", "star_skill_load", "star_skill_reference"]
# The owner's Obsidian vault, read-only (OBSIDIAN_TOOLS): Settings.obsidian_enabled and a vault folder.
OBSIDIAN = ["star_obsidian_search", "star_obsidian_read", "star_obsidian_list"]
# The workspace's Graphify graph (GRAPHIFY_TOOLS): a workspace with graphify-out/graph.json.
GRAPHIFY = ["star_graphify_query", "star_graphify_explain", "star_graphify_path", "star_graphify_stats"]
# Public Roblox research (ROBLOX_GAME_TOOLS, ROBLOX_KNOWLEDGE_TOOLS, ROBLOX_VIDEO_TOOLS).
ROBLOX_GAMES = ["star_roblox_resolve_game_url", "star_roblox_resolve_place", "star_roblox_search_games",
                "star_roblox_game_report", "star_roblox_compare_games", "star_roblox_game_image"]
ROBLOX_LINKS = ["star_roblox_docs", "star_roblox_docs_read"]      # only without STAR Knowledge
ROBLOX_FORUM = ["star_roblox_forum_search", "star_roblox_forum_topic", "star_roblox_forum_latest"]
ROBLOX_VIDEO = ["star_roblox_youtube_search", "star_roblox_youtube_video"]
# STAR Knowledge (DOC_KNOWLEDGE_TOOLS): the indexed documentation, when the service is configured.
STAR_KNOWLEDGE = ["star_docs_search", "star_api_lookup", "star_luau_check"]
# Roblox Open Cloud with the owner's key (ROBLOX_CLOUD_TOOLS).
ROBLOX_CLOUD = ["star_roblox_cloud_universe", "star_roblox_cloud_status", "star_roblox_cloud_place",
                "star_roblox_cloud_data_stores", "star_roblox_cloud_action", "star_roblox_cloud_request_publish",
                "star_roblox_cloud_request_test"]
# The workspace folder (star/workspace.py TOOLS); workspace_write only with Settings.workspace_edit.
WORKSPACE_READ = ["workspace_list", "workspace_read", "workspace_search"]
WORKSPACE_WRITE = ["workspace_write"]
# Added in integration round 5 (pull request 69, game projects of several engines); not in a7a36a3.
WORKSPACE_GAME = ["workspace_game_discover", "workspace_game_inspect", "workspace_game_plan"]
# Read-only MCP connections (star/mcp_connections.py TOOLS): when one is switched on in Settings.
MCP = ["star_mcp_search", "star_mcp_call"]
# Tool Workshop (star/tool_workshop.py TOOL_SCHEMAS).
WORKSHOP = ["star_toolforge_list", "star_toolforge_propose", "star_toolforge_test", "star_toolforge_run"]
# The research team (star/specialist_agents.py DELEGATE_TOOL).
SPECIALISTS = ["star_delegate_research"]
# Composer switches: research (web search) and the STAR source reader.
WEB = ["star_web_search"]
GITHUB = ["star_github_tree", "star_github_read"]


def reply(content=None, calls=None):
    return SimpleNamespace(model="star-fast", choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls))])


def tool_call(name, arguments="{}"):
    return SimpleNamespace(id="call_1", function=SimpleNamespace(name=name, arguments=arguments))


class Models:
    def __init__(self):
        self.responses, self.requests = [], []

    async def create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        return self.responses.pop(0) if self.responses else reply("done")


class Client:
    def __init__(self, models):
        self.chat = SimpleNamespace(completions=models)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def forget_process_memory():
    """What earlier tests in this process learned about a server (models, limits, slots, sticky tools)."""
    server_roles.forget()
    turn_memory.forget()
    providers._SERVER_LIMITS.clear()
    providers._MODEL_NAMES.clear()
    providers._SLOT_TABLE.clear()


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A private app-data folder and a fake model behind run_task, as the window would call it."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "appdata"))
    monkeypatch.setenv("STAR_SERVER_API_KEY", KEY)
    monkeypatch.delenv("STAR_ROBLOX_READ_API_KEY", raising=False)
    forget_process_memory()
    models = Models()
    monkeypatch.setattr(core, "open_client", lambda settings, **_: Client(models))
    home = core.app_data()
    home.mkdir(parents=True, exist_ok=True)
    events = []

    def turn(prompt, *, settings=None, answers=(), **options):
        settings = settings or Settings(provider="star_server", server_endpoint=LAN, model="star-fast",
                                        knowledge_endpoint="off")
        chats = Conversations(home / "conversations.sqlite3")
        try:
            chat = chats.new_chat(settings.project)
            chats.add(settings.project, "user", prompt, chat_id=chat)
        finally:
            chats.close()
        models.responses.extend(answers)
        first = len(models.requests)
        answer = run_task(settings, prompt, chat_id=chat, on_event=events.append, mode="agent", **options)
        return SimpleNamespace(answer=answer, requests=models.requests[first:])

    yield SimpleNamespace(turn=turn, events=events, home=home, tmp=tmp_path)
    forget_process_memory()


def offered(request) -> list[str]:
    return [tool["function"]["name"] for tool in request.get("tools") or []]


def test_the_acceptance_prompt_is_offered_the_agent_skills_catalogue(desk):
    """Default settings, a new chat, Agent mode: exactly the delegate tool and the three skill tools."""
    result = desk.turn(ACCEPTANCE_PROMPT)
    assert offered(result.requests[0]) == ALWAYS + SKILLS
    assert result.requests[0]["tool_choice"] == "auto"
    chosen = [event for event in desk.events if event.get("event") == "route_selected"]
    assert [event["profile"] for event in chosen] == ["agent"]


def test_a_scripted_model_calls_the_skill_catalogue_and_gets_the_real_list(desk):
    """The whole loop: the model asks for star_skill_catalog, STAR runs it, the result goes back."""
    result = desk.turn(ACCEPTANCE_PROMPT, answers=[
        reply(None, [tool_call("star_skill_catalog")]),
        reply("The star_skill_catalog tool returned the Agent Skills."),
    ])
    assert result.answer == "The star_skill_catalog tool returned the Agent Skills."
    assert len(result.requests) == 2
    assert {"event": "tool_started", "tool": "star_skill_catalog"} in desk.events
    assert {"event": "tool_finished", "tool": "star_skill_catalog", "is_error": False} in desk.events
    # The second request carries the tool's own output: the installed skills, by name.
    sent_back = [message for message in result.requests[1]["messages"] if message["role"] == "tool"]
    assert len(sent_back) == 1
    payload = json.loads(sent_back[0]["content"])
    assert payload["isError"] is False
    skills = json.loads(payload["output"])["skills"]
    names = {skill["name"] for skill in skills}
    assert {"roblox-ui-craft", "roblox-luau-review", "evidence-first-debugging"} <= names
    assert len(skills) >= 12
    # The tools stay attached on the follow-up call, in the same order.
    assert offered(result.requests[1]) == ALWAYS + SKILLS


EVERYTHING_PROMPT = (
    "Research this Roblox game and its players for my notes: search the devforum, watch the YouTube "
    "video tutorial, read the docs, check the Open Cloud data store, look at the graph of the codebase, "
    "list the MCP connector tool catalog, build a custom tool, and delegate to the research team.")


def everything_settings(desk, **fields) -> Settings:
    workspace = desk.tmp / "workspace"
    (workspace / "graphify-out").mkdir(parents=True, exist_ok=True)
    (workspace / "graphify-out" / "graph.json").write_text('{"nodes": [], "links": []}', encoding="utf-8")
    vault = desk.tmp / "vault"
    vault.mkdir(exist_ok=True)
    return Settings(**{"provider": "star_server", "server_endpoint": LAN, "model": "star-fast",
                       "knowledge_endpoint": "off", "workspace": str(workspace), "obsidian_enabled": True,
                       "obsidian_vault": str(vault), "mcp_graphify_docs": True, **fields})


def everything_on(desk, monkeypatch, *, knowledge: bool, **fields):
    """Every built-in source switched on, with nothing leaving the test process."""
    import star.intelligence as intelligence
    import star.roblox_cloud as roblox_cloud
    import star.web_search as web_search

    async def no_search(*_args, **_kwargs):
        return []
    monkeypatch.setattr(web_search, "search_web", no_search)
    monkeypatch.setattr(roblox_cloud.RobloxCloud, "status", lambda self: {"key_present": True})
    if knowledge:   # a configured STAR Knowledge service (only its presence matters for the catalogue)
        monkeypatch.setattr(intelligence, "client_for", lambda settings: SimpleNamespace(configured=True))
    result = desk.turn(EVERYTHING_PROMPT, settings=everything_settings(desk, **fields),
                       research=True, github_enabled=True)
    return offered(result.requests[0])


def test_every_built_in_tool_is_offered_when_its_source_is_on(desk, monkeypatch):
    names = everything_on(desk, monkeypatch, knowledge=False)
    expected = (GITHUB + ALWAYS + WEB + WORKSPACE_READ + WORKSPACE_GAME + SKILLS + OBSIDIAN + GRAPHIFY
                + ROBLOX_GAMES + ROBLOX_LINKS + ROBLOX_FORUM + ROBLOX_VIDEO + ROBLOX_CLOUD + MCP + WORKSHOP
                + SPECIALISTS)
    assert names == expected          # the order is part of the request the server caches
    assert len(names) == len(set(names))


def test_star_knowledge_replaces_the_link_finder_and_write_needs_the_edit_switch(desk, monkeypatch):
    names = everything_on(desk, monkeypatch, knowledge=True, workspace_edit=True)
    expected = (GITHUB + ALWAYS + WEB + WORKSPACE_READ + WORKSPACE_WRITE + WORKSPACE_GAME + SKILLS + OBSIDIAN
                + GRAPHIFY + STAR_KNOWLEDGE + ROBLOX_GAMES + ROBLOX_FORUM + ROBLOX_VIDEO + ROBLOX_CLOUD + MCP
                + WORKSHOP + SPECIALISTS)
    assert names == expected
    assert not set(ROBLOX_LINKS) & set(names)


def test_switching_agent_skills_off_removes_only_the_skill_tools(desk):
    settings = Settings(provider="star_server", server_endpoint=LAN, model="star-fast",
                        knowledge_endpoint="off", skills_enabled=False)
    result = desk.turn(ACCEPTANCE_PROMPT, settings=settings)
    assert offered(result.requests[0]) == ALWAYS


def test_the_written_lists_are_the_whole_built_in_catalogue():
    """A built-in tool added to (or dropped from) a source table must be added to the lists above."""
    from star import intelligence, mcp_connections, specialist_agents, tool_workshop, workspace
    assert set(intelligence.ALL_TOOLS) == set(SKILLS + OBSIDIAN + GRAPHIFY + ROBLOX_GAMES + ROBLOX_LINKS
                                             + ROBLOX_FORUM + ROBLOX_VIDEO + STAR_KNOWLEDGE + ROBLOX_CLOUD)
    assert [tool["name"] for tool in intelligence.SKILL_TOOLS] == SKILLS
    assert {tool["name"] for tool in workspace.TOOLS} == set(WORKSPACE_READ + WORKSPACE_WRITE + WORKSPACE_GAME)
    assert [tool["name"] for tool in mcp_connections.TOOLS] == MCP
    assert [tool["name"] for tool in tool_workshop.TOOL_SCHEMAS] == WORKSHOP
    assert specialist_agents.DELEGATE_TOOL["name"] == SPECIALISTS[0]
