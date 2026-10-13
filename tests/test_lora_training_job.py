"""QLoRA pilot preflight is offline and does not import GPU stacks until approved."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

from star import lora_training_job as lora
from star import verified_training as train


def source_data(tmp_path):
    examples = []
    for project in "abcde":
        for i in range(5):
            examples.append(train.Example(
                id=f"example-{project}-{i}", project=project,
                prompt=f"Create a Luau function for project {project}, unique task {i}",
                answer=f"local function task{i}(n) return n + {i} end\nreturn task{i}",
                origin="owner_original", license="owned-original",
                model="verified-local-code-model", rights_reviewed=True,
                owner_consented=True))
    evidence = {e.id: train.TestReceipt(
        id=e.id, project=e.project, answer_sha256=train.sha(e.answer),
        runner="isolated_luau_sandbox", run_id=f"case-{e.id}",
        evidence_sha256="a" * 64, test_suite_sha256="b" * 64,
        executed=2, failed=0, status="passed") for e in examples}
    holdout = train.HoldoutFence(frozenset({"heldout"}),
                                 frozenset({train.sha("protected query")}), "d" * 64)
    reviewed = train.curate(examples, evidence, holdout, model_license_reviewed=True)
    assert reviewed["ready_for_owner_training_review"]
    train.export_private(reviewed, tmp_path, approved=True)


def local_model(tmp_path):
    path = tmp_path / "local-qwen"
    path.mkdir()
    (path / "config.json").write_text(json.dumps({"architectures": ["Qwen2ForCausalLM"]}))
    (path / "tokenizer_config.json").write_text("{}")
    (path / "weights.safetensors").write_bytes(b"dummy safety preflight only")
    return path


def test_approved_pilot_plan_is_offline_and_no_cuda_import(tmp_path):
    source_data(tmp_path)
    model = local_model(tmp_path)
    before = (tmp_path / "training" / "verified" / "manifest.json").read_bytes()
    report = lora.plan(tmp_path, model)
    assert report["ready_for_owner_review"]
    assert report["counts"] == {"train": 15, "validation": 5, "test": 5}
    assert report["training_started"] is False
    assert not (tmp_path / "training" / "lora-runs").exists()
    assert (tmp_path / "training" / "verified" / "manifest.json").read_bytes() == before
    with pytest.raises(PermissionError):
        lora.train_approved(tmp_path, model, approved=False)
    assert not (tmp_path / "training" / "lora-runs").exists()


def test_tampered_training_dataset_or_manifest_blocks_plan(tmp_path):
    source_data(tmp_path)
    model = local_model(tmp_path)
    train_file = tmp_path / "training" / "verified" / "train.jsonl"
    train_file.write_text(train_file.read_text() + "\n")
    with pytest.raises(ValueError, match="SHA-256"):
        lora.plan(tmp_path, model)


def test_missing_partitions_and_wrong_model_are_refused(tmp_path):
    source_data(tmp_path)
    model = local_model(tmp_path)
    (model / "config.json").write_text(json.dumps({"architectures": ["UntrustedRemoteCodeModel"]}))
    with pytest.raises(PermissionError):
        lora.plan(tmp_path, model)
    (model / "config.json").write_text(json.dumps({"architectures": ["Qwen2ForCausalLM"]}))
    (tmp_path / "training" / "verified" / "test.jsonl").unlink()
    with pytest.raises(PermissionError):
        lora.plan(tmp_path, model)


def test_qlora_budgets_reject_unbounded_settings():
    for kwargs in ({"epochs": 10}, {"epochs": True}, {"max_length": 100000},
                   {"gradient_accumulation": 0}, {"lora_rank": 99},
                   {"min_free_vram_mib": 1024}):
        with pytest.raises(ValueError):
            lora.QLoRAConfig(**kwargs)


def test_approved_export_bytes_match_manifest_without_platform_newline_translation(tmp_path):
    source_data(tmp_path)
    directory = tmp_path / "training" / "verified"
    manifest = json.loads((directory / "manifest.json").read_bytes())
    assert manifest["accepted"] == 25
    for split, count in (("train", 15), ("validation", 5), ("test", 5)):
        contents = (directory / f"{split}.jsonl").read_bytes()
        assert contents.endswith(b"\n")
        assert b"\r\n" not in contents
        assert hashlib.sha256(contents).hexdigest() == manifest["files"][split]["sha256"]
        assert len(contents.splitlines()) == manifest["files"][split]["examples"] == count
    result = lora.plan(tmp_path, local_model(tmp_path))
    assert result["ready_for_owner_review"] and result["training_started"] is False
    assert result["counts"] == {"train": 15, "validation": 5, "test": 5}


@pytest.mark.parametrize("split", ["train", "validation", "test"])
def test_crlf_conversion_cannot_bypass_training_approval(tmp_path, split):
    source_data(tmp_path)
    model = local_model(tmp_path)
    target = tmp_path / "training" / "verified" / f"{split}.jsonl"
    approved_bytes = target.read_bytes()
    assert b"\r\n" not in approved_bytes
    target.write_bytes(approved_bytes.replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="SHA-256 differs"):
        lora.plan(tmp_path, model)
    assert not (tmp_path / "training" / "lora-runs").exists()
    target.write_bytes(approved_bytes)
    assert lora.plan(tmp_path, model)["ready_for_owner_review"] is True


@pytest.mark.parametrize("split", ["train", "validation", "test"])
def test_changing_approval_hash_cannot_authorize_dataset(tmp_path, split):
    source_data(tmp_path)
    model = local_model(tmp_path)
    manifest_path = tmp_path / "training" / "verified" / "manifest.json"
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    manifest["files"][split]["sha256"] = "0" * 64
    manifest_path.write_bytes(json.dumps(manifest, sort_keys=True).encode("utf-8"))
    with pytest.raises(ValueError, match="SHA-256 differs"):
        lora.plan(tmp_path, model)
    manifest_path.write_bytes(original)
    assert lora.plan(tmp_path, model)["ready_for_owner_review"]


def test_byte_tampering_fails_before_training_imports_or_gpu_work(tmp_path):
    source_data(tmp_path)
    model = local_model(tmp_path)
    with pytest.raises(PermissionError, match="explicitly approve"):
        lora.train_approved(tmp_path, model, approved=False)
    approved = tmp_path / "training" / "verified" / "train.jsonl"
    approved.write_bytes(approved.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA-256 differs"):
        lora.train_approved(tmp_path, model, approved=True)
    assert not (tmp_path / "training" / "lora-runs").exists()


@pytest.mark.parametrize("architectures", [
    [], ["Qwen2ForCausalLM", "UnreviewedArchitecture"], ["UnreviewedArchitecture"],
])
def test_model_identity_is_rejected_without_gpu_or_job_side_effects(tmp_path, architectures):
    source_data(tmp_path)
    model = local_model(tmp_path)
    (model / "config.json").write_text(json.dumps({"architectures": architectures}),
                                       encoding="utf-8")
    with pytest.raises(PermissionError, match="reviewed local small Qwen"):
        lora.plan(tmp_path, model)
    assert not (tmp_path / "training" / "lora-runs").exists()
