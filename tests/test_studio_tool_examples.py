"""Opt-in example calls appended to Studio tool descriptions (research PR #347, item 7).

Every example must be a call STAR's own policy accepts and the connector's real schema
(tests/studio_fake.py, copied from the live connector) validates. Off by default.
"""
import json
import re

import pytest
from jsonschema import Draft7Validator

from star import policy
from star import studio_tool_examples as examples
from star.desktop_core import Settings
from tests.studio_fake import TOOLS

STUDIO = "studio-1"


def example_args(description: str) -> dict:
    found = re.search(r"Example call in STAR: (\{.*\})", description)
    assert found, description
    return json.loads(found.group(1).replace(examples.EXAMPLE_STUDIO_ID, STUDIO))


def test_examples_are_off_by_default():
    assert Settings().studio_tool_examples is False


def test_every_example_is_valid_for_the_real_schema_and_accepted_by_star_policy():
    tools = examples.with_examples(TOOLS)
    by_name = {tool["name"]: tool for tool in tools}
    assert set(examples.TOOL_EXAMPLES) <= set(by_name)
    registry = policy.allowed_registry(tools, may_edit=True, allow_luau=True)
    for name in examples.TOOL_EXAMPLES:
        args = example_args(by_name[name]["description"])
        Draft7Validator(by_name[name]["inputSchema"]).validate(args)
        policy.enforce(name, args, registry, STUDIO, may_edit=True, allow_luau=True)


def test_read_only_examples_are_accepted_without_edit_permission():
    tools = examples.with_examples(TOOLS)
    registry = policy.allowed_registry(tools, may_edit=False)
    for name in sorted(policy.READ_TOOLS & set(examples.TOOL_EXAMPLES)):
        policy.enforce(name, example_args(registry[name]["description"]), registry, STUDIO, may_edit=False)


def test_examples_are_byte_stable_and_do_not_change_the_input():
    original = json.dumps(TOOLS, sort_keys=True)
    first, second = examples.with_examples(TOOLS), examples.with_examples(TOOLS)
    assert first == second
    assert json.dumps(TOOLS, sort_keys=True) == original
    untouched = {t["name"] for t in TOOLS} - set(examples.TOOL_EXAMPLES)
    for before, after in zip(TOOLS, first):
        if before["name"] in untouched:
            assert after == before


def test_an_example_naming_an_argument_the_connector_no_longer_has_is_left_out():
    renamed = [dict(t, inputSchema={**t["inputSchema"], "properties": {
        ("target_path" if k == "target_file" else k): v for k, v in t["inputSchema"]["properties"].items()}})
        if t["name"] == "script_read" else t for t in TOOLS]
    tool = next(t for t in examples.with_examples(renamed) if t["name"] == "script_read")
    assert "Example call in STAR" not in tool["description"]


@pytest.mark.parametrize("value", [None, "yes", 1])
def test_the_setting_must_be_a_boolean(value):
    with pytest.raises(ValueError):
        Settings(model="qwen-test", studio_tool_examples=value).validate()


def test_the_setting_can_be_saved_from_the_desktop():
    from star.react_shell import PERMITTED_SETTINGS
    assert "studio_tool_examples" in PERMITTED_SETTINGS


@pytest.mark.parametrize("enabled", [False, True])
def test_run_task_offers_the_examples_only_when_the_setting_is_on(tmp_path, monkeypatch, enabled):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    import star.desktop_core as core
    import star.doc_grounding as doc_grounding
    from star import local_mcp
    from star.desktop_core import Conversations, run_task

    home = tmp_path / "profile"
    home.mkdir()
    monkeypatch.setattr(core, "app_data", lambda: home)

    async def no_documentation(*_args, **_kwargs):
        return doc_grounding.Grounding()

    monkeypatch.setattr(doc_grounding, "prepare_async", no_documentation)
    tools = [t for t in TOOLS if t["name"] in ("script_read", "get_studio_state")]
    proxy = SimpleNamespace(discovered=tools, verdict=SimpleNamespace(editable=False, reason="read only."),
                            journal=SimpleNamespace(text=lambda: "STAR changed nothing in Studio."))

    @asynccontextmanager
    async def connect(settings, where, studio_configuration_home=None):
        yield proxy

    seen = []

    async def execute(**kwargs):
        seen.append(kwargs)
        return "Read it.", [], []

    monkeypatch.setattr(core, "execute", execute)
    monkeypatch.setattr(local_mcp, "connect_studio", connect)
    settings = Settings(model="offline-test", studio_id="selected", skills_enabled=False, graphify_enabled=False,
                        roblox_research_enabled=False, tool_workshop_enabled=False, specialists_enabled=False,
                        studio_tool_examples=enabled)
    chats = Conversations(home / "conversations.sqlite3")
    try:
        chat = chats.new_chat(settings.project)
        chats.add(settings.project, "user", "Read the open Roblox Studio place", chat_id=chat)
        run_task(settings, "Read the open Roblox Studio place", chat_id=chat, mode="agent",
                 studio_configuration_home=tmp_path / "settings")
    finally:
        chats.close()
    offered = {t["name"]: t["description"] for t in seen[-1]["discovered"]}
    assert ("Example call in STAR" in offered["script_read"]) is enabled
    assert "Example call in STAR" not in offered["get_studio_state"]
    assert proxy.discovered is tools and "Example call in STAR" not in tools[0]["description"]
