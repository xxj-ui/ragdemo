"""M4 问答路由：04 §4.4（SSE）"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from server.api.deps import get_container
from server.core.errors import AppError
from server.api.schemas import ChatRequest
from server.services import chat

router = APIRouter(tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/chat", summary="基于知识库问答（SSE）", response_class=StreamingResponse)
async def chat_stream(payload: ChatRequest):
    question = payload.question.strip()
    if not question:
        raise AppError("QUESTION_EMPTY")
    if len(question) > 500:
        raise AppError("QUESTION_TOO_LONG")
    stream = chat.ask_stream(get_container(), question)
    return StreamingResponse(stream, media_type="text/event-stream; charset=utf-8", headers=SSE_HEADERS)
