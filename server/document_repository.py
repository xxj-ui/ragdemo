"""documents 表的数据访问（唯一写 SQL 的地方之一）

约定：
  - 每个方法都接受可选的 `conn`：由服务层传入时复用同一事务；不传则自开连接。
  - 连接统一使用 `dict_row`，返回值是 dict，列名与 03 文档一致。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

COLUMNS = "id, filename, stored_path, file_type, file_size, chunk_count, created_at, updated_at"


class DocumentRepository:
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
    def list_all(self, conn: psycopg.Connection | None = None) -> list[dict[str, Any]]:
        """按最近更新倒序（FR-2 / Q5）。"""
        with self._using(conn) as c:
            rows = c.execute(
                f"SELECT {COLUMNS} FROM documents ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return list(rows)

    def get(self, document_id: int, conn: psycopg.Connection | None = None) -> dict[str, Any] | None:
        with self._using(conn) as c:
            return c.execute(
                f"SELECT {COLUMNS} FROM documents WHERE id = %s", (document_id,)
            ).fetchone()

    def find_by_filename(self, filename: str, conn: psycopg.Connection | None = None) -> dict[str, Any] | None:
        """按 lower(filename) 命中同名文档（uq_documents_filename_lower，大小写不敏感）。"""
        with self._using(conn) as c:
            return c.execute(
                f"SELECT {COLUMNS} FROM documents WHERE lower(filename) = lower(%s)", (filename,)
            ).fetchone()

    # ------------------------------------------------------------------
    # 写
    # ------------------------------------------------------------------
    def insert(
        self,
        *,
        filename: str,
        stored_path: str,
        file_type: str,
        file_size: int,
        conn: psycopg.Connection | None = None,
    ) -> int:
        with self._using(conn) as c:
            row = c.execute(
                """
                INSERT INTO documents (filename, stored_path, file_type, file_size, chunk_count)
                VALUES (%s, %s, %s, %s, 0)
                RETURNING id
                """,
                (filename, stored_path, file_type, file_size),
            ).fetchone()
        return int(row["id"])

    def replace_meta(
        self,
        document_id: int,
        *,
        filename: str,
        stored_path: str,
        file_type: str,
        file_size: int,
        conn: psycopg.Connection | None = None,
    ) -> None:
        """同名覆盖：更新元信息并把 updated_at 置 now()（BR-1 / BR-2）。"""
        with self._using(conn) as c:
            c.execute(
                """
                UPDATE documents
                   SET filename = %s, stored_path = %s, file_type = %s,
                       file_size = %s, updated_at = now()
                 WHERE id = %s
                """,
                (filename, stored_path, file_type, file_size, document_id),
            )

    def update_chunk_count(
        self, document_id: int, chunk_count: int, conn: psycopg.Connection | None = None
    ) -> None:
        with self._using(conn) as c:
            c.execute(
                "UPDATE documents SET chunk_count = %s WHERE id = %s",
                (chunk_count, document_id),
            )

    def delete(self, document_id: int, conn: psycopg.Connection | None = None) -> int:
        with self._using(conn) as c:
            cur = c.execute("DELETE FROM documents WHERE id = %s", (document_id,))
            return cur.rowcount
