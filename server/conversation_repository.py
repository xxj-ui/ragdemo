"""conversations / messages 的数据访问

骨架：签名按 03/04 定稿，实现留到 M1。
"""
from __future__ import annotations

from typing import Any


class ConversationRepository:
    def __init__(self, container: Any) -> None:
        self._c = container

    def list(self, limit: int, offset: int) -> list[dict]:
        """created_at DESC, id DESC；不返回 total（04 §4.5）。"""
        raise NotImplementedError("M1 实现")

    def get_with_messages(self, conversation_id: int) -> dict | None:
        """返回会话 + 按 created_at ASC 排序的 2 条消息（04 §4.6）。"""
        raise NotImplementedError("M1 实现")

    def create_with_messages(
        self, *, title: str, question: str, answer: str, citations: list[dict]
    ) -> int:
        """一个事务内写 conversations + 两条 messages，返回 conversation_id。"""
        raise NotImplementedError("M1 实现")

    def delete(self, conversation_id: int) -> int:
        """先删 messages 再删会话（同一事务，BR-3 同理）。"""
        raise NotImplementedError("M1 实现")
