"""Explicit CGNAT permission must not relax LAN SSRF protections."""
from types import SimpleNamespace

import pytest

from star.desktop_core import Settings
from star.providers import connection_for, validate_lan_endpoint
from star.react_shell import apply_setting_changes


@pytest.mark.parametrize("host", ["100.64.0.1", "100.99.1.2", "100.127.255.254"])
def test_cgnat_opt_in_validator(host):
    endpoint = f"http://{host}:8080/v1"
    with pytest.raises(ValueError):
        validate_lan_endpoint(endpoint)
    with pytest.raises(ValueError):
        validate_lan_endpoint(endpoint, allow_cgnat=False)
    assert validate_lan_endpoint(endpoint, allow_cgnat=True) == endpoint


@pytest.mark.parametrize("host", ["100.100.100.200", "169.254.169.254", "8.8.8.8",
                                    "100.63.255.255", "100.128.0.1"])
def test_cgnat_opt_in_does_not_allow_other_ranges_or_metadata(host):
    for allow in (False, True):
        with pytest.raises(ValueError):
            validate_lan_endpoint(f"http://{host}:8080/v1", allow_cgnat=allow)


def test_cgnat_opt_in_preserves_existing_restrictions():
    for endpoint in ("http://100.64.0.1:80/v1",
                     "http://100.64.0.1:8080/v1?token=x",
                     "http://100.64.0.1:8080/other",
                     "http://example.com:8080/v1",
                     "http://[::ffff:100.64.0.1]:8080/v1"):
        with pytest.raises(ValueError):
            validate_lan_endpoint(endpoint, allow_cgnat=True)
    assert validate_lan_endpoint("http://192.168.1.20:8080/v1") == "http://192.168.1.20:8080/v1"


def test_saved_setting_defaults_off_and_is_boolean(tmp_path):
    cfg = Settings()
    assert cfg.allow_cgnat is False
    cfg.provider = "star_server"
    cfg.server_endpoint = "http://100.64.0.1:8080/v1"
    with pytest.raises(ValueError):
        cfg.save(tmp_path / "settings.json")
    cfg.allow_cgnat = True
    cfg.save(tmp_path / "settings.json")
    assert Settings.load(tmp_path / "settings.json").allow_cgnat is True
    cfg.allow_cgnat = "true"
    with pytest.raises(ValueError):
        cfg.validate()


def test_real_lan_connection_path_uses_saved_permission(monkeypatch):
    monkeypatch.setattr("star.providers.get_api_key", lambda name: "test-only-key")
    cfg = SimpleNamespace(provider="star_server", server_endpoint="http://100.64.0.1:8080/v1")
    with pytest.raises(ValueError):
        connection_for(cfg)
    cfg.allow_cgnat = True
    assert connection_for(cfg) == ("http://100.64.0.1:8080/v1", "test-only-key")
    cfg.server_endpoint = "http://100.100.100.200:8080/v1"
    with pytest.raises(ValueError):
        connection_for(cfg)


def test_react_settings_allowlist_applies_opt_in():
    cfg = Settings()
    assert apply_setting_changes(cfg, {"allow_cgnat": True}).allow_cgnat is True
    assert apply_setting_changes(cfg, {"allow_cgnat": False}).allow_cgnat is False
