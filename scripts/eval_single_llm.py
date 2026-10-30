"""1단계: 의도분류 없이 FC 모델(out/fc_merged) 하나만 쓸 때의 성능을 v2.1 과 같은 test 431문장·같은 지표 코드로 측정.

- 재학습 없음. 평가 코드는 노트북 셀(row_results / summarize_rr, scripts/nb_rules.py)을 그대로 쓴다.
- FC 단독 = FC 출력의 fn 을 그대로 의도로 보고(one-hot), 되묻기 없음(tau 0), LLM 건너뛰기 없음(SKIP_FNS 비움).
- v2.1 기준값은 results/v2_1/ 의 저장된 결과(같은 코드로 계산된 것)를 쓴다.
- 지연은 이 PC(GPU)에서 문장 하나씩(배치 1) 잰다. 보드 값이 아니다.

실행:  .venv\\Scripts\\python.exe scripts/eval_single_llm.py
결과:  results/single_llm/
"""
import json, os, sys, time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nb_rules import load_rules, ROOT

OUT = f"{ROOT}/results/single_llm"
os.makedirs(OUT, exist_ok=True)

R = load_rules(with_route=True)
FUNCS, LABEL2ID, SYSTEM_PROMPT = R["FUNCS"], R["LABEL2ID"], R["SYSTEM_PROMPT"]
parse_call, summarize_rr = R["parse_call"], R["summarize_rr"]
V21 = json.load(open(f"{ROOT}/config/pipeline_v2_1.json", encoding="utf-8"))
assert SYSTEM_PROMPT == V21["system_prompt"], "노트북 시스템 프롬프트와 v2.1 설정이 다름"

import torch
from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer

DEVICE = "cuda"
DTYPE = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
intent_df = pd.read_csv(f"{ROOT}/data/intent_dataset.csv", encoding="utf-8-sig")
fc_df = pd.read_csv(f"{ROOT}/data/fc_dataset.csv")
vi = intent_df[intent_df.split == "test"].reset_index(drop=True)
vf = fc_df[fc_df.split == "test"].reset_index(drop=True)
assert len(vf) == 431 and (vi.id.values == vf.id.values).all()

tok = AutoTokenizer.from_pretrained(f"{ROOT}/out/fc_merged")
tok.padding_side = "left"
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
model = AutoModelForCausalLM.from_pretrained(f"{ROOT}/out/fc_merged", torch_dtype=DTYPE, device_map={"": 0}).eval()


def prompt(t):
    return tok.apply_chat_template([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": t}],
                                   tokenize=False, add_generation_prompt=True, enable_thinking=False)


# ---------------- (1) 배치 생성: v2.1 평가와 같은 조건 ----------------
@torch.no_grad()
def generate_batch(texts, bs=8):
    outs = []
    for i in range(0, len(texts), bs):
        enc = tok([prompt(t) for t in texts[i:i + bs]], return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
        gen = model.generate(**enc, max_new_tokens=64, do_sample=False, pad_token_id=tok.pad_token_id)
        outs += tok.batch_decode(gen[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
    return [o.strip() for o in outs]


raws = generate_batch(vf.text.tolist())
prev = pd.read_csv(f"{ROOT}/results/v2_1/test_pred_fc.csv", encoding="utf-8-sig")
same = float(np.mean(np.array(raws) == prev.pred_raw.fillna("").values))
print(f"FC 출력이 v2.1 저장 결과와 같은 비율: {same:.4f}")

# ---------------- (2) FC 단독 파이프라인: 지표 ----------------
fns = [parse_call(r).get("fn", "other") for r in raws]
assert all(f in LABEL2ID for f in fns)
P = np.zeros((len(raws), len(FUNCS)))
P[np.arange(len(raws)), [LABEL2ID[f] for f in fns]] = 1.0
R["SKIP_FNS"] = ()
rr = R["row_results"](vf, P, raws, 0.0)
S = {k: float(v) for k, v in summarize_rr(rr).items()}
ref = json.load(open(f"{ROOT}/results/v2_1/test_summary.json", encoding="utf-8"))["test"]["v2_1"]
rr21 = pd.read_csv(f"{ROOT}/results/v2_1/test_rows_v2_1.csv", encoding="utf-8-sig")
assert (rr21.id.values == rr.id.values).all()

# 슬롯 부족으로 resolve 가 되묻는 비율 (FC 단독에서도 일어나는 되묻기; 지표의 '되묻기'와는 다른 종류)
slot_ask = float(np.mean([not R["resolve"](parse_call(r), R["CURRENT_STORE"])["ok"] for r in raws]))
slot_ask_gold = float(np.mean([not R["resolve"](json.loads(t), R["CURRENT_STORE"])["ok"] for t in vf.target]))

# 클래스별 정확도·혼동행렬
from sklearn.metrics import confusion_matrix
cm_fc = confusion_matrix(rr.gold_fn, rr.intent_pred, labels=FUNCS)
cm_rb = confusion_matrix(rr21.gold_fn, rr21.intent_pred, labels=FUNCS)
per_class = pd.DataFrame({
    "n": rr.groupby("gold_fn").size().reindex(FUNCS),
    "roberta(의도분류)": rr21.groupby("gold_fn").intent_ok.mean().reindex(FUNCS),
    "FC fn": rr.groupby("gold_fn").intent_ok.mean().reindex(FUNCS),
    "v2.1 최종 정답(되묻기 포함)": rr21.assign(f=rr21.ok | (rr21.route == "ask") & rr21.after_choice_ok).groupby("gold_fn").f.mean().reindex(FUNCS),
    "FC단독 최종 정답": rr.ok.groupby(rr.gold_fn).mean().reindex(FUNCS),
})
per_class.to_csv(f"{OUT}/per_class.csv", encoding="utf-8-sig")

# 두 방식이 다르게 나온 문장
a = rr21.ok | ((rr21.route == "ask") & rr21.after_choice_ok)
b = rr.ok
diff = pd.DataFrame({"id": rr.id, "text": rr.text, "gold_fn": rr.gold_fn, "target": rr.target, "v2_1_route": rr21.route,
                     "v2_1_intent": rr21.intent_pred, "fc_pred_raw": rr.pred_raw, "fc_fn": rr.intent_pred,
                     "v2_1_ok": a, "fc_only_ok": b, "ambiguity": rr.ambiguity, "source": rr.source})
diff[a != b].to_csv(f"{OUT}/disagree_v2_1_vs_fc_only.csv", index=False, encoding="utf-8-sig")
paired = {"both_ok": int((a & b).sum()), "only_v2_1_ok": int((a & ~b).sum()), "only_fc_only_ok": int((~a & b).sum()),
          "both_wrong": int((~a & ~b).sum())}
rr.to_csv(f"{OUT}/test_rows_fc_only.csv", index=False, encoding="utf-8-sig")

# 슬롯까지 맞는지(FC 완전일치)와 fn 만 틀린 경우 구분
fn_wrong = rr[~rr.intent_ok][["id", "text", "gold_fn", "intent_pred", "pred_raw", "ambiguity", "source"]]
fn_wrong.to_csv(f"{OUT}/fn_wrong_fc.csv", index=False, encoding="utf-8-sig")

# ---------------- (3) 지연: 배치 1, 문장별 ----------------
mi = AutoModelForSequenceClassification.from_pretrained(f"{ROOT}/out/intent_model").eval().to(DEVICE)
mt = AutoTokenizer.from_pretrained(f"{ROOT}/out/intent_model")


def sync():
    torch.cuda.synchronize()


@torch.no_grad()
def time_fc(text):
    enc = tok([prompt(text)], return_tensors="pt", add_special_tokens=False).to(model.device)
    sync(); t = time.perf_counter()
    g = model.generate(**enc, max_new_tokens=64, do_sample=False, pad_token_id=tok.pad_token_id)
    sync(); ms = (time.perf_counter() - t) * 1000
    new = g[0, enc["input_ids"].shape[1]:].tolist()
    n_noeos = len([x for x in new if x not in (151645, 151643)])
    return ms, n_noeos, enc["input_ids"].shape[1]


@torch.no_grad()
def time_intent(text):
    enc = mt([text], truncation=True, max_length=64, return_tensors="pt").to(DEVICE)
    sync(); t = time.perf_counter()
    mi(**enc).logits.softmax(-1).cpu()
    sync()
    return (time.perf_counter() - t) * 1000


for t in vf.text[:6]:                      # 워밍업
    time_fc(t); time_intent(t)
lat = []
for t in vf.text:
    ms, n, plen = time_fc(t)
    lat.append({"fc_ms": ms, "gen_tokens": n, "prompt_tokens": plen, "intent_ms": time_intent(t)})
L = pd.concat([rr[["id", "gold_fn"]].reset_index(drop=True), pd.DataFrame(lat)], axis=1)
L["v2_1_route"] = rr21.route.values
L["v2_1_ms"] = L.intent_ms + np.where(L.v2_1_route == "skip", 0.0, L.fc_ms)       # 건너뛴 문장은 LLM 을 안 부름
L["v2_1_ms"] = np.where(L.v2_1_route == "ask", L.intent_ms, L.v2_1_ms)             # 되묻기는 의도분류까지만
L.to_csv(f"{OUT}/latency_per_sentence.csv", index=False, encoding="utf-8-sig")


def stat(x):
    return {"mean": float(x.mean()), "median": float(x.median()), "p95": float(x.quantile(0.95))}


lat_by_fn = {f: {"n": int((L.gold_fn == f).sum()), "fc_only_ms": stat(L[L.gold_fn == f].fc_ms),
                 "v2_1_ms": stat(L[L.gold_fn == f].v2_1_ms), "gen_tokens_mean": float(L[L.gold_fn == f].gen_tokens.mean()),
                 "gen_tokens_max": int(L[L.gold_fn == f].gen_tokens.max())} for f in FUNCS}
novalue = L[L.gold_fn.isin(["next_stop", "scan", "other"])]
lat_sum = {"all": {"fc_only_ms": stat(L.fc_ms), "v2_1_ms": stat(L.v2_1_ms), "intent_ms": stat(L.intent_ms),
                   "gen_tokens_mean": float(L.gen_tokens.mean()), "prompt_tokens_mean": float(L.prompt_tokens.mean())},
           "no_value_fns(next_stop,scan,other)": {"n": len(novalue), "fc_only_ms": stat(novalue.fc_ms),
                                                  "gen_tokens_mean": float(novalue.gen_tokens.mean()),
                                                  "gen_tokens_max": int(novalue.gen_tokens.max())},
           "by_fn": lat_by_fn,
           "env": f"{torch.cuda.get_device_name(0)}, {str(DTYPE)}, 배치 1, torch {torch.__version__}"}

# ---------------- (4) 정답 JSON 길이(토큰) -> max_new_tokens 64 충분한가 ----------------
tl = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in fc_df.target]
gen_tok_stats = {"gold_json_tokens_max_all_splits": int(max(tl)), "gold_json_tokens_mean": float(np.mean(tl)),
                 "pred_tokens_max_test": int(L.gen_tokens.max())}

summary = {"fc_only": S, "v2_1": {k: float(v) for k, v in ref.items()}, "same_raw_as_saved_v2_1": same,
           "slot_ask_rate_fc_only": slot_ask, "slot_ask_rate_gold": slot_ask_gold, "paired_final_ok": paired,
           "confusion_labels": FUNCS, "confusion_fc": cm_fc.tolist(), "confusion_roberta": cm_rb.tolist(),
           "latency": lat_sum, "token_stats": gen_tok_stats}
json.dump(summary, open(f"{OUT}/summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

rows = [("의도분류 정확도(fn)", "intent_acc"), ("의도분류 macro-F1", "intent_macro_f1"), ("FC JSON 유효율", "fc_json_valid"),
        ("FC 완전일치", "fc_exact"), ("FC 값 F1", "fc_slot_f1"), ("전체 최종 정답(되묻기 없이)", "pipeline_acc_no_ask"),
        ("전체 최종 정답(되묻기 포함)", "pipeline_incl_ask"), ("틀리게 실행한 비율", "wrong_exec_rate"),
        ("되묻기 비율(의도분류 margin)", "ask_rate"), ("LLM 건너뛴 비율", "llm_skip_rate")]
print("\n=== test 431: v2.1 vs FC 단독 ===")
print(pd.DataFrame({n: {"v2.1": ref[k], "FC 단독": S[k]} for n, k in rows}).T.round(4).to_string())
print("\n되묻기 아닌 슬롯 부족 질문 비율(FC 단독 예측 / 정답):", round(slot_ask, 4), round(slot_ask_gold, 4))
print("\n클래스별\n", per_class.round(3).to_string())
print("\n혼동행렬 FC (행 정답)\n", pd.DataFrame(cm_fc, index=FUNCS, columns=FUNCS))
print("\n짝 비교(최종 정답):", paired)
print("\n지연:", json.dumps({k: v for k, v in lat_sum.items() if k != "by_fn"}, ensure_ascii=False, indent=1))
print(pd.DataFrame({f: {"n": v["n"], "FC단독 평균ms": v["fc_only_ms"]["mean"], "v2.1 평균ms": v["v2_1_ms"]["mean"],
                        "생성토큰 평균": v["gen_tokens_mean"], "최대": v["gen_tokens_max"]} for f, v in lat_by_fn.items()}).T.round(1).to_string())
print("\n토큰:", gen_tok_stats)
