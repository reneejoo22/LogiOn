README
기기
orange pi + 모바일 앱
tts기능은 orangepi에 설치되서옴

해야할 작업 1
데이터를 앱에서 볼 수 이도록

---

## 구성

FastAPI + SQLite. DB 설계는 [DB_DESIGN.md](DB_DESIGN.md) 참고.

```
backend/
├─ app/
│  ├─ main.py               서버 시작 (테이블 생성 + 시연용 데이터 입력)
│  ├─ api/routes.py         REST API
│  ├─ api/assistant.py      음성 비서 API
│  ├─ services/delivery.py  배송 데이터 조회·변경
│  ├─ services/assistant.py 음성 비서 (AI 파이프라인 + DB)
│  └─ db/                   연결, schema.sql, seed.py
└─ tests/                  test_api.py, test_assistant.py
```

## 실행

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux(Orange Pi): source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 처음 켜면 `backend/data/logion.db`가 만들어지고 시연용 데이터(기사 1명, 점포 3곳, 품목 20개, 오늘 운행)가 들어갑니다.
- 서버를 켠 날짜에 운행이 없으면 그날 운행을 새로 만듭니다. 처음 상태로 되돌리려면 `data/logion.db`를 지우고 다시 켜면 됩니다.
- API 목록과 직접 호출: http://localhost:8000/docs
- 테스트: `python -m pytest`

### 음성 비서까지 켜기

위 `backend/.venv` 에는 torch 가 없어서 음성 API 가 503 이 됩니다. 음성 비서까지 쓰려면 **저장소 루트의 `.venv`**(루트 README 1단계)로 켭니다.

```powershell
cd LogiOn
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt     # 처음 한 번
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 모델 로딩에 수십 초 걸립니다. `GET /api/assistant/status` 가 `{"ready": true, "device": "<GPU 이름>"}` 이면 준비 완료입니다.
- 시험 DB 를 따로 쓰려면 `LOGION_DB` 환경변수에 파일 경로를 주세요 (기본 `backend/data/logion.db`).

## API

| 메서드 | 경로 | 내용 |
| --- | --- | --- |
| GET | `/api/health` | 서버 확인 |
| GET | `/api/driver` | 기사 정보 |
| GET | `/api/routes/today` | 오늘 운행: 요약(전체/완료/완료율), 다음 배송지, 배송지 목록 |
| GET | `/api/stops/{id}` | 배송지 상세: 구역별 박스·확인 여부, 품목, 이상 보고 |
| POST | `/api/stops/{id}/complete` | 배송 완료. 본문 `{"receiver": "점장님"}` (생략 가능) |
| DELETE | `/api/stops/{id}/complete` | 배송 완료 취소 |
| PATCH | `/api/stops/{id}/zones/{category}` | 구역 확인 체크. 본문 `{"checked": true}` |
| POST | `/api/stops/{id}/issues` | 이상 보고. 본문 `{"type": "파손", "product_id": 1, "qty": 2, "unit": "개"}` |
| GET | `/api/products/barcode/{barcode}` | 바코드로 품목 조회 |
| POST | `/api/assistant/chat` | 음성 비서. 본문 `{"text": "다음 어디야", "session_id": "d1"}`. 모델이 없으면 503 |
| GET | `/api/assistant/status` | 음성 비서 모델이 올라갔는지 (`ready`, 못 올렸으면 `error`) |

- `category`: `tobacco`(담배류) · `ambient_drink`(상온 음료) · `chilled`(냉장 상품) · `ready_meal`(간편식)
- `type`: `파손` · `수량부족` · `오배송` · `온도이상`
- 배송지의 `status`는 `pending` / `done` 두 가지이고, 다음 배송지는 `is_next: true`로 표시됩니다.

## 음성 비서 (`/api/assistant/chat`)

- AI 파이프라인(`demo/pipeline.py`)을 서버 시작 때 한 번 올려서 씁니다 (`app/services/assistant.py`). 점포·품목·배송지는 **DB 에서 읽고**, 납품 완료·이상 보고는 화면 API 와 같은 `delivery.py` 함수로 **DB 에 기록**합니다 (`source: "voice"`). 말한 문장은 `utterance_logs` 에 남습니다.
- 모델(`out/intent_model`, `out/fc_merged`)과 torch·transformers 가 필요합니다. 저장소 루트의 `requirements.txt` 환경(`.venv`)에 이 폴더의 `requirements.txt` 도 같이 설치해서 서버를 켜세요.
- 모델이 없으면 서버는 그대로 뜨고 음성 API 만 503 입니다. 모델을 일부러 안 올리려면 `LOGION_ASSISTANT=0` (테스트는 자동으로 꺼짐).
- 요청·응답 필드와 앱 쪽 처리 방법은 [`docs/backend_integration.md`](../docs/backend_integration.md) 4장·6장 그대로입니다.

## 앱에서 연결할 때

- 주소는 `http://<Orange Pi IP>:8000`. 에뮬레이터에서 PC의 서버에 붙을 때는 `http://10.0.2.2:8000`.
- `AndroidManifest.xml`에 `INTERNET` 권한이 필요하고, HTTPS가 아니므로 `android:usesCleartextTraffic="true"` 설정도 필요합니다.
- 앱 **AI 채팅 탭**(`screens/ChatScreen.kt`)이 `/api/assistant/chat` 을 씁니다.
  - 화면을 열 때 `/api/assistant/status` 로 모델 상태를 확인해 상단에 표시합니다.
  - `session_id` 는 화면마다 하나 만들어 보내므로 되묻기가 이어집니다. `options` 가 오면 버튼으로 보여 주고, 누르면 그 글자를 다시 보냅니다.
  - `action` 이 `refresh_route`·`refresh_stop` 이면 운행 목록을 다시 불러오고, `open_scanner` 이면 스캔 화면을 엽니다 (`LogiOnApp.kt`).