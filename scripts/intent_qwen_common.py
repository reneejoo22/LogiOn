"""Qwen3-0.6B 의도분류 공용 코드. 학습·평가·캘리브레이션·보드가 모두 이 파일의 상수와 함수를 쓴다.

FC 모델(Qwen2.5-1.5B, notebooks/LogiOn_AI_pipeline.ipynb 25~26번 셀)의 build_prompt/build_example/collate 를
그대로 따르되, 시스템 지시와 정답만 의도분류용으로 바꿨다.
"""
import os
from pathlib import Path

import pandas as pd

ROOT = Path(os.environ.get("ROOT", Path(__file__).resolve().parents[1]))
BASE = "Qwen/Qwen3-0.6B"
FUNCS = ["next_stop", "stop_items", "complete", "report_issue", "scan", "other"]  # 노트북 FUNCS 순서와 같다
SEED = 42

# 학습, 평가, 캘리브레이션, 보드 추론이 이 문장을 그대로 쓴다. 바꾸면 다시 학습해야 한다.
INTENT_SYSTEM = (
    "편의점 납품기사의 말이 어떤 기능인지 분류하라. "
    "next_stop, stop_items, complete, report_issue, scan, other 중 하나의 단어만 출력하라."
)

DATA_CSV = ROOT / "data" / "intent_dataset.csv"
OUT_LORA = ROOT / "out" / "intent_qwen3_lora"
OUT_CKPT = ROOT / "out" / "intent_qwen3_ckpt"
OUT_MERGED = ROOT / "out" / "intent_qwen3_merged"
RES_DIR = ROOT / "results" / "intent_qwen3"


def load_tokenizer(path=BASE):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(path)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return tok


def chat(tok, messages, add_generation_prompt):
    return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_generation_prompt,
                                   enable_thinking=False)


def build_prompt(tok, text):
    """추론 프롬프트. 생성 시작 위치(assistant 턴 머리)까지."""
    return chat(tok, [{"role": "system", "content": INTENT_SYSTEM}, {"role": "user", "content": text}], True)


def build_train_string(tok, text, label):
    """학습 문자열. 추론 프롬프트로 시작해야 하고, 뒤에 정답 + <|im_end|> 가 붙는다."""
    prompt = build_prompt(tok, text)
    full = chat(tok, [{"role": "system", "content": INTENT_SYSTEM}, {"role": "user", "content": text},
                      {"role": "assistant", "content": label}], False)
    if not full.startswith(prompt):
        raise ValueError(f"학습 문자열이 추론 프롬프트로 시작하지 않음:\n{prompt!r}\n{full!r}")
    return prompt, full


def build_example(tok, text, label, max_len=160):
    prompt, full = build_train_string(tok, text, label)
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    f_ids = tok(full, add_special_tokens=False)["input_ids"][:max_len]
    labels = [-100] * len(p_ids) + f_ids[len(p_ids):]
    return {"input_ids": f_ids, "attention_mask": [1] * len(f_ids), "labels": labels[:len(f_ids)]}


def collate_factory(tok):
    import torch

    def collate(batch):
        m = max(len(b["input_ids"]) for b in batch)
        pad = lambda x, v: x + [v] * (m - len(x))
        return {"input_ids": torch.tensor([pad(b["input_ids"], tok.pad_token_id) for b in batch]),
                "attention_mask": torch.tensor([pad(b["attention_mask"], 0) for b in batch]),
                "labels": torch.tensor([pad(b["labels"], -100) for b in batch])}
    return collate


def load_split(split):
    df = pd.read_csv(DATA_CSV, encoding="utf-8-sig")
    return df[df.split == split].reset_index(drop=True)


def label_first_tokens(tok):
    """라벨마다 첫 토큰 id. 서로 달라야 첫 토큰 확률로 6개 확률을 만들 수 있다."""
    return {f: tok(f, add_special_tokens=False)["input_ids"] for f in FUNCS}


# ---------------- 추론 ----------------
def load_model(path, device_map=None):
    import torch
    from transformers import AutoModelForCausalLM
    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    kw = {"device_map": {"": 0}} if torch.cuda.is_available() and device_map is None else {}
    if device_map == "cpu":
        dtype, kw = torch.float32, {}
    m = AutoModelForCausalLM.from_pretrained(path, torch_dtype=dtype, **kw)
    return m.eval()


def _device(model):
    return next(model.parameters()).device


def generate_raw(model, tok, texts, bs=16, max_new_tokens=8):
    """탐욕적 디코딩. 특수 토큰을 남긴 원문 문자열 리스트 (<think> 같은 군더더기 확인용)."""
    import torch
    tok.padding_side = "left"
    outs = []
    for i in range(0, len(texts), bs):
        prompts = [build_prompt(tok, t) for t in texts[i:i + bs]]
        enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(_device(model))
        with torch.no_grad():
            g = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                               pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id)
        outs += tok.batch_decode(g[:, enc["input_ids"].shape[1]:], skip_special_tokens=False)
    return outs


def clean_label(raw):
    """<|im_end|> 앞까지 잘라 공백을 지운 문자열. 6개 라벨이 아니면 형식 오류."""
    return raw.split("<|im_end|>")[0].replace("<|endoftext|>", "").strip()


def first_token_probs(model, tok, texts, bs=16):
    """첫 생성 위치 로짓에서 6개 라벨의 첫 토큰만 골라 소프트맥스. (확률 n×6, 6개가 전체 어휘에서 차지한 확률 n)"""
    import numpy as np
    import torch
    tok.padding_side = "left"
    ids = [tok(f, add_special_tokens=False)["input_ids"][0] for f in FUNCS]
    P, mass = [], []
    for i in range(0, len(texts), bs):
        prompts = [build_prompt(tok, t) for t in texts[i:i + bs]]
        enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(_device(model))
        with torch.no_grad():
            logits = model(**enc).logits[:, -1, :].float()
        full = torch.softmax(logits, -1)
        P.append(torch.softmax(logits[:, ids], -1).cpu().numpy())
        mass.append(full[:, ids].sum(-1).cpu().numpy())
    return np.concatenate(P), np.concatenate(mass)
