import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.db import get_db

router = APIRouter(prefix="/api/assistant")

MAX_UPLOAD = 5 * 1024 * 1024  # 15초 wav 16kHz mono ≈ 0.5MB, 48kHz 스테레오도 넉넉히


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    session_id: str = Field(default="default", min_length=1, max_length=64)


@router.get("/status")
def status(request: Request):
    """앱이 음성 기능 버튼을 켤지 정할 때. voice_ready 가 true 면 /voice 를 쓸 수 있다."""
    bot = request.app.state.assistant
    voice = getattr(request.app.state, "voice", None)
    return {"ready": bot is not None, "device": bot.device_name if bot else None,
            "error": request.app.state.assistant_error,
            "voice_ready": bot is not None and voice is not None,
            "voice_error": getattr(request.app.state, "voice_error", None)}


@router.post("/chat")
def chat(body: ChatIn, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    bot = request.app.state.assistant
    if bot is None:
        raise HTTPException(status_code=503, detail="음성 비서 모델이 올라가 있지 않습니다.")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text 가 비어 있습니다.")
    return bot.chat(conn, text, body.session_id)


@router.post("/voice")
def voice(request: Request, file: UploadFile = File(...),
          session_id: str = Form("default", min_length=1, max_length=64),
          conn: sqlite3.Connection = Depends(get_db)):
    """녹음 파일 → 보드에서 STT → /chat 과 같은 파이프라인 → TTS. 응답 음성은 audio_url 로 받는다."""
    from app.services.voice import AudioError

    bot = request.app.state.assistant
    svc = getattr(request.app.state, "voice", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="음성 비서 모델이 올라가 있지 않습니다.")
    if svc is None:
        raise HTTPException(status_code=503, detail=f"STT/TTS 가 올라가 있지 않습니다: {request.app.state.voice_error}")
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="음성 파일이 너무 큽니다 (5MB 이하).")
    if not data:
        raise HTTPException(status_code=422, detail="음성 파일이 비어 있습니다.")
    try:
        return svc.handle(data, lambda text: bot.chat(conn, text, session_id))
    except AudioError as e:
        raise HTTPException(status_code=415, detail=str(e))


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@router.post("/tts")
def tts(body: TtsIn, request: Request):
    """글자로 받은 답을 소리로 (앱에서 글자로 물었을 때 답 읽어 주기용). 음성은 /voice 와 같이 audio_url 로 받는다."""
    svc = getattr(request.app.state, "voice", None)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"TTS 가 올라가 있지 않습니다: {request.app.state.voice_error}")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text 가 비어 있습니다.")
    audio_id, ms = svc.synthesize(text)
    return {"text": text, "audio_url": f"/api/assistant/voice/audio/{audio_id}", "latency": {"tts": round(ms)}}


@router.get("/voice/audio/{audio_id}")
def voice_audio(audio_id: str, request: Request):
    svc = getattr(request.app.state, "voice", None)
    wav = svc.get_audio(audio_id) if svc else None
    if wav is None:
        raise HTTPException(status_code=404, detail="응답 음성이 없거나 만료되었습니다 (10분 보관).")
    return Response(content=wav, media_type="audio/wav")
