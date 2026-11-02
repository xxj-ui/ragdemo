"""conversations / messages 的数据访问（M2 实现，签名先用）"""
from __future__ import annotations

from typing import Any


class ConversationRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def list(self, limit: int, offset: int, conn: Any = None) -> list[dict]:
        raise NotImplementedError("M2 实现")

    def get_with_messages(self, conversation_id: int, conn: Any = None) -> dict | None:
        raise NotImplementedError("M2 实现")

    def create_with_messages(
        self, *, title: str, question: str, answer: str, citations: list[dict], conn: Any = None
    ) -> int:
        raise NotImplementedError("M2 实现")

    def delete(self, conversation_id: int, conn: Any = None) -> int:
        raise NotImplementedError("M2 实现")
