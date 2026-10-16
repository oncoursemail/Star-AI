"""Open Roblox benchmark: Roblox/Luau tasks whose checks run in a real Roblox Studio playtest.

    benchmarks/roblox/tasks/<id>.json        prompt, level (easy|medium|hard), kind (module|script), playSeconds
    benchmarks/roblox/tasks/<id>.check.luau  check body (runs after benchmarks/roblox/harness.luau)
    benchmarks/roblox/tasks/<id>.reference.luau  a known-good answer (the pseudo-model "reference")

    1. answers  each model writes every task once through the brain's OpenAI-compatible endpoint; the answers are
                saved (<answers>/<model>/<id>.txt), so a slow model is asked once and Studio runs can be repeated.
    2. run      per task and model, STAR Test Place gets Workspace/MapDrafts/Bench/<id> = the answer (module tasks:
                a ModuleScript "Solution"; script tasks: server Scripts) + the check Script; one playtest; the check
                prints STAR_BENCH lines. A task passes when every check passed and the answer printed no error.
    3. score    results.json + results.md: per model tasks passed and a weighted score (easy 1, medium 2, hard 3).

The "reference" answers must pass every task: that is how the benchmark checks itself. Adding a task = three
files in the tasks folder (see benchmarks/roblox/README.md). Studio access goes through the Studio Lab's guarded
path (playtest_learning.studio_opener: STAR Test Place or a blank place only, one undo step per edit); the answers
are stored as script sources in Edit mode and only run inside the playtest.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re
import secrets
import statistics
import sys
import time

from . import playtest_learning as pl

BENCH_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "roblox"
TASKS_DIR = BENCH_DIR / "tasks"
MARK = "STAR_BENCH "
APPLY_MARK = "STAR_BENCH_APPLY "
FOLDER = "Bench"
CHECK_NAME = "StarBenchCheck"
LEVELS = {"easy": 1, "medium": 2, "hard": 3}
KINDS = ("module", "script")
REFERENCE = "reference"
DEFAULT_MODELS = ("star-fast", "star-deep", "star-quick")
_ID = re.compile(r"[A-Z][0-9]{2}-[a-z0-9-]{1,40}\Z")

SYSTEM = """You are STAR, writing Roblox Luau that an automated test runs in a Roblox Studio playtest (server side).
- Module tasks: answer with exactly one ```lua code block: the whole ModuleScript, ending with `return <module>`.
- Script tasks: answer with one ```lua code block: a server Script. `script.Parent` is a Folder in Workspace.
- Use only the Roblox engine API. Not allowed: HttpService, DataStoreService, MarketplaceService, TeleportService,
  InsertService, MessagingService, loadstring, require of asset ids, getfenv/setfenv.
- No explanations outside the code block."""


# --------------------------------------------------------------------------- tasks

def load_tasks(folder: Path = TASKS_DIR, only: set[str] | None = None) -> list[dict]:
    """Every task in the folder, sorted by id; raises ValueError on a malformed task."""
    tasks = []
    for path in sorted(Path(folder).glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        tid = task.get("id")
        if (not isinstance(tid, str) or not _ID.fullmatch(tid) or path.stem != tid
                or task.get("level") not in LEVELS or task.get("kind") not in KINDS
                or not isinstance(task.get("prompt"), str) or len(task["prompt"]) < 20
                or not isinstance(task.get("playSeconds"), (int, float)) or not 10 <= task["playSeconds"] <= 180):
            raise ValueError(f"malformed benchmark task {path.name}")
        check, reference = path.with_suffix(".check.luau"), path.with_suffix(".reference.luau")
        if not check.is_file() or not reference.is_file():
            raise ValueError(f"task {tid} needs {check.name} and {reference.name}")
        if only and tid not in only:
            continue
        tasks.append({**task, "check": check.read_text(encoding="utf-8"),
                      "reference": reference.read_text(encoding="utf-8")})
    return tasks


def messages(task: dict) -> list[dict]:
    kind = "Module task" if task["kind"] == "module" else "Script task"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"{kind}: {task['prompt']}"}]


def scripts_for(task: dict, answer: str) -> tuple[list[dict], list[str]]:
    """[{name, class, source}] to put in Studio, and static problems (no code, forbidden API)."""
    parsed = pl.parse_answer(answer)
    scripts, problems = parsed["scripts"], [p for p in parsed["problems"] if "more than" not in p]
    if task["kind"] == "module":
        return ([{"name": "Solution", "class": "ModuleScript", "source": scripts[0]["source"]}] if scripts else []), problems
    return [{"name": s["name"], "class": "Script", "source": s["source"]} for s in scripts[:pl.MAX_SCRIPTS]], problems


def check_source(task: dict) -> str:
    """Harness + the task's check body. An error outside check() (e.g. require of a broken Solution) becomes one
    failed "setup" check, so the done line is always printed."""
    harness = (BENCH_DIR / "harness.luau").read_text(encoding="utf-8")
    return (harness + "local bodyOk, bodyError = pcall(function()\n" + task["check"].rstrip() + "\nend)\n"
            'if not bodyOk then\n\tcheck("setup", function() error(bodyError, 0) end)\nend\n'
            'say("done", { checks = results })\n')


def apply_luau(task: dict, scripts: list[dict], run: str) -> str:
    """Edit-mode Luau: Workspace/MapDrafts/Bench holds one folder with the answer (stored, not run) and the check;
    every other script of the place is paused for the playtest (switched back on by remove_luau)."""
    if not re.fullmatch(r"[0-9a-f]{8,32}", run) or not _ID.fullmatch(task["id"]):
        raise ValueError("invalid run token or task id")
    s = pl._lua_string
    lines = [
        "-- STAR benchmark apply (scripts are stored, not run, in Edit mode)",
        "local function folder(parent, name)",
        "\tlocal found = parent:FindFirstChild(name)",
        "\tif found then return found end",
        '\tlocal made = Instance.new("Folder")',
        "\tmade.Name = name",
        "\tmade.Parent = parent",
        "\treturn made",
        "end",
        'local drafts = folder(workspace, "MapDrafts")',
        f"local bench = folder(drafts, {s(FOLDER)})",
        "bench:ClearAllChildren()",
        'local root = Instance.new("Folder")',
        f"root.Name = {s(task['id'])}",
    ]
    for script in scripts + [{"name": CHECK_NAME, "class": "Script", "source": check_source(task)}]:
        if script["class"] not in ("Script", "ModuleScript") or not pl._NAME.fullmatch(script["name"]):
            raise ValueError("invalid script")
        lines += ["do", f"\tlocal x = Instance.new({s(script['class'])})", f"\tx.Name = {s(script['name'])}",
                  f"\tx.Source = {s(script['source'])}"]
        if script["name"] == CHECK_NAME:
            lines.append(f'\tx:SetAttribute("StarBenchRun", {s(run)})')
        lines += ["\tx.Parent = root", "end"]
    lines += [
        pl.SERVICES_LUAU,
        "local silenced = 0",
        "for _, service in ipairs(SERVICES) do",
        "\tfor _, other in ipairs(service:GetDescendants()) do",
        '\t\tif other:IsA("BaseScript") and other.Enabled and not other:IsDescendantOf(bench) then',
        "\t\t\tother.Enabled = false",
        f"\t\t\tother:SetAttribute({s(pl.PAUSED)}, true)",
        "\t\t\tsilenced += 1",
        "\t\tend",
        "\tend",
        "end",
        "root.Parent = bench",
        f'return "{APPLY_MARK}" .. game:GetService("HttpService"):JSONEncode({{run = {s(run)}, '
        f"scripts = {len(scripts)}, silenced = silenced}})",
    ]
    return "\n".join(lines) + "\n"


def remove_luau() -> str:
    """Remove the benchmark folder and switch the paused scripts back on."""
    s = pl._lua_string
    return ("-- STAR benchmark cleanup\n" + pl.SERVICES_LUAU + "\nlocal drafts = workspace:FindFirstChild(\"MapDrafts\")\n"
            f"local bench = drafts and drafts:FindFirstChild({s(FOLDER)})\n"
            "local n = 0\nif bench then n = #bench:GetChildren(); bench:Destroy() end\n"
            "local restored = 0\nfor _, service in ipairs(SERVICES) do\n\tfor _, item in ipairs(service:GetDescendants()) do\n"
            f"\t\tif item:IsA(\"BaseScript\") and item:GetAttribute({s(pl.PAUSED)}) then\n"
            f"\t\t\titem:SetAttribute({s(pl.PAUSED)}, nil)\n\t\t\titem.Enabled = true\n\t\t\trestored += 1\n"
            "\t\tend\n\tend\nend\n"
            f'return "{APPLY_MARK}" .. game:GetService("HttpService"):JSONEncode({{removed = n, restored = restored}})\n')


def parse_console(console: str, run: str) -> dict:
    lines = []
    for raw in console.splitlines():
        at = raw.find(MARK)
        if at < 0:
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(raw[at + len(MARK):])
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("run") == run:
            lines.append(value)
    done = next((line for line in reversed(lines) if line.get("kind") == "done"), None)
    # Without a done line (a check hung until the play time ran out) the per-check lines still count.
    checks = (done or {}).get("checks") or [line for line in lines if line.get("kind") == "check"]
    return {"started": any(line.get("kind") == "start" for line in lines), "finished": done is not None,
            "checks": [c for c in checks if isinstance(c, dict)]}


_ERROR = re.compile(r"(?i)\b(error|attempt to|is not a valid member|expected|infinite yield|stack begin)\b")


def answer_errors(console: str, run: str, task_id: str) -> list[str]:
    """Error lines from the answer's own scripts (they name the task folder, not the check) after the check started."""
    lines = console.splitlines()
    first = next((i for i, line in enumerate(lines) if MARK in line and run in line), None)
    if first is None:
        return []
    path = f"{FOLDER}.{task_id}."
    return [line.strip()[:400] for line in lines[first:]
            if path in line and CHECK_NAME not in line and MARK not in line and _ERROR.search(line)][:10]


def judge(parsed: dict, errors: list[str], problems: list[str]) -> dict:
    checks = parsed["checks"]
    passed = (not problems and parsed["finished"] and bool(checks)
              and all(c.get("ok") is True for c in checks) and not errors)
    why = problems[:2] or ([] if parsed["started"] else ["the check never started"]) \
        or ([] if parsed["finished"] else ["the check did not finish in time"]) \
        or [f"{c.get('name')}: {c.get('why')}" for c in checks if not c.get("ok")][:3] or errors[:2]
    return {"passed": passed, "checks_passed": sum(1 for c in checks if c.get("ok") is True),
            "checks": len(checks), "why": [] if passed else why}


# --------------------------------------------------------------------------- answers (brain only)

def answer_path(answers: Path, model: str, task_id: str) -> Path:
    return Path(answers) / model / f"{task_id}.txt"


def load_endpoints(path: Path | None) -> dict[str, dict]:
    """Optional endpoints file {"<label>": {"url": ..., "model": ..., "key_file": ...}}: any OpenAI-compatible chat
    endpoint can be a contestant (e.g. a later "versus" run). Labels without an entry use STAR's brain
    (STAR_BRAIN_URL) with the label as the model name. The file names a key FILE, never a key."""
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(v, dict) and isinstance(v.get("url"), str)
                                             and isinstance(v.get("model"), str) for v in data.values()):
        raise ValueError("endpoints file: {label: {url, model, key_file?}}")
    return data


NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}


def brain_factory(endpoints: dict[str, dict], extra: dict | None = None):
    """extra: request fields for every contestant (e.g. NO_THINK); an endpoint's own "extra" wins."""
    def brain_for(label: str):
        spec = endpoints.get(label, {})
        return pl.Brain(url=spec.get("url"), key_file=spec.get("key_file"), model=spec.get("model") or label,
                        timeout=2400, max_tokens=6000, extra={**(extra or {}), **(spec.get("extra") or {})})
    return brain_for


def collect_answers(tasks: list[dict], models: list[str], answers: Path, *, brain_for=None, log=print) -> list[dict]:
    """Ask each contestant (label) every task it has no saved answer for; saves text + meta. Returns meta rows."""
    rows = []
    for model in models:
        if model == REFERENCE:
            continue
        brain = (brain_for or brain_factory({}))(model)
        for task in tasks:
            path = answer_path(answers, model, task["id"])
            meta_path = path.with_suffix(".json")
            if path.is_file() and meta_path.is_file():
                rows.append(json.loads(meta_path.read_text(encoding="utf-8")))
                continue
            got = brain(messages(task))
            path.parent.mkdir(parents=True, exist_ok=True)
            meta = {"model": model, "task": task["id"], "ok": got.get("ok"), "seconds": got.get("seconds"),
                    "tokens": got.get("tokens"), "error": got.get("error", "")}
            if got.get("ok"):           # a failed call is retried on the next run
                path.write_text(got.get("text", ""), encoding="utf-8")
                meta_path.write_text(json.dumps(meta), encoding="utf-8")
            rows.append(meta)
            log(json.dumps(meta))
    return rows


def answer_for(task: dict, model: str, answers: Path) -> tuple[str | None, dict]:
    if model == REFERENCE:
        return "```lua\n" + task["reference"] + "```\n", {}
    path = answer_path(answers, model, task["id"])
    if not path.is_file():
        return None, {}
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    return path.read_text(encoding="utf-8"), meta


def api_findings(scripts: list[dict]) -> list[str]:
    """API names the offline checker doubts (information only; the playtest decides)."""
    try:
        from .roblox_api_checker import check_luau_api
        from .roblox_api_dataset import api_dump
        dump = api_dump()
    except Exception:
        return []
    return [f"{f.class_name or ''}.{f.name}" for s in scripts for f in check_luau_api(s["source"], dump)][:10]


# --------------------------------------------------------------------------- Studio side

class BenchRun:
    """Runs answers through apply -> playtest -> judge on an open GuardedStudio."""

    def __init__(self, guarded, *, log=print, sleep=asyncio.sleep, poll: float = 2.0, settle: float = 30.0,
                 retry_wait: float = 8.0):
        self.guarded, self.log, self.sleep, self.poll, self.settle = guarded, log, sleep, poll, settle
        self.retry_wait = retry_wait

    async def _call(self, name: str, **arguments):
        return await self.guarded.call_tool(name, {"studio_id": self.guarded.studio_id, **arguments})

    async def _luau(self, code: str) -> tuple[bool, str]:
        from .studio_loop import EDIT_MARK, _marked_json, result_failed, result_text
        result = await self._call("execute_luau", datamodel_type="Edit", code=code)
        entry = self.guarded.journal.entries[-1] if self.guarded.journal.entries else {}
        receipt = _marked_json(result_text(result), EDIT_MARK) or {}
        got = receipt.get("result")
        return (not result_failed(result) and entry.get("ok") is True), (got if isinstance(got, str) else result_text(result))

    async def remove(self) -> dict:
        ok, text = await self._luau(remove_luau())
        return {"ok": ok, **(pl.marked_json(text, APPLY_MARK) or {})}

    async def one(self, task: dict, scripts: list[dict], out: Path | None = None) -> dict:
        from .studio_loop import result_failed, result_text
        run = secrets.token_hex(6)
        ok, text = await self._luau(apply_luau(task, scripts, run))
        receipt = pl.marked_json(text, APPLY_MARK) or {}
        if not (ok and receipt.get("run") == run):
            return {"studio_problem": "apply failed: " + text[-200:]}
        # Studio on brain 2 sometimes misses the "Playing" confirmation (2026-10-16: twice in ~60 starts): stop, wait,
        # try once more before calling it a Studio problem.
        started = await self._call("start_stop_play", is_start=True)
        if result_failed(started):
            await self._call("start_stop_play", is_start=False)
            await self.sleep(self.retry_wait)
            started = await self._call("start_stop_play", is_start=True)
        if result_failed(started):
            return {"studio_problem": "playtest did not start: " + result_text(started)[:200]}
        began, console, parsed = time.monotonic(), "", parse_console("", run)
        try:
            while time.monotonic() - began < task["playSeconds"]:
                await self.sleep(self.poll)
                console = result_text(await self._call("get_console_output"))
                parsed = parse_console(console, run)
                if parsed["finished"] or (not parsed["started"] and time.monotonic() - began > self.settle):
                    break
            await self.sleep(min(self.poll, 1.0))
            console = result_text(await self._call("get_console_output"))
            parsed = parse_console(console, run)
        finally:
            stopped = await self._call("start_stop_play", is_start=False)
        if out is not None:
            at = console.find(MARK)
            out.write_text(console[console.rfind("\n", 0, at) + 1:] if at >= 0 else console[-4000:], encoding="utf-8")
        return {"run": run, "parsed": parsed, "errors": answer_errors(console, run, task["id"]),
                "play_seconds": round(time.monotonic() - began, 1),
                **({"studio_problem": "playtest did not stop"} if result_failed(stopped) else {})}


async def _task_row(bench: BenchRun, task: dict, model: str, answers: Path, out: Path) -> dict | None:
    """One scored row, or None when Studio itself failed (the caller reopens the session and retries)."""
    answer, meta = answer_for(task, model, answers)
    row = {"model": model, "task": task["id"], "level": task["level"],
           "brain_seconds": meta.get("seconds"), "tokens": meta.get("tokens")}
    if answer is None:
        return {**row, "passed": False, "checks_passed": 0, "checks": 0, "why": ["no answer"]}
    scripts, problems = scripts_for(task, answer)
    row["api_findings"] = api_findings(scripts)
    played: dict = {"parsed": parse_console("", ""), "errors": []}
    if not problems and scripts:
        folder = out / model
        folder.mkdir(parents=True, exist_ok=True)
        played = await bench.one(task, scripts, folder / f"{task['id']}-output.txt")
        if played.get("studio_problem"):
            bench.log(f"{model} {task['id']}: Studio problem: {played['studio_problem']}")
            return None
    verdict = judge(played["parsed"], played["errors"], problems or ([] if scripts else ["no code"]))
    bench.log(f"{model} {task['id']}: {'PASS' if verdict['passed'] else 'fail'} "
              f"{verdict['checks_passed']}/{verdict['checks']} {'; '.join(verdict['why'])[:200]}")
    return {**row, **verdict, "errors": played.get("errors", []), "play_seconds": played.get("play_seconds")}


async def run_bench(tasks: list[dict], models: list[str], answers: Path, open_guarded, out: Path, *, log=print,
                    bench_kwargs=None, sessions: int = 4, reopen_wait: float = 30.0) -> dict:
    """Every (model, task) once. A Studio failure (play did not start/stop, connector lost) closes the session and
    reopens it (up to `sessions` times; the failed task is played again); what is left is reported as not run."""
    out.mkdir(parents=True, exist_ok=True)
    kwargs = dict(bench_kwargs or {})
    sleep = kwargs.get("sleep", asyncio.sleep)
    rows: list[dict] = []
    pending = [(model, task) for model in models for task in tasks]
    cleanup: dict = {}
    for attempt in range(sessions):
        try:
            async with open_guarded() as (guarded, facts):
                if guarded is None:
                    if attempt == 0:
                        return {"ok": False, "problem": (facts or {}).get("problem") or "no verified STAR test place"}
                    log("Studio not available: " + str((facts or {}).get("problem")))
                else:
                    bench = BenchRun(guarded, log=log, **kwargs)
                    await bench._call("start_stop_play", is_start=False)     # a playtest left running by a failure
                    await bench.remove()
                    while pending:
                        model, task = pending[0]
                        row = await _task_row(bench, task, model, answers, out)
                        if row is None:
                            break
                        rows.append(row)
                        pending.pop(0)
                    cleanup = await bench.remove()
        except Exception as error:          # the connector dropped mid-run
            log(f"Studio session failed ({type(error).__name__})")
        if not pending:
            break
        await sleep(reopen_wait)
    rows += [{"model": m, "task": t["id"], "level": t["level"], "passed": False, "checks_passed": 0, "checks": 0,
              "why": ["not run: Studio problem"], "studio_problem": True} for m, t in pending]
    result = {"ok": not pending, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "tasks": len(tasks), "models": models, "summary": summarize(rows, tasks), "rows": rows,
              "cleanup": cleanup}
    (out / "results.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    (out / "results.md").write_text(markdown(result), encoding="utf-8")
    return result


# --------------------------------------------------------------------------- score

def summarize(rows: list[dict], tasks: list[dict]) -> dict:
    most = sum(LEVELS[t["level"]] for t in tasks)
    out = {}
    for model in dict.fromkeys(r["model"] for r in rows):
        mine = [r for r in rows if r["model"] == model]
        seconds = [r["brain_seconds"] for r in mine if r.get("brain_seconds")]
        out[model] = {
            "passed": sum(1 for r in mine if r["passed"]), "tasks": len(mine),
            "score": sum(LEVELS[r["level"]] for r in mine if r["passed"]), "max_score": most,
            "by_level": {lv: f"{sum(1 for r in mine if r['level'] == lv and r['passed'])}/"
                             f"{sum(1 for r in mine if r['level'] == lv)}" for lv in LEVELS},
            "checks": f"{sum(r.get('checks_passed', 0) for r in mine)}/{sum(r.get('checks', 0) for r in mine)}",
            "median_brain_seconds": round(statistics.median(seconds), 1) if seconds else None,
            "api_doubts": sum(len(r.get("api_findings") or []) for r in mine),
        }
    return out


def markdown(result: dict) -> str:
    summary = result["summary"]
    models = list(summary)
    lines = [f"# STAR Roblox benchmark results ({result['finished_utc']})", "",
             "Each task's checks ran in a real Roblox Studio playtest. Score: easy 1, medium 2, hard 3 points.", "",
             "| model | tasks passed | score | easy | medium | hard | checks | median answer s |",
             "|---|---|---|---|---|---|---|---|"]
    for m in models:
        s = summary[m]
        lines.append(f"| {m} | {s['passed']}/{s['tasks']} | {s['score']}/{s['max_score']} | {s['by_level']['easy']} | "
                     f"{s['by_level']['medium']} | {s['by_level']['hard']} | {s['checks']} | "
                     f"{s['median_brain_seconds'] if s['median_brain_seconds'] is not None else '-'} |")
    lines += ["", "| task | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    cells: dict[str, dict[str, str]] = {}
    for r in result["rows"]:
        cells.setdefault(r["task"], {})[r["model"]] = ("pass" if r["passed"] else
                                                     f"fail {r.get('checks_passed', 0)}/{r.get('checks', 0)}")
    for task, by_model in cells.items():
        lines.append(f"| {task} | " + " | ".join(by_model.get(m, "-") for m in models) + " |")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- CLI

def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description="STAR open Roblox benchmark (checks run in Roblox Studio)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate the task files offline")
    ask = sub.add_parser("answers", help="brain only: each model writes every task (saved, asked once)")
    run = sub.add_parser("run", help="playtest the saved answers (and the reference) in Studio")
    for command in (ask, run):
        command.add_argument("--answers", required=True, help="folder for <model>/<task>.txt")
        command.add_argument("--models", default=",".join(DEFAULT_MODELS))
        command.add_argument("--only", default="", help="comma-separated task ids")
    ask.add_argument("--endpoints", default="", help="JSON {label: {url, model, key_file, extra}} for other contestants")
    ask.add_argument("--no-think", action="store_true", help="ask with thinking off (chat_template_kwargs)")
    run.add_argument("--home", required=True, help="Studio Lab home with studio/lab-multi.json")
    run.add_argument("--out", required=True)
    chosen = parser.parse_args(arguments)
    only = {t for t in getattr(chosen, "only", "").split(",") if t}
    tasks = load_tasks(only=only or None)
    if chosen.command == "check":
        print(json.dumps({"ok": True, "tasks": [t["id"] for t in tasks],
                          "levels": {lv: sum(1 for t in tasks if t["level"] == lv) for lv in LEVELS}}, indent=1))
        return 0
    models = [m for m in chosen.models.split(",") if m]
    log = lambda text: print(time.strftime("%H:%M:%S"), text, flush=True)   # noqa: E731
    if chosen.command == "answers":
        endpoints = load_endpoints(Path(chosen.endpoints) if chosen.endpoints else None)
        if not pl.Brain().url and any(m not in endpoints and m != REFERENCE for m in models):
            print("no brain URL (STAR_PLAYTEST_BRAIN_URL or STAR_BRAIN_URL)")
            return 2
        collect_answers(tasks, models, Path(chosen.answers),
                        brain_for=brain_factory(endpoints, NO_THINK if chosen.no_think else None), log=log)
        return 0
    out = Path(chosen.out) / time.strftime("bench-%Y%m%dT%H%M%SZ", time.gmtime())
    result = asyncio.run(run_bench(tasks, models, Path(chosen.answers),
                                   pl.studio_opener(Path(chosen.home).expanduser()), out, log=log))
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=1))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
