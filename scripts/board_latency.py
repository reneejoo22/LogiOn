"""음성 한 번 처리에 단계마다 몇 ms 걸리는지 잰다: STT(SenseVoice) / 의도분류(ONNX) / LLM / 응답 만들기 / TTS(VITS).

보드(또는 모델이 설치된 PC)에서 실행한다. 필요한 것:
  pip install sherpa-onnx soundfile onnxruntime tokenizers numpy pandas requests
  - SenseVoice 폴더 (--sv-dir)   : model.int8.onnx, tokens.txt
  - VITS TTS 모델 (--tts-model, --tts-tokens, [--tts-lexicon], [--tts-data-dir])
  - 의도분류 ONNX (--intent-dir, 기본 export/intent_onnx)
  - 보드 LLM 서버 (--base-url), 없으면 LLM 단계는 "미측정" 으로 표시

입력 음성:
  --wav-dir 폴더가 있으면 그 안의 *.wav (16kHz 권장) 를 사용 -> 실제 녹음 기준.
  없으면 test 문장 20개를 TTS 로 합성해서 STT 에 넣음 -> **합성 음성 기준** (결과 JSON 에 source 로 기록).
  합성음은 실제 기사님 목소리/소음과 달라 STT 정확도·시간이 실제보다 좋게 나올 수 있다.

예:
  python scripts/board_latency.py --sv-dir ~/voice/models/sherpa-onnx-sense-voice-... --tts-model ~/voice/models/vits/model.onnx \
      --tts-tokens ~/voice/models/vits/tokens.txt --base-url http://127.0.0.1:8080/v1
결과: results/v2/board/latency_summary.json, latency_rows.csv
"""
import argparse, glob, json, os, sys, time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nb_rules import load_rules, ROOT

ap = argparse.ArgumentParser()
ap.add_argument("--sv-dir", default="")
ap.add_argument("--tts-model", default="")
ap.add_argument("--tts-tokens", default="")
ap.add_argument("--tts-lexicon", default="")
ap.add_argument("--tts-data-dir", default="")
ap.add_argument("--intent-dir", default=f"{ROOT}/export/intent_onnx")
ap.add_argument("--base-url", default=os.environ.get("BOARD_LLM_URL", ""))
ap.add_argument("--model", default=os.environ.get("BOARD_LLM_MODEL", "logion"))
ap.add_argument("--wav-dir", default="")
ap.add_argument("--n", type=int, default=20)
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--skip-conf", type=float, default=0.9)
ap.add_argument("--out-dir", default=f"{ROOT}/results/v2/board")
args = ap.parse_args()

missing = []
if not args.sv_dir or not os.path.exists(f"{args.sv_dir}/model.int8.onnx"):
    missing.append("--sv-dir (SenseVoice 폴더: model.int8.onnx, tokens.txt)")
if not args.tts_model or not os.path.exists(args.tts_model):
    missing.append("--tts-model / --tts-tokens (VITS TTS)")
if not os.path.exists(f"{args.intent_dir}/model.int8.onnx"):
    missing.append(f"--intent-dir ({args.intent_dir}/model.int8.onnx; scripts/export_intent_onnx.py 로 만든 폴더)")
if missing:
    sys.exit("필요한 파일이 없어 측정하지 못했습니다:\n  - " + "\n  - ".join(missing))

import requests, soundfile as sf, sherpa_onnx
sys.path.insert(0, args.intent_dir)
from infer import IntentONNX

R = load_rules(with_assistant=True)
SYSTEM_PROMPT, parse_call, resolve, CURRENT_STORE = R["SYSTEM_PROMPT"], R["parse_call"], R["resolve"], R["CURRENT_STORE"]
SKIP_FNS = ("next_stop", "scan", "other")

asr = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=f"{args.sv_dir}/model.int8.onnx", tokens=f"{args.sv_dir}/tokens.txt",
                                                    language="ko", use_itn=True, num_threads=args.threads)
tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
    model=sherpa_onnx.OfflineTtsModelConfig(vits=sherpa_onnx.OfflineTtsVitsModelConfig(
        model=args.tts_model, lexicon=args.tts_lexicon, tokens=args.tts_tokens, data_dir=args.tts_data_dir),
        num_threads=args.threads), max_num_sentences=1))
intent = IntentONNX(args.intent_dir, int8=True, threads=args.threads)
bot = R["Assistant"](current_store=CURRENT_STORE)


def run_stt(samples, sr):
    t0 = time.perf_counter()
    s = asr.create_stream()
    s.accept_waveform(sr, samples)
    asr.decode_stream(s)
    return s.result.text.strip(), (time.perf_counter() - t0) * 1000


def run_tts(text):
    t0 = time.perf_counter()
    a = tts.generate(text, sid=0, speed=1.0)
    ms = (time.perf_counter() - t0) * 1000
    return np.array(a.samples, dtype=np.float32), a.sample_rate, ms


def run_llm(text):
    if not args.base_url:
        return None, None
    payload = {"model": args.model, "temperature": 0, "top_k": 1, "max_tokens": 64, "stream": False,
               "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]}
    t0 = time.perf_counter()
    try:
        r = requests.post(f"{args.base_url.rstrip('/')}/chat/completions", json=payload, timeout=60)
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(요청 실패: {e})", (time.perf_counter() - t0) * 1000
    return out, (time.perf_counter() - t0) * 1000


# ---- 입력 음성 준비 ----
inputs = []                      # (reference_text or None, samples, sr, tts_ms or None)
if args.wav_dir:
    source = f"실제 녹음 {args.wav_dir}"
    for p in sorted(glob.glob(f"{args.wav_dir}/*.wav"))[:args.n]:
        a, sr = sf.read(p, dtype="float32")
        inputs.append((None, a.mean(axis=1) if a.ndim > 1 else a, sr, None))
else:
    source = "합성 음성 (test 문장을 보드 TTS 로 만들어 STT 에 입력) - 실제 녹음 아님"
    te = pd.read_csv(f"{ROOT}/data/fc_dataset.csv")
    te = te[(te.split == "test") & (te.source == "template")].sample(args.n, random_state=0)
    for t in te.text:
        a, sr, _ = run_tts(t)
        inputs.append((t, a, sr, None))
if not inputs:
    sys.exit("입력 음성이 없습니다.")

run_stt(inputs[0][1], inputs[0][2])                       # 예열 (첫 호출은 느림)
rows = []
for ref, a, sr, _ in inputs:
    text, stt_ms = run_stt(a, sr)
    t0 = time.perf_counter()
    r = intent.predict(text)
    intent_ms = (time.perf_counter() - t0) * 1000
    use_llm = not (r["top1"] in SKIP_FNS and r["p1"] >= args.skip_conf)
    raw, llm_ms = (run_llm(text) if use_llm else (None, 0.0))
    call = parse_call(raw) if raw else {"fn": r["top1"]}
    t0 = time.perf_counter()
    res = resolve(call, CURRENT_STORE)
    reply = res["ask"] if not res["ok"] else bot.execute(res)
    rule_ms = (time.perf_counter() - t0) * 1000
    wav, tsr, tts_ms = run_tts(reply)
    rows.append({"reference": ref, "stt_text": text, "stt_exact": (ref == text) if ref else None, "intent": r["top1"],
                 "margin": r["margin"], "used_llm": use_llm, "llm_raw": raw, "reply": reply,
                 "stt_ms": stt_ms, "intent_ms": intent_ms, "llm_ms": llm_ms if (use_llm and args.base_url) else None,
                 "rule_ms": rule_ms, "tts_ms": tts_ms, "tts_audio_s": len(wav) / tsr,
                 "tts_rtf": tts_ms / 1000 / (len(wav) / tsr)})
df = pd.DataFrame(rows)


def stat(c):
    x = df[c].dropna()
    return {"n": int(len(x)), "mean": float(x.mean()), "median": float(x.median()), "p95": float(x.quantile(.95))} if len(x) else "미측정"


summary = {"source": source, "n": len(df), "threads": args.threads, "llm": ("미측정(--base-url 없음)" if not args.base_url else args.base_url),
           "stt_ms": stat("stt_ms"), "intent_ms": stat("intent_ms"), "llm_ms(LLM 을 부른 문장만)": stat("llm_ms"),
           "rule_ms": stat("rule_ms"), "tts_ms": stat("tts_ms"), "tts_rtf": stat("tts_rtf"),
           "llm_skip_rate": float(1 - df.used_llm.mean()),
           "stt_exact_match_rate": (float(df.stt_exact.dropna().mean()) if df.stt_exact.notna().any() else "해당 없음(정답 문장 없음)")}
print(json.dumps(summary, ensure_ascii=False, indent=2))
os.makedirs(args.out_dir, exist_ok=True)
df.to_csv(f"{args.out_dir}/latency_rows.csv", index=False, encoding="utf-8-sig")
json.dump(summary, open(f"{args.out_dir}/latency_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("saved ->", args.out_dir)
