"""Command line: python -m startrain <command>

  run              generate (what the systemd unit runs)
  status           the running report, from the state files
  report           rewrite report.md / report.json
  build-decontam   build the evaluation-suite index from a suite folder (needs the brain for embeddings)
  selftest         check the Luau harness mocks, the tools and the decontamination index
  export           write the kept examples as chat-format JSONL with a manifest (no training is started)
  show             print kept examples for a quality review
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

from .config import Settings


def log(message: str) -> None:
    print(f"{datetime.now(timezone.utc).strftime('%H:%M:%S')}Z {message}", flush=True)


def _brain(s: Settings):
    from .brain import Brain
    return Brain(s.brain_url, s.key_file, poll_s=s.poll_s)


def cmd_run(args) -> int:
    from . import report as rep
    from .decontam import Decontaminator
    from .loop import Generator
    from .luau import LuauTools
    from .quiet import Stopper
    from .store import Store
    s = Settings()
    s.ensure_dirs()
    if args.window is not None:
        s.window_utc = args.window
    if not s.decontam_index.is_file():
        log("no decontamination index at " + str(s.decontam_index) + "; run build-decontam first")
        return 2
    stop = Stopper()
    tools = LuauTools(s)
    decontam = Decontaminator.load(s.decontam_index, s)
    suites = s.home / "suites"
    stale = decontam.is_fresh(suites) if suites.is_dir() else []
    if stale:
        log("the decontamination index is stale; these suite files are new or changed: " + ", ".join(stale[:8])
            + ". Run build-decontam again before generating (fail closed).")
        return 2
    store = Store(s.data)
    brain = _brain(s)
    gen = Generator(s, brain, tools, decontam, store, stop, log)
    log(f"start: {store.state['kept']} kept of {store.state['candidates']} so far; teachers "
        f"{s.task_model}/{s.solver_model}/{s.idea_model}; window {s.window_utc or 'any time'}; "
        f"decontamination items {len(decontam.items)}")
    gen.run(max_candidates=args.max_candidates, max_seconds=args.max_hours * 3600.0,
            report=lambda: rep.write(store, s.data))
    log("stopped cleanly")
    return 0


def cmd_status(args) -> int:
    from . import report as rep
    from .store import Store
    s = Settings()
    store = Store(s.data)
    info = rep.summary(store)
    print(rep.render(info) if not args.json else json.dumps(info, indent=1))
    return 0


def cmd_report(args) -> int:
    from . import report as rep
    from .store import Store
    s = Settings()
    rep.write(Store(s.data), s.data)
    log("wrote " + str(s.data / "report.md"))
    return 0


def cmd_build_decontam(args) -> int:
    from . import decontam
    s = Settings()
    s.ensure_dirs()
    root = Path(args.suite_root)
    extra = [Path(p) for p in args.extra]
    brain = _brain(s)
    index = decontam.build_index(root, extra, embed=lambda texts: brain.embed(s.embed_model, texts))
    s.decontam_index.write_text(json.dumps(index), encoding="utf-8")
    log(f"index written: {index['counts']}, suite digest {index['suite_digest'][:16]}")
    d = decontam.Decontaminator(index, s)
    missed = d.self_check(root, extra)
    log(f"self-check: {len(missed)} of {index['counts']['items']} suite texts were not recognised"
        + (": " + ", ".join(missed[:10]) if missed else ""))
    return 1 if missed else 0


def cmd_selftest(args) -> int:
    from . import harness
    from .luau import LuauTools
    s = Settings()
    tools = LuauTools(s)
    body = Path(__file__).with_name("selftest_body.luau").read_text(encoding="utf-8")
    script = harness.build_test_script(tools.prelude, "return {}\n", body)
    result = tools.run_script(script)
    out = harness.parse_output(result.stdout)
    bad = [name for name, ok in out.results if not ok]
    print(f"harness mocks: {len(out.results)} checks, {len(bad)} failed, done={out.done}, rc={result.rc}")
    for name in bad:
        print("  FAILED:", name)
    if out.error or out.load_error:
        print("  error:", out.error or out.load_error)
    if not out.done:
        print(result.stdout[-600:])
    return 0 if out.done and not bad and not out.error else 1


def cmd_show(args) -> int:
    from .store import Store, read_jsonl
    s = Settings()
    rows = read_jsonl(Store(s.data).kept_path)
    for row in rows[-args.n:]:
        print("=" * 100)
        print(f"{row['id']}  topic={row['topic']}  mode={row['mode']}  difficulty={row['difficulty']}  "
              f"G3={row['gates']['G3']}  G4={row['gates']['G4']}")
        print("--- PROMPT\n" + row["prompt"])
        print("--- RESPONSE\n" + row["response"])
        if args.tests:
            print("--- TESTS\n" + row["tests"])
    return 0


def cmd_export(args) -> int:
    from .store import Store, read_jsonl
    s = Settings()
    rows = read_jsonl(Store(s.data).kept_path)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    train, dev = [], []
    for row in rows:
        bucket = int(hashlib.sha256(row["topic"].encode()).hexdigest(), 16) % 100     # group = topic, never split
        record = {"id": row["id"], "category": row["category"], "group_id": row["topic"], "mode": row["mode"],
                  "messages": [{"role": "user", "content": row["prompt"]},
                               {"role": "assistant", "content": row["response"]}],
                  "evidence": {"gate_log_sha256": row["gate_log_sha256"], "verification": row["verification"]}}
        (dev if bucket < 10 else train).append(record)
    for name, part in (("train.jsonl", train), ("dev.jsonl", dev)):
        (out_dir / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part), encoding="utf-8")
    manifest = {
        "examples": len(rows), "train": len(train), "dev": len(dev), "split": "by topic group (10 percent of groups to dev)",
        "teachers": "the owner's own open-weight models served on the owner's server (Apache-2.0 weights)",
        "sources": ["owner-open-weight-models-synthetic"],
        "not_used": ["hosted-model outputs", "scraped text", "other people's games", "any evaluation task"],
        "verification": "every example passed gates G0-G8; mock-verified examples ran against harness stand-ins, not Roblox",
        "note": "Not reviewed by a person: a random 5 percent audit (at least 50 examples) is still required before training.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    log(f"exported {len(train)} train / {len(dev)} dev to {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="startrain", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--max-candidates", type=int, default=0)
    run.add_argument("--max-hours", type=float, default=0.0)
    run.add_argument("--window", default=None, help="UTC window like 04:00-10:00 (default: STAR_TRAIN_WINDOW_UTC, else any time)")
    run.set_defaults(fn=cmd_run)
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    st.set_defaults(fn=cmd_status)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    bd = sub.add_parser("build-decontam")
    bd.add_argument("--suite-root", required=True, help="folder with golden-tasks-*.json, reference/, tests/")
    bd.add_argument("--extra", nargs="*", default=[], help="more .json / .jsonl files with prompts or questions")
    bd.set_defaults(fn=cmd_build_decontam)
    sub.add_parser("selftest").set_defaults(fn=cmd_selftest)
    sh = sub.add_parser("show")
    sh.add_argument("-n", type=int, default=10)
    sh.add_argument("--tests", action="store_true")
    sh.set_defaults(fn=cmd_show)
    ex = sub.add_parser("export")
    ex.add_argument("--out", required=True)
    ex.set_defaults(fn=cmd_export)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
