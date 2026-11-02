"""M6 会话历史路由：04 §4.5~§4.7"""
from __future__ import annotations

from fastapi import APIRouter, Query

from server.deps import get_container
from server.schemas import ConversationDetail, ConversationList, Envelope
from server.service import history_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=Envelope[ConversationList], summary="历史列表")
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    result = history_service.list_conversations(get_container(), limit, offset)
    return Envelope(data=ConversationList(**result))


@router.get("/{conversation_id}", response_model=Envelope[ConversationDetail], summary="历史详情（只读）")
async def get_conversation(conversation_id: int):
    result = history_service.get_conversation(get_container(), conversation_id)
    return Envelope(data=ConversationDetail(**result))


@router.delete("/{conversation_id}", response_model=Envelope[None], summary="删除历史")
async def delete_conversation(conversation_id: int):
    history_service.delete_conversation(get_container(), conversation_id)
    return Envelope(data=None)
