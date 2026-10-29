"""3단계 끝: 에폭별 체크포인트를 val 로만 비교해 고른다 (test 는 보지 않는다).
기준(미리 정함): val 탐욕 디코딩 정확도 최고, 동점이면 val loss 가 낮은 쪽."""
import gc
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import intent_qwen_common as C
import numpy as np
import torch
from peft import PeftModel

tok = C.load_tokenizer()
va = C.load_split("val")
hist = json.loads((C.RES_DIR / "train_info_full.json").read_text(encoding="utf-8"))["log_history"]
eval_loss = {round(h["epoch"]): h["eval_loss"] for h in hist if "eval_loss" in h}
rows = []
for ck in sorted(C.OUT_CKPT.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1])):
    step = int(ck.name.split("-")[1])
    ep = round(step / 122)
    m = PeftModel.from_pretrained(C.load_model(C.BASE), ck).eval()
    raw = C.generate_raw(m, tok, list(va.text), bs=32)
    pred = [C.clean_label(r) for r in raw]
    ok = np.mean([p == y for p, y in zip(pred, va.label)])
    fmt = np.mean([p not in C.FUNCS for p in pred])
    P, mass = C.first_token_probs(m, tok, list(va.text), bs=32)
    am = np.mean([C.FUNCS[i] == y for i, y in zip(P.argmax(1), va.label)])
    rows.append({"epoch": ep, "ckpt": ck.name, "val_acc_greedy": float(ok), "val_format_err": float(fmt),
                 "val_acc_first_token_argmax": float(am), "val_loss": eval_loss.get(ep), "mass_mean": float(mass.mean())})
    print(rows[-1])
    del m
    gc.collect()
    torch.cuda.empty_cache()
best = max(rows, key=lambda r: (r["val_acc_greedy"], -r["val_loss"]))
print("선택:", best["ckpt"], "epoch", best["epoch"])
(C.RES_DIR / "val_ckpt_selection.json").write_text(json.dumps({"rows": rows, "selected": best}, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
