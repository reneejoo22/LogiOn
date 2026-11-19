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

### 구조: 폰 = 화면·마이크·스피커, 보드 = STT·Qwen·TTS·백엔드·DB

| 기기 | 맡는 일 |
| --- | --- |
| **폰** (Android 앱, 58MB) | 화면 · 마이크(16kHz wav 녹음) · 스피커(응답 음성 재생). 모델 없음 |
| **보드** (Orange Pi 5 Plus, RK3588 16GB) | STT(SenseVoice) · Qwen2.5-1.5B+LoRA(NPU) · TTS(VITS) · 백엔드(FastAPI) · DB(SQLite) |

```
 폰 (Android 앱)                         Orange Pi 5 Plus (RK3588, 16GB)
 ┌──────────────────┐  POST /api/assistant/voice   ┌─────────────────────────────────────────────┐
 │ 🎤 녹음 16kHz wav │ ───────────────────────────▶ │ ① VAD 앞뒤 무음 제거 · STT SenseVoice  (CPU 4) │
 │                  │                              │    → STT 오인식 별칭 ("정자님" → "점장님")      │
 │ 화면: 인식 글자·답 │ ◀──── JSON (text, reply, …) ── │ ② Qwen 기능·값 뽑기                  (NPU)    │
 │                  │                              │    → DB 이름 보정·되묻기 → 조회·기록 (SQLite)  │
 │ 🔊 응답 음성 재생  │ ◀──── GET audio_url (wav) ──── │ ③ 답 문장 → TTS VITS 한국어          (CPU 2) │
 └──────────────────┘   (USB 테더링, 포트 8000)        └─────────────────────────────────────────────┘
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
| `complete` | "점장님한테 넘겼어" | "○○ 납품 완료할까요?" 로 한 번 확인한 뒤 기록 (인수자 포함) |
| `report_issue` | "우유 두 개 터졌어" | 파손·수량부족·오배송·온도이상 기록 (품목이 모호하면 되묻기) |
| `scan` | "바코드 찍을게" | 스캔 화면 열기 |
| `other` | "근처 화장실 어디야" | 업무 밖 요청은 정중히 거절 |

LLM 은 "기능을 고르고 말한 값을 JSON 으로 옮기는 일"만 하고, DB 이름 맞추기·되묻기는 규칙 코드가 맡아 없는 값을 지어내지 않습니다.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| 앱 (폰) | Kotlin, Jetpack Compose, Retrofit/OkHttp · AudioRecord 녹음(16kHz wav, 말 끝 자동 종료) 업로드, MediaPlayer 응답 음성 재생 |
| 백엔드 (보드) | Python 3.10, FastAPI, SQLite, uvicorn |
| 음성 (보드 CPU) | sherpa-onnx 1.13.8: silero VAD, SenseVoice-Small int8 STT (4스레드), 한국어 VITS TTS (2스레드) |
| AI 모델 | Qwen2.5-1.5B-Instruct + LoRA (function calling), PyTorch·transformers·peft 로 학습 |
| 보드 추론 | Orange Pi 5 Plus (RK3588), RKLLM 1.3.0 W8A8 변환, NPU 추론 서버 (`rkllm/server/`) |

## 폴더 구조

```
LogiOn/
├─ android/        Android 앱 (화면, 녹음·재생, AI 채팅 탭, 더보기의 보드 주소 설정)
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

## 실행 방법 (시연)

순서: **보드 켜기 → (자동 실행) → 폰 USB 테더링 → 앱 설정에 보드 주소 입력 → 시연 문장 5개**.
처음 한 번 설치는 [`docs/board_deploy.md`](docs/board_deploy.md) 1절, 자동 실행(systemd) 설치는 같은 문서 2절의 블록을 보드에서 붙여 넣으면 됩니다.

### 1. 보드 켜기

Orange Pi 5 Plus 에 전원을 넣습니다.

### 2. 자동 실행 (기다리기만)

부팅하면 systemd 가 LLM 서버(:8090, NPU) → 백엔드(:8000, STT·TTS 포함)를 켭니다. 1분쯤 기다립니다.

- 백엔드는 켜질 때 그날 운행이 없으면 새로 만듭니다. 시연 날 켜면 완료 0/3 으로 시작합니다.
- 확인 (보드에서): `curl -s localhost:8000/api/assistant/status` → `"ready":true`, `"voice_ready":true`.
- systemd 를 아직 설치하지 않았다면 직접 켭니다: `cd ~/LogiOn && bash scripts/board/start_all.sh` (끄기 `stop_all.sh`).

### 3. 폰 USB 테더링

1. 폰과 보드를 USB 데이터 케이블로 연결합니다 (보드 USB-A 포트).
2. 폰: 설정 → 연결 → 모바일 핫스팟 및 테더링 → **USB 테더링** 켜기. 모바일 데이터는 꺼도 됩니다.
3. 보드 주소를 확인합니다. 보드 화면이나 SSH 에서 `hostname -I` (또는 `ip -br addr` 의 `usb0`/`enx…` 줄).

### 4. 앱 설정에 보드 주소 입력

1. 폰에 `LogiOn_board.apk` 를 설치합니다 (또는 Android Studio 로 `android/` 실행).
2. 앱 **더보기 → 보드 주소(서버)** 에 위에서 본 주소를 넣고 **저장** 합니다. 예: `192.168.42.37` (포트를 안 쓰면 8000).
3. 아래에 초록색 "연결됨 · RK3588 NPU … · 음성 준비됨" 이 보이면 됩니다. 테더링을 다시 켜면 주소가 바뀔 수 있으니 그때 다시 넣습니다.

### 5. 시연 문장

**채팅** 탭이나 아래 음성 카드의 🎤 를 누르고 말합니다. 말이 끝나고 1초 조용하면 자동으로 보내고, 버튼을 다시 눌러도 됩니다. 아래 응답은 보드 실측(2026-11-20, 같은 녹음)입니다.

| # | 말하기 | 응답 | 화면 변화 |
| --- | --- | --- | --- |
| 1 | "다음 어디야" | 다음은 GS25 성수연무장점이에요. 남은 곳은 3곳이에요. | — |
| 2 | "서울숲점 콜라 몇 박스야" | CU 서울숲점 콜라는 1박스예요. | — |
| 3 | "우유 두 개 터졌어" | GS25 성수연무장점 서울우유 2개 파손으로 기록했어요. | 배송지 상세에 이상 보고 |
| 4 | "성수연무장점 납품 완료, 점장님한테 넘겼어" → **"네 맞아요"** | GS25 성수연무장점 납품 완료할까요? → GS25 성수연무장점 납품 완료로 기록했어요. 인수자는 점장님이에요. | 배송목록 완료 1 |
| 5 | "근처 화장실 어디야" | 죄송해요, 배송 업무만 도와드릴 수 있어요. | — |

- 4번은 확인 질문에 "아니" 라고 하면 기록하지 않습니다. 한 음절 "네" 는 짧아서 놓칠 수 있으니 "네 맞아요" 처럼 말합니다.
- 4번 녹음은 STT 가 "성수연무 장점 … 정자님" 으로 듣지만, 보드의 STT 오인식 별칭 표([`config/stt_aliases.json`](config/stt_aliases.json))가 "성수연무장점 … 점장님" 으로 고칩니다.
- 3·4번은 DB 에 실제로 기록됩니다. 연습한 뒤 시연 전에 새 하루로 되돌리려면 보드에서 `bash ~/LogiOn/scripts/board/reset_demo_db.sh` (지금 DB 는 `logs/db_backup_<시각>/` 로 옮겨 둡니다).

PC 에서 음성 API 를 바로 확인할 수도 있습니다 (wav 16kHz mono).

```bash
curl -s -F file=@다음어디야.wav -F session_id=demo http://<보드 IP>:8000/api/assistant/voice
# → {"text":"다음 어디야?","reply":"다음은 GS25 성수연무장점이에요. …","audio_url":"/api/assistant/voice/audio/…", …}
```

### 다른 실행 방법

| 방법 | 요약 | 자세히 |
| --- | --- | --- |
| PC GPU 실행 | `.venv` 에 CUDA torch + `requirements.txt` → `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000` (STT·TTS 모델은 `python speech/download_models.py --no-android`) | [`docs/ai_details.md` 실행 방법](docs/ai_details.md#실행-방법) |
| 개발용 원격 (Tailscale) | 앱 더보기의 보드 주소를 `100.82.118.121` 로 (폰·PC 에 Tailscale 필요). 에뮬레이터는 `adb emu avd hostmicon` 으로 PC 마이크 | [`docs/board_deploy.md`](docs/board_deploy.md) 4절 |
| 앱 안 STT·TTS (예전 구조, 지금 앱에서 뺌) | 11-17 시연 때 구조. 모델·AAR 은 `android/unused_on_device_speech/` 에 옮겨 둠 | [`docs/speech_stt_tts.md`](docs/speech_stt_tts.md) |

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
| [`docs/voice_api.md`](docs/voice_api.md) | 음성 API (`/api/assistant/voice`, `/tts`): 요청·응답, 납품 완료 되묻기, 앱 반영 내용 |
| [`results/board_voice/report.md`](results/board_voice/report.md) | 보드 음성 검증: 녹음 5문장 인식·응답·시간, CPU·메모리 |
| [`docs/board_deploy.md`](docs/board_deploy.md) | 보드 배포: 구조, 켜고 끄기, **자동 실행(systemd) 설치 블록**, 시연 DB 초기화, 폰 연결(USB 테더링·공유기), 문제 해결 |
| [`results/rkllm_board/report.md`](results/rkllm_board/report.md) | 보드 LLM 검증: 431건 PC 대비, 함수별, 속도·메모리 |
| [`docs/rkllm_convert.md`](docs/rkllm_convert.md) | RKLLM W8A8 변환 절차 |
| [`docs/speech_stt_tts.md`](docs/speech_stt_tts.md) | 앱 음성(STT·TTS) 설계와 측정 |
| [`backend/README.md`](backend/README.md) | 백엔드 API·구조 |
| [`results/single_llm_report.md`](results/single_llm_report.md) | 단일 모델 구조 선택 근거 |
