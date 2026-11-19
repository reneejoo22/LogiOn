"""음성 비서 API. 모델 대신 문장별로 정해 둔 의도분류·LLM 결과를 끼워 DB 연결 부분만 본다.

기본 fixture(client)는 단일 모델(config/pipeline_v3_single.json): 의도분류 없이 LLM 이 fn 까지 고른다.
client_v21 은 의도분류가 있는 예전 구조(config/pipeline_v2_1.json) 검사용이다.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
V3_SINGLE = CONFIG_DIR / "pipeline_v3_single.json"
V2_1 = CONFIG_DIR / "pipeline_v2_1.json"

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

# 단일 모델에서는 의도분류가 LLM 을 건너뛰게 해 주지 않으므로, 위에서 None 인 문장에도 LLM 출력이 필요하다
SINGLE_LLM = {
    "바코드 찍을게": '{"fn":"scan"}',
    "참치삼각김밥": '{"fn":"other"}',
    "네": '{"fn":"other"}',   # 되묻기 없이 '네' 만 말하면 업무 밖 말
}


def _make_client(config_path, tmp_path, monkeypatch, single):
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "test.db"))
    from app.main import app
    from app.services.assistant import DbAssistant

    with TestClient(app) as c:
        assert app.state.assistant is None  # conftest 에서 꺼 둠
        bot = DbAssistant(config_path=config_path, load_models=False)
        assert bot.use_intent is (not single)
        bot.llm_calls = []
        bot.classify = lambda text: SCRIPT[text][0]

        def call_llm(text):
            bot.llm_calls.append(text)
            out = SINGLE_LLM.get(text) if single else None
            return (out or SCRIPT[text][1]), 0.99, 0.9

        bot.call_llm = call_llm
        app.state.assistant = bot
        yield c


@pytest.fixture
def client(tmp_path, monkeypatch):
    yield from _make_client(V3_SINGLE, tmp_path, monkeypatch, single=True)


@pytest.fixture
def client_v21(tmp_path, monkeypatch):
    yield from _make_client(V2_1, tmp_path, monkeypatch, single=False)


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
    assert r["reply"] == "GS25 성수연무장점 납품 완료할까요?"  # 바로 기록하지 않고 되묻는다
    assert (r["route"], r["action"], r["ask"], r["options"]) == ("confirm_ask", None, r["reply"], ["네", "아니요"])
    assert client.get("/api/stops/1").json()["status"] == "pending"

    r = say(client, "네")
    assert r["reply"] == "GS25 성수연무장점 납품 완료로 기록했어요. 인수자는 점장님이에요."
    assert (r["route"], r["action"], r["stop_id"], r["ask"]) == ("confirm_yes", "refresh_stop", 1, None)
    assert r["call"]["receiver"] == "점장님"

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


def test_choice_question_then_answer(client_v21):
    client = client_v21  # margin 되묻기는 의도분류가 있는 구조에만 있다
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


def test_scan_skips_llm(client_v21):
    r = say(client_v21, "바코드 찍을게")
    assert (r["route"], r["action"]) == ("skip", "open_scanner")
    assert client_v21.app.state.assistant.llm_calls == []


def test_default_config_is_single_model(monkeypatch):
    monkeypatch.delenv("LOGION_PIPELINE_CONFIG", raising=False)
    from app.services.assistant import DbAssistant

    assert DbAssistant(load_models=False).use_intent is False


def test_single_scan_goes_through_llm(client):
    r = say(client, "바코드 찍을게")
    assert (r["fn"], r["route"], r["action"]) == ("scan", "llm", "open_scanner")
    assert client.app.state.assistant.llm_calls == ["바코드 찍을게"]


def test_single_valueless_command_goes_through_llm(client):
    r = say(client, "다음 어디야")
    assert (r["fn"], r["route"], r["action"]) == ("next_stop", "llm", "refresh_route")
    assert client.app.state.assistant.llm_calls == ["다음 어디야"]
    assert r["reply"] == "다음은 GS25 성수연무장점이에요. 남은 곳은 3곳이에요."


# ---------------- 11/20: 납품 완료 되묻기, 단위 규칙, STT 오인식 별칭 ----------------
@pytest.mark.parametrize("answer", ["응", "네.", "어", "맞아", "어 맞아", "네 맞아요", "응 해줘"])
def test_complete_confirm_yes_words(client, answer):
    say(client, "납품 완료 점장님이 받았어")
    r = say(client, answer)
    assert r["route"] == "confirm_yes" and "기록했어요" in r["reply"]
    assert client.get("/api/stops/1").json()["status"] == "done"
    assert client.app.state.assistant.llm_calls == ["납품 완료 점장님이 받았어"]  # 답은 LLM 에 안 보냄


@pytest.mark.parametrize("answer", ["아니", "아니요", "아니 잠깐만"])
def test_complete_confirm_no_cancels(client, answer):
    say(client, "납품 완료 점장님이 받았어")
    r = say(client, answer)
    assert r["route"] == "confirm_no" and r["reply"] == "알겠어요. 납품 완료는 기록하지 않았어요."
    assert (r["action"], r["ask"]) == (None, None)
    assert client.get("/api/stops/1").json()["status"] == "pending"
    assert say(client, "네")["route"] != "confirm_yes"  # 취소한 뒤의 '네' 는 아무것도 완료하지 않음


def test_complete_confirm_other_speech_drops_question(client):
    """'어디야' 는 '어' 로 시작해도 '예' 가 아니다. 다른 말이면 되묻기는 버리고 그 말을 새로 처리한다."""
    bot = client.app.state.assistant
    say(client, "납품 완료 점장님이 받았어")
    real = bot.call_llm
    bot.call_llm = lambda text: ('{"fn":"next_stop"}', 0.99, 0.9) if text == "어디야" else real(text)
    r = say(client, "어디야")
    assert r["fn"] == "next_stop" and r["reply"].startswith("다음은 GS25 성수연무장점")
    assert client.get("/api/stops/1").json()["status"] == "pending"
    assert say(client, "네")["route"] != "confirm_yes"


def test_yes_no_matcher():
    from pipeline import match_yes_no
    assert [match_yes_no(t) for t in ["응.", "넵", "예", "어 맞아요", "그래 해줘"]] == ["yes"] * 5
    assert [match_yes_no(t) for t in ["아니", "아뇨", "취소해", "아니 다시"]] == ["no"] * 4
    assert [match_yes_no(t) for t in ["어디야", "네 개 터졌어", "응급", "", "우유"]] == [None] * 5


@pytest.mark.parametrize("text,unit", [("우유 두 박스 터졌어", "박스"), ("새우깡 세 봉지 모자라", "봉지"),
                                       ("계란 한 판 깨졌어", "판"), ("우유 2개 터졌어", "개")])
def test_issue_unit_from_sentence_when_llm_leaves_it_empty(client, text, unit):
    bot = client.app.state.assistant
    bot.call_llm = lambda t: ('{"fn":"report_issue","item":"우유","issue":"파손","qty":2}', 0.99, 0.9)
    r = say(client, text)
    assert r["call"]["unit"] == unit and r["call"]["qty"] == 2
    assert client.get("/api/stops/1").json()["issues"][0]["unit"] == unit


def test_issue_unit_kept_when_llm_gives_it(client):
    bot = client.app.state.assistant
    bot.call_llm = lambda t: ('{"fn":"report_issue","item":"우유","issue":"파손","qty":2,"unit":"개"}', 0.99, 0.9)
    assert say(client, "우유 두 박스 터졌어")["call"]["unit"] == "개"  # LLM 이 채운 값은 그대로


def test_stt_aliases_fix_text_before_llm(client):
    bot = client.app.state.assistant
    seen = []
    bot.call_llm = lambda t: (seen.append(t) or '{"fn":"complete","store":"성수연무장점","receiver":"점장님"}', 0.99, 0.9)
    r = say(client, "성수연 장점 납품 완료 정자님한테 넘겼어")
    assert seen == ["성수연무장점 납품 완료 점장님한테 넘겼어"]
    assert r["text_fixed"] == "성수연무장점 납품 완료 점장님한테 넘겼어"
    say(client, "성수연무 장점 정자님")
    assert seen[-1] == "성수연무장점 점장님"
    assert say(client, "다음 어디야")["text_fixed"] is None  # 안 바뀌면 None
