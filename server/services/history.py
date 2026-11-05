"""M6 会话历史的编排层（04 §4.5~§4.7）

时间统一转 +08:00；citations 是写库时的快照，直接回放，不做二次解释。
"""
from __future__ import annotations

import logging
from typing import Any

import psycopg
from psycopg_pool import PoolClosed, PoolTimeout

from server.core.errors import DependencyUnavailable, NotFoundError
from server.core.timeutil import to_local_iso

logger = logging.getLogger("ragdemo.history")

DB_ERRORS = (psycopg.OperationalError, PoolTimeout, PoolClosed)


def list_conversations(container: Any, limit: int, offset: int) -> dict:
    try:
        with container.pool().connection() as conn:
            rows = container.conversations.list(limit, offset, conn=conn)
    except DB_ERRORS as exc:
        raise DependencyUnavailable("DB_UNAVAILABLE") from exc
    return {
        "items": [
            {
                "id": row["id"],
                "title": row["title"] or "",
                "created_at": to_local_iso(row["created_at"]),
                "updated_at": to_local_iso(row["updated_at"]),
            }
            for row in rows
        ]
    }


def get_conversation(container: Any, conversation_id: int) -> dict:
    try:
        with container.pool().connection() as conn:
            row = container.conversations.get_with_messages(conversation_id, conn=conn)
    except DB_ERRORS as exc:
        raise DependencyUnavailable("DB_UNAVAILABLE") from exc
    if row is None:
        raise NotFoundError("CONVERSATION_NOT_FOUND")
    return {
        "id": row["id"],
        "title": row["title"] or "",
        "created_at": to_local_iso(row["created_at"]),
        "updated_at": to_local_iso(row["updated_at"]),
        "messages": [
            {
                "role": m["role"],
                "content": m["content"],
                "citations": m.get("citations") or [],
            }
            for m in row["messages"]
        ],
    }


def delete_conversation(container: Any, conversation_id: int) -> None:
    try:
        with container.pool().connection() as conn:
            if container.conversations.get_with_messages(conversation_id, conn=conn) is None:
                raise NotFoundError("CONVERSATION_NOT_FOUND")
            container.conversations.delete(conversation_id, conn=conn)
    except DB_ERRORS as exc:
        raise DependencyUnavailable("DB_UNAVAILABLE") from exc
    logger.info("删除会话 conv_id=%s", conversation_id)
