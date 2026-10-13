"""Owner-triggered, offline-only QLoRA training on privately curated STAR examples.

No scheduler, no automatic download, no cloud logging and no activation of the
resulting adapter. This script is NOT imported by ordinary chat: heavy optional
TRL/PEFT/Transformers/CUDA imports happen only after explicit training approval.
A successful job still needs an independent holdout/Studio acceptance gate.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets

FORMAT = "star-verified-luau-sft-v1"
MAX_FILE_BYTES = 8_000_000
MAX_TRAIN_ROWS = 4_000
ALLOWED_ARCHITECTURES = frozenset({"Qwen2ForCausalLM", "Qwen3ForCausalLM"})


@dataclass(frozen=True)
class QLoRAConfig:
    epochs: int = 1
    max_length: int = 1024
    gradient_accumulation: int = 8
    lora_rank: int = 8
    min_free_vram_mib: int = 5500

    def __post_init__(self):
        if (type(self.epochs) is not int or self.epochs not in (1, 2)
                or type(self.max_length) is not int or not 256 <= self.max_length <= 2048
                or type(self.gradient_accumulation) is not int
                or not 1 <= self.gradient_accumulation <= 32
                or type(self.lora_rank) is not int or self.lora_rank not in (4, 8, 16)
                or type(self.min_free_vram_mib) is not int
                or not 4096 <= self.min_free_vram_mib <= 32768):
            raise ValueError("QLoRA hyperparameters exceed the reviewed small-GPU limits")


def _private_file(path: Path, *, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise PermissionError("Missing, linked or oversized local dataset/model file")
    return path.read_bytes()


def _read_dataset(file: Path) -> tuple[list[dict], str]:
    data = _private_file(file)
    rows = []
    if not data:
        raise ValueError("Training split is empty")
    for line in data.splitlines():
        if len(rows) >= MAX_TRAIN_ROWS or len(line) > 20_000:
            raise ValueError("Training split exceeds bounds")
        item = json.loads(line)
        if (not isinstance(item, dict) or set(item) != {"messages"}
                or not isinstance(item["messages"], list)
                or len(item["messages"]) != 2):
            raise ValueError("Invalid supervised conversation")
        user, assistant = item["messages"]
        if (not isinstance(user, dict) or not isinstance(assistant, dict)
                or user.get("role") != "user" or assistant.get("role") != "assistant"
                or not isinstance(user.get("content"), str)
                or not isinstance(assistant.get("content"), str)
                or not user["content"] or not assistant["content"]):
            raise ValueError("Invalid training roles/content")
        rows.append(item)
    return rows, hashlib.sha256(data).hexdigest()


def _reviewed_source(home: Path) -> tuple[Path, dict, dict]:
    folder = home / "training" / "verified"
    if folder.is_symlink():
        raise PermissionError("Training folder cannot be a symlink")
    manifest = json.loads(_private_file(folder / "manifest.json", max_bytes=200_000))
    if (not isinstance(manifest, dict) or manifest.get("format") != FORMAT
            or manifest.get("training_started") is not False
            or manifest.get("rights_review_required_before_train") is not True
            or not isinstance(manifest.get("project_split"), dict)):
        raise PermissionError("Only a sealed, reviewed STAR training export is accepted")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != {"train", "validation", "test"}:
        raise ValueError("All three original dataset partitions are required")
    parts = {}
    projects = {part: set() for part in ("train", "validation", "test")}
    for project, split in manifest["project_split"].items():
        if not isinstance(project, str) or split not in projects:
            raise PermissionError("Only a project-disjoint three-way partition is trainable")
        projects[split].add(project)
    if any(not value for value in projects.values()):
        raise ValueError("Training must hold out whole nonempty projects")
    prompts = set()
    for split in ("train", "validation", "test"):
        rows, fingerprint = _read_dataset(folder / f"{split}.jsonl")
        metadata = files[split]
        if (not isinstance(metadata, dict) or metadata.get("sha256") != fingerprint
                or metadata.get("examples") != len(rows)):
            raise ValueError("Training dataset SHA-256 differs from approval manifest")
        for row in rows:
            prompt = " ".join(row["messages"][0]["content"].casefold().split())
            digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            if digest in prompts:
                raise ValueError("Question repeated across train/validation/test")
            prompts.add(digest)
        parts[split] = rows
    if len(parts["train"]) < 10 or min(len(parts["validation"]), len(parts["test"])) < 1:
        raise ValueError("Not enough train, validation and test examples")
    if sum(len(value) for value in parts.values()) != manifest.get("accepted"):
        raise ValueError("Training example count differs from manifest")
    return folder, manifest, parts


def plan(home: Path, model_dir: Path, options: QLoRAConfig = QLoRAConfig()) -> dict:
    """No filesystem writes, model import, GPU access, package install or network."""
    home = Path(home).expanduser().resolve(strict=True)
    if not home.is_dir():
        raise ValueError("STAR private profile must exist")
    folder, manifest, data = _reviewed_source(home)
    model = Path(model_dir).expanduser().resolve(strict=True)
    if not model.is_dir() or model.is_symlink():
        raise PermissionError("Choose a regular local model directory")
    config = json.loads(_private_file(model / "config.json", max_bytes=256_000))
    architectures = config.get("architectures") if isinstance(config, dict) else None
    if (not isinstance(architectures, list) or len(architectures) != 1
            or architectures[0] not in ALLOWED_ARCHITECTURES):
        raise PermissionError("Only a reviewed local small Qwen causal LM can be trained")
    _private_file(model / "tokenizer_config.json", max_bytes=256_000)
    weights = list(model.glob("*.safetensors"))
    if (not 1 <= len(weights) <= 32 or any(f.is_symlink() or not f.is_file() for f in weights)
            or sum(f.stat().st_size for f in weights) > 5_000_000_000):
        raise PermissionError("The local base model must use bounded SafeTensors weights")
    return {
        "model_dir": str(model), "model_architecture": architectures[0],
        "data_dir": str(folder), "counts": {k: len(v) for k, v in data.items()},
        "manifest_sha256": hashlib.sha256(_private_file(folder / "manifest.json")).hexdigest(),
        "holdout_suite_sha256": manifest.get("holdout_suite_sha256"),
        "hyperparameters": {
            "epochs": options.epochs, "max_length": options.max_length,
            "gradient_accumulation": options.gradient_accumulation,
            "lora_rank": options.lora_rank, "min_free_vram_mib": options.min_free_vram_mib,
        },
        "ready_for_owner_review": True, "training_started": False,
        "notes": ["Local SafeTensors only; no model download or remote code",
                  "CUDA/VRAM and optional TRL/PEFT libraries are checked only on --run",
                  "The saved LoRA will not be loaded into STAR without a separate evaluation gate"],
    }


def train_approved(home: Path, model_dir: Path, *, approved: bool = False,
                   options: QLoRAConfig = QLoRAConfig()) -> dict:
    """Explicitly approved on-device job; saves adapter without auto-applying it."""
    if approved is not True:
        raise PermissionError("The owner must explicitly approve actual LoRA training")
    checked = plan(home, model_dir, options)
    # Heavy packages are intentionally not desktop dependencies.
    import torch
    from datasets import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        raise RuntimeError("QLoRA requires a working CUDA GPU, not a CPU fallback")
    free, total = torch.cuda.mem_get_info()
    if free < options.min_free_vram_mib * 1024**2:
        raise RuntimeError("Available CUDA VRAM is below the owner-selected admission limit")
    root = Path(home).expanduser().resolve(strict=True) / "training" / "lora-runs"
    if root.is_symlink():
        raise PermissionError("LoRA output folder cannot be a symlink")
    # No overwrite of a prior adapter and no remote uploads.
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir = root / ("run-" + secrets.token_hex(8))
    run_dir.mkdir(mode=0o700)
    data_dir = Path(checked["data_dir"])
    train_rows, _ = _read_dataset(data_dir / "train.jsonl")
    val_rows, _ = _read_dataset(data_dir / "validation.jsonl")
    tokenizer = AutoTokenizer.from_pretrained(
        checked["model_dir"], trust_remote_code=False, local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                               bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=torch.float16)
    model = AutoModelForCausalLM.from_pretrained(
        checked["model_dir"], quantization_config=quant,
        trust_remote_code=False, local_files_only=True, device_map="auto")
    params = SFTConfig(
        output_dir=str(run_dir / "checkpoints"), num_train_epochs=options.epochs,
        learning_rate=1.0e-4, max_length=options.max_length,
        per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=options.gradient_accumulation,
        logging_steps=10, eval_strategy="epoch", save_strategy="no",
        report_to="none", push_to_hub=False,
        fp16=True, bf16=False, disable_tqdm=True,
    )
    adapter = LoraConfig(
        r=options.lora_rank, lora_alpha=options.lora_rank * 2,
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    trainer = SFTTrainer(
        model=model, args=params, peft_config=adapter,
        train_dataset=Dataset.from_list(train_rows),
        eval_dataset=Dataset.from_list(val_rows),
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(str(run_dir / "adapter"))
    receipt = {"status": "candidate_only", "manifest_sha256": checked["manifest_sha256"],
               "model_architecture": checked["model_architecture"],
               "train_rows": len(train_rows), "validation_rows": len(val_rows),
               "holdout_evaluated": False, "deployed_to_star": False,
               "owner_review_required": True}
    out = run_dir / "receipt.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(out, 0o600)
    return {"candidate_adapter_folder": str(run_dir / "adapter"),
            "training_executed": True, "deployed_to_star": False,
            "requires_holdout_review": True}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="STAR private reviewed Luau QLoRA pilot")
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--local-model", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--i-approve-training", action="store_true")
    args = parser.parse_args(argv)
    if args.run:
        report = train_approved(
            args.home, args.local_model, approved=args.i_approve_training)
    else:
        report = plan(args.home, args.local_model)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
