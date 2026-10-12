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
│  ├─ services/delivery.py  배송 데이터 조회·변경
│  └─ db/                   연결, schema.sql, seed.py
└─ tests/test_api.py
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

- `category`: `tobacco`(담배류) · `ambient_drink`(상온 음료) · `chilled`(냉장 상품) · `ready_meal`(간편식)
- `type`: `파손` · `수량부족` · `오배송` · `온도이상`
- 배송지의 `status`는 `pending` / `done` 두 가지이고, 다음 배송지는 `is_next: true`로 표시됩니다.

## 앱에서 연결할 때

- 주소는 `http://<Orange Pi IP>:8000`. 에뮬레이터에서 PC의 서버에 붙을 때는 `http://10.0.2.2:8000`.
- `AndroidManifest.xml`에 `INTERNET` 권한이 필요하고, HTTPS가 아니므로 `android:usesCleartextTraffic="true"` 설정도 필요합니다.