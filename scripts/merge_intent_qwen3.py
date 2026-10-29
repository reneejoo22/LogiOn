"""4단계: 선택한 LoRA 체크포인트를 base 에 병합해 fp16 HF 폴더(out/intent_qwen3_merged)로 저장하고,
어댑터 모델과 출력이 같은지 확인한다."""
import gc
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import intent_qwen_common as C
import numpy as np
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM

sel = json.loads((C.RES_DIR / "val_ckpt_selection.json").read_text(encoding="utf-8"))["selected"]
ck = C.OUT_CKPT / sel["ckpt"]
print("병합할 체크포인트:", ck)
tok = C.load_tokenizer()
va = C.load_split("val")
texts = list(va.text)

load = lambda: AutoModelForCausalLM.from_pretrained(C.BASE, dtype=torch.float16, device_map={"": 0})
ad = PeftModel.from_pretrained(load(), ck).eval()
raw_a = C.generate_raw(ad, tok, texts, bs=32)
P_a, _ = C.first_token_probs(ad, tok, texts, bs=32)

merged = ad.merge_and_unload()
C.OUT_MERGED.mkdir(parents=True, exist_ok=True)
merged.save_pretrained(C.OUT_MERGED, safe_serialization=True)
tok.save_pretrained(C.OUT_MERGED)
del ad, merged
gc.collect()
torch.cuda.empty_cache()

# eos 확인·보정
for fn in ("config.json", "generation_config.json"):
    p = C.OUT_MERGED / fn
    d = json.loads(p.read_text(encoding="utf-8"))
    print(fn, "eos_token_id =", d.get("eos_token_id"), "pad_token_id =", d.get("pad_token_id"))
    e = d.get("eos_token_id")
    has = (e == tok.eos_token_id) if not isinstance(e, list) else (tok.eos_token_id in e)
    if not has:
        d["eos_token_id"] = tok.eos_token_id
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  -> <|im_end|>(151645) 추가함")

mm = C.load_model(C.OUT_MERGED)  # bf16 로 다시 불러오지 않도록 아래에서 fp16 로 재로딩
del mm
mm = AutoModelForCausalLM.from_pretrained(C.OUT_MERGED, dtype=torch.float16, device_map={"": 0}).eval()
raw_m = C.generate_raw(mm, tok, texts, bs=32)
P_m, _ = C.first_token_probs(mm, tok, texts, bs=32)
same = np.mean([C.clean_label(a) == C.clean_label(b) for a, b in zip(raw_a, raw_m)])
acc = np.mean([C.clean_label(r) == y for r, y in zip(raw_m, va.label)])
res = {"checkpoint": sel["ckpt"], "val_same_output_rate_adapter_vs_merged": float(same), "val_acc_merged": float(acc),
       "val_max_abs_prob_diff": float(np.abs(P_a - P_m).max()), "dtype": "float16",
       "files": sorted(f.name for f in C.OUT_MERGED.iterdir()),
       "size_mb": round(sum(f.stat().st_size for f in C.OUT_MERGED.iterdir()) / 2**20, 1)}
print(json.dumps(res, ensure_ascii=False))
(C.RES_DIR / "merge_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
