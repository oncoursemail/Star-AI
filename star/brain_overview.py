"""Read-only snapshot for the Brain overview. Never probes provider endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from .desktop_core import Settings
from .intelligence import ALL_TOOLS, for_settings
from .lessons import learning_status
from .server_roles import role_report, _FLEETS


def brain_snapshot(settings_file: Path, home: Path) -> dict:
    settings = Settings.load(settings_file)
    intelligence = for_settings(settings, home).status()
    skills = intelligence["skills"]
    sources = [
        {"name": "Obsidian", "connected": intelligence["obsidian"]["enabled"]},
        {"name": "Graphify", "connected": intelligence["graphify"]["export_detected"]},
        {"name": "Roblox research", "connected": intelligence["roblox_research"]["enabled"]},
        {"name": "STAR Knowledge", "connected": intelligence.get("doc_knowledge", {}).get("enabled", False)},
    ]
    counts = learning_status(home, settings.project)
    evaluation = None
    # Explicitly named summary only; never inspect arbitrary files or expose raw evaluation traces.
    summary_path = home / "evals" / "latest_summary.json"
    if summary_path.is_file() and not summary_path.is_symlink():
        try:
            raw = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                evaluation = {key: raw[key] for key in ("score", "passed", "total", "created_at")
                              if key in raw and type(raw[key]) in (str, int, float, bool)}
        except (OSError, ValueError, UnicodeError):
            pass
    configured = [name for name in (
        settings.model, settings.fast_model, settings.reasoning_model,
        settings.roblox_model, settings.vision_model) if name]
    fleet = _FLEETS.get(str(settings.server_endpoint).rstrip("/"), {}) if settings.provider == "star_server" else {}
    offered = list(dict.fromkeys(fleet.get("ids", {}).values()))
    return {
        "provider": settings.provider,
        "models": offered,
        "configured_models": list(dict.fromkeys(configured)),
        "roles": role_report(settings),
        "knowledge": sources,
        "skills": {"enabled": skills["enabled"], "count": skills["count"],
                   "names": skills["names"]},
        "lessons": {"candidate": counts["candidate"], "accepted": counts["accepted"],
                    "retired": counts["superseded"] + counts["merged"] + counts["rejected"]},
        "tools": sorted(ALL_TOOLS),
        "evaluation": evaluation,
    }
