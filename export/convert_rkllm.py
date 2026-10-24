"""병합된 function-calling 모델(out/fc_merged) -> RKLLM (RK3588, W8A8) 변환.

** 이 스크립트는 Rockchip 의 rkllm-toolkit 이 설치된 x86 Linux(또는 WSL2 Ubuntu / Docker)에서만 끝까지 돈다. **
Windows 파이썬이나 보드(aarch64)에서는 toolkit 이 없어 변환 단계에서 멈춘다. 그래도 1단계(캘리브레이션 파일 만들기)는
toolkit 없이 어디서나 돌아가므로 `--prepare-only` 로 먼저 확인할 수 있다.

실행 순서
  1) (어디서나)  python export/convert_rkllm.py --prepare-only
       -> export/calibration_w8a8.json 생성, max_context·eos 점검 결과 출력
  2) (x86 Linux, rkllm-toolkit 설치된 환경)
       pip install rkllm_toolkit-<버전>-cp3x-...whl      # Rockchip 에서 받은 휠 (rknn-llm 저장소 release)
       python export/convert_rkllm.py --model-dir out/fc_merged --out export/model_w8a8.rkllm
  3) 보드에 model_w8a8.rkllm 을 복사해서 rkllm 서버(OpenAI 호환)로 띄움 -> scripts/board_eval.py 로 평가

주의
  - 평가·캘리브레이션·보드 서버가 모두 같은 SYSTEM_PROMPT 와 채팅 템플릿(Qwen2.5 ChatML)을 써야 한다.
    아래 SYSTEM_PROMPT 는 노트북 0장과 같은 문자열이다 (바꾸면 재학습 필요).
  - 학습 때 쓴 생성 설정과 맞추려면 보드 서버에서 top_k=1(탐욕), repeat_penalty=1.1 로 둔다.
    (평가 때 HF generate 가 generation_config 의 repetition_penalty=1.1 을 그대로 적용했음)
  - toolkit 버전마다 build() 인자 이름이 조금씩 다르다. 오류가 나면 해당 버전 문서의 인자 이름으로 바꿔야 한다.
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_PROMPT = (
    "편의점 납품기사의 말을 함수 호출 JSON 한 줄로 바꿔라. 말한 값만 그대로 쓰고 말하지 않은 값은 쓰지 마라.\n"
    "함수: next_stop(), stop_items(store?,item?), complete(store?,receiver?), "
    "report_issue(store?,item?,issue?,qty?,unit?), scan(), other()\n"
    "issue는 파손|수량부족|오배송|온도이상 중 하나, qty는 정수."
)

ap = argparse.ArgumentParser()
ap.add_argument("--model-dir", default=f"{ROOT}/out/fc_merged")
ap.add_argument("--calib-utterances", default=f"{ROOT}/data/calibration_utterances.json")
ap.add_argument("--fc-csv", default=f"{ROOT}/data/fc_dataset.csv")
ap.add_argument("--calib-out", default=f"{ROOT}/export/calibration_w8a8.json")
ap.add_argument("--out", default=f"{ROOT}/export/model_w8a8.rkllm")
ap.add_argument("--max-context", type=int, default=None, help="32의 배수. 생략하면 max(데이터 최대 토큰 길이를 32 배수로 올린 값, 256)")
ap.add_argument("--target", default="rk3588")
ap.add_argument("--npu-cores", type=int, default=3)
ap.add_argument("--device", default="cpu", help="변환 중 모델을 올릴 장치 (cpu 또는 cuda)")
ap.add_argument("--prepare-only", action="store_true")
args = ap.parse_args()

# ---------------- 1) 캘리브레이션 데이터 + max_context + eos 점검 (toolkit 불필요) ----------------
import pandas as pd
from transformers import AutoTokenizer, AutoConfig

tok = AutoTokenizer.from_pretrained(args.model_dir)


def chat(messages, gen_prompt):
    return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=gen_prompt, enable_thinking=False)


def build_prompt(text):
    return chat([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}], True)


df = pd.read_csv(args.fc_csv)
tgt = dict(zip(df.text, df.target))
utts = json.load(open(args.calib_utterances, encoding="utf-8"))
calib, missing = [], 0
for u in utts:
    if u not in tgt:
        missing += 1
        continue
    calib.append({"input": build_prompt(u), "target": tgt[u]})        # RKLLM 예제 형식: 템플릿이 적용된 프롬프트 + 정답
os.makedirs(os.path.dirname(args.calib_out), exist_ok=True)
json.dump(calib, open(args.calib_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"캘리브레이션 {len(calib)}건 저장 -> {args.calib_out}  (fc_dataset 에 없는 문장 {missing}건 제외)")

lens = [len(tok(build_prompt(t) + g + tok.eos_token, add_special_tokens=False)["input_ids"]) for t, g in zip(df.text, df.target)]
need = max(lens)
auto_ctx = ((need + 31) // 32) * 32
max_ctx = args.max_context or max(auto_ctx, 256)      # 데이터 최대 길이보다 여유를 두기 위해 최소 256
assert max_ctx % 32 == 0, "max_context 는 32의 배수여야 함"
print(f"데이터 전체의 최대 토큰 길이(프롬프트+정답+eos) = {need} -> 32의 배수로 올림 {auto_ctx}, 사용할 max_context = {max_ctx}")

cfg = AutoConfig.from_pretrained(args.model_dir)
gen_path = os.path.join(args.model_dir, "generation_config.json")
gen = json.load(open(gen_path, encoding="utf-8")) if os.path.exists(gen_path) else {}
im_end = tok.convert_tokens_to_ids("<|im_end|>")
print("eos 점검:", {"tokenizer.eos_token": tok.eos_token, "tokenizer.eos_token_id": tok.eos_token_id, "<|im_end|> id": im_end,
                    "config.eos_token_id": cfg.eos_token_id, "generation_config.eos_token_id": gen.get("eos_token_id")})
eos_set = cfg.eos_token_id if isinstance(cfg.eos_token_id, list) else [cfg.eos_token_id]
if tok.eos_token_id != im_end and im_end not in eos_set:
    print("!! 경고: 모델이 답을 끝낼 때 내는 <|im_end|> 가 eos 로 등록되어 있지 않다. 보드에서 답이 끝나지 않을 수 있음.")
else:
    print("OK: <|im_end|> 가 종료 토큰으로 인식됨 (보드 쪽 설정에서도 이 id 를 종료로 써야 함)")

if args.prepare_only:
    sys.exit(0)

# ---------------- 2) RKLLM 변환 (toolkit 필요) ----------------
try:
    from rkllm.api import RKLLM
except ImportError:
    sys.exit("rkllm-toolkit 이 없어 변환을 하지 못했습니다 (x86 Linux/WSL2/Docker 에서 toolkit 설치 후 다시 실행하세요).")

llm = RKLLM()
ret = llm.load_huggingface(model=args.model_dir, model_lora=None, device=args.device, dtype="float16", custom_config=None, load_weight=True)
if ret != 0:
    sys.exit(f"load_huggingface 실패 (ret={ret})")
ret = llm.build(do_quantization=True, optimization_level=1, quantized_dtype="w8a8", quantized_algorithm="normal",
                target_platform=args.target, num_npu_core=args.npu_cores, extra_qparams=None,
                dataset=args.calib_out, hybrid_rate=0, max_context=max_ctx)
if ret != 0:
    sys.exit(f"build 실패 (ret={ret})")
ret = llm.export_rkllm(args.out)
if ret != 0:
    sys.exit(f"export_rkllm 실패 (ret={ret})")
print("saved:", args.out, round(os.path.getsize(args.out) / 2**20), "MB")
