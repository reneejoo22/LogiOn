# Qwen3-0.6B 의도분류 -> RKLLM 변환 초안 (미실행)

상태: **변환을 실행하지 않았다.** 이 PC(Windows)에는 docker 가 없고 rkllm-toolkit(x86 Linux 전용)도 설치되어 있지 않다.
WSL 실행 파일은 있지만 toolkit 설치와 변환은 시도하지 않았다. 아래는 다른 x86 Linux 환경에서 그대로 따라 할 수 있게 정리한 설정과 명령이다.
`.rkllm` 파일 크기, 보드 지연, 보드 정확도는 모두 **미측정**이다.

## 1. 입력물

| 항목 | 경로 | 비고 |
|---|---|---|
| 병합 모델 (fp16) | `out/intent_qwen3_merged` | git 제외. 1152 MB. `eos_token_id` 151645 (config.json), generation_config 는 [151645, 151643] |
| 캘리브레이션 | `data/calib_intent_qwen3.json` | 480건, 함수별 80, train/val/test 와 문장 겹침 0 |

캘리브레이션 항목은 `{"input", "target", "text", "label", "ambiguity"}`. RKLLM 이 읽는 것은 `input`, `target` 이고 나머지는 참고용이다.
`input` 은 1단계에서 확인한 추론 프롬프트 전체(채팅 템플릿 적용 후), `target` 은 병합 모델의 탐욕 출력 + `<|im_end|>` 이다.
말투 구성: 정중체 어미 20%, 군더더기 앞말 78%, 명확/되묻기/헷갈림 = 376/32/72. 프롬프트 최대 85 토큰.

**미확인:** toolkit 이 `input` 에 채팅 템플릿을 한 번 더 씌우는지는 확인하지 못했다. 기존 FC 쪽 `export/calibration_w8a8.json` 도 템플릿이 적용된 문자열을 넣는 방식이라 같은 방식을 따랐다.
변환 환경에서 toolkit 버전의 예제(`generate_data_quant.py`)와 비교해 이중 적용이 아닌지 확인할 것.

## 2. 변환 설정 초안

| 인자 | 값 | 이유 |
|---|---|---|
| quantized_dtype | `w8a8` | 강의의 RK3588 벤치마크 Qwen3-0.6B w8a8 기준 (TTFT 214 ms, 32.2 tok/s, 메모리 774 MB) |
| quantized_algorithm | `normal` | 기존 FC 변환 스크립트와 같음 |
| target_platform | `rk3588` | |
| num_npu_core | 3 | |
| max_context | 256 | 32의 배수. 프롬프트 최대 85 토큰 + 출력 3~4 토큰이라 충분 |
| dataset | `data/calib_intent_qwen3.json` | |
| optimization_level | 1 | 기존 스크립트와 같음 |
| hybrid_rate | 0 | |
| calib 종료 토큰 | `<|im_end|>` | toolkit 버전에 `calib_stop_at` 류의 인자가 있으면 이 값을 준다. 인자 이름은 버전마다 다르다 (미확인) |

명령 (x86 Linux, rkllm-toolkit 설치 후). 기존 `export/convert_rkllm.py` 의 2단계와 같은 호출이고, 모델 경로와 캘리브레이션 파일만 바꾼다.

```python
from rkllm.api import RKLLM
llm = RKLLM()
assert llm.load_huggingface(model="out/intent_qwen3_merged", model_lora=None, device="cpu", dtype="float16",
                            custom_config=None, load_weight=True) == 0
assert llm.build(do_quantization=True, optimization_level=1, quantized_dtype="w8a8", quantized_algorithm="normal",
                 target_platform="rk3588", num_npu_core=3, extra_qparams=None,
                 dataset="data/calib_intent_qwen3.json", hybrid_rate=0, max_context=256) == 0
assert llm.export_rkllm("export/intent_qwen3_w8a8.rkllm") == 0
```

`export/intent_qwen3_w8a8.rkllm` 은 커밋하지 않는다(.rkllm 은 모델 파일).

## 3. 보드의 채팅 템플릿 (학습·평가와 반드시 같아야 함)

학습과 PC 평가는 `enable_thinking=False` 로 만든 아래 문자열을 썼다. 보드 쪽 `rkllm_set_chat_template` 의 system / prefix / postfix 도 이와 같아야 한다.

- system 지시문 (`scripts/intent_qwen_common.py` 의 `INTENT_SYSTEM`):
  `편의점 납품기사의 말이 어떤 기능인지 분류하라. next_stop, stop_items, complete, report_issue, scan, other 중 하나의 단어만 출력하라.`
- 사용자 발화 앞 (prefix): `<|im_start|>user\n`
- 사용자 발화 뒤 (postfix): `<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n`
- system 부분: `<|im_start|>system\n{INTENT_SYSTEM}<|im_end|>\n`

보드가 만드는 전체 프롬프트는 다음과 같아야 한다.

```
<|im_start|>system\n{INTENT_SYSTEM}<|im_end|>\n<|im_start|>user\n{발화}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n
```

주의할 점
1. **빈 think 블록(`<think>\n\n</think>\n\n`)을 postfix 에 반드시 넣는다.** 모델은 이 블록이 있는 상태로 학습됐다. 빠지면 학습 때 보지 못한 형식이 된다. 그 영향은 측정하지 않았다.
2. RKLLM 의 기본 Qwen3 템플릿이 think 블록을 넣는지는 확인하지 못했다. 기본 템플릿을 쓰지 말고 위 문자열을 직접 지정하는 쪽이 안전하다.
3. 디코딩은 탐욕으로 둔다 (top_k=1, 반복 억제 없음). 병합 모델의 generation_config 는 do_sample true / temperature 0.6 이 들어 있어서, 보드 설정이 이를 따르면 결과가 흔들릴 수 있다. PC 평가는 모두 `do_sample=False` 였다.
4. 최대 생성 토큰은 8이면 충분하다. 정답 단어는 1~2 토큰이고 뒤에 `<|im_end|>` 한 토큰이 붙는다 (PC 측정 평균 2.46 토큰).
5. 출력은 `<|im_end|>` 앞까지 자르고 공백을 지운 뒤 6개 라벨 중 하나인지 확인한다. 아니면 `다시 말씀해 주세요`. (PC 평가에서 형식 오류는 val 383, test 431 모두 0건이었다.)

## 4. 변환 후 확인할 것 (모두 미실행)

1. 보드에서 val 383문장을 돌려 PC 결과(탐욕 정확도 val 0.8877)와 일치율을 본다. w8a8 양자화로 달라질 수 있다.
2. 보드에서 형식 오류율, `<think>` 같은 군더더기 출력 여부.
3. 보드 지연: TTFT 와 전체 응답 시간(프롬프트 약 71 토큰 + 출력 약 2.5 토큰).
4. RKLLM 런타임이 로짓 또는 토큰별 확률을 주는지. 주지 않으면 확률/되묻기(margin) 기능은 쓸 수 없고 `argmax 전용` 설정만 쓴다 (`config/pipeline_v2_2_qwen3_intent.json` 참고).
