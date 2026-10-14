"""Fine-tune the knowledge service's embedding model (EmbeddingGemma-300M) on (query, passage) pairs.

    python train_embed.py --pairs pairs.jsonl --out runs/ft-a --epochs 1 --lr 2e-5

Loss: CachedMultipleNegativesRankingLoss (in-batch negatives with a large effective batch at low memory).
The batch sampler never puts two pairs of the same chunk in one batch (they would be false negatives).
Interruptible: create the file STOP-TRAIN (next to --out) and the run saves a checkpoint and stops; rerun the
same command to resume from the newest checkpoint. Progress is appended to <out>/progress.log.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import time

from common import RAM_FLOOR_GB, free_ram_gb, load_model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=Path, required=True)
    ap.add_argument("--base", default="unsloth/embeddinggemma-300m")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--mini-batch", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=384)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--save-steps", type=int, default=50)
    ap.add_argument("--train-embeddings", action="store_true", help="also train the token embedding table (needs more VRAM)")
    ap.add_argument("--optim", default="adamw_bnb_8bit", help="8-bit AdamW keeps the run inside 8 GB of VRAM")
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from sentence_transformers import SentenceTransformerTrainer, SentenceTransformerTrainingArguments
    from sentence_transformers.losses import CachedMultipleNegativesRankingLoss
    from sentence_transformers.training_args import BatchSamplers
    from transformers import TrainerCallback

    rows = [json.loads(l) for l in args.pairs.read_text(encoding="utf-8").splitlines()]
    random.Random(args.seed).shuffle(rows)
    # NO_DUPLICATES compares texts: same chunk => same positive text => never twice in one batch
    data = Dataset.from_dict({"anchor": [r["anchor"] for r in rows], "positive": [r["positive"] for r in rows]})
    model = load_model(args.base)
    model.max_seq_length = args.max_len
    if not args.train_embeddings:
        # 201M of EmbeddingGemma's 308M parameters are the 262k-token embedding table; freezing it keeps the
        # gradients and optimizer state small enough for 8 GB (and limits drift on tokens the pairs never show).
        for name, param in model.named_parameters():
            if "embed_tokens" in name:
                param.requires_grad = False
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"trainable parameters: {trainable / 1e6:.1f}M", flush=True)
    loss = CachedMultipleNegativesRankingLoss(model, mini_batch_size=args.mini_batch)
    args.out.mkdir(parents=True, exist_ok=True)
    stop_file = args.out.parent / "STOP-TRAIN"
    log_path = args.out / "progress.log"
    started = time.monotonic()

    class Progress(TrainerCallback):
        def on_log(self, targs, state, control, logs=None, **kw):
            mem = torch.cuda.max_memory_allocated() / 2**30
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"t": round(time.monotonic() - started), "step": state.global_step,
                                     "max_steps": state.max_steps, "peak_vram_gb": round(mem, 2), **(logs or {})}) + "\n")

        def on_step_end(self, targs, state, control, **kw):
            low = free_ram_gb() < RAM_FLOOR_GB   # owner's rule: keep at least 6 GB of RAM free
            if stop_file.exists() or low:
                if low:
                    stop_file.write_text(f"free RAM below {RAM_FLOOR_GB} GB at step {state.global_step}\n")
                control.should_save = True
                control.should_training_stop = True
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"stopped_by": str(stop_file), "step": state.global_step}) + "\n")

    targs = SentenceTransformerTrainingArguments(
        output_dir=str(args.out / "checkpoints"), num_train_epochs=args.epochs, per_device_train_batch_size=args.batch,
        learning_rate=args.lr, warmup_steps=0.1, lr_scheduler_type="linear", weight_decay=0.01, bf16=True,
        batch_sampler=BatchSamplers.NO_DUPLICATES, logging_steps=5, save_strategy="steps", save_steps=args.save_steps,
        save_total_limit=2, seed=args.seed, report_to="none", dataloader_num_workers=0, optim=args.optim)
    trainer = SentenceTransformerTrainer(model=model, args=targs, train_dataset=data, loss=loss, callbacks=[Progress()])
    ckpts = sorted((args.out / "checkpoints").glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1]))
    trainer.train(resume_from_checkpoint=str(ckpts[-1]) if ckpts else None)
    if stop_file.exists():
        print("stopped early; rerun to resume")
        return
    model.max_seq_length = 512
    model.save(str(args.out / "final"))
    summary = {"pairs": len(rows), "epochs": args.epochs, "lr": args.lr, "batch": args.batch, "max_len": args.max_len,
               "seconds": round(time.monotonic() - started), "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
               "base": args.base}
    (args.out / "train-summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
