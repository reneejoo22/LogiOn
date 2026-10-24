import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import get_db

router = APIRouter(prefix="/api/assistant")


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    session_id: str = Field(default="default", min_length=1, max_length=64)


@router.get("/status")
def status(request: Request):
    """앱이 음성 기능 버튼을 켤지 정할 때."""
    bot = request.app.state.assistant
    return {"ready": bot is not None, "device": bot.device_name if bot else None,
            "error": request.app.state.assistant_error}


@router.post("/chat")
def chat(body: ChatIn, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    bot = request.app.state.assistant
    if bot is None:
        raise HTTPException(status_code=503, detail="음성 비서 모델이 올라가 있지 않습니다.")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text 가 비어 있습니다.")
    return bot.chat(conn, text, body.session_id)
