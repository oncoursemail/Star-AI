"""Offline proof of reviewed-example validation; no fine-tuning is performed."""
import hashlib
import json

import pytest
from star.roblox_training import main, split_examples, validate_example


def example(index, group=None):
    return {
        "id": f"scene_{index:03}",
        "group_id": group or f"scene_{index:03}",
        "category": "luau",
        "instruction": f"Write and explain server-side validation of a Roblox RemoteEvent for case {index}.",
        "response": f"--!strict\n-- Reviewed example {index}\nUse typeof checks, a range clamp and server-side authorization.",
        "reviewed": True,
        "rights_confirmed": True,
        "evidence": [f"studio-test-{index}"],
    }


def test_reviewed_training_data_keeps_holdout_separate_and_deterministic():
    rows = [example(i) for i in range(60)]
    first = split_examples(rows)
    again = split_examples(rows)
    assert first == again
    assert first["counts"]["supplied"] == 60
    assert first["train"] and first["evaluation"]
    assert first["counts"]["train"] + first["counts"]["evaluation"] == 60
    assert all("messages" in row for row in first["train"])
    assert all("expected" in row for row in first["evaluation"])
    assert "training" in first["note"].lower()


def test_related_variants_share_train_or_holdout_group():
    a = example(1, group="paired_design")
    b = example(2, group="paired_design")
    combined = split_examples([a, b])
    assert len(combined["train"]) in {0, 2}
    assert len(combined["evaluation"]) in {0, 2}


def test_unreviewed_or_unlicensed_examples_rejected():
    for key in ("reviewed", "rights_confirmed"):
        row = example(5)
        row[key] = False
        with pytest.raises(ValueError):
            validate_example(row)


def test_private_credentials_or_bad_evidence_rejected():
    row = example(5)
    row["response"] += "\nYour token is ghp_abcdefghijklmnopqrstuvwxyz12345"
    with pytest.raises(ValueError):
        validate_example(row)
    row = example(5)
    row["evidence"] = []
    with pytest.raises(ValueError):
        validate_example(row)


def test_duplicate_ids_or_identical_examples_fail():
    rows = [example(1), example(1)]
    with pytest.raises(ValueError):
        split_examples(rows)
    twin = example(2)
    twin["instruction"] = rows[0]["instruction"]
    twin["response"] = rows[0]["response"]
    with pytest.raises(ValueError):
        split_examples([rows[0], twin])


def test_missing_group_id_or_illegal_category_rejected():
    row = example(12)
    row.pop("group_id")
    with pytest.raises(ValueError):
        validate_example(row)
    row = example(12)
    row["category"] = "secret-auto-actions"
    with pytest.raises(ValueError):
        validate_example(row)


def group_for_split(evaluation, *, exclude=()):
    """Find stable, different IDs on either side of the existing hash split."""
    for i in range(200):
        group = f"bucket_{i:03}"
        bucket = int(hashlib.sha256(group.encode("utf-8")).hexdigest(), 16) % 100
        if group not in exclude and (bucket < 20) is evaluation:
            return group
    raise AssertionError("Could not find a deterministic group for this split")


@pytest.mark.parametrize("same_bucket", [True, False], ids=["same-split", "cross-split"])
@pytest.mark.parametrize("same_answer", [True, False], ids=["same-answer", "conflicting-answer"])
def test_normalized_instructions_cannot_appear_in_different_groups(same_bucket, same_answer):
    train_group = group_for_split(False)
    other_group = group_for_split(False if same_bucket else True, exclude={train_group})
    first = example(501, group=train_group)
    second = example(502, group=other_group)
    # Case changes, line breaks and repeated spaces must not bypass the collision gate.
    second["instruction"] = "\n  ".join(first["instruction"].upper().split())
    if same_answer:
        second["response"] = first["response"]

    with pytest.raises(ValueError, match="different groups"):
        split_examples([first, second])


def test_same_group_may_contain_related_variants_without_split_leakage():
    for held_out in (False, True):
        group = group_for_split(held_out)
        first = example(601, group=group)
        variant = example(602, group=group)
        variant["instruction"] = "\t".join(first["instruction"].upper().split())
        # Different reviewed solutions in one explicitly related group remain together.
        result = split_examples([first, variant])
        assert (len(result["train"]), len(result["evaluation"])) == (
            (0, 2) if held_out else (2, 0)
        )


def test_normalized_repeated_example_in_one_group_is_still_rejected():
    first = example(603)
    repeated = example(604, group=first["group_id"])
    repeated["instruction"] = "  ".join(first["instruction"].upper().split())
    repeated["response"] = first["response"]
    with pytest.raises(ValueError, match="Duplicate instruction/answer"):
        split_examples([first, repeated])


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("id", "x"), ("id", "bad/id"), ("group_id", "xx"),
        ("group_id", []), ("category", "unreviewed"), ("category", ["luau"]),
        ("reviewed", 1), ("rights_confirmed", "true"),
        ("evidence", None), ("evidence", []), ("evidence", "studio-test"),
        ("evidence", [10]), ("evidence", ["   "]),
        ("evidence", ["e" * 201]), ("evidence", ["test"] * 11),
        ("instruction", "  \t  "), ("response", " \n "),
        ("instruction", "a" * 12001), ("response", "b" * 32001),
    ],
    ids=[
        "short-id", "unsafe-id", "short-group", "non-string-group",
        "invalid-category", "unhashable-category", "unreviewed", "unconfirmed-rights",
        "missing-evidence", "empty-evidence", "non-list-evidence",
        "non-string-evidence", "whitespace-only-evidence", "oversized-evidence",
        "too-many-evidence-references", "empty-instruction", "empty-response",
        "oversized-instruction", "oversized-response",
    ],
)
def test_invalid_review_metadata_and_content_raise_value_error(field, invalid):
    row = example(605)
    row[field] = invalid
    with pytest.raises(ValueError):
        validate_example(row)


@pytest.mark.parametrize("rows", [{}, [example(1)] * 5001])
def test_invalid_dataset_container_or_size_rejected(rows):
    with pytest.raises(ValueError, match="at most 5000"):
        split_examples(rows)


@pytest.mark.parametrize("holdout", [0, 4, 41, 20.0, "20", None])
def test_invalid_holdout_percent_rejected(holdout):
    with pytest.raises(ValueError, match="5..40"):
        split_examples([example(1)], holdout_percent=holdout)


def test_main_exports_unchanged_train_eval_and_report_contract(tmp_path, capsys):
    training = example(701, group=group_for_split(False))
    evaluation = example(702, group=group_for_split(True))
    source = tmp_path / "reviewed.json"
    output = tmp_path / "exports"
    source.write_text(json.dumps([training, evaluation]), encoding="utf-8")

    assert main(["--input", str(source), "--output-dir", str(output)]) == 0
    train = [json.loads(line) for line in (output / "roblox_train.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()]
    held_out = [json.loads(line) for line in (output / "roblox_eval.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()]
    report = json.loads((output / "roblox_dataset_report.json").read_text(encoding="utf-8"))
    assert len(train) == len(held_out) == 1
    assert train[0]["messages"][1] == {"role": "user", "content": training["instruction"]}
    assert train[0]["messages"][2] == {"role": "assistant", "content": training["response"]}
    assert held_out == [{
        "id": evaluation["id"], "category": evaluation["category"],
        "input": evaluation["instruction"], "expected": evaluation["response"],
    }]
    assert all("expected" not in row for row in train)
    assert report["counts"] == {"supplied": 2, "train": 1, "evaluation": 1}
    assert report["holdout_percent"] == 20
    assert json.loads(capsys.readouterr().out) == report


def test_main_rejects_cross_group_collision_before_creating_files(tmp_path):
    first = example(711, group=group_for_split(False))
    second = example(712, group=group_for_split(True))
    second["instruction"] = first["instruction"]
    source = tmp_path / "collision.json"
    output = tmp_path / "exports"
    source.write_text(json.dumps([first, second]), encoding="utf-8")

    with pytest.raises(ValueError, match="different groups"):
        main(["--input", str(source), "--output-dir", str(output)])
    assert not output.exists()


def test_main_does_not_overwrite_reviewed_export(tmp_path):
    source = tmp_path / "reviewed.json"
    source.write_text(json.dumps([
        example(721, group=group_for_split(False)),
        example(722, group=group_for_split(True)),
    ]), encoding="utf-8")
    output = tmp_path / "exports"
    output.mkdir()
    existing = output / "roblox_train.jsonl"
    existing.write_text("previous-reviewed-content", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["--input", str(source), "--output-dir", str(output)])
    assert error.value.code == 2
    assert existing.read_text(encoding="utf-8") == "previous-reviewed-content"
    assert not (output / "roblox_eval.jsonl").exists()
