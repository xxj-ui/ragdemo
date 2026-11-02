"""BM25 索引生命周期（02 S-04 / BR-4）

进程内缓存：启动构建一次 + 写操作置失效 + 下次检索前懒重建。
骨架：只定接口，M1 实现。
"""
from __future__ import annotations

from typing import Any


class Bm25Index:
    def __init__(self) -> None:
        self._built = False
        self._payload: Any = None

    @property
    def built(self) -> bool:
        return self._built

    def invalidate(self) -> None:
        """上传/删除成功后调用（BR-4）。"""
        self._built = False
        self._payload = None

    def ensure_built(self) -> Any:
        """检索前调用；失效则重建（进程内，单 worker）。"""
        raise NotImplementedError("M1 实现：从 rag_chunks 拉全量做分词与 df/avgdl 统计")
