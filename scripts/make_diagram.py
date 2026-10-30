"""docs/architecture.png / .svg 생성 — 단일 모델(v3-single) 구조. 숫자는 results/single_llm 파일에서 읽어 넣는다.

  python scripts/make_diagram.py

의도분류를 포함한 이전 구조(v2.1) 그림은 scripts/make_diagram_v2_1.py (docs/architecture_v2_1.png).
한글은 Windows 의 맑은 고딕(malgun.ttf)을 직접 지정한다. 폰트가 없으면 알리고 멈춘다.
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--results", default=f"{ROOT}/results/single_llm")
ap.add_argument("--config", default=f"{ROOT}/config/pipeline_v3_single.json")
ap.add_argument("--out", default=f"{ROOT}/docs/architecture")
args = ap.parse_args()

FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_BD = "C:/Windows/Fonts/malgunbd.ttf"
if not os.path.exists(FONT):
    sys.exit(f"한글 폰트가 없습니다: {FONT} (Windows 의 맑은 고딕이 필요합니다)")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

_SIZES = (7, 7.5, 8, 8.5, 9, 9.5, 10, 11, 15)
F = {s: FontProperties(fname=FONT, size=s) for s in _SIZES}
FB = {s: FontProperties(fname=FONT_BD if os.path.exists(FONT_BD) else FONT, size=s) for s in _SIZES}

# ---------------- 숫자 읽기 (직접 타이핑 금지) ----------------
S = json.load(open(f"{args.results}/summary.json", encoding="utf-8"))
CFG = json.load(open(args.config, encoding="utf-8"))
M, V = S["fc_only"], S["v2_1"]
PC = pd.read_csv(f"{args.results}/per_class.csv", index_col=0, encoding="utf-8-sig")
OK = PC["FC단독 최종 정답"].to_dict()
LAT = S["latency"]["all"]
NOVAL = S["latency"]["no_value_fns(next_stop,scan,other)"]


def pct(x):
    return f"{x * 100:.1f}%"


C = {"in": "#e8eef7", "llm": "#f7ded6", "res": "#e4e4ef", "exec": "#dce9f0", "out": "#e8eef7",
     "ask": "#efe2f5", "sum": "#f7f7f2", "off": "#eeeeee"}
EDGE = "#5a6472"

fig, ax = plt.subplots(figsize=(14, 10.5), dpi=170)
ax.set_xlim(0, 136)
ax.set_ylim(0, 106)
ax.axis("off")
fig.patch.set_facecolor("white")


def box(x, y, w, h, lines, fc, fs=8, align="center", dashed=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2",
                                facecolor=fc, edgecolor=EDGE, linewidth=0.9, linestyle="--" if dashed else "-"))
    gap = 3.3 if fs >= 9 else 2.9
    top = y + h - (h - (len(lines) - 1) * gap) / 2
    tx, ha = (x + w / 2, "center") if align == "center" else (x + 2.5, "left")
    for i, t in enumerate(lines):
        ax.text(tx, top - i * gap, t, ha=ha, va="center", fontproperties=(FB[fs] if i == 0 else F[fs]))


def arrow(p1, p2):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=12, linewidth=1.1,
                                 color=EDGE, shrinkA=0, shrinkB=0))


def line(p1, p2):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=EDGE, linewidth=1.1, solid_capstyle="round")


ax.text(68, 102.5, "LogiOn 음성 업무 비서 — 단일 모델 구조 (v3-single)", ha="center", fontproperties=FB[15])
ax.text(68, 98.6, f"test {int(M['n'])}문장 기준 · 재학습 없음 · 숫자는 results/single_llm 파일에서 읽어 넣음",
        ha="center", fontproperties=F[8.5], color="#555")

box(4, 84, 32, 8, ["입력", "텍스트 (현재)  /  음성→STT (추후)"], C["in"], 9)
arrow((36.2, 88), (41.5, 88))

box(42, 80, 90, 16, [
    "function calling   Qwen2.5-1.5B-Instruct + LoRA   (의도분류까지 겸함)",
    "출력 JSON 한 줄:  fn ∈ {next_stop, stop_items, complete, report_issue, scan, other}  + 값",
    f"fn 정확도 {M['fc_fn_acc']:.3f} · 완전일치 {M['fc_exact']:.3f} · 값 F1 {M['fc_slot_f1']:.3f} · JSON 유효 {pct(M['fc_json_valid'])}",
    f"기능별 최종 정답  next_stop {OK['next_stop']:.3f} · stop_items {OK['stop_items']:.3f} · complete {OK['complete']:.3f}",
    f"report_issue {OK['report_issue']:.3f} · scan {OK['scan']:.3f} · other {OK['other']:.3f}"], C["llm"], 8.5)

box(4, 62, 32, 12, [
    "의도분류 모듈 (분리)",
    "klue/roberta-small · Qwen3-0.6B",
    "기본 경로에서 제외 — 코드·결과는 보존",
    "config/pipeline_v2_1.json 으로 재사용"], C["off"], 8, dashed=True)

arrow((87, 79.8), (87, 74.4))
box(40, 58, 94, 16, [
    "값 보정  resolve()   (규칙 기반)",
    "DB 이름 맞추기 (정확 → 별칭 → 포함 → 발음 유사도)  ·  단위 맞추기 (개 / 박스 / 판 / 봉지)",
    "점포를 말하지 않으면 다음 배송지로 채움",
    "값이 비면 그 값만 되물음  (슬롯 되묻기 — 확률 기반 되묻기·LLM 생략은 없음)"], C["res"], 8.5)

arrow((87, 57.8), (87, 52.4))
box(4, 38, 56, 14, [
    "실행  백엔드 API",
    "GET /api/routes/today · GET /api/stops/{id}",
    "POST /api/stops/{id}/complete · /issues"], C["exec"], 8.5)
box(66, 38, 66, 14, [
    "응답 문장",
    "규칙으로 만든 한국어 문장 → (추후) TTS VITS",
    "되묻기는 실행 없이 질문만 내보냄"], C["out"], 8.5)
arrow((66, 45), (60.4, 45))

pd_ = S["paired_final_ok"]
sum_lines = [
    f"결과 요약  (test {int(M['n'])}문장, 이 PC 에서 실행한 값)  —  단일 모델  vs  의도분류 포함 v2.1",
    f"의도(fn) 정확도 {M['intent_acc']:.3f} vs {V['intent_acc']:.3f}     ·     최종 정확도(되묻기 포함) "
    f"{M['pipeline_incl_ask']:.3f} vs {V['pipeline_incl_ask']:.3f}     ·     틀리게 실행 "
    f"{pct(M['wrong_exec_rate'])} vs {pct(V['wrong_exec_rate'])}",
    f"되묻기(확률 기반) {pct(M['ask_rate'])} vs {pct(V['ask_rate'])}     ·     LLM 생략 {pct(M['llm_skip_rate'])} vs "
    f"{pct(V['llm_skip_rate'])}     ·     문장 단위 비교: 둘 다 정답 {pd_['both_ok']}, v2.1만 정답 "
    f"{pd_['only_v2_1_ok']}, 단일만 정답 {pd_['only_fc_only_ok']}, 둘 다 오답 {pd_['both_wrong']}",
    f"PC GPU(RTX 5050, bf16, 배치 1) 문장당 {LAT['fc_only_ms']['mean']:.0f}ms (v2.1 {LAT['v2_1_ms']['mean']:.0f}ms) · "
    f"값 없는 명령 평균 {NOVAL['fc_only_ms']['mean']:.0f}ms, 생성 토큰 평균 {NOVAL['gen_tokens_mean']:.1f}개",
    "※ 보드(RK3588) 실측값이 아니며, STT·TTS 단계는 아직 측정하지 않았음 (미실행)",
]
box(4, 6, 128, 25, sum_lines, C["sum"], 8.5)

for p, fmt in ((f"{args.out}.png", "png"), (f"{args.out}.svg", "svg")):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fig.savefig(p, format=fmt, bbox_inches="tight", facecolor="white")
    print("saved:", p, f"{os.path.getsize(p) / 1024:.0f} KB")
