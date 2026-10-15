"""Keep pyright errors in star/ from growing.

pyright (basic mode, settings in pyrightconfig.json) still reports errors in older
code. They are counted per file and rule in scripts/pyright_baseline.json. The
check fails when a file gains an error of some rule, so new code cannot add type
errors, while edits that move existing lines do not matter.

Run it against a Python with no third-party packages installed (CI does), so that
library stub updates never change the counts.

    npx --yes pyright@1.1.414 --outputjson > pyright.json
    python scripts/pyright_baseline.py check pyright.json
    python scripts/pyright_baseline.py update pyright.json   # after fixing errors
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "pyright_baseline.json"


def _relative(path: str) -> str:
    """The repo-relative POSIX path, whichever OS or checkout produced the report."""
    root = os.path.normcase(str(ROOT)).replace("\\", "/").rstrip("/") + "/"
    text = path.replace("\\", "/")
    if os.path.normcase(text).replace("\\", "/").startswith(root):
        return text[len(root):]
    marker = text.find("/star/")
    return text[marker + 1:] if marker >= 0 else text


def load_report(path: Path) -> list[dict]:
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    if "generalDiagnostics" not in report or "summary" not in report:
        raise ValueError(f"{path} is not pyright --outputjson output")
    return [item for item in report["generalDiagnostics"] if item.get("severity") == "error"]


def count(errors: list[dict]) -> Counter[str]:
    return Counter(f"{_relative(item['file'])}::{item.get('rule') or 'unknown'}" for item in errors)


def compare(baseline: dict[str, int], current: Counter[str]) -> tuple[dict[str, tuple[int, int]], int]:
    """(keys that grew -> (allowed, now), number of errors fixed since the baseline)."""
    grew = {key: (baseline.get(key, 0), now) for key, now in sorted(current.items()) if now > baseline.get(key, 0)}
    fixed = sum(max(0, allowed - current.get(key, 0)) for key, allowed in baseline.items())
    return grew, fixed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare pyright errors with the checked-in baseline.")
    parser.add_argument("command", choices=("check", "update"))
    parser.add_argument("report", type=Path, help="pyright --outputjson output")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args(argv)
    errors = load_report(args.report)
    current = count(errors)
    if args.command == "update":
        args.baseline.write_text(json.dumps(dict(sorted(current.items())), indent=1) + "\n", encoding="utf-8")
        print(f"Baseline written: {sum(current.values())} errors in {len(current)} file/rule pairs")
        return 0
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    grew, fixed = compare(baseline, current)
    if grew:
        print("New pyright errors (fix them; the baseline only shrinks):")
        for item in errors:
            key = f"{_relative(item['file'])}::{item.get('rule') or 'unknown'}"
            if key in grew:
                line = item["range"]["start"]["line"] + 1
                print(f"  {_relative(item['file'])}:{line}: {item['message'].splitlines()[0]} [{item.get('rule')}]")
        for key, (allowed, now) in grew.items():
            print(f"  {key}: {now} errors, baseline allows {allowed}")
        return 1
    total = sum(current.values())
    print(f"pyright: {total} known errors, none new" + (f"; {fixed} fixed since the baseline "
          "(run `update` to lock that in)" if fixed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
