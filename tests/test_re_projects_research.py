"""Reverse-engineering / decompilation project research: notes, two catalog skill packs and a small golden suite.

The packs are listed by the skill catalog (star_skill_catalog / SkillLibrary) but are NOT routed automatically:
they are absent from star.skill_packs.TRIGGERS, so no prompt changes until the evaluation gate has measured them.
"""
import json
from pathlib import Path
import re

import pytest

from star import eval_checks, eval_runner, skill_packs
from star.agent_skills import SkillLibrary, _frontmatter

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "research" / "reverse-engineering"
SUITE = ROOT / "evals" / "reverse-engineering" / "golden-tasks-re-v1.json"

PROJECTS = ["openrct2", "openttd", "openra", "fheroes2", "openmw", "scummvm", "devilutionx", "reactos",
            "sm64-decomp", "zeldaret", "pret", "n64-pc-ports", "dolphin", "rpcs3", "ryujinx-yuzu", "wine-proton",
            "asahi-gpu", "nouveau", "ghidra-ida-ecosystem", "llm-decompilation", "matching-decomp-tooling"]
PACKS = ["re-decomp-lessons", "eng-legacy-archaeology"]
SECTIONS = ["## 1. What it is and its 2026 state", "## 2. How the original was reversed",
            "## 3. Workflow: matching, non-matching or clean-room", "## 4. Testing and verification",
            "## 5. Structuring a large legacy codebase", "## 6. Engine architecture insights",
            "## 7. Legal history and lessons", "## 8. Transferable lessons for STAR", "## Sources"]
FORBIDDEN_IN_BODY = ("ignore previous", "system prompt", "api key", "http://", "https://", "execute_luau", "publish")
# Research must stay on the legitimate side: no circumvention or exploit how-tos anywhere in the new material.
FORBIDDEN_ANYWHERE = re.compile(r"prod\.keys|title\.keys|how to (?:dump|extract) (?:the )?keys|keygen|executor script|"
                                r"anti-?cheat bypass|bypass (?:the )?anti-?cheat|download (?:the )?ROMs? (?:from|at)", re.I)


@pytest.mark.parametrize("name", PROJECTS)
def test_each_project_has_a_sourced_case_study(name):
    text = (DOCS / "projects" / f"{name}.md").read_text(encoding="utf-8")
    first = text.split("\n", 1)[0]
    assert first.startswith("# ") and "2026-10-13" in first, name
    at = -1
    for heading in SECTIONS:
        found = text.find(heading, at + 1)
        assert found > at, (name, heading)
        at = found
    sources = text[text.rfind("## Sources"):]
    assert len(set(re.findall(r"https://[^\s)>\]]+", sources))) >= 5, name
    assert "http://" not in text, name
    assert not FORBIDDEN_ANYWHERE.search(text), (name, FORBIDDEN_ANYWHERE.search(text).group(0))


def test_the_index_lists_every_project_and_summarises_lessons():
    index = (DOCS / "INDEX.md").read_text(encoding="utf-8")
    for name in PROJECTS:
        assert f"(projects/{name}.md)" in index, name
    assert "## Cross-project lessons" in index and "## Legal lessons" in index
    for name in PACKS:
        assert name in index, name


@pytest.mark.parametrize("name", PACKS)
def test_re_packs_use_the_skill_format_and_stay_small(name):
    folder = skill_packs.PACKS_DIR / name
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    fields, body = _frontmatter(text)
    assert fields.get("name") == name and 1 <= len(fields.get("description", "")) <= 1024
    body = body.strip()
    assert body.startswith("# ") and len(body) <= skill_packs.MAX_BODY_CHARS, (name, len(body))
    lowered = body.lower()
    for word in FORBIDDEN_IN_BODY:
        assert word not in lowered, (name, word)
    assert not FORBIDDEN_ANYWHERE.search(text), name
    sources = (folder / "references" / "sources.md").read_text(encoding="utf-8")
    assert sources.count("https://") >= 6 and "http://" not in sources, name
    assert "Not verified with the STAR knowledge service" in sources, name
    for extra in (folder / "references").glob("*.md"):
        assert extra.stat().st_size <= 24_000, extra.name
        assert not FORBIDDEN_ANYWHERE.search(extra.read_text(encoding="utf-8")), extra.name


def test_re_packs_are_in_the_catalog_but_never_routed_automatically(tmp_path):
    lib = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    catalog = {s.name: s for s in lib.catalog()}
    assert set(PACKS) <= set(catalog)
    assert not set(PACKS) & set(skill_packs.TRIGGERS) and not set(PACKS) & set(skill_packs.DEFAULT_ENABLED)
    assert not set(PACKS) & {p.name for p in skill_packs.available()}
    loaded = lib.load("re-decomp-lessons")
    assert "oracle" in loaded["instructions"] and "references/sources.md" in loaded["references"]
    assert "characterization" in lib.load("eng-legacy-archaeology")["instructions"].lower()


@pytest.fixture(scope="module")
def suite():
    return eval_runner.load_suite(SUITE)


def _no_luau_check(*_args, **_kwargs):
    raise AssertionError("reverse-engineering tasks are graded on prose only")


def test_the_suite_loads_and_every_task_is_prose_graded(suite):
    assert len(suite.tasks) >= 6
    for task in suite.tasks:
        auto = task["auto"]
        assert task["id"].startswith("REV-") and task["run_mode"] == "automated", task["id"]
        assert auto["code"] is False and auto["compile"] is False and auto.get("require"), task["id"]
        assert all(item.get("scope") == "prose" for item in auto.get("require", []) + auto.get("forbid", [])), task["id"]
        assert set(task["helps"]) <= set(PACKS), task["id"]
        assert task["split"] == "development" and task["expected_sources"], task["id"]
        assert all(s.startswith("https://") for s in task["expected_sources"]), task["id"]


def test_reference_answers_pass_bad_answers_fail_and_empty_answers_fail(suite):
    ref = SUITE.parent / "reference"
    for task in suite.tasks:
        good = eval_checks.score_answer(task, (ref / f"{task['id']}.md").read_text(encoding="utf-8"),
                                        luau_check=_no_luau_check)
        assert good.passed, (task["id"], good.reasons)
        bad = eval_checks.score_answer(task, (ref / f"{task['id']}.bad.md").read_text(encoding="utf-8"),
                                       luau_check=_no_luau_check)
        assert not bad.passed, task["id"]
        assert not eval_checks.score_answer(task, "", luau_check=_no_luau_check).passed, task["id"]


def test_selftest_of_the_runner_agrees(suite):
    scorer = lambda task, answer: eval_checks.score_answer(task, answer, luau_check=_no_luau_check)  # noqa: E731
    assert eval_runner.selftest(suite, scorer, log=lambda m: None) == 0


def test_no_reference_file_is_orphaned(suite):
    ids = {t["id"] for t in suite.tasks}
    for file in (SUITE.parent / "reference").glob("*.md"):
        assert file.name.split(".")[0] in ids, file.name
    raw = SUITE.read_text(encoding="utf-8")
    assert not eval_runner._PRIVATE_IP.search(raw)
    json.loads(raw)
