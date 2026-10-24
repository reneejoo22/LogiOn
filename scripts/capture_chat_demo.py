"""채팅 데모 화면을 Playwright 로 캡처한다 -> docs/chat_demo/

먼저 서버를 띄워 둔다:  python demo/chat_server.py
그다음:                 python scripts/capture_chat_demo.py

전체 화면 1장 + 문장별 결과 카드 1장씩 저장한다. 캡처 전에 하단 입력창은 숨긴다.
선택지 되묻기가 뜨면 선택지 버튼을 눌러 이어받기까지 캡처한다.
문장별 수치는 docs/chat_demo/results.json 과 results.md 에 함께 저장한다.
"""
import argparse, json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost:7860")
ap.add_argument("--out", default=f"{ROOT}/docs/chat_demo")
ap.add_argument("--timeout", type=int, default=120000)
args = ap.parse_args()

SENTENCES = ["다음 어디야", "서울숲점 콜라 몇 박스야", "우유 두 개 터졌어", "이거 미지근해",
             "바나나우유", "점장님한테 넘겼어", "물건 확인할게", "노래 틀어줘"]

from playwright.sync_api import sync_playwright

os.makedirs(args.out, exist_ok=True)


def slug(i, text):
    return f"{i:02d}_" + re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_")


rows = []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 900, "height": 1100}, device_scale_factor=2)
    page.goto(args.url, wait_until="networkidle")
    badge = page.locator("#badge").inner_text()
    print("배지:", badge)
    if "실제 모델" not in badge:
        browser.close()
        sys.exit(f"실제 모델 모드가 아닙니다 (배지: {badge}). out/intent_model, out/fc_merged 를 확인하세요.")

    def ask(text, idx, label=None):
        """문장 하나를 넣고 결과 카드가 생길 때까지 기다린 뒤, 카드만 캡처."""
        before = page.locator(".card").count()
        page.fill("#q", text)
        page.click("#send")
        page.wait_for_function(f"document.querySelectorAll('.card').length > {before}", timeout=args.timeout)
        page.wait_for_timeout(250)
        card = page.locator(".card").nth(before)
        name = slug(idx, label or text)
        card.screenshot(path=f"{args.out}/{name}.png")
        data = page.evaluate("""() => {
            const c = document.querySelectorAll('.card');
            return c[c.length - 1].innerText;
        }""")
        bubble = page.locator(".row.bot .bubble").last
        opts = bubble.locator("button[data-o]")
        return name, data, [opts.nth(i).inner_text() for i in range(opts.count())]

    page.add_style_tag(content="#composer{visibility:hidden}")   # 캡처 전 하단 입력창 숨김
    page.eval_on_selector("#composer", "e => e.style.visibility='visible'")

    idx = 0
    for s in SENTENCES:
        idx += 1
        page.eval_on_selector("#composer", "e => e.style.visibility='visible'")
        name, text, opts = ask(s, idx)
        print(f"  [{idx}] {s} -> 카드 저장 {name}.png" + (f" / 선택지 {opts}" if opts else ""))
        rows.append({"i": idx, "text": s, "card": name + ".png", "card_text": text, "options": opts})
        if opts:                                   # 선택지 되묻기면 첫 버튼을 눌러 이어받기까지
            idx += 1
            page.locator(".row.bot .bubble").last.locator("button[data-o]").first.click()
            page.wait_for_function(
                f"document.querySelectorAll('.card').length > {page.locator('.card').count() - 1}",
                timeout=args.timeout)
            page.wait_for_timeout(250)
            card = page.locator(".card").last
            name2 = slug(idx, f"{opts[0]}_선택")
            card.screenshot(path=f"{args.out}/{name2}.png")
            t2 = page.evaluate("() => document.querySelectorAll('.card')[document.querySelectorAll('.card').length-1].innerText")
            print(f"  [{idx}] 선택지 '{opts[0]}' 누름 -> {name2}.png")
            rows.append({"i": idx, "text": f"(선택지) {opts[0]}", "card": name2 + ".png",
                         "card_text": t2, "options": []})

    # 전체 화면 (입력창 숨김, sticky 헤더는 고정 해제해야 긴 화면 중간에 겹쳐 찍히지 않음)
    page.eval_on_selector("#composer", "e => e.style.visibility='hidden'")
    page.add_style_tag(content="header{position:static !important} #composer{display:none !important}")
    page.wait_for_timeout(200)
    page.screenshot(path=f"{args.out}/00_full.png", full_page=True)
    print("전체 화면 저장: 00_full.png")
    browser.close()


# ---- 카드 글에서 수치 뽑아 표로 ----
MARKS = ["이어받기", "② 의도분류", "③ LLM", "④ 값 보정", "⑤ 실행", "⑥ 응답"]


def sections(t):
    """카드 글을 ②③④⑤⑥ 구역으로 나눈다 (없는 구역은 빈 문자열)."""
    idx = sorted(((t.index(m), m) for m in MARKS if m in t))
    out = {m: "" for m in MARKS}
    for k, (pos, m) in enumerate(idx):
        end = idx[k + 1][0] if k + 1 < len(idx) else len(t)
        out[m] = t[pos + len(m):end].strip()
    return out


def grab(t, pat, default="—"):
    m = re.search(pat, t)
    return m.group(1) if m else default


table = []
for r in rows:
    t = r["card_text"]
    sec = sections(t)
    bars = re.findall(r"^(next_stop|stop_items|complete|report_issue|scan|other)\n(\d\.\d{3})$",
                      sec["② 의도분류"], re.M)
    llm = sec["③ LLM"]
    table.append({
        "문장": r["text"],
        "의도분류 1등": f"{bars[0][0]} {bars[0][1]}" if bars else "— (이어받기)",
        "margin": grab(sec["② 의도분류"], r"margin (\d\.\d{3})"),
        "LLM 출력": ("건너뜀 (LLM 생략)" if "건너뜀" in llm
                     else grab(llm, r"(\{[^\n]*\})") if llm else "호출 안 함 (직전 답 이어받기)"),
        "확신도(평균/최소)": (f'{grab(llm, r"평균 (\d\.\d{3})")} / {grab(llm, r"최솟값 (\d\.\d{3})")}'
                              if "확신도" in llm else "—"),
        "응답": sec["⑥ 응답"].split("\n")[0] if sec["⑥ 응답"] else "—",
        "전체 ms": grab(t, r"전체 (\d+\.\d)ms"),
        "캡처": r["card"],
    })

json.dump({"url": args.url, "rows": rows, "table": table},
          open(f"{args.out}/results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
cols = ["문장", "의도분류 1등", "margin", "LLM 출력", "확신도(평균/최소)", "응답", "전체 ms", "캡처"]
md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
for r in table:
    md.append("| " + " | ".join(str(r[c]).replace("|", "\\|") for c in cols) + " |")
open(f"{args.out}/results.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n" + "\n".join(md))
print(f"\n저장: {args.out}")
