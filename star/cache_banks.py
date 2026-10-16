"""Opt-in llama.cpp prompt-prefix KV banks for the operator's own STAR Server.

An on-server snapshot is not a knowledge database: the model must use exactly
the same tokenizer/template and prompt prefix. STAR stores only an opaque local
receipt, not raw prompts, cache tensors, user content or authentication tokens.
The actual KV state remains under llama-server's owner-configured --slot-save-path.

Never enable this silently. The read/write slot endpoints can interfere with
other clients and expose cached prompt state on an unsecured server.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any

import httpx

from .providers import connection_for, provider_kind, server_slots

ENV_ENABLE = "STAR_KV_BANKS"
ENV_REVISION = "STAR_KV_BANK_MODEL_REVISION"
SCHEMA_VERSION = 1
MAX_INDEX_BYTES = 24_000
MAX_REPLY_BYTES = 4_096
MAX_BANKS = 16
MAX_BANK_AGE_SECONDS = 12 * 60 * 60
# Server may have gigabytes of KV. This is only a sanity check of its report;
# the actual storage quota must be configured and monitored on the server.
MAX_SNAPSHOT_BYTES = 16 * 1024**3
MODEL_REV = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{7,95}$")
BANK_NAME = re.compile(r"^star-kv-[a-f0-9]{40}\.bin$")


@dataclass(frozen=True)
class BankPlan:
    filename: str
    fingerprint: str
    slot: int
    model: str
    scope: str


def enabled() -> bool:
    """Explicit opt-in; no other environment value means approval."""
    return os.environ.get(ENV_ENABLE) == "on"


def plan(settings: Any, request: dict, *, scope: str) -> BankPlan | None:
    """Build a project/chat/model-specific receipt from the *shared prefix*.

    Hash system and tools but NOT the changing history: on restore llama.cpp
    must compare request tokens to the snapshot and re-evaluate any divergent
    suffix (cache_prompt=True). No snapshot is an authority for live context.
    """
    revision = os.environ.get(ENV_REVISION, "")
    if not enabled() or not MODEL_REV.fullmatch(revision):
        return None
    if provider_kind(settings) != "lan" or type(scope) is not str or not 1 <= len(scope) <= 200:
        return None
    if any(ord(ch) < 32 for ch in scope):
        return None
    if not isinstance(request, dict) or not isinstance(request.get("messages"), list):
        return None
    messages = request["messages"]
    if not messages or not isinstance(messages[0], dict) or messages[0].get("role") != "system":
        return None
    model = request.get("model")
    extras = request.get("extras")
    if not isinstance(model, str) or not 1 <= len(model) <= 180 or not isinstance(extras, dict):
        return None
    slot = extras.get("id_slot")
    slots = server_slots(settings, model)
    if type(slot) is not int or not 2 <= slots <= 64 or not 0 <= slot < slots:
        return None
    if extras.get("cache_prompt") is not True:
        return None
    # Inference template settings and tool *order* are part of the prefix.
    try:
        common = {
            "schema": SCHEMA_VERSION, "server": str(settings.server_endpoint).rstrip("/"),
            "project": str(settings.project), "conversation_scope": scope,
            "model": model, "revision": revision, "system": messages[0],
            "tools": request.get("tools") or [],
            "template": extras.get("chat_template_kwargs") or {},
        }
        encoded = json.dumps(common, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > 250_000:
            return None
        fingerprint = hashlib.sha256(encoded).hexdigest()
        # A stable filename for this chat/model/revision, so updated content
        # replaces the old snapshot rather than proliferating files per turn.
        namespace = json.dumps([SCHEMA_VERSION, common["server"], common["project"],
                                scope, model, revision], ensure_ascii=False).encode("utf-8")
        filename = "star-kv-" + hashlib.sha256(namespace).hexdigest()[:40] + ".bin"
    except (ValueError, TypeError, AttributeError):
        return None
    return BankPlan(filename=filename, fingerprint=fingerprint, slot=slot, model=model, scope=scope)


def _index_path(home: Path) -> Path:
    folder = home / "cache-banks"
    if home.is_symlink() or folder.is_symlink():
        raise PermissionError("KV bank index cannot be in a symlink")
    return folder / "index.json"


def _load(home: Path) -> dict:
    file = _index_path(home)
    if file.is_symlink():
        raise PermissionError("KV bank index cannot be a symlink")
    if not file.is_file():
        return {}
    if file.stat().st_size > MAX_INDEX_BYTES:
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        return data["banks"] if isinstance(data, dict) and data.get("version") == SCHEMA_VERSION and (
            isinstance(data.get("banks"), dict)) else {}
    except (OSError, UnicodeError, ValueError, TypeError):
        return {}


def _has_matching_receipt(home: Path, candidate: BankPlan, *, now: float) -> bool:
    try:
        record = _load(home).get(candidate.filename)
    except (PermissionError, OSError):
        return False
    if not isinstance(record, dict):
        return False
    stamp = record.get("saved_at")
    return (record.get("fingerprint") == candidate.fingerprint
            and isinstance(stamp, (int, float)) and not isinstance(stamp, bool) and 0 <= now - stamp <= MAX_BANK_AGE_SECONDS)


def _record(home: Path, candidate: BankPlan, *, now: float, n_saved: int) -> None:
    """Atomic, restricted local metadata only; no raw user/project/model prompt."""
    if not 1 <= n_saved <= 10_000_000:
        return
    file = _index_path(home)
    banks = _load(home)
    banks = {key: value for key, value in banks.items()
             if BANK_NAME.fullmatch(str(key)) and isinstance(value, dict)
             and type(value.get("saved_at")) in (float, int)
             and 0 <= now - value["saved_at"] <= MAX_BANK_AGE_SECONDS}
    banks[candidate.filename] = {"fingerprint": candidate.fingerprint, "saved_at": now}
    banks = dict(sorted(banks.items(), key=lambda item: item[1]["saved_at"], reverse=True)[:MAX_BANKS])
    file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if file.is_symlink():
        raise PermissionError("KV bank index cannot be a symlink")
    payload = json.dumps({"version": SCHEMA_VERSION, "banks": banks},
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=file.parent, prefix=".kv-bank-", delete=False) as stream:
            name = Path(stream.name)
            os.chmod(name, 0o600)
            stream.write(payload)
        os.replace(name, file)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


async def _post(settings, candidate: BankPlan, *, action: str,
                transport: httpx.AsyncBaseTransport | None = None,
                cancel_event=None) -> dict:
    """One no-redirect LAN call, after checking that the exact model slot is idle."""
    if action not in {"save", "restore"} or not enabled():
        return {"performed": False, "reason": "disabled"}
    if cancel_event is not None and cancel_event.is_set():
        return {"performed": False, "reason": "cancelled"}
    try:
        endpoint, key = connection_for(settings)
        if provider_kind(settings) != "lan":
            return {"performed": False, "reason": "not_local_server"}
        endpoint = endpoint.rstrip("/")
        if not endpoint.endswith("/v1") or not isinstance(key, str) or not key:
            return {"performed": False, "reason": "endpoint"}
        root = endpoint[:-3]
        headers = {"Authorization": "Bearer " + key, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=1.0),
                                     trust_env=False, follow_redirects=False,
                                     transport=transport) as client:
            # More than one STAR client or worker can use this same server.
            # A busy slot must never be saved/overwritten by a bank operation.
            probe = await client.get(root + "/slots", params={"model": candidate.model}, headers=headers)
            if probe.status_code != 200 or len(probe.content) > MAX_REPLY_BYTES:
                return {"performed": False, "reason": "slots_unavailable"}
            slots = probe.json()
            if not isinstance(slots, list):
                return {"performed": False, "reason": "slots_invalid"}
            selected = next((row for row in slots if isinstance(row, dict)
                             and type(row.get("id")) is int and row["id"] == candidate.slot), None)
            if selected is None or selected.get("is_processing") is not False:
                return {"performed": False, "reason": "slot_busy_or_unknown"}
            if cancel_event is not None and cancel_event.is_set():
                return {"performed": False, "reason": "cancelled"}
            async with client.stream("POST", root + f"/slots/{candidate.slot}",
                                     params={"action": action, "model": candidate.model},
                                     headers={**headers, "Content-Type": "application/json"},
                                     json={"filename": candidate.filename}) as response:
                if response.status_code != 200:
                    return {"performed": False, "reason": "unsupported_or_missing"}
                parts, total = [], 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_REPLY_BYTES:
                        return {"performed": False, "reason": "reply_too_large"}
                    parts.append(chunk)
                payload = json.loads(b"".join(parts))
                key = "n_saved" if action == "save" else "n_restored"
                byte_key = "n_written" if action == "save" else "n_read"
                count, byte_count = payload.get(key), payload.get(byte_key)
                if (type(payload.get("id_slot")) is not int or payload["id_slot"] != candidate.slot
                        or payload.get("filename") != candidate.filename
                        or type(count) is not int or count <= 0 or count > 10_000_000
                        or type(byte_count) is not int or byte_count <= 0
                        or byte_count > MAX_SNAPSHOT_BYTES):
                    return {"performed": False, "reason": "invalid_receipt"}
                return {"performed": True, "tokens": count, "bytes": byte_count}
    except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError):
        return {"performed": False, "reason": "unavailable"}


async def restore(settings, home: Path, candidate: BankPlan, *,
                  transport=None, cancel_event=None, now=None) -> dict:
    """Skip unknown/stale/incompatible banks; never guess whether a slot save exists."""
    current = time.time() if now is None else now
    if not _has_matching_receipt(home, candidate, now=current):
        return {"performed": False, "reason": "not_cached"}
    return await _post(settings, candidate, action="restore",
                       transport=transport, cancel_event=cancel_event)


async def save(settings, home: Path, candidate: BankPlan, *,
               transport=None, cancel_event=None, now=None) -> dict:
    """Call only after a successfully primed response, and record verified saves."""
    result = await _post(settings, candidate, action="save",
                         transport=transport, cancel_event=cancel_event)
    if result.get("performed"):
        try:
            _record(home, candidate, now=time.time() if now is None else now,
                    n_saved=result["tokens"])
        except (OSError, PermissionError, ValueError):
            return {"performed": False, "reason": "index_write_failed"}
    return result
