"""Settings page switches that reach the backend: live Roblox docs (opt-in) and automatic web search."""
import pytest

from star.desktop_core import Settings
from star.react_shell import PERMITTED_SETTINGS
from star.roblox_docs_live import live_enabled


def test_live_roblox_docs_is_off_by_default_and_the_setting_turns_it_on(monkeypatch):
    monkeypatch.delenv("STAR_ROBLOX_DOCS_LIVE", raising=False)
    assert Settings().roblox_docs_live_enabled is False
    assert live_enabled(Settings()) is False
    assert live_enabled(Settings(roblox_docs_live_enabled=True)) is True


def test_live_roblox_docs_must_be_a_real_boolean():
    with pytest.raises(ValueError):
        Settings(roblox_docs_live_enabled="yes").validate()


def test_the_interface_may_save_both_switches():
    assert {"roblox_docs_live_enabled", "web_auto_search"} <= PERMITTED_SETTINGS
    assert Settings().web_auto_search is True
