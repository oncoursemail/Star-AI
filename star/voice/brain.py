"""Streaming chat client for voice calls (OpenAI-compatible server, e.g. the STAR Server llama.cpp router).

Hand-off note: this module reads STAR_SERVER_URL and STAR_SERVER_API_KEY from the environment because the
`star_server` provider is being added to star/providers.py on another branch. Once that lands, replace
`ServerBrain.from_env()` with the (base_url, api_key) pair from `connection_for(settings)`; nothing else here
depends on where the address and key come from.

The key is only ever placed in the Authorization header. It is never logged, printed or put in an exception.
"""
from __future__ import annotations

import ipaddress
import json
import os
import threading
from typing import Iterator
from urllib.parse import urlsplit

DEFAULT_MODEL = "star-fast"


class BrainError(RuntimeError):
    """A failure talking to the brain, with a message that is safe to show to the user."""


def validate_server_url(url: str) -> str:
    """Accept only http(s)://<private or loopback IP>[:port]/v1, so the key cannot be sent to a public host."""
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("STAR_SERVER_URL must look like http://10.0.0.5:8080/v1")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("STAR_SERVER_URL must not contain a user name, query or fragment")
    if parts.path.rstrip("/") != "/v1":
        raise ValueError("STAR_SERVER_URL must end with /v1")
    host = parts.hostname
    if host != "localhost":
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("STAR_SERVER_URL must use an IP address on your own network, not a host name") from exc
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ValueError("STAR_SERVER_URL must point to your own network (private or loopback address)")
    return url.strip().rstrip("/")


class ChatStream:
    """Iterator of text deltas. close() may be called from another thread to abort the request at once."""

    def __init__(self, open_response) -> None:
        self._closed = threading.Event()
        self._context = open_response()
        try:
            self._response = self._context.__enter__()
        except Exception as exc:
            raise BrainError(_describe(exc)) from None
        if self._response.status_code != 200:
            status = self._response.status_code
            try:
                self._response.read()
                detail = self._response.text[:200]
            except Exception:
                detail = ""
            self.close()
            raise BrainError(_status_message(status, detail))
        self._lines = self._response.iter_lines()

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        while True:
            if self._closed.is_set():
                raise StopIteration
            try:
                line = next(self._lines)
            except StopIteration:
                self.close()
                raise
            except Exception as exc:
                was_closed = self._closed.is_set()
                self.close()
                if was_closed:           # closed on purpose (barge-in): a clean stop, not an error
                    raise StopIteration from None
                raise BrainError(_describe(exc)) from None
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                self.close()
                raise StopIteration
            try:
                choice = json.loads(data)["choices"][0]
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            text = (choice.get("delta") or {}).get("content")     # reasoning_content is ignored on purpose
            if text:
                return text

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self._response.close()
        except Exception:
            pass
        try:
            self._context.__exit__(None, None, None)
        except Exception:
            pass


def _status_message(status: int, detail: str) -> str:
    if status == 401:
        return "The STAR Server refused the key (401). Check STAR_SERVER_API_KEY."
    if status == 503:
        return "The STAR Server is still loading its model (503). Try again in a moment."
    if status in {400, 404}:
        return f"The STAR Server does not know this model ({status}). {detail[:120]}"
    return f"The STAR Server answered with an error ({status})."


def _describe(exc: Exception) -> str:
    name = type(exc).__name__
    if "Timeout" in name:
        return "The STAR Server did not answer in time."
    if "Connect" in name:
        return "Could not reach the STAR Server. Is it on, and is the address right?"
    return f"The connection to the STAR Server broke ({name})."


class ServerBrain:
    """Talks to one OpenAI-compatible endpoint. Thread-safe: each stream() call is its own request."""

    def __init__(self, base_url: str, api_key: str, model: str = DEFAULT_MODEL, *, max_tokens: int = 220,
                 temperature: float = 0.7, connect_timeout: float = 5.0, read_timeout: float = 60.0) -> None:
        import httpx
        self.base_url = validate_server_url(base_url)
        if not api_key:
            raise ValueError("The STAR Server key is empty")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # trust_env=False: a Windows system proxy must never see LAN traffic or the key.
        self._client = httpx.Client(trust_env=False, timeout=httpx.Timeout(read_timeout, connect=connect_timeout))

    @classmethod
    def from_env(cls, **kwargs) -> "ServerBrain":
        url = os.environ.get("STAR_SERVER_URL", "").strip()
        key = os.environ.get("STAR_SERVER_API_KEY", "").strip()
        if not url or not key:
            raise BrainError("Set STAR_SERVER_URL (for example http://10.17.0.146:8080/v1) and STAR_SERVER_API_KEY "
                             "before starting a voice call.")
        return cls(url, key, os.environ.get("STAR_VOICE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL, **kwargs)

    def stream(self, messages: list[dict], *, max_tokens: int | None = None) -> ChatStream:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature,
            "top_p": 0.9,
            "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False},   # a voice reply must not spend seconds thinking
        }
        return ChatStream(lambda: self._client.stream("POST", f"{self.base_url}/chat/completions",
                                                      headers=self._headers, json=payload))

    def prime(self, messages: list[dict]) -> None:
        """Have the server read the system prompt before the first turn so its prefix is already cached."""
        try:
            stream = self.stream(messages + [{"role": "user", "content": "Hello."}], max_tokens=1)
            for _ in stream:
                break
            stream.close()
        except BrainError:
            pass          # priming is only an optimisation; the first real turn will report any problem

    def close(self) -> None:
        self._client.close()


class _ScriptedStream:
    def __init__(self, text: str, first_delay: float, delay: float) -> None:
        words = text.split(" ")
        self._pieces = [w if i == 0 else " " + w for i, w in enumerate(words)]
        self._first_delay, self._delay, self._sent = first_delay, delay, 0
        self._closed = threading.Event()

    def __iter__(self):
        return self

    def __next__(self) -> str:
        wait = self._first_delay if self._sent == 0 else self._delay
        if self._closed.wait(wait) or self._sent >= len(self._pieces):
            raise StopIteration
        self._sent += 1
        return self._pieces[self._sent - 1]

    def close(self) -> None:
        self._closed.set()


class ScriptedBrain:
    """Offline stand-in for the server: fixed replies at a set pace. For testing the audio path only."""

    REPLIES = (
        "Oh, hello love. I'm right here, and I'm listening. Tell me what's on your mind.",
        "Okay, I hear you. That sounds like a lot for one day, so let's take it one small step at a time. "
        "First we'll look at what you already have, then we'll fix the one thing that is bothering you, "
        "and after that we can decide together what comes next.",
        "Of course, sweetheart. We can stop there. What would you like to do instead?",
    )

    def __init__(self, replies: tuple[str, ...] | list[str] | None = None, first_delay: float = 0.9,
                 tokens_per_second: float = 4.6) -> None:
        self.replies = tuple(replies or self.REPLIES)
        self.first_delay, self.delay = first_delay, 1.0 / tokens_per_second
        self.requests: list[list[dict]] = []

    def stream(self, messages: list[dict]) -> _ScriptedStream:
        self.requests.append(messages)
        text = self.replies[(len(self.requests) - 1) % len(self.replies)]
        return _ScriptedStream(text, self.first_delay, self.delay)
