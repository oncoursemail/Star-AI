"""QLoRA FEASIBILITY run for a small generator model on the 8 GB card (W10 step 2 groundwork, not a quality claim).

Measures whether a 4-bit LoRA run of e.g. google/gemma-4-E2B-it (Apache-2.0) fits in 8 GB of VRAM, how fast a step
is, and that the adapter saves/merges. The data is deliberately simple and rights-clean: a synthetic developer
question (written by a local open-weight model, gen_queries.py) -> the documentation passage that answers it
(Roblox Creator Docs CC-BY-4.0 / Luau MIT). No Claude/ChatGPT output, no worked example with an agent-written prompt.
Reports held-out loss before/after only as a sanity check that training moves the model.

    python qlora_feasibility.py --pairs pairs.jsonl --model google/gemma-4-E2B-it --out runs/qlora-e2b --steps 40
Stop early: create STOP-TRAIN next to --out. Stops by itself below the free-RAM floor (6 GB).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import time

from common import TrainingGate, free_ram_gb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=Path, required=True)
    ap.add_argument("--model", default="google/gemma-4-E2B-it")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--n-eval", type=int, default=40)
    args = ap.parse_args()

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    rows = [json.loads(l) for l in args.pairs.read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["origin"] == "synthetic-question"]
    random.Random(7).shuffle(rows)
    evals, train = rows[:args.n_eval], rows[args.n_eval:]
    tok = AutoTokenizer.from_pretrained(args.model)

    def encode(row):
        question = row["anchor"].split("query: ", 1)[-1]
        passage = row["positive"].split(" | text: ", 1)[-1]
        prompt = tok.apply_chat_template([{"role": "user", "content": question}], tokenize=False, add_generation_prompt=True)
        p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
        a_ids = tok(passage + tok.eos_token, add_special_tokens=False)["input_ids"]
        ids = (p_ids + a_ids)[:args.max_len]
        labels = ([-100] * len(p_ids) + a_ids)[:args.max_len]
        return torch.tensor([ids]), torch.tensor([labels])

    torch.cuda.reset_peak_memory_stats()
    t0 = time.monotonic()
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True, llm_int8_enable_fp32_cpu_offload="gemma-4" in args.model.lower())
    # Gemma 4 E2B: 2.35B of its 5.1B parameters are the per-layer embedding table (a lookup, made to live in CPU
    # memory), plus audio/vision towers that text training never runs. Only the decoder goes to the 8 GB card.
    # prepare_model_for_kbit_training is NOT used: it casts every non-4-bit weight to fp32 (that table alone ->
    # 9.4 GB), which spilled into shared memory and tripped the RAM floor on the first attempt.
    # Measured: with this map the decoder fits in 6.9 GB of VRAM, but bitsandbytes keeps CPU-offloaded weights in
    # fp32, so the table costs ~9.4 GB of host RAM and the 6 GB free-RAM floor stops the run. Dense 2-4B models
    # (e.g. Qwen/Qwen3.5-2B) need no offload: they get {"": 0}.
    device_map = {"model.language_model.embed_tokens_per_layer": "cpu", "model.audio_tower": "cpu",
                  "model.vision_tower": "cpu", "model.embed_audio": "cpu", "model.embed_vision": "cpu", "": 0}         if "gemma-4" in args.model.lower() else {"": 0}
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map=device_map,
                                                 dtype=torch.bfloat16)
    load_s = time.monotonic() - t0
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    lora = LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                      # text decoder only: Gemma 4 also carries vision/audio towers whose layers LoRA must not touch
                      target_modules=r"^(?!.*(vision|visual|audio)).*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$")
    model = get_peft_model(model, lora)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)

    def eval_loss() -> float:
        model.eval()
        total = 0.0
        with torch.no_grad():
            for r in evals:
                ids, labels = encode(r)
                total += model(input_ids=ids.cuda(), labels=labels.cuda()).loss.item()
        model.train()
        return total / len(evals)

    before = eval_loss()
    args.out.mkdir(parents=True, exist_ok=True)
    stop_file = args.out.parent / "STOP-TRAIN"
    log = (args.out / "progress.log").open("a", encoding="utf-8")
    step_times, i, stopped = [], 0, None
    gate = TrainingGate("qlora-" + args.out.name, log=lambda m: print(m, flush=True))
    if not gate.start(stop=stop_file.exists):
        stopped = "not admitted (RAM floor, stop file or planner)"
    model.train()
    for step in range(args.steps if stopped is None else 0):
        if stop_file.exists():
            stopped = "stop file"
            break
        reason = gate.stop_reason()      # the free-RAM floor every step; a planner "yield" (owner gaming) every 30 s
        if reason:
            stopped = reason
            break
        s0 = time.monotonic()
        loss_sum = 0.0
        for _ in range(args.accum):
            ids, labels = encode(train[i % len(train)])
            i += 1
            loss = model(input_ids=ids.cuda(), labels=labels.cuda()).loss / args.accum
            loss.backward()
            loss_sum += loss.item()
        opt.step()
        opt.zero_grad(set_to_none=True)
        step_times.append(time.monotonic() - s0)
        log.write(json.dumps({"step": step + 1, "loss": round(loss_sum, 4), "s": round(step_times[-1], 2),
                              "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                              "free_ram_gb": round(free_ram_gb(), 1)}) + "\n")
        log.flush()
    gate.close()
    after = eval_loss()
    model.save_pretrained(str(args.out / "adapter"))
    summary = {"model": args.model, "trainable_params_m": round(trainable / 1e6, 1), "rank": args.rank,
               "max_len": args.max_len, "accum": args.accum, "steps_done": len(step_times), "stopped": stopped,
               "load_seconds": round(load_s, 1), "median_step_seconds": round(sorted(step_times)[len(step_times) // 2], 2) if step_times else None,
               "examples_seen": i, "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
               "heldout_loss_before": round(before, 4), "heldout_loss_after": round(after, 4),
               "note": "feasibility only: passage-recall SFT, not a coding-quality measurement"}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
