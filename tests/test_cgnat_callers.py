"""The CGNAT opt-in reaches every caller that checks the saved server address, and only when set."""
from types import SimpleNamespace

import pytest

from star.desktop_core import Settings
from star.doc_knowledge import knowledge_endpoint_for
from star.model_health import probe_server
from star.voice.brain import server_connection

CGNAT = "http://100.64.0.1:8080/v1"  # star:allow
LAN = "http://192.168.1.20:8080/v1"  # star:allow


def _settings(endpoint, **extra):
    return SimpleNamespace(provider="star_server", server_endpoint=endpoint, knowledge_endpoint="",
                           model="star-chat", **extra)


def test_default_is_off():
    assert Settings().allow_cgnat is False


@pytest.mark.parametrize("flag", [{}, {"allow_cgnat": False}, {"allow_cgnat": "true"}, {"allow_cgnat": 1}])
def test_server_check_refuses_cgnat_unless_flag_is_exactly_true(monkeypatch, flag):
    monkeypatch.setattr("star.model_health.get_api_key", lambda name: "")
    report = probe_server(_settings(CGNAT, **flag), chat=False)
    assert report["code"] == "bad_address"                     # refused at the address check


def test_server_check_accepts_cgnat_only_with_flag(monkeypatch):
    monkeypatch.setattr("star.model_health.get_api_key", lambda name: "")     # stop right after the address check
    assert probe_server(_settings(CGNAT, allow_cgnat=True), chat=False)["code"] == "no_key"
    assert probe_server(_settings(CGNAT, allow_cgnat=False), chat=False)["code"] == "bad_address"


@pytest.mark.parametrize("flag", [{}, {"allow_cgnat": False}, {"allow_cgnat": True}])
def test_server_check_plain_lan_unchanged(monkeypatch, flag):
    monkeypatch.setattr("star.model_health.get_api_key", lambda name: "")
    assert probe_server(_settings(LAN, **flag), chat=False)["code"] == "no_key"


@pytest.mark.parametrize("endpoint", ["http://100.100.100.200:8080/v1", "http://8.8.8.8:8080/v1",
                                       "http://[::ffff:100.64.0.1]:8080/v1"])  # star:allow
def test_server_check_flag_does_not_open_other_addresses(monkeypatch, endpoint):
    monkeypatch.setattr("star.model_health.get_api_key", lambda name: "")
    assert probe_server(_settings(endpoint, allow_cgnat=True), chat=False)["code"] == "bad_address"


def test_voice_brain_connection_follows_flag(monkeypatch):
    monkeypatch.delenv("STAR_SERVER_URL", raising=False)
    monkeypatch.setenv("STAR_VOICE_MODEL", "voice-model")
    monkeypatch.setattr("star.providers.get_api_key", lambda name: "test-only-key")
    assert server_connection(_settings(CGNAT), discover=False)[0] == ""
    assert server_connection(_settings(CGNAT, allow_cgnat=False), discover=False)[0] == ""
    assert server_connection(_settings(CGNAT, allow_cgnat=True), discover=False)[0] == CGNAT
    for flag in (False, True):                                  # the plain LAN check is the same either way
        assert server_connection(_settings(LAN, allow_cgnat=flag), discover=False)[0] == LAN


def test_knowledge_address_derived_from_server_follows_flag():
    assert knowledge_endpoint_for(_settings(CGNAT)) == ""
    assert knowledge_endpoint_for(_settings(CGNAT, allow_cgnat=False)) == ""
    assert knowledge_endpoint_for(_settings(CGNAT, allow_cgnat=True)) == "http://100.64.0.1:8091"  # star:allow
    assert knowledge_endpoint_for(_settings(LAN)) == "http://192.168.1.20:8091"  # star:allow
    assert knowledge_endpoint_for(_settings(LAN, allow_cgnat=True)) == "http://192.168.1.20:8091"  # star:allow


def test_explicit_knowledge_endpoint_stays_strict():
    explicit = SimpleNamespace(server_endpoint=CGNAT, knowledge_endpoint="http://100.64.0.1:8091",  # star:allow
                               allow_cgnat=True)
    assert knowledge_endpoint_for(explicit) == ""
