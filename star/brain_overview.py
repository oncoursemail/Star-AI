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


def planner_snapshot(settings_file: Path, *, client=None) -> dict:
    """Per-machine load, running jobs and the queue from STAR's resource planner, for the Brain page. Asked only when
    the page is open; the planner is the STAR Server's address on port 8098 (or ~/.star/planner_url /
    $STAR_PLANNER_URL). Not a STAR Server, no planner, or no answer: {"available": False} and nothing else."""
    from urllib.parse import urlsplit
    from .planner_client import PlannerClient, configured_url
    if client is None:
        settings = Settings.load(settings_file)
        if settings.provider != "star_server":
            return {"available": False, "reason": "not using a STAR Server"}
        url = configured_url()
        if not url:
            parts = urlsplit(str(settings.server_endpoint))
            if not parts.hostname:
                return {"available": False, "reason": "no STAR Server address"}
            host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
            url = f"http://{host}:8098"
        try:
            from .providers import connection_for
            _endpoint, key = connection_for(settings)
        except Exception:                       # no key: the planner answers 401 -> not available
            key = ""
        client = PlannerClient(url, key=key, timeout=2.0, down_for=0.0)
    data = client.status()
    if not isinstance(data, dict) or "machines" not in data:
        return {"available": False, "reason": "the resource planner did not answer"}
    machines = []
    for name, m in sorted((data.get("machines") or {}).items()):
        if not isinstance(m, dict):
            continue
        slots = {model: [bool(s.get("processing")) for s in rows if isinstance(s, dict)]
                 for model, rows in (m.get("models") or {}).items() if isinstance(rows, list)}
        machines.append({
            "name": str(name)[:20], "cpu": float(m.get("cpu_busy") or 0.0),
            "memFreeGiB": round(float(m.get("mem_available_mib") or 0) / 1024, 1),
            "memTotalGiB": round(float(m.get("mem_total_mib") or 0) / 1024, 1),
            "ageSeconds": float(m.get("age_s") or 0.0), "chatActive": bool(m.get("chat_active")),
            "ownerBusy": str(m.get("owner_busy") or "")[:80], "quietLock": str(m.get("lock_owner") or "")[:40],
            "gpu": (float(m["gpu_util"]) if m.get("gpu_util") is not None else None),
            "studios": len(m.get("studios") or []),
            "slots": {k: {"busy": sum(v), "total": len(v)} for k, v in slots.items()}})
    jobs = [{"jobClass": str(l.get("job_class", ""))[:20], "holder": str(l.get("holder", ""))[:40],
             "machine": str(l.get("machine", ""))[:20], "seconds": float(l.get("age_s") or 0)}
            for l in data.get("leases") or [] if isinstance(l, dict)]
    queue = [{"jobClass": str(w.get("job_class", ""))[:20], "holder": str(w.get("holder", ""))[:40],
              "machine": str(w.get("machine", ""))[:20]} for w in data.get("waiting") or [] if isinstance(w, dict)]
    return {"available": True, "machines": machines, "jobs": jobs, "queue": queue}
