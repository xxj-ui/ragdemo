"""M4 问答路由：04 §4.4（SSE）"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from server.deps import get_container
from server.errors import AppError
from server.schemas import ChatRequest
from server.service import chat_service

router = APIRouter(tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/chat", summary="基于知识库问答（SSE）", response_class=StreamingResponse)
async def chat(payload: ChatRequest):
    question = payload.question.strip()
    if not question:
        raise AppError("QUESTION_EMPTY")
    if len(question) > 500:
        raise AppError("QUESTION_TOO_LONG")
    stream = await chat_service.ask_stream(get_container(), question)
    return StreamingResponse(stream, media_type="text/event-stream; charset=utf-8", headers=SSE_HEADERS)
