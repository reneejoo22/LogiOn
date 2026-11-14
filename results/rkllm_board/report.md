# RKLLM 보드 검증 결과 (2026-11-14)

Orange Pi 5+ (RK3588) 위에서 RKLLM 으로 변환한 FC 모델이 PC 원본(`out/fc_merged`)과 같은 결과를 내는지 확인했다.

## 모델 파일 (레포에 넣지 않음)

| 파일 | 크기 | md5 | 보드 경로 |
|---|---|---|---|
| logion-delivery_w8a8_opt1_cal450.rkllm | 2,038,770,100 B | 908a0eaacf137d6c7e5c2920fdb7e03d | ~/rkllm/logion/ |
| logion-delivery_w8a8_opt1_cal450.rkllm.json | 957 B | 8b062a3e8cf294090ba7b735799e6c9d | ~/rkllm/logion/ |
| demo_Linux_aarch64/lib/librkllmrt.so | 7.6 MB | 78d6d4094a64ee7659bbafde6b07c408 | ~/rkllm/logion/demo_Linux_aarch64/lib/ |

변환: rkllm-toolkit 1.3.0, w8a8, optimization 1, calib 450문장(`data_quant.json`, PC 와 같은 system prompt + Qwen 템플릿), max_context 256, target RK3588. PC(CPU) 에서 변환.
PC 에서 만든 파일과 보드 파일의 md5 는 4개 모두 같다.

## 처음 llm_demo 에서 JSON 이 안 나온 이유

`llm_demo` 는 system prompt 를 넣지 않아서 `.rkllm.json` 의 기본값 `You are Qwen, created by Alibaba Cloud...` 로 돌았다 (prefill 14~35 토큰).
양자화나 길이 문제가 아니었다.

- system + 짧은 질문 = 120 토큰, test 431건 최장 입력 145 + 최장 정답 37 = 179 토큰 → max_context 256 안에 들어감
- 서버(`rkllm/server/logion_server.py`)에서 `rkllm_set_chat_template` 으로 PC 와 같은 Qwen2.5 템플릿 + LogiOn system prompt 를 넣으면 첫 요청 prefill 이 126 토큰으로 PC 기록(`latency_per_sentence.csv` prompt_tokens)과 같다.
- 생성 설정도 PC(`config/pipeline_v3_single.json` generation)와 같게: top_k 1(greedy), repeat_penalty 1.1, 최대 64 토큰.

## test 431건: PC vs 보드

| 지표 | PC (fc_merged, GPU) | 보드 (RKLLM w8a8) |
|---|---|---|
| JSON 유효 | 1.000 (431) | 1.000 (431) |
| fn 정확도 | 0.886 (382) | 0.896 (386) |
| 완전일치 | 0.847 (365) | 0.856 (369) |
| PC 와 출력이 글자까지 같음 | — | 97.9% (422/431) |
| 응답시간 중앙값 / p90 / 최대 | 317 / 1063 / 1655 ms | 574 / 1848 / 2915 ms |

채점은 PC 결과 CSV(`results/single_llm/test_rows_fc_only.csv`)의 fn_ok·exact 를 431건 모두 그대로 재현하는 방식으로 했다 (불일치 0건).
보드가 4건 더 맞힌 것은 9건 차이 안의 우연으로 보고, "같은 수준" 으로 판단한다.

함수별 (n / PC fn / 보드 fn / PC 완전일치 / 보드 완전일치):

| 함수 | n | PC fn | 보드 fn | PC exact | 보드 exact |
|---|---|---|---|---|---|
| next_stop | 74 | 57 | 61 | 57 | 61 |
| stop_items | 75 | 66 | 66 | 66 | 65 |
| complete | 70 | 70 | 70 | 70 | 70 |
| report_issue | 69 | 60 | 60 | 43 | 44 |
| scan | 73 | 60 | 61 | 60 | 61 |
| other | 70 | 69 | 68 | 69 | 68 |

## 출력이 다른 9건 (`diff431.csv`)

| id | 문장 | PC | 보드 | 정답 기준 |
|---|---|---|---|---|
| u00340 | 몇 개 남았지 얼른 | stop_items | next_stop | 보드 맞음 |
| u02162 | 아 몇 개 남았지 빨리 | stop_items | next_stop | 보드 맞음 |
| u02509 | 자 몇 개 남았지 빨리 | stop_items | next_stop | 보드 맞음 |
| u01590 | 저기 물건 확인할게 | stop_items | scan | 보드 맞음 |
| u01863 | 아 네비 다음에 어디 가래 | other | next_stop | 보드 맞음 |
| u01782 | 젤리 박스 하나 찌그러졌어 | unit "개" | unit "박스" | 보드 맞음 |
| u01444 | 반포점 커피 얼마나 하차하지 | item 커피 | item 빠짐 | PC 맞음 |
| u02240 | 이제 엄마한테 전화해주세요 | other | **complete(receiver 엄마)** | PC 맞음 |
| u01286 | 요구르트 박스 하나 파손됐어 | unit "개" | unit 빠짐 | 둘 다 틀림 (정답 박스) |

### 위험 오류 1건

**"이제 엄마한테 전화해주세요" → `{"fn":"complete","receiver":"엄마"}`**.
상관없는 말을 납품 완료로 처리하는 오류라 실제 동작으로 이어지면 위험하다. 431건 중 이 1건뿐이지만, 백엔드에서 complete 실행 전 확인(되묻기)이나 receiver 값 검증을 두는 것이 좋다.

## 12개 비교표 (`compare12.csv`, 원본 응답 `res12/`)

test 세트에서 함수별 2개씩 (calib 와 겹치지 않는 문장). 12개 모두 PC 와 글자까지 같다.

| 문장 | PC = 보드 출력 | PC ms | 보드 ms (curl) |
|---|---|---|---|
| 지금 다음 남은 데가 어디지 | {"fn":"next_stop"} | 321 | 965 (첫 요청, prefill 126) |
| 어디로 갈지 알려줘 | {"fn":"next_stop"} | 319 | 556 |
| 여기 내릴 거 읽어줘 | {"fn":"stop_items"} | 317 | 568 |
| 반포점 리스트 불러줘 | {"fn":"stop_items","store":"반포점"} | 578 | 985 |
| 점장님 확인했어 완료 빨리 | {"fn":"complete","receiver":"점장님"} | 497 | 879 |
| 어 점장님한테 인계했어 얼른 | {"fn":"complete","receiver":"점장님"} | 498 | 848 |
| 제육도시락 박스 하나 다 녹았어 | {"fn":"report_issue","item":"제육도시락","issue":"온도이상","qty":1} | 1217 | 2041 |
| 자 서초점 커피 여덟판 터졌어 등록해줘 | {...,"store":"서초점","item":"커피","issue":"파손","qty":8,"unit":"판"} | 1479 | 2498 |
| 스캐너 켜라고 | {"fn":"scan"} | 284 | 474 |
| 송장 스캔 켜라 | {"fn":"scan"} | 275 | 487 |
| 근처 화장실 어디야 얼른 | {"fn":"other"} | 275 | 489 |
| 저기 근처 화장실 어디야 지금 | {"fn":"other"} | 272 | 500 |

## 속도·메모리 (`speed_memory.json`)

CPU/NPU 클럭 고정 없이 측정 (sudo 미사용) → 참고값.

- 생성 13.1 tok/s (중앙값), prefill 약 145 tok/s
- 첫 요청 뒤에는 system prompt KV 를 재사용해 user 부분(12~25 토큰)만 prefill
- 최대 메모리 1,681 MB (16GB 보드)
- 짧은 명령(next_stop/scan/other) 약 0.5초, report_issue 2~3초

## 파일

- `res_431.jsonl` — 보드 출력 431건 (id, board_out, client_ms, perf)
- `diff431.csv` — PC 와 출력이 다른 9건
- `compare12.csv`, `res12/` — 12개 비교표와 서버 원본 응답
- `speed_memory.json` — 속도·메모리 요약
- 서버 코드: `rkllm/server/logion_server.py` (보드 `~/rkllm/server/logion_server.py` 와 md5 3eac025392553db03956e5df434afa9d 동일)
