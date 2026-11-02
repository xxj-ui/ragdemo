"""检索编排（02 §3.2）：问题 → 稠密召回 + 关键词召回 → RRF 融合。

分工：`rag/` 只提供纯算法（`embed_query` / `BM25KeywordSearch` / `rrf_fuse`），
"从库里取哪些片段、两路各召回多少、融合后留几条"属于编排，放在这里，
参数一律走 `Settings`（recall_k / top_k / rrf_k），不散落在各处。
"""
from __future__ import annotations

import asyncio
from typing import Any

from server.rag.embedder import embed_query
from server.rag.rrf import rrf_fuse


def retrieve(
    container: Any,
    question: str,
    top_k: int | None = None,
    recall_k: int | None = None,
    rrf_k: int | None = None,
) -> list[dict]:
    """两路召回 + RRF 融合，返回 top_k 条（每条形如 04 的 citations 元素原料）。"""
    settings = container.settings
    top_k = settings.top_k if top_k is None else top_k
    recall_k = settings.recall_k if recall_k is None else recall_k
    rrf_k = settings.rrf_k if rrf_k is None else rrf_k

    repo = container.chunks
    dense = repo.search(embed_query(question), top_k=recall_k)
    # BM25 索引进程内缓存：写操作已 invalidate，这里懒重建（02 S-04）
    index = container.bm25.ensure_built(repo.fetch_all)
    keyword = index.search(question, top_k=recall_k)
    return rrf_fuse([("dense", dense), ("bm25", keyword)], k=rrf_k, top_k=top_k)


async def aretrieve(container: Any, question: str, **kwargs: Any) -> list[dict]:
    """异步包装：检索是同步阻塞的（psycopg + 模型），放进线程池，别堵事件循环。"""
    return await asyncio.to_thread(retrieve, container, question, **kwargs)
