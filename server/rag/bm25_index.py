"""BM25 索引生命周期（02 S-04 / BR-4）

进程内缓存：首次检索前构建 → 上传/删除成功后置失效 → 下次检索前懒重建。
上传/导入结束时会**主动 rebuild 一次**（services/indexing），把重建成本从
"用户第一次提问"挪到"导入响应"里；删除只做后台预热，不阻塞删除响应。
单 worker（S-01）前提下无需加锁；多 worker 会各存一份，属已知限制。

内核不做数据库访问：`ensure_built` 只接收一个取数回调，由 `services/retrieval`
传入 `container.chunks.fetch_all`。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from server.rag.keyword_search import BM25KeywordSearch

logger = logging.getLogger("zhiwen.bm25")


class Bm25Index:
    def __init__(self) -> None:
        self._index: BM25KeywordSearch | None = None
        self._last_build_seconds: float = 0.0
        # 构建可能耗时十几秒（4,576 块实测 10.7 s）。启动预热与首个请求可能同时到达，
        # 用一个锁把并发构建收敛成一次；invalidate() 不抢锁（只自增代数），
        # 这样上传/删除不会被正在进行的构建卡住。
        self._build_lock = threading.Lock()
        self._generation = 0

    def _build(self, fetch_all: Callable[[], list[dict]]) -> BM25KeywordSearch:
        started = time.perf_counter()
        built = BM25KeywordSearch(fetch_all())
        self._last_build_seconds = time.perf_counter() - started
        return built

    def _build_fresh(
        self, fetch_all: Callable[[], list[dict]], attempts: int = 2
    ) -> tuple[BM25KeywordSearch, bool]:
        """构建索引；构建期间若有写入（代数变了），丢弃结果并重试。

        返回 `(索引, 是否为最新数据)`。重试用尽仍未成功时，返回最后一次结果但
        标记为不新鲜 —— 调用方可以拿它应急，**不能**装进缓存（否则会一直缺最新写入）。
        """
        built: BM25KeywordSearch | None = None
        for attempt in range(1, attempts + 1):
            generation = self._generation
            built = self._build(fetch_all)
            if generation == self._generation:
                return built, True
            logger.warning(
                "BM25 构建期间发生写入，丢弃第 %d 次构建结果（generation %d → %d）%s",
                attempt,
                generation,
                self._generation,
                "，重试一次" if attempt < attempts else "，本次使用可能缺少最新写入",
            )
        assert built is not None
        return built, False

    @property
    def built(self) -> bool:
        return self._index is not None

    @property
    def size(self) -> int:
        """当前索引里的片段数（未构建为 0）。"""
        return self._index.size if self._index is not None else 0

    @property
    def last_build_seconds(self) -> float:
        """最近一次构建耗时（不含等锁时间），仅用于日志/度量。"""
        return self._last_build_seconds

    def rebuild(self, fetch_all: Callable[[], list[dict]]) -> BM25KeywordSearch:
        """强制重建（导入完成后调用）。与 ensure_built 共用锁，避免并发双建。"""
        with self._build_lock:
            built, fresh = self._build_fresh(fetch_all)
            if fresh:
                self._index = built
            return built

    def invalidate(self) -> None:
        """上传 / 覆盖 / 删除成功后调用（BR-4）。"""
        self._generation += 1        # 让正在构建的那一份作废
        self._index = None

    def ensure_built(self, fetch_all: Callable[[], list[dict]]) -> BM25KeywordSearch:
        """检索前调用：未构建则拉一次全量片段建索引。"""
        index = self._index
        if index is not None:
            return index
        with self._build_lock:
            if self._index is not None:
                return self._index
            built, fresh = self._build_fresh(fetch_all)
            if fresh:                     # 构建期间没人置失效，才装进缓存
                self._index = built
            return built

    def search(self, question: str, top_k: int = 5) -> list[dict]:
        if self._index is None:
            raise RuntimeError("BM25 索引尚未构建，请先调用 ensure_built()")
        return self._index.search(question, top_k)
