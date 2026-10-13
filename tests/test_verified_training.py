"""Verified Luau examples require independent tests, rights and sealed project splits."""
import hashlib
import json
from dataclasses import replace

import pytest

from star import verified_training as train


def example(i, project="project-a", *, origin="star_generated", license="owned-original"):
    return train.Example(
        id=f"case-{project}-{i}", project=project,
        prompt=f"Write server-owned Luau routine for unique feature {project} {i}",
        answer=f"local function feature{i}(value) return value + {i} end\nreturn feature{i}",
        origin=origin, license=license, model="owner-reviewed-code-model",
        rights_reviewed=True, owner_consented=True,
    )


def receipt(item):
    return train.TestReceipt(
        id=item.id, project=item.project,
        answer_sha256=train.sha(item.answer), runner="isolated_luau_sandbox",
        run_id=f"run-{item.id}", evidence_sha256="a" * 64,
        test_suite_sha256="b" * 64, executed=3, failed=0, status="passed",
    )


def fence():
    return train.HoldoutFence(
        excluded_projects=frozenset({"protected-project"}),
        excluded_prompt_digests=frozenset({train.sha("protected prompt")}),
        suite_sha256="d" * 64,
    )


def training_inputs():
    samples = [example(i, project=p) for p in
               ("a", "b", "c", "d", "e") for i in range(5)]
    return samples, {x.id: receipt(x) for x in samples}


def test_validated_examples_split_by_project_and_are_never_trained():
    items, receipts = training_inputs()
    result = train.curate(items, receipts, fence(), model_license_reviewed=True)
    assert result["accepted"] == 25
    assert result["ready_for_owner_training_review"]
    assert result["trained"] is False
    assert len(result["splits"]["train"]) == 15
    assert len(result["splits"]["test"]) == 5
    assert len(result["splits"]["validation"]) == 5
    projects = [set(x["project"] for x in result["splits"][p])
                for p in ("train", "validation", "test")]
    assert not projects[0] & projects[1]
    assert not projects[1] & projects[2]
    assert not projects[0] & projects[2]


def test_no_rights_assumption_from_a_generated_response():
    item = example(0)
    for modified in (
        replace(item, owner_consented=False),
        replace(item, rights_reviewed=False),
        replace(item, license="unknown"),
        replace(item, source_path="evals/roblox/hidden.json"),
        replace(item, prompt="token = '1234567890abcdef' " + item.prompt),
    ):
        with pytest.raises((PermissionError, ValueError)):
            modified.validate()
    with pytest.raises(PermissionError):
        train.curate([item], {item.id: receipt(item)}, fence())


def test_rejects_forged_unexecuted_or_mismatched_receipt():
    item = example(0)
    valid = receipt(item)
    for changed in (replace(valid, failed=1), replace(valid, executed=0),
                    replace(valid, status="not_run"), replace(valid, runner="model_claim"),
                    replace(valid, answer_sha256="0" * 64)):
        if changed.answer_sha256 != valid.answer_sha256:
            # The shape can pass validation but must fail answer matching.
            changed.validate()
        else:
            with pytest.raises(ValueError):
                changed.validate()
        result = train.curate([item], {item.id: changed}, fence(), model_license_reviewed=True)
        assert result["accepted"] == 0
        assert not result["ready_for_owner_training_review"]


def test_frozen_holdout_and_duplicate_prompt_contamination_are_excluded():
    heldout = example(1, project="protected-project")
    question = replace(example(2, project="other-project"),
                       prompt="protected prompt")
    original = example(3, project="project-a")
    duplicated = replace(example(10, project="project-b"), prompt=original.prompt)
    items = [heldout, question, original, duplicated]
    result = train.curate(items, {x.id: receipt(x) for x in items},
                          fence(), model_license_reviewed=True)
    assert result["accepted"] == 1
    assert result["rejected"]["holdout_contamination"] == 2
    assert result["rejected"]["duplicate"] == 1
    assert not result["ready_for_owner_training_review"]


def test_fence_is_mandatory_and_cannot_use_heldout_test_suite():
    x = example(0)
    no_fence = train.HoldoutFence(frozenset(), frozenset(), "c" * 64)
    with pytest.raises(ValueError):
        train.curate([x], {x.id: receipt(x)}, no_fence, model_license_reviewed=True)
    same_suite = replace(receipt(x), test_suite_sha256="d" * 64)
    result = train.curate([x], {x.id: same_suite}, fence(), model_license_reviewed=True)
    assert result["accepted"] == 0
    assert result["rejected"]["holdout_contamination"] == 1


def test_reviewed_private_export_is_explicit_and_no_overwrite(tmp_path):
    items, receipts = training_inputs()
    data = train.curate(items, receipts, fence(), model_license_reviewed=True)
    with pytest.raises(PermissionError):
        train.export_private(data, tmp_path)
    assert not (tmp_path / "training").exists()
    saved = train.export_private(data, tmp_path, approved=True)
    assert saved["exported"] and saved["training_started"] is False
    assert saved["model_weights_changed"] is False
    folder = tmp_path / "training" / "verified"
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["format"] == "star-verified-luau-sft-v1"
    assert manifest["files"]["train"]["examples"] == 15
    assert len((folder / "train.jsonl").read_text().splitlines()) == 15
    with pytest.raises(FileExistsError):
        train.export_private(data, tmp_path, approved=True)
    assert not any("sk-" in p.read_text() for p in folder.iterdir() if p.is_file())


def test_tiny_dataset_is_quarantined_and_not_trainable():
    x = example(0)
    result = train.curate([x], {x.id: receipt(x)}, fence(), model_license_reviewed=True)
    assert result["accepted"] == 1
    assert result["splits"]["quarantine"]
    assert not result["ready_for_owner_training_review"]
