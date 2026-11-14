# 보드 단독 실행 (PC 없이 Orange Pi 5+ 하나로)

폰 앱(STT·TTS 는 폰 안에서) → **보드 백엔드 → 보드 파이프라인 → 보드 LLM 서버**. PC 와 인터넷 없이 돈다.

```
 ┌───────────── 폰 (Android 앱) ─────────────┐
 │  마이크 → STT(sherpa-onnx) → 텍스트          │
 │  응답 텍스트 → TTS → 스피커                   │
 └──────────────┬───────────────────────────┘
                │ HTTP  POST /api/assistant/chat  {"text": "...", "session_id": "..."}
                │ (USB 테더링 또는 공유기, 포트 8000)
 ┌──────────────▼──── Orange Pi 5+ (RK3588, 16GB) ─────────────────────────┐
 │  백엔드  FastAPI  0.0.0.0:8000   backend/app  (SQLite backend/data/logion.db) │
 │     └─ 파이프라인  demo/pipeline.py  (LOGION_LLM_BACKEND=rkllm, torch 없음)    │
 │          값 보정·되묻기·실행은 CPU, LLM 만 HTTP 로 ↓                           │
 │  LLM 서버  rkllm/server/logion_server.py  127.0.0.1:8090 (보드 안에서만)       │
 │     └─ ~/rkllm/logion/logion-delivery_w8a8_opt1_cal450.rkllm  (NPU, 1.7GB)    │
 └──────────────────────────────────────────────────────────────────────────┘
```

- system prompt 와 생성 설정(greedy, repetition_penalty 1.1, 최대 64 토큰)은 `config/pipeline_v3_single.json` 한 곳에서 읽는다. PC(GPU) 와 보드가 같은 값을 쓴다.
- PC 에서는 지금처럼 `LOGION_LLM_BACKEND` 를 안 주면 기존 local(GPU) 모드다.
- 보드 모델 정확도·속도 검증: [results/rkllm_board/report.md](../results/rkllm_board/report.md)

## 1. 처음 설치 (한 번)

```bash
ssh orangepi@<보드 IP>
cd ~/LogiOn
git fetch origin && git checkout board-llm      # (아직 GitHub 에 안 올렸으면 git bundle 로 받음)
bash scripts/board/setup_venv.sh                # ~/LogiOn/.venv-board 에 fastapi·uvicorn·pytest·httpx 만 (torch 없음)
```

- 보드 Ubuntu 22.04 에는 `python3.10-venv`(ensurepip) 가 없어서, `setup_venv.sh` 는 `python3 -m venv --without-pip` 로 만든 뒤 `get-pip.py` 로 **venv 안에만** pip 를 넣는다. sudo 불필요, 시스템 파이썬은 그대로.
  (sudo 가 되면 `sudo apt install python3.10-venv` 후 일반 venv 로 만들어도 된다.)
- 설치 때만 인터넷 필요. 실행 중에는 필요 없다.
- 보드에 실제 설치된 버전: `scripts/board/requirements-board.lock.txt` (Python 3.10 이라 PC 보다 starlette 가 한 단계 낮음. backend/tests 23개 통과 확인)
- 모델 파일은 레포에 없다. `~/rkllm/logion/` 에 아래 파일이 있어야 한다.

| 파일 | 크기 | md5 |
|---|---|---|
| logion-delivery_w8a8_opt1_cal450.rkllm | 2,038,770,100 B | 908a0eaacf137d6c7e5c2920fdb7e03d |
| demo_Linux_aarch64/lib/librkllmrt.so | 7.6 MB | 78d6d4094a64ee7659bbafde6b07c408 |

## 2. 켜고 끄기

```bash
cd ~/LogiOn
bash scripts/board/start_all.sh     # LLM 서버(모델 로딩 수 초) → 백엔드 순서, 백그라운드
bash scripts/board/stop_all.sh      # 둘 다 끄기 (pid 파일 기준)
```

정상이면 마지막 줄이 `백엔드 준비: {"ready":true,"device":"RK3588 NPU (rkllm, ...) model=logion-delivery_w8a8_opt1_cal450"...}`.

| 스크립트 | 하는 일 |
|---|---|
| `rkllm/server/start_llm.sh` | LLM 서버를 127.0.0.1:8090 으로 (포그라운드). 모델 경로는 `LOGION_RKLLM_MODEL`, 런타임은 `LOGION_RKLLM_LIB` 로 바꿀 수 있음 |
| `scripts/board/start_backend.sh` | 백엔드를 0.0.0.0:8000 으로 (포그라운드, `LOGION_LLM_BACKEND=rkllm`) |
| `scripts/board/start_all.sh` / `stop_all.sh` | 위 둘을 백그라운드로 켜고 끔 |
| `scripts/board/verify_board.py` | 함수 6개 요청 + 동시 요청 2개 확인 (표준 라이브러리만) |

로그: `~/LogiOn/logs/llm_server.log`, `~/LogiOn/logs/backend.log` (pid: `logs/llm.pid`, `logs/backend.pid`)

간단 확인:
```bash
curl -s localhost:8090/health                     # LLM 서버
curl -s localhost:8000/api/assistant/status       # 백엔드 + 파이프라인
curl -s -H 'Content-Type: application/json' -d '{"text":"다음 어디야","session_id":"t"}' localhost:8000/api/assistant/chat
```

### 재부팅 후 자동 실행 (systemd, sudo 필요 — 아직 설치 안 함)

서비스 파일만 레포에 있다: `scripts/board/systemd/logion-llm.service`, `logion-backend.service` (User=orangepi, 로그는 위와 같은 파일).
설치하려면 보드에서 (sudo 가능한 사람이):

```bash
sudo cp ~/LogiOn/scripts/board/systemd/logion-llm.service ~/LogiOn/scripts/board/systemd/logion-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now logion-llm.service logion-backend.service
systemctl status logion-llm logion-backend
```

systemd 로 돌릴 때는 `start_all.sh` 를 같이 쓰지 않는다 (포트가 겹침). 끄기: `sudo systemctl stop logion-backend logion-llm`.

## 3. 측정값 (2026-11-14, CPU/NPU 클럭 고정 없음)

보드 안에서 백엔드에 요청 (`results/rkllm_board/board_verify.json`):

| 함수 | 문장 | 응답 | 백엔드 ms |
|---|---|---|---|
| next_stop | 다음 어디야 | 다음은 GS25 성수연무장점이에요. 남은 곳은 3곳이에요. | 615 |
| stop_items | 서울숲점 내릴 거 알려줘 | CU 서울숲점 납품은 서울우유 6개, 참치삼각김밥 10개, 콜라 1박스예요. | 1098 |
| complete | 점장님한테 줬어 | GS25 성수연무장점 납품 완료로 기록했어요. 인수자는 점장님이에요. | 856 |
| report_issue | 서울숲점 콜라 두 박스 파손됐어 | CU 서울숲점 콜라 2박스 파손으로 기록했어요. | 2541 |
| scan | 바코드 찍을게 | 스캔 화면을 열게요. | 483 |
| other | 근처 화장실 어디야 | 죄송해요, 배송 업무만 도와드릴 수 있어요. | 484 |

- PC 에서 Tailscale(100.82.118.121:8000) 로 같은 요청: 6개 모두 같은 기능. 왕복 시간은 백엔드 처리 시간보다 20~45ms 더 걸림 (네트워크).
- 동시 요청 2개: 둘 다 HTTP 200. 두 번째는 첫 번째가 끝날 때까지 기다렸다가 처리 (1.0초 / 1.5초에 끝남). 백엔드가 요청을 한 번에 하나씩 처리하므로 busy 오류는 나지 않는다.
- LLM 서버를 끈 상태: `/api/assistant/chat` 이 HTTP 200 으로 `"잠시 후 다시 말씀해 주세요."` (action 없음) 를 바로 돌려줌. LLM 서버를 다시 켜면 백엔드 재시작 없이 정상 응답.
- 메모리: LLM 서버 RSS 약 1.7GB, 백엔드 약 46MB. 보드 전체 사용 437MB + 공유 1.7GB, 남은 메모리 13.6GB. 생성 중 CPU 약 130% (4코어 중), 전체 CPU 80% 유휴.
- 보드 LLM 정확도: test 431건에서 PC 원본과 같은 수준 (fn 0.896 vs 0.886, PC 와 출력 97.9% 일치).

## 4. 인터넷 없이 폰과 보드 연결

**보드(Orange Pi 5+)에는 Wi-Fi 가 없다.** 유선 이더넷 2개(`enP3p49s0`, `enP4p65s0`)와 USB 만 있다. 그래서 폰과는 USB 또는 공유기를 거쳐 연결한다.

### (a) 폰 USB 테더링 (공유기 없이 케이블 하나)

1. 폰과 보드를 USB 케이블로 연결 (보드의 USB-A 포트, 데이터 케이블).
2. 폰: 설정 → 연결 → 모바일 핫스팟 및 테더링 → **USB 테더링** 켜기. (모바일 데이터는 꺼도 됨. 인터넷이 없어도 폰-보드 사이 통신은 된다.)
3. 보드에 새 네트워크 장치(`usb0` 또는 `enx...`)가 생기고 NetworkManager 가 폰에서 IP 를 받는다. 보드에서 확인:
   ```bash
   ip -br addr                 # usb0 / enx... 줄의 IPv4 (예: 192.168.42.37/24, 기종마다 대역이 다름)
   ip route                    # 그 장치의 기본 게이트웨이 = 폰 주소
   nmcli device status         # 장치가 connected 인지
   ```
4. 앱의 서버 주소를 `http://<위에서 본 보드 IP>:8000/` 로 한다.

- 테더링을 다시 켤 때마다 보드 IP 가 바뀔 수 있다 → 앱에서 주소를 바꿀 수 있게 해 두는 것이 좋다 (아래 앱 팀 요청 1).
- 장치가 안 보이면 `dmesg | tail` 로 rndis/cdc 장치 인식 여부 확인. 자동으로 IP 를 못 받으면 `nmcli` 로 연결을 올리는 작업에 sudo 가 필요할 수 있다.
- 이 방식은 2026-11-14 기준 **아직 실기기로 시험하지 않았다**.

### (b) 소형 공유기 + 유선 (시연에 가장 안정적)

1. 공유기 LAN 포트 ↔ 보드 이더넷(`enP3p49s0`) 케이블 연결. 공유기의 인터넷(WAN) 연결은 없어도 된다.
2. 폰은 공유기 Wi-Fi 에 접속.
3. 공유기 관리 화면에서 보드 MAC `c0:74:2b:f2:3c:6a` 에 **고정 IP(DHCP 예약)** 를 걸어 두면 앱 주소가 바뀌지 않는다.
4. 보드 IP 확인: `ip -br addr show enP3p49s0` (현재 실험실 네트워크에서는 192.168.0.2).
5. 앱 서버 주소 `http://<보드 IP>:8000/`.

### 개발용 원격 접속: Tailscale

- 보드 Tailscale 주소 `100.82.118.121`. PC 에서 `ssh orangepi@100.82.118.121`, 백엔드 `http://100.82.118.121:8000/docs`.
- 인터넷이 있어야 하므로 현장 시연용이 아니라 개발용이다.
- LLM 서버(8090)는 127.0.0.1 에만 열려 있다. PC 에서 직접 보려면 SSH 터널: `ssh -N -L 18090:127.0.0.1:8090 orangepi@100.82.118.121` → PC 에서 `LOGION_LLM_BACKEND=rkllm LOGION_LLM_URL=http://127.0.0.1:18090 python demo/chat_server.py` 로 채팅 데모 화면을 보드 LLM 으로 돌릴 수 있다 (캡처: `results/rkllm_board/chat_demo_board/`).

## 5. 문제 해결

| 증상 | 확인 |
|---|---|
| `start_all.sh` 가 "LLM 서버가 90초 안에 뜨지 않음" | `logs/llm_server.log`. "파일 없음" 이면 `~/rkllm/logion/` 모델·라이브러리 경로. `rkllm init failed` 면 NPU 드라이버(`dmesg | grep -i rknpu`) |
| 음성 응답이 항상 "잠시 후 다시 말씀해 주세요." | LLM 서버가 꺼졌거나 8초 넘게 답이 없음: `curl localhost:8090/health`, `logs/llm_server.log` |
| `/api/assistant/status` 의 ready 가 false | `logs/backend.log` 의 "음성 비서 모델을 올리지 못했습니다" 다음 줄 |
| 앱에서 연결 안 됨 | 폰과 보드가 같은 네트워크인지, 보드에서 `ss -ltnp | grep 8000` 이 `0.0.0.0:8000` 인지, 앱 주소의 IP·포트 |
| 포트 사용 중 | 이전 프로세스: `bash scripts/board/stop_all.sh`, systemd 로도 켜 두었는지 `systemctl status logion-backend` |
| 시연 데이터 초기화 | 백엔드를 끄고 `backend/data/logion.db` 를 백업한 뒤 새 파일로 시작 (backend/README) |

## 6. 팀원에게 필요한 변경 (직접 고치지 않음)

### 앱 (android/)

1. **서버 주소** — `android/app/src/main/java/com/example/logion/data/remote/RetrofitClient.kt:14`
   `private const val BASE_URL = "http://10.0.2.2:8000/"` 는 에뮬레이터 → PC 주소다. 보드에 붙이려면 이 값을 보드 주소로 바꿔야 한다.
   - 공유기 방식: `http://<DHCP 예약한 보드 IP>:8000/`
   - USB 테더링: 연결할 때마다 바뀔 수 있음
   - 개발(Tailscale): `http://100.82.118.121:8000/` (폰에도 Tailscale 필요)
   → 상수 대신 **설정 화면이나 디버그 메뉴에서 주소를 입력해 SharedPreferences 에 저장**하고 Retrofit 을 그 값으로 만드는 방식을 권장 (빌드 변종 `BuildConfig` 필드로 나누는 것도 가능). 마지막 `/` 는 꼭 필요하다.
2. **평문 HTTP** — `AndroidManifest.xml` 에 `usesCleartextTraffic="true"` 가 이미 있어 그대로 된다.
3. **시간 제한** — 지금 Retrofit 은 OkHttp 기본값(읽기 10초)을 쓴다. 보드 응답은 최대 약 3초, LLM 이 막히면 백엔드가 8초 뒤 "잠시 후 다시 말씀해 주세요." 를 돌려주므로 기본값으로 충분하다. 바꿀 경우 10초 이상 유지.
4. **conf 값** — 보드(rkllm) 모드에서는 LLM 토큰 확률을 받지 않아 `conf` 가 항상 0.0 이다. 지금 앱은 `conf` 를 받기만 하고 쓰지 않으므로 문제 없음. 화면에 표시하거나 판단에 쓰지 말 것.

### 백엔드 (backend/) — 보드에서 돌리는 데 꼭 필요한 변경은 없음

backend/tests 23개가 보드(rkllm 모드)에서 그대로 통과한다. 아래는 권장 사항:

1. **`/api/assistant/status`** (`backend/app/api/assistant.py`) — 지금은 파이프라인 객체가 있으면 `ready: true` 라서 LLM 서버가 꺼져 있어도 true 다. `bot.llm_health()` (rkllm 모드일 때만 존재)를 불러 `llm_ok` 같은 값을 추가하면 앱이 음성 버튼 상태를 정확히 보여 줄 수 있다.
2. **위험한 납품 완료 오류** — 보드 test 431건 중 "이제 엄마한테 전화해주세요" 가 `complete(receiver=엄마)` 로 나온 1건이 있다 (PC 모델은 other). 음성 `complete` 는 실행 전 한 번 확인하거나, receiver 를 아는 값(점장님·직원·알바생·매니저 등)일 때만 바로 실행하는 규칙을 `DbAssistant.resolve()` 에 두는 것을 권장.
3. **README** — "음성 비서까지 켜기" 에 보드 방식(이 문서) 링크 추가.

### 보드 관리자 (sudo 필요, 선택)

- 자동 실행: 위 systemd 설치 명령
- `sudo apt install python3.10-venv` (없어도 setup_venv.sh 로 됨)
- `.local` 이름으로 찾고 싶으면 avahi-daemon 활성화 (지금 inactive). 그러면 앱 주소를 `http://orangepi5plus.local:8000/` 로 쓸 수 있으나 Android 의 mDNS 지원이 기종마다 달라 IP 방식이 더 확실하다.
- 정확한 속도 측정이 필요하면 rknn-llm 의 `fix_freq_rk3588.sh` 로 클럭 고정 (sudo)
