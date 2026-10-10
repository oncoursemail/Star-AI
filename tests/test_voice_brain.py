"""The voice brain client: LAN-only address, streamed text, clean cancellation, and a key that never leaks."""
import json
import threading
import time

import httpx
import pytest

from star.voice.brain import BrainError, ScriptedBrain, ServerBrain, validate_server_url
from star.voice.persona import VOICE_SYSTEM_PROMPT, system_message
from star.voice.settings import VoiceSettings

KEY = "sk-test-do-not-leak-1234567890"


def sse(*pieces, reasoning=None):
    lines = ['data: {"choices":[{"delta":{"role":"assistant","content":null}}]}', ""]
    if reasoning:
        lines += ["data: " + json.dumps({"choices": [{"delta": {"reasoning_content": reasoning}}]}), ""]
    for piece in pieces:
        lines += ["data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}), ""]
    lines += ["data: [DONE]", ""]
    return "\n".join(lines).encode()


def brain_with(handler, **kwargs):
    brain = ServerBrain("http://10.17.0.146:8080/v1", KEY, **kwargs)
    brain._client = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
    return brain


def test_only_private_or_loopback_ip_addresses_ending_in_v1_are_accepted():
    for good in ("http://10.17.0.146:8080/v1", "http://127.0.0.1:8080/v1/", "https://192.168.1.20/v1",
                 "http://localhost:8080/v1"):
        assert validate_server_url(good).endswith("/v1")
    for bad in ("http://8.8.8.8:8080/v1", "http://example.com/v1", "ftp://10.0.0.1/v1", "http://10.0.0.1:8080/",
                "http://user:pw@10.0.0.1/v1", "http://10.0.0.1/v1?x=1", "http://10.0.0.1/v1/chat", ""):
        with pytest.raises(ValueError):
            validate_server_url(bad)
    with pytest.raises(ValueError):
        ServerBrain("http://10.0.0.1:8080/v1", "")


def test_stream_yields_text_only_and_sends_a_short_spoken_style_request():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=sse("Oh,", " well", " done.", reasoning="thinking hard"))

    brain = brain_with(handler, max_tokens=120)
    assert list(brain.stream([system_message(), {"role": "user", "content": "hi"}])) == ["Oh,", " well", " done."]
    body = seen["body"]
    assert seen["auth"] == f"Bearer {KEY}"
    assert body["model"] == "star-fast" and body["stream"] is True and body["max_tokens"] == 120
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["messages"][0] == {"role": "system", "content": VOICE_SYSTEM_PROMPT}


def test_errors_are_friendly_and_never_contain_the_key():
    for status, words in ((401, "refused the key"), (503, "still loading"), (400, "does not know this model"),
                          (500, "error (500)")):
        brain = brain_with(lambda request, s=status: httpx.Response(s, text=f"detail {KEY}"[:20]))
        with pytest.raises(BrainError) as caught:
            brain.stream([])
        assert words in str(caught.value) and KEY not in str(caught.value)

    def refuse(request):
        raise httpx.ConnectError(f"cannot connect with {KEY}")

    with pytest.raises(BrainError) as caught:
        brain_with(refuse).stream([])
    assert "Could not reach" in str(caught.value) and KEY not in str(caught.value)


def test_from_env_needs_both_variables_and_reads_them(monkeypatch):
    monkeypatch.delenv("STAR_SERVER_URL", raising=False)
    monkeypatch.delenv("STAR_SERVER_API_KEY", raising=False)
    with pytest.raises(BrainError, match="STAR_SERVER_URL"):
        ServerBrain.from_env()
    monkeypatch.setenv("STAR_SERVER_URL", "http://10.17.0.146:8080/v1")
    monkeypatch.setenv("STAR_SERVER_API_KEY", KEY)
    monkeypatch.setenv("STAR_VOICE_MODEL", "star-other")
    brain = ServerBrain.from_env()
    assert brain.base_url == "http://10.17.0.146:8080/v1" and brain.model == "star-other"
    assert KEY not in repr(vars(brain).get("base_url")) and KEY not in repr(brain)


def test_close_from_another_thread_ends_a_stream_cleanly():
    brain = ScriptedBrain(["one two three four five six seven eight"], first_delay=0.01, tokens_per_second=20)
    stream = brain.stream([])
    got = []
    threading.Timer(0.12, stream.close).start()
    started = time.monotonic()
    for piece in stream:
        got.append(piece)
    assert 1 <= len(got) < 8 and time.monotonic() - started < 0.4


def test_voice_prompt_asks_for_short_spoken_replies_with_a_quick_opening():
    prompt = VOICE_SYSTEM_PROMPT.lower()
    for phrase in ("two to five words", "one to three short sentences", "no lists", "you are an ai"):
        assert phrase in prompt
    assert len(VOICE_SYSTEM_PROMPT) < 1800                       # short and stable, so the server can cache it
    assert system_message("The user's name is Alex.")["content"].endswith("The user's name is Alex.")


def test_settings_validate_everything_the_ui_can_send(monkeypatch):
    defaults = VoiceSettings().validate()
    assert defaults.voice == "heart" and defaults.endpointer == "smart-turn" and defaults.output == "headphones"
    custom = VoiceSettings.from_mapping({"voice": "blend-heart-nicole", "speed": "0.9", "barge_in_ms": "400",
                                         "partial_transcripts": "false", "output": "speakers", "junk": 1})
    assert (custom.voice, custom.speed, custom.barge_in_ms, custom.partial_transcripts) == (
        "blend-heart-nicole", 0.9, 400, False)
    config = custom.call_config()
    assert config.use_echo_gate and config.turn.barge_in_ms == 400 and not config.partial_transcripts
    for bad in ({"voice": "../../etc/passwd"}, {"speed": 3}, {"asr_model": "huge"}, {"tts_engine": "sapi"},
                {"end_silence_ms": 10}, {"output": "phone"}, {"device": "tpu"}, {"max_reply_tokens": 5000}):
        with pytest.raises(ValueError):
            VoiceSettings.from_mapping(bad)
    monkeypatch.setenv("STAR_VOICE_VOICE", "af_heart:0.7+af_nicole:0.3")
    monkeypatch.setenv("STAR_VOICE_ASR_MODEL", "base.en")
    from_env = VoiceSettings.from_env()
    assert from_env.voice == "af_heart:0.7+af_nicole:0.3" and from_env.asr_model == "base.en"
