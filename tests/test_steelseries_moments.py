import json
from pathlib import Path
import pytest

from star.steelseries_moments import MomentsEvents, _local_endpoint


def make_engine(tmp_path, address="127.0.0.1:51248"):
    f = tmp_path / "coreProps.json"
    f.write_text(json.dumps({"address": address}), encoding="utf-8")
    calls = []
    engine = MomentsEvents(f, lambda endpoint, route, body: calls.append((endpoint, route, body)))
    return engine, f, calls


def test_only_loopback_discovery(tmp_path):
    for addr in ("evil.invalid:51248", "192.168.1.1:51248", "localhost:51248",
                 "127.0.0.1:80", "127.0.0.1:99999", "127.0.0.1:1/redirect"):
        engine, f, _ = make_engine(tmp_path, addr)
        assert _local_endpoint(f) is None
        assert engine.handle("clipMomentsStatus", {})["available"] is False
    _, f, _ = make_engine(tmp_path)
    assert _local_endpoint(f) == "http://127.0.0.1:51248"


def test_owner_consent_and_game_namespace_required(tmp_path):
    engine, _, calls = make_engine(tmp_path)
    for body in ({}, {"confirm": True, "game": "STAR_GAME"},
                 {"confirm": True, "ownsGame": True, "game": "STAR_GAME"}):
        with pytest.raises(PermissionError):
            engine.handle("clipMomentsRegister", body)
    with pytest.raises(ValueError):
        engine.handle("clipMomentsRegister", {"confirm": True, "ownsGame": True, "game": "FORTNITE"})
    assert not calls


def test_register_then_trigger_fixed_endpoints(tmp_path):
    engine, _, calls = make_engine(tmp_path)
    body = {"confirm": True, "ownsGame": True, "game": "STAR_MY_GAME"}
    with pytest.raises(PermissionError):
        engine.handle("clipMomentsTrigger", body)
    registered = engine.handle("clipMomentsRegister", body)
    assert registered["accepted"]
    assert calls[0][0] == "http://127.0.0.1:51248"
    assert calls[0][1] == "register_autoclip_rules"
    assert calls[0][2]["rules"][0]["rule_key"] == "star_highlight"
    triggered = engine.handle("clipMomentsTrigger", body)
    assert triggered["accepted"]
    assert "Verify" in triggered["message"]
    assert calls[1][1] == "autoclip"
    assert calls[1][2] == {"game": "STAR_MY_GAME", "key": "star_highlight"}


def test_failure_does_not_mark_registration(tmp_path):
    file = tmp_path / "coreProps.json"
    file.write_text('{"address":"127.0.0.1:51248"}')
    engine = MomentsEvents(file, lambda *a: (_ for _ in ()).throw(RuntimeError("secret token 123")))
    with pytest.raises(ConnectionError) as exc:
        engine.handle("clipMomentsRegister", {
            "confirm": True, "ownsGame": True, "game": "STAR_MY_GAME"
        })
    assert "secret" not in str(exc.value)
    assert not engine.registered


def test_reject_unlisted_operations_and_unavailable_server(tmp_path):
    engine = MomentsEvents(tmp_path / "missing")
    assert engine.handle("clipMomentsStatus", {})["available"] is False
    with pytest.raises(PermissionError):
        engine.handle("clipMomentsUpload", {})
    with pytest.raises(ConnectionError):
        engine.handle("clipMomentsRegister", {
            "confirm": True, "ownsGame": True, "game": "STAR_MY_GAME"
        })
