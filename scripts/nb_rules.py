"""노트북의 '규칙 코드'(설정, 가상 DB, parse_call/resolve/snap, score_fc)를 그대로 불러온다.
평가 스크립트가 노트북과 다른 규칙을 쓰지 않도록 복사본을 만들지 않고 노트북 셀을 실행한다. (torch/GPU 불필요)

  from nb_rules import load_rules
  R = load_rules()          # dict: SYSTEM_PROMPT, FUNCS, CURRENT_STORE, parse_call, resolve, score_fc ...
"""
import contextlib, io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "notebooks", "LogiOn_AI_pipeline.ipynb")
MARKERS = ["SEED = 42", "STORES = [", "TEMPLATES = {", "NEEDS = {", "def slot_pairs"]
# 되묻기·파이프라인 지표 셀은 뒤쪽에 모델이 필요한 코드가 붙어 있어, 그 줄부터 잘라내고 함수 정의만 불러온다
ROUTE_MARKERS = {"def route_decision": "va_i = intent_df", "def pipeline_rows": "P_te = intent_probs"}


def load_rules(with_assistant=False, with_route=False):
    """with_assistant=True 면 가상 DB 와 Assistant 클래스(응답 문장 만들기)까지,
    with_route=True 면 되묻기 판정(route_decision/force_fn/ask_stats)과 파이프라인 지표
    (pipeline_rows/row_results/summarize_rr)까지 불러온다. 후자는 ID2LABEL 과 numpy/pandas/f1_score 를
    쓰므로 이 함수가 먼저 ns 에 넣어 준다."""
    nb = json.load(open(NB, encoding="utf-8"))
    code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    ns = {"__name__": "nb_rules_ns"}
    cwd = os.getcwd()
    os.chdir(ROOT)                      # 노트북의 ROOT 판정(".") 이 레포 루트를 가리키게
    try:
        for m in MARKERS + (["ROUTE = ["] if with_assistant else []):
            src = [s for s in code if m in s]
            assert len(src) == 1, (m, len(src))
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(src[0], f"<notebook:{m}>", "exec"), ns)
        if with_route:
            import numpy as np
            import pandas as pd
            from sklearn.metrics import f1_score
            funcs = ns["FUNCS"]
            ns.update(np=np, pd=pd, f1_score=f1_score, json=json, os=os,
                      LABEL2ID={f: i for i, f in enumerate(funcs)},
                      ID2LABEL=dict(enumerate(funcs)))
            for m, cut in ROUTE_MARKERS.items():
                src = [s for s in code if m in s]
                assert len(src) == 1, (m, len(src))
                head = src[0].split(cut)[0]
                assert m in head, f"{m}: 자르는 위치가 잘못됨"
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(head, f"<notebook:{m}>", "exec"), ns)
    finally:
        os.chdir(cwd)
    return ns


if __name__ == "__main__":
    R = load_rules()
    print(R["resolve"]({"fn": "report_issue", "item": "우유", "issue": "파손", "qty": 2}, R["CURRENT_STORE"]))
