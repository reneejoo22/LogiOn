"""의도분류 모델(klue/roberta-small 계열) -> ONNX (fp32, int8 동적 양자화) 변환과 검증.

사용:  python scripts/export_intent_onnx.py [--model-dir out/intent_model] [--out export/intent_onnx]
결과:  export/intent_onnx/{model.onnx, model.int8.onnx, tokenizer.json, labels.json}
       results/v2/onnx_intent.json  (PyTorch 와 예측 일치율, CPU ms/문장)
변환 자체는 PC 에서 하고, 보드에는 export/intent_onnx/ 폴더를 복사해서 infer.py 로 돌린다 (torch 불필요).
"""
import argparse, json, os, sys, time
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--model-dir", default=f"{ROOT}/out/intent_model")
ap.add_argument("--data", default=f"{ROOT}/data/intent_dataset.csv")
ap.add_argument("--out", default=f"{ROOT}/export/intent_onnx")
ap.add_argument("--results", default=f"{ROOT}/results/v2/onnx_intent.json")
ap.add_argument("--max-len", type=int, default=64)
ap.add_argument("--threads", type=int, default=4, help="onnxruntime CPU 스레드 수 (보드 CPU 4코어 기준)")
args = ap.parse_args()

import torch
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType
from transformers import AutoModelForSequenceClassification, AutoTokenizer

os.makedirs(args.out, exist_ok=True)
tok = AutoTokenizer.from_pretrained(args.model_dir)
model = AutoModelForSequenceClassification.from_pretrained(args.model_dir).eval().to("cpu")
id2label = {int(k): v for k, v in model.config.id2label.items()}
use_tt = "token_type_ids" in tok.model_input_names
names = ["input_ids", "attention_mask"] + (["token_type_ids"] if use_tt else [])

# ---- 내보내기 (고정 형태 없이 batch, seq 를 동적으로) ----
enc = tok(["다음 어디야", "우유 두 개 터졌어"], padding=True, return_tensors="pt", max_length=args.max_len, truncation=True)
dummy = tuple(enc[n] for n in names)
fp32_path, int8_path = f"{args.out}/model.onnx", f"{args.out}/model.int8.onnx"
with torch.no_grad():
    torch.onnx.export(model, dummy, fp32_path, input_names=names, output_names=["logits"],
                      dynamic_axes={**{n: {0: "batch", 1: "seq"} for n in names}, "logits": {0: "batch"}},
                      opset_version=17, do_constant_folding=True, dynamo=False)
quantize_dynamic(fp32_path, int8_path, weight_type=QuantType.QInt8)

tok.save_pretrained(args.out)           # tokenizer.json 포함
json.dump({"id2label": id2label, "max_len": args.max_len, "inputs": names}, open(f"{args.out}/labels.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
sizes = {"fp32_mb": os.path.getsize(fp32_path) / 2**20, "int8_mb": os.path.getsize(int8_path) / 2**20}
print("saved:", sizes)

# ---- test 세트로 비교 ----
df = pd.read_csv(args.data)
te = df[df.split == "test"].reset_index(drop=True)
texts, gold = te.text.tolist(), te.label.tolist()


def torch_probs(ts):
    out = []
    with torch.no_grad():
        for i in range(0, len(ts), 64):
            e = tok(ts[i:i + 64], padding=True, truncation=True, max_length=args.max_len, return_tensors="pt")
            out.append(model(**e).logits.softmax(-1).numpy())
    return np.concatenate(out)


def make_session(path):
    so = ort.SessionOptions()
    so.intra_op_num_threads = args.threads
    return ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])


def ort_probs(sess, ts, bs=1):
    out = []
    for i in range(0, len(ts), bs):
        e = tok(ts[i:i + bs], padding=True, truncation=True, max_length=args.max_len, return_tensors="np")
        logits = sess.run(["logits"], {n: e[n].astype(np.int64) for n in names})[0]
        z = np.exp(logits - logits.max(-1, keepdims=True))
        out.append(z / z.sum(-1, keepdims=True))
    return np.concatenate(out)


def timed(fn, ts, repeat=1):
    fn(ts[:5])                                   # 예열
    t0 = time.perf_counter()
    for _ in range(repeat):
        fn(ts)
    return (time.perf_counter() - t0) / (len(ts) * repeat) * 1000


Pt = torch_probs(texts)
pred_t = Pt.argmax(1)
res = {"n_test": len(te), "threads": args.threads, "model_dir": os.path.relpath(args.model_dir, ROOT), "size_mb": sizes}
lab = np.array([{v: k for k, v in id2label.items()}[g] for g in gold])
res["pytorch"] = {"acc": float((pred_t == lab).mean())}
torch.set_num_threads(args.threads)
res["pytorch"]["cpu_ms_per_sentence_bs1"] = timed(lambda ts: [torch_probs([t]) for t in ts], texts[:100])
for tag, path in (("onnx_fp32", fp32_path), ("onnx_int8", int8_path)):
    sess = make_session(path)
    P = ort_probs(sess, texts)
    pred = P.argmax(1)
    res[tag] = {"acc": float((pred == lab).mean()),
                "agree_with_pytorch": float((pred == pred_t).mean()),
                "max_abs_prob_diff": float(np.abs(P - Pt).max()),
                "cpu_ms_per_sentence_bs1": timed(lambda ts: ort_probs(sess, ts, 1), texts)}
    print(tag, json.dumps(res[tag], ensure_ascii=False))
res["note"] = (f"CPU {args.threads}스레드, 문장 1개씩 처리한 시간(토크나이징 포함). 이 PC 에서 잰 값이며 보드(RK3588)의 시간이 아님. "
               "PyTorch 시간은 앞 100문장 기준.")
os.makedirs(os.path.dirname(args.results), exist_ok=True)
json.dump(res, open(args.results, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(res, ensure_ascii=False, indent=2))
