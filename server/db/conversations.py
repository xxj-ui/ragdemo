"""conversations / messages 的数据访问（M6 + 多轮）

多轮（SRS FR-9 / 10.多轮会话设计）：一个会话可含 N 轮，每轮 2 条消息；
`conversations.updated_at` 记录最近活动时间，历史列表按它倒序。
V002 迁移已删除 `uq_messages_conversation_role`，不再有"每角色一条"的限制。
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
        """updated_at DESC, id DESC（04 §4.5 / FR-9）；不带 total（D-10）。"""
        with self._using(conn) as c:
            return list(c.execute(
                """
                SELECT id, title, created_at, updated_at
                  FROM conversations
                 ORDER BY updated_at DESC, id DESC
                 LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall())

    def get(self, conversation_id: int, conn: psycopg.Connection | None = None) -> dict[str, Any] | None:
        with self._using(conn) as c:
            return c.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = %s",
                (conversation_id,),
            ).fetchone()

    def get_with_messages(self, conversation_id: int, conn: psycopg.Connection | None = None) -> dict | None:
        """会话 + 全部消息（按 id 升序 = 轮次先后），无则 None。"""
        with self._using(conn) as c:
            row = c.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = %s",
                (conversation_id,),
            ).fetchone()
            if row is None:
                return None
            messages = c.execute(
                """
                SELECT role, content, citations
                  FROM messages
                 WHERE conversation_id = %s
                 ORDER BY id
                """,
                (conversation_id,),
            ).fetchall()
        result = dict(row)
        result["messages"] = [dict(m) for m in messages]
        return result

    def load_recent_messages(
        self, conversation_id: int, limit: int, conn: psycopg.Connection | None = None
    ) -> list[dict[str, Any]]:
        """取最近 N 条消息，返回**从旧到新**（拼提示词用）。

        先按 id 倒序取、再反转，保证"取最新"与"展示顺序"同一口径。
        """
        if limit <= 0:
            return []
        with self._using(conn) as c:
            rows = c.execute(
                """
                SELECT id, role, content
                  FROM messages
                 WHERE conversation_id = %s
                 ORDER BY id DESC
                 LIMIT %s
                """,
                (conversation_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

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

    def append_turn(
        self,
        conversation_id: int,
        *,
        question: str,
        answer: str,
        citations: list[dict],
        conn: psycopg.Connection | None = None,
    ) -> None:
        """在已有会话上追加一轮（2 条消息）并刷新 updated_at，同一事务。"""
        with self._using(conn) as c:
            c.execute(
                "INSERT INTO messages (conversation_id, role, content, citations) VALUES (%s, %s, %s, %s::jsonb)",
                (conversation_id, "user", question, "[]"),
            )
            c.execute(
                "INSERT INTO messages (conversation_id, role, content, citations) VALUES (%s, %s, %s, %s::jsonb)",
                (conversation_id, "assistant", answer, json.dumps(citations, ensure_ascii=False)),
            )
            c.execute(
                "UPDATE conversations SET updated_at = now() WHERE id = %s",
                (conversation_id,),
            )

    def delete(self, conversation_id: int, conn: psycopg.Connection | None = None) -> int:
        """先删消息再删会话（无物理外键，级联由服务层事务保证）。"""
        with self._using(conn) as c:
            c.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
            cur = c.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
            return cur.rowcount
