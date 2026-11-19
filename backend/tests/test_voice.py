"""POST /api/assistant/voice: 녹음 → STT → /chat 과 같은 파이프라인 → TTS.

기본 테스트는 가짜 STT/TTS 엔진과 가짜 LLM 으로 API 연결만 본다 (모델 없이 어디서나).
test_real_models_* 는 실제 sherpa-onnx 모델이 있을 때만 돈다 (보드: LOGION_SPEECH_MODELS=~/voice/models).
"""
import io
import os
import re
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from tests.test_assistant import SCRIPT, SINGLE_LLM, V3_SINGLE


def wav_bytes(samples: np.ndarray, sr: int = 16000) -> bytes:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()


def tone(seconds=1.0, sr=16000):
    t = np.arange(int(seconds * sr)) / sr
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


class FakeEngine:
    """소리가 있으면 next_text 를 인식한 것으로, TTS 는 길이만 맞춘 무음."""

    def __init__(self):
        self.next_text = "다음 어디야"
        self.seen_sr = []

    def trim_silence(self, samples):
        return samples if np.abs(samples).max(initial=0) > 0.01 else np.zeros(0, np.float32)

    def stt_samples(self, samples, sample_rate=16000):
        self.seen_sr.append(sample_rate)
        return self.next_text

    def synthesize(self, text):
        return SimpleNamespace(samples=np.zeros(22050 // 2, np.float32), sample_rate=22050, elapsed_ms=1.0)


def norm(text):  # STT 는 끝에 마침표·물음표를 붙인다
    return re.sub(r"[.?!,\s]+$", "", text)


def fake_bot(config_path=V3_SINGLE):
    from app.services.assistant import DbAssistant

    bot = DbAssistant(config_path=config_path, load_models=False)
    bot.classify = lambda text: SCRIPT[norm(text)][0]
    bot.call_llm = lambda text: (SINGLE_LLM.get(norm(text)) or SCRIPT[norm(text)][1], 0.99, 0.9)
    return bot


@pytest.fixture
def vclient(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "test.db"))
    from app.main import app
    from app.services.voice import VoiceService

    with TestClient(app) as c:
        assert app.state.voice is None  # conftest 에서 꺼 둠
        app.state.assistant = fake_bot()
        eng = FakeEngine()
        app.state.voice = VoiceService(eng)
        c.engine = eng
        yield c


def post_voice(c, data, session_id="v1", name="a.wav"):
    return c.post("/api/assistant/voice", files={"file": (name, data, "audio/wav")},
                  data={"session_id": session_id})


def test_voice_runs_pipeline_and_returns_audio(vclient):
    r = post_voice(vclient, wav_bytes(tone()))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["text"] == "다음 어디야"
    assert j["reply"] == "다음은 GS25 성수연무장점이에요. 남은 곳은 3곳이에요."
    assert (j["fn"], j["action"], j["options"]) == ("next_stop", "refresh_route", None)
    assert set(j["latency"]) == {"stt", "llm", "tts", "total"}
    assert "call" in j and "stop_id" in j

    a = vclient.get(j["audio_url"])
    assert a.status_code == 200 and a.headers["content-type"] == "audio/wav"
    with wave.open(io.BytesIO(a.content)) as w:
        assert (w.getframerate(), w.getnchannels()) == (22050, 1)


def test_voice_writes_db_like_chat(vclient):
    vclient.engine.next_text = "납품 완료 점장님이 받았어."
    j = post_voice(vclient, wav_bytes(tone())).json()
    assert j["fn"] == "complete" and j["route"] == "confirm_ask" and j["reply"] == "GS25 성수연무장점 납품 완료할까요?"
    vclient.engine.next_text = "네."
    j = post_voice(vclient, wav_bytes(tone())).json()
    assert j["fn"] == "complete" and j["stop_id"] == 1 and j["route"] == "confirm_yes"
    assert vclient.get("/api/stops/1").json()["receiver"] == "점장님"


def test_voice_follow_up_question_uses_session(vclient):
    vclient.engine.next_text = "삼각김밥 두 개 터졌어"
    j = post_voice(vclient, wav_bytes(tone()), session_id="s").json()
    assert j["options"] == ["참치삼각김밥", "스팸마요삼각김밥"]
    vclient.engine.next_text = "참치삼각김밥"
    j = post_voice(vclient, wav_bytes(tone()), session_id="s").json()
    assert j["reply"] == "GS25 성수연무장점 참치삼각김밥 2개 파손으로 기록했어요."


def test_value_outside_function_is_ignored(vclient):
    """보드 실측: STT "성수연무 장점, 납품완 정자님한테 넘겼어." → LLM 이 complete 에 item="장점" 을 붙임.
    complete 는 품목을 안 쓰므로 버리고 완료를 되묻고, 다음 말도 품목 되묻기 답으로 삼키지 않는다.
    (11/20: STT 오인식 별칭으로 LLM 에는 "성수연무장점, 납품완 점장님한테 넘겼어." 가 들어간다)"""
    bot = vclient.app.state.assistant
    llm = {"성수연무장점, 납품완 점장님한테 넘겼어.":
           '{"fn":"complete","store":"성수연무","item":"장점","receiver":"점장님"}',
           "근처 화장실 어디야?": '{"fn":"other"}'}
    bot.call_llm = lambda text: (llm[text], 0.99, 0.9)
    vclient.engine.next_text = "성수연무 장점, 납품완 정자님한테 넘겼어."
    j = post_voice(vclient, wav_bytes(tone())).json()
    assert j["text"] == "성수연무장점, 납품완 점장님한테 넘겼어." and j["stt_text"] == "성수연무 장점, 납품완 정자님한테 넘겼어."
    assert j["reply"] == "GS25 성수연무장점 납품 완료할까요?"
    assert j["call"] == {"store": "성수연무", "receiver": "점장님"}
    vclient.engine.next_text = "응."
    j = post_voice(vclient, wav_bytes(tone())).json()
    assert j["reply"] == "GS25 성수연무장점 납품 완료로 기록했어요. 인수자는 점장님이에요."
    vclient.engine.next_text = "근처 화장실 어디야?"
    j = post_voice(vclient, wav_bytes(tone())).json()
    assert j["fn"] == "other" and j["route"] != "choice_answer"


def test_silence_asks_again_without_llm(vclient):
    j = post_voice(vclient, wav_bytes(np.zeros(16000, np.float32))).json()
    assert j["text"] == "" and j["reply"] == "잘 못 들었어요. 다시 말씀해 주세요."
    assert j["fn"] is None and j["action"] is None and j["latency"]["llm"] == 0
    assert vclient.get(j["audio_url"]).status_code == 200  # 다시 말해 달라는 말도 읽어 준다


def test_other_sample_rate_is_resampled(vclient):
    stereo48k = np.stack([tone(1.0, 48000)] * 2, axis=1)
    buf = io.BytesIO()
    import soundfile as sf

    sf.write(buf, stereo48k, 48000, format="WAV", subtype="PCM_16")
    j = post_voice(vclient, buf.getvalue()).json()
    assert j["input"]["sample_rate"] == 48000 and abs(j["input"]["seconds"] - 1.0) < 0.01
    assert j["text"] == "다음 어디야"


def test_bad_file_and_missing_audio(vclient):
    assert post_voice(vclient, b"not audio", name="a.m4a").status_code == 415
    assert vclient.get("/api/assistant/voice/audio/nope").status_code == 404
    assert vclient.post("/api/assistant/voice", data={"session_id": "x"}).status_code == 422


def test_voice_503_when_engine_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        assert post_voice(c, wav_bytes(tone())).status_code == 503
        app.state.assistant = fake_bot()
        r = post_voice(c, wav_bytes(tone()))
        assert r.status_code == 503 and "STT/TTS" in r.json()["detail"]
        assert c.get("/api/assistant/status").json()["voice_ready"] is False


# ---------------------------------------------------------------- 실제 모델 (있을 때만)
def _models_dir():
    import importlib.util

    from app.services.voice import REPO_DIR  # noqa: F401  (저장소 루트를 sys.path 에 넣음)

    if importlib.util.find_spec("sherpa_onnx") is None or importlib.util.find_spec("soundfile") is None:
        return None
    d = Path(os.environ.get("LOGION_SPEECH_MODELS") or REPO_DIR / "speech" / "models")
    return d if (d / "silero_vad.onnx").exists() else None


needs_models = pytest.mark.skipif(
    os.environ.get("LOGION_SKIP_REAL_VOICE") == "1" or _models_dir() is None,
    reason="sherpa-onnx STT/TTS 모델 없음 (LOGION_SPEECH_MODELS)")


@needs_models
def test_real_models_tts_then_stt_round_trip(tmp_path, monkeypatch):
    """실제 TTS 로 만든 '다음 어디야' 앞뒤에 무음을 붙여 올림 → 실제 VAD·STT 가 알아듣고, 응답도 실제 TTS."""
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("LOGION_VOICE", "1")
    from app.main import app
    from speech.speech_engine import resample

    with TestClient(app) as c:
        svc = app.state.voice
        assert svc is not None, app.state.voice_error
        bot = fake_bot()
        # 한국어 VITS(kss_low) 는 생성할 때마다 소리가 조금씩 달라(무작위 noise) STT 결과도 흔들린다
        # ("단음배질 어디야", "다음 배송지는 어때야?"). 정확도는 실제 녹음으로 따로 쟀으므로(results/board_voice)
        # 여기서는 실제 모델 연결만 본다: LLM 은 고정, VAD 가 말을 찾고 STT 가 글자를 냈는지만 확인
        # (낱말 검사는 20번에 1번꼴로 "단배지는는 나디야." 처럼 빗나가 테스트가 들쑥날쑥해짐)
        bot.call_llm = lambda text: ('{"fn":"next_stop"}', 0.99, 0.9)
        app.state.assistant = bot
        r = svc.engine.synthesize("다음 배송지는 어디야")
        x = resample(r.samples, r.sample_rate, 16000)
        pad = np.zeros(16000, np.float32)
        j = post_voice(c, wav_bytes(np.concatenate([pad, x, pad]))).json()
        assert len(j["text"]) >= 3 and j["route"] != "not_heard", j
        assert j["fn"] == "next_stop"
        assert j["latency"]["tts"] > 0
        a = c.get(j["audio_url"])
        with wave.open(io.BytesIO(a.content)) as w:
            assert w.getnframes() > w.getframerate() * 0.5  # 0.5초 넘는 실제 음성


def test_tts_endpoint_returns_audio(vclient):
    r = vclient.post("/api/assistant/tts", json={"text": "다음은 GS25 성수연무장점이에요."})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["audio_url"].startswith("/api/assistant/voice/audio/") and "tts" in j["latency"]
    a = vclient.get(j["audio_url"])
    assert a.status_code == 200 and a.headers["content-type"] == "audio/wav"
    assert vclient.post("/api/assistant/tts", json={"text": "  "}).status_code == 422
    assert vclient.post("/api/assistant/tts", json={}).status_code == 422


def test_tts_503_without_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGION_DB", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        assert c.post("/api/assistant/tts", json={"text": "안녕"}).status_code == 503
