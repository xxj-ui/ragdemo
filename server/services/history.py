"""M6 会话历史的编排层（骨架）"""
from __future__ import annotations

from typing import Any


def list_conversations(container: Any, limit: int, offset: int) -> dict:
    raise NotImplementedError("M2 实现")


def get_conversation(container: Any, conversation_id: int) -> dict:
    raise NotImplementedError("M2 实现")


def delete_conversation(container: Any, conversation_id: int) -> None:
    raise NotImplementedError("M2 实现")
