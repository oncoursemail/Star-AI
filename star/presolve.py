"""Overnight pre-solving: answer the owner's likely next requests while STAR Server is idle.

Opt-in (`presolve_enabled`, off by default). One night run:

1. predict: a short list of likely requests from the owner's own recent requests in this app's chat
   database (read-only), favouring topics that came up more than once and ones that name a file of the
   open project. It re-uses the owner's own wording; it does not invent new tasks.
2. solve: each one is asked on the owner's own STAR Server, only after the server had no request at all for
   10 minutes (night school's own politeness rule, see IdleWatch), at most MAX_PER_NIGHT answers: night school
   and timing runs always go first.
3. verify: the answer must contain Luau code that passes the same automatic checks STAR already uses
   (the STAR Knowledge compile + type check and the offline Roblox API-name check). Anything else is
   dropped: an answer that cannot be checked is never stored.
4. store: verified answers go to `presolved.sqlite3` in the app folder for KEEP_HOURS.

A new request that closely matches a stored one (same words, see MATCH_MIN) is answered at once with the
stored answer, clearly marked; sending the same request again right after gets a fresh answer.
Nothing leaves the owner's machines: the chats are read on this PC and the requests go to STAR Server.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Awaitable, Callable

from .worked_examples import terms

MAX_PER_NIGHT = 6
KEEP_HOURS = 36
MAX_ROWS = 30                # stored answers per project
MATCH_MIN = 0.8              # Jaccard similarity of the request words
MIN_TERMS = 4
RECENT_DAYS = 3
MAX_REQUEST_CHARS = 1500
MAX_ANSWER_CHARS = 12000
SYSTEM = ("You are STAR, a Roblox and Luau coding assistant. Answer the request with complete, working Luau "
          "code in a ```lua block and a short explanation.")
_CODE_INTENT = re.compile(r"(?i)\b(?:script|luau|lua|roblox|function|module|code|remote|tween|datastore|gui|"
                          r"npc|part|player|leaderstats|system|fix|write|make|build|create|implement)\b")
_FOLLOW_UP = re.compile(r"(?i)^\s*(?:and|but|also|now|then|ok|okay|yes|no|thanks|it|this|that|again|same|"
                        r"what about|how about|instead)\b")
_FRESH: dict[tuple[str, str], str] = {}     # (project, chat) -> request last answered from the store


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def similarity(a: str, b: str) -> float:
    x, y = set(terms(a)), set(terms(b))
    if len(x) < MIN_TERMS or len(y) < MIN_TERMS:
        return 1.0 if _norm(a) == _norm(b) and _norm(a) else 0.0
    return len(x & y) / len(x | y)


# ----------------------------------------------------------------------------------------------- predict
def recent_requests(home: Path, project: str, *, days: int = RECENT_DAYS, limit: int = 200,
                    now: datetime | None = None) -> list[str]:
    """The owner's own messages of the last `days` days in this project, newest first (read-only)."""
    path = Path(home) / "conversations.sqlite3"
    if not path.is_file():
        return []
    since = ((now or datetime.now(timezone.utc)) - timedelta(days=days)).isoformat()
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT body FROM messages WHERE project=? AND role='user' AND created>=? "
                          "ORDER BY id DESC LIMIT ?", (project, since, limit)).fetchall()
    return [str(row[0]) for row in rows]


def predict(requests: list[str], *, files: tuple[str, ...] = (), limit: int = MAX_PER_NIGHT) -> list[str]:
    """Likely next requests: standalone coding requests, recurring topics and project files first."""
    usable = []
    for text in requests:
        text = text.strip()
        if (not 20 <= len(text) <= MAX_REQUEST_CHARS or _FOLLOW_UP.match(text) or not _CODE_INTENT.search(text)
                or len(set(terms(text))) < MIN_TERMS):
            continue
        usable.append(text)
    stems = {Path(name).stem.lower() for name in files if Path(name).stem}
    scored = []
    for index, text in enumerate(usable):
        words = set(terms(text))
        recurring = sum(1 for other in usable if other is not text and similarity(text, other) >= 0.3)
        named = any(stem in text.lower() for stem in stems)
        recency = 1.0 / (1 + index)            # newest first
        scored.append((recurring + 2 * named + recency, index, text, words))
    chosen: list[str] = []
    for _, _, text, _ in sorted(scored, key=lambda item: (-item[0], item[1])):
        if any(similarity(text, kept) >= 0.6 for kept in chosen):
            continue
        chosen.append(text)
        if len(chosen) >= limit:
            break
    return chosen


# ----------------------------------------------------------------------------------------------- verify
def verify(answer: str, *, luau_check: Callable[[str], dict], api_check: Callable[[str], list]) -> tuple[bool, list[str]]:
    """(passed, evidence). Every Luau block must pass the compile + type check and the API-name check.
    No Luau code, a truncated answer or a check that could not run: not verified."""
    from .best_of_n import fenced, truncated
    if not answer or truncated(answer):
        return False, ["answer is empty or cut off"]
    blocks = fenced(answer, "luau")
    if not blocks:
        return False, ["no Luau code to check"]
    for code in blocks:
        try:
            result = luau_check(code)
        except Exception as exc:          # no verdict is not a pass
            return False, ["Luau check did not run: " + type(exc).__name__]
        if result.get("ran") is not True or result.get("ok") is not True:
            return False, [f"Luau check failed ({result.get('error_count', '?')} errors)"]
        findings = api_check(code)
        if findings:
            return False, [f"{len(findings)} unknown Roblox API names"]
    return True, [f"Luau compile + type check passed ({len(blocks)} block{'s' if len(blocks) > 1 else ''})",
                  "Roblox API names: none unknown (offline API dump)"]


# ----------------------------------------------------------------------------------------------- store
@dataclass(frozen=True)
class Solved:
    project: str
    request: str
    answer: str
    evidence: tuple[str, ...]
    created: str
    expires: str


class Store:
    def __init__(self, home: Path):
        self.path = Path(home) / "presolved.sqlite3"

    def _open(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("CREATE TABLE IF NOT EXISTS presolved (project TEXT NOT NULL, request TEXT NOT NULL, "
                   "answer TEXT NOT NULL, evidence TEXT NOT NULL, created TEXT NOT NULL, expires TEXT NOT NULL, "
                   "PRIMARY KEY (project, request))")
        return db

    def put(self, project: str, request: str, answer: str, evidence: list[str], *, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        with self._open() as db:
            db.execute("DELETE FROM presolved WHERE expires<=?", (now.isoformat(),))
            db.execute("INSERT OR REPLACE INTO presolved VALUES (?,?,?,?,?,?)",
                       (project, request[:MAX_REQUEST_CHARS], answer[:MAX_ANSWER_CHARS], json.dumps(evidence),
                        now.isoformat(), (now + timedelta(hours=KEEP_HOURS)).isoformat()))
            db.execute("DELETE FROM presolved WHERE project=? AND rowid NOT IN (SELECT rowid FROM presolved "
                       "WHERE project=? ORDER BY created DESC LIMIT ?)", (project, project, MAX_ROWS))

    def live(self, project: str, *, now: datetime | None = None) -> list[Solved]:
        if not self.path.is_file():
            return []
        stamp = (now or datetime.now(timezone.utc)).isoformat()
        with sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True) as db:
            rows = db.execute("SELECT project, request, answer, evidence, created, expires FROM presolved "
                              "WHERE project=? AND expires>? ORDER BY created DESC", (project, stamp)).fetchall()
        return [Solved(r[0], r[1], r[2], tuple(json.loads(r[3])), r[4], r[5]) for r in rows]

    def best(self, project: str, request: str, *, now: datetime | None = None) -> Solved | None:
        found = [(similarity(request, row.request), row) for row in self.live(project, now=now)]
        found = [item for item in found if item[0] >= MATCH_MIN]
        return max(found, key=lambda item: item[0])[1] if found else None


def take(home: Path, project: str, chat_id: str | None, request: str) -> Solved | None:
    """The stored answer for this request, or None. The same request sent again right after a stored
    answer in the same chat means "ask fresh": None, and the normal path answers it."""
    key = (project, chat_id or "")
    if _FRESH.pop(key, None) == _norm(request):
        return None
    try:
        found = Store(home).best(project, request)
    except (OSError, sqlite3.DatabaseError, ValueError):
        return None
    if found is not None:
        _FRESH[key] = _norm(request)
    return found


def marked(found: Solved) -> str:
    when = found.created[:16].replace("T", " ")
    return (f"**Pre-solved overnight** ({when} UTC) - checked automatically: {'; '.join(found.evidence)}. "
            "Not run in Roblox Studio. Send the same request again for a fresh answer.\n\n" + found.answer)


# ----------------------------------------------------------------------------------------------- night run
async def run_night(project: str, home: Path, *, ask: Callable[[str], Awaitable[str]], idle: Callable[[], Awaitable[bool]],
                    luau_check: Callable[[str], dict], api_check: Callable[[str], list],
                    files: tuple[str, ...] = (), max_answers: int = MAX_PER_NIGHT, wait_s: float = 60.0,
                    max_wait_s: float = 3 * 3600.0, sleep=asyncio.sleep, clock=time.monotonic) -> dict:
    """Predict, then solve and verify one request at a time while STAR Server is idle."""
    store = Store(home)
    known = [row.request for row in store.live(project)]
    todo = [text for text in predict(recent_requests(home, project), files=files, limit=max_answers)
            if not any(similarity(text, done) >= MATCH_MIN for done in known)]
    report = {"predicted": len(todo), "asked": 0, "verified": 0, "rejected": [], "stopped": ""}
    waited_since = clock()
    for text in todo:
        while not await idle():
            if clock() - waited_since > max_wait_s:
                report["stopped"] = "STAR Server was not idle"
                return report
            await sleep(wait_s)
        try:
            answer = await ask(text)
        except Exception as exc:
            report["rejected"].append("request failed: " + type(exc).__name__)
            continue
        report["asked"] += 1
        ok, evidence = verify(answer, luau_check=luau_check, api_check=api_check)
        if ok:
            store.put(project, text, answer, evidence)
            report["verified"] += 1
        else:
            report["rejected"].append(evidence[0])
        waited_since = clock()
    return report


QUIET_S = 600.0               # the brain must have had no request at all for this long (night school's own rule)


class IdleWatch:
    """STAR Server is idle when no slot of any loaded model is generating AND no slot started a new request
    (`id_task` changed) for `quiet_s` seconds. Night school and timing runs therefore always go first: this
    job only runs in their gaps. `fetch(path) -> parsed JSON` (async) talks to the server."""

    def __init__(self, fetch, *, quiet_s: float = QUIET_S, clock=time.monotonic):
        self.fetch, self.quiet_s, self.clock = fetch, quiet_s, clock
        self._tasks: dict | None = None
        self._changed = clock()

    async def __call__(self) -> bool:
        try:
            table, busy = {}, False
            listed = await self.fetch("/v1/models")
            for row in (listed.get("data") or []) if isinstance(listed, dict) else []:
                status = row.get("status") if isinstance(row, dict) else None
                if not isinstance(row, dict) or (isinstance(status, dict) and status.get("value") not in (None, "loaded")):
                    continue
                slots = await self.fetch("/slots?model=" + str(row.get("id")))
                for slot in slots if isinstance(slots, list) else []:
                    if isinstance(slot, dict):
                        busy = busy or bool(slot.get("is_processing"))
                        table[(row.get("id"), slot.get("id"))] = slot.get("id_task")
        except Exception:
            return False
        if busy or table != self._tasks:
            self._tasks, self._changed = table, self.clock()
        return not busy and self.clock() - self._changed >= self.quiet_s


def _server_idle(settings) -> IdleWatch:
    import httpx
    from .providers import connection_for

    async def fetch(path: str):
        endpoint, key = connection_for(settings)
        root = endpoint.rstrip("/").removesuffix("/v1")
        async with httpx.AsyncClient(trust_env=False, timeout=6.0) as http:
            reply = await http.get(root + path, headers={"Authorization": f"Bearer {key}"})
        return reply.json()
    return IdleWatch(fetch)


def run_once(settings, home: Path) -> dict:
    """One night run with the app's own STAR Server, STAR Knowledge and API dump."""
    from . import doc_knowledge
    from .providers import open_client
    from .roblox_api_checker import check_luau_api
    from .roblox_api_dataset import api_dump
    knowledge = doc_knowledge.client_for(settings)
    if knowledge is None:
        return {"stopped": "needs STAR Knowledge (its Luau check verifies every answer)"}
    dump = api_dump()
    client = open_client(settings, request_timeout=600)
    model = settings.roblox_model or settings.model

    async def ask(text: str) -> str:
        reply = await client.chat.completions.create(
            model=model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}])
        return reply.choices[0].message.content or ""

    files: tuple[str, ...] = ()
    if settings.workspace and Path(settings.workspace).is_dir():
        files = tuple(p.name for p in list(Path(settings.workspace).rglob("*.lua*"))[:500])
    return asyncio.run(run_night(settings.project, home, ask=ask, idle=_server_idle(settings),
                                 luau_check=knowledge.luau_check, api_check=lambda code: check_luau_api(code, dump),
                                 files=files))


NIGHT_HOURS = range(2, 7)        # local time the app's own nightly run may start


def due(home: Path, now: datetime) -> bool:
    """Inside the night window and not yet run tonight (marker file in the app folder)."""
    marker = Path(home) / "presolve-last-run.txt"
    try:
        last = marker.read_text(encoding="utf-8").strip()
    except OSError:
        last = ""
    return now.hour in NIGHT_HOURS and last != now.date().isoformat()


def start_nightly(settings_file: Path, home: Path, *, every_s: float = 900.0) -> None:
    """A daemon thread in the desktop app: every 15 minutes it reads the setting; with it on and inside the
    night window it does one run per night. Off (the default) it does nothing else."""
    import threading
    from .desktop_core import Settings

    def loop() -> None:
        while True:
            time.sleep(every_s)
            try:
                settings = Settings.load(settings_file)
                now = datetime.now()
                if settings.presolve_enabled is True and due(home, now):
                    (Path(home) / "presolve-last-run.txt").write_text(now.date().isoformat(), encoding="utf-8")
                    report = run_once(settings, home)
                    (Path(home) / "presolve-last-report.json").write_text(json.dumps(report), encoding="utf-8")
            except Exception:
                pass                 # a failed night is retried the next night; chat is never affected
    threading.Thread(target=loop, name="star-presolve", daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Overnight pre-solving (needs presolve_enabled in Settings)")
    parser.add_argument("command", choices=["run", "list"])
    parser.add_argument("--home", type=Path, default=None)
    args = parser.parse_args(argv)
    from .desktop_core import Settings, app_data
    home = args.home or app_data()
    settings = Settings.load(home / "settings.json")
    if args.command == "list":
        for row in Store(home).live(settings.project):
            print(row.created[:16], "|", row.request[:100].replace(chr(10), " "))
        return 0
    if settings.presolve_enabled is not True:
        print("Pre-solving is off (Settings > Knowledge & expert tools: Pre-solve likely requests overnight).")
        return 0
    print(json.dumps(run_once(settings, home)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
