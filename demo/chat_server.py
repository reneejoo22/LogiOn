"""LogiOn 채팅 데모 서버 — 앱의 AI 채팅 화면과 같은 모양으로, 실제 모델을 붙여 돌려 봅니다.

  python demo/chat_server.py                 # http://localhost:7860
  python demo/chat_server.py --port 8080
  python demo/chat_server.py --no-models     # 모델 없이 화면만 (응답은 안 나옴)

필요한 것: out/intent_model, out/fc_merged  (없으면 무엇이 없는지 알려 주고 멈춥니다)
파이썬 표준 라이브러리만 씁니다 (추가 설치 없음). 배송 데이터는 backend/app/db/seed.py 를 읽어 쓰고,
DB 변경은 이 서버 안 메모리에서만 일어납니다. 백엔드 서버나 코드는 건드리지 않습니다.
"""
import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import Assistant, ModelsMissing

PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LogiOn AI 채팅 데모</title>
<style>
  :root { --green:#2E7D57; --green-l:#E8F3EC; --line:#E3E6E4; --ink:#1B1F1D; --dim:#6B7570; }
  * { box-sizing:border-box; }
  body { margin:0; background:#F4F6F5; color:var(--ink);
         font:15px/1.55 "Malgun Gothic","맑은 고딕",system-ui,sans-serif; }
  .phone { max-width:760px; margin:0 auto; background:#FAFBFA; min-height:100vh;
           display:flex; flex-direction:column; }
  header { display:flex; align-items:center; gap:10px; padding:14px 18px; background:#fff;
           border-bottom:1px solid var(--line); position:sticky; top:0; z-index:5; }
  .logo { width:34px; height:34px; border-radius:9px; background:var(--green); color:#fff;
          display:grid; place-items:center; font-size:18px; }
  .brand { font-weight:700; font-size:19px; }
  .brand span { font-weight:500; font-size:12px; letter-spacing:.14em; color:var(--dim); margin-left:6px; }
  .badge { margin-left:auto; font-size:12px; padding:6px 12px; border-radius:999px;
           background:var(--green-l); color:var(--green); font-weight:700; }
  .badge.off { background:#FDECEC; color:#B3261E; }
  .title { padding:16px 18px 6px; }
  .title h1 { margin:0; font-size:21px; }
  .title p { margin:3px 0 0; color:var(--dim); font-size:13px; }
  .cfg { margin:10px 18px 0; padding:9px 13px; border-radius:10px; background:var(--green-l);
         color:#2b5e45; font-size:12.5px; }
  #log { flex:1; padding:14px 18px 20px; display:flex; flex-direction:column; gap:12px; }
  .row { display:flex; }
  .row.me { justify-content:flex-end; }
  .bubble { max-width:78%; padding:11px 15px; border-radius:16px; white-space:pre-wrap; }
  .me .bubble { background:var(--green); color:#fff; border-bottom-right-radius:5px; }
  .bot .bubble { background:#fff; border:1px solid var(--line); border-bottom-left-radius:5px; }
  .opts { display:flex; gap:8px; flex-wrap:wrap; margin-top:9px; }
  .opts button { border:1.5px solid var(--green); background:#fff; color:var(--green);
                 padding:8px 15px; border-radius:999px; font-size:14px; font-weight:700; cursor:pointer; }
  .card { background:#fff; border:1px solid var(--line); border-radius:13px; overflow:hidden; font-size:13px; }
  .card h4 { margin:0; padding:9px 14px; background:#F2F5F3; font-size:12.5px; color:var(--dim);
             border-bottom:1px solid var(--line); font-weight:700; letter-spacing:.02em; }
  .card .body { padding:11px 14px; display:flex; flex-direction:column; gap:9px; }
  .step { display:grid; grid-template-columns:86px 1fr; gap:10px; align-items:start; }
  .step b { color:var(--green); font-size:12px; padding-top:1px; }
  .bars { display:flex; flex-direction:column; gap:3px; }
  .bar { display:grid; grid-template-columns:96px 1fr 50px; gap:7px; align-items:center; font-size:12px; }
  .bar i { font-style:normal; color:var(--dim); }
  .bar .t { height:7px; background:#EDF0EE; border-radius:4px; overflow:hidden; }
  .bar .t div { height:100%; background:var(--green); }
  code { background:#F2F5F3; padding:2px 6px; border-radius:5px; font-size:12px;
         font-family:Consolas,monospace; word-break:break-all; }
  .why { color:var(--dim); font-size:12px; }
  .ms { display:flex; gap:7px; flex-wrap:wrap; }
  .ms span { background:#F2F5F3; border-radius:999px; padding:3px 10px; font-size:11.5px; color:var(--dim); }
  .ms span.tot { background:var(--green-l); color:var(--green); font-weight:700; }
  table.res { border-collapse:collapse; width:100%; font-size:12px; }
  table.res td { padding:3px 6px; border-bottom:1px dashed var(--line); }
  table.res td:first-child { color:var(--dim); width:74px; }
  #composer { position:sticky; bottom:0; display:flex; gap:9px; padding:12px 18px 16px;
              background:#FAFBFA; border-top:1px solid var(--line); }
  #q { flex:1; padding:12px 15px; border:1.5px solid var(--green); border-radius:13px; font-size:15px; outline:none; }
  #send { width:46px; border:0; border-radius:50%; background:var(--green); color:#fff; font-size:17px; cursor:pointer; }
  .hint { padding:0 18px 10px; color:var(--dim); font-size:12px; }
</style></head><body>
<div class="phone">
  <header>
    <div class="logo">&#128666;</div>
    <div class="brand">LogiOn<span>DRIVER</span></div>
    <div class="badge" id="badge">…</div>
  </header>
  <div class="title"><h1>AI 채팅</h1><p>배송 업무를 텍스트로 입력</p></div>
  <div class="cfg" id="cfg"></div>
  <div id="log"></div>
  <div id="composer">
    <input id="q" placeholder="예: 다음 배송 어디야?" autocomplete="off">
    <button id="send">&#10148;</button>
  </div>
  <div class="hint">값 보정과 실행은 backend/app/db/seed.py 의 데이터를 이 서버 메모리에서 처리합니다.</div>
</div>
<script>
const log = document.getElementById('log'), q = document.getElementById('q');
let n = 0;
fetch('/info').then(r => r.json()).then(d => {
  const b = document.getElementById('badge');
  b.textContent = d.models ? ('실제 모델 · ' + d.device_name) : '모델 없음 · 화면만';
  if (!d.models) b.classList.add('off');
  document.getElementById('cfg').textContent =
    (d.cfg.use_intent
      ? 'tau ' + d.cfg.ask_tau + ' · LLM 생략 ' + d.cfg.skip_llm_fns.join('/') + ' (확률 ≥ ' + d.cfg.skip_llm_conf + ')'
      : '단일 모델 (의도분류 없음 · FC 모델이 기능+값 모두 추출)')
    + ' · 설정 ' + d.cfg.version;
});
function el(html) { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; }
function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function addMe(t) { log.appendChild(el('<div class="row me"><div class="bubble">' + esc(t) + '</div></div>')); }
function card(d) {
  n += 1;
  let h = '<div class="card" id="card-' + n + '" data-q="' + esc(d.text) + '"><h4>' + n + '. "'
        + esc(d.text) + '"</h4><div class="body">';
  if (d.carry) h += '<div class="step"><b>이어받기</b><div class="why">' + esc(d.carry) + '</div></div>';
  if (d.intent && !d.intent.single) {
    let bars = d.intent.top3.map(x =>
      '<div class="bar"><i>' + x.fn + '</i><div class="t"><div style="width:' + (x.p * 100).toFixed(1)
      + '%"></div></div><i>' + x.p.toFixed(3) + '</i></div>').join('');
    h += '<div class="step"><b>② 의도분류</b><div><div class="bars">' + bars + '</div>'
       + '<div class="why">margin ' + d.intent.margin.toFixed(3) + ' · ' + esc(d.intent.why) + '</div></div></div>';
  }
  if (d.llm) {
    h += d.llm.skipped
      ? '<div class="step"><b>③ LLM</b><div class="why">건너뜀 — ' + esc(d.llm.why) + '</div></div>'
      : '<div class="step"><b>③ LLM</b><div><code>' + esc(d.llm.raw) + '</code>'
        + '<div class="why">확신도 평균 ' + d.llm.conf_mean.toFixed(3)
        + ' · 최솟값 ' + d.llm.conf_min.toFixed(3) + '</div></div></div>';
  }
  if (d.resolve && d.resolve.length) {
    const rows = d.resolve.map(s => '<tr><td>' + s.slot + '</td><td>' + esc(s.spoken) + ' → <b>'
      + esc(s.found) + '</b> <span class="why">[' + s.how + ' ' + s.score + ']'
      + (s.cands.length > 1 ? ' 후보 ' + esc(s.cands.join(', ')) : '') + '</span></td></tr>').join('');
    h += '<div class="step"><b>④ 값 보정</b><table class="res">' + rows + '</table></div>';
  }
  h += '<div class="step"><b>⑤ 실행</b><div>' + (d.request && d.request.method
      ? '<code>' + d.request.method + ' ' + d.request.path + '</code>'
        + (d.request.body ? ' <code>' + esc(JSON.stringify(d.request.body)) + '</code>' : '')
      : '<span class="why">DB 를 바꾸지 않음</span>') + '</div></div>';
  h += '<div class="step"><b>⑥ 응답</b><div>' + esc(d.reply) + '</div></div>';
  const ms = Object.entries(d.timings).map(([k, v]) =>
    '<span' + (k === '전체' ? ' class="tot"' : '') + '>' + k + ' ' + v.toFixed(1) + 'ms</span>').join('');
  h += '<div class="ms">' + ms + '</div></div></div>';
  return el(h);
}
async function ask(text) {
  if (!text) return;
  addMe(text); q.value = '';
  const r = await fetch('/chat', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                  body: JSON.stringify({text})});
  const d = await r.json();
  if (d.error) { log.appendChild(el('<div class="row bot"><div class="bubble">오류: ' + esc(d.error)
                                    + '</div></div>')); return; }
  let b = '<div class="row bot"><div class="bubble">' + esc(d.reply);
  if (d.options && d.options.length)
    b += '<div class="opts">' + d.options.map(o => '<button data-o="' + esc(o) + '">' + esc(o)
         + '</button>').join('') + '</div>';
  const node = el(b + '</div></div>');
  node.querySelectorAll('button[data-o]').forEach(x => x.onclick = () => ask(x.dataset.o));
  log.appendChild(node);
  log.appendChild(card(d));
  window.scrollTo(0, document.body.scrollHeight);
}
document.getElementById('send').onclick = () => ask(q.value.trim());
q.addEventListener('keydown', e => { if (e.key === 'Enter') ask(q.value.trim()); });
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-models", action="store_true", help="모델 없이 화면만 띄움 (응답은 안 나옴)")
    ap.add_argument("--config", default=None,
                    help="파이프라인 설정 (기본 config/pipeline_v3_single.json, 의도분류 포함은 config/pipeline_v2_1.json)")
    args = ap.parse_args()

    try:
        bot = Assistant(config_path=args.config, load_models=not args.no_models)
    except ModelsMissing as e:
        sys.exit(str(e))
    lock = threading.Lock()
    if bot.models_loaded:
        print(f"모델 준비됨: {bot.device} {bot.device_name}")
    else:
        print("모델 없이 화면만 띄웁니다 (--no-models).")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.startswith("/info"):
                return self._send(200, json.dumps({
                    "models": bot.models_loaded, "device": bot.device, "device_name": bot.device_name,
                    "cfg": {**{k: bot.cfg.get(k) for k in ("version", "ask_tau", "skip_llm_conf", "skip_llm_fns")},
                            "use_intent": bot.use_intent},
                }, ensure_ascii=False), "application/json")
            if self.path.startswith("/health"):
                return self._send(200, json.dumps({"status": "ok"}), "application/json")
            return self._send(200, PAGE, "text/html")

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            text = (body.get("text") or "").strip()
            if not bot.models_loaded:
                return self._send(200, json.dumps({"error": "모델이 올라가 있지 않습니다 (--no-models)."},
                                                  ensure_ascii=False), "application/json")
            try:
                with lock:                       # 모델은 한 번에 한 요청만
                    out = bot.run(text)
            except Exception as e:               # 실패는 숨기지 말고 화면에 그대로
                out = {"error": f"{type(e).__name__}: {e}"}
            return self._send(200, json.dumps(out, ensure_ascii=False, default=str), "application/json")

    srv = ThreadingHTTPServer((args.host, args.port), H)
    print(f"http://localhost:{args.port}  (Ctrl+C 로 종료)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
