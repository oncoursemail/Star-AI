"""STAR Studio Lab, parallel: one suite of lab specs spread over several Roblox Studios at once.

Why: one Studio runs one playtest at a time, and a lab run spends most of its time waiting on Studio (apply, read
back, screenshots, a real playtest). Several Studios on the same machine test several specs in the same minutes, so
STAR gets more Studio-verified results (and lesson candidates) per hour.

What it does, per Studio instance ("worker"):
  * its OWN connector session (one MCP stdio process per worker; the connector lists every attached Studio and each
    worker selects exactly one by studio_id);
  * identity, fail closed: the instance must answer STAR's pin question (star/studio_remote.PinnedSession: STAR Test
    Place or a never-saved blank place, checked inside the same engine call) AND pass studio_loop's sandbox rule AND
    be admitted by the test-farm planner of PR #207 (star/studio_test_farm.preview_studio_farm) with an operator
    approval list of exactly those places. Anything else: the worker refuses and runs nothing;
  * its own draft root (Workspace/MapDrafts/Slot<n>), its own playtests and character (one play session per Studio);
  * every change still goes through studio_loop.GuardedStudio (one undo step per edit, re-checks the place before
    each change, journal), exactly like the single-Studio lab.

Admission and scheduling between STAR's jobs belong to the resource planner (star/planner_client.py, PR #266): the
runner asks it per spec run when it is configured ("studio-test", holder studio-lab-s<slot>) and goes on when it is
not reachable (fail-open, like the single lab). Starting and stopping extra Studio processes is the operator's
script on the Studio machine (server/setup/server2/bin/studio-extra.sh in the project folder); this module never
starts programs on another machine.

The connector command comes from the operator: $STAR_STUDIO_LAB_MULTI_COMMAND (JSON list) or <home>/studio/lab-multi.json
{"command": [...]}. It is never shown to a model and never written into a report.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import time

from . import map_plan, studio_lab
from .studio_test_farm import StudioInstance, StudioScenario, preview_studio_farm

MULTI_COMMAND_ENV = "STAR_STUDIO_LAB_MULTI_COMMAND"
APPROVED_PLACES = frozenset({(studio_lab.TEST_PLACE[0], studio_lab.TEST_PLACE[1]), (0, 0)})
MAX_WORKERS = 4


# --------------------------------------------------------------------------- configuration

def multi_command(home) -> list[str] | None:
    """The operator's connector command for the multi-Studio machine, or None."""
    from .studio_remote import validate_command
    raw = os.environ.get(MULTI_COMMAND_ENV, "").strip()
    try:
        if raw:
            return validate_command(json.loads(raw))
        saved = json.loads((Path(home) / "studio" / "lab-multi.json").read_text(encoding="utf-8"))
        return validate_command(saved.get("command")) if isinstance(saved, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def configured_account(home) -> int | None:
    """STAR's own Roblox account id as the operator wrote it in <home>/studio/lab-multi.json ("own_account_id"), for
    a Studio machine that holds no Open Cloud key (the key never leaves the PC). Only used when the key-backed check
    (studio_loop.own_account_id) has no answer; the place must still be STAR Test Place or a blank place (pin check,
    sandbox rule and #207's approved places), so this cannot widen what the lab may edit."""
    try:
        saved = json.loads((Path(home) / "studio" / "lab-multi.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = saved.get("own_account_id") if isinstance(saved, dict) else None
    return value if type(value) is int and value > 0 else None


def slot_root(slot: int) -> str:
    return f"{map_plan.MANAGED_ROOT}/Slot{int(slot)}"


def for_slot(spec: dict, slot: int) -> dict:
    """The spec with the worker's own draft root (Workspace/MapDrafts/Slot<n>); UI specs are unchanged."""
    spec = copy.deepcopy(spec)
    if spec.get("kind", "map") == "map":
        spec["plan"]["rootPath"] = slot_root(slot)
    return spec


# --------------------------------------------------------------------------- identity (fail closed)

def farm_admits(studio_id: str, identity, verified: bool, scenario: str) -> tuple[bool, str]:
    """#207's planner as the last gate: one test on this Studio, only an approved place, only a verified identity."""
    if identity is None:
        return False, "identity_unknown"
    try:
        instance = StudioInstance(studio_id=studio_id, universe_id=int(identity.game_id), place_id=int(identity.place_id),
                                  identity_verified=bool(verified))
        test = StudioScenario(scenario_id=scenario, studio_id=studio_id, universe_id=instance.universe_id,
                              place_id=instance.place_id, simulated_clients=1)
        preview = preview_studio_farm((instance,), (test,), approved_places=APPROVED_PLACES, max_parallel_studios=1,
                                      max_total_clients=1)
    except (ValueError, TypeError):
        return False, "invalid_identity"
    if preview.admitted == (scenario,):
        return True, "admitted"
    reasons = [d.reason for d in preview.rejected + preview.waiting]
    return False, reasons[0] if reasons else "not_admitted"


async def open_instance(session, discovered: list[dict], studio_id: str, *, home, own_account_id=None):
    """(GuardedStudio or None, facts) for exactly one Studio instance of a multi-Studio connector."""
    from . import studio_loop, studio_remote
    pinned = studio_remote.PinnedSession(session)
    if own_account_id is None:
        own_account_id = studio_loop.own_account_id(home)
    guarded = await studio_loop.open_guarded(pinned, discovered, studio_id=studio_id, opted_in=True, own_places=True,
                                             own_account_id=own_account_id)
    identity = guarded.verdict.identity
    place = (identity.game_id, identity.place_id) if identity is not None else None
    try:
        answered = await pinned.pinned(studio_id)
    except Exception:
        answered = False
    verified = bool(identity is not None and place in APPROVED_PLACES and guarded.verdict.editable and answered)
    admitted, reason = farm_admits(studio_id, identity, verified, "lab-identity")
    facts = {"studio_id": studio_id, "place": {"universe_id": place[0], "place_id": place[1]} if place else None,
             "pin": bool(answered), "editable": bool(guarded.verdict.editable), "verified": verified,
             "farm": reason, "verdict": guarded.verdict.public()}
    return (guarded if admitted else None), facts


async def wait_for_instance(session, studio_id: str, *, seconds: float = 20.0, pause: float = 0.5,
                            sleep=asyncio.sleep, clock=time.monotonic) -> bool:
    from . import studio_loop
    end = clock() + seconds
    while True:
        listed = studio_loop.studios(await session.call_tool("list_roblox_studios", arguments={}))
        if any(item.get("id") == studio_id for item in listed):
            return True
        if clock() >= end:
            return False
        await sleep(pause)


# --------------------------------------------------------------------------- planner (admission is its job)

def _admit(slot: int):
    try:
        from .planner_client import PlannerClient
    except Exception:
        return None, None
    try:
        client = PlannerClient(timeout=3.0)
        if not client.enabled:
            return None, None
        grant = client.admit("studio-test", f"studio-lab-s{slot}", "lab-run", universe_id=studio_lab.TEST_PLACE[0],
                             place_id=studio_lab.TEST_PLACE[1], identity_verified=True)
        return client, grant
    except Exception:
        return None, None


def _release(client, grant) -> None:
    if client is not None and getattr(grant, "planned", False):
        try:
            client.release(grant)
        except Exception:
            pass


# --------------------------------------------------------------------------- one worker = one Studio

class Worker:
    def __init__(self, slot: int, studio_id: str, connect, out: Path, *, home, log=print, lab_kwargs=None,
                 keep_drafts: bool = False, own_account_id=None, admit=_admit, deadline: float | None = None):
        self.slot, self.studio_id, self.connect, self.out, self.home = slot, studio_id, connect, Path(out), home
        self.deadline = deadline          # clock() value after which no new spec is started (nightly runtime cap)
        self.log, self.lab_kwargs, self.keep_drafts = log, dict(lab_kwargs or {}), keep_drafts
        self.own_account_id, self.admit = own_account_id, admit
        self.facts: dict = {}
        self.rows: list[dict] = []
        self.broken = False
        self.clean_names: set[str] = set()

    def say(self, text: str) -> None:
        self.log(f"[s{self.slot}] {text}")

    async def run(self, queue: asyncio.Queue, clock=time.monotonic) -> list[dict]:
        from . import studio
        try:
            async with self.connect() as session:
                discovered = await studio.list_tools(session)
                # A fresh connector knows no Studio for a moment, until the Studios attach to it.
                if not await wait_for_instance(session, self.studio_id):
                    self.facts = {"studio_id": self.studio_id, "verified": False,
                                  "problem": "this Studio did not attach to the worker's connector"}
                    self.say(self.facts["problem"])
                    return self.rows
                guarded, self.facts = await open_instance(session, discovered, self.studio_id, home=self.home,
                                                          own_account_id=self.own_account_id)
                self.say(f"identity: {self.facts.get('place')} verified={self.facts.get('verified')} "
                         f"farm={self.facts.get('farm')}")
                if guarded is None:
                    self.say("refused: not a verified STAR test place; this worker runs nothing")
                    return self.rows
                if self.clean_names:
                    # Drafts a stopped earlier run left in this slot would overlap the next build: remove them
                    # (lab drafts by name, inside this slot's root only; one undo step).
                    # Every slot root: the slot number of a Studio can differ between runs (listing order).
                    cleaner = studio_lab.Lab(guarded, self.out)
                    self.facts["cleaned"] = [await cleaner.remove(sorted(self.clean_names)[:50], slot_root(n))
                                             for n in range(1, MAX_WORKERS + 1)]
                while not self.broken:
                    if self.deadline is not None and clock() >= self.deadline:
                        self.say("runtime cap reached: no new spec")
                        break
                    try:
                        index, spec = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    await self._one(guarded, index, spec, clock)
        except Exception as error:                     # the text could carry the command: kind only
            self.facts["problem"] = f"worker stopped ({type(error).__name__})"
            self.say(self.facts["problem"])
        return self.rows

    async def _one(self, guarded, index: int, spec: dict, clock) -> None:
        spec = for_slot(spec, self.slot)
        client, grant = self.admit(self.slot)
        if grant is not None and getattr(grant, "action", "") in ("wait", "yield", "refuse"):
            self.rows.append({"index": index, "spec": spec["name"], "slot": self.slot, "ran": False,
                              "problem": "resource planner: " + (getattr(grant, "reason", "") or grant.action)})
            return
        folder = self.out / f"{index:02d}-{spec['name']}-s{self.slot}"
        started = clock()
        try:
            lab_class = studio_lab.UiLab if spec.get("kind") == "ui" else studio_lab.Lab
            lab = lab_class(guarded, folder, log=lambda text: self.say(f"{spec['name']} {text}"), **self.lab_kwargs)
            report = await (lab.run(spec, keep=self.keep_drafts) if spec.get("kind") == "ui"  # pyright: ignore[reportCallIssue]  # UiLab.run
                            else lab.run(spec))
            if spec.get("kind", "map") == "map" and not self.keep_drafts:
                report["cleanup"] = await lab.remove([spec["plan"]["mapName"]], slot_root(self.slot))
        except Exception as error:
            report = {"passed": False, "problem": f"lab run failed ({type(error).__name__})", "iterations": []}
        finally:
            _release(client, grant)
        seconds = round(clock() - started, 1)
        self.rows.append(row_of(index, spec, self.slot, report, seconds))
        iterations = report.get("iterations", [])
        if (any((it.get("playtest") or {}).get("stopped") is False
                or (it.get("playtest") or {}).get("started") is False for it in iterations)
                or any("unconfirmed" in str((it.get("apply") or {}).get("detail", "")) for it in iterations)):
            # Studio may still be in Play: GuardedStudio refuses further edits until a person looks. Stop taking
            # specs here; the rest of the queue goes to the other Studios.
            self.broken = True
            self.facts["problem"] = "a playtest start/stop was not confirmed; this worker stopped taking specs"
            self.say(self.facts["problem"])
        self.say(f"{spec['name']}: passed={report.get('passed')} iterations={len(report.get('iterations', []))} "
                 f"{seconds}s")


def row_of(index: int, spec: dict, slot: int, report: dict, seconds: float) -> dict:
    """One line of the suite table: what was tested, how often Studio really played it, what was fixed."""
    iterations = report.get("iterations", [])
    playtests = sum(1 for it in iterations if (it.get("playtest") or {}).get("started"))
    checks = sum(len(it.get("devices", [])) for it in iterations) if spec.get("kind") == "ui" else 0
    first = iterations[0] if iterations else {}
    return {"index": index, "spec": spec["name"], "kind": spec.get("kind", "map"), "defect": spec.get("defect", ""),
            "slot": slot, "ran": True, "seconds": seconds, "passed": bool(report.get("passed")),
            "iterations": len(iterations), "playtests": playtests, "ui_checks": checks,
            "first_pass": bool(first.get("passed")),
            "first_defects": [d.get("code") for d in first.get("defects", [])]
            + [p.get("code") for p in first.get("problems", [])],
            "expect": studio_lab.expectation(spec, report),
            "fixes": [c.get("fix") for it in iterations for c in it.get("fixes", [])],
            "lesson": (report.get("lesson") or {}).get("code"), "run": report.get("run"),
            "problem": report.get("problem", ""), "cleanup": (report.get("cleanup") or {}).get("ok")}


# --------------------------------------------------------------------------- the suite

def summarize(rows: list[dict], wall_seconds: float, workers: int) -> dict:
    """Throughput: tested results (real playtests read back) per hour, specs per hour, for this many Studios."""
    ran = [r for r in rows if r.get("ran")]
    playtests = sum(r.get("playtests", 0) for r in ran)
    hours = max(wall_seconds, 1e-9) / 3600
    return {"workers": workers, "wall_seconds": round(wall_seconds, 1), "specs": len(rows), "specs_ran": len(ran),
            "passed": sum(1 for r in ran if r["passed"]), "first_pass": sum(1 for r in ran if r["first_pass"]),
            "fixed_then_passed": sum(1 for r in ran if r["passed"] and not r["first_pass"]),
            "playtests": playtests, "playtests_per_hour": round(playtests / hours, 1),
            "specs_per_hour": round(len(ran) / hours, 1),
            "lessons": sum(1 for r in ran if r.get("lesson")),
            "ui_checks": sum(r.get("ui_checks", 0) for r in ran),
            "expected_declared": sum(1 for r in ran if (r.get("expect") or {}).get("declared")),
            "expected_met": sum(1 for r in ran if (r.get("expect") or {}).get("met")),
            "defects_reproduced": sum(1 for r in ran if (r.get("expect") or {}).get("reproduced") is True),
            "defects_not_reproduced": sum(1 for r in ran if (r.get("expect") or {}).get("reproduced") is False),
            "mean_spec_seconds": round(sum(r["seconds"] for r in ran) / len(ran), 1) if ran else None}


async def run_suite(specs: list[dict], studio_ids: list[str], connect_factory, out: Path, *, home, log=print,
                    lab_kwargs=None, keep_drafts: bool = False, own_account_id=None, admit=_admit,
                    clock=time.monotonic, anchored: bool = False, max_seconds: float | None = None) -> dict:
    """Spread `specs` over the given Studio instances (one worker each, each with its own connector session)."""
    if not 1 <= len(studio_ids) <= MAX_WORKERS or len(set(studio_ids)) != len(studio_ids):
        raise ValueError(f"1..{MAX_WORKERS} distinct Studio instances")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    queue: asyncio.Queue = asyncio.Queue()
    for index, spec in enumerate(specs, 1):
        queue.put_nowait((index, spec))
    play_lock = asyncio.Lock()          # one Play start/stop at a time across the Studios (see Lab.play_lock)
    kwargs = {"play_lock": play_lock, **dict(lab_kwargs or {})}
    names = {spec["plan"]["mapName"] for spec in specs if spec.get("kind", "map") == "map"}
    started = clock()
    deadline = started + max_seconds if max_seconds else None
    workers = [Worker(slot, studio_id, connect_factory, out, home=home, log=log, lab_kwargs=kwargs,
                      keep_drafts=keep_drafts, own_account_id=own_account_id, admit=admit, deadline=deadline)
               for slot, studio_id in enumerate(studio_ids, 1)]
    for worker in workers:
        worker.clean_names = set(names)
    # The first connector process on the Studio machine becomes the host every Studio attaches to; a worker that
    # finishes early would take the host down with it. An anchor session opened first stays the host until the end.
    if anchored:
        results = await asyncio.gather(*(worker.run(queue, clock) for worker in workers))
    else:
        async with connect_factory() as anchor:
            try:
                from . import studio
                await studio.list_tools(anchor)
            except Exception:
                pass
            results = await asyncio.gather(*(worker.run(queue, clock) for worker in workers))
    wall = clock() - started
    rows = sorted((row for part in results for row in part), key=lambda r: r["index"])
    left = []
    while not queue.empty():
        index, spec = queue.get_nowait()
        capped = deadline is not None and clock() >= deadline
        left.append({"index": index, "spec": spec["name"], "slot": None, "ran": False,
                     "problem": "runtime cap reached" if capped else "no verified Studio was left to run it"})
    rows = sorted(rows + left, key=lambda r: r["index"])
    summary = summarize(rows, wall, sum(1 for w in workers if w.facts.get("verified")))
    report = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "summary": summary,
              "instances": [w.facts for w in workers], "rows": rows}
    (out / "suite.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


async def list_instances(session, *, expect: int = 1, seconds: float = 90.0) -> list[dict]:
    """[{id, name}] of the Studios attached to an open connector session (waits until `expect` attach). After a
    host connector exits, Studios re-attach to the next host with a back-off that was seen to take over a minute."""
    from . import studio, studio_loop
    await studio.list_tools(session)
    end = time.monotonic() + seconds
    while True:
        listed = studio_loop.studios(await session.call_tool("list_roblox_studios", arguments={}))
        if len(listed) >= expect or time.monotonic() >= end:
            return listed
        await asyncio.sleep(1.0)


async def run_cli(specs: list[dict], connect, out_root: Path, *, home, studios: int, keep_drafts: bool,
                  log, max_seconds: float | None = None, prefix: str = "suite", own_account_id=None) -> dict:
    """Open the anchor session (the connector host), find the Studios, run the suite while the anchor stays open."""
    async with connect() as anchor:
        listed = await list_instances(anchor, expect=max(studios, 1))
        ids = [item["id"] for item in listed][:studios or MAX_WORKERS]
        if not ids:
            return {"ok": False, "problem": "no Studio is attached to the connector"}
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        out = Path(out_root) / f"{prefix}-{len(ids)}studio-{stamp}"
        report = await run_suite(specs, ids, connect, out, home=home, log=log, keep_drafts=keep_drafts,
                                 anchored=True, max_seconds=max_seconds, own_account_id=own_account_id)
        report["out"] = str(out)
        return report


def connector(command: list[str]):
    """A factory of fresh connector sessions (one per worker) for the operator's multi-Studio command."""
    from . import studio

    def make():
        return studio.connect(target="host_launcher", command=command)
    return make


def outbox_records(rows_dir: Path) -> list[dict]:
    """Lesson candidates of every run in a suite folder (report.json files), for the night-school outbox."""
    records = []
    for report in sorted(Path(rows_dir).glob("*/report.json")):
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("lesson"):
            records.append(data["lesson"])
    return records


# --------------------------------------------------------------------------- nightly (scheduled, rotating, capped)

NIGHTLY_MAX_STUDIOS = 3           # the Studio machine's measured safe maximum is 2 (see docs); 3 only by hand
ROTATION_FILE = "rotation.json"


def load_spec_tree(folder: Path) -> tuple[list[dict], list[dict]]:
    """Every lab spec under a folder (map and UI, sub-folders too), in a stable order; (specs, invalid)."""
    folder = Path(folder)
    files = sorted(folder.rglob("*.json"), key=lambda f: f.relative_to(folder).as_posix()) if folder.is_dir() else [folder]
    specs, invalid = [], []
    for file in files:
        try:
            raw = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            invalid.append({"file": file.name, "problems": ["not JSON"]})
            continue
        spec, problems = studio_lab.check_spec(raw)
        if spec is None:
            invalid.append({"file": file.name, "problems": problems})
        else:
            specs.append(spec)
    return specs, invalid


def rotation(specs: list[dict], count: int, state_file: Path) -> tuple[list[dict], int]:
    """The next `count` specs after where the last night stopped (wrapping), and the offset used. Pure apart from
    reading the state file; advance_rotation() writes it after a run that ran something."""
    total = len(specs)
    if not total or count <= 0:
        return [], 0
    try:
        start = int(json.loads(Path(state_file).read_text(encoding="utf-8")).get("next", 0)) % total
    except (OSError, ValueError, TypeError, AttributeError):
        start = 0
    return [specs[(start + i) % total] for i in range(min(count, total))], start


def advance_rotation(state_file: Path, start: int, ran: int, total: int) -> None:
    Path(state_file).parent.mkdir(parents=True, exist_ok=True)
    Path(state_file).write_text(json.dumps({"next": (start + ran) % max(total, 1), "total": total,
                                            "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}),
                                encoding="utf-8")


def prune_evidence(out_root: Path, keep: int) -> list[str]:
    """Keep the newest `keep` nightly-* evidence folders under out_root; older ones are deleted (only those)."""
    import shutil
    folders = sorted((f for f in Path(out_root).glob("nightly-*") if f.is_dir()), key=lambda f: f.name[-16:])
    removed = []
    for folder in folders[:max(len(folders) - max(keep, 1), 0)]:
        shutil.rmtree(folder, ignore_errors=True)
        removed.append(folder.name)
    return removed


def nightly(spec_folder: Path, *, home, out: Path, outbox: Path | None, studios: int, rotate: int,
            max_minutes: float, keep: int, log=print, run=None) -> dict:
    """One scheduled night: a rotating slice of the spec tree on up to `studios` Studios, capped in time; evidence
    under out/nightly-<n>studio-<stamp>/, lesson candidates (owner review) to the outbox, old evidence pruned."""
    out = Path(out)
    specs, invalid = load_spec_tree(Path(spec_folder))
    state = out / ROTATION_FILE
    chosen, start = rotation(specs, rotate or len(specs), state)
    result = {"ok": False, "specs_total": len(specs), "invalid": invalid, "rotation_start": start,
              "chosen": [s["name"] for s in chosen], "studios_cap": studios, "max_minutes": max_minutes}
    if not chosen:
        result["problem"] = "no valid specs"
        return result
    command = multi_command(home)
    if not command and run is None:
        result["problem"] = f"no multi-Studio connector command ({MULTI_COMMAND_ENV} or <home>/studio/lab-multi.json)"
        return result
    studios = max(1, min(int(studios), NIGHTLY_MAX_STUDIOS))
    account = None
    if run is None:
        from . import studio_loop
        account = studio_loop.own_account_id(home) or configured_account(home)
    runner = run or (lambda: asyncio.run(run_cli(chosen, connector(command or []), out, home=home, studios=studios,
                                                 keep_drafts=False, log=log, max_seconds=max_minutes * 60,
                                                 prefix="nightly", own_account_id=account)))
    report = runner()
    if "summary" not in report:
        result["problem"] = report.get("problem", "the suite did not run")
        return result
    folder = Path(report["out"])
    ran = report["summary"]["specs_ran"]
    if ran:
        advance_rotation(state, start, ran, len(specs))
    result.update(ok=bool(ran), out=str(folder), summary=report["summary"],
                  not_run=[r["spec"] for r in report["rows"] if not r.get("ran")])
    if outbox:
        records = outbox_records(folder)
        result["outbox"] = studio_lab.write_outbox(Path(outbox), records) if records else {"records": 0}
    (folder / "nightly.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    result["pruned"] = prune_evidence(out, keep)
    return result


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description="STAR Studio Lab across several Studios at once")
    parser.add_argument("specs", help="folder of lab spec files (or one file)")
    parser.add_argument("--home", required=True, help="STAR data folder (studio/lab-multi.json, roblox/access.json)")
    parser.add_argument("--out", required=True, help="evidence folder")
    parser.add_argument("--studios", type=int, default=0, help="use this many attached Studios (default: all, max 4)")
    parser.add_argument("--only", default="", help="comma-separated spec names to run")
    parser.add_argument("--outbox", default="", help="folder for Studio-verified lesson candidates")
    parser.add_argument("--keep-drafts", action="store_true", help="leave each draft in Studio after its run")
    chosen = parser.parse_args(arguments)
    home = Path(chosen.home).expanduser()
    command = multi_command(home)
    if not command:
        print(json.dumps({"ok": False, "problem": f"no multi-Studio connector command ({MULTI_COMMAND_ENV} or "
                                                  "<home>/studio/lab-multi.json)"}))
        return 2
    specs, problems = [], []
    wanted = {n.strip() for n in chosen.only.split(",") if n.strip()}
    for raw in studio_lab._load_specs(Path(chosen.specs)):
        spec, issues = studio_lab.check_spec(raw)
        if spec is None:
            problems.append({"spec": raw.get("name"), "problems": issues})
        elif not wanted or spec["name"] in wanted:
            specs.append(spec)
    if problems:
        print(json.dumps({"ok": False, "invalid_specs": problems}, indent=1))
        return 2
    connect = connector(command)
    report = asyncio.run(run_cli(specs, connect, Path(chosen.out), home=home, studios=chosen.studios,
                                 keep_drafts=chosen.keep_drafts,
                                 log=lambda text: print(time.strftime("%H:%M:%S"), text, flush=True)))
    if "summary" not in report:
        print(json.dumps(report))
        return 1
    out = Path(report["out"])
    print(json.dumps(report["summary"], indent=1))
    if chosen.outbox:
        records = outbox_records(out)
        if records:
            print(json.dumps(studio_lab.write_outbox(Path(chosen.outbox), records)))
    return 0 if report["summary"]["specs_ran"] else 1


if __name__ == "__main__":
    sys.exit(main())
