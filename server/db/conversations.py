"""conversations / messages 的数据访问（M6）

约束：`uq_messages_conversation_role` 保证一个会话只有一问一答，
所以"每问一次 = 新建一个会话"，不在已有会话上追加。
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row


class ConversationRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def _using(self, conn: psycopg.Connection | None) -> Iterator[psycopg.Connection]:
        if conn is not None:
            yield conn
            return
        with psycopg.connect(self.dsn, row_factory=dict_row) as own:
            yield own

    # ------------------------------------------------------------------
    # 读
    # ------------------------------------------------------------------
    def list(self, limit: int, offset: int, conn: psycopg.Connection | None = None) -> list[dict[str, Any]]:
        """created_at DESC, id DESC；不带 total（04 §4.5 / D-10）。"""
        with self._using(conn) as c:
            return list(c.execute(
                """
                SELECT id, title, created_at
                  FROM conversations
                 ORDER BY created_at DESC, id DESC
                 LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall())

    def get_with_messages(self, conversation_id: int, conn: psycopg.Connection | None = None) -> dict | None:
        """会话 + 两条消息（user 在前），无则 None。"""
        with self._using(conn) as c:
            row = c.execute(
                "SELECT id, title, created_at FROM conversations WHERE id = %s",
                (conversation_id,),
            ).fetchone()
            if row is None:
                return None
            messages = c.execute(
                """
                SELECT role, content, citations
                  FROM messages
                 WHERE conversation_id = %s
                 ORDER BY CASE role WHEN 'user' THEN 0 ELSE 1 END, id
                """,
                (conversation_id,),
            ).fetchall()
        result = dict(row)
        result["messages"] = [dict(m) for m in messages]
        return result

    # ------------------------------------------------------------------
    # 写
    # ------------------------------------------------------------------
    def create_with_messages(
        self,
        *,
        title: str,
        question: str,
        answer: str,
        citations: list[dict],
        conn: psycopg.Connection | None = None,
    ) -> int:
        """一个事务内：建会话 + 写 user / assistant 两条消息，返回会话 id。"""
        with self._using(conn) as c:
            conv_id = c.execute(
                "INSERT INTO conversations (title) VALUES (%s) RETURNING id",
                (title,),
            ).fetchone()["id"]
            c.execute(
                "INSERT INTO messages (conversation_id, role, content, citations) VALUES (%s, %s, %s, %s::jsonb)",
                (conv_id, "user", question, "[]"),
            )
            c.execute(
                "INSERT INTO messages (conversation_id, role, content, citations) VALUES (%s, %s, %s, %s::jsonb)",
                (conv_id, "assistant", answer, json.dumps(citations, ensure_ascii=False)),
            )
        return int(conv_id)

    def delete(self, conversation_id: int, conn: psycopg.Connection | None = None) -> int:
        """先删消息再删会话（无物理外键，级联由服务层事务保证）。"""
        with self._using(conn) as c:
            c.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
            cur = c.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
            return cur.rowcount
