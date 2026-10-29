"""3단계: Qwen3-0.6B LoRA 의도분류 학습. FC 학습(노트북 26번 셀)의 설정을 시작점으로 썼다.

사용: python scripts/train_intent_qwen3.py --smoke   (200문장 1 step: 로딩→학습→저장→재로딩)
      python scripts/train_intent_qwen3.py           (본 학습)
"""
import argparse
import gc
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import intent_qwen_common as C
import numpy as np
import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import Trainer, TrainerCallback, TrainingArguments, set_seed

ap = argparse.ArgumentParser()
ap.add_argument("--smoke", action="store_true")
ap.add_argument("--epochs", type=int, default=3)
ap.add_argument("--lr", type=float, default=2e-4)
ap.add_argument("--bs", type=int, default=4)
ap.add_argument("--ga", type=int, default=4)
ap.add_argument("--r", type=int, default=16)
args = ap.parse_args()

set_seed(C.SEED)
tag = "smoke" if args.smoke else "full"
ckpt_dir = C.ROOT / "out" / ("intent_qwen3_smoke_ckpt" if args.smoke else "intent_qwen3_ckpt")
lora_dir = C.ROOT / "out" / ("intent_qwen3_smoke_lora" if args.smoke else "intent_qwen3_lora")
C.RES_DIR.mkdir(parents=True, exist_ok=True)

tok = C.load_tokenizer()
tr, va = C.load_split("train"), C.load_split("val")
if args.smoke:
    tr, va = tr.sample(200, random_state=C.SEED), va.head(16)
ds_tr = [C.build_example(tok, t, y) for t, y in zip(tr.text, tr.label)]
ds_va = [C.build_example(tok, t, y) for t, y in zip(va.text, va.label)]
print(f"train {len(ds_tr)} / val {len(ds_va)} / 토큰 길이 최대 {max(len(r['input_ids']) for r in ds_tr)}")

# 학습 전 20문장 출력 (base 모델, 특수 토큰 그대로)
base = C.load_model(C.BASE)
sample = va.head(20) if not args.smoke else va.head(5)
raw0 = C.generate_raw(base, tok, list(sample.text))
before = [{"text": t, "label": y, "raw": r} for t, y, r in zip(sample.text, sample.label, raw0)]
for b in before[:20]:
    print("  [학습 전]", b["label"], "|", repr(b["raw"]))
del base
gc.collect()
torch.cuda.empty_cache()

DTYPE = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
model = C.load_model(C.BASE)
model.train()
lora_cfg = LoraConfig(r=args.r, lora_alpha=2 * args.r, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()


class Timing(TrainerCallback):
    def __init__(self):
        self.t, self.steps, self.vram = None, [], []

    def on_step_begin(self, a, s, c, **k):
        torch.cuda.synchronize()
        self.t = time.time()

    def on_step_end(self, a, s, c, **k):
        torch.cuda.synchronize()
        self.steps.append(time.time() - self.t)
        self.vram.append((torch.cuda.max_memory_allocated() / 2**30, torch.cuda.max_memory_reserved() / 2**30))


cb = Timing()
targs = TrainingArguments(
    output_dir=str(ckpt_dir), num_train_epochs=args.epochs, learning_rate=args.lr, max_steps=1 if args.smoke else -1,
    per_device_train_batch_size=args.bs, per_device_eval_batch_size=8, gradient_accumulation_steps=args.ga,
    lr_scheduler_type="cosine", warmup_ratio=0.05, logging_steps=10,
    eval_strategy="no" if args.smoke else "epoch", save_strategy="no" if args.smoke else "epoch", save_total_limit=None,
    bf16=(DTYPE == torch.bfloat16), fp16=(DTYPE == torch.float16), seed=C.SEED, report_to="none",
    remove_unused_columns=False,
)
trainer = Trainer(model=model, args=targs, train_dataset=ds_tr, eval_dataset=ds_va, data_collator=C.collate_factory(tok),
                  callbacks=[cb])
torch.cuda.reset_peak_memory_stats()
t0 = time.time()
trainer.train()
total = time.time() - t0
steps = np.array(cb.steps)
info = {
    "mode": tag, "base": C.BASE, "epochs": args.epochs, "lr": args.lr, "r": args.r, "alpha": 2 * args.r,
    "batch": args.bs, "grad_accum": args.ga, "n_train": len(ds_tr), "n_val": len(ds_va), "seed": C.SEED,
    "total_sec": round(total, 1), "optimizer_steps": len(steps),
    "step_sec_mean": round(float(steps.mean()), 3), "step_sec_median": round(float(np.median(steps)), 3),
    "step_sec_max": round(float(steps.max()), 3),
    "vram_peak_alloc_gb": round(max(v[0] for v in cb.vram), 2), "vram_peak_reserved_gb": round(max(v[1] for v in cb.vram), 2),
    "gpu": torch.cuda.get_device_name(0), "log_history": trainer.state.log_history,
    "system_prompt": C.INTENT_SYSTEM,
}
print(json.dumps({k: v for k, v in info.items() if k not in ("log_history", "system_prompt")}, ensure_ascii=False))
model.save_pretrained(lora_dir)
tok.save_pretrained(lora_dir)
(C.RES_DIR / f"train_info_{tag}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
(C.RES_DIR / f"before_train_20_{tag}.json").write_text(json.dumps(before, ensure_ascii=False, indent=1), encoding="utf-8")

# 저장 → 재로딩 확인
del trainer, model
gc.collect()
torch.cuda.empty_cache()
re = PeftModel.from_pretrained(C.load_model(C.BASE), lora_dir).eval()
raw1 = C.generate_raw(re, tok, list(sample.text))
for t, y, r in zip(sample.text, sample.label, raw1):
    print("  [학습 후]", y, "|", repr(r))
print("재로딩 OK")
