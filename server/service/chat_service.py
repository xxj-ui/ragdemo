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
    """返回 SSE 字节流（每个事件已编码为 `event:` 行 + `data:` 行 + 空行）。

    注意：本函数是**协程**（await 后得到异步迭代器），不是异步生成器 ——
    这样"未实现"能在路由层立刻抛出、被统一转成 501，而不是等流建立后才失败。
    M2 实现时先完成检索与引用组装，再把内层异步生成器返回出去。
    """
    raise NotImplementedError("M2 实现：检索 → 引用 → 流式生成 → 落库")
