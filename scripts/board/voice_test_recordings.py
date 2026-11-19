"""녹음 파일들을 보드 POST /api/assistant/voice 로 보내 인식·응답·시간을 기록하고 응답 음성(wav)을 저장.

    python scripts/board/voice_test_recordings.py --src <녹음 폴더> --out <결과 폴더> \
        [--ffmpeg ffmpeg] [--base http://<보드 IP>:8000]

m4a/mp3 등은 ffmpeg 로 wav 16kHz mono 로 바꿔서 보낸다. 결과: <out>/results.json, in_N.wav, reply_N.wav
(results/board_voice/ 의 표가 이 스크립트로 만든 것)
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

import httpx

ORDER = ["다음어디야", "서울숲점 콜라몇박스야", "우유두개터졌어", "성수연장점납품완료,점장님한테넘겼어", "근처화장실어디야"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--base", default="http://100.82.118.121:8000")
    ap.add_argument("--session", default="voice-test")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    files = [next(a.src.glob(n + ".*")) for n in ORDER if any(a.src.glob(n + ".*"))] or sorted(a.src.iterdir())
    rows = []
    with httpx.Client(timeout=60) as c:
        for i, src in enumerate(files, 1):
            wav = a.out / f"in_{i}.wav"
            subprocess.run([a.ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "16000",
                            "-sample_fmt", "s16", str(wav)], check=True)
            t0 = time.perf_counter()
            r = c.post(f"{a.base}/api/assistant/voice", files={"file": (wav.name, wav.read_bytes(), "audio/wav")},
                       data={"session_id": a.session})
            t_resp = (time.perf_counter() - t0) * 1000
            r.raise_for_status()
            j = r.json()
            audio = c.get(a.base + j["audio_url"])
            audio.raise_for_status()
            t_audio = (time.perf_counter() - t0) * 1000
            (a.out / f"reply_{i}.wav").write_bytes(audio.content)
            j.update(file=src.stem, client_ms=round(t_resp), client_with_audio_ms=round(t_audio),
                     audio_bytes=len(audio.content))
            rows.append(j)
            print(json.dumps(j, ensure_ascii=False))
            time.sleep(1)
    (a.out / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
