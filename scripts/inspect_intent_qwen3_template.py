"""1단계: Qwen3 채팅 템플릿(enable_thinking=False)의 추론 프롬프트와 학습 문자열이 같은 형식인지 확인."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import intent_qwen_common as C

tok = C.load_tokenizer()
text = "다음 어디야"
prompt, full = C.build_train_string(tok, text, "next_stop")
print("=== 추론 프롬프트 ===")
print(repr(prompt))
print("=== 학습 문자열 ===")
print(repr(full))
print("학습 문자열이 추론 프롬프트로 시작:", full.startswith(prompt))
print("추가분(정답+끝):", repr(full[len(prompt):]))
print("think 블록 개수 추론/학습:", prompt.count("<think>"), full.count("<think>"))

print("\n=== 라벨 토큰화 ===")
ft = C.label_first_tokens(tok)
for f, ids in ft.items():
    print(f"{f:14s} {ids} {[tok.decode([i]) for i in ids]}")
firsts = [v[0] for v in ft.values()]
print("첫 토큰 서로 다름:", len(set(firsts)) == len(firsts))
print("eos:", tok.eos_token, tok.eos_token_id, "pad:", tok.pad_token, tok.pad_token_id)

ex = C.build_example(tok, text, "next_stop")
print("학습되는 부분:", repr(tok.decode([t for t, l in zip(ex["input_ids"], ex["labels"]) if l != -100])))
import numpy as np
df = __import__("pandas").read_csv(C.DATA_CSV, encoding="utf-8-sig")
lens = [len(tok(C.build_prompt(tok, t), add_special_tokens=False)["input_ids"]) for t in df.text]
print(f"프롬프트 토큰 길이: 평균 {np.mean(lens):.0f}, 최대 {max(lens)} (전체 {len(df)}문장)")
