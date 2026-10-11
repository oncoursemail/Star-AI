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

def test_conversation_slots_stable_without_process_state():
    from star import providers
    cfg = SimpleNamespace(provider="star_server", server_endpoint="http://127.0.0.1:8080/v1",
                          model="model-slot-test")
    providers.remember_server_limits(cfg.server_endpoint, cfg.model, 8192, 2)
    ids = ["conversation-a", "conversation-b"]
    # Select two ids with different homes, independently of hash implementation.
    candidates = [f"conversation-{i}" for i in range(32)]
    first = candidates[0]
    second = next(x for x in candidates[1:]
                  if providers.llama_request_fields(cfg, conversation=x)["id_slot"] !=
                     providers.llama_request_fields(cfg, conversation=first)["id_slot"])
    a = providers.llama_request_fields(cfg, conversation=first)
    b = providers.llama_request_fields(cfg, conversation=second)
    assert a["id_slot"] != b["id_slot"]
    assert providers.llama_request_fields(cfg, conversation=first)["id_slot"] == a["id_slot"]
    # Simulate a fresh process: no in-memory chat assignment needed.
    assert providers.llama_request_fields(cfg, conversation=first)["id_slot"] == a["id_slot"]


def test_background_and_warmup_requests_are_not_pinned():
    from star import providers
    cfg = SimpleNamespace(provider="star_server", server_endpoint="http://127.0.0.1:8080/v1",
                          model="model-batch-test")
    providers.remember_server_limits(cfg.server_endpoint, cfg.model, 8192, 4)
    for options in ({"background": True}, {"prime": True}, {}):
        fields = providers.llama_request_fields(cfg, conversation="" if not options else "chat",
                                                **options)
        assert "id_slot" not in fields
        assert fields["cache_prompt"] is True


def test_single_slot_or_unknown_slot_never_pins():
    from star import providers
    cfg = SimpleNamespace(provider="star_server", server_endpoint="http://127.0.0.1:8080/v1",
                          model="model-single-test")
    assert "id_slot" not in providers.llama_request_fields(cfg, conversation="a")
    providers.remember_server_limits(cfg.server_endpoint, cfg.model, 8192, 1)
    assert "id_slot" not in providers.llama_request_fields(cfg, conversation="a")


def test_background_client_dispatch_does_not_pin():
    import asyncio
    from star import providers
    cfg = SimpleNamespace(provider="star_server", server_endpoint="http://127.0.0.1:8080/v1",
                          model="model-dispatch-test")
    providers.remember_server_limits(cfg.server_endpoint, cfg.model, 8192, 2)
    calls = []
    class FakeCompletion:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return {"ok": True}
    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeCompletion())
    client = providers.background_client(FakeClient(), cfg, conversation="chat")
    assert asyncio.run(client.chat.completions.create(model=cfg.model, messages=[])) == {"ok": True}
    assert calls[0]["extra_body"]["cache_prompt"] is True
    assert "id_slot" not in calls[0]["extra_body"]
