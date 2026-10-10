"""Nonsecret provenance of a Windows STAR executable or source checkout.

CI stamps the actual checkout SHA and workflow run into a JSON file before
PyInstaller packaging. This is diagnostic metadata, NOT a code signature.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_RUN = re.compile(r"^[0-9]{1,20}$")
_EVENT = frozenset({"push", "pull_request", "workflow_dispatch"})


def read_build_info(root: Path | None = None) -> dict:
    base = Path(root) if root is not None else Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])
    )
    source = base / "star" / "build-info.json"
    unknown = {
        "stamped": False, "source_commit": "", "head_commit": "",
        "run_url": "", "build_event": "local_source",
        "note": "Build metadata is informational, not a cryptographic signature.",
    }
    try:
        if not source.is_file() or source.stat().st_size > 2000:
            return unknown
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema") != 1:
            return unknown
        commit = raw.get("source_commit")
        head = raw.get("head_commit")
        event = raw.get("build_event")
        run_id = str(raw.get("run_id", ""))
        if (not isinstance(commit, str) or not _COMMIT.fullmatch(commit)
                or not isinstance(head, str) or not _COMMIT.fullmatch(head)
                or event not in _EVENT or not _RUN.fullmatch(run_id)):
            return unknown
        return {
            "stamped": True, "source_commit": commit,
            "head_commit": head, "build_event": event,
            "run_url": "https://github.com/oncoursemail/Star-AI/actions/runs/" + run_id,
            "note": "Build metadata is informational, not a cryptographic signature.",
        }
    except (OSError, ValueError, TypeError, UnicodeError):
        return unknown
