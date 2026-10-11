"""Run a golden-task suite through STAR's real task path and score the answers deterministically.

    python -m star.evals run --suite evals/roblox/golden-tasks-v2.json --out evals/results/x.json

Every automatable task is sent through `desktop_core.run_task` (the function the app itself calls)
with the STAR Server provider and an isolated, throw-away APPDATA, so nothing of the owner's real
profile is read or written. The answer is then scored by `star.eval_checks`: fenced Luau extracted,
compiled and type-checked by the knowledge service, unit tests run on the server in the standalone
Luau VM as user `star` under time and memory limits (never on this PC), required API names and
forbidden patterns, and a citation for documentation questions.

Operating rules built in:
  * quality-only: one request at a time, no lock taken;
  * before each task the runner waits while /opt/star/lock exists ("quiet please" for timing runs);
  * the result file is rewritten after every task and a re-run resumes where it stopped;
  * a task whose infrastructure failed is `error`, never `fail`;
  * nothing private is written: server addresses, the SSH target and the key are scrubbed.

Configuration is by environment variable or option, never from the repository:
  STAR_EVAL_SERVER   STAR Server URL, for example http://192.168.1.20:8080/v1
  STAR_EVAL_SSH      user@host that reaches the server's LXD host (sandbox and lock probe)
  STAR_EVAL_KEY_FILE file holding the server key (default ~/.star/server_api_key)
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
import time

from . import eval_checks as checks

SCHEMA = 1
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEY_FILE = Path.home() / ".star" / "server_api_key"
LOCK_POLL_SECONDS = 20
LOCK_LIMIT_SECONDS = 3 * 3600
_PRIVATE_IP = re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")
_KEEP_EVENTS = {"route_selected", "knowledge_finished", "luau_check_finished", "skill_packs"}


class RunAborted(RuntimeError):
    """The run stopped on purpose (lock held too long, interrupted). The checkpoint is saved."""


# --- suite -----------------------------------------------------------------------------------------

@dataclass
class Suite:
    path: Path
    sha256: str
    tasks: list[dict]
    prelude: str

    @property
    def directory(self) -> Path:
        return self.path.parent

    def runnable(self) -> list[dict]:
        return [t for t in self.tasks if t.get("run_mode") == "automated"]

    def test_body(self, task: dict) -> str:
        unit = (task.get("auto") or {}).get("unit_test")
        if not unit:
            return ""
        return (self.directory / unit["file"]).read_text(encoding="utf-8").replace("
", "
")


def load_suite(path: Path) -> Suite:
    from .evals import load_catalog
    path = Path(path)
    raw = path.read_bytes()
    load_catalog(path)                                     # the existing loader's rules (ids, modes, fields)
    tasks = json.loads(raw.decode("utf-8"))
    prelude_file = path.parent / "prelude.luau"
    prelude = prelude_file.read_text(encoding="utf-8").replace("
", "
") if prelude_file.is_file() else ""
    problems = validate_tasks(tasks, path.parent)
    if problems:
        raise ValueError("suite is invalid: " + "; ".join(problems[:8]))
    # Hash with normalised line endings: a Windows checkout (CRLF) and a git archive (LF) must agree.
    return Suite(path, hashlib.sha256(raw.replace(b"
", b"
")).hexdigest(), tasks, prelude)


def validate_tasks(tasks: list[dict], directory: Path) -> list[str]:
    problems = []
    for task in tasks:
        tid = task["id"]
        if not isinstance(task.get("prompt"), str) or not task["prompt"].strip():
            problems.append(f"{tid}: prompt missing")
        if task["run_mode"] == "studio" and not task.get("studio_check"):
            if not task.get("grader"):
                problems.append(f"{tid}: studio task needs studio_check or grader")
        if task["run_mode"] != "automated":
            continue
        auto = task.get("auto")
        if not isinstance(auto, dict):
            problems.append(f"{tid}: automated task needs an auto block")
            continue
        unit = auto.get("unit_test")
        if unit and not (directory / unit.get("file", "")).is_file():
            problems.append(f"{tid}: unit test file missing")
        for key in ("require", "require_any", "forbid"):
            for item in auto.get(key, []):
                try:
                    for pattern in (item["any"] if "any" in item else [item["re"]]):
                        re.compile(pattern)
                except (re.error, KeyError):
                    problems.append(f"{tid}: bad {key} pattern {item.get('id')}")
    return problems


# --- result file -----------------------------------------------------------------------------------

def scrub(value, secrets=()):
    """Recursively remove private addresses and any given secret strings from a JSON-able value."""
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "<redacted>")
        return _PRIVATE_IP.sub("<private-address>", value)
    if isinstance(value, list):
        return [scrub(v, secrets) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v, secrets) for k, v in value.items()}
    return value


def write_result(path: Path, result: dict, secrets=()) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(scrub(result, secrets), ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def summarize(tasks: dict) -> dict:
    counts = {"pass": 0, "fail": 0, "error": 0}
    seconds = []
    for record in tasks.values():
        if record["status"] in counts:
            counts[record["status"]] += 1
            seconds.append(record.get("seconds", 0.0))
    scored = counts["pass"] + counts["fail"]
    return {**counts, "scored": scored,
            "pass_rate": round(counts["pass"] / scored, 4) if scored else None,
            "median_seconds": round(statistics.median(seconds), 1) if seconds else None}


def git_state(root: Path = ROOT) -> dict:
    forced = os.environ.get("STAR_EVAL_APP_COMMIT", "").strip()
    try:
        head = forced or subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                                        text=True, timeout=15).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "star", "evals"],
                                    capture_output=True, text=True, timeout=15).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        head, dirty = forced, False
    return {"app_commit": head or "unknown", "app_dirty": dirty}


# --- pause while the server lock exists ---------------------------------------------------------------

def wait_for_lock(probe, *, sleep=time.sleep, now=time.monotonic, log=print,
                  poll: float = LOCK_POLL_SECONDS, limit: float = LOCK_LIMIT_SECONDS) -> float:
    """Block while the server lock exists; returns the seconds waited. `probe()` -> True/False/None."""
    started = now()
    announced = False
    while probe() is True:
        if not announced:
            log("server lock present: pausing")
            announced = True
        if now() - started > limit:
            raise RunAborted(f"the server lock was held for more than {int(limit)} s")
        sleep(poll)
    if announced:
        log("server lock released: resuming")
    return now() - started


# --- one run ---------------------------------------------------------------------------------------

@dataclass
class Asked:
    answer: str
    events: list
    seconds: float


def compact_events(events: list) -> list[dict]:
    keep = []
    for event in events:
        if isinstance(event, dict) and event.get("event") in _KEEP_EVENTS:
            keep.append({k: v for k, v in event.items() if isinstance(v, (str, int, float, bool, list))})
    return keep[:20]


def record_for(task: dict, asked: Asked | None, score: checks.TaskScore | None, error: str = "") -> dict:
    if error or score is None or asked is None:
        return {"status": "error", "passed": False, "reasons": [error or "no score"], "checks": [],
                "seconds": round(asked.seconds, 1) if asked else 0.0, "error": error}
    events = compact_events(asked.events)
    packs = next((e.get("names") for e in events if e.get("event") == "skill_packs"), [])
    return {
        "status": "pass" if score.passed else "fail", "passed": score.passed,
        "prompt_sha256": hashlib.sha256(task["prompt"].encode("utf-8")).hexdigest()[:16],
        "reasons": score.reasons, "checks": [c.record() for c in score.checks],
        "seconds": round(asked.seconds, 1), "timings": score.timings, "blocks": score.blocks,
        "answer_chars": len(asked.answer), "answer_sha256": hashlib.sha256(asked.answer.encode("utf-8")).hexdigest(),
        "packs": packs or [], "events": events, "answer": asked.answer,
    }


def run_suite(suite: Suite, *, out: Path, ask, scorer, lock_probe=None, run_info: dict, task_ids=None,
              resume: bool = True, retry_errors: bool = False, sleep=time.sleep, now=time.monotonic,
              log=print, secrets=()) -> dict:
    """Run the runnable tasks one at a time, checkpointing after each. Returns the result dict."""
    selected = [t for t in suite.runnable() if not task_ids or t["id"] in set(task_ids)]
    unknown = set(task_ids or []) - {t["id"] for t in suite.tasks}
    if unknown:
        raise ValueError("unknown task ids: " + ", ".join(sorted(unknown)))
    result = {
        "schema": SCHEMA,
        "suite": {"file": suite.path.name, "sha256": suite.sha256, "tasks_total": len(suite.tasks),
                  "automated": len(suite.runnable()), "selected": [t["id"] for t in selected]},
        "run": {**run_info, "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "complete": False, "tasks": {},
    }
    out = Path(out)
    if resume and out.is_file():
        previous = json.loads(out.read_text(encoding="utf-8"))
        same = (previous.get("suite", {}).get("sha256") == suite.sha256
                and previous.get("run", {}).get("fingerprint") == run_info.get("fingerprint"))
        if not same:
            raise ValueError(f"{out.name} exists from a different suite or configuration; use another --out or delete it")
        result["run"]["started_at"] = previous["run"].get("started_at", result["run"]["started_at"])
        result["tasks"] = {tid: rec for tid, rec in previous.get("tasks", {}).items()
                           if tid in {t["id"] for t in selected} and (rec["status"] != "error" or not retry_errors)}
    for task in suite.tasks:
        if task.get("run_mode") != "automated" and (not task_ids or task["id"] in task_ids):
            result["tasks"].setdefault(task["id"], {"status": "skipped", "reasons": ["needs Roblox Studio or a human"]})
    todo = [t for t in selected if t["id"] not in result["tasks"]]
    log(f"{len(selected)} tasks selected, {len(selected) - len(todo)} already done, {len(todo)} to run")
    waited = 0.0
    try:
        for number, task in enumerate(todo, 1):
            if lock_probe is not None:
                waited += wait_for_lock(lock_probe, sleep=sleep, now=now, log=log)
            asked, score, error = None, None, ""
            try:
                asked = ask(task)
                score = scorer(task, asked.answer)
            except checks.InfraError as exc:
                error = str(exc)
            except Exception as exc:                       # the task path failed: infrastructure, not a wrong answer
                error = f"{type(exc).__name__}: {str(exc)[:200]}"
            result["tasks"][task["id"]] = record_for(task, asked, score, error)
            record = result["tasks"][task["id"]]
            result["summary"] = summarize(result["tasks"])
            result["run"]["waited_for_lock_s"] = round(waited, 1)
            write_result(out, result, secrets)
            log(f"[{number}/{len(todo)}] {task['id']} {record['status']} {record.get('seconds', 0)}s"
                + (": " + "; ".join(record["reasons"])[:160] if record["status"] != "pass" else ""))
        result["complete"] = True
        result["run"]["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    except (KeyboardInterrupt, RunAborted) as exc:
        log("stopped: " + (str(exc) or type(exc).__name__) + " (progress is saved; run again to resume)")
        result["run"]["stopped"] = str(exc) or type(exc).__name__
    result["summary"] = summarize(result["tasks"])
    write_result(out, result, secrets)
    return result


# --- real wiring --------------------------------------------------------------------------------------

@contextmanager
def isolated_appdata():
    """Point APPDATA (and XDG_DATA_HOME) at a new empty folder, then restore. Never the real profile."""
    names = ("APPDATA", "XDG_DATA_HOME")
    saved = {n: os.environ.get(n) for n in names}
    with tempfile.TemporaryDirectory(prefix="star-eval-") as folder:
        for n in names:
            os.environ[n] = folder
        try:
            yield Path(folder)
        finally:
            for n, v in saved.items():
                if v is None:
                    os.environ.pop(n, None)
                else:
                    os.environ[n] = v


def read_key(path: Path) -> str:
    key = os.environ.get("STAR_SERVER_API_KEY", "").strip()
    if not key and Path(path).is_file():
        key = Path(path).read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit("No server key: set STAR_SERVER_API_KEY or pass --key-file")
    return key


def served_models(server: str, key: str) -> list[str]:
    """Model ids the server lists; empty when it cannot be asked."""
    try:
        import httpx
        reply = httpx.get(server.rstrip("/") + "/models", headers={"Authorization": "Bearer " + key},
                          timeout=10, trust_env=False)
        return sorted(str(m.get("id")) for m in reply.json().get("data", []) if isinstance(m, dict))[:20]
    except Exception:
        return []


def build_real(args, log=print):
    """(run_info, ask, scorer, lock_probe, secrets) wired to the real server."""
    from .desktop_core import Settings, run_task
    from .doc_knowledge import client_for
    from .eval_sandbox import ContainerSandbox

    key = read_key(Path(args.key_file))
    os.environ["STAR_SERVER_API_KEY"] = key
    os.environ["STAR_SKILL_PACKS"] = args.packs
    server = (args.server or os.environ.get("STAR_EVAL_SERVER", "")).rstrip("/")
    if not server:
        raise SystemExit("Give the STAR Server URL with --server or STAR_EVAL_SERVER")
    settings = Settings(provider="star_server", server_endpoint=server, model=args.model, project="STAR-eval")
    settings.validate()
    knowledge = client_for(settings)
    if knowledge is None:
        raise SystemExit("STAR Knowledge is not configured for this server address")
    ssh = args.ssh or os.environ.get("STAR_EVAL_SSH", "")
    sandbox = ContainerSandbox(ssh) if ssh else None

    def luau_check(code: str, strict: bool = False):
        last = None
        for attempt in range(3):
            try:
                return knowledge.luau_check(code, strict=strict)
            except OSError as exc:
                last = exc
                time.sleep(3 * (attempt + 1))
        raise last

    def ask(task: dict) -> Asked:
        events: list = []
        started = time.monotonic()
        with isolated_appdata():
            answer = run_task(Settings(**{**settings.__dict__, "project": "eval-" + task["id"].lower()}),
                              task["prompt"], mode=args.mode, on_event=events.append)
        return Asked(answer, events, time.monotonic() - started)

    suite = args._suite

    def scorer(task: dict, answer: str) -> checks.TaskScore:
        return checks.score_answer(task, answer, luau_check=luau_check, sandbox=sandbox,
                                   prelude=suite.prelude, test_body=suite.test_body(task))

    served = served_models(server, key)
    fingerprint_source = {"mode": args.mode, "model": args.model, "packs": args.packs, "provider": "star_server"}
    run_info = {
        **git_state(),
        "runner": "star.eval_runner/" + str(SCHEMA),
        "provider": "star_server", "model": args.model, "models_served": served, "mode": args.mode,
        "skill_packs": args.packs, "knowledge": "on", "temperature": 0,
        "server": "<private-address>", "sandbox": "lxc container as user star (prlimit + timeout)" if sandbox else "none",
        "platform": sys.platform,
        "fingerprint": hashlib.sha256(json.dumps(fingerprint_source, sort_keys=True).encode()).hexdigest()[:12],
    }
    probe = sandbox.lock_present if sandbox else None
    return run_info, ask, scorer, probe, [key, server, ssh, ssh.split("@")[-1] if ssh else ""]


def rescore(suite: Suite, result: dict, scorer, *, log=print) -> dict:
    """Score the recorded answers again with the suite's current checks. No model is called.

    Used when a grader was corrected after a run: the answers are the expensive part and do not change.
    Refuses a task whose prompt differs from the one that was asked.
    """
    by_id = {t["id"]: t for t in suite.tasks}
    changed = []
    for tid, record in result["tasks"].items():
        task = by_id.get(tid)
        if task is None or "answer" not in record:
            continue
        if record.get("prompt_sha256") != hashlib.sha256(task["prompt"].encode("utf-8")).hexdigest()[:16]:
            raise ValueError(f"{tid}: the prompt changed since the run; its answer cannot be re-scored")
        score = scorer(task, record["answer"])
        status = "pass" if score.passed else "fail"
        if status != record["status"]:
            changed.append(f"{tid}: {record['status']} -> {status}")
        record.update({"status": status, "passed": score.passed, "reasons": score.reasons,
                       "checks": [c.record() for c in score.checks], "timings": {**record.get("timings", {}), **score.timings}})
    result["suite"].update({"sha256": suite.sha256, "tasks_total": len(suite.tasks), "automated": len(suite.runnable())})
    result["run"]["rescored_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["summary"] = summarize(result["tasks"])
    log("rescored; changed: " + ("; ".join(changed) if changed else "none"))
    return result


# --- self-test: reference answers must pass, bad ones must fail ------------------------------------------

def selftest(suite: Suite, scorer, *, log=print) -> int:
    """Score the shipped reference answers (must pass) and bad answers (must fail). Returns failures."""
    failures = 0
    ref_dir = suite.directory / "reference"
    for task in suite.runnable():
        auto = task.get("auto") or {}
        for kind, expect in (("", True), (".bad", False)):
            file = ref_dir / f"{task['id']}{kind}.md"
            if not file.is_file():
                continue
            try:
                score = scorer(task, file.read_text(encoding="utf-8"))
            except checks.InfraError as exc:
                log(f"{task['id']}{kind or ' reference'}: infrastructure: {exc}")
                failures += 1
                continue
            good = score.passed == expect
            failures += 0 if good else 1
            log(f"{'ok  ' if good else 'FAIL'} {task['id']}{kind or ' reference'} "
                f"(expected {'pass' if expect else 'fail'}, got {'pass' if score.passed else 'fail'})"
                + ("" if good else ": " + "; ".join(score.reasons)[:200]))
        if auto.get("code", True) and not (ref_dir / f"{task['id']}.md").is_file():
            log(f"note {task['id']}: no reference answer")
        empty = scorer(task, "")
        if empty.passed:
            failures += 1
            log(f"FAIL {task['id']}: an empty answer passed")
    return failures


# --- command line -------------------------------------------------------------------------------------

def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--server", default="", help="STAR Server URL (or STAR_EVAL_SERVER)")
    parser.add_argument("--ssh", default="", help="user@host of the server's LXD host (or STAR_EVAL_SSH)")
    parser.add_argument("--key-file", default=str(DEFAULT_KEY_FILE))
    parser.add_argument("--model", default="star-fast")
    parser.add_argument("--mode", default="auto", choices=["auto", "fast", "agent"])
    parser.add_argument("--packs", default="off", help="skill packs: off, all, or a comma list of pack names")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.evals")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a suite and write a result file")
    add_common(run)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--tasks", default="", help="comma list of task ids (default: every automated task)")
    run.add_argument("--no-resume", action="store_true")
    run.add_argument("--retry-errors", action="store_true")
    st = sub.add_parser("selftest", help="check that reference answers pass and bad ones fail")
    add_common(st)
    rs = sub.add_parser("rescore", help="re-score the answers stored in a result file with the current checks")
    add_common(rs)
    rs.add_argument("--result", required=True, type=Path)
    rs.add_argument("--out", required=True, type=Path)
    ls = sub.add_parser("list", help="list the suite")
    ls.add_argument("--suite", required=True, type=Path)
    args = parser.parse_args(argv)

    suite = load_suite(args.suite)
    if args.command == "list":
        auto = suite.runnable()
        print(f"{len(suite.tasks)} tasks, {len(auto)} automated, {len(suite.tasks) - len(auto)} need Studio or a human")
        for t in suite.tasks:
            print(f"{t['id']:8} {t['run_mode']:9} {t['category']}")
        return 0
    args._suite = suite
    run_info, ask, scorer, probe, secrets = build_real(args)
    if args.command == "selftest":
        failures = selftest(suite, scorer)
        print("selftest:", "all good" if not failures else f"{failures} problem(s)")
        return 1 if failures else 0
    if args.command == "rescore":
        done = rescore(suite, json.loads(args.result.read_text(encoding="utf-8")), scorer)
        write_result(args.out, done, secrets)
        print(json.dumps(done["summary"]))
        return 0
    ids = [x for x in args.tasks.split(",") if x] or None
    result = run_suite(suite, out=args.out, ask=ask, scorer=scorer, lock_probe=probe, run_info=run_info,
                       task_ids=ids, resume=not args.no_resume, retry_errors=args.retry_errors, secrets=secrets)
    print(json.dumps(result["summary"]))
    return 0 if result.get("complete") else 2


if __name__ == "__main__":
    raise SystemExit(main())
