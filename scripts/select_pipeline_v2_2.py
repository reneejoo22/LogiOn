"""v2.2: 의도분류 모듈만 Qwen3-0.6B LoRA 로 바꿔 끼운 파이프라인 평가. FC 는 v2.1 과 같은 out/fc_merged (재학습 없음).
선정 규칙은 select_pipeline_v2_1.py 와 같다: 격자(건너뛰기 기준 x 건너뛰기 대상 x tau) 를 val 로만 훑고,
tau = '되묻기 <=10% 중 실행 정확도 최고(동률이면 작은 tau)', 설정 = val pipeline_incl_ask 최고. test 는 설정당 한 번.

모드
  roberta_v2_1       : 기존 v2.1 설정 그대로 (같은 코드로 다시 계산한 기준값)
  qwen3_prob         : 첫 토큰 확률로 6개 확률을 만들어 사용 (PC 에서만). val 에서 설정 선택
  qwen3_prob_v21cfg  : 위 확률을 쓰되 설정은 v2.1 값(tau 0.05, 건너뛰기 0.9, scan·other)을 그대로 (선택 없음, 비교용)
  qwen3_argmax       : 확률 없이 생성한 단어만 (one-hot). 되묻기 판정 불가 -> 되묻기 0. 건너뛰기 대상만 val 에서 선택
"""
import gc, json, os, sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nb_rules import load_rules, ROOT
import intent_qwen_common as C

SKIP_CONFS = [0.9, 0.95, 0.98, 0.99]
SKIP_SETS = {"next_stop 포함": ("next_stop", "scan", "other"), "next_stop 불포함": ("scan", "other")}
TAUS = [0.0] + [round(0.05 * k, 2) for k in range(1, 11)]
MAX_ASK = 0.10
V21 = json.load(open(f"{ROOT}/config/pipeline_v2_1.json", encoding="utf-8"))

R = load_rules(with_route=True)
summarize_rr = R["summarize_rr"]
ID2LABEL, LABEL2ID, FUNCS, SYSTEM_PROMPT = R["ID2LABEL"], R["LABEL2ID"], R["FUNCS"], R["SYSTEM_PROMPT"]

import torch
from transformers import AutoModelForSequenceClassification, AutoModelForCausalLM, AutoTokenizer

DTYPE = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
intent_df = pd.read_csv(f"{ROOT}/data/intent_dataset.csv", encoding="utf-8-sig")
fc_df = pd.read_csv(f"{ROOT}/data/fc_dataset.csv")
SPLITS = {s: (intent_df[intent_df.split == s].reset_index(drop=True), fc_df[fc_df.split == s].reset_index(drop=True))
          for s in ("val", "test")}
for s, (vi, vf) in SPLITS.items():
    assert (vi.id.values == vf.id.values).all()

# ---- 확률 배열 (열 순서는 노트북 ID2LABEL 기준) ----
P = {}
m = AutoModelForSequenceClassification.from_pretrained(f"{ROOT}/out/intent_model").eval().cuda()
tk = AutoTokenizer.from_pretrained(f"{ROOT}/out/intent_model")
for s, (vi, _) in SPLITS.items():
    out = []
    for i in range(0, len(vi), 64):
        enc = tk(vi.text.tolist()[i:i + 64], truncation=True, max_length=64, padding=True, return_tensors="pt").to("cuda")
        with torch.no_grad():
            out.append(m(**enc).logits.float().softmax(-1).cpu().numpy())
    P[("roberta", s)] = np.concatenate(out)
del m
gc.collect()
torch.cuda.empty_cache()

for s in SPLITS:
    q = pd.read_csv(C.RES_DIR / f"{s}_pred.csv", encoding="utf-8-sig")
    assert (q.id.values == SPLITS[s][0].id.values).all()
    assert q.pred_greedy.isin(FUNCS).all(), "형식 오류 문장이 있으면 one-hot 처리 방법을 따로 정해야 함"
    arr = np.zeros((len(q), len(FUNCS)))
    for f in FUNCS:
        arr[:, LABEL2ID[f]] = q[f"p_{f}"].values
    P[("qwen3_prob", s)] = arr
    onehot = np.zeros_like(arr)
    onehot[np.arange(len(q)), [LABEL2ID[x] for x in q.pred_greedy]] = 1.0
    P[("qwen3_argmax", s)] = onehot


# ---- FC v2 출력 (val·test) ----
@torch.no_grad()
def fc_generate(model, tok, texts, bs=8):
    pr = lambda t: tok.apply_chat_template([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": t}],
                                           tokenize=False, add_generation_prompt=True, enable_thinking=False)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    outs = []
    for i in range(0, len(texts), bs):
        enc = tok([pr(t) for t in texts[i:i + bs]], return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
        gen = model.generate(**enc, max_new_tokens=64, do_sample=False, pad_token_id=tok.pad_token_id)
        outs += tok.batch_decode(gen[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
    return [o.strip() for o in outs]


fm = AutoModelForCausalLM.from_pretrained(f"{ROOT}/out/fc_merged", torch_dtype=DTYPE, device_map={"": 0}).eval()
ftk = AutoTokenizer.from_pretrained(f"{ROOT}/out/fc_merged")
RAW = {s: fc_generate(fm, ftk, vf.text.tolist()) for s, (_, vf) in SPLITS.items()}
del fm
gc.collect()
torch.cuda.empty_cache()
prev = pd.read_csv(f"{ROOT}/results/v2_1/test_pred_fc.csv", encoding="utf-8-sig")
print("FC test 출력이 v2.1 결과와 같은 비율:", float(np.mean(np.array(RAW["test"]) == prev.pred_raw.fillna("").values)))


def evaluate(mode, split, tau, skip_conf, skip_fns):
    vi, vf = SPLITS[split]
    d = vf.assign(pred_raw=RAW[split])
    R["SKIP_FNS"] = skip_fns
    _orig = R["route_decision"]
    R["route_decision"] = lambda p, t, sc=skip_conf: _orig(p, t, sc)
    try:
        return R["row_results"](d, P[(mode, split)], d.pred_raw.tolist(), tau)
    finally:
        R["route_decision"] = _orig


def pick_tau(sub):
    cand = sub[(sub.tau > 0) & (sub.ask_rate <= MAX_ASK)]
    if cand.empty:
        return sub[sub.tau > 0].nsmallest(1, "tau").iloc[0]
    return cand.sort_values(["exec_precision", "tau"], ascending=[False, True]).iloc[0]


def val_select(mode, taus, confs):
    grid = []
    for sc in confs:
        for sname, sfns in SKIP_SETS.items():
            for tau in taus:
                s = summarize_rr(evaluate(mode, "val", tau, sc, sfns))
                grid.append({"mode": mode, "skip_conf": sc, "skip_set": sname, "tau": tau, **{k: float(v) for k, v in s.items()}})
    G = pd.DataFrame(grid)
    G.to_csv(C.RES_DIR / f"pipeline_val_grid_{mode}.csv", index=False, encoding="utf-8-sig")
    best = pd.DataFrame([pick_tau(s) for _, s in G.groupby(["skip_conf", "skip_set"])])
    ranked = best.sort_values(["pipeline_incl_ask", "ask_rate", "exec_precision"], ascending=[False, True, False])
    print(f"\n[val:{mode}] 상위 5 설정")
    print(ranked[["skip_conf", "skip_set", "tau", "ask_rate", "exec_precision", "pipeline_incl_ask", "wrong_exec_rate",
                  "llm_skip_rate", "intent_acc"]].head(5).round(4).to_string(index=False))
    return ranked.iloc[0]


RES = {}


def run_test(tag, mode, tau, sc, sname):
    sfns = SKIP_SETS[sname]
    rr = evaluate(mode, "test", tau, sc, sfns)
    S = {k: float(v) for k, v in summarize_rr(rr).items()}
    Sv = {k: float(v) for k, v in summarize_rr(evaluate(mode, "val", tau, sc, sfns)).items()}
    RES[tag] = {"mode": mode, "tau": tau, "skip_conf": sc, "skip_set": sname, "skip_fns": list(sfns), "test": S, "val": Sv}
    rr.to_csv(C.RES_DIR / f"pipeline_test_rows_{tag}.csv", index=False, encoding="utf-8-sig")
    print(f"[test:{tag}] tau {tau} skip {sc} {sname} -> pipeline_incl_ask {S['pipeline_incl_ask']:.4f}, "
          f"wrong_exec {S['wrong_exec_rate']:.4f}, skip {S['llm_skip_rate']:.4f}, ask {S['ask_rate']:.4f}, intent_acc {S['intent_acc']:.4f}")


b21 = (V21["ask_tau"], V21["skip_llm_conf"], "next_stop 불포함" if tuple(V21["skip_llm_fns"]) == ("scan", "other") else "next_stop 포함")
run_test("roberta_v2_1", "roberta", *b21)
run_test("qwen3_prob_v21cfg", "qwen3_prob", *b21)
bp = val_select("qwen3_prob", TAUS, SKIP_CONFS)
run_test("qwen3_prob", "qwen3_prob", float(bp.tau), float(bp.skip_conf), bp.skip_set)
ba = val_select("qwen3_argmax", [0.05], [0.9])
run_test("qwen3_argmax", "qwen3_argmax", 0.05, 0.9, ba.skip_set)

json.dump(RES, open(C.RES_DIR / "pipeline_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
cols = ["intent_acc", "intent_macro_f1", "fc_final_ok", "pipeline_incl_ask", "pipeline_direct_ok", "exec_precision", "wrong_exec_rate",
        "ask_rate", "llm_skip_rate"]
T = pd.DataFrame({k: {c: v["test"][c] for c in cols} for k, v in RES.items()})
print("\n=== test (431) ===")
print(T.round(4).to_string())
T.to_csv(C.RES_DIR / "pipeline_test_compare.csv", encoding="utf-8-sig")
