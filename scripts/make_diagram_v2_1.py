"""[의도분류 포함 v2.1 구조] docs/architecture_v2_1.png / .svg 생성. 숫자는 results/v2_1 파일에서 읽어 넣는다 (손으로 적지 않음).

  python scripts/make_diagram_v2_1.py
  python scripts/make_diagram_v2_1.py --results results/v2_1 --out docs/architecture_v2_1

한글은 Windows 의 맑은 고딕(malgun.ttf)을 직접 지정한다. 폰트가 없으면 어떤 폰트가 없는지 알리고 멈춘다.
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--results", default=f"{ROOT}/results/v2_1")
ap.add_argument("--onnx", default=f"{ROOT}/results/v2/onnx_intent.json")
ap.add_argument("--config", default=f"{ROOT}/config/pipeline_v2_1.json")
ap.add_argument("--out", default=f"{ROOT}/docs/architecture_v2_1")
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
S = json.load(open(f"{args.results}/test_summary.json", encoding="utf-8"))
CFG = json.load(open(args.config, encoding="utf-8"))
M = S["test"]["v2_1"]
ONNX = json.load(open(args.onnx, encoding="utf-8")) if os.path.exists(args.onnx) else None
BY_FN = pd.read_csv(f"{args.results}/test_by_fn.csv", index_col=0)
OK = BY_FN["FC 최종동작일치"].to_dict()


def pct(x):
    return f"{x * 100:.1f}%"


C = {"in": "#e8eef7", "intent": "#d6e4f7", "fast": "#dcf0e2", "slot": "#fdf0d5", "llm": "#f7ded6",
     "ask": "#efe2f5", "res": "#e4e4ef", "exec": "#dce9f0", "out": "#e8eef7", "sum": "#f7f7f2"}
EDGE = "#5a6472"

fig, ax = plt.subplots(figsize=(14, 12.2), dpi=170)
ax.set_xlim(0, 136)
ax.set_ylim(0, 126)
ax.axis("off")
fig.patch.set_facecolor("white")


def box(x, y, w, h, lines, fc, fs=8, align="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.35,rounding_size=1.6",
                                facecolor=fc, edgecolor=EDGE, linewidth=0.9))
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


def tag(x, y, t):
    ax.text(x, y, t, ha="center", va="center", fontproperties=F[7.5],
            bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none"))


ax.text(68, 122.5, "LogiOn 음성 업무 비서 — 구조와 측정 결과 (v2.1)", ha="center", fontproperties=FB[15])
ax.text(68, 118.6, f"test {int(M['n'])}문장 기준 · 기준값은 val 로만 골랐음 · 숫자는 results/v2_1 파일에서 읽어 넣음",
        ha="center", fontproperties=F[8.5], color="#555")

# 1) 입력 -> 의도분류
box(4, 105, 32, 8, ["입력", "텍스트 (현재)  /  음성→STT (추후)"], C["in"], 9)
box(42, 103.5, 90, 11, [
    "의도분류   klue/roberta-small   (6개 클래스)",
    f"test 정확도 {M['intent_acc']:.3f}  ·  macro F1 {M['intent_macro_f1']:.3f}",
    (f"보드용 ONNX int8 {ONNX['size_mb']['int8_mb']:.0f}MB · CPU "
     f"{ONNX['onnx_int8']['cpu_ms_per_sentence_bs1']:.1f}ms/문장 · PyTorch 와 예측 "
     f"{pct(ONNX['onnx_int8']['agree_with_pytorch'])} 일치") if ONNX else "ONNX 결과 파일 없음"], C["intent"], 9)
arrow((36.2, 109), (41.5, 109))
arrow((87, 103.3), (87, 99.9))

# 2) 갈림길
box(4, 93, 128, 6.5, ["갈림길  —  1·2등 확률차(margin) 와 1등 확신도로 세 길 중 하나를 고름"], C["intent"], 9)
for x, t in ((20, "① 값이 없는 기능 · 확신 높음"), (69, "② 값이 있는 기능"), (117, f"③ margin < {CFG['ask_tau']}")):
    arrow((x, 92.8), (x, 85.4))
    tag(x, 89.1, t)

# 3) 세 갈래
box(4, 68, 32, 17, [
    "빠른 길 (LLM 없이 바로)",
    "scan / other",
    f"확률 ≥ {CFG['skip_llm_conf']} 이면 LLM 생략",
    f"test 문장의 {pct(M['llm_skip_rate'])}",
    f"scan {OK.get('scan', float('nan')):.3f}",
    f"other {OK.get('other', float('nan')):.3f}"], C["fast"], 8)
box(40, 68, 58, 17, [
    "값이 있는 기능 — 슬롯을 채워야 함",
    f"stop_items ( store? , item? )                   {OK.get('stop_items', float('nan')):.3f}",
    f"complete ( store? , receiver? )                {OK.get('complete', float('nan')):.3f}",
    f"report_issue ( store? , item? , issue , qty? , unit )    {OK.get('report_issue', float('nan')):.3f}",
    "     issue ∈ {파손, 수량부족, 오배송, 온도이상}",
    "     unit ∈ {개, 박스, 판, 봉지}"], C["slot"], 8, align="left")
box(102, 68, 30, 17, [
    "선택지로 되묻기",
    "실행하지 않고 두 후보를",
    "말해 주며 고르게 함",
    f'한 쪽이 other 면 "{CFG["retry_message"]}"',
    f"test 되묻기 비율 {pct(M['ask_rate'])}"], C["ask"], 8)

# 4) LLM
arrow((69, 67.8), (69, 64.4))
box(40, 52, 58, 12, [
    "function calling   Qwen2.5-1.5B-Instruct + LoRA",
    f"fn 정확도 {M['fc_fn_acc']:.3f} · 완전일치 {M['fc_exact']:.3f} · 값 F1 {M['fc_slot_f1']:.3f} · JSON 유효 {pct(M['fc_json_valid'])}",
    f"next_stop 도 v2.1 부터 여기로 보낸다 (건너뛰기 대상에서 제외, {OK.get('next_stop', float('nan')):.3f})"], C["llm"], 8.5)

# 5) 값 보정
arrow((69, 51.8), (69, 47.4))
box(40, 33, 58, 14, [
    "값 보정  resolve()",
    "DB 이름 맞추기 (정확 → 별칭 → 포함 → 발음 유사도)",
    "단위 맞추기 (개 / 박스 / 판 / 봉지)",
    "점포를 말하지 않으면 다음 배송지로 채움",
    "값이 비면 그 값만 되물음"], C["res"], 8.5)
line((20, 68), (20, 40))
arrow((20, 40), (39.5, 40))

# 6) 실행 -> 응답
box(4, 16, 56, 11, [
    "실행  백엔드 API",
    "GET /api/routes/today · GET /api/stops/{id}",
    "POST /api/stops/{id}/complete · /issues"], C["exec"], 8.5)
box(66, 16, 66, 11, [
    "응답 문장",
    "규칙으로 만든 한국어 문장 → (추후) TTS VITS",
    "되묻기는 실행 없이 질문만 내보냄"], C["out"], 8.5)
arrow((58, 32.8), (46, 27.4))
arrow((60.3, 21.5), (65.5, 21.5))
line((117, 68), (117, 28))
arrow((117, 28), (117, 27.4))

# 7) 결과 요약
sum_lines = [
    f"결과 요약  (test {int(M['n'])}문장, 이 PC 에서 실행한 값)",
    f"파이프라인 전체 정확도(되묻기 없음) {M['pipeline_acc_no_ask']:.3f}     ·     되묻기 포함 성공 "
    f"{M['pipeline_incl_ask']:.3f}     ·     실행한 것 중 정답 {M['exec_precision']:.3f}",
    f"되묻기 비율 {pct(M['ask_rate'])}     ·     틀리게 실행 {pct(M['wrong_exec_rate'])}"
    f"     ·     LLM 생략 {pct(M['llm_skip_rate'])}",
]
TM = S.get("timing_ms_per_sentence", {})
fc_ms = TM.get(f"fc_{S['selected_config']['fc']}_ms_per_sentence")
if ONNX and fc_ms:
    sum_lines.append(
        f"단계별 시간: 의도분류 ONNX int8 {ONNX['onnx_int8']['cpu_ms_per_sentence_bs1']:.1f}ms (PC CPU 4스레드)"
        f"     ·     LLM 생성 {fc_ms:.0f}ms/문장 (PC GPU, 배치 처리 평균)"
        f"     ·     값 보정·응답 1ms 미만")
sum_lines.append("※ 보드(RK3588) 실측값이 아니며, STT·TTS 단계는 아직 측정하지 않았음 (미실행)")
box(4, 0.5, 128, 14, sum_lines, C["sum"], 8.5)

for p, fmt in ((f"{args.out}.png", "png"), (f"{args.out}.svg", "svg")):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fig.savefig(p, format=fmt, bbox_inches="tight", facecolor="white")
    print("saved:", p, f"{os.path.getsize(p) / 1024:.0f} KB")
