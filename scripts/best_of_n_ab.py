"""Paired A/B of best-of-N (star/best_of_n.py) on the Roblox eval suites, through the real desktop turn.

For each task: one answer with best-of-N off ("single") and one with it on ("best"), alternating which arm goes
first, both through star.desktop_core.run_task against the STAR Server, then both scored by the suite's GOLDEN
checks (star/eval_checks.py: compile/type check by STAR Knowledge, the task's own unit tests in the server's Luau
VM sandbox, patterns). The golden unit tests are never shown to the model or to best-of-N: best-of-N writes its
own tests from the prompt. The evidence line best-of-N appends is cut before scoring.

    APPDATA=<temp> STAR_EVAL_SERVER=http://<server>:8080/v1 STAR_EVAL_SSH=<user>@<lxd-host> \
      python scripts/best_of_n_ab.py --suite evals/roblox/golden-tasks-v2.json --tasks LUA-01,LUA-02 \
        --out <results.json> [--max-n 4] [--wait-free 900]

Waits while the server's quiet lock exists, and (with --wait-free) until every star-fast slot is free before each
answer, so both arms meet the same idle server. Resumes from --out. Never prints the key or the addresses.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from star import eval_checks as checks  # noqa: E402
from star import eval_runner  # noqa: E402

FOOTER = "\n\n**Best of"


def strip_footer(answer: str) -> str:
    at = answer.find(FOOTER)
    return answer if at == -1 else answer[:at]


def slots_busy(server: str, key: str, model: str = "star-fast") -> int | None:
    import httpx
    root = server[:-3] if server.endswith("/v1") else server
    try:
        reply = httpx.get(root + "/slots", params={"model": model}, headers={"Authorization": "Bearer " + key},
                          timeout=5, trust_env=False)
        rows = reply.json()
        return sum(1 for r in rows if r.get("is_processing")) if isinstance(rows, list) else None
    except Exception:
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--tasks", default="", help="comma list (default: every task with unit tests)")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-n", type=int, default=4)
    parser.add_argument("--wait-free", type=float, default=0.0, help="seconds to wait for idle star-fast slots")
    parser.add_argument("--arms", default="single,best")
    parser.add_argument("--key-file", default=str(Path.home() / ".star" / "server_api_key"))
    parser.add_argument("--model", default="star-fast")
    args = parser.parse_args(argv)

    from star.desktop_core import Settings, run_task
    from star.doc_knowledge import client_for
    from star.eval_sandbox import ContainerSandbox
    from star import server_roles

    key = eval_runner.read_key(Path(args.key_file))
    os.environ["STAR_SERVER_API_KEY"] = key
    os.environ["STAR_SKILL_PACKS"] = os.environ.get("STAR_SKILL_PACKS", "off")
    server = os.environ.get("STAR_EVAL_SERVER", "").rstrip("/")
    ssh = os.environ.get("STAR_EVAL_SSH", "")
    if not server or not ssh:
        raise SystemExit("Set STAR_EVAL_SERVER and STAR_EVAL_SSH")
    os.environ["STAR_BON_SSH"] = ssh                      # best-of-N's own generated tests use the same sandbox
    suite = eval_runner.load_suite(args.suite)
    wanted = [t for t in args.tasks.split(",") if t]
    tasks = [t for t in suite.runnable() if (t["id"] in wanted if wanted else (t.get("auto") or {}).get("unit_test"))]
    base = Settings(provider="star_server", server_endpoint=server, model=args.model, project="STAR-eval",
                    server_timeout=eval_runner.SERVER_TIMEOUT_SECONDS, best_of_n_max=args.max_n)
    base.validate()
    server_roles.discover(server, key)                    # roles + slot counts, as the desktop knows them
    knowledge = client_for(base)
    sandbox = ContainerSandbox(ssh)

    def luau_check(code, strict=False):
        return knowledge.luau_check(code, strict=strict)

    results = json.loads(args.out.read_text(encoding="utf-8")) if args.out.is_file() else {"runs": []}
    done = {(r["task"], r["arm"]) for r in results["runs"] if not r.get("error")}
    results["runs"] = [r for r in results["runs"] if not r.get("error")]
    arms = [a for a in args.arms.split(",") if a in ("single", "best")]
    for number, task in enumerate(tasks):
        order = arms if number % 2 == 0 else list(reversed(arms))
        for arm in order:
            if (task["id"], arm) in done:
                continue
            while sandbox.lock_present():
                print("quiet lock present; waiting", flush=True)
                time.sleep(30)
            if args.wait_free:
                waited = 0.0
                while (slots_busy(server, key) or 0) > 0 and waited < args.wait_free:
                    time.sleep(10)
                    waited += 10
            events: list = []
            started = time.monotonic()
            settings = Settings(**{**base.__dict__, "project": "bon-" + task["id"].lower(),
                                   "best_of_n": "auto" if arm == "best" else "off"})
            record = {"task": task["id"], "arm": arm}
            try:
                with eval_runner.isolated_appdata():
                    answer = run_task(settings, task["prompt"], mode="auto", on_event=events.append)
                record["seconds"] = round(time.monotonic() - started, 1)
                score = checks.score_answer(task, strip_footer(answer), luau_check=luau_check, sandbox=sandbox,
                                            prelude=suite.prelude, test_body=suite.test_body(task))
                record.update(passed=score.passed, failed=score.reasons[:6], answer_chars=len(answer),
                              footer=answer[len(strip_footer(answer)):][:900])
            except Exception as exc:
                record.update(error=type(exc).__name__ + ": " + str(exc)[:200],
                              seconds=round(time.monotonic() - started, 1))
            record["best_of_n"] = [{k: v for k, v in e.items() if k != "text"} for e in events
                                   if str(e.get("event", "")).startswith("best_of_n")]
            results["runs"].append(record)
            args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
            print(f"{task['id']:8} {arm:6} passed={record.get('passed')} {record.get('seconds')}s "
                  f"{record.get('error', '')[:80]}", flush=True)
    summary = {}
    for arm in arms:
        rows = [r for r in results["runs"] if r["arm"] == arm and not r.get("error")]
        summary[arm] = {"tasks": len(rows), "passed": sum(1 for r in rows if r.get("passed")),
                        "seconds_median": sorted(r["seconds"] for r in rows)[len(rows) // 2] if rows else None}
    results["summary"] = summary
    args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
