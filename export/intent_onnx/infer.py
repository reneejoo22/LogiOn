"""보드용 의도분류 추론 (onnxruntime + tokenizers + numpy 만 사용, torch/transformers 불필요).

  pip install onnxruntime tokenizers numpy
  python infer.py "다음 어디야" "우유 두 개 터졌어"            # int8 모델 (기본)
  python infer.py --fp32 "역삼점 뭐 내려"

코드에서:
  from infer import IntentONNX
  clf = IntentONNX(".")
  r = clf.predict("다음 어디야")   # {'top1': 'next_stop', 'p1': 0.99, 'top2': 'stop_items', 'p2': 0.004, 'margin': 0.98, 'probs': {...}}
margin(1등-2등 확률 차) 이 기준 tau 보다 작으면 실행하지 말고 두 후보를 말해 주며 되묻는다 (README 의 '선택지 되묻기').
"""
import json, os, sys
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


class IntentONNX:
    def __init__(self, model_dir=None, int8=True, threads=4):
        d = model_dir or os.path.dirname(os.path.abspath(__file__))
        meta = json.load(open(os.path.join(d, "labels.json"), encoding="utf-8"))
        self.id2label = {int(k): v for k, v in meta["id2label"].items()}
        self.inputs = meta["inputs"]
        self.tok = Tokenizer.from_file(os.path.join(d, "tokenizer.json"))
        self.tok.enable_truncation(max_length=meta.get("max_len", 64))
        self.tok.enable_padding(pad_id=self.tok.token_to_id("[PAD]") or 0, pad_token="[PAD]")
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        path = os.path.join(d, "model.int8.onnx" if int8 else "model.onnx")
        self.sess = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])

    def probs(self, texts):
        encs = self.tok.encode_batch(list(texts))
        feed = {"input_ids": np.array([e.ids for e in encs], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in encs], dtype=np.int64)}
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.array([e.type_ids for e in encs], dtype=np.int64)
        logits = self.sess.run(["logits"], feed)[0]
        z = np.exp(logits - logits.max(-1, keepdims=True))
        return z / z.sum(-1, keepdims=True)

    def predict(self, text):
        p = self.probs([text])[0]
        o = np.argsort(-p)
        return {"top1": self.id2label[int(o[0])], "p1": float(p[o[0]]),
                "top2": self.id2label[int(o[1])], "p2": float(p[o[1]]),
                "margin": float(p[o[0]] - p[o[1]]),
                "probs": {self.id2label[i]: float(p[i]) for i in range(len(p))}}


if __name__ == "__main__":
    args = sys.argv[1:]
    fp32 = "--fp32" in args
    texts = [a for a in args if not a.startswith("--")] or ["다음 어디야", "우유 두 개 터졌어", "노래 틀어줘"]
    clf = IntentONNX(int8=not fp32)
    for t in texts:
        r = clf.predict(t)
        print(f"{t} -> {r['top1']} ({r['p1']:.3f}), 2등 {r['top2']} ({r['p2']:.3f}), margin {r['margin']:.3f}")
