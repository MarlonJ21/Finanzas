from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.services import luka as luka_service

router = APIRouter(prefix="/api/luka", tags=["luka"])


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=luka_service.MAX_MESSAGE_CHARS)


class PageContext(BaseModel):
    route: str | None = Field(default=None, max_length=100)
    scenario: str | None = Field(default=None, max_length=40)
    selected_category_id: str | None = Field(default=None, max_length=100)


class ChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=luka_service.MAX_MESSAGE_CHARS)
    conversation_id: str | None = Field(default=None, max_length=100)
    page_context: PageContext | None = None
    history: list[HistoryMessage] = Field(default_factory=list, max_length=6)
    response_mode: Literal["text", "audio"] = "text"


@router.get("/status")
def luka_status() -> dict:
    return luka_service.status()


@router.post("/chat")
def luka_chat(payload: ChatPayload) -> dict:
    if not luka_service.enabled():
        raise HTTPException(status_code=404, detail="LUKA_DISABLED")
    try:
        result = luka_service.answer(payload.message, payload.page_context.model_dump(exclude_none=True) if payload.page_context else None, [item.model_dump() for item in payload.history])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        luka_service.log.exception("luka_chat unexpected error: %s", exc)
        text, card, tool = luka_service._deterministic(payload.message)
        result = {
            "message": text,
            "structured_cards": card,
            "provider": "deterministic",
            "model": None,
            "tool_calls": [tool] if tool else [],
            "fallback_used": True,
            "fallback_reason": "Error inesperado en el servidor.",
            "provider_error": str(exc),
        }
    result["conversation_id"] = payload.conversation_id or str(uuid.uuid4())
    result["response_mode"] = payload.response_mode
    result["voice_requested"] = payload.response_mode == "audio"
    return result


@router.post("/transcribe")
async def luka_transcribe(file: UploadFile = File(...)) -> dict:
    if not luka_service.enabled():
        raise HTTPException(status_code=404, detail="LUKA_DISABLED")
    mime_type = (file.content_type or "").split(";")[0].lower()
    content = await file.read(10 * 1024 * 1024 + 1)
    await file.close()
    try:
        text = await run_in_threadpool(luka_service.transcribe_audio, content, mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=415 if "TYPE" in str(exc) else 413, detail="AUDIO_INVALID") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="STT_NOT_AVAILABLE") from exc
    except Exception as exc:
        # Do not return provider details to the client.
        raise HTTPException(status_code=503, detail="STT_NOT_AVAILABLE") from exc
    return {"text": text}
