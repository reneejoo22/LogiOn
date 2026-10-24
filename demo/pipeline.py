"""음성 비서 파이프라인 (추론 전용). 채팅 데모 서버가 쓰는 부분.

한 문장이 거치는 단계는 notebooks/LogiOn_demo_pipeline.ipynb 와 같습니다.
노트북은 단계를 눈으로 보여 주려고 코드를 펼쳐 둔 것이고, 이 파일은 서버가 import 해서 쓰는 쪽입니다.

  from pipeline import Assistant
  bot = Assistant()                 # config/pipeline_v2_1.json 을 읽어 모델을 올림
  bot.run("다음 어디야")             # -> dict (응답 + 단계별 기록)

모델(out/intent_model, out/fc_merged)이 없으면 ModelsMissing 을 냅니다.
값 보정은 backend/app/db/seed.py 의 점포·품목을 읽어 씁니다 (백엔드 코드는 고치지 않음).
"""
import difflib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNITS = ["개", "박스", "판", "봉지"]
ORD_WORDS = {0: ["첫", "1번", "하나", "처음", "앞"], 1: ["두", "2번", "둘", "뒤", "나중"]}
CHOICE_KW = {
    "next_stop": ["배송지", "다음", "남은곳", "행선지"],
    "stop_items": ["물건", "품목", "내릴", "물량"],
    "report_issue": ["문제", "이상", "보고", "파손"],
    "complete": ["완료", "납품완료", "끝"],
    "scan": ["스캔", "바코드", "찍"],
}
ALLOWED_BY_FN = {
    "stop_items": {"store", "item"},
    "complete": {"store", "receiver"},
    "report_issue": {"store", "item", "issue", "qty", "unit"},
}


class ModelsMissing(RuntimeError):
    pass


def _flat(s):
    return str(s).replace(" ", "")


def josa(word, with_batchim, without_batchim):
    if not word:
        return without_batchim
    ch = word[-1]
    if "가" <= ch <= "힣":
        return with_batchim if (ord(ch) - 0xAC00) % 28 else without_batchim
    return without_batchim


def load_seed():
    """backend/app/db/seed.py 의 점포·품목·오늘 운행을 읽어 메모리 DB 로 만든다 (읽기만 함)."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.db import seed as SEED

    stores = [{"id": i, "name": n, "short_name": sn} for i, n, sn, *_ in SEED.STORES]
    products = [{"id": i, "name": n, "category": c,
                 "aliases": sorted({f.replace(" ", "") for f in forms})}
                for i, (n, (c, forms)) in enumerate(SEED.PRODUCTS.items(), start=1)]
    pid = {p["name"]: p["id"] for p in products}
    stops = []
    for seq, (store_id, eta, _km, _notice, _zones, items) in enumerate(SEED.ROUTE_STOPS, start=1):
        stops.append({
            "id": seq, "seq": seq, "eta": eta, "status": "pending", "receiver": None,
            "store": next(s for s in stores if s["id"] == store_id),
            "items": [{"product_id": pid[n], "name": n, "qty": q, "unit": u} for n, q, u in items],
            "issues": [],
        })
    return stores, products, stops


class Assistant:
    def __init__(self, config_path=None, load_models=True):
        self.cfg = json.loads((Path(config_path or ROOT / "config/pipeline_v2_1.json")).read_text(encoding="utf-8"))
        self.stores, self.products, self.stops = load_seed()
        self.pending = {}
        self.device = "cpu"
        self.device_name = ""
        self.models_loaded = False
        if load_models:
            self._load_models()

    # ---------------- 모델 ----------------
    def _load_models(self):
        intent_dir = ROOT / self.cfg["intent_model"]
        fc_dir = ROOT / self.cfg["fc_model"]
        missing = [str(p.relative_to(ROOT)) for p in (intent_dir, fc_dir) if not (p / "config.json").exists()]
        if missing:
            raise ModelsMissing(
                "모델이 없습니다: " + ", ".join(missing)
                + "\n먼저 notebooks/LogiOn_AI_pipeline.ipynb 를 실행해 모델을 만드세요 (GPU 필요, 약 40분).")
        import torch
        from transformers import AutoModelForSequenceClassification, AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device_name = torch.cuda.get_device_name(0) if self.device == "cuda" else "CPU"
        dtype = (torch.bfloat16 if self.device == "cuda" and torch.cuda.is_bf16_supported() else torch.float16)

        self.intent_tok = AutoTokenizer.from_pretrained(intent_dir)
        self.intent_model = AutoModelForSequenceClassification.from_pretrained(intent_dir).eval().to(self.device)
        self.intent_model.config.torchscript = False
        self.fc_tok = AutoTokenizer.from_pretrained(fc_dir)
        if self.fc_tok.pad_token is None:
            self.fc_tok.pad_token = self.fc_tok.eos_token
        self.fc_model = AutoModelForCausalLM.from_pretrained(
            fc_dir, torch_dtype=dtype, device_map=({"": 0} if self.device == "cuda" else None)).eval()
        if self.device == "cpu":
            self.fc_model = self.fc_model.to("cpu")
        self.id2label = dict(enumerate(self.cfg["funcs"]))
        self.models_loaded = True

    def classify(self, text):
        import numpy as np
        with self.torch.no_grad():
            enc = self.intent_tok([text], truncation=True, max_length=64, return_tensors="pt").to(self.device)
            p = self.intent_model(**enc).logits.float().softmax(-1)[0].cpu().numpy()
        order = np.argsort(-p)
        return [(self.id2label[int(i)], float(p[i])) for i in order]

    def call_llm(self, text):
        """LLM 출력 문자열과 생성 토큰 확률의 평균·최솟값."""
        import numpy as np
        prompt = self.fc_tok.apply_chat_template(
            [{"role": "system", "content": self.cfg["system_prompt"]}, {"role": "user", "content": text}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        with self.torch.no_grad():
            enc = self.fc_tok([prompt], return_tensors="pt", add_special_tokens=False).to(self.fc_model.device)
            out = self.fc_model.generate(
                **enc, max_new_tokens=self.cfg["generation"]["max_new_tokens"], do_sample=False,
                pad_token_id=self.fc_tok.pad_token_id, return_dict_in_generate=True, output_scores=True)
        new = out.sequences[0, enc["input_ids"].shape[1]:]
        probs = [float(self.torch.softmax(s[0].float(), -1)[t]) for s, t in zip(out.scores, new)]
        raw = self.fc_tok.decode(new, skip_special_tokens=True).strip()
        return raw, (float(np.mean(probs)) if probs else 0.0), (float(np.min(probs)) if probs else 0.0)

    # ---------------- 갈림길 ----------------
    def decide(self, ranked):
        (f1, p1), (f2, p2) = ranked[0], ranked[1]
        margin = p1 - p2
        tau, conf = self.cfg["ask_tau"], self.cfg["skip_llm_conf"]
        if margin < tau:
            if "other" in (f1, f2):
                return {"route": "ask", "opts": [], "msg": self.cfg["retry_message"], "margin": margin,
                        "why": f"margin {margin:.3f} < {tau} 이고 후보에 other 가 있어 선택지를 만들 수 없음"}
            L = self.cfg["choice_labels"]
            return {"route": "ask", "opts": [f1, f2], "margin": margin,
                    "msg": f"{L[f1]} 말씀하시는 건가요, {L[f2]} 말씀하시는 건가요?",
                    "why": f"margin {margin:.3f} < {tau} 이라 1등을 믿을 수 없음"}
        if f1 in self.cfg["skip_llm_fns"] and p1 >= conf:
            return {"route": "skip", "fn": f1, "margin": margin,
                    "why": f"{f1} 은 값이 필요 없고 확률 {p1:.3f} ≥ {conf} 이라 LLM 생략"}
        return {"route": "llm", "fn": f1, "margin": margin,
                "why": (f"{f1} 은 값을 뽑아야 하므로 LLM 으로" if f1 not in self.cfg["skip_llm_fns"]
                        else f"{f1} 이지만 확률 {p1:.3f} < {conf} 이라 LLM 으로 확인")}

    # ---------------- 값 보정 ----------------
    def next_stop(self):
        return next((s for s in self.stops if s["status"] == "pending"), None)

    @staticmethod
    def match_name(spoken, rows, name_keys, alias_key=None, cutoff=0.6):
        q = _flat(spoken)
        hits = [r for r in rows if any(_flat(r[k]) == q for k in name_keys)]
        if hits:
            return hits, "정확", 1.0
        if alias_key:
            hits = [r for r in rows if q in r[alias_key]]
            if hits:
                return hits, "별칭", 1.0
        hits = [r for r in rows if any(q in _flat(r[k]) or _flat(r[k]) in q for k in name_keys)]
        if hits:
            return hits, "포함", 1.0
        scored = sorted(((max(difflib.SequenceMatcher(None, q, _flat(r[k])).ratio() for k in name_keys), r)
                         for r in rows), key=lambda x: -x[0])
        if scored and scored[0][0] >= cutoff:
            best = scored[0][0]
            return [r for s, r in scored if s >= best - 1e-9], "발음 유사도", best
        return [], "못 찾음", (scored[0][0] if scored else 0.0)

    def resolve(self, call, steps):
        out = dict(call)
        out.pop("_bad", None)
        fn = out.get("fn")
        if out.get("store"):
            rows, how, score = self.match_name(out["store"], self.stores, ["name", "short_name"])
            cands = [r["name"] for r in rows]
            steps.append({"slot": "store", "spoken": out["store"], "found": cands[0] if len(rows) == 1 else "—",
                          "how": how, "score": round(score, 3), "cands": cands})
            if len(rows) == 1:
                stop = next((s for s in self.stops if s["store"]["id"] == rows[0]["id"]), None)
                if stop is None:
                    return out, f"{rows[0]['name']}은 오늘 배송지에 없어요.", []
                out["_stop"] = stop
            elif len(rows) > 1:
                return out, "어느 점포 말씀이신가요? " + ", ".join(cands), cands
            else:
                return out, f"'{out['store']}'이라는 점포를 찾지 못했어요.", []
        else:
            stop = self.next_stop()
            steps.append({"slot": "store", "spoken": "(말하지 않음)",
                          "found": stop["store"]["name"] if stop else "—",
                          "how": "다음 배송지로 채움", "score": "—", "cands": []})
            if stop is None and fn in ("stop_items", "complete", "report_issue"):
                return out, "오늘 배송이 모두 끝났어요.", []
            out["_stop"] = stop

        if out.get("item"):
            rows, how, score = self.match_name(out["item"], self.products, ["name"], alias_key="aliases")
            cands = [r["name"] for r in rows]
            steps.append({"slot": "item", "spoken": out["item"], "found": cands[0] if len(rows) == 1 else "—",
                          "how": how, "score": round(score, 3), "cands": cands})
            if len(rows) == 1:
                out["item"], out["product_id"] = rows[0]["name"], rows[0]["id"]
            elif len(rows) > 1:
                return out, ", ".join(cands) + " 중 어떤 건가요?", cands
            else:
                return out, f"'{out['item']}'이라는 품목을 찾지 못했어요.", []

        if out.get("qty") is not None and out.get("unit") not in UNITS:
            u = out.get("unit")
            new = "개" if not u else min(UNITS, key=lambda x: -difflib.SequenceMatcher(None, u, x).ratio())
            steps.append({"slot": "unit", "spoken": u or "(말하지 않음)", "found": new,
                          "how": "기본값 개" if not u else "가장 가까운 단위", "score": "—", "cands": UNITS})
            out["unit"] = new

        if fn == "report_issue":
            if not out.get("item"):
                return out, "어떤 품목인가요?", []
            if not out.get("issue"):
                return out, "어떤 문제인가요? 파손, 수량부족, 오배송, 온도이상 중에서 말씀해 주세요.", list("파손 수량부족 오배송 온도이상".split())
        return out, None, []

    # ---------------- 실행 ----------------
    @staticmethod
    def build_request(fn, call):
        stop = call.get("_stop")
        sid = stop["id"] if stop else None
        if fn == "next_stop":
            return {"method": "GET", "path": "/api/routes/today", "body": None}
        if fn == "stop_items":
            return {"method": "GET", "path": f"/api/stops/{sid}", "body": None}
        if fn == "complete":
            return {"method": "POST", "path": f"/api/stops/{sid}/complete", "body": {"receiver": call.get("receiver")}}
        if fn == "report_issue":
            body = {"type": call.get("issue"), "source": "voice"}        # issue -> type
            if call.get("product_id"):
                body["product_id"] = call["product_id"]                   # 이름 -> 숫자
            if call.get("qty") is not None:
                body["qty"], body["unit"] = call["qty"], call.get("unit")
            return {"method": "POST", "path": f"/api/stops/{sid}/issues", "body": body}
        return {"method": None, "path": None, "body": None}

    def run_virtual(self, fn, call, req):
        stop = call.get("_stop")
        if fn == "next_stop":
            left = [s for s in self.stops if s["status"] == "pending"]
            return {"next_store": left[0]["store"]["name"] if left else None, "remaining": len(left)}
        if fn == "stop_items":
            items = stop["items"]
            if call.get("item"):
                items = [i for i in items if i["name"] == call["item"]]
            return {"store": stop["store"]["name"], "items": items}
        if fn == "complete":
            stop["status"], stop["receiver"] = "done", call.get("receiver")
            return {"store": stop["store"]["name"], "receiver": stop["receiver"]}
        if fn == "report_issue":
            issue = dict(req["body"], id=len(stop["issues"]) + 1, product_name=call.get("item"))
            stop["issues"].append(issue)
            return issue
        if fn == "scan":
            return {"action": "open_scanner"}
        return {}

    def make_reply(self, fn, call, result):
        if fn == "next_stop":
            return (f"다음은 {result['next_store']}이에요. 남은 곳은 {result['remaining']}곳이에요."
                    if result["next_store"] else "오늘 배송이 모두 끝났어요.")
        if fn == "stop_items":
            items, store = result["items"], result["store"]
            if call.get("item"):
                if not items:
                    return f"{store}에 {call['item']}{josa(call['item'], '은', '는')} 없어요."
                i = items[0]
                return f"{store} {i['name']}{josa(i['name'], '은', '는')} {i['qty']}{i['unit']}예요."
            if not items:
                return f"{store}에 내릴 물건이 없어요."
            return f"{store} 납품은 " + ", ".join(f"{i['name']} {i['qty']}{i['unit']}" for i in items) + "예요."
        if fn == "complete":
            r = result.get("receiver")
            return f"{result['store']} 납품 완료로 기록했어요." + (f" 인수자는 {r}이에요." if r else "")
        if fn == "report_issue":
            qty = f" {result['qty']}{result['unit']}" if result.get("qty") else ""
            return (f"{call['_stop']['store']['name']} {result.get('product_name') or '품목 미상'}"
                    f"{qty} {result['type']}으로 기록했어요.")
        if fn == "scan":
            return "스캔 화면을 열게요."
        return "죄송해요, 배송 업무만 도와드릴 수 있어요."

    # ---------------- 되묻기 이어받기 ----------------
    def match_choice(self, text):
        if self.pending.get("kind") != "choice":
            return None
        t = _flat(text)
        for fn in self.pending["opts"]:
            if any(k in t for k in CHOICE_KW.get(fn, [])):
                return fn
        label2fn = {_flat(self.cfg["choice_labels"][f]): f for f in self.pending["opts"]}
        if t in label2fn:
            return label2fn[t]
        for i, words in ORD_WORDS.items():
            if any(w in t for w in words) and i < len(self.pending["opts"]):
                return self.pending["opts"][i]
        return None

    @staticmethod
    def parse_json(raw):
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {"_bad": True}
        try:
            d = json.loads(m.group(0))
            return d if isinstance(d, dict) else {"_bad": True}
        except Exception:
            return {"_bad": True}

    # ---------------- 전체 ----------------
    def run(self, text):
        t_all = time.perf_counter()
        T, trace = {}, {"text": text, "carry": None}
        picked = self.match_choice(text)
        carry = None

        if picked:
            carry = "choice"
            trace["carry"] = f"직전 선택지 되묻기의 답 → 기능을 {picked} 로 고정하고 원래 문장('{self.pending['text']}')을 다시 처리"
        elif self.pending.get("kind") == "slot":
            cands = self.pending.get("options") or []
            q = _flat(text)
            if [c for c in cands if _flat(c) == q or (q and q in _flat(c))] or (not cands and len(text) <= 12):
                carry = "slot"
                trace["carry"] = f"직전 질문의 답 → 모자랐던 값 '{self.pending['missing']}' 에 채움"

        if carry == "slot":
            call = dict(self.pending["call"])
            call[self.pending["missing"]] = text.strip()
            fn = call["fn"]
            trace["intent"] = None
            trace["llm"] = None
        else:
            src = self.pending["text"] if carry == "choice" else text
            t = time.perf_counter()
            ranked = self.classify(src)
            T["의도분류"] = (time.perf_counter() - t) * 1000
            d = self.decide(ranked)
            trace["intent"] = {"top3": [{"fn": f, "p": p} for f, p in ranked[:3]], "margin": d["margin"],
                               "route": d["route"], "why": d["why"]}

            if d["route"] == "ask" and carry != "choice":
                self.pending = {"kind": "choice", "opts": d["opts"], "text": text}
                T["전체"] = (time.perf_counter() - t_all) * 1000
                trace.update(llm=None, resolve=[], request=None, reply=d["msg"], route="ask",
                             options=[self.cfg["choice_labels"][o] for o in d["opts"]], timings=T)
                return trace

            if d["route"] == "skip":
                fn, call = d["fn"], {"fn": d["fn"]}
                trace["llm"] = {"skipped": True, "why": d["why"]}
            else:
                t = time.perf_counter()
                raw, cmean, cmin = self.call_llm(src)
                T["LLM"] = (time.perf_counter() - t) * 1000
                call = self.parse_json(raw)
                if carry == "choice":
                    fn = picked
                    call = {"fn": fn, **{k: v for k, v in call.items() if k in ALLOWED_BY_FN.get(fn, set())}}
                else:
                    fn = call.get("fn", d["fn"])
                trace["llm"] = {"skipped": False, "raw": raw, "parsed": call, "conf_mean": cmean, "conf_min": cmin}
        self.pending = {}

        t = time.perf_counter()
        steps = []
        if fn in ("scan", "other"):
            call2, ask, opts = dict(call), None, []
            call2["_stop"] = self.next_stop()
        else:
            call2, ask, opts = self.resolve(call, steps)
        T["값 보정"] = (time.perf_counter() - t) * 1000
        trace["resolve"] = steps

        if ask:
            miss = "item" if "품목" in ask else ("issue" if "문제" in ask else "store")
            self.pending = {"kind": "slot", "missing": miss, "options": opts,
                            "call": {k: v for k, v in call2.items() if k != "_stop"}}
            T["전체"] = (time.perf_counter() - t_all) * 1000
            trace.update(request=None, reply=ask, route="ask_slot", options=opts, timings=T, fn=fn)
            return trace

        req = self.build_request(fn, call2)
        t = time.perf_counter()
        result = self.run_virtual(fn, call2, req)
        T["실행"] = (time.perf_counter() - t) * 1000
        reply = self.make_reply(fn, call2, result)
        T["전체"] = (time.perf_counter() - t_all) * 1000
        trace.update(request=req, reply=reply, route=trace.get("intent", {}).get("route") if trace.get("intent") else "carry",
                     options=[], timings=T, fn=fn)
        return trace
