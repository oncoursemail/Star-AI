"""Independent fixtures: no candidate code or model-supplied scores are executed."""
from dataclasses import replace
import json
from pathlib import Path
import re

import pytest

# The scratch prototype extends the audited project package for tests only.
# This block is unnecessary when these files land in a normal STAR worktree.
import star
_scratch_star = Path(__file__).resolve().parents[1] / "star"
if _scratch_star.is_dir() and str(_scratch_star) not in star.__path__:
    star.__path__.append(str(_scratch_star))

from star.shared_brain.improve import Evidence, Fixture, ImprovementLoop, Limits
from star.knowledge import KnowledgeStore


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    for name in ("auth.md", "registry.md", "project.md"):
        (root / name).write_text("Independent source: " + name, encoding="utf-8")

    def graph(question, limit):
        words = set(re.findall(r"[a-z0-9_]+", question.lower()))
        evidence = []
        if "authenticate" in words:
            evidence.append(Evidence("authenticate", "auth.md", "Authenticate the selected project."))
        if "registry" in words:
            evidence.append(Evidence("registry", "registry.md", "The fixed configured tool registry."))
        return evidence[:limit]

    cases = (Fixture("AUTH", "Where is login?", ("auth.md",), expected_identifiers=("authenticate",)),
             Fixture("REGISTRY", "Where is registry?", ("registry.md",), expected_identifiers=("registry",)),
             Fixture("NEGATIVE", "Unrelated astronomy", ()))
    args = dict(source_root=root, source_files=("auth.md", "registry.md", "project.md"), cases=cases,
                sources={"graphify": graph}, vocabulary=("authenticate", "registry", "project"))
    return tmp_path, root, args


def loop_for(setup, **changes):
    tmp, _, args = setup
    return ImprovementLoop(tmp / "journal", **{**args, **changes})


def passing(loop):
    proposed = loop.propose_aliases({"login": ["authenticate"]})
    evaluated = loop.evaluate(proposed["id"])
    assert evaluated["evaluation"]["allowed"], evaluated["evaluation"]
    return evaluated


def approve_and_activate(loop, record):
    args = dict(evaluation_digest=record["evaluation_digest"], human_approved=True, reviewer="fixture owner")
    loop.review(record["id"], **args)
    return loop.activate(record["id"], **args)


def test_source_backed_alias_improves_real_retrieval_and_rolls_back(setup):
    loop = loop_for(setup)
    original = loop.status()["active_version"]
    record = passing(loop)
    evaluation = record["evaluation"]
    assert evaluation["baseline"]["AUTH"]["correct"] is False
    assert evaluation["candidate_results"]["AUTH"]["correct"] is True
    assert evaluation["candidate_results"]["REGISTRY"]["correct"]
    assert evaluation["candidate_results"]["NEGATIVE"]["correct"]
    assert set(evaluation["baseline"]) == set(evaluation["candidate_results"]) == {"AUTH", "REGISTRY", "NEGATIVE"}
    assert all(s["latency_ms"] >= 0 and s["context_chars"] <= 8000 for s in evaluation["candidate_results"].values())
    activation = approve_and_activate(loop, record)
    assert activation["previous_version"] == original
    retrieval = loop.retrieve("Where is login?")
    assert retrieval["active_version"] == record["id"] and retrieval["records"][0]["source"] == "auth.md"
    assert retrieval["untrusted"] and retrieval["context_chars"] <= 8000
    assert retrieval["context_chars"] == len(json.dumps(retrieval, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    reopened = loop_for(setup)
    assert reopened.status()["active_version"] == record["id"]
    assert reopened.rollback(expected_version=record["id"], human_approved=True, reviewer="fixture owner")["active_version"] == original
    assert reopened.status()["candidates"][record["id"]] == "rolled_back"
    assert reopened.retrieve("Where is login?")["records"] == []
    journal = [json.loads(line) for line in reopened.journal.read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in journal] == ["baseline", "candidate", "evaluated", "reviewed", "active", "rolled_back"]


def test_review_and_activation_require_separate_explicit_owner_action(setup):
    loop = loop_for(setup)
    record = passing(loop)
    with pytest.raises(PermissionError):
        loop.review(record["id"], evaluation_digest=record["evaluation_digest"])
    with pytest.raises(PermissionError):
        loop.activate(record["id"], evaluation_digest=record["evaluation_digest"], human_approved=True, reviewer="owner")
    with pytest.raises(PermissionError):
        loop.review(record["id"], evaluation_digest="forged", human_approved=True, reviewer="owner")
    assert loop.status()["candidates"][record["id"]] == "evaluated"


def test_changed_source_blocks_review_and_stale_proposal(setup):
    loop = loop_for(setup)
    record = passing(loop)
    (setup[1] / "auth.md").write_text("Changed source", encoding="utf-8")
    with pytest.raises(PermissionError):
        approve_and_activate(loop, record)
    pending = loop.propose_aliases({"login": ["authenticate"]})
    (setup[1] / "auth.md").write_text("Changed a second time", encoding="utf-8")
    with pytest.raises(RuntimeError, match="snapshot changed"):
        loop.evaluate(pending["id"])


def test_mutation_during_benchmark_leaves_no_evaluated_record(setup):
    original = setup[2]["sources"]["graphify"]
    count = 0

    def mutating(question, limit):
        nonlocal count
        count += 1
        (setup[1] / "auth.md").write_text(str(count), encoding="utf-8")
        return original(question, limit)

    loop = loop_for(setup, sources={"graphify": mutating})
    candidate = loop.propose_aliases({"login": ["authenticate"]})
    with pytest.raises(RuntimeError, match="during evaluation"):
        loop.evaluate(candidate["id"])
    assert loop.status()["candidates"][candidate["id"]] == "candidate"


def test_candidate_with_equal_quality_and_no_measurable_gain_stays_off(setup):
    loop = loop_for(setup, limits=Limits(minimum_latency_gain_ms=10000))
    record = loop.evaluate(loop.propose_aliases({"unused": ["authenticate"]})["id"])
    assert not record["evaluation"]["allowed"]
    assert record["evaluation"]["reasons"] == ["No measurable improvement"]
    with pytest.raises(PermissionError):
        approve_and_activate(loop, record)


def test_recipe_reuses_reviewed_knowledge_and_fixed_expected_tool_fixture(setup):
    tmp, _, args = setup
    knowledge = KnowledgeStore(tmp / "knowledge")
    try:
        note_id = knowledge.add_note(project="STAR", kind="decision", text="project settings use gold navigation",
                                     source="project.md", revision="fixture")
        knowledge.review_note(project="STAR", note_id=note_id, evidence="Independent owner fixture")
        knowledge.add_note(project="Other", kind="decision", text="project settings candidate private secret",
                           source="project.md", revision="fixture")

        def reviewed_source(question, limit):
            return [Evidence(str(n.id), n.source, n.text, "reviewed_reference")
                    for n in knowledge.find_ranked("STAR", question, reviewed_only=True, limit=limit)]

        # This fixture tests the knowledge primitive and operational tool success,
        # while retaining graph retrieval and the no-results negative fixture.
        cases = args["cases"][1:] + (Fixture("PROJECT", "project settings", ("project.md",), expected_tool_sources=("knowledge",)),)
        # A steady fake clock (+1 ms per reading): wall-clock latency on a cold start could trip the latency cap
        # and make this test flaky; latency is not what it tests.
        ticks = iter(range(10**6))
        loop = loop_for(setup, cases=cases, sources={**args["sources"], "knowledge": reviewed_source},
                        clock=lambda: next(ticks) / 1000)
        proposed = loop.propose_recipe({"name": "project-research", "description": "Read reviewed project decisions and graph entities",
                                       "steps": [{"source": "graphify", "limit": 5}, {"source": "knowledge", "limit": 2}]})
        record = loop.evaluate(proposed["id"])
        assert record["evaluation"]["allowed"], record["evaluation"]
        assert record["evaluation"]["baseline"]["PROJECT"]["tool_success"] is False
        assert record["evaluation"]["candidate_results"]["PROJECT"]["tool_success"] is True
        approve_and_activate(loop, record)
        # A retrieval configuration cannot mark any note or recipe approved.
        assert knowledge.db.execute("SELECT reviewed FROM notes WHERE project='Other'").fetchone()[0] == 0
    finally:
        knowledge.close()


@pytest.mark.parametrize("recipe", [
    {"name": "unsafe-tool", "description": "Try to execute an arbitrary expression", "steps": [{"source": "graphify", "code": "eval('1')"}]},
    {"name": "unsafe-tool", "description": "Try to acquire an unconfigured source", "steps": [{"source": "workspace"}]},
    {"name": "unsafe-tool", "description": "Try to run an arbitrary command", "steps": [{"source": "shell"}]},
])
def test_recipe_never_accepts_code_commands_or_new_permissions(setup, recipe):
    loop = loop_for(setup)
    with pytest.raises(Exception):
        loop.propose_recipe(recipe)
    assert loop.status()["candidates"] == {}


def test_aliases_cannot_invent_vocabulary_or_dynamic_expressions(setup):
    loop = loop_for(setup)
    for aliases in ({"login": ["made-up"]}, {"login": ["eval(1)"]}, {"login": "authenticate"}, {"../policy": ["authenticate"]}):
        with pytest.raises(ValueError):
            loop.propose_aliases(aliases)
    assert loop.status()["candidates"] == {}


@pytest.mark.parametrize("path", ["star/policy.py", "tests/test_eval_gate.py", "evals/roblox/fixtures.json", "star/skills/__init__.py", "star/skills/../../auth.py"])
def test_code_registration_cannot_edit_policy_fixtures_or_registration(setup, path):
    loop = loop_for(setup)
    with pytest.raises(ValueError):
        loop.register_code(path=path, source="pass", commit="a" * 40)


def test_generated_code_only_compiles_and_is_never_evaluated_or_activated(setup):
    loop = loop_for(setup)
    generated = "raise AssertionError('GENERATED CODE MUST NEVER EXECUTE')\n"
    record = loop.register_code(path="star/skills/example.py", source=generated, commit="a" * 40)
    assert record["verification"] == "syntax only; behavior not executed or verified"
    assert generated not in loop.journal.read_text(encoding="utf-8")
    with pytest.raises(PermissionError):
        loop.evaluate(record["id"])
    with pytest.raises(SyntaxError):
        loop.register_code(path="star/skills/broken.py", source="if", commit="a" * 40)


def test_context_growth_blocks_a_correctness_gain(setup):
    original = setup[2]["sources"]["graphify"]

    def bloated(question, limit):
        result = original(question, limit)
        return [replace(e, text=e.text + "x" * 550) if e.source == "auth.md" else e for e in result]

    loop = loop_for(setup, sources={"graphify": bloated})
    record = loop.evaluate(loop.propose_aliases({"login": ["authenticate"]})["id"])
    assert not record["evaluation"]["allowed"]
    assert any("context cap" in reason for reason in record["evaluation"]["reasons"])


def test_latency_cap_blocks_correctness_gain_with_trusted_clock(setup):
    class Clock:
        value = 0.
        def __call__(self):
            return self.value

    clock = Clock()
    original = setup[2]["sources"]["graphify"]

    def slow(question, limit):
        clock.value += .025 if "authenticate" in question else .002
        return original(question, limit)

    loop = loop_for(setup, sources={"graphify": slow}, clock=clock, limits=Limits(latency_ms=20))
    record = loop.evaluate(loop.propose_aliases({"login": ["authenticate"]})["id"])
    assert not record["evaluation"]["allowed"]
    assert any("latency cap" in reason for reason in record["evaluation"]["reasons"])


def test_per_fixture_regression_blocks_even_with_another_improvement(setup):
    original = setup[2]["sources"]["graphify"]

    def changed(question, limit):
        if "registry" in question and "authenticate" in question:
            return []
        return original(question, limit)

    loop = loop_for(setup, sources={"graphify": changed})
    record = loop.evaluate(loop.propose_aliases({"login": ["authenticate"], "registry": ["authenticate"]})["id"])
    assert not record["evaluation"]["allowed"]
    assert "REGISTRY: correct regressed" in record["evaluation"]["reasons"]
    assert "AUTH: correct improved" in record["evaluation"]["wins"]


def test_baseline_source_errors_are_incomplete_not_a_quality_win(setup):
    original = setup[2]["sources"]["graphify"]

    def failure(question, limit):
        if "login" in question and "authenticate" not in question:
            raise OSError("sensitive error text must never enter the journal")
        return original(question, limit)

    loop = loop_for(setup, sources={"graphify": failure})
    record = loop.evaluate(loop.propose_aliases({"login": ["authenticate"]})["id"])
    assert not record["evaluation"]["allowed"]
    assert "sensitive error text" not in loop.journal.read_text(encoding="utf-8")
    assert any("baseline source failure" in r for r in record["evaluation"]["reasons"])


def test_unverified_or_cross_project_evidence_is_rejected(setup):
    for evidence in (Evidence("fake", "auth.md", "model candidate", "candidate"),
                     Evidence("foreign", "../OtherProject/secret.md", "foreign source")):
        loop = ImprovementLoop(setup[0] / evidence.identifier, **{**setup[2], "sources": {"graphify": lambda q, n: [evidence]}})
        record = loop.evaluate(loop.propose_aliases({"login": ["authenticate"]})["id"])
        assert not record["evaluation"]["allowed"]


def test_journal_damage_and_changed_fixture_suite_fail_closed(setup):
    loop = loop_for(setup)
    passing(loop)
    with pytest.raises(ValueError, match="different fixture"):
        loop_for(setup, cases=(Fixture("AUTH", "Different fixture query", ("auth.md",)),))
    content = loop.journal.read_text(encoding="utf-8").replace('"kind":"candidate"', '"kind":"active"', 1)
    loop.journal.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        loop.status()


def test_source_escape_and_simultaneous_writer_are_rejected(setup):
    with pytest.raises(ValueError):
        loop_for(setup, source_files=("../foreign.md",))
    loop = loop_for(setup)
    (loop.home / ".improvements.lock").write_text("another host action", encoding="utf-8")
    with pytest.raises(RuntimeError, match="in use"):
        loop.propose_aliases({"login": ["authenticate"]})


def test_a_second_previously_reviewed_candidate_cannot_replace_new_baseline(setup):
    loop = loop_for(setup)
    first, second = passing(loop), passing(loop)
    kwargs = dict(evaluation_digest=second["evaluation_digest"], human_approved=True, reviewer="owner")
    loop.review(second["id"], **kwargs)
    approve_and_activate(loop, first)
    with pytest.raises(PermissionError, match="baseline"):
        loop.activate(second["id"], **kwargs)
    with pytest.raises(PermissionError):
        loop.rollback(expected_version=second["id"], human_approved=True, reviewer="owner")


def test_identical_files_in_another_project_cannot_reuse_the_journal(setup):
    loop = loop_for(setup)
    other = setup[0] / "other-project"
    other.mkdir()
    for path in setup[1].iterdir():
        (other / path.name).write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="different fixture"):
        loop_for(setup, source_root=other)
    assert loop.status()["active_version"].startswith("baseline-")


def test_efficiency_on_incorrect_answers_cannot_unlock_promotion(setup):
    def irrelevant(question, limit):
        return [Evidence("noise-" + str(i), "registry.md", "irrelevant result " * 10) for i in range(limit)]

    loop = loop_for(setup, cases=(Fixture("AUTH", "login", ("auth.md",)),),
                    sources={"graphify": irrelevant}, limits=Limits(minimum_latency_gain_ms=10000))
    candidate = loop.propose_recipe({"name": "thin-results", "description": "Read fewer configured graph results",
                                     "steps": [{"source": "graphify", "limit": 1}]})
    record = loop.evaluate(candidate["id"])
    assert record["evaluation"]["baseline"]["AUTH"]["correct"] is False
    assert record["evaluation"]["candidate_results"]["AUTH"]["correct"] is False
    assert record["evaluation"]["baseline"]["AUTH"]["context_chars"] > record["evaluation"]["candidate_results"]["AUTH"]["context_chars"]
    assert not record["evaluation"]["allowed"] and record["evaluation"]["wins"] == []


def test_mutable_input_fixture_lists_are_copied_before_digest_and_evaluation(setup):
    expected, forbidden, expected_tools = ["auth.md"], [], []
    fixture = Fixture("AUTH", "login", expected, forbidden, expected_tools)
    loop = loop_for(setup, cases=(fixture,))
    suite = loop.suite_digest
    candidate = loop.propose_aliases({"login": ["authenticate"]})
    expected[:] = ["registry.md"]
    forbidden[:] = ["auth.md"]
    expected_tools[:] = ["knowledge"]
    record = loop.evaluate(candidate["id"])
    assert loop.suite_digest == suite and loop.cases[0].expected_sources == ("auth.md",)
    assert record["evaluation"]["allowed"]


def test_parent_symlinks_and_journal_symlinks_are_never_followed(setup):
    tmp, root, args = setup
    linked = root / "linked"
    outside = tmp / "outside"
    outside.mkdir()
    (outside / "reference.md").write_text("Out of project", encoding="utf-8")
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("This Windows account cannot create symlinks")
    with pytest.raises(PermissionError, match="symlink"):
        loop_for(setup, source_files=("linked/reference.md",), cases=(Fixture("LINK", "reference", ("linked/reference.md",)),))
    loop = loop_for(setup)
    old = loop.journal
    target = tmp / "foreign-journal"
    target.write_bytes(old.read_bytes())
    old.unlink()
    old.symlink_to(target)
    with pytest.raises(PermissionError, match="symlink"):
        loop.status()


def test_small_response_budget_drops_records_then_refuses_oversized_metadata(setup):
    loop = loop_for(setup, limits=Limits(context_chars=256))
    response = loop.retrieve("Where is registry?")
    assert len(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) <= 256
    with pytest.raises(ValueError, match="metadata exceeds"):
        loop.retrieve("registry " * 50)


def test_optional_existing_gate_is_reused_without_overriding_metric_requirements(setup):
    import importlib.util
    record = passing(loop_for(setup))
    if importlib.util.find_spec("star.eval_gate") is not None:
        assert record["evaluation"]["existing_gate"]["allowed"]
        assert record["evaluation"]["existing_gate"]["improvements"] == ["AUTH"]
    else:
        assert record["evaluation"]["existing_gate"] is None


def test_host_fixture_change_invalidates_digest_before_promotion(setup):
    loop = loop_for(setup)
    record = passing(loop)
    loop.cases = (Fixture("AUTH", "login", ("registry.md",)),)
    with pytest.raises(ValueError, match="Independent fixtures"):
        approve_and_activate(loop, record)


def test_parent_link_check_fails_before_source_reads_without_windows_privileges(setup, monkeypatch):
    directory = setup[1] / "references"
    directory.mkdir()
    (directory / "guide.md").write_text("A guide", encoding="utf-8")
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == directory or original(path))
    with pytest.raises(PermissionError, match="symlink"):
        loop_for(setup, source_files=("references/guide.md",), cases=(Fixture("GUIDE", "guide", ("references/guide.md",)),))


def test_wrong_helper_from_expected_module_is_a_regression(setup):
    original = setup[2]["sources"]["graphify"]

    def wrong_helper(question, limit):
        rows = original(question, limit)
        return [replace(e, identifier="wrong_helper") if e.source == "registry.md" and "authenticate" in question else e for e in rows]

    loop = loop_for(setup, sources={"graphify": wrong_helper})
    record = loop.evaluate(loop.propose_aliases({"login": ["authenticate"], "registry": ["authenticate"]})["id"])
    assert record["evaluation"]["candidate_results"]["REGISTRY"]["sources"] == ["auth.md", "registry.md"]
    assert "registry" not in record["evaluation"]["candidate_results"]["REGISTRY"]["identifiers"]
    assert "REGISTRY: correct regressed" in record["evaluation"]["reasons"]
    assert not record["evaluation"]["allowed"]


def test_verifier_file_change_after_evaluation_blocks_promotion(setup):
    loop = loop_for(setup)
    record = passing(loop)
    copied = setup[0] / "controller-source.py"
    copied.write_bytes(loop._verifier_files["controller"].read_bytes())
    loop._verifier_files["controller"] = copied
    assert loop._current_verifier_digest() == loop.verifier_digest
    copied.write_text("# Changed independent verifier\n", encoding="utf-8")
    with pytest.raises(ValueError, match="verifier code changed"):
        approve_and_activate(loop, record)


def test_expected_source_and_identifier_cannot_be_satisfied_by_mismatched_records(setup):
    original = setup[2]["sources"]["graphify"]

    def mismatched(question, limit):
        records = original(question, limit)
        if "registry" in question and "authenticate" in question:
            records = [replace(e, source="auth.md") if e.identifier == "registry" else e for e in records]
            records.append(Evidence("decoy", "registry.md", "A different helper from the expected module."))
        return records[:limit]

    loop = loop_for(setup, sources={"graphify": mismatched}, limits=Limits(context_ratio=10))
    record = loop.evaluate(loop.propose_aliases({"login": ["authenticate"], "registry": ["authenticate"]})["id"])
    score = record["evaluation"]["candidate_results"]["REGISTRY"]
    # The old independent set checks both passed for these records.
    assert "registry.md" in score["sources"] and "registry" in score["identifiers"]
    assert {"source": "auth.md", "identifier": "registry"} in score["evidence"]
    assert {"source": "registry.md", "identifier": "decoy"} in score["evidence"]
    assert {"source": "registry.md", "identifier": "registry"} not in score["evidence"]
    assert record["evaluation"]["baseline"]["REGISTRY"]["correct"]
    assert not score["correct"] and not record["evaluation"]["allowed"]
    assert "REGISTRY: correct regressed" in record["evaluation"]["reasons"]


def test_explicit_pairs_catch_identifiers_swapped_between_expected_modules(setup):
    expected = (("auth.md", "authenticate"), ("registry.md", "registry"))
    fixture = Fixture("PAIRS", "helpers", ("auth.md", "registry.md"),
                      expected_identifiers=("authenticate", "registry"), expected_evidence=expected)

    def paired(question, limit):
        sources = ("auth.md", "registry.md") if "authenticate" in question else ("registry.md", "auth.md")
        return [Evidence(identifier, source, "Source-backed helper")
                for identifier, source in zip(("authenticate", "registry"), sources)][:limit]

    loop = loop_for(setup, cases=(fixture,), sources={"graphify": paired})
    record = loop.evaluate(loop.propose_aliases({"helpers": ["authenticate"]})["id"])
    before, after = record["evaluation"]["baseline"]["PAIRS"], record["evaluation"]["candidate_results"]["PAIRS"]
    assert set(before["sources"]) == set(after["sources"]) == set(fixture.expected_sources)
    assert set(before["identifiers"]) == set(after["identifiers"]) == set(fixture.expected_identifiers)
    assert not before["correct"] and after["correct"] and record["evaluation"]["allowed"]
    assert {(e["source"], e["identifier"]) for e in after["evidence"]} == set(expected)


def test_nested_mutable_expected_pairs_are_copied_and_digest_bound(setup):
    pairs = [["auth.md", "authenticate"]]
    fixture = Fixture("PAIR", "login", (), expected_evidence=pairs)
    loop = loop_for(setup, cases=(fixture,))
    candidate = loop.propose_aliases({"login": ["authenticate"]})
    pairs[0][:] = ["registry.md", "registry"]
    pairs.append(["project.md", "foreign"])
    assert loop.cases[0].expected_evidence == (("auth.md", "authenticate"),)
    record = loop.evaluate(candidate["id"])
    assert record["evaluation"]["allowed"]
    loop.cases = (replace(loop.cases[0], expected_evidence=(("registry.md", "registry"),)),)
    with pytest.raises(ValueError, match="Independent fixtures"):
        approve_and_activate(loop, record)


@pytest.mark.parametrize("pairs", [(('other-project.md', 'foreign'),), (('auth.md', ''),), (('auth.md', 'authenticate', 'extra'),)])
def test_expected_pairs_need_an_in_scope_source_and_bounded_identifier(setup, pairs):
    with pytest.raises(ValueError, match="Invalid fixture"):
        loop_for(setup, cases=(Fixture("PAIR", "login", (), expected_evidence=pairs),))


def test_oversized_candidate_append_is_refused_without_changing_journal(setup, monkeypatch):
    from star.shared_brain import improve
    loop = loop_for(setup)
    original = loop.journal.read_bytes()
    monkeypatch.setattr(improve, "MAX_JOURNAL_BYTES", len(original) + 1)
    with pytest.raises(ValueError, match="journal budget exhausted"):
        loop.propose_aliases({"login": ["authenticate"]})
    assert loop.journal.read_bytes() == original
    assert loop.status()["candidates"] == {}


def test_proposal_budget_preserves_space_for_owner_rollback(setup, monkeypatch):
    from star.shared_brain import improve
    loop = loop_for(setup)
    record = passing(loop)
    previous = approve_and_activate(loop, record)["previous_version"]
    cap = loop.journal.stat().st_size + improve.JOURNAL_CONTROL_RESERVE + 1
    monkeypatch.setattr(improve, "MAX_JOURNAL_BYTES", cap)
    with pytest.raises(ValueError, match="journal budget exhausted"):
        loop.propose_aliases({"login": ["authenticate"]})
    result = loop.rollback(expected_version=record["id"], human_approved=True, reviewer="fixture owner")
    assert result["active_version"] == previous and loop.journal.stat().st_size < cap
    assert loop.status()["candidates"][record["id"]] == "rolled_back"


def test_changed_home_link_is_refused_before_creating_a_lock(setup, monkeypatch):
    from star.shared_brain import improve
    loop = loop_for(setup)
    original_link, original_open = Path.is_symlink, improve.os.open
    opened = []
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == loop.home or original_link(path))
    def record_open(*args, **kwargs):
        opened.append(args[0])
        return original_open(*args, **kwargs)
    monkeypatch.setattr(improve.os, "open", record_open)
    with pytest.raises(PermissionError, match="symlink"):
        loop.status()
    assert opened == []


@pytest.mark.parametrize("blocked_kind", ("source_parent", "home_parent", "journal"))
def test_windows_reparse_attributes_block_paths_without_python312_api(setup, monkeypatch, blocked_kind):
    from types import SimpleNamespace
    from star.shared_brain import improve

    loop = loop_for(setup)
    blocked = {"source_parent": loop.root, "home_parent": loop.home, "journal": loop.journal}[blocked_kind]
    original_lstat, original_open = Path.lstat, Path.open
    opened = []
    # Simulate Python 3.11: the junction API is absent and a junction is not a
    # symbolic link, but lstat still reports its Windows reparse attribute.
    monkeypatch.delattr(Path, "is_junction", raising=False)
    monkeypatch.setattr(Path, "is_symlink", lambda path: False)
    monkeypatch.setattr(improve.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400, raising=False)

    def reparse_lstat(path):
        result = original_lstat(path)
        if path == blocked:
            return SimpleNamespace(st_file_attributes=getattr(result, "st_file_attributes", 0)
                                   | improve.stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return result

    def record_open(path, *args, **kwargs):
        opened.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", reparse_lstat)
    monkeypatch.setattr(Path, "open", record_open)
    with pytest.raises(PermissionError, match="symlink|junction"):
        loop._snapshot() if blocked_kind == "source_parent" else loop.status()
    assert opened == []
