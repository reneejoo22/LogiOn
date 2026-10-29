"""5단계 (1)~(3): 병합된 Qwen3-0.6B 의도분류를 val/test 에서 평가하고 roberta v2 와 같은 test 로 비교.
test 는 최종 모델 하나로 한 번만 돌린다 (체크포인트 선택은 select_intent_qwen3_ckpt.py 에서 val 로만 함).

예측 방식 두 가지
  greedy      : 모델이 생성한 단어 (RKLLM 에서도 가능). 6개 라벨 밖이면 형식 오류.
  first-token : 첫 생성 위치 로짓에서 6개 라벨의 첫 토큰만 골라 소프트맥스 (PC 에서만. RKLLM 이 로짓을 주는지 미확인)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import intent_qwen_common as C
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

tok = C.load_tokenizer(C.OUT_MERGED)
model = C.load_model(C.OUT_MERGED)
out = {}
for split in ("val", "test"):
    d = C.load_split(split)
    raw = C.generate_raw(model, tok, list(d.text), bs=32, max_new_tokens=8)
    P, mass = C.first_token_probs(model, tok, list(d.text), bs=32)
    d["raw"] = raw
    d["pred_greedy"] = [C.clean_label(r) for r in raw]
    d["format_err"] = ~d.pred_greedy.isin(C.FUNCS)
    d["pred_ft"] = [C.FUNCS[i] for i in P.argmax(1)]
    srt = np.sort(P, 1)
    d["p1"], d["margin"], d["mass"] = srt[:, -1], srt[:, -1] - srt[:, -2], mass
    for i, f in enumerate(C.FUNCS):
        d[f"p_{f}"] = P[:, i]
    d.to_csv(C.RES_DIR / f"{split}_pred.csv", index=False, encoding="utf-8-sig")
    out[split] = d
    print(split, "greedy acc", (d.pred_greedy == d.label).mean(), "ft acc", (d.pred_ft == d.label).mean(),
          "format_err", d.format_err.mean())

te, va = out["test"], out["val"]
rob = pd.read_csv(C.ROOT / "results" / "v2" / "test_pred_intent.csv")[["id", "pred", "conf"]].rename(
    columns={"pred": "pred_rob", "conf": "p1_rob"})
te = te.merge(rob, on="id", how="left")
assert te.pred_rob.notna().all() and len(te) == 431

# 이상 출력 확인 (<think> 등)
stray = te[te.raw.str.contains(r"<think>|</think>|<\|im_start\|>", regex=True)]
print("test 에서 <think> 등 군더더기가 나온 문장:", len(stray))
print("생성 원문 종류:", te.raw.value_counts().to_dict())

L = C.FUNCS
rep = {}
for name, col in (("roberta_v2", "pred_rob"), ("qwen3_greedy", "pred_greedy"), ("qwen3_first_token", "pred_ft")):
    r = classification_report(te.label, te[col], labels=L, output_dict=True, zero_division=0)
    cm = confusion_matrix(te.label, te[col], labels=L)
    rep[name] = {"acc": float((te.label == te[col]).mean()), "macro_f1": float(f1_score(te.label, te[col], labels=L, average="macro")),
                 "per_class": {f: {k: float(r[f][k]) for k in ("precision", "recall", "f1-score", "support")} for f in L},
                 "confusion": cm.tolist()}
    print(f"\n[{name}] acc {rep[name]['acc']:.4f}  macroF1 {rep[name]['macro_f1']:.4f}")
    print(pd.DataFrame(cm, index=L, columns=L))

# 짝 비교
a, b = te.pred_rob == te.label, te.pred_greedy == te.label
rep["paired"] = {"both_ok": int((a & b).sum()), "only_roberta_ok": int((a & ~b).sum()), "only_qwen3_ok": int((~a & b).sum()),
                 "both_wrong": int((~a & ~b).sum())}
print("\n짝 비교:", rep["paired"])

# 조각별 (출처·모호성)
sl = []
for col in ("source", "ambiguity"):
    for k, g in te.groupby(col):
        sl.append({"slice": f"{col}={k}", "n": len(g), "roberta": float((g.pred_rob == g.label).mean()),
                   "qwen3_greedy": float((g.pred_greedy == g.label).mean())})
sl = pd.DataFrame(sl)
print("\n조각별 정확도\n", sl.round(3).to_string(index=False))
sl.to_csv(C.RES_DIR / "test_slices.csv", index=False, encoding="utf-8-sig")

# 형식 오류
fe = {s: {"n": len(d), "format_err": int(d.format_err.sum()), "rate": float(d.format_err.mean()),
          "outputs_outside_labels": d[d.format_err].raw.value_counts().to_dict()} for s, d in (("val", va), ("test", te))}
print("\n형식 오류:", fe)

# 확률·margin
prob = {"mass_on_6_first_tokens_mean_test": float(te.mass.mean()), "mass_min_test": float(te.mass.min()),
        "greedy_equals_first_token_argmax_test": float((te.pred_greedy == te.pred_ft).mean())}
for tau in (0.05,):
    for nm, d, pc, mc in (("qwen3", te, "pred_ft", "margin"),):
        ask = d[mc] < tau
        prob[f"qwen3_ask_rate_tau{tau}_test"] = float(ask.mean())
        prob[f"qwen3_acc_among_not_asked_tau{tau}_test"] = float((d[~ask][pc] == d[~ask].label).mean())
        prob[f"qwen3_ask_rate_tau{tau}_val"] = float((va.margin < tau).mean())
wrong = te[te.pred_ft != te.label]
prob["qwen3_wrong_with_p1_ge_0.9_test"] = int((wrong.p1 >= 0.9).sum())
prob["qwen3_wrong_total_test"] = int(len(wrong))
prob["qwen3_margin_quantiles_test"] = {str(q): float(te.margin.quantile(q)) for q in (0.01, 0.05, 0.1, 0.25, 0.5)}
prob["qwen3_p1_quantiles_test_wrong"] = {str(q): float(wrong.p1.quantile(q)) for q in (0.1, 0.5, 0.9)} if len(wrong) else {}
print("\n확률:", json.dumps(prob, ensure_ascii=False, indent=1))

(C.RES_DIR / "eval_intent.json").write_text(json.dumps({"report": rep, "format_error": fe, "prob": prob}, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
te.to_csv(C.RES_DIR / "test_pred_with_roberta.csv", index=False, encoding="utf-8-sig")
