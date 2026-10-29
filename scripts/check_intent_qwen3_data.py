"""2단계: 학습/검증/테스트 분할 확인. 문장 누출, 라벨 분포, 학습 문자열 샘플."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import intent_qwen_common as C

tr, va, te = (C.load_split(s) for s in ("train", "val", "test"))
print("건수 train/val/test:", len(tr), len(va), len(te))
for n, d in (("train", tr), ("val", va), ("test", te)):
    print(n, d.label.value_counts().reindex(C.FUNCS).to_dict())
S = {n: set(d.text) for n, d in (("train", tr), ("val", va), ("test", te))}
print("겹치는 문장 train∩val:", len(S["train"] & S["val"]), " train∩test:", len(S["train"] & S["test"]),
      " val∩test:", len(S["val"] & S["test"]))
print("라벨 집합 외 값:", (set(tr.label) | set(va.label) | set(te.label)) - set(C.FUNCS))
print("중복 문장 내 라벨 충돌(train):", int((tr.groupby("text").label.nunique() > 1).sum()))
print("source:", tr.source.value_counts().to_dict())
