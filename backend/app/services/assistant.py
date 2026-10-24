"""음성 비서. POST /api/assistant/chat 이 쓰는 곳.

AI 파이프라인(demo/pipeline.py 의 Assistant)을 그대로 쓰고, 데이터 쪽만 바꿔 끼운다.
- 값 보정에 쓰는 점포·품목·오늘 배송지를 seed.py 복사본 대신 DB 에서 읽는다.
- 납품 완료·이상 보고는 메모리 대신 delivery.py 를 불러 실제 DB 를 바꾼다 (화면 API 와 같은 함수).
되묻기 상태는 session_id 별로 메모리에 둔다 (서버 1대 시연 기준).
"""
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from app.services import delivery

REPO_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_DIR / "demo"))
from pipeline import Assistant  # noqa: E402

log = logging.getLogger(__name__)

ISSUE_TYPES = ["파손", "수량부족", "오배송", "온도이상"]
PENDING_TTL = 180  # 초. 이보다 오래된 되묻기는 버린다

# 실행한 뒤 앱이 할 일
ACTIONS = {"next_stop": "refresh_route", "complete": "refresh_stop", "report_issue": "refresh_stop",
           "scan": "open_scanner"}


class DbAssistant(Assistant):
    def __init__(self, config_path=None, load_models=True):
        super().__init__(config_path, load_models)
        self.conn: sqlite3.Connection | None = None
        self.last_call = None
        self.sessions: dict[str, dict] = {}
        self.lock = threading.Lock()  # 모델 1개·되묻기 상태를 요청끼리 나눠 쓰므로 한 번에 하나씩

    # ---------------- 데이터: seed 대신 DB ----------------
    def load_db(self, conn: sqlite3.Connection) -> None:
        self.stores = [dict(r) for r in conn.execute("SELECT id, name, short_name FROM stores ORDER BY id")]
        aliases: dict[int, list[str]] = {}
        for r in conn.execute("SELECT product_id, alias FROM product_aliases"):
            aliases.setdefault(r["product_id"], []).append(r["alias"])
        self.products = [
            {"id": r["id"], "name": r["name"], "category": r["category"], "aliases": sorted(aliases.get(r["id"], []))}
            for r in conn.execute("SELECT id, name, category FROM products ORDER BY id")
        ]
        route = delivery.get_today_route(conn)
        self.stops = [delivery.get_stop(conn, s["id"]) for s in route["stops"]] if route else []

    def resolve(self, call, steps):
        call = dict(call)
        if call.get("qty") is not None:  # LLM 이 "2" 처럼 문자열로 줄 때가 있음. 0 이하는 버림 (IssueIn 과 같은 규칙)
            try:
                call["qty"] = int(call["qty"])
            except (TypeError, ValueError):
                call["qty"] = None
            if call["qty"] is not None and call["qty"] <= 0:
                call["qty"] = None
        out, ask, opts = super().resolve(call, steps)
        if not ask and out.get("fn") == "report_issue" and out.get("issue") not in ISSUE_TYPES:
            # DB CHECK 에 없는 값("터짐" 등)은 넣지 않고 되묻는다
            ask, opts = "어떤 문제인가요? 파손, 수량부족, 오배송, 온도이상 중에서 말씀해 주세요.", ISSUE_TYPES
        self.last_call = out
        return out, ask, opts

    def run_virtual(self, fn, call, req):
        """DB 를 바꾸는 기능만 delivery.py 로. 조회는 load_db 로 읽어 둔 DB 값을 그대로 쓴다."""
        stop = call.get("_stop")
        if fn == "complete":
            done = delivery.complete_stop(self.conn, stop["id"], call.get("receiver"))
            return {"store": done["store"]["name"], "receiver": done["receiver"]}
        if fn == "report_issue":
            b = req["body"]
            return delivery.create_issue(self.conn, stop["id"], b["type"], product_id=b.get("product_id"),
                                         qty=b.get("qty"), unit=b.get("unit"), source="voice")
        return super().run_virtual(fn, call, req)

    # ---------------- 요청 하나 ----------------
    def chat(self, conn: sqlite3.Connection, text: str, session_id: str) -> dict:
        with self.lock:
            now = time.time()
            for k in [k for k, s in self.sessions.items() if now - s["at"] > PENDING_TTL]:
                del self.sessions[k]
            sess = self.sessions.get(session_id, {})
            self.conn, self.pending, self.last_call = conn, dict(sess.get("pending", {})), None
            try:
                self.load_db(conn)
                trace = self.run(text)
            finally:
                self.conn = None
            # 값 되묻기의 답처럼 의도분류를 다시 안 돌린 경우는 직전 확률을 이어 쓴다
            conf = trace["intent"]["top3"][0]["p"] if trace.get("intent") else sess.get("conf", 0.0)
            if self.pending:
                self.sessions[session_id] = {"pending": self.pending, "at": now, "conf": conf}
            else:
                self.sessions.pop(session_id, None)
            resp = self._response(trace, conf)
        self._log(conn, text, trace, resp)
        return resp

    def _response(self, trace: dict, conf: float) -> dict:
        asked = trace.get("request") is None  # 되물을 때만 실행 요청이 없다
        fn = trace.get("fn") or (trace["intent"]["top3"][0]["fn"] if trace.get("intent") else None)
        last = self.last_call or {}
        call = {k: v for k, v in last.items() if k != "fn" and not k.startswith("_")}
        if "issue" in call:
            call["type"] = call.pop("issue")  # IssueIn 과 같은 이름으로
        if trace.get("carry"):
            route = "choice_answer"
        elif trace["route"] == "ask":
            route = "ask"
        else:
            route = trace["intent"]["route"]
        stop = last.get("_stop")
        return {
            "reply": trace["reply"],
            "fn": fn,
            "call": call,
            "route": route,
            "ask": trace["reply"] if asked else None,
            "options": trace.get("options") or None,
            "action": None if asked else ACTIONS.get(fn),
            "stop_id": stop["id"] if stop else None,
            "conf": round(conf, 4),
            "latency_ms": int(round(trace["timings"]["전체"])),
        }

    @staticmethod
    def _log(conn: sqlite3.Connection, text: str, trace: dict, resp: dict) -> None:
        conn.execute(
            "INSERT INTO utterance_logs (stop_id, text, intent, intent_conf, llm_raw, resolved, reply, latency_ms,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (resp["stop_id"], text, resp["fn"], resp["conf"], (trace.get("llm") or {}).get("raw"),
             json.dumps(resp["call"], ensure_ascii=False), resp["reply"], resp["latency_ms"],
             datetime.now().isoformat(timespec="seconds")),
        )


def load_assistant() -> tuple[DbAssistant | None, str | None]:
    """서버 시작 때 한 번 (모델 로딩은 수십 초). 못 올리면 (None, 이유): 음성 기능만 503, 화면 API 는 그대로."""
    if os.environ.get("LOGION_ASSISTANT", "1") == "0":
        return None, "LOGION_ASSISTANT=0 으로 꺼 두었습니다."
    try:
        bot = DbAssistant()
    except Exception as e:  # ModelsMissing, torch 미설치, GPU 메모리 부족 등
        log.warning("음성 비서 모델을 올리지 못했습니다. 음성 기능만 꺼집니다: %s", e)
        return None, str(e)
    log.warning("음성 비서 준비됨 (%s)", bot.device_name)
    return bot, None
