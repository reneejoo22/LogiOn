"""보드 백엔드 검증: 함수 6개별 1문장씩 + 동시 요청 2개. 표준 라이브러리만 사용.

  python3 scripts/board/verify_board.py [--url http://127.0.0.1:8000] [--out logs/verify.json]
PC 에서 Tailscale 로: python scripts/board/verify_board.py --url http://100.82.118.121:8000
주의: complete·report_issue 는 백엔드 DB 를 실제로 바꾼다.
"""
import argparse
import json
import threading
import time
import urllib.request

CASES = [
    ("next_stop", "다음 어디야"),
    ("stop_items", "서울숲점 내릴 거 알려줘"),
    ("complete", "점장님한테 줬어"),
    ("report_issue", "서울숲점 콜라 두 박스 파손됐어"),
    ("scan", "바코드 찍을게"),
    ("other", "근처 화장실 어디야"),
]
CONCURRENT = ["다음 어디야", "스캐너 켜줘"]


def chat(url, text, sid):
    body = json.dumps({"text": text, "session_id": sid}, ensure_ascii=False).encode()
    req = urllib.request.Request(url + "/api/assistant/chat", data=body, headers={"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
        code = r.status
    return code, d, (time.perf_counter() - t) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", choices=["cases", "concurrent"], default=None)
    a = ap.parse_args()
    res = {"url": a.url, "status": json.loads(urllib.request.urlopen(a.url + "/api/assistant/status", timeout=10).read())}
    print("status:", res["status"])
    if a.only != "concurrent":
        res["cases"] = []
        print(f"\n{'기대':12s} {'fn':12s} {'route':8s} {'백엔드ms':>8s} {'왕복ms':>7s}  문장 → 응답")
        for want, text in CASES:
            code, d, ms = chat(a.url, text, "verify")
            res["cases"].append({"want": want, "text": text, "http": code, "fn": d.get("fn"), "route": d.get("route"),
                                 "reply": d.get("reply"), "action": d.get("action"), "call": d.get("call"),
                                 "latency_ms": d.get("latency_ms"), "client_ms": round(ms)})
            print(f"{want:12s} {str(d.get('fn')):12s} {str(d.get('route')):8s} {d.get('latency_ms'):>8} {ms:7.0f}  {text} → {d.get('reply')}")
    if a.only != "cases":
        out, ths = [None, None], []
        t0 = time.perf_counter()

        def go(i):
            ts = time.perf_counter() - t0
            code, d, ms = chat(a.url, CONCURRENT[i], f"conc{i}")
            out[i] = {"text": CONCURRENT[i], "http": code, "fn": d.get("fn"), "reply": d.get("reply"),
                      "latency_ms": d.get("latency_ms"), "client_ms": round(ms), "sent_at_ms": round(ts * 1000),
                      "done_at_ms": round((time.perf_counter() - t0) * 1000)}

        for i in range(2):
            ths.append(threading.Thread(target=go, args=(i,)))
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        res["concurrent"] = out
        print("\n동시 요청 2개:")
        for o in out:
            print(f"  {o['text']}: http {o['http']} fn={o['fn']} 백엔드 {o['latency_ms']}ms, 왕복 {o['client_ms']}ms, "
                  f"보낸 시각 {o['sent_at_ms']}ms → 끝난 시각 {o['done_at_ms']}ms | {o['reply']}")
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
