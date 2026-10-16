"""Default-off native producers. No network, model prose, secrets or desktop capture.

The operator provisions the staging directory with writer access only for trusted
native jobs and read-only access for the bot. Hashes bind artifacts, not identity;
this filesystem permission boundary is required even on a shared host.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import stat
import sqlite3
import tempfile

from .lab_status import MAX_SCREENSHOT_BYTES, parse_receipt

_LOG = logging.getLogger(__name__)


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def trusted_path(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
                                     for p in (path, *path.parents)):
        raise ValueError("Evidence paths must be absolute and contain no links")
    return path


def read_bounded(path: Path, limit: int) -> bytes:
    trusted_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
        raise ValueError("Evidence must be a bounded regular file")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Evidence grew beyond the limit")
    return raw


def atomic_file(path: Path, data: bytes, *, immutable: bool = False) -> None:
    trusted_path(path)
    fd, name = tempfile.mkstemp(prefix=".stage-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # Private directories + group-readable files allow a distinct bot user.
        temporary.chmod(0o640)
        if immutable:
            try:
                os.link(temporary, path)  # atomic create-if-absent; never clobber an event
            except FileExistsError:
                if read_bounded(path, max(len(data), 1)) != data:
                    raise ValueError("Immutable evidence identity collision") from None
        else:
            os.replace(temporary, path)  # image first, manifest last
    finally:
        temporary.unlink(missing_ok=True)


def stage(directory: Path, receipt: dict, *, capture: bytes | None = None,
          event: bool = False) -> str | None:
    """Publish a validated native receipt; only independently checked jobs emit events."""
    trusted_path(directory)
    if not directory.is_dir():
        raise ValueError("Operator must provision the evidence directory")
    receipt = dict(receipt)
    if capture is not None:
        from .dm_mode import prepare_discord_image
        # Decode/signature-check and strip metadata before any bytes enter the shared directory.
        if not 0 < len(capture) <= MAX_SCREENSHOT_BYTES:
            raise ValueError("Native image is too large")
        suffix = "png" if capture.startswith(b"\x89PNG\r\n\x1a\n") else "jpg"
        clean = prepare_discord_image("capture." + suffix, "image/" + ("png" if suffix == "png" else "jpeg"),
                                     len(capture), capture)
        digest = sha256(clean).hexdigest()
        receipt.update(capture_file=digest + ".jpg", capture_sha256=digest)
        parse_receipt(encoded(receipt))
        atomic_file(directory / receipt["capture_file"], clean, immutable=True)
    parsed = parse_receipt(encoded(receipt))
    if not parsed.source:
        raise ValueError("Native receipt metadata is required")
    event_id = None
    if event:
        if (parsed.state != "completed" or parsed.checked != parsed.total or parsed.total == 0
                or parsed.evidence not in {"native-studio", "native-blender"}):
            raise ValueError("Only completed independently checked native tasks can notify")
        event_id = sha256(encoded([parsed.source, parsed.job_id, parsed.build_sha256])).hexdigest()
        events = trusted_path(directory / "events")
        events.mkdir(mode=0o750, exist_ok=True)
        atomic_file(events / (event_id + ".json"), encoded({"version": 1, "event_id": event_id,
                    "receipt": receipt}), immutable=True)
    # Serialize parallel Studio workers; an older completed job must not replace
    # a more recent status. Content-addressed images/events remain immutable.
    lock_path = trusted_path(directory / ".publisher.sqlite3")
    with sqlite3.connect(lock_path, timeout=10) as db:
        db.execute("BEGIN IMMEDIATE")
        latest = directory / "latest.json"
        current = parse_receipt(read_bounded(latest, 12000)) if latest.exists() else None
        if current is None or current.updated <= parsed.updated:
            atomic_file(latest, encoded(receipt))
    return event_id


def _receipt(source: str, run: str, task: str, build, iteration: int, finished: str = "") -> dict:
    # Native task names are identifiers, never free-form model instructions or exception text.
    from .lab_status import _JOB
    if not isinstance(task, str) or not _JOB.fullmatch(task):
        raise ValueError("Native task name must be an identifier")
    return {"version": 2, "job_id": run, "engine": "blender" if source == "blender-worker" else "roblox-studio",
            "state": "failed" if finished else "running", "phase": "verifying" if finished else "building",
            "task": task.replace("_", " "), "next_step": "Review native results" if finished else "Run native checks",
            "checked": 0, "total": 0, "evidence": "not-tested", "updated_at": finished or stamp(),
            "build_sha256": sha256(encoded(build)).hexdigest(), "iteration": iteration,
            "source": source, "camera": "", "captured_at": ""}


def publish_studio(directory: Path, report: dict, out: Path, *, playtest: bool = False,
                   phase: str = "building") -> str | None:
    """Adapt native checker facts, never a model's lesson or self-reported pass."""
    steps = report.get("iterations", [])
    last = steps[-1] if steps else {}
    source = "playtest-learning" if playtest else "studio-ui" if report.get("kind") == "ui" else "studio-lab"
    build = last.get("build_sha256") if playtest else last.get("build_spec", last.get("plan_hash", {}))
    receipt = _receipt(source, report["run"], report["game" if playtest else "spec"],
                       build, last.get("index", 0), report.get("finished", ""))
    if not report.get("finished"):
        receipt["phase"] = phase
    if playtest and isinstance(build, str) and len(build) == 64:
        receipt["build_sha256"] = build
    if source == "studio-lab" and last.get("verify", {}).get("build_hash"):
        receipt["build_sha256"] = last["verify"]["build_hash"]
    checked, total, valid = 0, 0, False
    shot, shot_folder = {}, out
    if playtest:
        robot, play, result = last.get("robot", {}), last.get("playtest") or {}, last.get("report", {})
        checks = robot.get("checks", [])
        total = len(checks)
        checked = sum(c.get("ok") is True for c in checks)
        valid = (bool(total) and checked == total and robot.get("started") is True
                 and robot.get("finished") is True and robot.get("ok") is True
                 and play.get("started") is True and play.get("stopped") is True
                 and last.get("apply", {}).get("ok") is True and result.get("passed") is True
                 and not result.get("failures") and not (play.get("errors") or {}).get("game"))
    elif source == "studio-ui":
        devices = last.get("devices", [])
        total = len(devices)
        checked = sum(bool(d.get("layout", {}).get("viewport")) and bool(d.get("layout", {}).get("rows"))
                      and not d.get("problems")
                      and d.get("screenshot", {}).get("ok") is True for d in devices)
        valid = bool(total) and checked == total and last.get("apply", {}).get("ok") is True
        if devices:
            shot = dict(devices[0].get("screenshot", {}), camera=devices[0].get("device", ""))
    else:
        probe, play = last.get("probe", {}), last.get("playtest", {})
        legs = probe.get("legs", [])
        total = len(legs)
        checked = sum(leg.get("reached") is True for leg in legs)
        valid = (bool(total) and checked == total and probe.get("ok") is True
                 and play.get("started") is True and play.get("stopped") is True
                 and not play.get("errors") and not last.get("defects")
                 and last.get("verify", {}).get("ok") is True and last.get("apply", {}).get("ok") is True)
        shots = [s for s in last.get("screenshots", []) if s.get("ok") is True]
        if shots:
            shot, shot_folder = shots[0], out / f"iteration-{last['index']}"
    receipt.update(checked=checked, total=total)
    if last.get("apply", {}).get("ok") is True:
        receipt["evidence"] = "native-studio"
    done = bool(report.get("finished"))
    if done and valid:
        receipt.update(state="completed", next_step="Review candidate; weights unchanged")
    capture = None
    if shot.get("ok") is True and shot.get("captured_at"):
        name = shot.get("file", "")
        if Path(name).name != name or not name:
            raise ValueError("Native capture must be a basename")
        capture = read_bounded(shot_folder / name, MAX_SCREENSHOT_BYTES)
        if sha256(capture).hexdigest() != shot.get("sha256"):
            raise ValueError("Native capture hash mismatch")
        receipt.update(capture_kind="studio-viewport", camera=shot["camera"], captured_at=shot["captured_at"])
    return stage(directory, receipt, capture=capture, event=done and valid)


def publish_blender(directory: Path, report: dict, out: Path, scene: dict) -> str | None:
    """Fixed first-party recipe worker only; GLB header and camera render checks, not Studio proof."""
    import struct
    if report.get("status") == "running":
        return stage(directory, _receipt("blender-worker", report["job_id"], scene["name"], scene, 1))
    if not report.get("preview_file"):
        return None
    glb = read_bounded(out / "scene.glb", 150_000_000)
    if len(glb) < 20 or struct.unpack("<4sII", glb[:12]) != (b"glTF", 2, len(glb)):
        raise ValueError("Invalid native GLB header")
    capture = read_bounded(out / "preview.png", MAX_SCREENSHOT_BYTES)
    receipt = _receipt("blender-worker", report["job_id"], scene["name"], scene, 1, stamp())
    receipt["build_sha256"] = sha256(glb).hexdigest()
    receipt.update(state="completed", phase="rendering", checked=2, total=2, evidence="native-blender",
                   capture_kind="blender-render", camera="STAR_ReviewCamera", captured_at=receipt["updated_at"],
                   next_step="Review camera render and GLB header; Studio import untested")
    return stage(directory, receipt, capture=capture, event=True)


def emit(source: str, report: dict, out: Path, *, scene: dict | None = None, phase: str = "building") -> None:
    """Native hook: disabled before any disk access; reporting failures never break a job."""
    if os.environ.get("STAR_DISCORD_EVIDENCE_PRODUCER") != "1":
        return
    try:
        directory = trusted_path(Path(os.environ.get("STAR_DISCORD_EVIDENCE_DIRECTORY", "")))
        if source == "blender-worker":
            publish_blender(directory, report, out, scene or {})
        else:
            publish_studio(directory, report, out, playtest=source == "playtest-learning", phase=phase)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        _LOG.warning("Native Discord evidence not staged (%s)", type(exc).__name__)
