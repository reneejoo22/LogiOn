"""v2.1 설정 고르기: 되묻기 tau, LLM 건너뛰기 기준, 쓸 모델 조합을 **val 로만** 고르고 test 는 한 번만 평가.

고르는 방법은 돌리기 전에 logs/ai-improve-1022.md "v2.1 작업 / 0. 선정 규칙" 에 적어 두었다. 요약:
  1) 격자 = 의도분류 v1/v2 × FC v1/v2 × 건너뛰기 기준 {0.9,0.95,0.98,0.99} × 건너뛰기 대상 {next_stop 포함/불포함}
  2) 설정마다 tau 는 '되묻기 비율 ≤10% 중 실행 정확도(exec_precision) 최고, 동률이면 작은 tau'
  3) 그렇게 tau 가 정해진 32개 설정 중 val 파이프라인 정확도(pipeline_incl_ask) 최고를 선택
  4) tau 와 건너뛰기 기준은 서로 영향을 주므로(되묻기 판정이 먼저) 1차원으로 나눠 고르지 않고 한 격자에서 함께 고름

지표 계산은 노트북 셀(pipeline_rows/summarize_rr)을 그대로 불러 쓴다 (scripts/nb_rules.py).

실행:  python scripts/select_pipeline_v2_1.py
결과:  results/v2_1/ (val_grid.csv, val_tau_sweep_*.csv, test_summary.json, test_pred_*.csv, comparison_v1_v2_v21.csv)
       config/pipeline_v2_1.json  (고른 설정: 모델 경로, tau, 건너뛰기 기준, 대상 fn)
"""
import argparse, gc, json, os, sys, time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nb_rules import load_rules, ROOT

ap = argparse.ArgumentParser()
ap.add_argument("--results", default=f"{ROOT}/results/v2_1")
ap.add_argument("--config", default=f"{ROOT}/config/pipeline_v2_1.json")
ap.add_argument("--max-ask", type=float, default=0.10)
ap.add_argument("--gen-bs", type=int, default=8)
args = ap.parse_args()

SKIP_CONFS = [0.9, 0.95, 0.98, 0.99]
SKIP_SETS = {"next_stop 포함": ("next_stop", "scan", "other"), "next_stop 불포함": ("scan", "other")}
MODELS = {"v1": f"{ROOT}/out_v1", "v2": f"{ROOT}/out"}
TAUS = [0.0] + [round(0.05 * k, 2) for k in range(1, 11)]

R = load_rules(with_route=True)
pipeline_rows, summarize_rr, ask_stats = R["pipeline_rows"], R["summarize_rr"], R["ask_stats"]
ID2LABEL, LABEL2ID, FUNCS = R["ID2LABEL"], R["LABEL2ID"], R["FUNCS"]
SYSTEM_PROMPT = R["SYSTEM_PROMPT"]

import torch
from transformers import AutoModelForSequenceClassification, AutoModelForCausalLM, AutoTokenizer

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
intent_df = pd.read_csv(f"{ROOT}/data/intent_dataset.csv")
fc_df = pd.read_csv(f"{ROOT}/data/fc_dataset.csv")
SPLITS = {s: (intent_df[intent_df.split == s].reset_index(drop=True), fc_df[fc_df.split == s].reset_index(drop=True))
          for s in ("val", "test")}
for s, (vi, vf) in SPLITS.items():
    assert (vi.id.values == vf.id.values).all(), f"{s}: 두 CSV 의 문장 순서가 다름"
print(f"val {len(SPLITS['val'][0])}건 / test {len(SPLITS['test'][0])}건")


@torch.no_grad()
def intent_probs(model, tok, texts, bs=64):
    out = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], truncation=True, max_length=64, padding=True, return_tensors="pt").to(model.device)
        out.append(model(**enc).logits.float().softmax(-1).cpu().numpy())
    return np.concatenate(out)


@torch.no_grad()
def fc_generate(model, tok, texts, bs):
    """노트북 평가와 같은 조건(탐욕적 디코딩, 같은 SYSTEM_PROMPT, 왼쪽 패딩)."""
    def prompt(t):
        return tok.apply_chat_template([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": t}],
                                       tokenize=False, add_generation_prompt=True, enable_thinking=False)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    outs = []
    for i in range(0, len(texts), bs):
        enc = tok([prompt(t) for t in texts[i:i + bs]], return_tensors="pt", padding=True,
                  add_special_tokens=False).to(model.device)
        gen = model.generate(**enc, max_new_tokens=64, do_sample=False, pad_token_id=tok.pad_token_id)
        outs += tok.batch_decode(gen[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
    return [o.strip() for o in outs]


# ---------------- 1) 두 모델의 val·test 예측을 미리 다 만들어 둠 (한 번에 하나씩 올려서 VRAM 절약) ----------------
P = {}        # P[(의도분류 버전, split)] = 확률 배열
RAW = {}      # RAW[(FC 버전, split)]     = LLM 출력 문자열
for ver, d in MODELS.items():
    t0 = time.time()
    m = AutoModelForSequenceClassification.from_pretrained(f"{d}/intent_model").eval().to(DEVICE)
    m.config.torchscript = False
    tk = AutoTokenizer.from_pretrained(f"{d}/intent_model")
    for s, (vi, _) in SPLITS.items():
        P[(ver, s)] = intent_probs(m, tk, vi.text.tolist())
    del m, tk
    gc.collect(); torch.cuda.empty_cache()
    print(f"의도분류 {ver}: 확률 계산 완료 ({time.time() - t0:.0f}초)")

for ver, d in MODELS.items():
    t0 = time.time()
    m = AutoModelForCausalLM.from_pretrained(f"{d}/fc_merged", torch_dtype=DTYPE, device_map={"": 0}).eval()
    tk = AutoTokenizer.from_pretrained(f"{d}/fc_merged")
    for s, (_, vf) in SPLITS.items():
        RAW[(ver, s)] = fc_generate(m, tk, vf.text.tolist(), args.gen_bs)
    del m, tk
    gc.collect(); torch.cuda.empty_cache()
    print(f"function calling {ver}: 생성 완료 ({time.time() - t0:.0f}초)")


def evaluate(intent_ver, fc_ver, split, tau, skip_conf, skip_fns):
    """한 설정으로 한 split 을 평가. 노트북과 같은 지표 계산."""
    vi, vf = SPLITS[split]
    d = vf.assign(pred_raw=RAW[(fc_ver, split)])
    R["SKIP_FNS"] = skip_fns                       # route_decision 이 참조하는 전역을 바꿈
    _orig = R["route_decision"]
    R["route_decision"] = lambda p, t, sc=skip_conf: _orig(p, t, sc)
    try:
        rr = R["row_results"](d, P[(intent_ver, split)], d.pred_raw.tolist(), tau)
    finally:
        R["route_decision"] = _orig
    return rr


# ---------------- 2) val 격자 ----------------
print("\n[val] 격자 훑기 (의도분류 2 × FC 2 × 건너뛰기 기준 4 × 건너뛰기 대상 2 × tau 11)")
grid = []
for iv in MODELS:
    for fv in MODELS:
        for sc in SKIP_CONFS:
            for sname, sfns in SKIP_SETS.items():
                for tau in TAUS:
                    s = summarize_rr(evaluate(iv, fv, "val", tau, sc, sfns))
                    grid.append({"intent": iv, "fc": fv, "skip_conf": sc, "skip_set": sname, "tau": tau,
                                 **{k: float(v) for k, v in s.items()}})
G = pd.DataFrame(grid)
os.makedirs(args.results, exist_ok=True)
G.to_csv(f"{args.results}/val_grid.csv", index=False, encoding="utf-8-sig")
print(f"격자 {len(G)}줄 저장 -> {args.results}/val_grid.csv")


def pick_tau_by(sub, metric):
    """되묻기 비율 ≤ max_ask 인 tau>0 중 metric 최고 (동률이면 작은 tau). 후보가 없으면 가장 작은 tau."""
    cand = sub[(sub.tau > 0) & (sub.ask_rate <= args.max_ask)]
    if cand.empty:
        return sub[sub.tau > 0].nsmallest(1, "tau").iloc[0]
    return cand.sort_values([metric, "tau"], ascending=[False, True]).iloc[0]


KEY = ["intent", "fc", "skip_conf", "skip_set"]
best_new = pd.DataFrame([pick_tau_by(s, "exec_precision") for _, s in G.groupby(KEY)])
best_old = pd.DataFrame([pick_tau_by(s, "ask_incl_success") for _, s in G.groupby(KEY)])
best_new.to_csv(f"{args.results}/val_best_by_exec_precision.csv", index=False, encoding="utf-8-sig")
best_old.to_csv(f"{args.results}/val_best_by_ask_incl_success.csv", index=False, encoding="utf-8-sig")

# 1-1 비교용: 지금 쓰는(v2) 조합·기본 건너뛰기 설정에서 두 기준이 각각 어떤 tau 를 고르는지
v2_base = G[(G.intent == "v2") & (G.fc == "v2") & (G.skip_conf == 0.9) & (G.skip_set == "next_stop 포함")]
v2_base.to_csv(f"{args.results}/val_tau_sweep_v2_base.csv", index=False, encoding="utf-8-sig")
tau_cmp = {
    "설정": "의도분류 v2 + FC v2, 건너뛰기 기준 0.9, next_stop 포함 (= v2 와 같은 설정)",
    "기존 기준(되묻기 포함 성공률)": {k: float(pick_tau_by(v2_base, "ask_incl_success")[k])
                                      for k in ("tau", "ask_rate", "exec_precision", "ask_incl_success", "pipeline_incl_ask")},
    "새 기준(실행 정확도)": {k: float(pick_tau_by(v2_base, "exec_precision")[k])
                              for k in ("tau", "ask_rate", "exec_precision", "ask_incl_success", "pipeline_incl_ask")},
}
print("\n[1-1] 같은 설정에서 두 기준이 고른 tau")
print(json.dumps(tau_cmp, ensure_ascii=False, indent=2))

# 1-3: tau 가 정해진 32 설정 중 val 파이프라인 정확도 최고
ranked = best_new.sort_values(["pipeline_incl_ask", "ask_rate", "exec_precision"], ascending=[False, True, False])
best = ranked.iloc[0]
print("\n[1-2·1-3] val 파이프라인 정확도 상위 8개 설정")
cols = KEY + ["tau", "ask_rate", "exec_precision", "pipeline_incl_ask", "wrong_exec_rate", "llm_skip_rate", "intent_acc", "fc_final_ok"]
print(ranked[cols].head(8).round(4).to_string(index=False))
print("\n고른 설정:", {k: (float(best[k]) if k in ("tau", "skip_conf") else best[k]) for k in KEY + ["tau"]})

# 참고: 4개 모델 조합 비교 (각 조합의 최선 설정)
combo = ranked.groupby(["intent", "fc"]).head(1)[cols].sort_values("pipeline_incl_ask", ascending=False)
combo.to_csv(f"{args.results}/val_combo_compare.csv", index=False, encoding="utf-8-sig")
print("\n[1-3] 모델 조합별 최선 (val)")
print(combo.round(4).to_string(index=False))

# ---------------- 3) 고른 설정으로 test 를 한 번만 평가 ----------------
CFG = {"intent": best.intent, "fc": best.fc, "tau": float(best.tau), "skip_conf": float(best.skip_conf),
       "skip_set": best.skip_set, "skip_fns": list(SKIP_SETS[best.skip_set])}
print(f"\n[test] 위 설정으로 한 번만 평가 (n={len(SPLITS['test'][0])})")
RR21 = evaluate(CFG["intent"], CFG["fc"], "test", CFG["tau"], CFG["skip_conf"], tuple(CFG["skip_fns"]))
S21 = {k: float(v) for k, v in summarize_rr(RR21).items()}
print(json.dumps(S21, ensure_ascii=False, indent=2))

# v1·v2 를 같은 test 에서 같은 코드로 다시 계산 (v2 = 기존 설정: tau 0.05, 건너뛰기 0.9, next_stop 포함)
V2_OLD = {"intent": "v2", "fc": "v2", "tau": 0.05, "skip_conf": 0.9, "skip_fns": ("next_stop", "scan", "other")}
V1_OLD = {"intent": "v1", "fc": "v1", "tau": 0.35, "skip_conf": 0.9, "skip_fns": ("next_stop", "scan", "other")}
S_ref = {}
for tag, c in (("v1", V1_OLD), ("v2", V2_OLD)):
    rr = evaluate(c["intent"], c["fc"], "test", c["tau"], c["skip_conf"], tuple(c["skip_fns"]))
    S_ref[tag] = {k: float(v) for k, v in summarize_rr(rr).items()}
    rr.to_csv(f"{args.results}/test_rows_{tag}.csv", index=False, encoding="utf-8-sig")

LABELS = [("intent_acc", "의도분류 정확도"), ("intent_macro_f1", "의도분류 macro F1"),
          ("fc_json_valid", "FC JSON 유효율"), ("fc_fn_acc", "FC fn 정확도"), ("fc_exact", "FC 완전일치"),
          ("fc_slot_f1", "FC 값 F1"), ("fc_final_ok", "FC 최종동작일치"),
          ("pipeline_acc_no_ask", "전체 파이프라인(되묻기 없음)"), ("ask_rate", "되묻기 비율"),
          ("ask_incl_success", "되묻기 포함 성공률(의도분류 기준)"), ("pipeline_direct_ok", "파이프라인: 바로 맞게 실행"),
          ("pipeline_incl_ask", "파이프라인: 되묻기 포함 성공"), ("exec_precision", "실행한 것 중 정답 비율"),
          ("wrong_exec_rate", "틀리게 실행한 비율"), ("llm_skip_rate", "LLM 건너뛴 비율")]
CMP = pd.DataFrame([{"지표": name, "v1": S_ref["v1"][k], "v2": S_ref["v2"][k], "v2.1": S21[k],
                     "차이(v2.1-v2)": S21[k] - S_ref["v2"][k]} for k, name in LABELS])
CMP.to_csv(f"{args.results}/comparison_v1_v2_v21.csv", index=False, encoding="utf-8-sig")
print("\n=== test: v1 / v2 / v2.1 ===")
print(CMP.round(4).to_string(index=False))

RR21.to_csv(f"{args.results}/test_rows_v2_1.csv", index=False, encoding="utf-8-sig")
RR21[["id", "text", "target", "source", "ambiguity", "pred_raw", "valid_json", "fn_ok", "exact",
      "tp", "n_pred", "n_gold", "final_ok"]].to_csv(f"{args.results}/test_pred_fc.csv", index=False, encoding="utf-8-sig")
RR21[["id", "text", "target", "source", "ambiguity", "pred_raw", "gold_fn", "intent_pred", "route", "margin",
      "ask_msg", "ok", "in_options", "after_choice_ok"]].to_csv(f"{args.results}/test_pred_pipeline.csv",
                                                                index=False, encoding="utf-8-sig")
ask_rows = RR21[RR21.route == "ask"][["text", "gold_fn", "ask_msg", "in_options", "after_choice_ok"]]
print(f"\n되묻기가 걸린 문장 {len(ask_rows)}건 (최대 15건 표시)")
print(ask_rows.head(15).to_string(index=False) if len(ask_rows) else "(없음)")

by_fn = RR21.assign(ask=RR21.route == "ask").groupby("gold_fn").apply(
    lambda d: pd.Series({"n": len(d), "되묻기": d.ask.mean(), "바로 맞게 실행": ((~d.ask) & d.ok).mean(),
                         "틀리게 실행": ((~d.ask) & ~d.ok).mean(), "FC 최종동작일치": d.final_ok.mean()}),
    include_groups=False)
by_fn.to_csv(f"{args.results}/test_by_fn.csv", encoding="utf-8-sig")
print("\n기능별 (test, v2.1)")
print(by_fn.round(3).to_string())

summary = {
    "note": "선정은 val 383건만 사용, test 431건은 이 설정으로 한 번만 평가함. 선정 규칙은 logs/ai-improve-1022.md 참고.",
    "selected_config": CFG, "tau_criterion_comparison_on_val": tau_cmp,
    "val_best_pipeline_incl_ask": float(best.pipeline_incl_ask),
    "test": {"v2_1": S21, "v2": S_ref["v2"], "v1": S_ref["v1"]},
    "test_ask_examples": ask_rows.head(15).to_dict("records"),
}
json.dump(summary, open(f"{args.results}/test_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

os.makedirs(os.path.dirname(args.config), exist_ok=True)
config = {
    "version": "v2.1",
    "selected_on": "val 383건 (test 는 마지막 1회 평가에만 사용)",
    "intent_model": os.path.relpath(f"{MODELS[CFG['intent']]}/intent_model", ROOT).replace("\\", "/"),
    "fc_model": os.path.relpath(f"{MODELS[CFG['fc']]}/fc_merged", ROOT).replace("\\", "/"),
    "intent_onnx": "export/intent_onnx",
    "system_prompt": SYSTEM_PROMPT,
    "funcs": FUNCS,
    "ask_tau": CFG["tau"],
    "ask_tau_rule": f"val 에서 되묻기 비율 ≤ {args.max_ask:.0%} 중 실행 정확도 최고 (동률이면 작은 tau)",
    "skip_llm_conf": CFG["skip_conf"],
    "skip_llm_fns": CFG["skip_fns"],
    "skip_llm_rule": "이 기능이고 의도분류 확률이 기준 이상이면 LLM 을 부르지 않고 바로 실행",
    "generation": {"do_sample": False, "top_k": 1, "repetition_penalty": 1.1, "max_new_tokens": 64,
                   "eos_token_id": 151645},
    "choice_labels": R["CHOICE_LABEL"], "retry_message": R["RETRY_MSG"],
    "test_metrics": S21,
}
json.dump(config, open(args.config, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n저장: {args.config}")
print(f"저장: {args.results}/ (test_summary.json, comparison_v1_v2_v21.csv, val_grid.csv 등)")
