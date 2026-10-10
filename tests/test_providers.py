"""Provider boundaries and credential-safe desktop configuration."""
from types import SimpleNamespace
import pytest
from star.providers import PROVIDERS, KEY_ENV, connection_for, credential_status, save_api_key

def test_provider_urls_are_fixed_https_and_local_is_explicit(monkeypatch):
    for name,p in PROVIDERS.items():
        assert p.base_url.startswith("https://")
        assert p.env_var in KEY_ENV.values()
    cfg=SimpleNamespace(provider="local",endpoint="http://127.0.0.1:8080/v1")
    assert connection_for(cfg)==("http://127.0.0.1:8080/v1","local-only")
    cfg.provider="evil"
    with pytest.raises(ValueError): connection_for(cfg)

def test_keys_only_from_environment_or_os_store(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY","dummy-test-token")
    cfg=SimpleNamespace(provider="groq",endpoint="http://127.0.0.1:8080/v1")
    url,key=connection_for(cfg)
    assert url=="https://api.groq.com/openai/v1" and key=="dummy-test-token"
    assert credential_status()["groq"]
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(ValueError,match="API key"):connection_for(cfg)

def test_reject_untrusted_credentials():
    for value in ("short","with spaces","line\nbreak", "x"*2049):
        with pytest.raises(ValueError):save_api_key("groq",value)
    with pytest.raises(ValueError):save_api_key("other","valid-secret")
