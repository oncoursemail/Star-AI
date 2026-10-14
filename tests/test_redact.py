"""Redaction replaces credentials only: ordinary prose and source code pass through unchanged."""
import base64
import json
import time

import pytest

from star.agent import tool_payload
from star.desktop_core import redact_for_logs
from star.redact import redact_text

LUAU = '''local DataStoreService = game:GetService("DataStoreService")
local store = DataStoreService:GetDataStore("PlayerData")
local function load(player)
    local key = "Player_" .. player.UserId
    local token = HttpService:GenerateGUID(false)
    local secret = string.format("%s_%d", prefix, player.UserId)
    for key, value in pairs(defaults) do data[key] = value end
    return store:GetAsync(key)
end
'''
PYTHON = '''def lookup(tokens, settings):
    token = tokens[0]
    key = lambda item: item.name
    password = load_password_from_settings(settings.path)
    secret = os.environ["STAR_SERVER_API_KEY"]
    api_key = settings.provider.credentials.current()
    cache_key = "3f2a9c1e7b6d4a5f8c0e1d2b3a4f5e6d7c8b9a0f"
    return {"key": "value", "token": "short", "password": None}
'''
TYPESCRIPT = '''type Login = {password: string; token?: string; secret: SecretStore}
const key: keyof Settings = 'provider'
const token = await session.manager.refreshAccessToken(account)
'''
PROSE = '''The server expects a Bearer token in the Authorization header.
Press the key: Enter. The secret: keep each save small.
Open http://localhost:8080/docs or https://example.invalid/a@b for the reference.
| name | key | token |
|---|---|---|
'''
MARKDOWN = "Here is the script:\n\n```lua\n" + LUAU + "```\n\nand the helper:\n\n```python\n" + PYTHON + "```\n"


@pytest.mark.parametrize("text", [LUAU, PYTHON, TYPESCRIPT, PROSE, MARKDOWN, "", "key", "token ="])
def test_ordinary_text_and_code_are_unchanged(text):
    assert redact_text(text) == text
    assert redact_for_logs({"messages": [{"role": "assistant", "content": text}]}) == {
        "messages": [{"role": "assistant", "content": text}]}


@pytest.mark.parametrize(("text", "secret"), [
    ("OPENAI_API_KEY=" + "sk-" + "a1B2" * 8, "a1B2" * 8),
    ('{"client_secret": "' + "q9Z-" * 8 + '"}', "q9Z-" * 8),
    ("DB_PASSWORD: " + "x7Yw" * 6, "x7Yw" * 6),
    ("local API_KEY = '" + "Zx81" * 7 + "'", "Zx81" * 7),
    ("Authorization: Bearer " + "c3Vw" * 6 + "==", "c3Vw" * 6),
    ("GET https://user:" + "p4ss" * 3 + "@example.invalid/v1 failed", "p4ss" * 3),
    ("token " + "ghp_" + "A1b2" * 9, "A1b2" * 9),
    ("-----BEGIN PRIVATE KEY-----\n" + "TUlJ" * 20 + "\n-----END PRIVATE KEY-----", "TUlJ" * 20),  # star:allow synthetic
])
def test_credentials_are_replaced_and_the_rest_is_kept(text, secret):
    safe = redact_text("before " + text + " after")
    assert secret not in safe
    assert "[REDACTED]" in safe
    assert safe.startswith("before ") and safe.endswith(" after")


def test_the_name_and_the_separator_stay_so_the_line_still_reads():
    assert redact_text("api_key = " + "R4nd" * 6) == "api_key = [REDACTED]"
    assert redact_text('"access_token": "' + "R4nd" * 6 + '",') == '"access_token": "[REDACTED]",'
    assert redact_text("https://user:pw@example.invalid/x") == "https://[REDACTED]@example.invalid/x"


def test_a_tool_error_is_redacted_and_a_successful_read_is_exact():
    line = 'local API_KEY = "' + "Zx81" * 7 + '"\n' + LUAU
    read = json.loads(tool_payload({"isError": False, "content": [{"type": "text", "text": line}]}))
    assert read == {"isError": False, "output": line}
    failure = "Workspace tool failed: ConnectError: https://user:" + "p4ss" * 3 + "@example.invalid Bearer " + "c3Vw" * 6
    failed = json.loads(tool_payload({"isError": True, "content": [{"type": "text", "text": failure}]}))
    assert failed["isError"] is True
    assert "p4ss" * 3 not in failed["output"] and "c3Vw" * 6 not in failed["output"]
    assert failed["output"].startswith("Workspace tool failed: ConnectError: https://[REDACTED]@example.invalid")


def test_long_input_is_handled_in_linear_time():
    hostile = (("token" * 6000) + " " + ("key=" * 5000) + ("A" * 30000) + "(" + ("http://a:" * 3000)
               + ("eyJ-" * 8000) + (" Bearer" * 4000) + ("-----BEGIN " * 2000) + ("sk-" * 9000) + " secret" + " " * 30000)
    began = time.perf_counter()
    redact_text(hostile)
    assert time.perf_counter() - began < 2.0


def test_a_finished_turn_keeps_the_answer_exact_for_the_user_and_redacts_only_the_artifacts(monkeypatch, tmp_path):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from star import desktop_core, doc_grounding
    from star.desktop_core import Settings, run_task

    secret = "Zx81" * 7
    reply = "Set it once:\n\n```lua\nlocal API_KEY = \"" + secret + "\"\n" + LUAU + "```\n"

    async def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply, tool_calls=None))])

    @asynccontextmanager
    async def fake_client(settings, **_):
        yield SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    home = tmp_path / "STAR"
    monkeypatch.setattr(desktop_core, "app_data", lambda: home)
    monkeypatch.setattr(desktop_core, "open_client", fake_client)
    monkeypatch.setattr(doc_grounding, "client_for", lambda settings: None)
    answer = run_task(Settings(model="m"), "Where do I put the key in my Roblox script?", on_event=lambda e: None)
    assert reply.strip() in (answer if isinstance(answer, str) else answer[0])   # what the user reads is not touched
    saved = next((home / "runs").glob("*/answer.md")).read_text(encoding="utf-8")
    assert secret not in saved and "local API_KEY = \"[REDACTED]\"" in saved
    assert LUAU in saved                                                         # the ordinary code is intact
    assert secret not in next((home / "runs").glob("*/transcript.json")).read_text(encoding="utf-8")
    for store in home.rglob("*.sqlite3"):
        if store.name != "conversations.sqlite3":                                # the chat itself keeps the exact answer
            assert secret.encode() not in store.read_bytes(), store.name


# Security audit 2026-10-13 (docs/security/AUDIT-20261013.md, L-5): more well-known key formats.
# Values are assembled from pieces so the source holds no credential-shaped literal.
# A Discord token's first part is the bot's numeric user id in base64 (24 characters for 18 digits).
_B64 = base64.urlsafe_b64encode(("1234" * 5)[:18].encode()).decode().rstrip("=")
_FORMATS = [
    ("hf_" + "Ab3d" * 9, "Ab3d" * 9),
    ("AKIA" + "Q7ZT" * 4, "Q7ZT" * 4),
    ("AIza" + "Sy9_" * 8 + "abc", "Sy9_" * 8),
    ("xoxb-" + "1234-5678-" + "aBcD" * 4, "aBcD" * 4),
    ("glpat-" + "Zq8-" * 6, "Zq8-" * 6),
    ("rk_" + "live_" + "Mn4p" * 6, "Mn4p" * 6),
    (_B64 + "." + "Gq1w2e" + "." + "Hm9" * 10, "Hm9" * 10),
    ("Authorization: Bot " + "c3Vw" * 6, "c3Vw" * 6),
]


@pytest.mark.parametrize(("text", "secret"), _FORMATS)
def test_more_key_formats_are_replaced(text, secret):
    safe = redact_text("seen " + text + " here")
    assert secret not in safe and "[REDACTED]" in safe
    assert safe.startswith("seen ") and safe.endswith(" here")


@pytest.mark.parametrize("text", [
    "The bot configuration_settings_file is loaded at start.",
    "Module.Something.Method(Instance.new('Part'))",
    "local hf_value = 3  -- AKIA prefix explained",
    "See https://example.invalid/docs/xox for details",
    "xoxo-gossip-girl-fans and xoxa-love-from-the-team",
    "require(NetworkReplicationController.Shared.AnimationControllerServiceModule)",
    "OnPlayerCharacterAddedEvent.Signal.ConnectParallelSomethingLongerName:Wait()",
])
def test_new_formats_leave_prose_alone(text):
    assert redact_text(text) == text
