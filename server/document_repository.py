"""documents 表的数据访问（唯一写 SQL 的地方之一）

骨架：方法签名按 03/04 定稿，实现留到 M1。
"""
from __future__ import annotations

from typing import Any


class DocumentRepository:
    def __init__(self, container: Any) -> None:
        self._c = container

    def list_all(self) -> list[dict]:
        """按 updated_at DESC, id DESC 返回全部文档（04 §4.2）。"""
        raise NotImplementedError("M1 实现")

    def get(self, document_id: int) -> dict | None:
        raise NotImplementedError("M1 实现")

    def find_by_filename(self, filename: str) -> dict | None:
        """按 lower(filename) 命中同名文档（uq_documents_filename_lower）。"""
        raise NotImplementedError("M1 实现")

    def insert(self, *, filename: str, stored_path: str, file_type: str, file_size: int) -> int:
        raise NotImplementedError("M1 实现：返回新 document_id")

    def replace_meta(
        self, document_id: int, *, filename: str, stored_path: str, file_type: str, file_size: int
    ) -> None:
        """同名覆盖：更新元信息并把 updated_at 置 now()（BR-1/BR-2）。"""
        raise NotImplementedError("M1 实现")

    def update_chunk_count(self, document_id: int, chunk_count: int) -> None:
        raise NotImplementedError("M1 实现")

    def delete(self, document_id: int) -> int:
        raise NotImplementedError("M1 实现：返回受影响行数（0 表示不存在）")
