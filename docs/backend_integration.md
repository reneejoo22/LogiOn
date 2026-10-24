# 음성 비서 ↔ 백엔드 연결 가이드

이 문서만 보고 붙일 수 있게 쓴 문서입니다. **AI 쪽에서 백엔드 코드는 한 줄도 고치지 않았습니다.** 아래 내용은 전부 제안이고, 구현 여부와 방식은 백엔드 담당자가 정하시면 됩니다.

- 이름·형식은 `backend/app/api/routes.py`, `backend/app/services/delivery.py`, `backend/app/db/schema.sql`, `backend/app/db/seed.py` 의 **실제 코드 그대로** 적었습니다.
- AI 쪽 설정은 `config/pipeline_v2_1.json` 한 파일에 모여 있습니다.
- 전체 구조 그림: [architecture.png](architecture.png) · 동작 확인용 노트북: [`notebooks/LogiOn_demo_pipeline.ipynb`](../notebooks/LogiOn_demo_pipeline.ipynb)

---

## 1. 음성 한 마디가 처리되는 순서

```
기사 말 (텍스트)
  → 의도분류 (6개 중 하나 + 확률)
  → 갈림길 ── margin 작음 → 선택지로 되묻기 (실행 안 함)
           ├─ scan/other 이고 확률 ≥ 0.9 → LLM 생략
           └─ 그 외 → LLM function calling (JSON 한 줄)
  → 값 보정 (DB 이름·단위 맞추기, 빈 값 되묻기)
  → 기존 API 호출
  → 응답 문장
```

AI 가 내놓는 것은 **함수 이름(fn) 하나와 값(JSON)** 입니다. 그 뒤는 백엔드가 기존 API 로 처리합니다.

---

## 2. fn → 기존 API 매핑

실제 코드와 대조해 확인했습니다. **아래 표는 현재 `routes.py` 와 일치합니다.**

| fn | 호출할 API | 보낼 것 | 받는 것 |
| --- | --- | --- | --- |
| `next_stop` | `GET /api/routes/today` | 없음 | `next_stop_id`, `summary.remaining`, `stops[]` |
| `stop_items` | `GET /api/stops/{stop_id}` | 없음 | `items[]` (`product_id`, `name`, `category`, `qty`, `unit`) |
| `complete` | `POST /api/stops/{stop_id}/complete` | `{"receiver": "점장님"}` (생략 가능) | 갱신된 배송지 전체 |
| `report_issue` | `POST /api/stops/{stop_id}/issues` | `{"type","product_id","qty","unit","source":"voice"}` | 생성된 이상 보고 (201) |
| `scan` | **DB 변경 없음** | — | 앱이 스캔 화면을 여는 신호만 |
| `other` | **아무 것도 안 함** | — | 거절 문구만 |

### 실제 코드와 달랐던 점 (중요)

1. **`report_issue` 의 키 이름이 `issue` 가 아니라 `type` 입니다.**
   AI 가 내놓는 JSON 은 `{"fn":"report_issue","issue":"파손", ...}` 인데, `IssueIn` 이 받는 필드는 `type` 입니다. 보내기 전에 **`issue` → `type` 으로 이름을 바꿔야 합니다.**
   값 자체는 같습니다: `파손 | 수량부족 | 오배송 | 온도이상` (`routes.py` 의 `Literal` 과 `schema.sql` 의 `CHECK` 가 같은 4개).

2. **`product_id` 는 숫자입니다. AI 는 품목 "이름"을 말합니다.**
   AI 출력은 `{"item":"우유"}` 인데 API 는 `product_id: int | None` 을 받습니다. 그래서 **이름 → `product_id` 변환이 선택이 아니라 필수**입니다. 방법은 3절에 있습니다.
   (`routes.py` 는 `product_id` 가 있으면 `delivery.product_exists` 로 검사하고 없으면 404 를 냅니다. 못 찾았으면 `product_id` 를 **빼고** 보내는 편이 낫습니다. `product_id` 는 nullable 이라 품목 없이도 이상 보고가 됩니다.)

3. **`qty` 는 0보다 커야 합니다** (`Field(gt=0)`). AI 가 0이나 음수를 낼 일은 없지만, 방어적으로 검사해 주세요.

4. **`unit` 은 `개 | 박스 | 판 | 봉지` 만 허용**됩니다 (`routes.py` 의 `Unit`, `schema.sql` 의 `CHECK`). AI 쪽도 같은 4개로 맞춰 둬서 (`snap_unit`) 그대로 보내면 됩니다.

5. **`qty` 없이 `unit` 만 보내면 백엔드가 `unit` 을 지웁니다.** `delivery.create_issue` 에 `if qty is None: unit = None` 이 있습니다. 반대로 **`qty` 만 있고 `unit` 이 없으면 백엔드가 `"개"` 를 넣습니다.** AI 쪽 `resolve()` 와 같은 규칙이라 결과는 같습니다.

6. **`stop_items` 는 전용 API 가 없고 배송지 상세에 들어 있습니다.** `GET /api/stops/{id}` 의 `items[]` 를 쓰면 되고, 특정 품목만 물었으면 그 안에서 골라내면 됩니다.

7. **이미 있는 로그 테이블을 쓰세요.** `schema.sql` 에 `utterance_logs` 가 이미 있고, 컬럼(`text`, `intent`, `intent_conf`, `llm_raw`, `resolved`, `reply`, `latency_ms`, `stop_id`, `created_at`)이 음성 처리 결과와 그대로 맞습니다. **새 테이블을 만들 필요가 없습니다.** 다만 이 테이블에 쓰는 코드는 아직 없습니다.

---

## 3. 값 보정을 DB 기준으로 하는 방법

AI 는 **기사가 말한 그대로** 내놓습니다 ("우유", "역삼점"). DB 이름과 맞추는 일은 백엔드에서 합니다.

### 3-1. 품목: `products` + `product_aliases`

`seed.py` 가 품목 20개와 별칭을 넣어 둡니다. 별칭은 **공백을 지운 형태**로 저장됩니다 (`aliases = {f.replace(" ", "") for f in forms}`).

```sql
-- 1단계: 별칭 정확히 일치 (말한 값의 공백을 지우고 비교)
SELECT p.id, p.name FROM product_aliases a JOIN products p ON p.id = a.product_id
WHERE a.alias = :spoken_nospace;

-- 2단계: 이름 정확히 일치
SELECT id, name FROM products WHERE REPLACE(name, ' ', '') = :spoken_nospace;

-- 3단계: 포함 (한쪽이 다른 쪽에 들어있음)
SELECT id, name FROM products WHERE REPLACE(name,' ','') LIKE '%' || :spoken_nospace || '%';
```

4단계로 발음 유사도(`difflib.SequenceMatcher`)를 쓰면 STT 오인식("바나나 우유" → "바나나 유유")을 어느 정도 받아 줍니다. AI 노트북의 `resolve()` 가 같은 순서(정확 → 별칭 → 포함 → 유사도)를 씁니다.

**후보가 여러 개면 실행하지 말고 되물으세요.** 예: "우유" → 서울우유·바나나우유·딸기우유 → `"서울우유, 바나나우유, 딸기우유 중 어떤 건가요?"`
(실제로 `seed.py` 의 별칭에서 `우유` → 서울우유, `삼각김밥` → 참치삼각김밥·스팸마요삼각김밥 처럼 겹치는 것이 있습니다.)

### 3-2. 점포: `stores(name, short_name)`

```sql
SELECT id, name, short_name FROM stores WHERE short_name = :spoken OR name LIKE '%' || :spoken || '%';
```

### 3-3. **학습 데이터 점포와 DB 점포가 다릅니다 (지금 상태로는 안 맞습니다)**

| | 점포 이름 |
| --- | --- |
| AI 학습 데이터 | 역삼점, 서초점, 방배점, 개포점, 신림점, 잠실점 … |
| `seed.py` 의 DB | **성수연무장점, 서울숲점, 뚝섬점** (`GS25 성수연무장점` / `CU 서울숲점` / `세븐일레븐 뚝섬점`) |

**그래서 기사가 "역삼점 뭐 내려" 라고 하면 DB 에서 그 점포를 찾지 못합니다.** 대응 방법은 세 가지입니다.

1. **(시연에 가장 쉬움) 점포를 말하지 않게 하거나, 못 찾으면 현재 배송지로 처리** — 아래 3-4 규칙을 그대로 쓰면 됩니다. 시연 시나리오를 "여기 뭐 내려", "납품 완료" 처럼 점포를 빼고 말하도록 짜면 문제가 없습니다.
2. **DB 점포 이름으로 말하기** — "서울숲점 콜라 몇 박스야" 는 지금도 잘 됩니다. AI 모델은 처음 보는 점포 이름도 `store` 값으로 잘 뽑아냅니다 (데모 노트북에 이 예시가 있습니다).
3. **맞추려면** — `seed.py` 의 `STORES` 를 학습 데이터 점포로 바꾸거나, 반대로 AI 쪽 `STORES` 목록을 DB 에 맞춰 다시 데이터를 만들고 재학습합니다. **후자는 재학습이 필요하니 1차 보고 뒤에 정하는 것이 좋겠습니다.**

> 못 찾았을 때 **지어내지 마세요.** 없는 점포면 "그 점포는 오늘 배송지에 없어요" 라고 답하는 편이 낫습니다.

### 3-4. 점포를 말하지 않았을 때

`store` 키가 없으면 **지금 있는 점포(= 다음 배송지)** 로 채웁니다.

```python
today = GET /api/routes/today
stop_id = today["next_stop_id"]          # 아직 안 끝난 곳 중 순서가 가장 빠른 곳
```

`delivery._next_stop_id` 가 `status='pending'` 중 `seq` 가 가장 작은 것을 고르므로, 완료 처리를 할수록 자동으로 다음 곳을 가리킵니다. `next_stop_id` 가 `None` 이면 오늘 배송이 다 끝난 것입니다.

### 3-5. 되묻기 상태를 세션별로 보관하기

되묻기는 두 종류입니다.

| 종류 | 언제 | 예 |
| --- | --- | --- |
| **값 되묻기** | 함수는 정해졌는데 값이 모자람 | "어떤 품목인가요?" / "서울우유, 바나나우유 중 어떤 건가요?" |
| **선택지 되묻기** | 어떤 기능인지 헷갈림 (margin < 0.05) | "남은 배송지 말씀하시는 건가요, 내릴 물건 말씀하시는 건가요?" |

둘 다 **직전 상태를 기억해야** 다음 말("서울우유", "배송지", "첫 번째")을 이어받을 수 있습니다. 한 기사만 쓰는 시연이라면 메모리 dict 로 충분합니다.

```python
# session_id -> 보류 중인 되묻기 (기한을 둬서 오래된 것은 버림)
PENDING: dict[str, dict] = {}
# 값 되묻기:    {"kind": "slot", "call": {...}, "missing": "item", "options": [...], "at": ts}
# 선택지 되묻기: {"kind": "choice", "text": 원래 문장, "options": ["next_stop", "stop_items"], "at": ts}
```

- 다음 말이 들어오면 **먼저 `PENDING` 과 맞춰 봅니다.** 선택지 되묻기면 "배송지/물건/문제/완료/스캔" 같은 말이나 "첫 번째/2번" 같은 순서 표현을 보고 고릅니다. 값 되묻기면 후보 목록과 맞춰 봅니다.
- 맞는 것이 없으면 **새로운 문장으로 보고 처음부터 처리**합니다 (기사가 마음을 바꾼 경우).
- 처리했으면 그 세션의 `PENDING` 을 지웁니다. 2~3분 지난 것은 버리는 편이 좋습니다.
- 서버를 여러 개 띄우면 메모리 dict 는 안 됩니다. 그때는 `utterance_logs` 나 Redis 같은 공용 저장소로 옮기세요. (시연은 1대이므로 메모리로 충분합니다.)

---

## 4. 추가 제안 API (구현은 백엔드 담당자가 판단)

앱이 매번 세 번 호출하지 않아도 되게, **음성 한 마디 = 요청 한 번** 으로 묶는 엔드포인트를 제안합니다.

```
POST /api/assistant/chat
```

### 요청

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `text` | `str` | 기사가 말한 문장 (STT 결과 또는 타이핑) |
| `session_id` | `str` | 되묻기 상태를 묶는 키. 앱이 만들어 계속 같은 값을 보냄 |

### 응답

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `reply` | `str` | 기사에게 읽어 줄 문장 (TTS 입력) |
| `fn` | `str` | `next_stop` / `stop_items` / `complete` / `report_issue` / `scan` / `other` |
| `call` | `dict` | AI 가 뽑은 값 (보정 후). 예: `{"item":"서울우유","type":"파손","qty":2,"unit":"개"}` |
| `route` | `str` | `skip`(LLM 생략) / `llm` / `ask`(선택지 되묻기) / `choice_answer`(되묻기 답 처리) |
| `ask` | `str \| null` | 되물을 때 질문 문장 (= `reply` 와 같음). 되묻지 않으면 `null` |
| `options` | `list[str] \| null` | 선택지. **있으면 앱이 버튼으로 보여 줌.** 없으면 `null` |
| `action` | `str \| null` | 앱이 할 일. `open_scanner` / `refresh_route` / `refresh_stop` / `null` |
| `stop_id` | `int \| null` | 이번에 다룬 배송지 |
| `conf` | `float` | 의도분류 1등 확률 |
| `latency_ms` | `int` | 서버 처리 시간 |

> `options` 가 있으면 **DB 를 바꾸지 않았다는 뜻**입니다. 앱은 버튼만 띄우고 기다리면 됩니다.

### 요청·응답 예시 5개

**(1) 일반 실행 — 바로 처리**

```json
// 요청
{"text": "다음 어디야", "session_id": "d1"}
// 응답
{"reply": "다음은 CU 서울숲점이에요. 남은 곳은 2곳이에요.",
 "fn": "next_stop", "call": {}, "route": "llm", "ask": null, "options": null,
 "action": "refresh_route", "stop_id": 2, "conf": 0.997, "latency_ms": 180}
```

**(2) 값 되묻기 — 품목이 여러 개라 실행 안 함**

```json
// 요청
{"text": "우유 두 개 터졌어", "session_id": "d1"}
// 응답
{"reply": "서울우유, 바나나우유, 딸기우유 중 어떤 건가요?",
 "fn": "report_issue", "call": {"type": "파손", "qty": 2, "unit": "개"},
 "route": "llm", "ask": "서울우유, 바나나우유, 딸기우유 중 어떤 건가요?",
 "options": ["서울우유", "바나나우유", "딸기우유"],
 "action": null, "stop_id": 1, "conf": 0.995, "latency_ms": 240}
```

**(3) 선택지 되묻기 — 어떤 기능인지 헷갈림**

```json
// 요청
{"text": "다음 거 알려줘", "session_id": "d1"}
// 응답
{"reply": "남은 배송지 말씀하시는 건가요, 내릴 물건 말씀하시는 건가요?",
 "fn": "next_stop", "call": {}, "route": "ask",
 "ask": "남은 배송지 말씀하시는 건가요, 내릴 물건 말씀하시는 건가요?",
 "options": ["남은 배송지", "내릴 물건"],
 "action": null, "stop_id": null, "conf": 0.52, "latency_ms": 12}
```

**(4) 되묻기 답 — (2) 에 이어서**

```json
// 요청
{"text": "서울우유", "session_id": "d1"}
// 응답  (여기서 POST /api/stops/1/issues 가 실제로 호출됨)
{"reply": "GS25 성수연무장점 서울우유 2개 파손으로 기록했어요.",
 "fn": "report_issue",
 "call": {"product_id": 1, "item": "서울우유", "type": "파손", "qty": 2, "unit": "개", "source": "voice"},
 "route": "choice_answer", "ask": null, "options": null,
 "action": "refresh_stop", "stop_id": 1, "conf": 0.995, "latency_ms": 8}
```

**(5) scan — DB 는 그대로, 앱만 화면을 엶**

```json
// 요청
{"text": "물건 확인할게요", "session_id": "d1"}
// 응답
{"reply": "스캔 화면을 열게요.", "fn": "scan", "call": {}, "route": "llm",
 "ask": null, "options": null, "action": "open_scanner",
 "stop_id": 1, "conf": 0.93, "latency_ms": 170}
```

> 스캔 뒤 바코드를 읽었으면 앱이 기존 `GET /api/products/barcode/{barcode}` 를 그대로 쓰면 됩니다.

---

## 5. 모델 올리는 방법

### 5-1. 설정 파일

`config/pipeline_v2_1.json` 한 개만 읽으면 됩니다.

| 키 | 지금 값 | 뜻 |
| --- | --- | --- |
| `intent_model` | `out/intent_model` | 의도분류 (PyTorch) |
| `intent_onnx` | `export/intent_onnx` | 의도분류 (ONNX, CPU 용·65MB) |
| `fc_model` | `out/fc_merged` | function calling (fp16, 약 2.9GB) |
| `system_prompt` | (문자열) | **이 문장을 바꾸면 재학습해야 합니다** |
| `ask_tau` | `0.05` | margin 이 이 값보다 작으면 선택지로 되묻기 |
| `skip_llm_conf` | `0.9` | 이 확률 이상이면 LLM 생략 |
| `skip_llm_fns` | `["scan","other"]` | 생략 대상 기능 |
| `generation` | `top_k=1`, `repetition_penalty=1.1` | 생성 설정 (평가와 같게 맞춰야 함) |

### 5-2. 서버 시작할 때 한 번만 올리기

모델 로딩은 수십 초 걸립니다. **요청마다 올리면 안 됩니다.** `main.py` 의 `lifespan` 에서 한 번 올리는 것이 가장 자연스럽습니다.

```python
# 제안 (구현은 백엔드 담당자 판단)
ASSISTANT = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); ...  # 지금 코드 그대로
    global ASSISTANT
    try:
        from app.assistant import Assistant      # 새로 만들 모듈
        ASSISTANT = Assistant("config/pipeline_v2_1.json")
    except Exception as e:
        ASSISTANT = None
        print("음성 비서 모델을 올리지 못했습니다. 음성 기능만 꺼집니다:", e)
    yield
```

- **GPU 가 있으면** `device_map={"": 0}`, fp16. LLM 1문장 약 0.2~1초.
- **CPU 만 있으면** LLM 은 매우 느립니다(수 초~수십 초). 의도분류만 ONNX 로 돌리고 LLM 은 끄거나, 보드에서는 RKLLM(W8A8) 로 바꿔야 합니다.
- 의도분류만 쓸 거라면 **ONNX 쪽이 가볍습니다**: `export/intent_onnx` + `onnxruntime`, `tokenizers` 만 있으면 되고 torch 가 필요 없습니다 (65MB, CPU 4스레드에서 약 2.9ms/문장).

### 5-3. 모델이 없을 때

모델 파일(`out/`)은 **용량 때문에 저장소에 없습니다.** 받으려면 `notebooks/LogiOn_AI_pipeline.ipynb` 를 돌려야 합니다 (GPU 필요, 약 40분).

모델이 없을 때는 **서버가 죽으면 안 됩니다.** 기존 화면 API 는 그대로 되어야 합니다.

```python
@router.post("/assistant/chat")
def assistant_chat(body: ChatIn):
    if ASSISTANT is None:
        raise HTTPException(status_code=503, detail="음성 비서 모델이 올라가 있지 않습니다.")
    ...
```

앱은 503 을 받으면 "음성 기능은 지금 쓸 수 없어요" 정도로 처리하면 됩니다.

### 5-4. 시연 구성

```
   휴대폰 (앱)  ──  같은 와이파이  ──  PC (백엔드 + 모델, GPU)
      http://<PC의 IP>:8000
```

1. PC 에서 서버를 **0.0.0.0 으로** 띄웁니다 (localhost 로 띄우면 휴대폰에서 안 붙습니다).
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. PC 의 IP 를 확인합니다: `ipconfig` → "IPv4 주소" (예: `192.168.0.12`).
3. **Windows 방화벽에서 8000 포트를 열어야 합니다.** 이걸 빼먹어서 안 되는 경우가 많습니다.
   ```powershell
   # 관리자 PowerShell에서 한 번만
   New-NetFirewallRule -DisplayName "LogiOn 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
   ```
4. 휴대폰 브라우저에서 `http://192.168.0.12:8000/api/health` 가 `{"status":"ok"}` 를 주면 성공입니다.
5. 앱 설정:
   - `AndroidManifest.xml` 에 `INTERNET` 권한
   - HTTPS 가 아니므로 `android:usesCleartextTraffic="true"`
   - 에뮬레이터에서 PC 에 붙을 때는 `http://10.0.2.2:8000`
6. 휴대폰과 PC 가 **같은 와이파이**여야 합니다. 학교 와이파이는 기기 간 통신을 막는 경우가 있으니, 안 되면 휴대폰 핫스팟에 PC 를 붙이는 쪽이 확실합니다.

---

## 6. 앱 채팅 탭이 쓸 응답 필드

| 필드 | 앱에서 할 일 |
| --- | --- |
| `reply` | 말풍선에 띄우고 TTS 로 읽기 |
| `options` | **`null` 이 아니면 버튼으로 보여 주기.** 누르면 그 글자를 그대로 `text` 로 다시 보냄 |
| `ask` | `null` 이 아니면 "답을 기다리는 중" 표시 (입력창에 포커스) |
| `action` | `open_scanner` → 스캔 화면 열기 / `refresh_route` → 운행 목록 새로고침 / `refresh_stop` → 배송지 상세 새로고침 |
| `fn`, `call` | 디버그 화면용. 평소에는 안 보여도 됩니다 |
| `conf`, `latency_ms` | 시연 때 "이만큼 빠르다"를 보여 줄 때만 |
| `stop_id` | 새로고침할 배송지 번호 |

### Kotlin 데이터 클래스 예시

```kotlin
data class ChatRequest(
    val text: String,
    val sessionId: String,
)

data class ChatResponse(
    val reply: String,
    val fn: String,
    val call: Map<String, Any?> = emptyMap(),
    val route: String,
    val ask: String? = null,
    val options: List<String>? = null,
    val action: String? = null,
    val stopId: Int? = null,
    val conf: Double = 0.0,
    val latencyMs: Int = 0,
)

interface AssistantApi {
    @POST("api/assistant/chat")
    suspend fun chat(@Body body: ChatRequest): ChatResponse
}
```

> JSON 키가 `session_id` · `stop_id` · `latency_ms` 처럼 밑줄이므로, Retrofit + Moshi/Gson 이면 `@Json(name = "session_id")` / `@SerializedName("session_id")` 를 붙이거나 변환기를 `LOWER_CASE_WITH_UNDERSCORES` 로 설정하세요.

화면 흐름:

```
기사 말 → POST /api/assistant/chat
  ├ options == null  → reply 를 말풍선에 + TTS, action 있으면 그 화면 처리
  └ options != null  → reply 를 말풍선에 + 버튼 N개 표시
                        버튼 누름 → 그 글자를 text 로 같은 session_id 로 다시 POST
```

---

## 7. 붙이기 전에 확인할 것

- [ ] `issue` → `type` 이름 바꾸기 (안 하면 422)
- [ ] 품목 이름 → `product_id` 변환, 못 찾으면 `product_id` 빼고 보내기 (안 하면 404)
- [ ] `source: "voice"` 넣기 (화면에서 들어온 것과 구분됨)
- [ ] `store` 가 없으면 `next_stop_id` 로 채우기
- [ ] 점포 이름이 DB 와 다른 문제(3-3) 를 어떻게 할지 정하기
- [ ] 되묻기 상태를 `session_id` 로 보관하고, 답을 받으면 지우기
- [ ] 모델이 없을 때 503 으로 내려주고 기존 화면 API 는 멀쩡히 돌아가는지
- [ ] `utterance_logs` 에 기록을 남길지 정하기 (테이블은 이미 있음)
