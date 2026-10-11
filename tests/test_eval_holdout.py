"""Structure and freeze checks for the blind holdout suite `evals/roblox/holdout-v1.json`.

Nothing here talks to a model, the server or the sandbox. The reference answers are run for real by
`python -m star.evals selftest --suite evals/roblox/holdout-v1.json` (see docs/evals-holdout.md).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import pytest

from star import eval_checks as checks
from star.eval_runner import load_suite

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals" / "roblox"
HOLDOUT = EVALS / "holdout-v1.json"
SHA_FILE = EVALS / "holdout-v1.sha256"
EARLIER_SUITES = ("golden-tasks-v1.json", "golden-tasks-v2.json", "golden-tasks-creation-v1.json")
FUZZY_LIMIT = 0.5          # token-overlap (Jaccard) at or above this counts as "the same task"
PRIVATE_ADDRESS = re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")

AREAS = {"NET": 5, "DAT": 4, "UI": 4, "ANI": 1, "VFX": 2, "BLD": 3, "ENG": 3, "DOC": 2}   # ANI + VFX = 3 animation and VFX tasks


def _tasks() -> list[dict]:
    return json.loads(HOLDOUT.read_text(encoding="utf-8"))


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]{3,}", text.lower()))


def _normal(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", text.lower()))


def _lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_suite_loads_with_the_harness_loader():
    suite = load_suite(HOLDOUT)
    assert len(suite.tasks) == 24
    assert len(suite.runnable()) == 24                      # every task is automated
    assert all(t["split"] == "holdout" for t in suite.tasks)


def test_ids_are_unique_and_prefixed():
    ids = [t["id"] for t in _tasks()]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"HO-[A-Z]+-\d\d", i) for i in ids)
    earlier = {t["id"] for name in EARLIER_SUITES for t in json.loads((EVALS / name).read_text(encoding="utf-8"))}
    assert not earlier & set(ids)


def test_coverage_per_area():
    counts: dict[str, int] = {}
    for t in _tasks():
        area = t["id"].split("-")[1]
        counts[area] = counts.get(area, 0) + 1
    assert counts == AREAS


def test_every_prompt_is_routed_as_a_roblox_question():
    # STAR answers prompts without a Roblox word as a quick chat; the suite must measure the Roblox route.
    for t in _tasks():
        assert re.search(r"\bRoblox\b", t["prompt"]), t["id"]


def test_no_task_repeats_an_existing_task():
    mine = _tasks()
    for name in EARLIER_SUITES:
        for old in json.loads((EVALS / name).read_text(encoding="utf-8")):
            old_prompt, old_words = _normal(old["prompt"]), _words(old["prompt"])
            for t in mine:
                assert _normal(t["prompt"]) != old_prompt, (t["id"], old["id"])
                assert _normal(t["goal"]) != _normal(old.get("goal", "")), (t["id"], old["id"])
                mine_words = _words(t["prompt"])
                overlap = len(mine_words & old_words) / max(1, len(mine_words | old_words))
                assert overlap < FUZZY_LIMIT, f"{t['id']} overlaps {name}:{old['id']} ({overlap:.2f})"


def test_every_task_has_both_reference_files_and_no_orphans():
    ids = {t["id"] for t in _tasks()}
    for tid in ids:
        for name in (f"{tid}.md", f"{tid}.bad.md"):
            path = EVALS / "reference" / name
            assert path.is_file() and path.read_text(encoding="utf-8").strip(), name
    on_disk = {p.name for p in (EVALS / "reference").glob("HO-*.md")}
    assert on_disk == {f"{tid}{kind}.md" for tid in ids for kind in ("", ".bad")}
    declared = {t["auto"]["unit_test"]["file"] for t in _tasks() if t["auto"].get("unit_test")}
    assert declared == {f"tests/{p.name}" for p in (EVALS / "tests").glob("HO-*.luau")}
    for file in declared:
        assert (EVALS / file).read_text(encoding="utf-8").strip()


def test_task_shape():
    for t in _tasks():
        auto = t["auto"]
        assert t["run_mode"] == "automated"
        assert t["fixtures"] == ([auto["unit_test"]["file"]] if auto.get("unit_test") else [])
        if auto.get("code", True):
            assert auto.get("unit_test"), t["id"]            # every code task is judged by unit tests, not by patterns alone
            assert isinstance(auto["unit_test"]["checks"], int) and auto["unit_test"]["checks"] >= 5, t["id"]
        else:
            assert auto["citation"]["required"] is True and auto["require"], t["id"]


def test_typecheck_probe_only_where_generics_are_the_point():
    probes = [t["id"] for t in _tasks() if t["auto"].get("typecheck_probe")]
    assert probes == ["HO-ENG-01"]
    suffix = _tasks()[[t["id"] for t in _tasks()].index("HO-ENG-01")]["auto"]["typecheck_probe"]["suffix"]
    assert "__M" in suffix


def test_no_private_address_or_secret_in_the_suite_files():
    files = [HOLDOUT, SHA_FILE, *EVALS.glob("tests/HO-*.luau"), *EVALS.glob("reference/HO-*.md")]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not PRIVATE_ADDRESS.search(text), path.name
        assert "api_key" not in text.lower(), path.name


def test_references_pass_and_bad_answers_fail_the_offline_pattern_checks():
    for t in _tasks():
        auto = t["auto"]
        for kind, expect in (("", True), (".bad", False)):
            text = (EVALS / "reference" / f"{t['id']}{kind}.md").read_text(encoding="utf-8")
            body, footer = checks.split_answer(text)
            blocks = checks.extract_luau_blocks(body)
            if not auto.get("code", True):
                assert not blocks
            else:
                assert blocks, f"{t['id']}{kind} has no Luau block"
            found = checks.pattern_checks(auto, blocks, body)
            if auto.get("citation", {}).get("required"):
                found.append(checks.citation_check(auto, footer))
            if not found:
                continue                                      # unit tests only: judged by selftest on the server
            if expect:
                assert all(c.ok for c in found), (t["id"], [c.id for c in found if not c.ok])
            elif not auto.get("unit_test"):
                assert not all(c.ok for c in found), f"{t['id']}.bad passes every offline check"


def _recorded_hashes() -> dict[str, str]:
    out = {}
    for line in SHA_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        out[name.strip()] = digest.strip()
    return out


def test_frozen_files_still_have_the_recorded_hashes():
    """Line endings are normalised to LF first, as the harness does, so a Windows checkout agrees with a git archive."""
    recorded = _recorded_hashes()
    expected = {"holdout-v1.json", *(f"tests/{p.name}" for p in (EVALS / "tests").glob("HO-*.luau")),
                *(f"reference/{p.name}" for p in (EVALS / "reference").glob("HO-*.md"))}
    assert set(recorded) == expected, "the hash file must list exactly the suite, its test bodies and its references"
    changed = [name for name, digest in recorded.items() if _lf_sha256(EVALS / name) != digest]
    assert not changed, f"frozen files were edited (results made before are no longer comparable): {changed}"


def test_the_freeze_is_stated_in_the_docs():
    text = (ROOT / "docs" / "evals-holdout.md").read_text(encoding="utf-8")
    assert "frozen 2026-10-11" in text
    assert "any later edit makes earlier results incomparable" in text
    assert "never use for training data or for tuning" in text.lower()
