"""Read-only, operator-scoped Studio/Blender job evidence for STAR Discord.

This is NOT screen sharing and does not connect to Brain 2. A trusted producer
must atomically place an up-to-date JSON receipt and optionally a single
viewport/render image on the Discord bot host. Discord input never chooses a
file, network address or action. Owner-only slash commands read the receipt.

Screenshot SHA-256 binds the displayed file to its producer's receipt; it does
not independently prove the producer's claims, visual quality or a live run.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Mapping

MAX_RECEIPT_BYTES = 12_000
MAX_SCREENSHOT_BYTES = 6 * 1024 * 1024
MAX_ACTIVE_AGE_SECONDS = 900
MAX_COMPLETED_AGE_SECONDS = 7 * 86400
_JOB = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_IMAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\.(?:png|jpg|jpeg|webp)\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_ENGINES = {"roblox-studio", "blender"}
_STATES = {"queued", "running", "paused", "completed", "failed"}
_PHASES = {"planning", "building", "rendering", "playtesting", "inspecting",
           "verifying", "learning", "waiting"}
_EVIDENCE = {"native-studio", "native-blender", "static-only", "simulated", "not-tested"}
_CAPTURES = {"studio-viewport": "roblox-studio", "blender-render": "blender"}


@dataclass(frozen=True)
class LabSettings:
    enabled: bool = False
    report_path: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LabSettings":
        values = os.environ if env is None else env
        flag = str(values.get("STAR_DISCORD_LAB_STATUS", "0")).strip() or "0"
        if flag not in {"0", "1"}:
            raise ValueError("STAR_DISCORD_LAB_STATUS must be 0 or 1")
        if flag == "0":
            return cls()
        raw = str(values.get("STAR_DISCORD_LAB_REPORT", "")).strip()
        path = Path(raw)
        if (not raw or len(raw) > 2048 or not path.is_absolute()
                or path.suffix.lower() != ".json" or path.is_symlink()):
            raise ValueError("Lab status requires an operator-selected absolute JSON report path")
        return cls(True, path)


@dataclass(frozen=True)
class LabReceipt:
    job_id: str
    engine: str
    state: str
    phase: str
    task: str
    next_step: str
    checked: int
    total: int
    evidence: str
    updated: datetime
    capture_kind: str = ""
    capture_file: str = ""
    capture_sha256: str = ""
    build_sha256: str = ""
    iteration: int = 0
    source: str = ""
    camera: str = ""
    captured_at: str = ""

    @property
    def stamp(self) -> str:
        return self.updated.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def age_seconds(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Current time must have a timezone")
        return (now.astimezone(timezone.utc) - self.updated).total_seconds()

    def fresh(self, now: datetime | None = None) -> bool:
        age = self.age_seconds(now)
        maximum = (MAX_COMPLETED_AGE_SECONDS if self.state in {"completed", "failed"}
                   else MAX_ACTIVE_AGE_SECONDS)
        return 0 <= age <= maximum


def _line(value: object, *, limit: int) -> str:
    """A host-provided, one-line progress label, not Discord Markdown or commands."""
    if (not isinstance(value, str) or not 1 <= len(value) <= limit
            or value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Invalid Lab task label")
    if any(c in value for c in "@*_~<>|") or chr(96) in value:
        raise ValueError("Lab task labels may not contain mentions or Markdown")
    return value


def _strict_integer(value: object, upper: int) -> int:
    if type(value) is not int or not 0 <= value <= upper:
        raise ValueError("Invalid Lab task count")
    return value


def parse_receipt(data: bytes) -> LabReceipt:
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_RECEIPT_BYTES:
        raise ValueError("Missing or oversized Lab report")
    try:
        record = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid Lab report JSON") from exc
    base = {"version", "job_id", "engine", "state", "phase", "task", "next_step",
            "checked", "total", "evidence", "updated_at"}
    picture = {"capture_kind", "capture_file", "capture_sha256"}
    native = {"build_sha256", "iteration", "source", "camera", "captured_at"}
    if not isinstance(record, dict) or not base <= set(record) or set(record) - base - picture - native:
        raise ValueError("Lab report fields are missing or unsupported")
    if record["version"] not in {1, 2} or type(record["version"]) is not int:
        raise ValueError("Unknown Lab report version")
    if record["version"] == 1 and set(record) & native:
        raise ValueError("Native metadata requires report version 2")
    if record["version"] == 2:
        if not native <= set(record):
            raise ValueError("Native metadata is missing")
        if not isinstance(record["build_sha256"], str) or not _HASH.fullmatch(record["build_sha256"]):
            raise ValueError("Invalid native build hash")
        _strict_integer(record["iteration"], 10000)
        if record["source"] not in {"studio-lab", "studio-ui", "playtest-learning", "blender-worker"}:
            raise ValueError("Unknown native producer")
        if record["engine"] != ("blender" if record["source"] == "blender-worker" else "roblox-studio"):
            raise ValueError("Native producer engine mismatch")
    job = record["job_id"]
    if not isinstance(job, str) or not _JOB.fullmatch(job):
        raise ValueError("Invalid Lab job id")
    for field, allowed in (("engine", _ENGINES), ("state", _STATES),
                           ("phase", _PHASES), ("evidence", _EVIDENCE)):
        if not isinstance(record[field], str) or record[field] not in allowed:
            raise ValueError("Unsupported Lab " + field)
    checked = _strict_integer(record["checked"], 10000)
    total = _strict_integer(record["total"], 10000)
    if checked > total:
        raise ValueError("Lab checks exceed declared total")
    stamp = record["updated_at"]
    if not isinstance(stamp, str) or not _TIMESTAMP.fullmatch(stamp):
        raise ValueError("Lab report needs a UTC timestamp")
    try:
        updated = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Lab timestamp is invalid") from exc
    kind, name, digest = (record.get("capture_kind", ""), record.get("capture_file", ""),
                          record.get("capture_sha256", ""))
    if any((kind, name, digest)):
        if (not all((kind, name, digest)) or kind not in _CAPTURES
                or _CAPTURES[kind] != record["engine"] or not isinstance(name, str)
                or not _IMAGE.fullmatch(name) or not isinstance(digest, str)
                or not _HASH.fullmatch(digest)):
            raise ValueError("Lab screenshot needs a matching engine, file and SHA-256")
    camera, captured = record.get("camera", ""), record.get("captured_at", "")
    if record["version"] == 2:
        if kind:
            if not isinstance(camera, str) or not _JOB.fullmatch(camera):
                raise ValueError("Invalid native camera")
            if not isinstance(captured, str) or not _TIMESTAMP.fullmatch(captured):
                raise ValueError("Invalid native capture timestamp")
            if datetime.fromisoformat(captured.replace("Z", "+00:00")) > updated:
                raise ValueError("Capture is newer than its receipt")
        elif camera or captured:
            raise ValueError("Camera metadata requires a capture")
    return LabReceipt(job, record["engine"], record["state"], record["phase"],
                      _line(record["task"], limit=180),
                      _line(record["next_step"], limit=180), checked, total,
                      record["evidence"], updated, kind, name, digest,
                      record.get("build_sha256", ""), record.get("iteration", 0),
                      record.get("source", ""), camera, captured)


def classify_lab_question(text: str) -> str:
    """A tiny owner-DM intent gate; only questions explicitly naming the lab.

    Return a read-only action. Normal chat never sees the receipt, and no user
    phrase can specify a file path, a host, or an operation to execute.
    """
    if not isinstance(text, str) or not 1 <= len(text) <= 180:
        return ""
    question = re.sub(r"\s+", " ", text.strip().lower()).rstrip("?.!")
    if question in {"lab", "lab status", "studio status", "test studio status",
                    "brain 2 studio status", "blender status", "what is star working on",
                    "what are you working on in the test studio",
                    "what are you working on in studio",
                    "what are you doing in test studio",
                    "what are you working on in blender",
                    "what is star testing in studio"}:
        return "status"
    if question in {"lab screenshot", "studio screenshot", "blender render",
                    "send lab screenshot", "send studio screenshot",
                    "show lab screenshot", "show studio screenshot",
                    "show blender render", "send blender render",
                    "send screenshot from brain 2", "show screenshot from brain 2"}:
        return "screenshot"
    return ""


def read_receipt(config: LabSettings) -> LabReceipt:
    if not config.enabled or config.report_path is None:
        raise ValueError("Lab reports are disabled; configure them on the bot host first")
    path = config.report_path
    from .native_evidence import trusted_path
    trusted_path(path)
    if not path.is_absolute() or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Lab report path is not trusted")
    try:
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= MAX_RECEIPT_BYTES:
            raise ValueError("Lab report must be a small regular JSON file")
        with path.open("rb") as handle:
            data = handle.read(MAX_RECEIPT_BYTES + 1)
    except OSError as exc:
        raise ValueError("No trusted Lab report is available") from exc
    return parse_receipt(data)


def format_receipt(receipt: LabReceipt, *, now: datetime | None = None) -> str:
    """Show only what was recorded, never synthesize a current job from stale data."""
    fresh = receipt.fresh(now)
    state = receipt.state if fresh else "unknown (stale report)"
    lines = [
        "**STAR Studio/Blender Lab — producer-reported evidence**",
        f"**Job:** {receipt.job_id}",
        f"**Engine:** {receipt.engine}",
        f"**Status:** {state}",
        f"**Phase at report:** {receipt.phase}",
        f"**Task:** {receipt.task}",
        f"**Next recorded step:** {receipt.next_step}",
        f"**Checks recorded:** {receipt.checked}/{receipt.total} (not independently verified by Discord)",
        f"**Evidence class:** {receipt.evidence}",
        f"**Report timestamp:** {receipt.stamp}",
        "**Screenshot:** " + ("available with /star labshot" if receipt.capture_kind else "no approved capture"),
        "A file receipt does not prove the application is still running or a screenshot is visually correct.",
    ]
    if receipt.source:
        lines.extend([f"**Native producer:** {receipt.source}; iteration {receipt.iteration}",
                      f"**Build SHA-256:** {receipt.build_sha256}"])
        if receipt.capture_kind:
            lines.append(f"**Camera:** {receipt.camera}; captured {receipt.captured_at}")
    return "\n".join(lines)


def read_capture(config: LabSettings, receipt: LabReceipt | None = None,
                 *, now: datetime | None = None) -> tuple[str, bytes]:
    """Owner-requested one-shot export of a SHA-matched viewport or Blender render.

    Explicitly refuses arbitrary host desktop screenshots and user-supplied
    paths. Read and normalize anew to strip metadata before sending to Discord.
    The caller must check owner authorization BEFORE invoking this function.
    """
    receipt = receipt or read_receipt(config)
    if not receipt.capture_kind:
        raise ValueError("The Lab report has no approved viewport/render screenshot")
    if not receipt.fresh(now):
        raise ValueError("Lab screenshot is stale; request a fresh producer report")
    if receipt.captured_at:
        age = ((now or datetime.now(timezone.utc)) -
               datetime.fromisoformat(receipt.captured_at.replace("Z", "+00:00"))).total_seconds()
        if not 0 <= age <= MAX_ACTIVE_AGE_SECONDS:
            raise ValueError("Lab screenshot is stale; request a fresh producer report")
    if not config.report_path:
        raise ValueError("The trusted Lab report path is missing")
    path = config.report_path.parent / receipt.capture_file
    from .native_evidence import trusted_path
    trusted_path(path)
    if (path.is_symlink() or config.report_path.parent.is_symlink()
            or path.parent.resolve() != config.report_path.parent.resolve()):
        raise ValueError("Lab screenshot is not a trusted local file")
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_SCREENSHOT_BYTES:
            raise ValueError("Lab screenshot has an invalid file size")
        with path.open("rb") as handle:
            raw = handle.read(MAX_SCREENSHOT_BYTES + 1)
    except OSError as exc:
        raise ValueError("Lab screenshot is not currently available") from exc
    if sha256(raw).hexdigest() != receipt.capture_sha256:
        raise ValueError("Lab screenshot no longer matches the job receipt")
    from .dm_mode import prepare_discord_image
    suffix = Path(receipt.capture_file).suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp"}[suffix.lstrip(".")]
    clean = prepare_discord_image(receipt.capture_file, mime, len(raw), raw)
    return "star-lab.jpg", clean
