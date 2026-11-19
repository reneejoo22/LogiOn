# LogiOn

**말 한마디로 납품 업무를 처리하는 온디바이스 AI 음성 비서 — 편의점 납품기사용, Orange Pi 5 Plus(RK3588) NPU 위에서 동작**

운전 중이거나 양손에 짐을 든 납품기사가 "다음 어디야", "우유 두 개 터졌어" 처럼 말하면, 폰이 녹음을 오렌지파이 보드로 보냅니다. **보드가 알아듣고(STT) → AI 가 기능과 값을 골라 배송 DB 를 조회·기록하고 → 답을 음성으로 만들어(TTS)** 폰이 화면에 띄우고 읽어 줍니다. 폰은 화면·마이크·스피커만 쓰고, 인터넷 클라우드 없이 **폰 + 보드 하나**로 돕니다 (PC GPU 모드도 지원).

| 항목 | 내용 |
| --- | --- |
| 과목 | 2026학년도 모바일시스템응용프로젝트 (C분반) |
| 팀 | [8] 2팀 LogiOn |
| 산학 멘토 | 마음AI |

| 역할 | 이름 | GitHub | 담당 |
| --- | --- | --- | --- |
| 팀장 | | | 앱 디자인, 발표 자료 준비 및 발표 |
| AI | | reneejoo22 | 데이터·모델 학습, RKLLM 변환, 보드 배포, 오렌지파이 설정 |
| 백엔드 | | KIMJAESUN | FastAPI·SQLite, 배송 API |
| 앱(프론트) | | yeeun0912 | Android 앱 프론트, STT·TTS 연동 |
| 보드·통합 | | | 미팅 준비 |

### 구조: STT·TTS·LLM 모두 보드

```
 폰 (Android 앱)                         Orange Pi 5 Plus (RK3588, 16GB)
 ┌──────────────────┐  POST /api/assistant/voice   ┌─────────────────────────────────────────────┐
 │ 🎤 녹음 16kHz wav │ ───────────────────────────▶ │ ① VAD 앞뒤 무음 제거 · STT SenseVoice  (CPU 4) │
 │                  │                              │ ② 파이프라인: LLM 기능·값 뽑기       (NPU)    │
 │ 화면: 인식 글자·답 │ ◀──── JSON (text, reply, …) ── │    → DB 이름 보정 → 조회·기록 (SQLite)        │
 │ 🔊 응답 음성 재생  │ ◀──── GET audio_url (wav) ──── │ ③ 답 문장 → TTS VITS 한국어          (CPU 2) │
 └──────────────────┘                              └─────────────────────────────────────────────┘
```

아래 그림은 AI 처리 흐름(②)을 자세히 그린 것입니다. 그림에는 STT·TTS 가 폰에 있는 예전 구조가 그려져 있고, 지금은 둘 다 보드에서 돕니다 ([음성 API](docs/voice_api.md)).

![LogiOn 전체 파이프라인](docs/pipeline.png)

## 핵심 결과

test 431건(학습에 쓰지 않은 문장)을 PC 원본 모델과 보드 변환 모델에 똑같이 넣어 비교했습니다. 자세히: [`results/rkllm_board/report.md`](results/rkllm_board/report.md)

| 지표 | PC 원본 (fp16, GPU) | **보드 (RKLLM W8A8, NPU)** |
| --- | ---: | ---: |
| JSON 형식 유효 | 100% | **100%** |
| 기능(함수) 정확도 | 88.6% | **89.6%** |
| 완전 일치 (기능 + 값 모두) | 84.7% | **85.6%** |
| 응답 시간 중앙값 | 317 ms | **574 ms** |
| LLM 메모리 | — | **1.7 GB** (보드 RAM 16GB) |

양자화 후에도 정확도가 떨어지지 않았고(출력이 PC 와 글자까지 같은 비율 97.9%), 보드 하나로 백엔드 + AI 파이프라인 + LLM 이 PC 없이 돌아가는 것을 확인했습니다 ([보드 배포](docs/board_deploy.md)).

**음성까지 보드에서 처리 (시연 녹음 5문장, [결과](results/board_voice/report.md)):** 5/5 성공했습니다.

| 단계 | 시간 |
| --- | ---: |
| STT | 0.18~0.35초 |
| LLM | 0.5~1.9초 |
| TTS | 0.6~1.2초 |
| 녹음 업로드 → 답 받기 | **1.4~3.5초** |

요청 처리 중 보드 CPU 는 최대 51%, 백엔드 메모리는 최대 722MB 였습니다.

## 지원 기능 6개

| 기능 | 예시 발화 | 하는 일 |
| --- | --- | --- |
| `next_stop` | "다음 어디야" | 다음 배송지와 남은 곳 수 안내 |
| `stop_items` | "서울숲점 콜라 몇 박스야" | 점포별 내릴 품목·수량 조회 |
| `complete` | "점장님한테 넘겼어" | 납품 완료 기록 (인수자 포함) |
| `report_issue` | "우유 두 개 터졌어" | 파손·수량부족·오배송·온도이상 기록 (품목이 모호하면 되묻기) |
| `scan` | "바코드 찍을게" | 스캔 화면 열기 |
| `other` | "근처 화장실 어디야" | 업무 밖 요청은 정중히 거절 |

LLM 은 "기능을 고르고 말한 값을 JSON 으로 옮기는 일"만 하고, DB 이름 맞추기·되묻기는 규칙 코드가 맡아 없는 값을 지어내지 않습니다.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| 앱 (폰) | Kotlin, Jetpack Compose, Retrofit · 녹음(16kHz wav) 업로드와 응답 음성 재생 |
| 백엔드 (보드) | Python 3.10, FastAPI, SQLite, uvicorn |
| 음성 (보드 CPU) | sherpa-onnx 1.13.8: silero VAD, SenseVoice-Small int8 STT (4스레드), 한국어 VITS TTS (2스레드) |
| AI 모델 | Qwen2.5-1.5B-Instruct + LoRA (function calling), PyTorch·transformers·peft 로 학습 |
| 보드 추론 | Orange Pi 5 Plus (RK3588), RKLLM 1.3.0 W8A8 변환, NPU 추론 서버 (`rkllm/server/`) |

## 폴더 구조

```
LogiOn/
├─ android/        Android 앱 (화면, 녹음·재생, AI 채팅 탭)
├─ backend/        FastAPI 백엔드 + SQLite 배송 DB (/api/assistant/voice, /chat)
├─ demo/           AI 파이프라인 (pipeline.py: LLM 호출 → 값 보정 → 실행 → 응답), 채팅 데모
├─ rkllm/          RKLLM 변환 설정, 보드 LLM 서버 (server/)
├─ scripts/board/  보드 설치·시작/종료 스크립트, systemd, 검증 스크립트
├─ speech/         STT/TTS 엔진 (보드 백엔드가 사용), 모델 받기·시험
├─ config/         파이프라인 설정 (system prompt, 생성 설정, LLM 백엔드)
├─ data/  notebooks/  export/   학습 데이터, 학습·평가 노트북, 변환
├─ results/        평가 결과 (rkllm_board/ = 보드 실측)
└─ docs/           문서 (개발문서 6종: dev_docs/)
```

모델 가중치(`out/`)와 `.rkllm` 파일은 용량 때문에 저장소에 넣지 않습니다.

## 실행 방법 (보드 하나로 시연하기)

STT·TTS·LLM 이 모두 보드에서 돕니다. 아래 순서대로 하면 됩니다. 처음 한 번 설치하는 방법은 [`docs/board_deploy.md`](docs/board_deploy.md) 1절에 있습니다.

### 1. 보드 켜기

1. Orange Pi 5 Plus 에 전원을 넣고 1분쯤 기다립니다.
2. 폰과 보드를 같은 망에 연결합니다. 셋 중 하나를 씁니다.
   - 소형 공유기
   - 폰 USB 테더링
   - Tailscale (개발용)
3. 보드 주소를 확인합니다. 보드에서 `hostname -I` 를 실행합니다 (Tailscale 은 `100.82.118.121`).
4. PC 에서 접속합니다.

```bash
ssh orangepi@<보드 IP>
```

### 2. 서버 실행 (보드에서)

```bash
cd ~/LogiOn
bash scripts/board/start_all.sh
```

- LLM 서버(:8090, NPU)를 먼저 켜고, 백엔드(:8000)를 켭니다.
- 백엔드는 시작할 때 STT·TTS 모델(`~/voice/models`)을 한 번 올립니다 (약 4초).
- 마지막 줄에 `"ready":true` 와 `"voice_ready":true` 가 보이면 준비된 것입니다.
- 끄기: `bash scripts/board/stop_all.sh`. 로그: `~/LogiOn/logs/backend.log`, `llm_server.log`

PC 에서 음성 API 를 바로 확인할 수 있습니다 (wav 16kHz mono 녹음).

```bash
curl -s -F file=@다음어디야.wav -F session_id=demo http://<보드 IP>:8000/api/assistant/voice
# → {"text":"다음 어디야?","reply":"다음은 GS25 성수연무장점이에요. …","audio_url":"/api/assistant/voice/audio/…", …}
curl -s -o reply.wav http://<보드 IP>:8000/api/assistant/voice/audio/<id>
```

### 3. 앱 연결

1. `android/app/src/main/java/com/example/logion/data/remote/RetrofitClient.kt` 의 `BASE_URL` 을 `http://<보드 IP>:8000/` 으로 바꿉니다.
2. Android Studio 로 폰(또는 에뮬레이터)에 설치합니다.
3. 앱 AI 채팅 탭 위쪽 카드에 "AI 연결됨 · RK3588 NPU …" 가 보이면 연결된 것입니다.

> **앱이 아직 바뀌기 전일 때:** 지금 앱은 폰 안에서 STT·TTS 를 하고 글자만 `/api/assistant/chat` 으로 보냅니다.
> 녹음을 `/api/assistant/voice` 로 보내도록 바꾸는 방법은 [`docs/voice_api.md`](docs/voice_api.md) 3절에 정리했습니다 (앱 담당).
> 바꾸기 전에도 위 순서로 보드 LLM 을 쓰는 시연은 그대로 됩니다.

### 4. 시연 문장

AI 채팅 탭에서 🎤 를 누르고 순서대로 말합니다. 아래 응답은 보드 실측입니다. 4번은 실측에서 "정자님" 으로 들렸는데, 표에는 "점장님" 으로 제대로 들었을 때의 응답을 적었습니다.

| # | 말하기 | 응답 | 화면 변화 |
| --- | --- | --- | --- |
| 1 | "다음 어디야" | 다음은 GS25 성수연무장점이에요. 남은 곳은 3곳이에요. | — |
| 2 | "서울숲점 콜라 몇 박스야" | CU 서울숲점 콜라는 1박스예요. | — |
| 3 | "우유 두 개 터졌어" | GS25 성수연무장점 서울우유 2개 파손으로 기록했어요. | 배송지 상세에 이상 보고 |
| 4 | "성수연무장점 납품 완료, 점장님한테 넘겼어" | GS25 성수연무장점 납품 완료로 기록했어요. 인수자는 점장님이에요. | 배송목록 완료 1 |
| 5 | "근처 화장실 어디야" | 죄송해요, 배송 업무만 도와드릴 수 있어요. | — |

- 3·4번은 DB 에 실제로 기록됩니다. 연습할 때는 DB 복사본으로 백엔드를 띄우면 원본이 그대로 남습니다.
  - 먼저 `bash scripts/board/stop_all.sh` 로 서버를 끕니다.
  - 그다음 `cp backend/data/logion.db logs/practice.db` 로 복사합니다.
  - 마지막으로 `LOGION_DB=$PWD/logs/practice.db bash scripts/board/start_all.sh` 로 다시 켭니다.
- 4번은 녹음에 따라 STT 가 "점장님" 을 "정자님" 으로 들은 적이 있습니다. 또박또박 말하면 됩니다.

### 다른 실행 방법

| 방법 | 요약 | 자세히 |
| --- | --- | --- |
| PC GPU 실행 | `.venv` 에 CUDA torch + `requirements.txt` → `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000` (STT·TTS 모델은 `python speech/download_models.py --no-android`) | [`docs/ai_details.md` 실행 방법](docs/ai_details.md#실행-방법) |
| 앱 안 STT·TTS (예전 구조) | 에뮬레이터에서 앱 실행 → 마이크 켜기(`adb emu avd hostmicon`) → 🎤 | [`docs/speech_stt_tts.md`](docs/speech_stt_tts.md) |

## 개발문서 6종

| # | 문서 |
| --- | --- |
| 1 | [요구사항 정의서](docs/dev_docs/%5B8%5D2팀%28LogiOn%29%20개발문서1_요구사항정의서.docx) |
| 2 | [아키텍처 설계서](docs/dev_docs/%5B8%5D2팀%28LogiOn%29%20개발문서2_아키텍처설계서.docx) |
| 3 | [모델 설계 및 최적화 문서](docs/dev_docs/%5B8%5D2팀%28LogiOn%29%20개발문서3_모델설계및최적화문서.docx) |
| 4 | [API 및 인터페이스 정의서](docs/dev_docs/%5B8%5D2팀%28LogiOn%29%20개발문서4_API및인터페이스정의서.docx) |
| 5 | [테스트 계획서 및 결과 보고서](docs/dev_docs/%5B8%5D2팀%28LogiOn%29%20개발문서5_테스트계획서및결과보고서.docx) |
| 6 | [배포 및 통합 가이드](docs/dev_docs/%5B8%5D2팀%28LogiOn%29%20개발문서6_배포및통합가이드.docx) |

## 더 볼 문서

| 문서 | 내용 |
| --- | --- |
| [`docs/ai_details.md`](docs/ai_details.md) | AI 파트 상세: 데이터 설계, 모델 선택, v1→v2→v3 평가, 틀린 예시 분석, 실행 방법 전체 |
| [`docs/voice_api.md`](docs/voice_api.md) | 음성 API (`/api/assistant/voice`): 요청·응답, 앱이 바꿀 것 |
| [`results/board_voice/report.md`](results/board_voice/report.md) | 보드 음성 검증: 녹음 5문장 인식·응답·시간, CPU·메모리 |
| [`docs/board_deploy.md`](docs/board_deploy.md) | 보드 배포: 구조, 켜고 끄기, 로그, 폰 연결(USB 테더링·공유기), 문제 해결 |
| [`results/rkllm_board/report.md`](results/rkllm_board/report.md) | 보드 LLM 검증: 431건 PC 대비, 함수별, 속도·메모리 |
| [`docs/rkllm_convert.md`](docs/rkllm_convert.md) | RKLLM W8A8 변환 절차 |
| [`docs/speech_stt_tts.md`](docs/speech_stt_tts.md) | 앱 음성(STT·TTS) 설계와 측정 |
| [`backend/README.md`](backend/README.md) | 백엔드 API·구조 |
| [`results/single_llm_report.md`](results/single_llm_report.md) | 단일 모델 구조 선택 근거 |
