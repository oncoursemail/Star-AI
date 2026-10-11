"""Client for the STAR Brain (llama.cpp router, OpenAI-compatible), standard library only.

* One request at a time (the caller never overlaps calls).
* Chat requests are streamed so that a running generation can be dropped within a few seconds when somebody
  else starts using the server (a second busy slot on the model, or any busy slot on another model), when the
  quiet lock appears, or when the job is asked to stop. The server cancels a generation whose connection closes.
* The key is read from a file into memory and is never printed or logged.
"""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import socket
import threading
import time
from urllib.parse import urlsplit


class BrainError(RuntimeError):
    pass


class Yielded(Exception):
    """The request was dropped on purpose; `reason` is interactive, lock, pause-file, window or stop."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Brain:
    def __init__(self, url: str, key_file: str, *, timeout: float = 900.0, poll_s: float = 3.0, clock=time.monotonic):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("brain url must be http(s)://host:port")
        self._https = parts.scheme == "https"
        self._host = parts.hostname
        self._port = parts.port or (443 if self._https else 80)
        self._timeout = timeout
        self._poll_s = poll_s
        self._clock = clock
        self._key = ""
        path = Path(key_file)
        if path.is_file():
            lines = path.read_text(encoding="utf-8").splitlines()
            self._key = lines[0].strip() if lines else ""
        self._loaded: list[str] = []
        self._alias_of: dict[str, str] = {}
        self._loaded_at = -1e9
        self._last_other = -1e9
        self._slot_errors: set[str] = set()

    # --- plumbing -----------------------------------------------------------------------------------------
    def _conn(self, timeout: float):
        cls = http.client.HTTPSConnection if self._https else http.client.HTTPConnection
        return cls(self._host, self._port, timeout=timeout)

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = "Bearer " + self._key
        headers.update(extra or {})
        return headers

    def _json(self, method: str, path: str, body: dict | None = None, timeout: float = 20.0):
        conn = self._conn(timeout)
        try:
            conn.request(method, path, body=None if body is None else json.dumps(body), headers=self._headers())
            response = conn.getresponse()
            raw = response.read(8 * 1024 * 1024)
            if response.status != 200:
                raise BrainError(f"{path} returned HTTP {response.status}")
            return json.loads(raw.decode("utf-8", "replace"))
        except (OSError, http.client.HTTPException, ValueError) as exc:
            if isinstance(exc, BrainError):
                raise
            raise BrainError(f"{path} failed: {type(exc).__name__}") from exc
        finally:
            conn.close()

    # --- who else is using the server ------------------------------------------------------------------------
    def loaded_models(self, max_age: float = 60.0) -> list[str]:
        now = self._clock()
        if now - self._loaded_at > max_age:
            try:
                data = self._json("GET", "/v1/models")
                rows = [m for m in data.get("data", [])
                        if isinstance(m, dict) and (m.get("status") or {}).get("value") == "loaded"]
                self._loaded = [m["id"] for m in rows]
                self._alias_of = {a: m["id"] for m in rows for a in (m.get("aliases") or [])}
                self._loaded_at = now
            except BrainError:
                self._loaded_at = now - max_age + 10      # try again in 10 s; keep the old list
        return list(self._loaded)

    def busy_slots(self, model: str) -> int:
        """Number of slots of `model` that are processing a request right now (0 when it cannot be asked)."""
        try:
            slots = self._json("GET", "/slots?model=" + model, timeout=5.0)
        except BrainError:
            if model not in self._slot_errors:
                self._slot_errors.add(model)
            return 0
        if not isinstance(slots, list):
            return 0
        return sum(1 for slot in slots if isinstance(slot, dict) and slot.get("is_processing"))

    def others_active(self, own_model: str | None = None) -> bool:
        """True when somebody else is using the brain. Our own request (if any) accounts for one busy slot of
        `own_model`. Remembers when it last saw activity."""
        models = self.loaded_models()
        own_model = self._alias_of.get(own_model, own_model)
        for model in models:
            allowed = 1 if model == own_model else 0
            if self.busy_slots(model) > allowed:
                self._last_other = self._clock()
                return True
        return False

    def seconds_since_other_activity(self) -> float:
        return self._clock() - self._last_other

    # --- requests -----------------------------------------------------------------------------------------------
    def chat(self, model: str, messages: list[dict], *, max_tokens: int, temperature: float = 0.6,
             top_p: float = 0.95, should_yield=lambda: "", seed: int | None = None) -> dict:
        """Stream one chat completion. Returns {text, finish, prompt_tokens, completion_tokens, seconds}.
        `should_yield()` is asked every few seconds from a watcher thread; a non-empty answer closes the
        connection (the server then cancels the generation) and raises Yielded."""
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                   "top_p": top_p, "stream": True, "stream_options": {"include_usage": True},
                   "cache_prompt": True, "chat_template_kwargs": {"enable_thinking": False}}
        if seed is not None:
            payload["seed"] = seed
        started = self._clock()
        conn = self._conn(self._timeout)
        abort = {"reason": "", "timeout": False}
        done = threading.Event()

        def watch() -> None:
            while not done.wait(self._poll_s):
                reason = ""
                if self._clock() - started > self._timeout:
                    abort["timeout"] = True
                    reason = "timeout"
                else:
                    try:
                        reason = should_yield() or ""
                    except Exception:      # a failing check must never kill the request silently
                        reason = ""
                if reason:
                    abort["reason"] = reason
                    try:
                        conn.sock.shutdown(socket.SHUT_RDWR)
                    except (OSError, AttributeError):
                        pass
                    return

        watcher = threading.Thread(target=watch, daemon=True)
        text: list[str] = []
        finish = ""
        usage: dict = {}
        try:
            conn.request("POST", "/v1/chat/completions", body=json.dumps(payload), headers=self._headers())
            watcher.start()
            response = conn.getresponse()
            if response.status != 200:
                raise BrainError(f"chat returned HTTP {response.status}")
            while True:
                chunk = response.fp.readline()
                if not chunk:
                    break
                line = chunk.strip()
                if not line.startswith(b"data:"):
                    continue
                body = line[5:].strip()
                if body == b"[DONE]":
                    break
                try:
                    event = json.loads(body.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if isinstance(event.get("error"), dict):
                    raise BrainError("chat error: " + str(event["error"].get("message", ""))[:120])
                if event.get("usage"):
                    usage = event["usage"]
                for choice in event.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        text.append(delta["content"])
                    if choice.get("finish_reason"):
                        finish = choice["finish_reason"]
        except (OSError, http.client.HTTPException, ValueError) as exc:
            if abort["reason"] and not abort["timeout"]:
                raise Yielded(abort["reason"]) from exc
            raise BrainError(f"chat failed: {type(exc).__name__}") from exc
        finally:
            done.set()
            conn.close()
            if watcher.is_alive():
                watcher.join(2.0)
        if abort["reason"]:
            if abort["timeout"]:
                raise BrainError("chat request timed out")
            raise Yielded(abort["reason"])
        return {"text": "".join(text), "finish": finish, "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "seconds": round(self._clock() - started, 2)}

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        data = self._json("POST", "/v1/embeddings", {"model": model, "input": texts}, timeout=120.0)
        rows = sorted(data["data"], key=lambda r: r["index"])
        return [r["embedding"] for r in rows]
