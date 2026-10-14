"""Shared helpers for the GPU training pilot (W10): a local embedding "brain" and index re-embedding.

The knowledge service (server/knowledge/starkb) embeds through the STAR Brain (llama.cpp, model
`star-embed` = EmbeddingGemma-300M Q8_0). For an offline A/B on the PC we copy the service's SQLite
index, replace the `star-embed` vectors with vectors from a local sentence-transformers model, and run
the service's own evaluation code (starkb.evaluate.run_eval) with `starkb.search.Brain` swapped for
LocalBrain. Everything else (chunking, per-page cap, ranking) is the service's code, unchanged.

No key or server address is read or written here.
"""
from __future__ import annotations

from array import array
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
KNOWLEDGE = REPO / "server" / "knowledge"
if str(KNOWLEDGE) not in sys.path:
    sys.path.insert(0, str(KNOWLEDGE))

from starkb.client import QUERY_PREFIX  # noqa: E402  (EmbeddingGemma query prompt)
from starkb.store import embed_input  # noqa: E402  (EmbeddingGemma document prompt + size cap)

MAX_TOKENS = 512   # the running star-embed rejects inputs over 512 tokens; the service shortens them


def load_model(name_or_path: str, device: str = "cuda"):
    from sentence_transformers import SentenceTransformer
    import torch
    model = SentenceTransformer(name_or_path, device=device, model_kwargs={"torch_dtype": torch.float32})
    model.max_seq_length = MAX_TOKENS
    return model


def st_encoder(model, batch: int = 32):
    """texts -> unit vectors (numpy) with a sentence-transformers model; prompts are already in the text."""
    def encode(texts: list[str]):
        return model.encode(texts, batch_size=batch, normalize_embeddings=True, prompt="",
                            convert_to_numpy=True, show_progress_bar=False)
    return encode


def http_encoder(url: str, model_name: str = "star-embed"):
    """texts -> unit vectors from a llama.cpp server (/v1/embeddings), e.g. the exported GGUF on this PC.
    Inputs over the server's batch limit are shortened by 15 % until they fit, like starkb.embed does."""
    import json
    import urllib.error
    import urllib.request

    import numpy as np

    def post(texts):
        req = urllib.request.Request(url.rstrip("/") + "/v1/embeddings", headers={"Content-Type": "application/json"},
                                     data=json.dumps({"model": model_name, "input": texts}).encode())
        with urllib.request.urlopen(req, timeout=600) as resp:
            rows = sorted(json.loads(resp.read())["data"], key=lambda r: r["index"])
        return [r["embedding"] for r in rows]

    def encode(texts: list[str]):
        try:
            vecs = post(texts)
        except urllib.error.HTTPError:
            vecs = []
            for text in texts:
                for _ in range(10):
                    try:
                        vecs += post([text])
                        break
                    except urllib.error.HTTPError:
                        text = text[: int(len(text) * 0.85)]
        arr = np.asarray(vecs, dtype=np.float32)
        return arr / np.linalg.norm(arr, axis=1, keepdims=True)
    return encode


class LocalBrain:
    """Drop-in for starkb.client.Brain (embed / embed_query) backed by a local encoder function."""

    def __init__(self, encode):
        self.encode = encode

    def embed(self, texts: list[str]) -> tuple[list[list[float]], int]:
        return [v.tolist() for v in self.encode(texts)], 0

    def embed_query(self, query: str) -> list[float]:
        return self.embed([QUERY_PREFIX + query])[0][0]

    def rerank(self, *a, **k):  # not used by the vector-mode evaluation
        raise RuntimeError("rerank is not available offline")


def chunk_inputs(db: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = db.execute("""SELECT c.text_sha, d.title, c.heading, c.text FROM chunks c JOIN docs d ON d.id=c.doc_id
                         GROUP BY c.text_sha ORDER BY c.id""").fetchall()
    return [(r[0], embed_input(r[1], r[2], r[3])) for r in rows]


def reembed_copy(src_db: Path, dst_db: Path, encode, *, batch: int = 64, log=print) -> dict:
    """Copy the index and replace every `star-embed` vector with one from `model` (chunks only;
    generated-question vectors are dropped, the evaluated modes do not use them)."""
    dst_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_db, dst_db)
    db = sqlite3.connect(dst_db)
    db.execute("DELETE FROM embeddings")
    todo = chunk_inputs(db)
    started = time.monotonic()
    # longest first keeps padding low; order of insertion does not matter
    todo.sort(key=lambda t: -len(t[1]))
    for start in range(0, len(todo), batch):
        part = todo[start:start + batch]
        vecs = encode([t for _, t in part])
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        db.executemany("INSERT OR REPLACE INTO embeddings(text_sha,model,dim,vec,created_at) VALUES(?,?,?,?,?)",
                       [(sha, "star-embed", len(v), array("f", v.astype("float32")).tobytes(), stamp)
                        for (sha, _), v in zip(part, vecs)])
        if (start // batch) % 50 == 0:
            log(f"reembed: {start + len(part)}/{len(todo)} ({time.monotonic() - started:.0f}s)")
    db.commit()
    db.execute("VACUUM")
    db.close()
    return {"chunks": len(todo), "seconds": round(time.monotonic() - started, 1)}


def env_hf_home() -> None:
    os.environ.setdefault("HF_HOME", str(Path(os.environ.get("STAR_TRAIN_DIR", ".")) / "hf"))


RAM_FLOOR_GB = float(os.environ.get("STAR_TRAIN_RAM_FLOOR_GB", "6"))   # owner's PC: always keep 6 GB free


def free_ram_gb() -> float:
    """Free physical memory in GB (Windows: GlobalMemoryStatusEx; Linux: MemAvailable)."""
    if os.name == "nt":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.ullAvailPhys / 2**30
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 2**20
    return float("inf")


class TrainingGate:
    """GPU training on the owner's PC asks STAR's resource planner first (class "gpu-train"): it starts only while the
    owner is not gaming (no known game, no fullscreen window, no graphics load on the GPU), with enough free VRAM and
    with RAM above the floor plus the job's own need; every `renew_every` seconds a renewal can say "yield" (the owner
    started a game, RAM fell), and the run saves a checkpoint and waits to resume.
    The free-RAM floor is checked locally on every call, planner or not. Planner not configured or unreachable:
    exactly the old behaviour (RAM floor only)."""

    def __init__(self, job_id: str, *, log=print, renew_every: float = 30.0, client=None, memory_mib: int = 4096,
                 vram_mib: int = 2048, free_gb=None):
        import re
        self.job_id = re.sub(r"[^A-Za-z0-9_.-]", "-", job_id)[:60] or "train"
        self.log, self.renew_every = log, renew_every
        self.client = client if client is not None else _planner_client()
        self.extra = {"memory_mib": memory_mib, "vram_mib": vram_mib}
        self.grant = None
        self._renewed = 0.0
        self._free_gb = free_gb or free_ram_gb

    def start(self, stop=lambda: False, max_wait: float | None = None) -> bool:
        """Block until the planner admits the run (or there is no planner). False when the RAM floor or stop says no."""
        if self._free_gb() < RAM_FLOOR_GB:
            self.log(f"free RAM {self._free_gb():.1f} GB is below the {RAM_FLOOR_GB} GB floor; not starting")
            return False
        if self.client is None:
            return True
        self.grant = self.client.wait_for("gpu-train", "pc-training", self.job_id, stop=stop, max_wait=max_wait,
                                          log=self.log, **self.extra)
        if self.grant.action == "fallback":
            self.log(f"planner: {self.grant.reason}; using the RAM floor only")
        self._renewed = time.monotonic()
        return self.grant.go

    def stop_reason(self) -> str:
        """"" to go on, else why the run should save and stop now."""
        if self._free_gb() < RAM_FLOOR_GB:
            return f"free RAM below {RAM_FLOOR_GB} GB"
        if self.client is None or self.grant is None or not self.grant.planned:
            return ""
        if time.monotonic() - self._renewed < self.renew_every:
            return ""
        self._renewed = time.monotonic()
        grant = self.client.renew(self.grant)
        if grant.action in ("yield", "refuse"):
            self.grant = None
            return "planner: " + (grant.reason or grant.action)
        self.grant = grant
        return ""

    def close(self) -> None:
        if self.client is not None:
            self.client.release(self.grant)
        self.grant = None


def _planner_client():
    """The planner client with a live PC snapshot, or None when no planner is configured."""
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    try:
        from star.planner_client import PlannerClient
        from star.resource_probes import CpuMeter, pc_snapshot
    except ImportError:
        return None
    meter = CpuMeter()
    client = PlannerClient(timeout=3.0, snapshot=lambda: pc_snapshot(cpu=meter))
    return client if client.enabled else None
