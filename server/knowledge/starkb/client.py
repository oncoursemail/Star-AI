"""Thin client for the STAR Brain llama.cpp router (OpenAI-compatible).

Endpoints verified on the running build b11541 on 2026-10-10:
  POST /v1/embeddings  {"model": "star-embed", "input": [...]}   -> 768-d unit vectors
  POST /v1/rerank      {"model": "star-rerank", "query", "documents", "top_n"} -> results[{index, relevance_score}]
The API key is read from a file into memory and is never printed or logged.
"""
from __future__ import annotations

import os
from pathlib import Path
import time

try:
    import requests
except ImportError:   # only the server needs it; the unit tests on the PC run without
    requests = None

DEFAULT_URL = os.environ.get("STAR_BRAIN_URL", "http://127.0.0.1:8080")
DEFAULT_KEY_FILE = os.environ.get("STAR_BRAIN_KEY_FILE", "/opt/star/secrets/api_keys")
EMBED_MODEL = os.environ.get("STAR_EMBED_MODEL", "star-embed")
RERANK_MODEL = os.environ.get("STAR_RERANK_MODEL", "star-rerank")
QUERY_PREFIX = "task: search result | query: "   # EmbeddingGemma retrieval-query prompt


class Brain:
    def __init__(self, url: str = DEFAULT_URL, key_file: str = DEFAULT_KEY_FILE, timeout: float = 300.0,
                 retries: int = 3):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.retries = retries   # the service uses 1: a busy brain must not hold a search for long
        if requests is None:
            raise RuntimeError("the requests package is needed to talk to the STAR Brain")
        self.session = requests.Session()
        self.session.trust_env = False
        key = ""
        path = Path(key_file)
        if path.is_file():
            key = path.read_text(encoding="utf-8").splitlines()[0].strip()
        if key:
            self.session.headers["Authorization"] = "Bearer " + key

    def _post(self, path: str, payload: dict, retries: int | None = None) -> dict:
        last = None
        retries = retries or self.retries
        for attempt in range(retries):
            try:
                response = self.session.post(self.url + path, json=payload, timeout=self.timeout)
                if response.status_code == 200:
                    return response.json()
                last = RuntimeError(f"{path} returned HTTP {response.status_code}: {response.text[:200]}")
                if response.status_code in (400, 401, 404) or "too large" in response.text:
                    break  # not transient: the caller shortens the input instead of waiting
            except requests.RequestException as exc:
                last = RuntimeError(f"{path} failed: {type(exc).__name__}")
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
        raise last  # type: ignore[misc]

    def embed(self, texts: list[str]) -> tuple[list[list[float]], int]:
        """Return (vectors in input order, prompt tokens reported by the server)."""
        data = self._post("/v1/embeddings", {"model": EMBED_MODEL, "input": texts})
        rows = sorted(data["data"], key=lambda r: r["index"])
        return [r["embedding"] for r in rows], int((data.get("usage") or {}).get("prompt_tokens") or 0)

    def embed_query(self, query: str) -> list[float]:
        return self.embed([QUERY_PREFIX + query])[0][0]

    def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list[tuple[int, float]]:
        data = self._post("/v1/rerank", {"model": RERANK_MODEL, "query": query, "documents": documents,
                                        "top_n": top_n or len(documents)})
        return [(int(r["index"]), float(r["relevance_score"])) for r in data["results"]]
