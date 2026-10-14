"""Owner corrections become regression-test candidates (W8 of docs/research/self-improving-star-claude-v2.md).

When the owner marks an answer as wrong and says what was wrong (thumbs-down plus a correction in the app, or a
`wrong: ...` / `correction: ...` DM to the Discord bot right after STAR's answer), STAR keeps a CANDIDATE: the original
prompt, an excerpt of the failing answer, the owner's correction and a check stub. Nothing more happens by itself:

* a candidate is added to the separate CORRECTIONS SUITE only when the owner approves it (an explicit click);
* the corrections suite is a development-tier task file in STAR's own data folder
  (`<data>/corrections/corrections-<project>.json`, same JSON shape as the evaluation suites). It is never the blind
  holdout and never written into the repository's `evals/` folder: the writer refuses such paths;
* everything stays on this PC. Text that looks like a key or password is refused and private addresses are replaced
  before anything is stored;
* each candidate is also a failure-ledger record (`as_failures`), so practice can target the cause.

The check stub is honest about what it is: `forbid`/`require` patterns only when the correction names them plainly
("use X instead of Y", "don't use Y"), otherwise the task is a `human` task that the owner (or a later session) gives a
real check. `check_status` says "stub" until then.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

from .knowledge import _project
from .lessons import has_secret

STATUSES = ("candidate", "approved", "dismissed")
SOURCES = ("app", "discord")
MAX_PROMPT = 4000
MAX_ANSWER = 1500
MAX_CORRECTION = 1000
_PRIVATE = re.compile(r"\b(?:10|127|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2,3}\b")
_CODE = re.compile(r"```")
_IDENT = r"[A-Za-z_][\w.:]*(?:\(\))?"
_INSTEAD = re.compile(r"\buse\s+`?(" + _IDENT + r")`?\s+(?:instead\s+of|not)\s+`?(" + _IDENT + r")`?", re.I)
_DONT = re.compile(r"\b(?:don'?t|do\s+not|never|stop)\s+(?:use|using|call|calling)\s+`?(" + _IDENT + r")`?", re.I)
# Words in a correction that point at one failure-ledger cause (star/failure_ledger.py CAUSES).
_CAUSE_WORDS = (
    ("invented API name", r"doesn'?t exist|does not exist|not a real|no such (?:function|method|api|property)|made up|invented|deprecated"),
    ("answer cut off", r"cut off|incomplete|unfinished|truncated|stopped (?:half|mid)|didn'?t finish"),
    ("self-check error left unrepaired", r"syntax|doesn'?t compile|does not compile|type error|error:|errors? in (?:the )?output|red underline"),
    ("required feature missing", r"\bmissing\b|forgot|you left out|didn'?t (?:add|include|implement)|no \w+ (?:check|handling)"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scrub(text: str, limit: int, *, one_line: bool = False) -> str:
    value = str(text or "").replace("\r\n", "\n")
    if one_line:
        value = " ".join(value.split())
    return _PRIVATE.sub("<private-address>", value)[:limit]


def cause_for(correction: str) -> str:
    """The failure-ledger cause a correction most plainly describes; "wrong logic" otherwise."""
    for cause, words in _CAUSE_WORDS:
        if re.search(words, correction or "", re.I):
            return cause
    return "wrong logic"


def check_stub(correction: str, answer: str) -> dict:
    """Patterns the correction itself names. Empty when it names none (the task then needs a human-written check)."""
    require, forbid = [], []
    for good, bad in _INSTEAD.findall(correction or ""):
        require.append({"id": f"uses_{len(require) + 1}", "re": re.escape(good.rstrip("()")),
                        "why": f"the owner said to use {good}", "scope": "code"})
        forbid.append({"id": f"avoids_{len(forbid) + 1}", "re": r"(?<![\w.:])" + re.escape(bad.rstrip("()")) + r"\b",
                       "why": f"the owner said not to use {bad}", "scope": "code"})
    for bad in _DONT.findall(correction or ""):
        if not any(bad.rstrip("()") in f["why"] for f in forbid):
            forbid.append({"id": f"avoids_{len(forbid) + 1}", "re": r"(?<![\w.:])" + re.escape(bad.rstrip("()")) + r"\b",
                           "why": f"the owner said not to use {bad}", "scope": "code"})
    return {"require": require, "forbid": forbid}


class CorrectionStore:
    def __init__(self, home: Path):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.home / "corrections.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL, created TEXT NOT NULL, source TEXT NOT NULL,
            ref TEXT NOT NULL, prompt TEXT NOT NULL, answer TEXT NOT NULL, correction TEXT NOT NULL,
            cause TEXT NOT NULL, status TEXT NOT NULL, task_id TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL,
            UNIQUE(project, source, ref))""")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def record(self, *, project: str, source: str, ref: str, prompt: str, answer: str, correction: str) -> dict:
        """Keep one candidate per corrected answer (a second correction of the same answer updates the text)."""
        project = _project(project)
        if source not in SOURCES:
            raise ValueError("Unknown correction source")
        if not isinstance(ref, str) or not 1 <= len(ref) <= 120:
            raise ValueError("A correction needs the answer it is about")
        correction = scrub(correction, MAX_CORRECTION, one_line=True).strip()
        if len(correction) < 3:
            raise ValueError("Say what was wrong (at least a few words)")
        prompt = scrub(prompt, MAX_PROMPT).strip()
        if not prompt:
            raise ValueError("The corrected answer has no question to test again")
        answer = scrub(answer, MAX_ANSWER)
        if has_secret(correction) or has_secret(prompt) or has_secret(answer):
            raise ValueError("STAR did not keep this correction: it looks like it contains a key or password")
        stamp = _now()
        row = self.db.execute("SELECT id,status FROM corrections WHERE project=? AND source=? AND ref=?",
                              (project, source, ref)).fetchone()
        if row is not None:
            if row["status"] == "candidate":
                self.db.execute("UPDATE corrections SET correction=?,cause=?,updated=? WHERE id=?",
                                (correction, cause_for(correction), stamp, row["id"]))
                self.db.commit()
            return self.get(project, int(row["id"]))
        new_id = self.db.execute(
            "INSERT INTO corrections(project,created,source,ref,prompt,answer,correction,cause,status,updated) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (project, stamp, source, ref, prompt, answer, correction, cause_for(correction), "candidate",
             stamp)).lastrowid
        self.db.commit()
        return self.get(project, int(new_id))

    def withdraw(self, *, project: str, source: str, ref: str) -> int:
        """The owner took the thumbs-down back: an unreviewed candidate goes too."""
        done = self.db.execute("DELETE FROM corrections WHERE project=? AND source=? AND ref=? AND status='candidate'",
                               (_project(project), source, ref)).rowcount
        self.db.commit()
        return int(done)

    def get(self, project: str, item_id: int) -> dict:
        if isinstance(item_id, bool) or not isinstance(item_id, int) or item_id < 1:
            raise ValueError("Invalid correction identifier")
        row = self.db.execute("SELECT * FROM corrections WHERE id=? AND project=?",
                              (item_id, _project(project))).fetchone()
        if row is None:
            raise ValueError("Correction not found in this project")
        return self._public(row)

    def _public(self, row) -> dict:
        out = {k: row[k] for k in row.keys()}
        out["check"] = check_stub(row["correction"], row["answer"])
        return out

    def list(self, project: str, status: str | None = None) -> list[dict]:
        if status is not None and status not in STATUSES:
            raise ValueError("Unknown correction status")
        sql, values = "SELECT * FROM corrections WHERE project=?", [_project(project)]
        if status:
            sql += " AND status=?"
            values.append(status)
        return [self._public(r) for r in self.db.execute(sql + " ORDER BY id DESC LIMIT 200", values)]

    def counts(self, project: str) -> dict:
        found = {s: 0 for s in STATUSES}
        for status, total in self.db.execute("SELECT status,COUNT(*) FROM corrections WHERE project=? GROUP BY status",
                                             (_project(project),)):
            found[status] = int(total)
        return found

    def suite_path(self, project: str) -> Path:
        name = re.sub(r"[^A-Za-z0-9_.-]+", "-", _project(project)).strip("-") or "project"
        return self.home / "corrections" / f"corrections-{name}.json"

    def approve(self, project: str, item_id: int, *, human_approved: bool = False) -> dict:
        """The owner promotes a candidate into the corrections suite (never the holdout)."""
        if human_approved is not True:
            raise PermissionError("Only the owner can add a correction to the corrections suite")
        item = self.get(project, item_id)
        if item["status"] != "candidate":
            raise ValueError("Only a waiting correction can be approved")
        path = self.suite_path(project)
        tasks = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
        task_id = f"CR-{item_id:04d}"
        tasks = [t for t in tasks if t.get("id") != task_id] + [task_for(item, task_id)]
        write_suite(path, tasks)
        self.db.execute("UPDATE corrections SET status='approved',task_id=?,updated=? WHERE id=?",
                        (task_id, _now(), item_id))
        self.db.commit()
        return self.get(project, item_id)

    def dismiss(self, project: str, item_id: int, *, human_approved: bool = False) -> dict:
        if human_approved is not True:
            raise PermissionError("Only the owner can dismiss a correction")
        item = self.get(project, item_id)
        if item["status"] != "candidate":
            raise ValueError("Only a waiting correction can be dismissed")
        self.db.execute("UPDATE corrections SET status='dismissed',updated=? WHERE id=?", (_now(), item_id))
        self.db.commit()
        return self.get(project, item_id)

    def as_failures(self, project: str):
        """Every non-dismissed correction as a failure-ledger record, for targeted practice."""
        from .failure_ledger import Failure
        return [Failure("corrections", f"CR-{c['id']:04d}", "owner-correction", c["cause"],
                        "owner correction: " + c["correction"][:180])
                for c in self.list(project) if c["status"] != "dismissed"]


def task_for(item: dict, task_id: str) -> dict:
    """A corrections-suite task in the evaluation-suite shape. Patterns only when the owner named them."""
    check = item["check"]
    named = bool(check["require"] or check["forbid"])
    code = bool(_CODE.search(item["answer"])) or "luau" in item["prompt"].lower() or "script" in item["prompt"].lower()
    task = {
        "id": task_id, "category": "owner-correction", "difficulty": 2,
        "run_mode": "automated" if (named and code) else "human",
        "goal": "Owner correction: " + item["correction"][:120],
        "prompt": item["prompt"], "split": "corrections", "source": f"owner-correction:{item['source']}",
        "correction": item["correction"], "failing_answer_excerpt": item["answer"][:600],
        "targets_cause": item["cause"], "check_status": "stub" if not named else "patterns-from-correction",
        "required_evidence": ["answer.md"],
        "pass_conditions": ["The answer no longer has the problem the owner corrected: " + item["correction"][:200]],
    }
    if task["run_mode"] == "automated":
        task["auto"] = {"compile_mode": "lenient", "require": check["require"], "forbid": check["forbid"]}
        task["pass_conditions"].append("Luau static checking succeeds and the owner's named patterns hold")
    else:
        task["grader"] = {"type": "owner", "checks": ["The owner (or a later session) writes the real check"]}
    return task


def write_suite(path: Path, tasks: list[dict]) -> None:
    """Write the corrections suite. Never inside an `evals` folder, never a golden or holdout file."""
    path = Path(path)
    if any(part.casefold() == "evals" for part in path.parts) or re.search(r"golden|holdout", path.name, re.I):
        raise ValueError("The corrections suite is never written into the evaluation corpus or the holdout")
    from .evals import load_catalog
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    load_catalog(temporary)                     # the evaluation loader's own rules, before the file replaces anything
    temporary.replace(path)


# --- app bridge --------------------------------------------------------------------------------------------------

CORRECTION_ACTIONS = frozenset({"listCorrections", "reviewCorrection"})


def handle_action(home: Path, project: str, action: str, body: dict) -> dict:
    if action not in CORRECTION_ACTIONS:
        raise PermissionError("Action not permitted")
    if not isinstance(body, dict):
        raise ValueError("Invalid request")
    store = CorrectionStore(home)
    try:
        if action == "reviewCorrection":
            op = body.get("op")
            approved = body.get("approved") is True
            if op == "approve":
                store.approve(project, body.get("id"), human_approved=approved)
            elif op == "dismiss":
                store.dismiss(project, body.get("id"), human_approved=approved)
            else:
                raise ValueError("Unknown operation")
        return {"project": _project(project), "corrections": store.list(project), "counts": store.counts(project),
                "suite": store.suite_path(project).name}
    finally:
        store.close()
