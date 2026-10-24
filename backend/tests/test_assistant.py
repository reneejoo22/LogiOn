"""음성 비서 API. 모델 대신 문장별로 정해 둔 의도분류·LLM 결과를 끼워 DB 연결 부분만 본다."""
import pytest
from fastapi.testclient import TestClient

# 문장: (의도분류 순위, LLM 출력)
SCRIPT = {
    "다음 어디야": ([("next_stop", 0.99), ("stop_items", 0.01)], '{"fn":"next_stop"}'),
    "여기 뭐 내려": ([("stop_items", 0.98), ("next_stop", 0.02)], '{"fn":"stop_items"}'),
    "납품 완료 점장님이 받았어": ([("complete", 0.99), ("report_issue", 0.01)],
                          '{"fn":"complete","receiver":"점장님"}'),
    "서울숲점 콜라 몇 박스야": ([("stop_items", 0.97), ("next_stop", 0.03)],
                        '{"fn":"stop_items","store":"서울숲점","item":"콜라"}'),
    "역삼점 뭐 내려": ([("stop_items", 0.97), ("next_stop", 0.03)], '{"fn":"stop_items","store":"역삼점"}'),
    "삼각김밥 두 개 터졌어": ([("report_issue", 0.99), ("complete", 0.01)],
                      '{"fn":"report_issue","item":"삼각김밥","issue":"파손","qty":"2","unit":"개"}'),
    "우유가 이상해": ([("report_issue", 0.99), ("complete", 0.01)],
                '{"fn":"report_issue","item":"우유","issue":"이상함"}'),
    "다음 거 알려줘": ([("next_stop", 0.51), ("stop_items", 0.49)], '{"fn":"next_stop"}'),
    "바코드 찍을게": ([("scan", 0.97), ("other", 0.03)], None),
    "참치삼각김밥": ([("other", 0.95), ("stop_items", 0.05)], None),
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "test.db"))
    from app.main import app
    from app.services.assistant import DbAssistant

    with TestClient(app) as c:
        assert app.state.assistant is None  # conftest 에서 꺼 둠
        bot = DbAssistant(load_models=False)
        bot.llm_calls = []
        bot.classify = lambda text: SCRIPT[text][0]

        def call_llm(text):
            bot.llm_calls.append(text)
            return SCRIPT[text][1], 0.99, 0.9

        bot.call_llm = call_llm
        app.state.assistant = bot
        yield c


def say(client, text, session_id="d1"):
    r = client.post("/api/assistant/chat", json={"text": text, "session_id": session_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_no_models_gives_503_and_screens_still_work(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        assert c.post("/api/assistant/chat", json={"text": "다음 어디야"}).status_code == 503
        assert c.get("/api/assistant/status").json()["ready"] is False
        assert c.get("/api/routes/today").status_code == 200


def test_next_stop_reads_db(client):
    r = say(client, "다음 어디야")
    assert r["reply"] == "다음은 GS25 성수연무장점이에요. 남은 곳은 3곳이에요."
    assert (r["fn"], r["route"], r["action"], r["ask"], r["options"]) == ("next_stop", "llm", "refresh_route", None, None)

    client.post("/api/stops/1/complete")  # 화면에서 완료하면 음성 답도 바로 바뀐다
    assert say(client, "다음 어디야")["reply"] == "다음은 CU 서울숲점이에요. 남은 곳은 2곳이에요."


def test_stop_items_with_store_and_item(client):
    r = say(client, "서울숲점 콜라 몇 박스야")
    assert r["reply"] == "CU 서울숲점 콜라는 1박스예요."
    assert r["stop_id"] == 2 and r["action"] is None


def test_unknown_store_is_not_made_up(client):
    r = say(client, "역삼점 뭐 내려")
    assert r["route"] == "llm" and r["ask"] == r["reply"]
    assert "찾지 못했어요" in r["reply"]


def test_complete_writes_db(client):
    r = say(client, "납품 완료 점장님이 받았어")
    assert r["reply"] == "GS25 성수연무장점 납품 완료로 기록했어요. 인수자는 점장님이에요."
    assert (r["action"], r["stop_id"]) == ("refresh_stop", 1)

    stop = client.get("/api/stops/1").json()
    assert stop["status"] == "done" and stop["receiver"] == "점장님"
    assert client.get("/api/routes/today").json()["next_stop_id"] == 2
    assert say(client, "여기 뭐 내려")["stop_id"] == 2  # 점포를 말 안 하면 다음 배송지


def test_issue_asks_item_then_writes_db(client):
    r = say(client, "삼각김밥 두 개 터졌어")
    assert r["options"] == ["참치삼각김밥", "스팸마요삼각김밥"] and r["action"] is None
    assert client.get("/api/stops/1").json()["issues"] == []  # 되묻는 동안은 DB 그대로

    r = say(client, "참치삼각김밥")
    assert r["route"] == "choice_answer" and r["conf"] == 0.99
    assert r["reply"] == "GS25 성수연무장점 참치삼각김밥 2개 파손으로 기록했어요."
    assert r["call"]["type"] == "파손" and r["call"]["qty"] == 2

    [issue] = client.get("/api/stops/1").json()["issues"]
    assert (issue["product_name"], issue["type"], issue["qty"], issue["unit"], issue["source"]) == (
        "참치삼각김밥", "파손", 2, "개", "voice")


def test_issue_type_outside_db_is_asked(client):
    r = say(client, "우유가 이상해")
    assert r["options"] == ["파손", "수량부족", "오배송", "온도이상"]
    r = say(client, "온도이상")
    assert r["reply"] == "GS25 성수연무장점 서울우유 온도이상으로 기록했어요."
    assert client.get("/api/stops/1").json()["issues"][0]["type"] == "온도이상"


def test_choice_question_then_answer(client):
    r = say(client, "다음 거 알려줘")
    assert r["route"] == "ask" and r["options"] == ["남은 배송지", "내릴 물건"]
    r = say(client, "내릴 물건")
    assert r["route"] == "choice_answer" and r["fn"] == "stop_items"
    assert r["reply"].startswith("GS25 성수연무장점 납품은 서울우유 12개")


def test_sessions_are_separate(client):
    say(client, "삼각김밥 두 개 터졌어", session_id="a")
    r = say(client, "참치삼각김밥", session_id="b")  # b 는 되묻기를 받은 적이 없음
    assert r["route"] != "choice_answer"
    assert client.get("/api/stops/1").json()["issues"] == []


def test_scan_skips_llm(client):
    r = say(client, "바코드 찍을게")
    assert (r["route"], r["action"]) == ("skip", "open_scanner")
    assert client.app.state.assistant.llm_calls == []
