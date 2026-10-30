# 단일 모델(v3-single) 보고서

브랜치 `single-llm` (main `5e9d7cd` 에서 분기). **의도분류(klue/roberta-small)를 기본 경로에서 빼고, function calling 모델(`out/fc_merged`, Qwen2.5-1.5B + LoRA 병합본) 하나가 기능 선택(JSON 의 `fn`)과 값 추출을 모두 맡는 구조.** 재학습 없음, test 431건·평가 기준은 v2.1 과 같음. 숫자는 모두 이 PC(RTX 5050 8GB, bf16)에서 실제로 돌린 값이며 **보드(RK3588) 측정값은 없습니다.**

원본 파일: `results/single_llm/` (`summary.json`, `per_class.csv`, `test_rows_fc_only.csv`, `disagree_v2_1_vs_fc_only.csv`, `fn_wrong_fc.csv`, `latency_per_sentence.csv`, `demo_results.json`, `demo_followup.json`, `demo_results_v2_1_regression.json`), 평가 코드 `scripts/eval_single_llm.py`, 로그 `logs/eval_single_llm.log`.

## 1단계 — FC 단독 vs v2.1 (test 431)

방법: v2.1 평가와 같은 `row_results`/`summarize_rr`(노트북 규칙 코드)에, FC 출력의 `fn` 을 one-hot 확률로 넣고 `SKIP_FNS=()`, `tau=0` 으로 돌렸습니다. FC 생성은 v2.1 과 동일(배치 8, 탐욕, repetition_penalty 1.1)하고, 저장돼 있던 `results/v2_1/test_pred_fc.csv` 와 **출력이 100% 일치**함을 확인했습니다.

### (1) 기능(fn) 정확도 — roberta vs FC

| 기능 | n | roberta (의도분류) | FC 의 fn | 최종 정답 v2.1 (되묻기 포함) | 최종 정답 FC 단독 |
| --- | --- | --- | --- | --- | --- |
| next_stop | 74 | 1.000 | 0.770 | 0.770 | 0.770 |
| stop_items | 75 | 0.933 | 0.880 | 0.893 | 0.880 |
| complete | 70 | 0.957 | 1.000 | 1.000 | 1.000 |
| report_issue | 69 | 0.971 | 0.870 | 0.623 | 0.623 |
| scan | 73 | 0.932 | 0.822 | 0.836 | 0.822 |
| other | 70 | 0.643 | 0.986 | 0.986 | 0.986 |
| **전체** | 431 | **0.9072** (macro-F1 0.9051) | **0.8863** (macro-F1 0.8931) | | |

FC 의 혼동 (행 = 정답, 열 = FC 예측; 순서 next_stop, stop_items, complete, report_issue, scan, other):

| 정답 \ 예측 | next_stop | stop_items | complete | report_issue | scan | other |
| --- | --- | --- | --- | --- | --- | --- |
| next_stop | 57 | **16** | 0 | 0 | 0 | 1 |
| stop_items | 0 | 66 | 0 | **9** | 0 | 0 |
| complete | 0 | 0 | 70 | 0 | 0 | 0 |
| report_issue | 0 | **9** | 0 | 60 | 0 | 0 |
| scan | 0 | **13** | 0 | 0 | 60 | 0 |
| other | 1 | 0 | 0 | 0 | 0 | 69 |

틀린 문장 예 (FC fn 오답 49건, `fn_wrong_fc.csv`): next_stop→stop_items 16건 "어 몇 개 남았죠", "몇 개 남았지 얼른"; scan→stop_items 13건 "물건 확인할게요"; stop_items→report_issue 9건 "아 사이다 여기 들어가는 거 맞아 얼른"; report_issue→stop_items 9건 "잠깐 이온 음료 상태 좀 봐야겠다 좀"; next_stop→other "아 네비 다음에 어디 가래"; other→next_stop "노래 다음 곡으로 넘겨".
오답이 같은 말 틀("몇 개 남았죠", "물건 확인할게", "상태 좀 봐야겠다", "여기 들어가는 거 맞아")에 몰려 있는데, 기존 분석(README "v2 에서 떨어진 이유")의 test 에만 있는 말 틀과 같은 유형으로 **보이지만, 이 틀들이 test 전용인지는 이번에 다시 확인하지 않았습니다 (추정).** roberta 도 같은 문장 일부에서 틀립니다 (next_stop 은 맞추지만 `other` 70건 중 24건을 next_stop 으로 봄).

### (2) 파이프라인 최종 결과

| 지표 | v2.1 | FC 단독 | 차이 |
| --- | --- | --- | --- |
| 최종 정확도 (되묻기 포함) | 0.8515 | 0.8469 | **−0.46pp** |
| 되묻기 없이 맞춘 비율 | 0.8469 | 0.8469 | 0 |
| 틀리게 실행한 비율 | 0.1485 | 0.1531 | **+0.46pp** |
| 확률 기반 되묻기 비율 | 0.0046 | 0 | −0.46pp |
| LLM 생략 비율 | 0.2413 | 0 | — |
| JSON 오류율 | 0 | 0 | 같음 |
| 값 되묻기(슬롯 부족) 비율 | — | 0.0603 (정답 기준 0.0580) | |

문장 단위: 둘 다 정답 365, **v2.1 만 정답 2**, 단일만 정답 0, 둘 다 오답 64. 차이 2문장은 모두 margin 되묻기가 구한 것("아 사이다 여기 들어가는 거 맞아 얼른", "저기 물건 확인할게").

### (3) PC 문장당 지연 (배치 1, bf16, RTX 5050, 문장당 단독 측정)

| 기능 | n | FC 단독 평균(ms) | v2.1 평균(ms, 시뮬레이션) | 생성 토큰 평균 |
| --- | --- | --- | --- | --- |
| next_stop | 74 | 317.6 | 322.2 | 6.0 |
| stop_items | 75 | 501.1 | 498.5 | 10.1 |
| complete | 70 | 474.4 | 479.1 | 9.5 |
| report_issue | 69 | 1070.1 | 1074.9 | 22.9 |
| scan | 73 | 282.6 | **57.1** | 5.2 |
| other | 70 | 274.3 | **106.6** | 5.0 |
| 전체 | 431 | **482.5** (중앙 317, p95 1231) | 418.9 | 9.7 |

v2.1 값은 "의도분류 시간 + (LLM 을 부른 문장만 LLM 시간)" 으로 계산한 시뮬레이션입니다. 의도분류(PyTorch)는 문장당 평균 4.7ms 입니다. 값 없는 명령(next_stop/scan/other 217건)의 FC 단독 평균은 291.8ms 입니다.

### (4) 값 없는 명령의 생성 토큰

평균 **5.40개** (최대 6, 종료 토큰 제외; next_stop 6.0, scan 5.2, other 5.0). 평균 프롬프트 126.3토큰. 정답 JSON 최대 36토큰, 예측 최대 36토큰 (→ `max_new_tokens` 64 면 충분).

### 판정

기준: 최종 정확도가 v2.1 보다 1pp 이상 낮지 않고, 틀리게 실행한 비율이 1pp 이상 높지 않으면 "괜찮음".
**최종 정확도 −0.46pp, 틀리게 실행 +0.46pp → 기준 충족("괜찮음"), 2·3단계로 진행했습니다.**
단, 기능 정확도 자체는 −2.1pp 이고 scan/other 의 빠른 길(57~107ms)이 사라져 PC 에서 이 두 기능은 약 275~280ms 가 됩니다. **보드에서의 지연은 측정하지 못해 모릅니다.**

## 2단계 — 코드·설정·데모

- `config/pipeline_v3_single.json` 신설 (`intent_model: null`; 기존 `pipeline_v2_1.json` 은 수정 안 함). `demo/pipeline.py` 는 `intent_model` 이 null 이면 의도분류 없이 항상 FC 를 부르고, `fn` 이 없거나 알 수 없는 값이면 "다시 말씀해 주세요" 로 되묻습니다. 경로가 있으면(v2.1 설정) 예전과 동일하게 동작합니다. `demo/chat_server.py` 에 `--config` 추가.
- 기본 설정이 v3 로 바뀌므로 **백엔드의 `DbAssistant` 도 설정을 안 주면 단일 모델로 돕니다** (백엔드 코드는 건드리지 않음). 호환을 위해 단일 모델에서도 `trace["intent"]` 를 `{"route":"llm","top3":[{"fn","p"}]}` 모양으로 채우고, 이때 `p`(응답의 `conf`)는 **분류 확률이 아니라 LLM 토큰 확률 평균**입니다. 환경변수 `LOGION_PIPELINE_CONFIG` 로 설정을 고를 수 있습니다.
- 백엔드 테스트(`backend/tests`, 읽기 전용으로 실행만 함): `LOGION_PIPELINE_CONFIG=config/pipeline_v2_1.json` 이면 **20개 모두 통과**(= v2.1 동작 유지 확인), 기본(v3 단일)이면 **17 통과 / 3 실패** (`test_choice_question_then_answer`, `test_sessions_are_separate`, `test_scan_skips_llm` — 가짜 분류기로 margin 되묻기·LLM 생략을 검사하는 테스트라 단일 모델에서는 성립하지 않음). 백엔드 담당자가 단일 모델 기준으로 고쳐야 합니다.
- `scripts/board_latency.py` 는 `--with-intent` 를 줄 때만 의도분류 단계를 넣도록 바꿨습니다 (문법 확인만 함, 보드·sherpa 없이 실행은 못 함). `scripts/make_diagram.py` 는 단일 구조 그림으로 바꾸고 이전 그림은 `scripts/make_diagram_v2_1.py` → `docs/architecture_v2_1.png` 로 보존했습니다.

### 채팅 서버 실제 실행 결과 (`python demo/chat_server.py --port 7861`, 설정 v3-single, PC GPU)

`scripts/demo_single_llm.py` 로 `/chat` 에 보냄 (문장 순서대로, 같은 서버 세션). 아래 값은 `demo_results.json` 의 실제 출력입니다.

| # | 입력 | fn | LLM 출력 | 응답 | 전체 ms |
| --- | --- | --- | --- | --- | --- |
| 1 | 다음 배송지 어디야 | next_stop | `{"fn":"next_stop"}` | 다음은 GS25 성수연무장점이에요. 남은 곳은 3곳이에요. | 815.1 |
| 2 | CU 서울숲점에 내릴 물건 알려줘 | stop_items | `{"fn":"stop_items","store":"CU 서울숲점"}` | CU 서울숲점 납품은 서울우유 6개, 참치삼각김밥 10개, 콜라 1박스예요. | 634.3 |
| 3 | GS25 성수연무장점 납품 끝났어 | complete | `{"fn":"complete","store":"GS25","store_name":"성수연무장점"}` | GS25 성수연무장점 납품 완료로 기록했어요. | 979.2 |
| 4 | 서울우유 두 개 파손됐어 | report_issue | `{"fn":"report_issue","item":"서울우유","issue":"파손","qty":2,"unit":"개"}` | CU 서울숲점 서울우유 2개 파손으로 기록했어요. | 1211.3 |
| 5 | 바코드 찍을게 | scan | `{"fn":"scan"}` | 스캔 화면을 열게요. | 271.4 |
| 6 | 오늘 날씨 어때 | other | `{"fn":"other"}` | 죄송해요, 배송 업무만 도와드릴 수 있어요. | 272.0 |
| 7 | 세븐일레븐 뚝섬점 컵라면 3개 수량부족 | report_issue | `{"fn":"report_issue","store":"세븐일레븐","item":"컵라면","issue":"수량부족","qty":3,"unit":"개"}` | 세븐일레븐 뚝섬점 컵라면 3개 수량부족으로 기록했어요. | 1556.9 |
| 8 | 물건 문제 있어요 | report_issue | `{"fn":"report_issue"}` | **되묻기(슬롯)**: 어떤 품목인가요? | 315.5 |
| 9 | (8 에 이어) 컵라면 | report_issue | (이어받기, LLM 안 부름) | **되묻기**: 어떤 문제인가요? 파손, 수량부족, 오배송, 온도이상 중에서 말씀해 주세요. | — |

- 전체 ms 는 LLM 호출 포함 서버 내부 측정(값 보정·실행은 0.0ms 로 찍힘)이고, 첫 요청은 워밍업 영향이 섞였을 수 있습니다. 1회씩만 잰 값이라 평가용 지연이 아닙니다 (지연은 위 (3) 표 사용).
- 모든 기능이 의도분류 없이 FC 의 `fn` 만으로 올바르게 갈렸고, 슬롯이 빈 경우의 되묻기와 이어받기도 동작했습니다 (`demo_results.json`, `demo_followup.json`).
- 3번의 `store_name` 은 모델이 만든 불필요한 키로, `resolve()` 가 무시하고 `store:"GS25"` + 점포 후보로 "GS25 성수연무장점"을 찾았습니다 (이 PC 의 DB 에 GS25 가 1곳뿐이라 맞았습니다).
- **margin 기반 선택지 되묻기("남은 배송지 말씀하시는 건가요, …")는 단일 모델에는 없습니다.** 되묻기가 필요한 모호한 말은 FC 가 하나를 골라 실행합니다 (v2.1 에서 이 되묻기가 구한 건 test 2문장).
- 같은 8문장을 v2.1 설정(`--config config/pipeline_v2_1.json`, 포트 7862)으로도 돌려 동작 확인: 응답 문장은 동일하고 5·6번(scan/other)만 LLM 을 건너뜀(route `skip`). `demo_results_v2_1_regression.json`.
- 화면(HTML) 캡처는 다시 만들지 않았습니다 (`docs/chat_demo/` 는 v2.1 때 캡처 그대로). 브라우저로 직접 화면을 열어 보는 확인도 하지 않았습니다 (`/info`·`/chat` 응답만 확인).

## 3단계 — RKLLM 변환 (상세: `docs/rkllm_convert.md`)

| 항목 | 상태 |
| --- | --- |
| 배포물 SHA256 (도커 이미지·템플릿·보드 패키지) | **실제 계산, SHA256SUMS 와 모두 일치** |
| 작업 폴더 `E:\logion-rkllm\rkllm-team\` (model/, data/config.yaml, data/queries.json) | **완료**. system_prompt 가 FC 상수와 글자 단위로 같음을 확인, eos 151645 (config.json·generation_config.json), max_context 256, calib_max_new_tokens 64 |
| 저장소 `rkllm/` (config.yaml, queries.json, 템플릿 README, run.sh) | 커밋 (모델·.rkllm 없음) |
| 작업 폴더 압축본 | `E:\logion-rkllm\logion-rkllm-team.zip` 2.41GB, SHA256 `96b02d6b…cbb88c7` (저장소 밖) |
| 3-2 `./run.sh check/calib/convert/build-demo` | **미실행.** 이 PC: 하드웨어 가상화 꺼짐(BIOS), docker 미설치, WSL 미설치. `.rkllm` 파일 없음 |

수치: max_context 근거 = 전체 2,754건 프롬프트+정답+종료 토큰 최대 179 (→192 → 256), 정답 JSON 최대 36토큰 (64 로 충분).
**지키지 못한 조건:** 캘리브레이션 450건은 val·test 와 겹치지 않지만 **train 450건과는 100% 겹칩니다** (train 에서 뽑은 것).

## 못 한 것 / 추정 / 미확인

- **못 한 것:** RKLLM 변환 4단계(`check/calib/convert/build-demo`) 전부, `.rkllm` 산출물, 보드 측정(정확도·지연·메모리), 보드에서의 양자화 후 정확도.
- **추정:** FC 오답 틀이 test 전용 말 틀이라는 설명(기존 분석과 같은 유형으로 보임, 재확인 안 함); 보드에서 scan/other 가 LLM 을 거치면 약 5~6토큰 생성이므로 PC 처럼 짧을 것이라는 기대(NPU 에서의 값은 모름); `calib` 이 `generation_config.json` 의 greedy 설정을 따를 것이라는 가정.
- **미확인:** 도커 이미지 안 `calib` 이 만드는 target 이 한 줄 JSON 인지; `./run.sh check` 통과 여부; PDF 안내문(변환 도구가 없어 읽지 못함); 브라우저에서 실제 화면 모양(HTTP 응답만 확인); `scripts/board_latency.py` 의 `--with-intent` 없는 경로(문법만 확인).

## 사람이 해야 할 일

1. **BIOS 에서 CPU 가상화(SVM) 켜기** — 이 PC 에서 WSL2/Docker 로 변환하려면 필요. 아니면 수업 서버에서 변환 (권장).
2. **서버 접속 정보/계정 확보** → `docs/rkllm_convert.md` 의 "서버에서 할 일" 순서대로 실행 (zip: `E:\logion-rkllm\logion-rkllm-team.zip`, 도커 이미지 `rkllm-class-1.3.0.tar.gz`). 서버는 x86_64 리눅스 + NVIDIA GPU 권장 (ARM 불가).
3. 변환 후 `./run.sh calib` 결과(`data_quant.json`) 앞 10건·무작위 10건 눈으로 확인 — target 이 한 줄 JSON 인지.
4. `.rkllm` 과 `.rkllm.json`, `demo_Linux_aarch64/` 를 보드로 복사하고, `.rkllm` 은 **구글 드라이브에 업로드** (md5 와 크기를 함께 기록). 이 저장소에는 올리지 않습니다.
5. 보드에서 `scripts/board_eval.py`, `scripts/board_latency.py` 로 정확도·지연 측정 → 값 없는 명령(scan/other/next_stop)이 LLM 을 거쳐도 쓸 만한지 결정.
6. 백엔드 담당자: `backend/tests/test_assistant.py` 3개 테스트를 단일 모델 기준으로 수정 (또는 `LOGION_PIPELINE_CONFIG=config/pipeline_v2_1.json` 로 실행).
7. (선택) 가능하면 train 과 겹치지 않는 실제 기사 발화 300~1,000건으로 `rkllm/queries.json` 교체.
