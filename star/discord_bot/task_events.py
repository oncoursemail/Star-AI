"""Native task events consumed by the existing owner-only Night School timer.

The event directory must be operator-controlled, never writable by model tools.
Review manifests live in a SEPARATE operator-only directory. No lesson prose is
sent or promoted. Native success is reported as tested, not weight training.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
import re

from .lab_status import LabSettings, parse_receipt, read_capture
from .learning_sender import DeliveryLedger
from .native_evidence import encoded, read_bounded, trusted_path

_LOG = logging.getLogger(__name__)
MAX_EVENTS = 256


def load_event(path: Path, *, now):
    raw = read_bounded(path, 16000)
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {"version", "event_id", "receipt"}
            or type(value["version"]) is not int or value["version"] != 1):
        raise ValueError("Invalid native event schema")
    receipt = parse_receipt(encoded(value["receipt"]))
    event_id = sha256(encoded([receipt.source, receipt.job_id, receipt.build_sha256])).hexdigest()
    if (value["event_id"] != event_id or path.name != event_id + ".json" or not receipt.source
            or receipt.state != "completed" or receipt.checked != receipt.total or not receipt.total
            or receipt.evidence != ("native-blender" if receipt.engine == "blender" else "native-studio")):
        raise ValueError("Native event lacks checked evidence")
    if not receipt.fresh(now):
        raise ValueError("Native event is stale or in the future")
    return event_id, sha256(raw).hexdigest(), receipt


def review_for(directory: Path | None, event_id: str, digest: str) -> dict:
    if directory is None:
        return {}
    path = trusted_path(directory / (event_id + ".json"))
    if not path.exists():
        return {}
    value = json.loads(read_bounded(path, 2000))
    if (not isinstance(value, dict) or set(value) - {"event_id", "event_sha256", "approved_for_reuse", "image_sha256"}
            or value.get("event_id") != event_id or value.get("event_sha256") != digest
            or type(value.get("approved_for_reuse")) is not bool
            or (value.get("image_sha256") and not re.fullmatch(r"[0-9a-f]{64}", value["image_sha256"]))):
        raise ValueError("Invalid or mismatched independent review")
    return value


def format_event(receipt, review: dict) -> str:
    evidence = {"studio-lab": "Native Studio playtest and build checks",
                "playtest-learning": "Native Studio robot playtest",
                "studio-ui": "Native Studio UI geometry/device checks (not a gameplay test)",
                "blender-worker": "Native Blender camera render and GLB header check (Studio import untested)"}
    return (f"**STAR task checked: {receipt.task}**\n"
            f"Evidence: {evidence[receipt.source]}. {receipt.checked}/{receipt.total} checks passed.\n"
            f"Job: {receipt.job_id}; iteration {receipt.iteration}; recorded {receipt.stamp}.\n"
            f"Build SHA-256: {receipt.build_sha256}\n"
            "Owner review: " + ("approved for reuse." if review.get("approved_for_reuse") else "pending; lesson remains a candidate.")
            + "\nThis is a checked task result, not proof of a new general skill. "
            "No lesson was automatically promoted and no model weights were trained.")


async def check_task_events(config, send, *, now=None) -> dict:
    if not config.enabled or config.evidence_directory is None:
        return {"state": "disabled", "sent": False}
    now = now or datetime.now(timezone.utc)
    directory = trusted_path(config.evidence_directory)
    events = trusted_path(directory / "events")
    if not events.is_dir():
        return {"state": "no_task_evidence", "sent": False}
    records = []
    # Bound directory enumeration and work per tick; retention is an operator action.
    for path in events.iterdir():
        if path.suffix != ".json":
            continue
        if len(records) >= MAX_EVENTS:
            raise ValueError("Archive old native events before continuing")
        records.append(path)
    valid = []
    for path in records:
        try:
            valid.append(load_event(path, now=now))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            _LOG.warning("Native task event skipped (%s)", type(exc).__name__)
    valid.sort(key=lambda entry: (entry[2].stamp, entry[0]))
    config.state_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = DeliveryLedger(config.state_path, config.owner_id)
    try:
        for event_id, digest, receipt in valid:
            try:
                review = review_for(config.evidence_reviews, event_id, digest)
                if review.get("approved_for_reuse") is False:
                    continue  # rejected builds never become reusable because a checker passed
                visual = None
                if review.get("image_sha256"):
                    if review["image_sha256"] != receipt.capture_sha256:
                        raise ValueError("Review approves a different image")
                    visual = read_capture(LabSettings(True, directory / "latest.json"), receipt, now=now)
                body = format_event(receipt, review)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                _LOG.warning("Native task review skipped (%s)", type(exc).__name__)
                continue
            reason = ledger.reserve_task(event_id, now=now, cooldown_hours=config.cooldown_hours)
            if reason == "already_processed":
                continue
            if reason != "ready":
                return {"state": reason, "sent": False}
            try:
                await send(body, visual)
            except BaseException:
                ledger.mark_task(event_id, "unknown", now=now)
                raise
            ledger.mark_task(event_id, "sent", now=now)
            return {"state": "task_sent", "sent": True}
        return {"state": "no_new_task_evidence", "sent": False}
    finally:
        ledger.close()
