"""QLoRA pilot preflight is offline and does not import GPU stacks until approved."""
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
