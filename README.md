# LogiOn

**음성만으로 납품 업무를 처리하는 온디바이스 AI 어시스턴트 (Orange Pi 5+, 편의점 납품기사용)**

편의점에 물건을 내리는 기사가 운전 중이거나 양손에 짐을 든 상태에서, 말 한마디로 다음 배송지 확인·납품 목록 조회·완료 처리·이상 보고·스캔을 할 수 있게 하는 시스템입니다. 인터넷 연결 없이 Orange Pi 5+ (RK3588) 보드 위에서 모든 추론이 돌아갑니다.

이 저장소는 그중 **AI 파트**(데이터 설계 → 의도분류 학습 → function calling 학습 → 평가 → 파이프라인)를 담고 있습니다.

---

## 전체 구조

```
🎤 음성
  │
  ├─▶ ① STT (SenseVoice-Small int8, sherpa-onnx)          "우유 두 개 터졌어"
  │
  ├─▶ ② 의도분류 (klue/roberta-small)                      report_issue (0.94)
  │        └─ next_stop / scan / other 이고 확신 0.9 이상이면 ③~④ 건너뛰고 바로 ⑤ (빠른 길)
  │
  ├─▶ ③ LLM function calling (Qwen2.5-1.5B-Instruct + LoRA)
  │        {"fn":"report_issue","item":"우유","issue":"파손","qty":2,"unit":"개"}
  │
  ├─▶ ④ 값 보정 (규칙 코드, 모델 아님)
  │        DB 이름 맞추기 · 발음 유사도 비교 · 모호하면 되묻기
  │        "우유" → 서울우유 / 바나나우유 / 딸기우유 → 되묻기
  │
  ├─▶ ⑤ 실행 (배송 DB 조회·기록)
  │
  ├─▶ ⑥ 응답 문장 생성 (템플릿)                            "역삼점 서울우유 2개 파손으로 기록했어요."
  │
  └─▶ ⑦ TTS (한국어 VITS) 🔊
```

**핵심 설계**: LLM은 "말한 값을 JSON으로 옮기는 일"만 하고, DB 이름 맞추기·되묻기 판단은 규칙 코드(④)가 맡습니다. 모델이 없는 값을 지어내지 않게 하고, 보드에서 LLM 호출 횟수를 줄이기 위해서입니다.

---

## 지원 기능 6개

| 함수 | 언제 | 값(슬롯) | 예시 발화 | 출력 JSON |
| --- | --- | --- | --- | --- |
| `next_stop` | 다음/남은 배송지를 물을 때 | 없음 | "다음 어디야" | `{"fn":"next_stop"}` |
| `stop_items` | 내릴 품목·수량을 물을 때 | `store?`, `item?` | "서초점 콜라 몇 박스야" | `{"fn":"stop_items","store":"서초점","item":"콜라"}` |
| `complete` | 납품을 마쳤다고 알릴 때 | `store?`, `receiver?` | "점장님한테 넘겼어" | `{"fn":"complete","receiver":"점장님"}` |
| `report_issue` | 물건에 문제가 있을 때 | `store?`, `item?`, `issue?`, `qty?`, `unit?` | "우유 두 개 터졌어" | `{"fn":"report_issue","item":"우유","issue":"파손","qty":2,"unit":"개"}` |
| `scan` | 바코드/송장 스캔을 켤 때 | 없음 | "바코드 찍을게" | `{"fn":"scan"}` |
| `other` | 그 외 모든 말 (잡담 등) | 없음 | "노래 틀어줘" | `{"fn":"other"}` |

`issue`는 `파손 | 수량부족 | 오배송 | 온도이상` 중 하나, `qty`는 정수, `unit`은 `개 | 박스 | 판 | 봉지`입니다.
말하지 않은 값은 키 자체를 쓰지 않습니다. 필수 값이 빠지면 ④에서 되묻습니다.

---

## 데이터 설계

**통합 데이터셋 1개에서 두 학습용 파일을 파생**합니다. 원본은 `(발화, 정답 JSON)` 한 쌍이고,

- 의도분류용 `data/intent_dataset.csv` — 정답 JSON의 `fn`만 라벨로 사용
- function calling용 `data/fc_dataset.csv` — JSON 전체를 생성 타깃으로 사용

두 파일의 `train/val/test` 분할은 완전히 동일합니다. 그래서 같은 test 문장에 대해 두 모듈의 판단을 직접 비교할 수 있습니다.

**틀(템플릿) 단위 분할**: 함수마다 말 틀 32개를 만들고, *틀 자체*를 train/val/test로 나눕니다. test 문장은 학습에서 한 번도 본 적 없는 틀에서 나오므로, "문장 모양이 조금만 바뀌어도 틀리는지"를 test 점수로 바로 확인할 수 있습니다.

**ambiguity 라벨**: 각 문장을 값 보정 규칙(④)에 통과시켜 자동 분류합니다.
- `clear` — 값이 바로 확정됨
- `ask` — 되물어야 함 (예: "우유"는 서울우유/바나나우유/딸기우유에 걸림)
- `hard` — 다른 기능이나 잡담과 헷갈리기 쉬운 표현 (틀 앞에 `!` 표시)

**제미나이 데이터 혼합**: 템플릿만 쓰면 문장 모양이 한정되므로, `data/gemini_prompt.txt`를 제미나이에 넣어 받은 자유 생성 문장을 섞습니다. 검증(JSON 형식·함수명·issue 값·qty 정수·정답 값이 실제 문장에 있는지)을 통과한 것만 사용하고, 그중 30%를 test에 넣어 "우리 템플릿이 아닌 문장"에 대한 일반화를 따로 측정합니다.

### 실제 생성된 데이터

총 **2,754건** (템플릿 2,520 + 제미나이 234, 제미나이 원본 236줄 중 2줄 검증 탈락)

| fn | train | val | test | 합계 |
| --- | ---: | ---: | ---: | ---: |
| complete | 325 | 64 | 70 | 459 |
| next_stop | 321 | 63 | 74 | 458 |
| other | 327 | 63 | 70 | 460 |
| report_issue | 325 | 64 | 69 | 458 |
| scan | 323 | 64 | 73 | 460 |
| stop_items | 319 | 65 | 75 | 459 |
| **합계** | **1,940** | **383** | **431** | **2,754** |

ambiguity 분포 (분할별 비율)

| ambiguity | train | val | test |
| --- | ---: | ---: | ---: |
| clear | 0.79 | 0.79 | 0.84 |
| ask | 0.07 | 0.07 | 0.04 |
| hard | 0.14 | 0.14 | 0.13 |

RKLLM 양자화 캘리브레이션용 발화 450건은 `data/calibration_utterances.json`에 있습니다 (train에서 함수별 75건 균등 추출).

---

## 사용 모델

| 단계 | 모델 | 이유 |
| --- | --- | --- |
| STT | **SenseVoice-Small int8** (sherpa-onnx) | 비자동회귀라 보드 CPU에서 빠름, 한국어 지원, `use_itn`으로 "두 개"→"2개" 변환 |
| 의도분류 | **klue/roberta-small** (약 6,800만 파라미터) | 한국어 사전학습, 문장당 수 ms, 값이 필요 없는 명령은 이 모델만으로 처리 |
| function calling | **Qwen2.5-1.5B-Instruct + LoRA** (r=16, α=32) | RKLLM 지원 목록에 있고 텍스트 전용이라 NPU 변환이 단순 |
| TTS | **한국어 VITS** | 보드 CPU에서 실시간 합성 |

LoRA는 `q/k/v/o/gate/up/down_proj`에 적용했고 학습 가능 파라미터는 18,464,768개 (전체의 1.18%)입니다. 학습 후 원본에 병합해 fp16으로 저장하며, 이 폴더가 RKLLM 변환(W8A8)의 입력이 됩니다.

---

## 실행 방법

### 1. 환경 설치

**torch는 반드시 CUDA 빌드로 따로 설치해야 합니다.** pip 기본 저장소의 torch는 CPU 전용이라 `torch.cuda.is_available()`가 `False`가 됩니다. RTX 50 시리즈(Blackwell, sm_120)는 **cu128 이상** 빌드가 필요합니다.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS: source .venv/bin/activate)

pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

설치 후 확인:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# True NVIDIA GeForce RTX 5050
```

> **transformers 5.x는 쓰지 마세요.** `TrainingArguments`에서 `warmup_ratio`가 제거되어 학습 셀이 바로 실패합니다. `requirements.txt`에 `<5`로 막아두었습니다.

### 2. 노트북 실행

```bash
jupyter notebook notebooks/LogiOn_AI_pipeline.ipynb
```

순서대로 실행하면 됩니다.

| 섹션 | 내용 | 산출물 |
| --- | --- | --- |
| 1 | 데이터 생성 (템플릿 + 제미나이 병합) | `data/*.csv`, `data/calibration_utterances.json` |
| 2 | 의도분류 학습 | `out/intent_model/` |
| 3 | function calling LoRA 학습 → 병합 | `out/fc_lora/`, `out/fc_merged/` |
| 4 | test 평가 | `out/test_summary.json`, `out/test_pred_*.csv` |
| 5 | 완성 파이프라인 데모 | (화면 출력) |
| 6 | (선택) STT 붙이기 | SenseVoice 모델·`test.wav` 필요 |

- 섹션 5 마지막 셀은 `RUN_INTERACTIVE = True`로 바꾸면 직접 문장을 입력해 볼 수 있습니다 (기본값 `False`: 일괄 실행 시 멈추지 않게).
- 섹션 6은 SenseVoice 모델 폴더나 `test.wav`가 없으면 자동으로 건너뜁니다.
- 이미 학습을 마쳤다면 섹션 2 첫 셀의 `SKIP_TRAIN = True`로 저장본을 불러와 4~5단계만 실행할 수 있습니다.

### GPU 요구사항 (중요)

**VRAM 8GB 환경에서는 배치 크기를 반드시 낮춰야 합니다.** Windows(WDDM)는 VRAM이 부족해도 OOM을 내지 않고 시스템 RAM으로 조용히 넘기기 때문에, 오류 없이 30배 느려집니다. RTX 5050(8GB)에서 실측한 값입니다.

| `per_device_train_batch_size` | 학습 속도 | 피크 VRAM | 결과 |
| ---: | --- | --- | --- |
| 4 | **0.74 초/step** | 7.2 GiB | 정상 |
| 8 | 22.2 초/step | 11.4 GiB (초과) | 시스템 RAM 스필 |
| 16 | 약 39 초/step | 초과 | 1 epoch에 80분 |

현재 노트북은 `batch_size=4`, `gradient_accumulation_steps=4` (유효 배치 16)로 설정되어 있습니다. VRAM이 16GB 이상이면 배치를 키우고 누적을 1로 줄여도 됩니다.

모델 로딩에 `device_map="auto"` 대신 `device_map={"": 0}`를 씁니다. `auto`는 여유 VRAM을 보수적으로 잡아 일부 레이어를 CPU로 내려버리고, 그러면 학습이 수십 배 느려집니다.

---

## 실제 실행한 test 결과

RTX 5050 (8GB) / torch 2.11.0+cu128 / transformers 4.57.6 환경에서 실제로 돌린 결과입니다. test 431건 (학습에 쓰지 않은 틀 + 제미나이 데이터 30%).

### 의도분류 (klue/roberta-small)

학습 시간 **32초** (5 epoch, batch 32), 추론 **1.9 ms/문장**

| 지표 | 값 |
| --- | ---: |
| 정확도 | **0.893** |
| macro F1 | **0.894** |

함수별 리포트

| fn | precision | recall | f1 | support |
| --- | ---: | ---: | ---: | ---: |
| complete | 1.000 | 0.886 | 0.939 | 70 |
| next_stop | 0.974 | 1.000 | 0.987 | 74 |
| other | 1.000 | 0.714 | 0.833 | 70 |
| report_issue | 0.861 | 0.986 | 0.919 | 69 |
| scan | 0.903 | 0.890 | 0.897 | 73 |
| stop_items | 0.717 | 0.880 | 0.790 | 75 |

혼동표 (행=정답, 열=예측)

| 정답 \ 예측 | complete | next_stop | other | report_issue | scan | stop_items |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| complete | **62** | 0 | 0 | 1 | 7 | 0 |
| next_stop | 0 | **74** | 0 | 0 | 0 | 0 |
| other | 0 | 2 | **50** | 1 | 0 | 17 |
| report_issue | 0 | 0 | 0 | **68** | 0 | 1 |
| scan | 0 | 0 | 0 | 0 | **65** | 8 |
| stop_items | 0 | 0 | 0 | 9 | 0 | **66** |

source·ambiguity별 정확도

| source | ambiguity | 정확도 | 건수 |
| --- | --- | ---: | ---: |
| gemini | ask | 1.000 | 4 |
| gemini | clear | 0.925 | 67 |
| template | ask | 0.917 | 12 |
| template | clear | 0.918 | 294 |
| template | hard | **0.704** | 54 |

### function calling (Qwen2.5-1.5B-Instruct + LoRA)

학습 시간 **1,374초 (약 23분)** (3 epoch, batch 4 × 누적 4, lr 2e-4), 최종 eval_loss 0.039
생성 **115초 / 431건 = 266 ms/문장** (서버 GPU 배치 기준, 탐욕적 디코딩)

| 지표 | 값 |
| --- | ---: |
| JSON 유효율 | **1.000** |
| fn 정확도 | **0.910** |
| 완전 일치율 | **0.863** |
| 값(slot) F1 | **0.935** |
| 최종 동작 일치율 | **0.868** |

> 최종 동작 일치율 = 값 보정(④)까지 거친 실행 내용(되묻기 여부 포함)이 정답과 같은 비율. 실사용에 가장 가까운 지표입니다.

source·ambiguity별

| source | ambiguity | fn 정확도 | 완전 일치 | 최종 동작 일치 |
| --- | --- | ---: | ---: | ---: |
| gemini | ask | 1.000 | 1.000 | 1.000 |
| gemini | clear | 0.970 | 0.896 | 0.896 |
| template | ask | 1.000 | 0.833 | 1.000 |
| template | clear | 0.905 | 0.861 | 0.861 |
| template | hard | 0.833 | 0.833 | 0.833 |

제미나이 데이터(`clear` 0.970)가 템플릿 데이터(`clear` 0.905)보다 오히려 높습니다. 템플릿에 과적합되지 않았다는 뜻입니다.

함수별

| fn | fn 정확도 | 완전 일치 | 최종 동작 일치 |
| --- | ---: | ---: | ---: |
| complete | 1.000 | 0.986 | 0.986 |
| scan | 1.000 | 1.000 | 1.000 |
| other | 0.986 | 0.986 | 0.986 |
| report_issue | 0.870 | **0.623** | 0.652 |
| stop_items | 0.840 | 0.813 | 0.813 |
| next_stop | **0.770** | 0.770 | 0.770 |

의도분류와 LLM의 `fn` 판단이 일치한 비율: **0.807**

### 틀린 예시와 원인 분석

틀린 57건을 함수별로 보면 `report_issue` 24건, `next_stop` 17건, `stop_items` 14건, `other`·`complete` 각 1건입니다.

| # | 발화 | 정답 | 예측 | 원인 |
| ---: | --- | --- | --- | --- |
| 1 | 저기 참치삼각김밥 박스 하나 수량이 안 맞아 | `issue:수량부족` (qty 없음) | `+qty:1, unit:박스` | **정답 라벨 쪽 문제.** "박스 하나"는 사람이 보면 수량 1박스인데, 템플릿이 `{qty}` 자리에서 생성한 게 아니라 틀 안에 박힌 문구라 정답에 qty가 없음. 모델이 더 맞게 뽑았는데 오답 처리됨 |
| 2 | 바나나우유 박스 하나 새고 있어 빨리 | `issue:파손` | `+qty:1, unit:박스` | 위와 같은 원인 (틀 `"{item} 박스 하나 {issue}"`) |
| 8 | 바나나우유 박스 하나 엉뚱한 게 실렸어 | `issue:오배송` | `+qty:1, unit:박스` | 위와 같은 원인 |
| 10 | 요구르트 박스 하나 온도가 높아 | `issue:온도이상` | `+qty:1, unit:박스` | 위와 같은 원인 |
| 3 | 서초점 라면 한 박스 모자라요 | `unit:"박스"` | `unit:"박"` | 단위 토큰을 끝까지 생성하지 못함. `unit` 후보를 제한된 집합으로 강제(constrained decoding)하거나 보정 규칙에서 교정 가능 |
| 7 | 신림점 치킨마요 하나 모자람 | `qty:1, unit:개` | qty·unit 누락 | "하나"처럼 단위 없는 순우리말 수사를 수량으로 못 집어냄. 학습 데이터에 "하나/둘" 단독 표현이 부족 |
| 4 | 자 몇 개 남았지 | `next_stop` | `stop_items` | **의미가 진짜 모호함.** "몇 개"가 남은 배송지 수인지 남은 물건 수인지 문장만으로는 구분 불가. 같은 유형이 test에 반복 등장해 `next_stop` 점수를 깎음 (17건 중 다수) |
| 6 | 몇 개 남았지 | `next_stop` | `stop_items` | 위와 같음 |
| 11 | 이제 여기 내릴 거 읽어줘 | `stop_items` | `scan` | "읽어줘"가 바코드 읽기로 해석됨. `scan` 틀에 "바코드 읽을게"가 있어 동사가 겹침 |
| 12 | 여기 내릴 거 읽어줘 | `stop_items` | `scan` | 위와 같음 |
| 5 | 바나나우유 상태 좀 봐야겠다 좀 | `report_issue` (issue 없음) | `stop_items` | hard 라벨. "상태를 본다"가 조회인지 이상 보고인지 애매 |
| 9 | 아 박스 진짜 무게 나가네 | `other` | `report_issue` (수량부족) | 제미나이 생성 문장. 납품 단어("박스")가 들어간 잡담을 명령으로 오인 |

정리하면 실제 모델 결함은 **(a) 단위/수사 생성 불안정**(3·7), **(b) 동사 겹침으로 인한 기능 혼동**(11·12), **(c) 잡담 속 납품 단어에 과반응**(9) 세 가지입니다. 1·2·8·10은 데이터 생성 틀이 "박스 하나"를 수량으로 라벨링하지 않은 **정답 쪽 결함**이고, 4·6은 문장만으로는 사람도 못 가르는 **본질적 모호성**입니다. 이 둘을 고치면 점수가 더 올라갑니다.

### 파이프라인 데모 (10문장)

| # | 발화 | 경로 | 모델 출력 | 응답 | ms |
| ---: | --- | --- | --- | --- | ---: |
| 1 | 다음 어디야 | 의도분류만 (LLM 생략) | `next_stop` (0.97) | 다음은 서초점이에요. 남은 곳은 5곳이에요. | 118 |
| 2 | 여기 뭐 내려야 돼 | LLM function calling | `{"fn":"stop_items"}` | 역삼점 납품은 서울우유 12개, 바나나우유 6개, 제육도시락 4개, 생수 2박스예요. | 691 |
| 3 | 우유 두 개 터졌어 | LLM function calling | `{"fn":"report_issue","item":"우유","issue":"파손","qty":2,"unit":"개"}` | 서울우유, 바나나우유, 딸기우유 중 어떤 건가요? | 2,769 |
| 4 | 서울우유 | 되묻기 답 | — | 역삼점 서울우유 2개 파손으로 기록했어요. | 1 |
| 5 | 점장님한테 넘겼어 | LLM function calling | `{"fn":"complete","receiver":"점장님"}` | 역삼점 납품 완료로 기록했어요. 인수자는 점장님이에요. | 1,161 |
| 6 | 서초점 콜라 몇 박스야 | LLM function calling | `{"fn":"stop_items","store":"서초점","item":"콜라"}` | 서초점 콜라는 1박스예요. | 1,540 |
| 7 | 이거 미지근해 | LLM function calling | `{"fn":"report_issue","issue":"온도이상"}` | 어떤 품목인가요? | 1,072 |
| 8 | 바나나우유 | 되묻기 답 | — | 서초점 바나나우유 온도이상으로 기록했어요. | 0 |
| 9 | 다음 어디 가야 하지 | 의도분류만 (LLM 생략) | `next_stop` (0.97) | 다음은 방배점이에요. 남은 곳은 4곳이에요. | 11 |
| 10 | 노래 틀어줘 | 의도분류만 (LLM 생략) | `other` (0.95) | 죄송해요, 배송 업무만 도와드릴 수 있어요. | 12 |

되묻기(3→4, 7→8)가 의도대로 동작하고, 값이 필요 없는 명령(1·9·10)은 LLM을 건너뛰어 **11~118 ms**에 끝납니다. LLM을 타면 PC GPU 기준 0.7~2.8초입니다.

---

## 한계와 다음 단계

**지금의 한계**

- 모든 평가가 **합성 데이터 기반 텍스트 입력**입니다. 실제 기사의 목소리, 트럭 소음, 사투리로는 아직 측정하지 않았습니다.
- STT를 거치지 않았으므로 **STT 오류가 누적됐을 때의 성능**을 모릅니다. 데이터 생성 시 자모 치환으로 오인식을 약 10% 흉내 냈을 뿐입니다.
- `next_stop` vs `stop_items`처럼 **문장만으로 구분 불가능한 발화**가 남아 있습니다. 화면 상태나 직전 대화를 문맥으로 넣어야 풀립니다.
- 속도는 **PC GPU 기준**입니다. 보드(RK3588 NPU) 실측치가 아닙니다.
- 배송 DB가 **노트북 안의 가상 DB**입니다. 앱/백엔드 팀의 실제 API로 교체해야 합니다.

**다음 단계**

1. **RKLLM 변환 (W8A8)** — `out/fc_merged/`를 입력으로 `data/calibration_utterances.json`(450건)을 써서 양자화. 양자화 전후 test 점수 비교 필요.
2. **보드 포팅** — Orange Pi 5+에 STT(CPU 4스레드) + LLM(NPU) + TTS를 올리고 실제 지연시간 측정. NPU는 LLM 전용으로 둡니다.
3. **실제 음성 평가** — 기사 목소리로 녹음한 발화 세트를 만들어 STT→파이프라인 전 구간 정확도 측정.
4. **데이터 보강** — 위 오답 분석의 (a)(b)(c)와 "박스 하나" 라벨링 문제를 고쳐 재학습.
5. **문맥 활용** — 현재 화면/직전 발화를 프롬프트에 넣어 모호한 발화 해소.

---

## 저장소 구조

```
LogiOn/
├─ README.md
├─ requirements.txt
├─ .gitignore
├─ notebooks/
│  └─ LogiOn_AI_pipeline.ipynb      실행 결과가 모두 들어간 노트북
├─ data/
│  ├─ intent_dataset.csv            의도분류 학습용 (id, text, label, split, source, ambiguity)
│  ├─ fc_dataset.csv                function calling 학습용 (id, text, target, split, source, ambiguity)
│  ├─ gemini_prompt.txt             제미나이에 넣을 데이터 생성 프롬프트
│  ├─ gemini_raw.jsonl              제미나이가 생성한 원본 236줄
│  └─ calibration_utterances.json   RKLLM 양자화 캘리브레이션용 450건
└─ results/
   ├─ test_summary.json             핵심 지표
   ├─ test_pred_intent.csv          의도분류 test 예측 431건 (틀린 건 포함)
   └─ test_pred_fc.csv              function calling test 예측 431건 (지표 컬럼 포함)
```

모델 가중치(`out/`)는 용량 때문에 저장소에 포함하지 않습니다. 노트북을 실행하면 다시 만들어집니다.

---

## 팀 역할

| 역할 | 담당 범위 |
| --- | --- |
| AI | 데이터 설계·생성, 의도분류·function calling 학습, 평가, RKLLM 변환 |
| 보드 | Orange Pi 5+ 환경 구성, NPU 런타임, STT/TTS 포팅, 실시간 성능 |
| 앱 | 음성 입출력, 화면, 배송 상태 관리, AI 모듈 연동 |
| 프론트 | 기사용 UI/UX, 되묻기 흐름 화면 설계 |
