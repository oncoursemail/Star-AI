"""STAR invents its own game ideas, the robot playtests them, and the ideas that play best feed the next build list.

    STAR (star-fast) -> new game specs (simple: one mechanic; hard: several systems or a multi-stage puzzle), each
    with a fun hook, rules, a win condition and checks in the robot's vocabulary -> validated + deduplicated against
    every earlier spec and idea -> ledger (ideas.json) -> next night's build list (new ideas first, then the
    best-rated) -> playtest_learning plays them -> results back into the ledger as fun signals:
    reached the goal / passed, time to win, fail + retry counts, stuck points -> rating.

Off by default: needs STAR_PLAYTEST_LEARNING=1 and STAR_PLAYTEST_IDEAS=1. Ideas are candidates for STAR's own
practice; nothing is published.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from typing import Callable

from . import playtest_learning as pl

IDEAS_SWITCH = "STAR_PLAYTEST_IDEAS"
LEDGER = "ideas.json"
MAX_IDEAS = 200
SIMILAR = 0.6           # word-overlap (Jaccard) above which two ideas count as the same game
_WORD = re.compile(r"[a-z][a-z0-9]{2,}")
_STOP = frozenset("the and with that then from into each when your this for are player players game must have "
                  "part named once after before over under".split())

CHECK_GUIDE = """Checks the robot player can run (use only these; "target"/"name"/"stat"/"item" are names your game must use):
- {"do":"route","prefix":"Stage","target":"Goal","min":N}  jump Stage1..StageN in order, then reach Goal
- {"do":"reach","target":"X"}  walk/jump to the part X     - {"do":"touch","target":"X"}  step on X, then step off
- {"do":"blocked","target":"X"}  X must NOT be reachable yet (e.g. behind a closed door)
- {"do":"collect","name":"Coin","stat":"Coins","min":N,"each":V}  touch every part named Coin; each must vanish and add V
- {"do":"set_stat","stat":"S","value":V}  {"do":"mark","stat":"S"}  {"do":"expect_stat","stat":"S","equals"|"min"|"delta":V}
- {"do":"expect_item","item":"ToolName"} (add "absent":true to require NOT having it)   {"do":"expect_speed","min":V}
- {"do":"dies_on","target":"Lava"}  touching it kills   {"do":"respawn_near","target":"Checkpoint"}  respawn there
- {"do":"near","target":"Start","within":8}  the player was sent back to Start   {"do":"wait","seconds":S}
- {"do":"observe","value":"TimeLeft","status":"Status","seconds":40}  a countdown value reaches 0 and Status changes"""

IDEA_SYSTEM = f"""You are STAR, a Roblox game designer. Invent small games that are FUN to play and that a robot player can
test in a Roblox Studio playtest (server Scripts only, no saving/DataStores, no purchases, nothing outside the game).
{CHECK_GUIDE}
Answer ONLY with a JSON array. Each element:
{{"name": "CamelCaseName", "difficulty": "simple"|"hard", "hook": "one line: why it is fun",
  "brief": "2-3 sentences: what the player sees and does", "rules": ["..."], "win": "the win condition",
  "contract": ["exact names and behaviours the robot will check, one sentence each"], "checks": [ ...checks... ]}}
simple = one mechanic; hard = several systems together (e.g. rounds + coins + shop) or a multi-stage puzzle.
Every name used in "checks" must appear in "contract". 2 to 6 checks per game."""


def switched_on() -> bool:
    return pl.switched_on() and os.environ.get(IDEAS_SWITCH, "").strip() == "1"


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def similarity(a: dict, b: dict) -> float:
    wa = _words(" ".join([a.get("name", ""), a.get("hook", ""), a.get("brief", "")]))
    wb = _words(" ".join([b.get("name", ""), b.get("hook", ""), b.get("brief", "")]))
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def is_duplicate(idea: dict, known: list[dict]) -> str | None:
    for other in known:
        if idea["name"].lower() == str(other.get("name", "")).lower() or similarity(idea, other) >= SIMILAR:
            return str(other.get("name"))
    return None


def check_idea(raw) -> tuple[dict | None, list[str]]:
    """An idea = a playtest spec plus hook/rules/win/difficulty; the spec part must pass playtest_learning's check."""
    if not isinstance(raw, dict):
        return None, ["not an object"]
    problems = []
    difficulty = raw.get("difficulty")
    if difficulty not in ("simple", "hard"):
        problems.append("difficulty must be simple or hard")
    for key in ("hook", "win"):
        if not isinstance(raw.get(key), str) or not raw[key].strip() or len(raw[key]) > 300:
            problems.append(f"{key} must be a short sentence")
    rules = raw.get("rules")
    if not isinstance(rules, list) or not rules or not all(isinstance(r, str) for r in rules):
        problems.append("rules must be a list of sentences")
    spec = {"name": raw.get("name"), "kind": f"idea-{difficulty}", "brief": raw.get("brief"),
            "contract": raw.get("contract"), "checks": raw.get("checks"), "playSeconds": 180}
    if isinstance(spec["brief"], str) and isinstance(raw.get("win"), str):
        spec["brief"] = f"{spec['brief']} Win: {raw['win']}"
    checked, spec_problems = pl.check_spec(spec)
    problems += spec_problems
    if checked is not None:
        names = {str(step.get(k)) for step in checked["checks"] for k in ("target", "name", "item") if step.get(k)}
        text = " ".join(checked["contract"])
        missing = sorted(n for n in names if n not in text)
        if missing:
            problems.append("checks use names the contract does not mention: " + ", ".join(missing))
    if problems or checked is None:
        return None, problems
    return {"name": checked["name"], "difficulty": difficulty, "hook": raw["hook"].strip(), "rules": list(rules or [])[:8],
            "win": raw["win"].strip(), "spec": checked}, []


def parse_ideas(text: str) -> list:
    text = re.sub(r"(?s)<think>.*?</think>", "", text or "")
    start = text.find("[")
    if start < 0:
        return []
    try:
        found, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return []
    return found if isinstance(found, list) else []


# --------------------------------------------------------------------------- the ledger

def load_ledger(folder: Path) -> dict:
    try:
        data = json.loads((Path(folder) / LEDGER).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("ideas"), list) else {"ideas": []}
    except (OSError, ValueError):
        return {"ideas": []}


def save_ledger(folder: Path, ledger: dict) -> None:
    Path(folder).mkdir(parents=True, exist_ok=True)
    ledger["ideas"] = ledger["ideas"][-MAX_IDEAS:]
    tmp = Path(folder) / (LEDGER + ".tmp")
    tmp.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    tmp.replace(Path(folder) / LEDGER)


def invent(brain: Callable[[list[dict]], dict], folder: Path, known_specs: list[dict], *, count: int = 4,
           log=print) -> dict:
    """Ask STAR for `count` new ideas (half simple, half hard); keep the valid, new ones in the ledger."""
    ledger = load_ledger(folder)
    known = [s for s in known_specs] + [i["spec"] | {"hook": i.get("hook", "")} for i in ledger["ideas"]]
    hard = count // 2
    avoid = ", ".join(sorted({str(k.get("name")) for k in known}))[:1500]
    messages = [{"role": "system", "content": IDEA_SYSTEM},
                {"role": "user", "content": f"Invent {count} new games: {count - hard} simple and {hard} hard. "
                                            f"Do not repeat these existing games: {avoid}."}]
    answer = brain(messages)
    result = {"asked": count, "brain_seconds": answer.get("seconds"), "ok": bool(answer.get("ok")), "added": [],
              "refused": [], "duplicates": []}
    if not answer.get("ok"):
        result["error"] = answer.get("error")
        return result
    for raw in parse_ideas(answer.get("text", ""))[:count * 2]:
        idea, problems = check_idea(raw)
        name = raw.get("name") if isinstance(raw, dict) else None
        if idea is None:
            result["refused"].append({"name": name, "problems": problems[:4]})
            continue
        same = is_duplicate(idea["spec"] | {"hook": idea["hook"]}, known)
        if same:
            result["duplicates"].append({"name": idea["name"], "like": same})
            continue
        idea.update({"id": f"idea-{time.strftime('%Y%m%d', time.gmtime())}-{idea['name']}",
                     "created": pl._now(), "runs": [], "rating": None})
        ledger["ideas"].append(idea)
        known.append(idea["spec"] | {"hook": idea["hook"]})
        result["added"].append({"name": idea["name"], "difficulty": idea["difficulty"], "hook": idea["hook"]})
    save_ledger(folder, ledger)
    (Path(folder) / "last-answer.txt").write_text(answer.get("text", ""), encoding="utf-8")
    log(json.dumps({k: v for k, v in result.items() if k != "refused"} | {"refused": len(result["refused"])}))
    return result


# --------------------------------------------------------------------------- fun signals and rating

def signals(report: dict) -> dict:
    """What the robot measured that says something about play: passed, retries, time to win, stuck points."""
    its = report.get("iterations", [])
    last = its[-1] if its else {}
    checks = (last.get("robot") or {}).get("checks", [])
    win_seconds, stuck, jumps = 0.0, 0, 0
    for check in checks:
        facts = check.get("facts") or {}
        legs = facts.get("legs") or [facts]
        for leg in legs:
            if isinstance(leg, dict):
                win_seconds += float(leg.get("seconds") or 0)
                jumps += int(leg.get("jumps") or 0)
                s = leg.get("stuck")
                stuck += len(s) if isinstance(s, list) else int(s or 0)
    return {"passed": bool(report.get("passed")), "first_pass": bool(report.get("first_pass")),
            "builds": len(its), "failed_playtests": sum(1 for it in its if not (it.get("report") or {}).get("passed")),
            "checks": (last.get("report") or {}).get("checks", 0), "time_to_win": round(win_seconds, 1),
            "jumps": jumps, "stuck_points": stuck}


def rate(idea: dict) -> float | None:
    """Playable first (a game the robot cannot finish is not fun yet), then more to do, then a little challenge:
    1 for a passing build, +0.5 hard, +up to 0.5 for time to win (60 s = full), +0.1 per jump up to 0.3,
    -0.1 per stuck point (the robot getting stuck in a passing build points at awkward level design)."""
    runs = [r for r in idea.get("runs", []) if isinstance(r, dict)]
    if not runs:
        return None
    best = None
    for run in runs:
        s = run["signals"]
        score = 0.0
        if s["passed"]:
            score = (1.0 + (0.5 if idea.get("difficulty") == "hard" else 0.0) + min(s["time_to_win"], 60) / 120
                     + min(s["jumps"], 3) * 0.1 - 0.1 * s["stuck_points"])
        best = score if best is None else max(best, score)
    return round(best or 0.0, 3)


def record_results(folder: Path, reports: list[dict]) -> int:
    ledger = load_ledger(folder)
    by_name = {i["name"]: i for i in ledger["ideas"]}
    count = 0
    for report in reports:
        idea = by_name.get(report.get("game"))
        if idea is None or not report.get("iterations"):
            continue
        idea["runs"] = (idea.get("runs", []) + [{"run": report.get("run"), "finished": report.get("finished"),
                                                 "signals": signals(report)}])[-10:]
        idea["rating"] = rate(idea)
        count += 1
    save_ledger(folder, ledger)
    return count


def build_list(folder: Path, *, new: int = 3, best: int = 3) -> list[dict]:
    """Next night's idea specs: the newest never-played ideas (they need a rating), then the best-rated playable ones."""
    ideas = load_ledger(folder)["ideas"]
    unplayed = [i for i in ideas if not i.get("runs")][-new:]
    rated = sorted((i for i in ideas if (i.get("rating") or 0) >= 1.0), key=lambda i: -(i["rating"] or 0))[:best]
    return [i["spec"] for i in unplayed + rated]
