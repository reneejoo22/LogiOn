"""보드(RK3588)에서 돌아가는 양자화 LLM(W8A8 RKLLM)을 test 문장으로 평가한다.

보드의 OpenAI 호환 서버(/v1/chat/completions)에 test 431문장을 하나씩 보내고,
  - 같은 SYSTEM_PROMPT 로 요청 (학습·캘리브레이션과 동일)
  - 점수는 노트북과 같은 score_fc 로 계산
  - PC 에서 낸 원본(fp16 병합 모델) 예측(results/v2/test_pred_fc.csv)과 나란히 비교
  - 요청마다 TTFT(첫 글자까지)·전체 시간(ms) 기록

사용 (PC 에서, 보드 서버 주소를 알고 있을 때):
  python scripts/board_eval.py --base-url http://<보드IP>:<포트>/v1 --model <서버가 쓰는 모델 이름>
결과: results/v2/board/{board_eval_summary.json, board_pred_fc.csv, board_vs_pc.csv}

서버 없이 이 스크립트가 돌아가는지만 보려면:  python scripts/board_eval.py --selftest
  (가짜 서버가 정답을 그대로 돌려주는 시험이다. 결과는 results/v2/board/ 에 저장하지 않고 숫자도 성능이 아니다.)
보드 서버 설정은 top_k=1(탐욕), repeat_penalty=1.1, 종료 토큰 <|im_end|>(151645) 로 맞춘다.
"""
import argparse, json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nb_rules import load_rules, ROOT

ap = argparse.ArgumentParser()
ap.add_argument("--base-url", default=os.environ.get("BOARD_LLM_URL", ""), help="예: http://192.168.0.20:8080/v1")
ap.add_argument("--model", default=os.environ.get("BOARD_LLM_MODEL", "logion"))
ap.add_argument("--api-key", default=os.environ.get("BOARD_LLM_KEY", "none"))
ap.add_argument("--fc-csv", default=f"{ROOT}/data/fc_dataset.csv")
ap.add_argument("--pc-pred", default=f"{ROOT}/results/v2/test_pred_fc.csv", help="PC 원본 모델의 test 예측 (노트북이 저장)")
ap.add_argument("--out-dir", default=f"{ROOT}/results/v2/board")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--timeout", type=float, default=60)
ap.add_argument("--selftest", action="store_true")
args = ap.parse_args()

R = load_rules()
SYSTEM_PROMPT, score_fc, parse_call = R["SYSTEM_PROMPT"], R["score_fc"], R["parse_call"]


def start_mock(gold):
    """selftest 용 가짜 OpenAI 호환 서버: 문장에 맞는 정답 JSON 을 한 글자씩 스트리밍."""
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            user = body["messages"][-1]["content"]
            assert body["messages"][0]["content"] == SYSTEM_PROMPT
            text = gold.get(user, '{"fn":"other"}')
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            time.sleep(0.01)
            for ch in [text[i:i + 4] for i in range(0, len(text), 4)]:
                chunk = {"choices": [{"delta": {"content": ch}}]}
                self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def ask_board(base_url, text):
    """한 문장을 보내고 (출력 문자열, ttft_ms, total_ms) 반환. 실패하면 (None, None, None, 오류)."""
    payload = {"model": args.model, "stream": True, "temperature": 0, "top_k": 1, "max_tokens": 64,
               "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]}
    t0 = time.perf_counter()
    ttft, out = None, []
    try:
        with requests.post(f"{base_url.rstrip('/')}/chat/completions", json=payload, stream=True, timeout=args.timeout,
                           headers={"Authorization": f"Bearer {args.api_key}"}) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=False):
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    break
                delta = json.loads(data.decode("utf-8"))["choices"][0].get("delta", {}).get("content") or ""
                if delta and ttft is None:
                    ttft = (time.perf_counter() - t0) * 1000
                out.append(delta)
    except Exception as e:                                             # 요청 실패는 기록하고 계속
        return None, None, (time.perf_counter() - t0) * 1000, f"{type(e).__name__}: {e}"
    return "".join(out).strip(), ttft, (time.perf_counter() - t0) * 1000, ""


df = pd.read_csv(args.fc_csv)
te = df[df.split == "test"].reset_index(drop=True)
if args.limit:
    te = te.head(args.limit)

base_url = args.base_url
if args.selftest:
    srv = start_mock(dict(zip(df.text, df.target)))
    base_url = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    args.out_dir = None
    print("[selftest] 가짜 서버로 시험합니다. 이 숫자는 보드 성능이 아닙니다.")
elif not base_url:
    sys.exit("--base-url 이 없습니다. 보드 LLM 서버 주소를 알려 주세요 (예: --base-url http://<보드IP>:<포트>/v1).\n"
             "서버 없이 코드만 시험하려면 --selftest.")

rows = []
for i, (t, g) in enumerate(zip(te.text, te.target)):
    raw, ttft, total, err = ask_board(base_url, t)
    rows.append({"pred_raw": raw if raw is not None else "", "ttft_ms": ttft, "total_ms": total, "error": err})
    if (i + 1) % 50 == 0:
        print(f"  {i + 1}/{len(te)}", flush=True)
res = pd.DataFrame(rows, index=te.index)
board = pd.concat([te, res], axis=1)
n_err = int((board.error != "").sum())
summ_b, r_b = score_fc(board)
board = pd.concat([board, r_b], axis=1)

summary = {"n": len(board), "request_errors": n_err, "model": args.model, "base_url": "(selftest)" if args.selftest else base_url,
           "board_quantized": {k: float(v) for k, v in summ_b.items()}}
lat = board[board.error == ""]
if len(lat):
    summary["latency_ms"] = {
        "ttft_mean": float(lat.ttft_ms.mean()), "ttft_median": float(lat.ttft_ms.median()), "ttft_p95": float(lat.ttft_ms.quantile(.95)),
        "total_mean": float(lat.total_ms.mean()), "total_median": float(lat.total_ms.median()), "total_p95": float(lat.total_ms.quantile(.95)),
        "note": "PC 에서 요청을 보내 잰 값이라 네트워크 시간 포함. 보드 안에서만의 시간이 아님"}

if os.path.exists(args.pc_pred) and not args.limit:
    pc = pd.read_csv(args.pc_pred)
    pc = pc.set_index("id").loc[board.id]
    summ_p, r_p = score_fc(pc.reset_index())
    same = (board.pred_raw.values == pc.pred_raw.values)
    same_call = [parse_call(a) == parse_call(b) for a, b in zip(board.pred_raw, pc.pred_raw)]
    summary["pc_original"] = {k: float(v) for k, v in summ_p.items()}
    summary["agreement"] = {"raw_string_equal": float(same.mean()), "parsed_json_equal": float(sum(same_call) / len(same_call)),
                            "final_ok_both_right": float((board.final_ok.values & r_p.final_ok.values).mean()),
                            "final_ok_only_pc_right": float((~board.final_ok.values & r_p.final_ok.values).sum()),
                            "final_ok_only_board_right": float((board.final_ok.values & ~r_p.final_ok.values).sum())}
    diff = pd.DataFrame({"id": board.id.values, "text": board.text.values, "gold": board.target.values,
                         "pc_pred": pc.pred_raw.values, "board_pred": board.pred_raw.values,
                         "pc_final_ok": r_p.final_ok.values, "board_final_ok": board.final_ok.values})
    diff = diff[(diff.pc_pred != diff.board_pred)]
    summary["n_prediction_differs"] = len(diff)
else:
    diff = None
    summary["pc_original"] = "비교 파일 없음 또는 --limit 사용"

print(json.dumps(summary, ensure_ascii=False, indent=2))
if args.out_dir:
    os.makedirs(args.out_dir, exist_ok=True)
    board.to_csv(f"{args.out_dir}/board_pred_fc.csv", index=False, encoding="utf-8-sig")
    if diff is not None:
        diff.to_csv(f"{args.out_dir}/board_vs_pc.csv", index=False, encoding="utf-8-sig")
    json.dump(summary, open(f"{args.out_dir}/board_eval_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved ->", args.out_dir)
