"""关键词索引预热（BM25 生命周期，BR-4 / 02 S-04）

目的：把 BM25 全量重建从"用户第一次提问"挪到"导入响应"里 ——
导入完成时索引已就绪，用户立刻提问不用再等 jieba 切全量语料。

  - 上传/导入结束：`await rebuild_bm25()`，**等构建完成再返回**，响应即"可检索"；
  - 删除文档：`warm_in_background()` 起后台任务，不阻塞删除响应；
  - 构建在 `asyncio.to_thread` 里跑：事件循环与其它请求不受影响；
  - 失败只记日志（检索路径仍会自动懒重建），不让上传/删除因此失败。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("ragdemo.indexing")


async def rebuild_bm25(container: Any) -> float:
    """强制重建 BM25 并等待完成，返回耗时（秒）；失败返回 -1。"""
    started = time.perf_counter()
    try:
        index = await asyncio.to_thread(container.bm25.rebuild, container.chunks.fetch_all)
        total = time.perf_counter() - started
        build = container.bm25.last_build_seconds
        logger.info(
            "BM25 预热完成 chunks=%s 构建=%.1fs 排队=%.1fs",
            index.size,
            build,
            max(total - build, 0.0),
        )
        return total
    except Exception:
        # 预热失败绝不能影响上传/删除的结果：检索路径还会懒重建
        logger.exception("BM25 预热失败（检索时会懒重建，不影响本次结果）")
        return -1.0


# 删除后预热做合并：一批连续删除（如多选删）只重建一次，避免 N 次全量重建
_DEBOUNCE_SECONDS = 1.5
_warming: dict[int, asyncio.Task] = {}


def warm_in_background(container: Any) -> None:
    """起后台任务重建索引（删除后用）：不阻塞当前响应，且在途任务会被合并。"""
    key = id(container)

    async def _run() -> None:
        await asyncio.sleep(_DEBOUNCE_SECONDS)  # 合并窗口内的连续写
        await rebuild_bm25(container)
        _warming.pop(key, None)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 没有事件循环（同步调用 / CLI）：退回同步重建
        try:
            index = container.bm25.rebuild(container.chunks.fetch_all)
            logger.info("BM25 预热完成 chunks=%s", index.size)
        except Exception:
            logger.exception("BM25 预热失败（检索时会懒重建）")
        return

    running = _warming.get(key)
    if running is not None and not running.done():
        return  # 已有预热在排队/进行中：它读到的是最新数据，覆盖本次写入
    _warming[key] = loop.create_task(_run())
