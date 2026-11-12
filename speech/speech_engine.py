"""sherpa-onnx 기반 STT/TTS 엔진 (PC/보드 공용).

강의 자료(마음AI 특강3) 와 같은 구성:
  VAD  : silero_vad.onnx            — 말한 구간만 잘라 냄
  STT  : SenseVoice-Small int8      — 비자동회귀, 한국어 지원, use_itn 으로 "두 개" → "2개"
  TTS  : 한국어 VITS (mimic3 kss)   — 문장 단위로 나눠 생성해 첫 소리까지 지연을 줄임

어떤 텍스트/오디오에도 쓸 수 있게 프로젝트 코드와 분리했습니다.

    from speech.speech_engine import SpeechEngine
    eng = SpeechEngine()                       # speech/models 에서 모델을 찾음
    text = eng.stt_file("hello.wav")           # 음성 → 글자
    eng.tts_to_file("안녕하세요.", "out.wav")    # 글자 → 음성
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import sherpa_onnx
import soundfile as sf

MODELS_DIR = Path(__file__).resolve().parent / "models"
STT_DIR = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
TTS_DIR = "vits-mimic3-ko_KO-kss_low"
VAD_FILE = "silero_vad.onnx"
SAMPLE_RATE = 16000  # STT/VAD 입력 샘플레이트


@dataclass
class SpeechConfig:
    models_dir: Path = MODELS_DIR
    num_threads_stt: int = 4      # 강의: stt 스레드 4
    num_threads_tts: int = 2      # 강의: numThreads = 2
    num_threads_vad: int = 1      # 강의: vad 스레드 1
    language: str = "ko"          # SenseVoice 언어 (auto 도 가능)
    use_itn: bool = True          # 숫자/기호 정규화
    tts_speed: float = 1.0
    tts_sid: int = 0
    # VAD 기준값 (강의 Vad.kt 설정과 동일한 의미)
    vad_threshold: float = 0.5
    vad_min_silence: float = 0.5  # 말이 끝났다고 볼 침묵(초)
    vad_min_speech: float = 0.25  # 이보다 짧으면 무시(초)


@dataclass
class TtsResult:
    samples: np.ndarray
    sample_rate: int
    elapsed_ms: float
    sentences: list[str] = field(default_factory=list)


def split_sentences(text: str) -> list[str]:
    """TTS 지연을 줄이려고 문장 단위로 나눔 (강의 p.24 와 같은 방식)."""
    parts = re.split(r"(?<=[.!?。？！])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


class SpeechEngine:
    """STT/TTS/VAD 를 필요할 때 한 번만 로딩해 재사용."""

    def __init__(self, config: SpeechConfig | None = None):
        self.cfg = config or SpeechConfig()
        self._stt: sherpa_onnx.OfflineRecognizer | None = None
        self._tts: sherpa_onnx.OfflineTts | None = None

    # ------------------------------------------------------------ 경로
    def _path(self, *parts: str) -> str:
        p = Path(self.cfg.models_dir, *parts)
        if not p.exists():
            raise FileNotFoundError(
                f"모델 파일이 없습니다: {p}\n먼저 `python speech/download_models.py` 를 실행하세요.")
        return str(p)

    # ------------------------------------------------------------ STT
    @property
    def stt(self) -> sherpa_onnx.OfflineRecognizer:
        if self._stt is None:
            self._stt = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=self._path(STT_DIR, "model.int8.onnx"),
                tokens=self._path(STT_DIR, "tokens.txt"),
                num_threads=self.cfg.num_threads_stt,
                language=self.cfg.language,
                use_itn=self.cfg.use_itn,
                provider="cpu",
            )
        return self._stt

    def stt_samples(self, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
        """float32 [-1,1] 모노 음성 → 글자."""
        stream = self.stt.create_stream()
        stream.accept_waveform(sample_rate, np.asarray(samples, dtype=np.float32))
        self.stt.decode_stream(stream)
        return stream.result.text.strip()

    def stt_file(self, path: str | Path) -> str:
        samples, sr = read_mono(path)
        return self.stt_samples(samples, sr)

    # ------------------------------------------------------------ VAD
    def new_vad(self, buffer_seconds: float = 60) -> sherpa_onnx.VoiceActivityDetector:
        c = sherpa_onnx.VadModelConfig()
        c.silero_vad.model = self._path(VAD_FILE)
        c.silero_vad.threshold = self.cfg.vad_threshold
        c.silero_vad.min_silence_duration = self.cfg.vad_min_silence
        c.silero_vad.min_speech_duration = self.cfg.vad_min_speech
        c.silero_vad.window_size = 512
        c.sample_rate = SAMPLE_RATE
        c.num_threads = self.cfg.num_threads_vad
        c.provider = "cpu"
        return sherpa_onnx.VoiceActivityDetector(c, buffer_size_in_seconds=buffer_seconds)

    def stt_long(self, path: str | Path) -> list[tuple[float, float, str]]:
        """긴 녹음: VAD 로 말한 구간을 자르고 구간마다 인식. [(시작초, 끝초, 글자)]"""
        samples, sr = read_mono(path)
        if sr != SAMPLE_RATE:
            samples = resample(samples, sr, SAMPLE_RATE)
        vad = self.new_vad(buffer_seconds=len(samples) / SAMPLE_RATE + 5)
        out = []
        w = 512
        for i in range(0, len(samples), w):
            vad.accept_waveform(samples[i:i + w])
        vad.flush()
        while not vad.empty():
            seg = vad.front
            text = self.stt_samples(np.array(seg.samples, dtype=np.float32))
            st = seg.start / SAMPLE_RATE
            out.append((st, st + len(seg.samples) / SAMPLE_RATE, text))
            vad.pop()
        return out

    # ------------------------------------------------------------ TTS
    @property
    def tts(self) -> sherpa_onnx.OfflineTts:
        if self._tts is None:
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=self._path(TTS_DIR, "ko_KO-kss_low.onnx"),
                lexicon="",
                tokens=self._path(TTS_DIR, "tokens.txt"),
                data_dir=self._path(TTS_DIR, "espeak-ng-data"),
            )
            cfg = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=vits, num_threads=self.cfg.num_threads_tts, provider="cpu"),
                max_num_sentences=1,
            )
            if not cfg.validate():
                raise RuntimeError("TTS 설정 검증 실패 (모델 경로 확인)")
            self._tts = sherpa_onnx.OfflineTts(cfg)
        return self._tts

    def tts_iter(self, text: str):
        """문장 하나씩 (문장, samples, sample_rate) 를 돌려줌 → 첫 문장부터 바로 재생 가능."""
        for sent in split_sentences(text):
            audio = self.tts.generate(sent, sid=self.cfg.tts_sid, speed=self.cfg.tts_speed)
            yield sent, np.asarray(audio.samples, dtype=np.float32), audio.sample_rate

    def synthesize(self, text: str) -> TtsResult:
        t0 = time.perf_counter()
        chunks, sents, sr = [], [], self.tts.sample_rate
        for sent, samples, sr in self.tts_iter(text):
            sents.append(sent)
            chunks.append(samples)
            chunks.append(np.zeros(int(sr * 0.15), dtype=np.float32))  # 문장 사이 쉼
        samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        return TtsResult(samples, sr, (time.perf_counter() - t0) * 1000, sents)

    def tts_to_file(self, text: str, path: str | Path) -> TtsResult:
        r = self.synthesize(text)
        sf.write(str(path), r.samples, r.sample_rate, subtype="PCM_16")
        return r


# ---------------------------------------------------------------- 오디오 유틸
def read_mono(path: str | Path) -> tuple[np.ndarray, int]:
    samples, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return samples.mean(axis=1), sr


def resample(x: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    """간단한 선형 보간 리샘플 (STT 입력용으로 충분)."""
    if sr_from == sr_to:
        return x
    n = int(round(len(x) * sr_to / sr_from))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
