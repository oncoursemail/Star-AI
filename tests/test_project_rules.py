"""Opt-in project rules file from the workspace (research PR #347, item 5)."""
import pytest

from star import project_rules
from star.desktop_core import Settings

from tests.test_learning_loop import desk, text_of  # noqa: F401  (shared fixture)


def test_agents_md_wins_over_the_older_names(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("claude rules", encoding="utf-8")
    (tmp_path / ".cursorrules").write_text("cursor rules", encoding="utf-8")
    assert project_rules.load(tmp_path) == ("CLAUDE.md", "claude rules")
    (tmp_path / "AGENTS.md").write_text("Server scripts live in src/server.\n", encoding="utf-8")
    assert project_rules.load(tmp_path) == ("AGENTS.md", "Server scripts live in src/server.")


def test_no_file_an_empty_file_or_no_workspace_gives_nothing(tmp_path):
    assert project_rules.load(tmp_path) is None
    (tmp_path / "AGENTS.md").write_text("   \n", encoding="utf-8")
    assert project_rules.load(tmp_path) is None
    assert project_rules.load(tmp_path / "missing") is None


def test_unreadable_files_are_skipped_not_raised(tmp_path):
    (tmp_path / "AGENTS.md").write_bytes(b"\xff\xfe\x00bad")
    (tmp_path / "CLAUDE.md").write_text("x" * (70 * 1024), encoding="utf-8")
    (tmp_path / ".cursorrules").write_text("Use Promise.", encoding="utf-8")
    assert project_rules.load(tmp_path) == (".cursorrules", "Use Promise.")


def test_long_rules_are_cut_and_say_so(tmp_path):
    (tmp_path / "AGENTS.md").write_text("rule line\n" * 500, encoding="utf-8")
    name, text = project_rules.load(tmp_path, max_chars=100)
    assert name == "AGENTS.md" and len(text) < 160 and text.endswith("[... rest of AGENTS.md not shown]")


def test_keys_in_the_rules_file_are_redacted(tmp_path):
    secret = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
    (tmp_path / "AGENTS.md").write_text(f"Deploy with OPENAI_API_KEY={secret}\n", encoding="utf-8")
    _, text = project_rules.load(tmp_path)
    assert secret not in text


def test_the_setting_is_off_by_default_and_must_be_a_boolean():
    assert Settings().project_rules_enabled is False
    with pytest.raises(ValueError):
        Settings(model="qwen-test", project_rules_enabled="yes").validate()
    from star.react_shell import PERMITTED_SETTINGS
    assert "project_rules_enabled" in PERMITTED_SETTINGS


@pytest.mark.parametrize("enabled", [False, True])
def test_a_turn_carries_the_rules_only_when_the_owner_turned_them_on(desk, tmp_path, enabled):  # noqa: F811
    workspace = tmp_path / "game"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text("Server scripts live in src/server; use the Promise library.",
                                         encoding="utf-8")
    settings = Settings(model="qwen-test", project="STAR", workspace=str(workspace),
                        project_rules_enabled=enabled)
    turn = desk.turn("Write a coin pickup script for my Roblox game.", "Here it is.", settings=settings, mode="auto")
    sent = text_of(turn.request["messages"][-1])
    assert (project_rules.HEADING in sent) is enabled
    assert ("use the Promise library" in sent) is enabled


def test_quick_chat_stays_small(desk, tmp_path):  # noqa: F811
    workspace = tmp_path / "game"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text("Use the Promise library.", encoding="utf-8")
    settings = Settings(model="qwen-test", project="STAR", workspace=str(workspace), project_rules_enabled=True)
    turn = desk.turn("hi", "Hello.", settings=settings, mode="fast")
    assert project_rules.HEADING not in text_of(turn.request["messages"][-1])
