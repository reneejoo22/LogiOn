"""보드 LLM 모드(LOGION_LLM_BACKEND=rkllm) 테스트. 가짜 LLM 서버(표준 라이브러리)를 띄워서 확인한다.

  python -m pytest demo/tests -q          (저장소 루트에서. torch 없이도 돈다)
"""
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
CFG = json.loads((ROOT / "config/pipeline_v3_single.json").read_text(encoding="utf-8"))


class FakeLLM:
    """mode: ok | slow | busy | broken"""

    def __init__(self, replies, mode="ok"):
        self.replies, self.mode, self.requests = replies, mode, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, obj):
                data = json.dumps(obj, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._json(200, {"status": "ok", "model": "fake"})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                if outer.mode == "slow":
                    time.sleep(1.5)
                if outer.mode == "busy":
                    return self._json(503, {"error": "busy"})
                if outer.mode == "broken":
                    data = b"not json"
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                user = body["messages"][-1]["content"]
                self._json(200, {"choices": [{"message": {"content": outer.replies.get(user, '{"fn":"other"}')}}],
                                 "error": False})

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


@pytest.fixture
def fake():
    servers = []

    def make(replies=None, mode="ok"):
        s = FakeLLM(replies or {}, mode)
        servers.append(s)
        return s

    yield make
    for s in servers:
        s.close()


def bot_for(monkeypatch, url, timeout="1"):
    monkeypatch.setenv("LOGION_LLM_BACKEND", "rkllm")
    monkeypatch.setenv("LOGION_LLM_URL", url)
    monkeypatch.setenv("LOGION_LLM_TIMEOUT", timeout)
    from pipeline import Assistant
    return Assistant()


def test_default_backend_is_local(monkeypatch):
    monkeypatch.delenv("LOGION_LLM_BACKEND", raising=False)
    from pipeline import Assistant
    assert Assistant(load_models=False).llm_backend == "local"


def test_rkllm_mode_does_not_import_torch(fake):
    s = fake({"다음 어디야": '{"fn":"next_stop"}'})
    code = ("import sys, os; sys.path.insert(0, r'%s');"
            "os.environ.update(LOGION_LLM_BACKEND='rkllm', LOGION_LLM_URL='%s');"
            "from pipeline import Assistant; b = Assistant(); r = b.run('다음 어디야');"
            "assert r['fn'] == 'next_stop', r;"
            "bad = [m for m in ('torch', 'transformers', 'numpy') if m in sys.modules];"
            "assert not bad, bad; print('ok')") % (ROOT / "demo", s.url)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_request_uses_config_prompt_and_generation(fake, monkeypatch):
    s = fake({"반포점 리스트 불러줘": '{"fn":"stop_items","store":"반포점"}'})
    bot = bot_for(monkeypatch, s.url)
    assert bot.models_loaded and bot.device == "rkllm"
    r = bot.run("반포점 리스트 불러줘")
    assert r["fn"] == "stop_items" and "반포점" in r["reply"]
    body = s.requests[-1]
    assert body["messages"] == [{"role": "system", "content": CFG["system_prompt"]},
                                {"role": "user", "content": "반포점 리스트 불러줘"}]
    g = CFG["generation"]
    assert (body["max_tokens"], body["top_k"], body["repeat_penalty"]) == (
        g["max_new_tokens"], g["top_k"], g["repetition_penalty"])


@pytest.mark.parametrize("mode", ["slow", "busy", "broken"])
def test_llm_trouble_gives_retry_reply(fake, monkeypatch, mode):
    s = fake(mode=mode)
    bot = bot_for(monkeypatch, s.url, timeout="0.5")
    r = bot.run("다음 어디야")
    assert r["reply"] == CFG["llm_busy_message"]
    assert r["request"] is None and r["fn"] is None and r["route"] == "ask"
    assert r["llm"]["error"]


def test_server_down_at_start_and_request(monkeypatch):
    # 아무도 안 듣는 포트: 시작은 되고, 요청에는 다시 말해 달라고 답한다
    bot = bot_for(monkeypatch, "http://127.0.0.1:9")
    assert bot.models_loaded
    r = bot.run("다음 어디야")
    assert r["reply"] == CFG["llm_busy_message"]


def test_backend_chat_in_rkllm_mode(fake, monkeypatch, tmp_path):
    """백엔드(/api/assistant/chat)가 rkllm 모드 파이프라인으로 끝까지 도는지 (백엔드 코드는 그대로)."""
    s = fake({"다음 어디야": '{"fn":"next_stop"}', "점장님한테 줬어": '{"fn":"complete","receiver":"점장님"}'})
    monkeypatch.setenv("LOGION_LLM_BACKEND", "rkllm")
    monkeypatch.setenv("LOGION_LLM_URL", s.url)
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "t.db"))
    monkeypatch.delenv("LOGION_ASSISTANT", raising=False)
    sys.path.insert(0, str(ROOT / "backend"))
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        st = c.get("/api/assistant/status").json()
        assert st["ready"] is True and "rkllm" in st["device"]
        r = c.post("/api/assistant/chat", json={"text": "다음 어디야", "session_id": "t"}).json()
        assert r["fn"] == "next_stop" and r["action"] == "refresh_route"
        r = c.post("/api/assistant/chat", json={"text": "점장님한테 줬어", "session_id": "t"}).json()
        assert r["fn"] == "complete" and r["route"] == "confirm_ask"   # 11/20: 납품 완료는 되묻고 기록
        r = c.post("/api/assistant/chat", json={"text": "네", "session_id": "t"}).json()
        assert r["fn"] == "complete" and r["action"] == "refresh_stop"
        s.mode = "busy"
        r = c.post("/api/assistant/chat", json={"text": "다음 어디야", "session_id": "t"})
        assert r.status_code == 200 and r.json()["reply"] == CFG["llm_busy_message"] and r.json()["action"] is None
