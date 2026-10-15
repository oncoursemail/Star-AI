"""Opt-in skill-pack routing by embedding similarity (star/skill_routing.py). The embedder is scripted."""
import asyncio
import json

import pytest

from star import skill_packs, skill_routing
from star.desktop_core import Settings

ALL = frozenset(p.name for p in skill_packs.available())
NO_TRIGGER = "Players in my Roblox game sometimes lose their progress when the server shuts down. How do I fix it?"


class Embedder:
    """Unit vectors: a pack whose name contains `near` points the same way as every query; others are orthogonal."""

    def __init__(self, near="roblox-datastore-safety", fail=None):
        self.near, self.fail, self.calls = near, fail, []

    async def __call__(self, texts):
        self.calls.append(list(texts))
        if self.fail:
            raise self.fail
        out = []
        for text in texts:
            if text.startswith(skill_routing.QUERY_PREFIX) or self.near.replace("-", " ") in text:
                out.append([1.0, 0.0])
            else:
                out.append([0.0, 1.0])
        return out


def run(coro):
    return asyncio.run(coro)


def test_off_by_default():
    assert Settings().skill_pack_embeddings is False


def test_a_prompt_without_trigger_words_gets_the_closest_pack(tmp_path):
    assert skill_packs.select(NO_TRIGGER, enabled=ALL) == []                     # the keyword router is silent
    embed = Embedder()
    chosen = run(skill_routing.select(NO_TRIGGER, embed, enabled=ALL, home=tmp_path))
    assert [p.name for p in chosen] == ["roblox-datastore-safety"]


def test_the_keyword_router_wins_when_it_has_an_answer(tmp_path):
    prompt = "Roblox: how do I validate RemoteEvent arguments on the server against exploiters?"
    keyword = skill_packs.select(prompt, enabled=ALL)
    assert keyword
    embed = Embedder()
    assert run(skill_routing.select(prompt, embed, enabled=ALL, home=tmp_path)) == keyword
    assert embed.calls == []                                                     # no server call at all


def test_prompts_outside_the_context_rules_never_reach_the_embedder(tmp_path):
    embed = Embedder()
    assert run(skill_routing.select("How do I bake bread?", embed, enabled=ALL, home=tmp_path)) == []
    assert run(skill_routing.select(NO_TRIGGER, embed, enabled=frozenset(), home=tmp_path)) == []
    assert embed.calls == []


def test_nothing_close_enough_means_no_pack(tmp_path):
    embed = Embedder(near="no-such-pack")
    assert run(skill_routing.select(NO_TRIGGER, embed, enabled=ALL, home=tmp_path)) == []


def test_server_problems_fall_back_to_the_keyword_answer_and_are_reported(tmp_path):
    reasons = []
    for failure in (ConnectionError("unreachable"), asyncio.TimeoutError()):
        embed = Embedder(fail=failure)
        assert run(skill_routing.select(NO_TRIGGER, embed, enabled=ALL, home=tmp_path,
                                        on_fallback=reasons.append)) == []
    assert reasons == ["ConnectionError", "TimeoutError"]

    async def odd(texts):
        return [[1.0]]                                                           # wrong count
    assert run(skill_routing.select(NO_TRIGGER, odd, enabled=ALL, home=tmp_path)) == []


def test_pack_vectors_are_cached_on_disk_and_only_the_query_is_embedded_next_time(tmp_path):
    first = Embedder()
    run(skill_routing.select(NO_TRIGGER, first, enabled=ALL, home=tmp_path))
    assert len(first.calls) == 2 and len(first.calls[0]) > 1                     # pack batch, then the query
    cache = json.loads((tmp_path / skill_routing.CACHE_FILE).read_text(encoding="utf-8"))
    assert len(cache) == len(first.calls[0])
    second = Embedder()
    run(skill_routing.select(NO_TRIGGER, second, enabled=ALL, home=tmp_path))
    assert second.calls == [[skill_routing.QUERY_PREFIX + NO_TRIGGER]]


@pytest.mark.parametrize("value", [None, "yes", 1])
def test_the_setting_is_a_strict_boolean_and_saved_by_the_desktop(value):
    with pytest.raises(ValueError):
        Settings(model="m", skill_pack_embeddings=value).validate()
    from star.react_shell import PERMITTED_SETTINGS
    assert "skill_pack_embeddings" in PERMITTED_SETTINGS


@pytest.mark.parametrize(("enabled", "provider", "embedded"), [
    (True, "star_server", True), (False, "star_server", False), (True, "local", False)])
def test_run_task_asks_star_server_for_embeddings_only_when_opted_in(tmp_path, monkeypatch, enabled, provider, embedded):
    from types import SimpleNamespace
    import star.desktop_core as core
    import star.doc_grounding as doc_grounding
    from tests.test_wave3_integration import FLEET, KEY, Models, reply
    from star import server_roles
    lan = "http://192.168." + "1.20:8080/v1"
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("STAR_SERVER_API_KEY", KEY)
    monkeypatch.setenv(skill_packs.ENV_VAR, "all")
    models, asked = Models(), []
    models.responses.append(reply("Done.", model="star-fast"))

    async def embeddings(*, model, input):
        asked.append((model, list(input)))
        vectors = [[1.0, 0.0] if t.startswith(skill_routing.QUERY_PREFIX) or "datastore safety" in t else [0.0, 1.0]
                   for t in input]
        return SimpleNamespace(data=[SimpleNamespace(index=i, embedding=v) for i, v in enumerate(vectors)])

    class Client:
        def __init__(self):
            self.chat = SimpleNamespace(completions=models)
            self.embeddings = SimpleNamespace(create=embeddings)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False
    monkeypatch.setattr(core, "open_client", lambda settings, **_: Client())
    monkeypatch.setattr(doc_grounding, "client_for", lambda settings: None)
    fields = {"provider": "star_server", "server_endpoint": lan} if provider == "star_server" else {}
    if provider == "star_server":
        server_roles.remember_models(lan, FLEET)
    settings = Settings(model="star-fast", skill_pack_embeddings=enabled, **fields)
    events = []
    try:
        core.run_task(settings, NO_TRIGGER, mode="auto", on_event=events.append)
    finally:
        server_roles.forget()
    assert bool(asked) is embedded
    sent = json.dumps(models.requests[-1]["messages"][-1])
    assert ("Save Roblox player data" in sent or "DataStore" in sent) is embedded
    if embedded:
        assert asked[0][0] == skill_routing.EMBED_MODEL
        assert next(e for e in events if e["event"] == "skill_packs")["names"] == ["roblox-datastore-safety"]
