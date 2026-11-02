"""BM25 索引生命周期（02 S-04 / BR-4）

进程内缓存：首次检索前构建 → 上传/删除成功后置失效 → 下次检索前懒重建。
单 worker（S-01）前提下无需加锁；多 worker 会各存一份，属已知限制。

内核不做数据库访问：`ensure_built` 只接收一个取数回调，由 `services/retrieval`
传入 `container.chunks.fetch_all`。
"""
from __future__ import annotations

from typing import Any, Callable

from server.rag.keyword_search import BM25KeywordSearch


class Bm25Index:
    def __init__(self) -> None:
        self._index: BM25KeywordSearch | None = None

    @property
    def built(self) -> bool:
        return self._index is not None

    def invalidate(self) -> None:
        """上传 / 覆盖 / 删除成功后调用（BR-4）。"""
        self._index = None

    def ensure_built(self, fetch_all: Callable[[], list[dict]]) -> BM25KeywordSearch:
        """检索前调用：未构建则拉一次全量片段建索引。"""
        if self._index is None:
            self._index = BM25KeywordSearch(fetch_all())
        return self._index

    def search(self, question: str, top_k: int = 5) -> list[dict]:
        if self._index is None:
            raise RuntimeError("BM25 索引尚未构建，请先调用 ensure_built()")
        return self._index.search(question, top_k)
