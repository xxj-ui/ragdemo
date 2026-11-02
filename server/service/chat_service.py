"""M4 问答生成 + M5 引用组装（骨架）

实现要点：
  1. 两路召回各 recall_k → RRF(k=60) 取 top_k（F-13/F-14）。
  2. 两路皆空：不调大模型，只发 delta（固定话术）+ done，仍保存历史（BR-6、01 Q7）。
  3. 有结果：先发 citations（编号在此刻固定，BR-7），再流式 delta，最后 done。
  4. 生成失败：发 error 事件，不保存历史（FR-6）。
  5. 客户端断开：取消生成，不保存历史（SRS 7.4）。
"""
from __future__ import annotations

from typing import Any, AsyncIterator


async def ask_stream(container: Any, question: str) -> AsyncIterator[bytes]:
    """返回 SSE 字节流（已编码好 `event: ...\ndata: ...\n\n`）。"""
    raise NotImplementedError("M2 实现：检索 → 引用 → 流式生成 → 落库")
    yield b""  # pragma: no cover  —— 让类型检查知道这是异步生成器
