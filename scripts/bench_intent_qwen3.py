"""5단계 (4): 문장 1개씩(bs=1) 처리 시간. 이 PC 에서 잰 값이며 보드(RK3588) 값이 아니다.
측정 항목: 생성 전체(탐욕, max_new_tokens 8, eos 에서 멈춤) / 첫 토큰 로짓만(prefill 1회). GPU 와 CPU."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import intent_qwen_common as C
import numpy as np
import torch

dev = sys.argv[1]  # cuda | cpu
N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
tok = C.load_tokenizer(C.OUT_MERGED)
te = C.load_split("test")
texts = list(te.text)[:N]
if dev == "cpu":
    torch.set_num_threads(4)
    model = C.load_model(C.OUT_MERGED, device_map="cpu")
else:
    model = C.load_model(C.OUT_MERGED)
tok.padding_side = "left"


def sync():
    if dev == "cuda":
        torch.cuda.synchronize()


def run(t, gen):
    enc = tok(C.build_prompt(tok, t), return_tensors="pt", add_special_tokens=False).to(next(model.parameters()).device)
    sync()
    t0 = time.perf_counter()
    with torch.no_grad():
        if gen:
            g = model.generate(**enc, max_new_tokens=8, do_sample=False, pad_token_id=tok.pad_token_id,
                               eos_token_id=tok.eos_token_id)
            n_new = g.shape[1] - enc["input_ids"].shape[1]
        else:
            model(**enc).logits[:, -1, :]
            n_new = 1
    sync()
    return (time.perf_counter() - t0) * 1000, enc["input_ids"].shape[1], n_new


for t in texts[:5]:  # 예열
    run(t, True)
    run(t, False)
res = {"device": dev, "n": len(texts), "threads": torch.get_num_threads() if dev == "cpu" else None,
       "gpu": torch.cuda.get_device_name(0) if dev == "cuda" else None,
       "dtype": str(next(model.parameters()).dtype)}
g = [run(t, True) for t in texts]
f = [run(t, False) for t in texts]
res["generate_ms_mean"], res["generate_ms_median"], res["generate_ms_p95"] = (float(np.mean([x[0] for x in g])),
    float(np.median([x[0] for x in g])), float(np.percentile([x[0] for x in g], 95)))
res["first_token_only_ms_mean"], res["first_token_only_ms_median"] = float(np.mean([x[0] for x in f])), float(np.median([x[0] for x in f]))
res["prompt_tokens_mean"] = float(np.mean([x[1] for x in g]))
res["generated_tokens_mean_incl_eos"] = float(np.mean([x[2] for x in g]))
print(json.dumps(res, ensure_ascii=False))
(C.RES_DIR / f"latency_{dev}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
