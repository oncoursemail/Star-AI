"""Owner-bound visual approval for STAR design candidates.

An image existing, matching a baseline, or passing code tests is not a quality
approval. This module verifies local evidence and records exact-byte owner
reviews; it never calls an LLM, edits designs, publishes, or grants permissions.

Review writes must be exposed *only* by a trusted local owner-facing UI/CLI,
never as a tool for AI agents. Local SQLite is not a tamper-resistant signature.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

from PIL import Image, ImageChops, UnidentifiedImageError

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_MAX_IMAGE_BYTES = 12 * 1024 * 1024
_MAX_IMAGE_PIXELS = 16_000_000
_MAX_VIEWS = 12
_MAX_FEEDBACK = 2000


def _name(value: object, label: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError(f"{label} needs a short stable alphanumeric ID")
    return value


def _file(root: Path, relative: object, *, max_bytes: int) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise ValueError("Evidence path must be a relative workspace path")
    child = Path(relative)
    if child.is_absolute() or ".." in child.parts:
        raise ValueError("Evidence cannot reference files outside the workspace")
    resolved_root = root.resolve(strict=True)
    candidate = root / child
    if candidate.is_symlink():
        raise ValueError("Evidence cannot be a symlink")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
        raise ValueError("Evidence must be an ordinary workspace file")
    size = resolved.stat().st_size
    if not 0 < size <= max_bytes:
        raise ValueError("Evidence file is empty or too large")
    return resolved


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _image(path: Path, width: int, height: int) -> Image.Image:
    try:
        with Image.open(path) as screenshot:
            if screenshot.format != "PNG" or screenshot.size != (width, height):
                raise ValueError("Screenshot is not a PNG at the declared viewport size")
            if width * height > _MAX_IMAGE_PIXELS:
                raise ValueError("Screenshot exceeds the pixel budget")
            screenshot.load()
            return screenshot.convert("RGBA")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Screenshot could not be decoded") from exc


def compare_pixels(reference: Image.Image, actual: Image.Image, *, tolerance: int = 16) -> float:
    """Return changed-pixel ratio; baseline agreement is *not* aesthetic approval."""
    if reference.size != actual.size:
        raise ValueError("Screenshot and baseline have different dimensions")
    if type(tolerance) is not int or not 0 <= tolerance <= 255:
        raise ValueError("Pixel tolerance must be 0..255")
    channels = ImageChops.difference(reference.convert("RGBA"), actual.convert("RGBA")).split()
    highest = channels[0]
    for channel in channels[1:]:
        highest = ImageChops.lighter(highest, channel)
    changed = highest.point(lambda value: 255 if value > tolerance else 0).histogram()[255]
    return round(changed / (reference.width * reference.height), 8)


def capture_evidence(workspace: Path, manifest: dict) -> dict:
    """Verify screenshot files/dimensions, retain content hashes, never trust AI quality claims.

    Manifest: project, artifact, source, views: {name: {file,width,height}},
    optional baselines: {name: relative PNG path}. Baselines must be review-owned.
    """
    if not isinstance(manifest, dict):
        raise ValueError("Review manifest must be an object")
    project, artifact = _name(manifest.get("project"), "project"), _name(manifest.get("artifact"), "artifact")
    source = manifest.get("source")
    source_file = _file(workspace, source, max_bytes=_MAX_SOURCE_BYTES)
    source_paths = manifest.get("sources", [source])
    if (not isinstance(source_paths, list) or not 1 <= len(source_paths) <= 32
            or any(not isinstance(entry, str) for entry in source_paths)
            or len(source_paths) != len(set(source_paths)) or source not in source_paths):
        raise ValueError("Sources must be unique workspace files and include the primary source")
    source_hashes = {entry: _hash(_file(workspace, entry, max_bytes=_MAX_SOURCE_BYTES))
                     for entry in sorted(source_paths)}
    views, baselines = manifest.get("views"), manifest.get("baselines", {})
    if not isinstance(views, dict) or not 1 <= len(views) <= _MAX_VIEWS:
        raise ValueError("One to twelve captured views are required")
    if not isinstance(baselines, dict) or set(baselines) - set(views):
        raise ValueError("Baselines may only name captured views")

    captures: dict[str, dict] = {}
    for name, spec in sorted(views.items()):
        _name(name, "view")
        if not isinstance(spec, dict) or set(spec) != {"file", "width", "height"}:
            raise ValueError("Each view needs file, width and height")
        w, h = spec["width"], spec["height"]
        if type(w) is not int or type(h) is not int or not 200 <= w <= 8192 \
                or not 200 <= h <= 8192 or w * h > _MAX_IMAGE_PIXELS:
            raise ValueError("Viewport dimensions are out of bounds")
        path = _file(workspace, spec["file"], max_bytes=_MAX_IMAGE_BYTES)
        actual = _image(path, w, h)
        capture = {"sha256": _hash(path), "width": w, "height": h}
        if name in baselines:
            reference = _file(workspace, baselines[name], max_bytes=_MAX_IMAGE_BYTES)
            comparison = _image(reference, w, h)
            capture["baseline_sha256"] = _hash(reference)
            capture["pixel_change_ratio"] = compare_pixels(comparison, actual)
        captures[name] = capture

    source_sha = _hash(source_file)
    stable = {"project": project, "artifact": artifact, "source_sha256": source_sha,
              "sources_sha256": source_hashes, "captures": captures}
    evidence_key = hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**stable, "evidence_key": evidence_key,
            "warning": "File presence and pixel similarity never establish design quality or functionality."}


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.execute("""CREATE TABLE IF NOT EXISTS owner_creative_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project TEXT NOT NULL, artifact TEXT NOT NULL, evidence_key TEXT NOT NULL,
        decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
        feedback TEXT NOT NULL, reviewed_at TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS review_lookup ON owner_creative_reviews(project, artifact, id)")
    return conn


def record_owner_review(database: Path, evidence: dict, decision: str, feedback: str = "") -> None:
    """Trusted UI boundary only. Do not make this callable by generated model tools."""
    project, artifact = _name(evidence.get("project"), "project"), _name(evidence.get("artifact"), "artifact")
    key = evidence.get("evidence_key")
    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
        raise ValueError("Candidate evidence key is invalid")
    if decision not in {"approve", "reject"} or not isinstance(feedback, str) or len(feedback) > _MAX_FEEDBACK:
        raise ValueError("Review decision/feedback is invalid")
    if decision == "reject" and not feedback.strip():
        raise ValueError("A rejection needs actionable feedback")
    with _connect(database) as conn:
        conn.execute("INSERT INTO owner_creative_reviews(project,artifact,evidence_key,decision,feedback,reviewed_at) "
                     "VALUES (?,?,?,?,?,?)", (project, artifact, key, decision, feedback.strip(),
                                              datetime.now(timezone.utc).isoformat()))


def assess(database: Path, evidence: dict) -> dict:
    """A new source OR screenshot invalidates the old decision; rejection remains visible."""
    project, artifact, key = evidence["project"], evidence["artifact"], evidence["evidence_key"]
    with _connect(database) as conn:
        rows = conn.execute("SELECT evidence_key,decision,feedback,reviewed_at FROM owner_creative_reviews "
                            "WHERE project=? AND artifact=? ORDER BY id DESC LIMIT 100", (project, artifact)).fetchall()
    current = next((row for row in rows if row[0] == key), None)
    previous_rejection = next((row[2] for row in rows if row[1] == "reject"), None)
    if current:
        status = "owner_approved" if current[1] == "approve" else "owner_rejected"
    else:
        status = "awaiting_owner_review"
    return {"project": project, "artifact": artifact, "evidence_key": key, "status": status,
            "owner_approved": status == "owner_approved", "latest_owner_feedback": current[2] if current else "",
            "previous_rejection": previous_rejection or "",
            "reviewed_at": current[3] if current else None,
            "note": "This is an owner decision for exact evidence, not an automated proof of professional quality."}


def _default_db() -> Path:
    import os
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / ".local" / "state") / "STAR" / "creative_reviews.sqlite3"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect local visual evidence and request explicit owner review")
    parser.add_argument("action", choices=["inspect", "review"])
    parser.add_argument("manifest", type=Path, help="JSON evidence manifest in your workspace")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--database", type=Path, default=_default_db())
    parser.add_argument("--decision", choices=["approve", "reject"])
    parser.add_argument("--feedback", default="")
    args = parser.parse_args(argv)
    raw = _file(args.workspace, args.manifest.as_posix(), max_bytes=32_000)
    evidence = capture_evidence(args.workspace, json.loads(raw.read_text(encoding="utf-8")))
    if args.action == "review":
        if not args.decision or not sys.stdin.isatty():
            parser.error("Review requires a decision and a real interactive owner terminal")
        marker = f"{args.decision.upper()} {evidence['evidence_key'][:12]}"
        print("Inspect the ACTUAL screenshots before deciding. Automation cannot certify aesthetics.")
        if input(f"Type {marker} to record your decision: ").strip() != marker:
            parser.error("Review confirmation did not match")
        record_owner_review(args.database, evidence, args.decision, args.feedback)
    print(json.dumps({"evidence": evidence, "review": assess(args.database, evidence)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
