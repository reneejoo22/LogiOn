"""노트북의 '규칙 코드'(설정, 가상 DB, parse_call/resolve/snap, score_fc)를 그대로 불러온다.
평가 스크립트가 노트북과 다른 규칙을 쓰지 않도록 복사본을 만들지 않고 노트북 셀을 실행한다. (torch/GPU 불필요)

  from nb_rules import load_rules
  R = load_rules()          # dict: SYSTEM_PROMPT, FUNCS, CURRENT_STORE, parse_call, resolve, score_fc ...
"""
import contextlib, io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "notebooks", "LogiOn_AI_pipeline.ipynb")
MARKERS = ["SEED = 42", "STORES = [", "TEMPLATES = {", "NEEDS = {", "def slot_pairs"]


def load_rules(with_assistant=False):
    """with_assistant=True 면 가상 DB 와 Assistant 클래스(응답 문장 만들기)까지 불러온다."""
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
    finally:
        os.chdir(cwd)
    return ns


if __name__ == "__main__":
    R = load_rules()
    print(R["resolve"]({"fn": "report_issue", "item": "우유", "issue": "파손", "qty": 2}, R["CURRENT_STORE"]))
