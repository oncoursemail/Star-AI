"""Consent-based, privacy-filtered STAR support/review package.

Collect only aggregate, local diagnostics that help reproduce app failures.
No chats, prompts, source documents, workspace paths, API keys, logs or
model weights are included. A screenshot is OPTIONAL and must be requested
explicitly by the user because it may reveal private on-screen content.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import json
import os
import platform
import re
import sqlite3
import tempfile
import zipfile

from PIL import Image

from .providers import credential_status
from .version import __version__
from .build_info import read_build_info

_ALLOWED_MODEL = re.compile(r"^[A-Za-z0-9._/:+-]{1,160}$")
_MAX_SCREENSHOT_BYTES = 8_000_000
_HELP = """STAR Intelligence — review bundle

This ZIP contains read-only diagnostic summaries useful for reviewing startup,
model connectivity, responsiveness, failures and tool configuration.

Files:
  manifest.json           Application/build and privacy information
  environment.json        General OS/Python/architecture facts (no username)
  configuration.json      Nonsecret model/provider/tool flags (no local paths)
  activity-summary.json   Aggregated local task durations and failures
  current-screen.png      OPTIONAL screenshot, only if you explicitly opted in

Excluded by design: conversations, private prompts, project names, API keys,
private directories, raw error logs, document content, checkpoints and models.
An optional screenshot MAY show sensitive chat messages or account details.

Check the contents yourself before uploading. To request an investigation,
attach this ZIP to your ChatGPT conversation with the error and steps to
reproduce. STAR does not upload or transmit this package automatically.
"""

def _read_activity(home: Path, *, days: int = 14) -> dict:
    """Summarize SQLite analytics, without exposing its free-text detail column."""
    summary = {
        "period_days": days,
        "events": {},
        "duration_ms": {"count": 0, "p50": None, "p95": None, "max": None},
        "first_visible_token_ms": {"count": 0, "p50": None, "p95": None},
        "failures_by_exception_type": {},
        "conversation_message_count": 0,
    }
    db = home / "analytics.sqlite3"
    if db.is_file():
        connection = None
        try:
            connection = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=2)
            cutoff = (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
            rows = connection.execute(
                "SELECT kind, elapsed_ms, detail FROM events WHERE recorded_at>=? "
                "ORDER BY recorded_at DESC LIMIT 3000", (cutoff,)
            ).fetchall()
            events = Counter()
            failures = Counter()
            times = []
            first_tokens = []
            for kind, elapsed_ms, detail in rows:
                if kind not in {"run_started","run_succeeded","run_failed","tool_completed","tool_rejected","first_token"}:
                    continue
                events[kind] += 1
                if kind == "run_succeeded" and type(elapsed_ms) is int and 0 <= elapsed_ms <= 86_400_000:
                    times.append(elapsed_ms)
                if kind == "first_token" and type(elapsed_ms) is int and 0 <= elapsed_ms <= 86_400_000:
                    first_tokens.append(elapsed_ms)
                if kind == "run_failed":
                    exc = str(detail or "").strip()
                    # Only a Python exception type is safe. No arbitrary message text.
                    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", exc):
                        failures[exc] += 1
                    else:
                        failures["Other"] += 1
            summary["events"] = dict(events)
            summary["failures_by_exception_type"] = dict(failures)
            if first_tokens:
                first_tokens.sort()
                summary["first_visible_token_ms"] = {
                    "count": len(first_tokens),
                    "p50": first_tokens[(len(first_tokens)-1)//2],
                    "p95": first_tokens[max(0, (95*len(first_tokens)+99)//100-1)],
                }
            if times:
                times.sort()
                summary["duration_ms"] = {
                    "count": len(times), "p50": times[(len(times)-1)//2],
                    "p95": times[max(0, (95*len(times)+99)//100 -1)], "max": times[-1],
                }
        except (sqlite3.Error, OSError):
            summary["analytics_unavailable"] = True
        finally:
            if connection is not None:
                connection.close()

    db = home / "conversations.sqlite3"
    if db.is_file():
        connection = None
        try:
            connection = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=2)
            summary["conversation_message_count"] = int(connection.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0])
        except (sqlite3.Error, OSError):
            summary["conversations_unavailable"] = True
        finally:
            if connection is not None:
                connection.close()
    return summary


def _validate_screenshot(data: bytes | None) -> bytes | None:
    if data is None:
        return None
    if not isinstance(data, bytes) or not 20 < len(data) <= _MAX_SCREENSHOT_BYTES:
        raise ValueError("Screenshot must be a PNG of 8 MB or less")
    with Image.open(BytesIO(data)) as image:
        if image.format != "PNG" or image.width * image.height > 24_000_000:
            raise ValueError("Unsupported screenshot dimensions or format")
        image.verify()
    # Screenshot bytes originate from the explicit Qt current-screen capture.
    return data


def review_snapshot(home: Path, settings, runtime_status: str) -> dict[str, dict]:
    """Fixed, nonsecret fields only; never dump settings.__dict__ or logs."""
    from .brain_setup import BrainInstall
    try:
        installed = BrainInstall.load(home / "brain.json") is not None
    except (OSError, ValueError, TypeError, KeyError):
        installed = False
    model = str(settings.model or "")
    model = model if _ALLOWED_MODEL.fullmatch(model) else "(hidden custom model)"
    return {
        "manifest.json": {
            "format": "star-review-v1",
            "star_version": __version__,
            "build": read_build_info(),
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "screenshot_included": False,  # explicitly updated for screenshot exports
            "privacy": "No prompts, chat text, paths, account names, raw logs or API keys",
            "independent_windows_gpu_test": False,
        },
        "environment.json": {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "configuration.json": {
            "inference_provider": settings.provider,
            "star_server_configured": bool(getattr(settings, "server_endpoint", "")),
            "model_id": model,
            "local_brain_installed": installed,
            "local_brain_running": runtime_status == "running",
            "max_model_calls": settings.max_calls,
            "context_char_budget": settings.context_chars,
            "studio_configured": bool(settings.studio_id),
            "studio_edits_enabled": bool(settings.studio_edit),
            "workspace_configured": bool(settings.workspace),
            "workspace_edits_enabled": bool(settings.workspace_edit),
            "obsidian_enabled": bool(getattr(settings, "obsidian_enabled", False)),
            "graphify_enabled": bool(getattr(settings, "graphify_enabled", False)),
            "skills_enabled": bool(getattr(settings, "skills_enabled", False)),
            "local_comfyui_workflow_configured": bool(settings.comfy_workflow),
            "provider_credentials_configured": credential_status(),
        },
        "activity-summary.json": _read_activity(home),
    }


def export_review_bundle(
    home: Path, settings, output: Path, *,
    runtime_status: str = "not started", screenshot_png: bytes | None = None,
) -> Path:
    """Write an inspected, small ZIP into a user-selected location, atomically."""
    home = Path(home)
    output = Path(output).expanduser()
    if output.suffix.lower() != ".zip" or not output.parent.is_dir():
        raise ValueError("Select a ZIP filename in an existing folder")
    if output.is_symlink() or output.is_dir():
        raise PermissionError("Review bundle target must not be a directory or symlink")
    image = _validate_screenshot(screenshot_png)
    files = review_snapshot(home, settings, runtime_status)
    files["manifest.json"]["screenshot_included"] = image is not None
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".zip", prefix=".star-review-", dir=output.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(temporary, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("README.txt", _HELP)
            for name, body in files.items():
                package.writestr(name, json.dumps(body, indent=2, sort_keys=True))
            if image is not None:
                package.writestr("current-screen.png", image)
        if temporary.stat().st_size > 10_000_000:
            raise ValueError("Review package is unexpectedly large")
        os.replace(temporary, output)
        return output
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
