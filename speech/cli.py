"""아무 텍스트/음성에 STT·TTS 를 돌려 보는 명령줄 도구.

저장소 루트(LogiOn\\)에서:
  python speech/cli.py tts "다음 배송지는 서울숲점입니다." -o out.wav
  python speech/cli.py stt out.wav
  python speech/cli.py stt long_recording.wav --vad      # 긴 녹음: 말한 구간별로
  python speech/cli.py roundtrip "우유 두 개 터졌어"        # TTS → STT 로 되돌려 비교
  python speech/cli.py bench                              # 단계별 ms 측정
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from speech.speech_engine import SAMPLE_RATE, SpeechConfig, SpeechEngine, resample  # noqa: E402

BENCH_SENTENCES = ["다음 어디야", "서울숲점 콜라 몇 박스야", "우유 두 개 터졌어", "성수연무장점 납품 완료"]


def main() -> None:
    for s in (sys.stdout, sys.stderr):  # Windows 콘솔(cp949) 한글 깨짐 방지
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap =argparse.ArgumentParser(description="sherpa-onnx STT/TTS")
    ap.add_argument("--threads", type=int, default=None, help="STT/TTS 스레드 수")
    ap.add_argument("--speed", type=float, default=1.0, help="TTS 속도")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tts"); p.add_argument("text"); p.add_argument("-o", "--out", default="tts_out.wav")
    p = sub.add_parser("stt"); p.add_argument("wav"); p.add_argument("--vad", action="store_true")
    p = sub.add_parser("roundtrip"); p.add_argument("text"); p.add_argument("-o", "--out", default=None)
    sub.add_parser("bench")
    a = ap.parse_args()

    cfg = SpeechConfig(tts_speed=a.speed)
    if a.threads:
        cfg.num_threads_stt = cfg.num_threads_tts = a.threads
    eng = SpeechEngine(cfg)

    if a.cmd == "tts":
        r = eng.tts_to_file(a.text, a.out)
        print(f"{a.out}  ({len(r.samples) / r.sample_rate:.2f}s 음성, 합성 {r.elapsed_ms:.0f}ms, 문장 {len(r.sentences)}개)")

    elif a.cmd == "stt":
        t0 = time.perf_counter()
        if a.vad:
            for st, en, text in eng.stt_long(a.wav):
                print(f"[{st:6.2f} ~ {en:6.2f}] {text}")
        else:
            print(eng.stt_file(a.wav))
        print(f"({(time.perf_counter() - t0) * 1000:.0f}ms)", file=sys.stderr)

    elif a.cmd == "roundtrip":
        r = eng.synthesize(a.text)
        if a.out:
            import soundfile as sf
            sf.write(a.out, r.samples, r.sample_rate, subtype="PCM_16")
        t0 = time.perf_counter()
        heard = eng.stt_samples(resample(r.samples, r.sample_rate, SAMPLE_RATE))
        print(f"입력 : {a.text}\nTTS  : {r.elapsed_ms:.0f}ms\nSTT  : {heard}  ({(time.perf_counter() - t0) * 1000:.0f}ms)")

    elif a.cmd == "bench":
        _ = eng.stt, eng.tts  # 로딩 시간은 빼고 측정
        print(f"{'문장':<16} {'TTS ms':>7} {'음성 s':>6} {'STT ms':>7}  STT 결과")
        for s in BENCH_SENTENCES:
            r = eng.synthesize(s)
            t0 = time.perf_counter()
            heard = eng.stt_samples(resample(r.samples, r.sample_rate, SAMPLE_RATE))
            ms = (time.perf_counter() - t0) * 1000
            print(f"{s:<16} {r.elapsed_ms:7.0f} {len(r.samples) / r.sample_rate:6.2f} {ms:7.0f}  {heard}")


if __name__ == "__main__":
    main()
