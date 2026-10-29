"""6단계: RKLLM 양자화 캘리브레이션 발화 생성 -> data/calib_intent_qwen3.json

- 노트북 13번 셀의 render() 를 새 시드로 돌려 만든다 (함수별 80문장 = 480문장, 명확/되묻기/헷갈림 = 0.65/0.20/0.15, 기존 450건과 같은 비율).
- 틀은 train 몫(template_split_v1.json)만 쓴다. 문장은 train·val·test 의 어떤 문장과도 겹치지 않게 걸러낸다.
  (틀은 train 과 같아서 말투 분포는 학습 데이터와 같고, 문장 자체는 새것이다.)
- input 은 1단계에서 확인한 추론 프롬프트(시스템 지시 + 생각 끄기 템플릿)를 그대로 쓴다.
  target 은 병합된 모델이 탐욕적으로 낸 출력(RKLLM 예제 generate_data_quant.py 방식), label 은 정답 (참고용).
"""
import io, contextlib, json, os, random, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import intent_qwen_common as C
from nb_rules import load_rules, NB, ROOT
import pandas as pd

R = load_rules()
nb = json.load(open(NB, encoding="utf-8"))
src = [("".join(c["source"])) for c in nb["cells"] if c["cell_type"] == "code" and "def render(func, tmpl, rng)" in "".join(c["source"])]
assert len(src) == 1
head = src[0].split("TEMPLATE_SPLIT_FIXED = None")[0]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, "<notebook:render>", "exec"), R)
render, ambiguity_of = R["render"], R["ambiguity_of"]

SEED_CALIB = 20261029
PER_FUNC = 80
MIX = {"clear": 0.65, "ask": 0.20, "hard": 0.15}
split = json.load(open(C.ROOT / "data" / "template_split_v1.json", encoding="utf-8"))
df = pd.read_csv(C.DATA_CSV, encoding="utf-8-sig")
seen = set(df.text)
rng = random.Random(SEED_CALIB)

rows = []
for f in C.FUNCS:
    pool = {"clear": [], "ask": [], "hard": []}
    tms = split[f]["train"]
    for _ in range(4000):
        tmpl = rng.choice(tms)
        text, call = render(f, tmpl, rng)
        if text in seen:
            continue
        seen.add(text)
        pool[ambiguity_of(call, tmpl.startswith("!"))].append(text)
    want = {k: int(PER_FUNC * r) for k, r in MIX.items()}
    want["clear"] = PER_FUNC - want["ask"] - want["hard"]
    for k in ("ask", "hard"):                   # 그 유형이 만들어지지 않는 기능(값 빠짐이 없는 기능)은 clear 로 보충
        short = max(0, want[k] - len(pool[k]))
        want[k] -= short
        want["clear"] += short
    assert len(pool["clear"]) >= want["clear"], (f, len(pool["clear"]), want)
    print(f"{f}: {want}")
    for amb, k in want.items():
        rows.append(pd.DataFrame({"text": pool[amb][:k], "label": f, "ambiguity": amb}))
cal = pd.concat(rows, ignore_index=True)
# 부족분 보충 후 함수별 80 확인
if cal.groupby("label").size().min() < PER_FUNC:
    print("경고: 함수별 80 미달", cal.groupby("label").size().to_dict())
assert not (set(cal.text) & set(df.text)), "train/val/test 와 겹침"
assert cal.text.is_unique

# 병합 모델의 출력으로 target 채우기
tok = C.load_tokenizer(C.OUT_MERGED)
model = C.load_model(C.OUT_MERGED)
raw = C.generate_raw(model, tok, cal.text.tolist(), bs=32, max_new_tokens=8)
cal["target"] = [r.split("<|im_end|>")[0].strip() + "<|im_end|>" for r in raw]
cal["input"] = [C.build_prompt(tok, t) for t in cal.text]
agree = float((cal.target.str.replace("<|im_end|>", "", regex=False) == cal.label).mean())

polite = cal.text.str.contains(r"(?:요|니다|세요|죠)\s*$")
pre = cal.text.str.match(r"^(어|음|자|아|저기|그|이제|잠깐)\s")
stats = {"n": len(cal), "per_function": cal.groupby("label").size().to_dict(), "ambiguity": cal.ambiguity.value_counts().to_dict(),
         "polite_ending_rate": float(polite.mean()), "filler_prefix_rate": float(pre.mean()),
         "mean_chars": float(cal.text.str.len().mean()),
         "overlap_with_train_val_test": 0, "model_output_equals_label_rate": agree,
         "seed": SEED_CALIB, "templates_from": "train 몫 (data/template_split_v1.json)",
         "prompt_tokens_max": int(max(len(tok(p, add_special_tokens=False)["input_ids"]) for p in cal.input))}
print(json.dumps(stats, ensure_ascii=False, indent=1))
out = [{"input": i, "target": t, "text": x, "label": l, "ambiguity": a}
       for i, t, x, l, a in zip(cal.input, cal.target, cal.text, cal.label, cal.ambiguity)]
(C.ROOT / "data" / "calib_intent_qwen3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
(C.RES_DIR / "calib_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
print(cal.sample(8, random_state=1)[["text", "label", "ambiguity"]].to_string(index=False))
