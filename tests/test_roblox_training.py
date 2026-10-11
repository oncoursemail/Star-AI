"""Offline proof of reviewed-example validation; no fine-tuning is performed."""
import pytest
from star.roblox_training import split_examples, validate_example


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
