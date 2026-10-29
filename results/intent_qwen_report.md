# Qwen3-0.6B + LoRA 의도분류 vs klue/roberta-small

브랜치 `intent-qwen3`. 의도분류 모듈만 Qwen3-0.6B 로 새로 만들어 기존 roberta 와 같은 분할(train 1940 / val 383 / test 431)에서 비교했다.
FC 모델(`out/fc_merged`)은 다시 학습하지 않았고, 기존 산출물(`out/intent_model`, `out/fc_merged`, `export/intent_onnx`, `config/pipeline_v2_1.json`)은 건드리지 않았다.
평가 기준과 분할은 결과와 상관없이 바꾸지 않았다. 체크포인트 선택은 val 로만 했고 test 는 최종 모델 하나로 한 번 평가했다.

## 0. 한 줄 결론

**의도분류 정확도에서 Qwen3-0.6B(탐욕 출력) 는 roberta 에 못 미친다: test 정확도 0.8561 vs 0.9072 (-5.1%p).**
파이프라인 전체(FC 포함)에서는 차이가 1문장 이내로 줄지만, 이는 FC 가 의도분류 오류를 대부분 덮기 때문이고 Qwen3 쪽 이점은 아니다.
정확도 기준으로는 roberta 를 대체할 근거가 없다. 보드 지연·메모리는 측정하지 못했다(아래 7절).

## 1. 환경과 호환성

| 항목 | 값 |
|---|---|
| torch | 2.11.0+cu128 |
| transformers | 4.57.6 (요구: <5, >=4.51 충족) |
| 충돌 | 없음 |
| GPU | NVIDIA GeForce RTX 5050 (WDDM) |
| 기반 모델 | `Qwen/Qwen3-0.6B` |

## 2. 채팅 템플릿 (1단계)

`enable_thinking=False`. 추론 프롬프트와 학습 문자열이 같은 형식임을 `scripts/inspect_intent_qwen3_template.py` 로 확인했다
(학습 문자열 = 추론 프롬프트 + `정답<|im_end|>\n`, 둘 다 빈 think 블록 1개).

추론 프롬프트 (그대로):

```
'<|im_start|>system\n{INTENT_SYSTEM}<|im_end|>\n<|im_start|>user\n{발화}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
```

학습 문자열 (발화 `다음 어디야`, 정답 `next_stop`): 위와 같은 문자열 뒤에 `next_stop<|im_end|>\n`. 손실은 `next_stop<|im_end|>\n` 부분에만 건다.

- 프롬프트 앞부분 (prefix, 발화 앞까지): `<|im_start|>system\n{INTENT_SYSTEM}<|im_end|>\n<|im_start|>user\n`
- 프롬프트 뒷부분 (postfix, 발화 뒤): `<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n`
- `INTENT_SYSTEM` (`scripts/intent_qwen_common.py` 한 곳에만 정의, 학습·평가·캘리브레이션이 공유): `편의점 납품기사의 말이 어떤 기능인지 분류하라. next_stop, stop_items, complete, report_issue, scan, other 중 하나의 단어만 출력하라.`
- eos `<|im_end|>` 151645, pad `<|endoftext|>` 151643.
- 라벨 토큰화: next_stop [3600, 19039], stop_items [9495, 12134], complete [14737], report_issue [11736, 53340], scan [16405], other [1575]. **6개 라벨의 첫 토큰이 모두 달라** 첫 토큰 확률로 6-클래스 확률을 만들 수 있다.
- 프롬프트 길이: 평균 약 71 토큰.

`<think>` 군더더기 확인:
- 학습 전 기반 모델, 20문장: `report_issue<|im_end|>` 19건, `next_stop<|im_end|>` 1건. `<think>` 는 0건 (그 시점엔 거의 모든 문장을 report_issue 로 찍음 = 학습 전에는 분류를 못 함).
- 학습 후: 같은 20문장을 따로 다시 돌리지는 않았다. 대신 병합 모델로 val 383 + test 431 전체를 돌려 `<think>`·`</think>`·`<|im_start|>` 등장 0건, 출력 종류는 6개 라벨뿐이다 (`results/intent_qwen3/{val,test}_pred.csv` 의 `raw` 열).

## 3. 데이터와 학습 (2~3단계)

- 데이터: `data/intent_dataset.csv` 의 기존 split 그대로. train 1940 (템플릿 1800 + gemini 140), val 383, test 431. 템플릿 단위 분할이라 train/val/test 문장 겹침 0, 같은 템플릿이 split 에 걸쳐 나오지 않음 (`scripts/check_intent_qwen3_data.py`). 라벨은 함수별로 대체로 균형(train 약 320, val 64, test 69~75).
- LoRA: r 16, alpha 32, dropout 0.05, 대상 q/k/v/o/gate/up/down_proj, 학습 파라미터 10,092,544 (1.67%).
- lr 2e-4, 3 epoch, 배치 4 x grad accum 4 (유효 16), cosine, warmup 0.05, bf16, seed 42, `device_map={"":0}`.
- 학습 시간 **450.5 초** (366 optimizer step). step 시간 평균 1.168 s (중앙값 1.17, 최대 1.403) -> 학습 중 느려짐 없음. 스모크 테스트에서는 1.57 s/step.
- VRAM: peak allocated **2.79 GB**, peak reserved **7.98 GB** (reserved 는 캐싱 할당기가 잡아둔 양이라 실제 사용량보다 크다. 이 GPU 의 전용 메모리 한도 대비 여유 여부는 따로 확인하지 않았지만 step 시간이 안정적이라 공유 메모리 넘침 증상은 없었다고 판단).
- eval_loss: epoch1 0.351 / epoch2 0.147 / epoch3 0.171.
- 체크포인트 선택 (val 만 사용; 기준: val 탐욕 정확도 최고, 동률이면 val loss 낮은 쪽):

| epoch | val 탐욕 정확도 | val 첫토큰 argmax | val 형식 오류 | val loss |
|---|---|---|---|---|
| 1 | 0.7963 | 0.7963 | 0 | 0.351 |
| **2 (선택)** | **0.8877** | 0.8877 | 0 | 0.147 |
| 3 | 0.8668 | 0.8695 | 0 | 0.171 |

- 병합 (4단계): fp16 `out/intent_qwen3_merged` (1152 MB). 어댑터와 병합 모델의 val 출력 일치율 1.0, 병합 후 val 정확도 0.8877, 첫 토큰 확률 최대 차이 0.019 (fp16 반올림). `config.json` 의 eos 151645, `generation_config.json` 의 eos [151645, 151643]. 다만 generation_config 에 do_sample true / temperature 0.6 이 들어 있으므로 사용 시 탐욕(`do_sample=False`)을 명시해야 한다.

## 4. test 431 비교 (5단계, 같은 분할)

| 모델 / 방식 | 정확도 | macro-F1 | 형식 오류 |
|---|---|---|---|
| roberta-small (v2) | **0.9072** | 0.9051 | - |
| Qwen3-0.6B 탐욕 생성 (argmax 전용, RKLLM 에서도 가능) | 0.8561 | 0.8625 | 0 / 431 (0.0%) |
| Qwen3-0.6B 첫 토큰 확률 argmax (PC 전용) | 0.8538 | 0.8604 | - |

val 형식 오류도 0 / 383. 탐욕 출력과 첫 토큰 argmax 가 같은 비율은 0.993.

클래스별 (precision / recall / F1):

| 기능 (n) | roberta | Qwen3 탐욕 |
|---|---|---|
| next_stop (74) | 0.755 / 1.000 / 0.860 | 0.983 / 0.784 / 0.872 |
| stop_items (75) | 0.909 / 0.933 / 0.921 | 0.619 / 0.867 / 0.722 |
| complete (70) | 1.000 / 0.957 / 0.978 | 0.882 / 0.957 / 0.918 |
| report_issue (69) | 0.918 / 0.971 / 0.944 | 0.857 / 0.870 / 0.863 |
| scan (73) | 0.958 / 0.932 / 0.944 | 0.985 / 0.890 / 0.935 |
| other (70) | 1.000 / 0.643 / 0.783 | 0.982 / 0.771 / 0.864 |

혼동행렬 (행 = 정답, 열 = 예측; 순서 next_stop, stop_items, complete, report_issue, scan, other):

roberta
```
next_stop     74  0  0  0  0  0
stop_items     0 70  0  5  0  0
complete       0  0 67  0  3  0
report_issue   0  2  0 67  0  0
scan           0  5  0  0 68  0
other         24  0  0  1  0 45
```
Qwen3 탐욕
```
next_stop     58 16  0  0  0  0
stop_items     0 65  0  8  1  1
complete       0  3 67  0  0  0
report_issue   0  9  0 60  0  0
scan           0  8  0  0 65  0
other          1  4  9  2  0 54
```

- 오류 양상이 다르다: roberta 는 other 를 next_stop 으로 보는 오류 24건이 대부분이고, Qwen3 는 stop_items 로 쏠리는 오류(next_stop 16, report_issue 9, scan 8 등)가 많다.
- 같은 문장 짝 비교: 둘 다 맞음 344, roberta 만 맞음 47, Qwen3 만 맞음 25, 둘 다 틀림 15. (47 대 25 에 대해 연속성 보정 McNemar 를 손으로 계산하면 chi2 약 6.1, p 약 0.013. 별도 통계 도구로 검증하지는 않았다.)
- 조각별 정확도 (test):

| 조각 (n) | roberta | Qwen3 |
|---|---|---|
| 출처 gemini (71) | 0.958 | 0.930 |
| 출처 template (360) | 0.897 | 0.842 |
| 모호성 clear (361) | 0.917 | 0.906 |
| 모호성 ask (16) | 1.000 | 1.000 |
| 모호성 hard (54) | 0.815 | **0.481** |

격차 대부분이 hard(헷갈리는 문장) 조각에서 나온다. clear 에서는 차이가 1.1%p 에 그친다.

## 5. 확률과 되묻기 (5단계, 두 경우를 나눠서 보고)

**(A) argmax 만 (RKLLM 이 로짓을 주지 않을 수도 있어 보드에서 안전하게 쓸 수 있는 경우)**: 생성한 단어만 쓴다. 신뢰도·margin 이 없어 **되묻기 불가**, "신뢰도 조건부 LLM 생략"도 못 쓴다.

**(B) 확률 사용 (PC 전용)**: 첫 생성 위치 로짓에서 6개 라벨의 첫 토큰만 소프트맥스. 6개 첫 토큰이 전체 어휘 확률에서 차지하는 비율은 평균 0.9986 (최소 0.921) 이라 6-클래스 확률로 쓸 만하다.
다만 **과신이 심하다**: 오답 63건 중 48건이 최대 확률 0.9 이상이다(오답 최대확률 중앙값 0.981). margin 이 기준 0.05 미만으로 되묻는 비율은 test 0.7%, val 0.3% 로, 되묻기가 거의 작동하지 않는다. 그래서 확률이 있어도 오류 걸러내기에 크게 도움이 되지 않았다.

RKLLM 이 로짓/확률을 노출하는지는 **확인하지 못했다** (미확인). 노출되지 않으면 (A) 만 가능하다.

## 6. 파이프라인 교체 평가 (의도분류 모듈만 교체, FC 동일; test 431)

선정 방식은 v2.1 과 같다 (val 로만 격자 선택, test 1회).

| 설정 | tau / 건너뛰기 | 의도 정확도 | pipeline_incl_ask | 오실행률 | 되묻기율 | LLM 생략률 |
|---|---|---|---|---|---|---|
| roberta v2.1 (기준) | 0.05 / 0.9 / scan,other | 0.9072 | 0.8515 | 0.1485 | 0.0046 | 0.2413 |
| Qwen3 확률, v2.1 값 그대로 | 0.05 / 0.9 / scan,other | 0.8538 | 0.8492 | 0.1439 | 0.0070 | 0.2483 |
| Qwen3 확률, val 선택 | 0.5 / 0.95 / scan,other | 0.8538 | 0.8306 | 0.1415 | 0.0348 | 0.2459 |
| Qwen3 argmax 만 | - / 0.9(one-hot) / scan,other | 0.8561 | 0.8538 | 0.1462 | 0 | 0.2807 |

- `fc_final_ok` 는 네 경우 모두 0.8469 로 같다 (FC 출력은 같고 의도분류는 건너뛰기와 되묻기 판단에만 영향을 줌). 그래서 파이프라인 수치 차이는 1~10문장 수준이다.
- Qwen3 확률의 val 선택값은 tau 격자의 상한(0.5)이 선택돼 격자 가장자리이다. val 의 pipeline_incl_ask 는 Qwen3 확률 0.9034 / argmax 0.893 / roberta 0.9687 이었다.
- 위 표에서 "Qwen3 argmax 만" 이 roberta 와 비슷하게 보이는 것은 되묻기 0 이고 LLM 을 더 많이(28%) 건너뛰어서이지, 의도분류 정확도가 좋아서가 아니다. 한 번의 test 431 에서 0.3%p(1문장) 차이는 유의하다고 말할 수 없다.
- 건너뛰기를 했을 때 틀리는 문장의 위험(의도분류가 틀렸는데 FC 를 생략)은 정확도가 낮을수록 커지므로 argmax 전용에서는 오실행 위험이 roberta 보다 낮다고 단정할 수 없다. 이 부분은 별도로 분석하지 않았다.
- val 분할에서 Qwen3 파이프라인이 roberta 보다 크게 낮은 것(0.89~0.90 vs 0.9687)은 val 의 roberta 점수가 이미 높게 나오는 경향(이전 세션에서 확인한 val/test 비대칭)과도 겹친다. 원인 분석은 하지 않았다.

## 7. 지연·메모리 (PC 실측 / 보드 추정)

| 환경 | 방식 | 평균 지연 | 비고 |
|---|---|---|---|
| PC GPU (RTX 5050, bf16, 배치 1, n=100) | 전체 생성 | 137.6 ms (중앙 116.0, p95 168.6) | 프롬프트 평균 70.9 토큰, 생성 2.46 토큰(eos 포함) |
| PC GPU | 첫 토큰만 | 58.4 ms | 확률용 |
| PC CPU (4 스레드, fp32, n=40) | 전체 생성 | 626.6 ms (p95 710.6) | 첫 토큰만 581.6 ms |
| **보드 RK3588 w8a8** | 전체 생성 | **약 250~280 ms (추정, 미측정)** | 강의 벤치마크 TTFT 214 ms + 약 1.5 토큰 / 32.2 tok/s. 벤치마크의 프롬프트 길이를 모르므로 TTFT 가 우리 프롬프트(약 71 토큰)와 같다고 가정한 값 |
| 보드 메모리 | | 약 774 MB (벤치마크 값, 추정) | roberta ONNX 와의 비교는 이번에 다시 재지 않음 |

## 8. 대체 가능성 판단

- **정확도**: 의도분류 단독으로 roberta 보다 낮다 (0.8561 vs 0.9072, 짝 비교 47 대 25). 특히 헷갈리는 문장(hard) 정확도가 0.481 vs 0.815.
- **파이프라인**: FC 가 의도분류 오류를 흡수해 argmax 전용에서도 pipeline_incl_ask 0.8538 vs 0.8515 로 비슷하다. 그러나 이것이 Qwen3 의도분류가 충분하다는 증거는 아니다 (위 6절).
- **기능 손실**: 보드에서 확률을 못 쓰면 되묻기가 사라진다. 확률을 써도 과신 때문에 되묻기가 거의 안 걸린다.
- **비용**: 보드에서 모델 두 개(Qwen2.5-1.5B FC + Qwen3-0.6B 의도분류)를 메모리에 올려야 하며, 지연은 roberta(ONNX)보다 클 것으로 추정된다(측정 안 함).
- 결론: **현재 결과로는 roberta 를 Qwen3-0.6B 로 대체할 근거가 부족하다.** 형식 오류가 0 이고 `<think>` 문제가 없다는 점(= RKLLM 으로 옮길 때 형식 안정성은 괜찮을 가능성)은 긍정적이지만, 보드 변환·양자화 후 정확도는 확인하지 못했다.

## 9. 정확도가 낮은 원인 후보 (검증하지 않음)

1. **보지 못한 템플릿**: 분할이 템플릿 단위라 test 에 train 에 없는 템플릿이 있다. 0.6B 생성 모델이 새 말투에 덜 일반화하는 것으로 보인다 (template 출처 0.842 vs gemini 출처 0.930, hard 0.481).
2. **모델 크기와 데이터 양**: 0.6B, train 1940문장, 3 epoch. 데이터를 늘리거나 epoch 와 lr 을 조정하면 달라질 수 있으나 이번엔 하지 않았다 (val 에서 epoch 2 가 3 보다 좋아 과적합 징후는 있음: epoch 3 에서 val loss 상승).
3. **라벨 표현**: 영어 스네이크케이스 단어를 2토큰으로 생성하는 방식. 첫 토큰이 모두 달라 충돌은 없으므로 주된 원인은 아닌 것으로 보인다. 그러나 stop_items 로 쏠리는 오류가 많아(다른 5개 기능 -> stop_items 총 40건) 라벨 토큰 편향 가능성은 완전히 배제하지 못했다.
4. **형식 오류**: 0건이라 원인 아님.
5. **생각 모드 형식**: 학습과 추론이 같은 빈 think 블록을 쓰고 군더더기도 없어 원인 아님. 단, 보드에서 이 블록이 빠지면 새로운 문제가 될 수 있다 (docs/rkllm_intent_qwen3.md).

## 10. 하지 않은 것과 추정인 것

- **RKLLM 변환 미실행**: docker 가 없고 rkllm-toolkit(x86 Linux)도 없다. 설정과 명령은 `docs/rkllm_intent_qwen3.md` 에 정리했다.
- **보드 측정 없음**: 보드 정확도, 지연, 메모리는 모두 미측정이다. 지연·메모리의 보드 값은 강의 벤치마크에서 계산한 추정이다.
- **RKLLM 로짓 노출 여부**: 미확인.
- **캘리브레이션 템플릿 적용 방식**: toolkit 이 `input` 에 템플릿을 한 번 더 씌우는지 미확인.
- **학습 후 20문장 재출력**: 학습 전과 같은 20문장을 학습 후에 따로 뽑지 않았다 (전체 val/test 로 대체; 2절).
- 학습 전 기반 모델과 학습 후 토크나이저가 동일한지 직접 비교하는 검사는 완료하지 못했다 (병합 폴더의 토크나이저로 평가한 결과가 어댑터와 일치해서 실질적 문제는 없다고 판단).
- 하이퍼파라미터 탐색, 추가 데이터 증강, 다른 라벨 표현, 다른 모델 크기는 시도하지 않았다.

## 11. 산출물

| 파일 | 내용 |
|---|---|
| `scripts/intent_qwen_common.py` | 공용 상수·프롬프트·학습/추론 함수 |
| `scripts/inspect_intent_qwen3_template.py`, `check_intent_qwen3_data.py` | 1~2단계 확인 |
| `scripts/train_intent_qwen3.py`, `select_intent_qwen3_ckpt.py`, `merge_intent_qwen3.py` | 3~4단계 |
| `scripts/eval_intent_qwen3.py`, `bench_intent_qwen3.py`, `select_pipeline_v2_2.py` | 5단계 |
| `scripts/make_calib_intent_qwen3.py`, `data/calib_intent_qwen3.json` | 6단계 캘리브레이션 480건 |
| `docs/rkllm_intent_qwen3.md` | RKLLM 변환 초안 |
| `config/pipeline_v2_2_qwen3_intent.json` | 교체 후보 설정 (v2.1 은 그대로) |
| `results/intent_qwen3/` | 예측 CSV, 평가·지연·병합·파이프라인 JSON/CSV |
| `logs/train_intent_qwen3_full.log`, `logs/select_pipeline_v2_2.log` | 실행 로그 |

모델 폴더(`out/intent_qwen3_*`)는 git 에 넣지 않았다.
