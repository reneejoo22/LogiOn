"""음성 비서 (보드에서 STT·TTS 까지). POST /api/assistant/voice 가 쓰는 곳.

폰은 녹음 파일만 올리고, 보드가 STT(SenseVoice) → /chat 과 같은 파이프라인(LLM, NPU) → TTS(VITS) 를 다 한다.
STT·TTS 는 CPU (강의 기준 스레드 STT 4, TTS 2), NPU 는 LLM 전용.
응답 음성은 메모리에 잠깐 들고 있다가 GET /api/assistant/voice/audio/{id} 로 내려준다.
"""
import io
import re
import logging
import os
import sys
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import numpy as np

REPO_DIR = Path(__file__).resolve().parents[3]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

log = logging.getLogger(__name__)

NOT_HEARD = "잘 못 들었어요. 다시 말씀해 주세요."
AUDIO_KEEP = 32          # 최근 응답 음성 몇 개를 들고 있을지
AUDIO_TTL = 600          # 초. 이보다 오래된 응답 음성은 버린다
SHORT_REPLY_PEAK = 0.05  # 이보다 큰 소리가 있어야 VAD 없이 인식해 봄 (조용한 녹음은 그대로 '못 들음')
MAX_SECONDS = 15         # 이보다 긴 녹음은 앞 15초만 (한 문장 명령용)


class AudioError(ValueError):
    """올라온 파일을 음성으로 읽지 못함 → 415."""


class VoiceService:
    def __init__(self, engine):
        self.engine = engine
        self.stt_lock = threading.Lock()   # sherpa 객체 하나를 요청끼리 나눠 쓰므로 한 번에 하나씩
        self.tts_lock = threading.Lock()
        self.audio: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self.audio_lock = threading.Lock()

    # ---------------- 입력: 파일 → 16kHz mono float32 ----------------
    @staticmethod
    def decode(data: bytes) -> tuple[np.ndarray, int]:
        import soundfile as sf

        from speech.speech_engine import SAMPLE_RATE, resample

        try:
            x, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
        except Exception as e:  # m4a/mp3 등 libsndfile 이 못 읽는 형식
            raise AudioError(f"음성 파일을 읽지 못했습니다 (wav 16kHz mono 권장): {e}") from e
        x = x.mean(axis=1)
        x = x[: int(MAX_SECONDS * sr)]
        return resample(x, sr, SAMPLE_RATE), sr

    # ---------------- STT ----------------
    def transcribe(self, samples: np.ndarray) -> str:
        with self.stt_lock:
            speech = self.engine.trim_silence(samples)
            if len(speech) >= 1600:  # 0.1초 이상 말이 있음
                return self.engine.stt_samples(speech)
            # VAD 는 0.25초보다 짧은 말을 버린다. "네"·"응" 같은 한 음절 대답(납품 완료 되묻기)이 여기 걸리므로,
            # 짧은 녹음(4초 이하)에 소리가 분명히 있으면 통째로 한 번 인식해 본다
            if len(samples) <= 4 * 16000 and float(np.abs(samples).max(initial=0)) >= SHORT_REPLY_PEAK:
                return self.engine.stt_samples(samples)
            return ""

    # ---------------- TTS ----------------
    def synthesize(self, text: str) -> tuple[str | None, float]:
        """응답 문장 → wav 저장, (audio id, 걸린 ms)."""
        import soundfile as sf

        if not text:
            return None, 0.0
        with self.tts_lock:
            r = self.engine.synthesize(text)
        buf = io.BytesIO()
        sf.write(buf, r.samples, r.sample_rate, format="WAV", subtype="PCM_16")
        audio_id = uuid.uuid4().hex
        now = time.time()
        with self.audio_lock:
            for k in [k for k, (t, _) in self.audio.items() if now - t > AUDIO_TTL]:
                del self.audio[k]
            self.audio[audio_id] = (now, buf.getvalue())
            while len(self.audio) > AUDIO_KEEP:
                self.audio.popitem(last=False)
        return audio_id, r.elapsed_ms

    def get_audio(self, audio_id: str) -> bytes | None:
        with self.audio_lock:
            item = self.audio.get(audio_id)
        return item[1] if item else None

    # ---------------- 요청 하나 ----------------
    def handle(self, data: bytes, chat) -> dict:
        """chat(text) -> /chat 과 같은 응답 dict."""
        t_all = time.perf_counter()
        samples, sr = self.decode(data)

        t0 = time.perf_counter()
        text = self.transcribe(samples)
        if not re.sub(r"[\W_]+", "", text):   # "." 처럼 글자 없이 문장부호만 = 못 들음
            text = ""
        stt_ms = (time.perf_counter() - t0) * 1000

        llm_ms = 0.0
        if text:
            t0 = time.perf_counter()
            resp = chat(text)
            llm_ms = (time.perf_counter() - t0) * 1000
        else:
            resp = {"reply": NOT_HEARD, "fn": None, "call": {}, "route": "not_heard", "ask": None,
                    "options": None, "action": None, "stop_id": None, "conf": 0.0}
        resp.pop("latency_ms", None)
        fixed = resp.pop("text_fixed", None)    # STT 오인식 별칭으로 고친 말 ("정자님" → "점장님")

        audio_id, tts_ms = self.synthesize(resp["reply"])
        total_ms = (time.perf_counter() - t_all) * 1000
        return {
            "text": fixed or text,
            "stt_text": text,
            **resp,
            "latency": {"stt": round(stt_ms), "llm": round(llm_ms), "tts": round(tts_ms), "total": round(total_ms)},
            "audio_url": f"/api/assistant/voice/audio/{audio_id}" if audio_id else None,
            "input": {"sample_rate": sr, "seconds": round(len(samples) / 16000, 2)},
        }


def load_voice() -> tuple[VoiceService | None, str | None]:
    """서버 시작 때 한 번. 못 올리면 (None, 이유): /voice 만 503, /chat·화면 API 는 그대로."""
    if os.environ.get("LOGION_VOICE", "1") == "0":
        return None, "LOGION_VOICE=0 으로 꺼 두었습니다."
    try:
        from speech.speech_engine import SpeechEngine

        t0 = time.perf_counter()
        eng = SpeechEngine()
        eng.load_all()
    except Exception as e:  # sherpa-onnx 미설치, 모델 없음 등
        log.warning("STT/TTS 를 올리지 못했습니다. /voice 만 꺼집니다: %s", e)
        return None, str(e)
    log.warning("STT/TTS 준비됨 (%s, %.1fs)", eng.cfg.models_dir, time.perf_counter() - t0)
    return VoiceService(eng), None
