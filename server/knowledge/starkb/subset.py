"""Deterministic ~2,000-chunk subset used for the first, quick embedding experiment.

Composition (in this order, until `size` is reached):
  1. every chunk of the focus-area guides (Roblox UI, Luau and scripting guides, luau.org docs);
  2. every chunk of the pages named as `expected` in the evaluation questions (an answer page that
     is not embedded can never be retrieved, so these must be present);
  3. a hash-ordered (pseudo-random but reproducible) sample of all remaining chunks as distractors.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from .quiet import wait_while_locked
from .store import connect

FOCUS = ("content/en-us/ui/", "content/en-us/luau/", "content/en-us/scripting/", "src/content/docs/")


def write_subset(db_path: Path, out: Path, size: int = 2000, questions: Path | None = None) -> dict:
    db = connect(db_path)
    rows = db.execute("SELECT c.id, c.text_sha, d.path FROM chunks c JOIN docs d ON d.id=c.doc_id ORDER BY c.id").fetchall()
    expected: set[str] = set()
    if questions and questions.is_file():
        for line in questions.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("//"):
                expected.update(json.loads(line)["expected"])
    chosen: dict[str, str] = {}
    counts = {"focus": 0, "expected_pages": 0, "distractors": 0}
    for _, sha, path in rows:
        wait_while_locked(log=lambda message: print(message, file=sys.stderr))
        if path.startswith(FOCUS) and sha not in chosen:
            chosen[sha] = "focus"
            counts["focus"] += 1
    for _, sha, path in rows:
        wait_while_locked(log=lambda message: print(message, file=sys.stderr))
        if path in expected and sha not in chosen:
            chosen[sha] = "expected"
            counts["expected_pages"] += 1
    rest = sorted((hashlib.sha256(("subset-v1:" + sha).encode()).hexdigest(), sha)
                  for _, sha, _ in rows if sha not in chosen)
    for _, sha in rest:
        wait_while_locked(log=lambda message: print(message, file=sys.stderr))
        if len(chosen) >= size:
            break
        if sha not in chosen:
            chosen[sha] = "distractor"
            counts["distractors"] += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(chosen) + "\n", encoding="utf-8")
    db.close()
    return {"size": len(chosen), **counts, "out": str(out)}
