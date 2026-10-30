"""단일 모델 설정으로 띄운 demo/chat_server.py 에 문장을 보내고 응답을 results/single_llm/demo_results.json 에 저장."""
import argparse, json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENTENCES = [
    "다음 배송지 어디야",              # next_stop
    "CU 서울숲점에 내릴 물건 알려줘",   # stop_items
    "GS25 성수연무장점 납품 끝났어",     # complete
    "서울우유 두 개 파손됐어",          # report_issue (점포 없음 → 되묻기 가능)
    "바코드 찍을게",                   # scan
    "오늘 날씨 어때",                  # other
    "세븐일레븐 뚝섬점 컵라면 3개 수량부족",  # report_issue (전부 있음)
    "물건 문제 있어요",                # 모호 → 슬롯 되묻기
]


def post(url, text):
    req = urllib.request.Request(url + "/chat", data=json.dumps({"text": text}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:7861")
    ap.add_argument("--out", default=str(ROOT / "results/single_llm/demo_results.json"))
    ap.add_argument("--extra", nargs="*", default=[], help="추가 문장 (바로 이어서 전송, 되묻기 답변용)")
    ap.add_argument("--no-default", action="store_true")
    a = ap.parse_args()
    rows = []
    for s in ([] if a.no_default else SENTENCES) + a.extra:
        r = post(a.url, s)
        rows.append({"text": s, "fn": r.get("fn"), "route": r.get("route"), "intent": r.get("intent"),
                     "llm_raw": (r.get("llm") or {}).get("raw"), "resolve": r.get("resolve"),
                     "request": r.get("request"), "reply": r.get("reply"),
                     "timings_ms": {k: round(v, 1) for k, v in (r.get("timings") or {}).items()}})
        print(s, "->", rows[-1]["fn"], rows[-1]["route"], "|", rows[-1]["llm_raw"], "|", rows[-1]["reply"])
    Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
