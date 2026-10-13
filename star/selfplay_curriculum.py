"""STAR self-play curriculum: deterministic obbies and trusted Studio Lab review.

The model may propose ideas, but never chooses a privileged Studio target or
runs arbitrary Luau here. A human-operated host explicitly authorizes a bounded
campaign. Each round uses the guarded Studio Lab when that separate feature is
installed. Dry-run plans and fake-runner tests are NOT Studio evidence.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
from typing import Callable

from . import map_plan

MAX_ROUNDS = 6
MAX_DAILY_CAMPAIGNS = 4
PROJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Curriculum:
    project: str
    seed: int = 1
    rounds: int = 3
    difficulty: int = 1
    max_iterations: int = 3
    play_seconds: int = 90

    def __post_init__(self):
        if type(self.project) is not str or not PROJECT.fullmatch(self.project):
            raise ValueError("Self-play project must be a valid scoped identifier")
        if type(self.seed) is not int or not 0 <= self.seed <= 2_147_483_647:
            raise ValueError("Self-play seed must be a bounded integer")
        if type(self.rounds) is not int or not 1 <= self.rounds <= MAX_ROUNDS:
            raise ValueError("Self-play has a bounded 1..6 rounds per campaign")
        if type(self.difficulty) is not int or not 1 <= self.difficulty <= 3:
            raise ValueError("Self-play difficulty must be 1..3")
        if type(self.max_iterations) is not int or not 1 <= self.max_iterations <= 5:
            raise ValueError("Studio Lab can fix at most five iterations")
        if type(self.play_seconds) is not int or not 15 <= self.play_seconds <= 150:
            raise ValueError("Self-play test time must be 15..150 seconds")


def build_obstacle_course(seed: int, *, difficulty: int = 1,
                          max_iterations: int = 3, play_seconds: int = 90) -> dict:
    """Produce an original small, versioned Studio Lab map, not executable source."""
    cfg = Curriculum(project="Curriculum", seed=seed, rounds=1, difficulty=difficulty,
                     max_iterations=max_iterations, play_seconds=play_seconds)
    rng = random.Random(cfg.seed)
    positions = [70, 83, 93, 103, 114]
    # Geometry stays within Studio Lab's known-safe scale; variation tests
    # navigation and clearance rather than filling memory with a giant scene.
    positions[1] += rng.choice((-1, 0, 1))
    positions[2] += rng.choice((-1, 0, 1))
    positions[3] += rng.choice((-1, 0, 1))
    zs = [0, 0, 0, 0, 0]
    if difficulty == 3:
        zs[2] = rng.choice((-1, 0, 1))
        zs[3] = rng.choice((-1, 0, 1))
    y2 = 8 if difficulty >= 2 else 6
    y3 = 8 if difficulty >= 2 else 6
    plan = {
        "version": 1, "mapName": "SelfPlayCourse", "style": "obby",
        "bounds": {"size": [82, 48, 32], "center": [92, 16, 0]},
        "parts": [
            {"name": "StartFloor", "position": [positions[0], 6, 0],
             "size": [12, 1, 12], "role": "floor", "material": "SmoothPlastic",
             "color": "#567DB5"},
            {"name": "P1", "position": [positions[1], 6, zs[1]],
             "size": [6, 1, 6], "role": "platform", "color": "#DFA246"},
            {"name": "P2", "position": [positions[2], y2, zs[2]],
             "size": [6, 1, 6], "role": "platform", "color": "#DFA246"},
            {"name": "P3", "position": [positions[3], y3, zs[3]],
             "size": [6, 1, 6], "role": "platform", "color": "#DFA246"},
            {"name": "Goal", "position": [positions[4], y3, 0],
             "size": [8, 1, 8], "role": "goal", "material": "Neon",
             "color": "#33B887"},
        ],
        "spawns": [{"name": "Start", "position": [positions[0], 7, 0],
                    "color": "#FFFFFF"}],
        "route": {"waypoints": ["Start", "StartFloor", "P1", "P2", "P3", "Goal"]},
    }
    if difficulty >= 2:
        # A beam in the intended route intentionally tests Studio's ability
        # to find the obstruction and repair it. The dry run is not a pass.
        plan["parts"].append({
            "name": "TrainingBanner", "position": [(positions[2] + positions[3]) / 2, 12, 0],
            "size": [0.4, 8, 7], "role": "decor", "material": "Fabric",
            "color": "#B44E44",
        })
    spec = {
        "name": "SelfPlayCourse", "kind": "map",
        "description": "Disposable, deterministic obby curriculum; not a published game.",
        "plan": plan, "maxIterations": cfg.max_iterations,
        "playSeconds": cfg.play_seconds,
        "lesson": {"topic": "safe obby navigation and jump clearance"},
    }
    check = map_plan.dry_run(plan, include_operations=False)
    if not check["ok"]:
        raise ValueError("Internal course generator failed map-plan preflight")
    return spec


def preview(cfg: Curriculum) -> dict:
    """Never connects to Studio, writes files, or calls a model."""
    plans = [build_obstacle_course(cfg.seed + index, difficulty=cfg.difficulty,
                                   max_iterations=cfg.max_iterations,
                                   play_seconds=cfg.play_seconds)
             for index in range(cfg.rounds)]
    return {"project": cfg.project, "rounds": cfg.rounds,
            "specs": [{"ordinal": i + 1, "name": item["name"],
                       "sha256": digest(item), "parts": len(item["plan"]["parts"]),
                       "play_seconds": item["playSeconds"],
                       "kind": "studio-lab-spec"} for i, item in enumerate(plans)],
            "studio_started": False, "code_executed": False,
            "notice": "Static map checks only. No Studio playtest or learning promotion occurred."}


class CampaignRefused(RuntimeError):
    pass


class CampaignLedger:
    """One unresolved campaign per test target; a timeout requires human review."""

    def __init__(self, file: Path):
        file = Path(file)
        if file.is_symlink() or file.parent.is_symlink():
            raise PermissionError("Self-play ledger cannot be symlinked")
        file.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(file), isolation_level=None, timeout=10)
        self.db.execute("""CREATE TABLE IF NOT EXISTS selfplay_campaigns (
            id INTEGER PRIMARY KEY, project TEXT NOT NULL, target TEXT NOT NULL,
            start_epoch INTEGER NOT NULL, status TEXT NOT NULL,
            rounds INTEGER NOT NULL, results_sha256 TEXT NOT NULL DEFAULT ''
        )""")

    def close(self):
        self.db.close()

    def reserve(self, cfg: Curriculum, target: tuple[int, int], *, now: int) -> int:
        if (type(now) is not int or now < 1
                or type(target) is not tuple or len(target) != 2
                or any(type(value) is not int or value <= 0 for value in target)):
            raise ValueError("Unknown time or Studio target identity")
        target_key = str(target[0]) + ":" + str(target[1])
        self.db.execute("BEGIN IMMEDIATE")
        try:
            pending = self.db.execute(
                "SELECT id FROM selfplay_campaigns WHERE target=? "
                "AND status IN ('running','unknown') LIMIT 1", (target_key,)).fetchone()
            if pending:
                raise CampaignRefused("An active/uncertain Studio campaign needs inspection before reuse")
            count = self.db.execute(
                "SELECT COUNT(*) FROM selfplay_campaigns WHERE target=? AND start_epoch>=? "
                "AND start_epoch<=?", (target_key, now - 86_400, now)).fetchone()[0]
            if count >= MAX_DAILY_CAMPAIGNS:
                raise CampaignRefused("Studio campaign daily budget exhausted")
            entry = self.db.execute(
                "INSERT INTO selfplay_campaigns(project,target,start_epoch,status,rounds) "
                "VALUES(?,?,?,'running',?)",
                (cfg.project, target_key, now, cfg.rounds))
            self.db.commit()
            return int(entry.lastrowid)
        except BaseException:
            self.db.rollback()
            raise

    def finish(self, ident: int, *, status: str, results: list[dict]):
        if status not in {"passed", "failed", "unknown"}:
            raise ValueError("Invalid campaign outcome")
        stamp = digest([{"seed": x.get("seed"), "status": x.get("status"),
                         "evidence": x.get("evidence")} for x in results])
        self.db.execute("BEGIN IMMEDIATE")
        try:
            updated = self.db.execute(
                "UPDATE selfplay_campaigns SET status=?,results_sha256=? "
                "WHERE id=? AND status='running'", (status, stamp, ident))
            if updated.rowcount != 1:
                raise CampaignRefused("Campaign already finished or was not reserved")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def acknowledge_unknown(self, ident: int, *, human_approved: bool):
        if human_approved is not True:
            raise PermissionError("Independent human review required for an uncertain Studio run")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            changed = self.db.execute(
                "UPDATE selfplay_campaigns SET status='acknowledged' "
                "WHERE id=? AND status='unknown'", (ident,))
            if changed.rowcount != 1:
                raise CampaignRefused("No matching uncertain campaign")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise


def studio_proof(report: object, target: tuple[int, int]) -> dict:
    """Classify actual host-supplied Studio Lab output, not a model assertion."""
    result = {"studio_verified": False, "visual_reviewed": False, "reason": "incomplete_lab_evidence"}
    if not isinstance(report, dict):
        return result
    place = report.get("place")
    steps = report.get("iterations")
    if (report.get("ok") is not True or report.get("passed") is not True
            or not isinstance(place, dict)
            or (place.get("universe_id"), place.get("place_id")) != target
            or not isinstance(steps, list) or not steps):
        return result
    last = steps[-1]
    if not isinstance(last, dict):
        return result
    verify = last.get("verify")
    playtest = last.get("playtest")
    probe = last.get("probe")
    if (last.get("passed") is not True or not isinstance(verify, dict)
            or verify.get("ok") is not True or not isinstance(playtest, dict)
            or playtest.get("ok") is not True
            or playtest.get("started") is not True or playtest.get("stopped") is not True
            or not isinstance(probe, dict) or probe.get("finished") is not True
            or probe.get("ok") is not True or playtest.get("errors")):
        return result
    report_hash = verify.get("build_hash")
    if not isinstance(report_hash, str) or not SHA256.fullmatch(report_hash):
        return result
    shots = last.get("screenshots")
    evidence = (isinstance(shots, list) and any(
        isinstance(shot, dict) and shot.get("ok") is True
        and isinstance(shot.get("sha256"), str) and SHA256.fullmatch(shot["sha256"])
        for shot in shots))
    return {"studio_verified": True, "visual_reviewed": False,
            "screenshot_evidence": bool(evidence), "build_sha256": report_hash,
            "reason": "real_engine_probe_and_readback"}


async def run_approved_campaign(cfg: Curriculum, home: Path, *, approved: bool = False,
                                lab_runner: Callable | None = None, clock: Callable | None = None) -> dict:
    """Bounded owner-only orchestration. Never publishes or edits another place.

    The real Studio Lab module is pending review separately. A host-injected
    runner is supported for offline tests, not exposed as a model tool.
    """
    if approved is not True:
        raise PermissionError("The operator must explicitly approve a disposable Studio campaign")
    try:
        from . import studio_lab
    except ImportError:
        if lab_runner is None:
            return {"status": "unavailable", "reason": "Studio Lab is not installed on this branch",
                    "studio_verified": False, "rounds": []}
        studio_lab = None
    if studio_lab is not None:
        target = studio_lab.TEST_PLACE
        validate = studio_lab.check_spec
        runner = lab_runner or studio_lab.run_lab
    else:
        # For fake offline tests only. The production caller never sees an
        # alternate target or gets to set the place from a language-model reply.
        target = (10770312935, 128074805767678)
        validate = lambda spec: (spec, [])
        runner = lab_runner

    home = Path(home).expanduser().resolve()
    if not home.is_dir() or (home / "selfplay").is_symlink():
        raise PermissionError("Choose a real local STAR private data directory")
    specs = [build_obstacle_course(cfg.seed + i, difficulty=cfg.difficulty,
                                   max_iterations=cfg.max_iterations,
                                   play_seconds=cfg.play_seconds)
             for i in range(cfg.rounds)]
    for raw in specs:
        checked, problems = validate(raw)
        if checked is None or problems:
            raise ValueError("Self-play spec was rejected by Studio Lab preflight")
    moment = int((clock or (lambda: datetime.now(timezone.utc).timestamp()))())
    ledger = CampaignLedger(home / "selfplay" / "campaigns.sqlite3")
    results = []
    try:
        cycle = ledger.reserve(cfg, target, now=moment)
        status = "failed"
        for ordinal, spec in enumerate(specs, 1):
            directory = home / "selfplay" / "runs" / f"campaign-{cycle}" / f"round-{ordinal}"
            # Only the real guarded StudioLab writes here. All runs reuse the
            # one managed draft name, preserving unrelated Roblox content.
            try:
                report = await runner(home, spec, directory, log=lambda *_: None)
                proof = studio_proof(report, target)
                entry = {"seed": cfg.seed + ordinal - 1, "ordinal": ordinal,
                         "status": "passed" if proof["studio_verified"] else "failed",
                         "evidence": proof, "spec_sha256": digest(spec)}
                results.append(entry)
                if not report.get("ok") and not report.get("iterations"):
                    status = "unknown"
                    break
            except BaseException:
                status = "unknown"
                results.append({"seed": cfg.seed + ordinal - 1,
                                "ordinal": ordinal, "status": "unknown",
                                "evidence": {"reason": "remote_result_unknown"}})
                break
        else:
            if results and all(x["status"] == "passed" for x in results):
                status = "passed"
        ledger.finish(cycle, status=status, results=results)
        return {"status": status, "campaign_id": cycle, "rounds": results,
                "studio_verified": status == "passed",
                "learned_candidates": sum(x["status"] == "passed" for x in results),
                "promoted_lessons": 0, "trained_weights": False,
                "note": "Learning records are only candidates until independent review."}
    finally:
        ledger.close()
