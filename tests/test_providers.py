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


@pytest.fixture
def two_slot_server():
    """A STAR Server whose model has reported two slots; what the process remembers is put back."""
    from star import providers
    kept = dict(providers._SERVER_LIMITS), dict(providers._SLOT_TABLE)
    cfg = SimpleNamespace(provider="star_server", server_endpoint="http://127.0.0.1:8080/v1",
                          model="model-slot-test")
    providers._SLOT_TABLE.clear()
    providers.remember_server_limits(cfg.server_endpoint, cfg.model, 8192, 2)
    yield cfg
    for table, before in zip((providers._SERVER_LIMITS, providers._SLOT_TABLE), kept):
        table.clear()
        table.update(before)


CACHE_ONLY = {"cache_prompt": True, "chat_template_kwargs": {"preserve_thinking": True}}


def test_a_turn_and_its_warm_up_share_one_slot_and_background_work_names_none(two_slot_server):
    from star import providers
    cfg = two_slot_server
    turn = providers.llama_request_fields(cfg, conversation="chat")
    assert turn in ({**CACHE_ONLY, "id_slot": 0}, {**CACHE_ONLY, "id_slot": 1})
    # The warm-up prepares the prompt for the next turn, so it must go where that turn goes.
    for options in ({"prime": True}, {"prime": True, "tools": True}, {"tools": True}):
        assert providers.llama_request_fields(cfg, conversation="chat", **options) == turn
    for options in ({"background": True}, {"background": True, "prime": True}, {"background": True, "tools": True}):
        assert providers.llama_request_fields(cfg, conversation="chat", **options) == CACHE_ONLY
    for options in ({}, {"prime": True}):                    # nothing to come back to: not pinned
        assert providers.llama_request_fields(cfg, conversation="", **options) == CACHE_ONLY
    assert providers.llama_request_fields(cfg, conversation="chat") == turn


def test_single_slot_or_unknown_slot_never_pins(two_slot_server):
    from star import providers
    cfg = SimpleNamespace(provider="star_server", server_endpoint=two_slot_server.server_endpoint,
                          model="model-single-test")
    assert providers.llama_request_fields(cfg, conversation="a") == CACHE_ONLY          # /props not read yet
    providers.remember_server_limits(cfg.server_endpoint, cfg.model, 8192, 1)
    assert providers.llama_request_fields(cfg, conversation="a") == CACHE_ONLY
    assert providers.llama_request_fields(cfg, conversation="a", prime=True) == CACHE_ONLY


def test_background_client_dispatch_does_not_pin(two_slot_server):
    import asyncio
    from star import providers
    cfg = two_slot_server
    calls = []

    class FakeCompletion:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return {"ok": True}

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeCompletion())
    plain = FakeClient()
    client = providers.background_client(plain, cfg, conversation="chat")
    assert client is not plain
    assert asyncio.run(client.chat.completions.create(model=cfg.model, messages=[])) == {"ok": True}
    assert calls == [{"model": cfg.model, "messages": [], "extra_body": CACHE_ONLY}]
    # A caller's own extra_body is passed on untouched.
    asyncio.run(client.chat.completions.create(model=cfg.model, messages=[], extra_body={"id_slot": 1}))
    assert calls[1]["extra_body"] == {"id_slot": 1}
