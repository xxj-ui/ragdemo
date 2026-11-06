"""M4 问答生成 + M5 引用组装（04 §4.4 事件序列 / SRS FR-9 多轮）

顺序（不可调换）：
  1. 检索：`services/retrieval` 两路召回 + RRF（F-13/F-14）
  2. 有结果 → 先发 `citations`（编号在此刻固定，BR-7），再流式 `delta`，最后 `done`
     无结果 → 不调大模型，只发 `delta`（固定话术）+ `done`（BR-6，01 Q7 仍存历史）
  3. 生成失败 → 发 `error` 事件，**不保存历史**（FR-6）
  4. 客户端断开 → 生成被取消，不保存历史（SRS 7.4）
事件 `data` 不套信封，是全项目唯一例外（04 §5.1）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncIterator, cast

import psycopg
from psycopg_pool import PoolClosed, PoolTimeout

from server.core.errors import ERROR_CODES, DependencyUnavailable
from server.rag import llm
from server.services import retrieval

logger = logging.getLogger("zhiwen.chat")

DB_ERRORS = (psycopg.OperationalError, PoolTimeout, PoolClosed)

FALLBACK_TEXT = "根据已有资料无法回答"
TITLE_MAX = 30
SNIPPET_MAX = 100


def sse(event: str, data: dict) -> bytes:
    """SSE 帧：event 行 + 单行 data + 空行（04 §5.1）。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def error_event(code: str, message: str | None = None) -> bytes:
    return sse("error", {"code": code, "message": message or ERROR_CODES.get(code, (500, "服务内部错误"))[1]})


def _clean_snippet(text: str) -> str:
    """摘要只做展示：去掉 Markdown 标记、压缩空白（不改库里的正文）。"""
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[#>]+\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"\*\*|__|`{1,3}", "", line)
        line = line.lstrip("|").replace("|", " ")
        if line:
            lines.append(line)
    return " ".join(" ".join(lines).split())[:SNIPPET_MAX]


def build_citations(chunks: list[dict]) -> list[dict]:
    """M5：唯一引用组装处。编号即展示顺序，从 1 开始。"""
    citations = []
    for i, chunk in enumerate(chunks, 1):
        snippet = _clean_snippet(chunk.get("content") or "")
        citations.append({
            "n": i,
            "filename": chunk.get("filename") or chunk.get("source") or "",
            "page": chunk.get("page") or "全文",
            "snippet": snippet,
            "chunk_id": chunk.get("id"),
        })
    return citations


def conversation_exists(container: Any, conversation_id: int) -> bool:
    """续聊前置校验：会话不存在要在**流建立之前**返回 404（04 §4.4）。"""
    with container.pool().connection() as conn:
        return container.conversations.get(conversation_id, conn=conn) is not None


def load_history(container: Any, conversation_id: int | None) -> list[dict]:
    """取最近 5 轮（≤4000 字符）历史，返回 [{"role","content"}]，旧 → 新。

    规则（10.多轮会话设计 §6.2）：
      1. 按 id 倒序取最多 2×轮数 条，再反转成旧→新；
      2. 从最新往旧累加，超过字符预算即停（保证最近的内容一定留下）；
      3. 裁完若首条是 assistant，说明它的 user 已被裁掉，整条丢弃。
    """
    if conversation_id is None:
        return []
    settings = container.settings
    try:
        with container.pool().connection() as conn:
            rows = container.conversations.load_recent_messages(
                conversation_id, settings.history_max_turns * 2, conn=conn
            )
    except DB_ERRORS as exc:
        raise DependencyUnavailable("DB_UNAVAILABLE") from exc

    kept: list[dict] = []
    total = 0
    for row in reversed(rows):
        content = row.get("content") or ""
        if kept and total + len(content) > settings.history_char_budget:
            break
        kept.append({"role": row["role"], "content": content})
        total += len(content)
    kept.reverse()
    while kept and kept[0]["role"] != "user":
        kept.pop(0)
    return kept


def retrieval_query(question: str, history: list[dict]) -> str:
    """检索 query = 上一轮 user 问题 + 当前问题（确定性拼接，不做模型改写）。"""
    previous = next((h["content"] for h in reversed(history) if h["role"] == "user"), "")
    previous = " ".join(previous.split())[:200]
    return f"{previous}\n{question}" if previous else question


def _save(
    container: Any,
    conversation_id: int | None,
    question: str,
    answer_text: str,
    citations: list[dict],
) -> int:
    """整轮落库：新会话建行 + 2 条消息；续聊追加 2 条并刷新 updated_at。"""
    with container.pool().connection() as conn:
        if conversation_id is None:
            title = " ".join(question.split())[:TITLE_MAX]
            return container.conversations.create_with_messages(
                title=title,
                question=question,
                answer=answer_text,
                citations=citations,
                conn=conn,
            )
        container.conversations.append_turn(
            conversation_id,
            question=question,
            answer=answer_text,
            citations=citations,
            conn=conn,
        )
        return conversation_id


async def ask_stream(
    container: Any, question: str, conversation_id: int | None = None
) -> AsyncIterator[bytes]:
    """返回 SSE 字节流（每个事件已编码）。

    `conversation_id` 非空 = 续在该会话后追加一轮，此时**按会话串行**（10.多轮会话设计 §9）：
    同一会话的两条提问不会交错写库，后到者等前一轮落库完再开始。
    """
    if conversation_id is None:
        async for chunk in _run_turn(container, question, None):
            yield chunk
        return

    lock = container.conversation_lock(conversation_id)
    async with lock:
        async for chunk in _run_turn(container, question, conversation_id):
            yield chunk


async def _run_turn(
    container: Any, question: str, conversation_id: int | None
) -> AsyncIterator[bytes]:
    settings = container.settings

    # 0) 历史（仅续聊才取；读失败按依赖不可用处理，流已建立只能用 error 事件）
    try:
        history = await asyncio.to_thread(load_history, container, conversation_id)
    except Exception as exc:
        logger.error("读取历史失败 conv=%s err=%s", conversation_id, type(exc).__name__)
        yield error_event("DB_UNAVAILABLE")
        return

    # 1) 检索（同步阻塞，放线程池）；query 用「上一轮问题 + 当前问题」
    search_query = retrieval_query(question, history)
    try:
        chunks = await retrieval.aretrieve(container, search_query)
    except Exception as exc:
        logger.error("检索失败 question_len=%s err=%s", len(question), type(exc).__name__)
        yield error_event("DB_UNAVAILABLE")
        return

    citations = build_citations(chunks)
    answer_parts: list[str] = []

    if not citations:
        # 2a) 无结果：固定话术，不调大模型
        answer_parts.append(FALLBACK_TEXT)
        yield sse("delta", {"text": FALLBACK_TEXT})
    else:
        # 2b) 有结果：先引用，再流式
        yield sse("citations", {"items": citations})
        try:
            # stream=True 时 answer() 返回异步生成器；签名上是 union，这里显式收窄给类型检查看
            agen = cast(
                AsyncIterator[str],
                await llm.answer(
                    question,
                    chunks,
                    stream=True,
                    history=history,
                    timeout_first=settings.llm_timeout_first_byte,
                    timeout_total=settings.llm_timeout_total,
                ),
            )
            async for piece in agen:
                answer_parts.append(piece)
                yield sse("delta", {"text": piece})
        except asyncio.CancelledError:
            raise                                   # 客户端断开：不落库（SRS 7.4）
        except llm.LlmKeyMissing:
            yield error_event("LLM_KEY_MISSING")
            return
        except llm.LlmTimeout:
            yield error_event("LLM_TIMEOUT")
            return
        except Exception as exc:
            logger.error("生成失败 err=%s", type(exc).__name__)
            yield error_event("LLM_ERROR")
            return

    answer_text = "".join(answer_parts)
    if not answer_text.strip() and citations:
        yield error_event("LLM_ERROR")
        return

    # 3) 保存历史（问答都成功才写；一个事务）
    try:
        saved_id = await asyncio.to_thread(
            _save, container, conversation_id, question, answer_text, citations
        )
    except DB_ERRORS as exc:
        logger.error("保存历史失败 err=%s", type(exc).__name__)
        yield error_event("DB_UNAVAILABLE")
        return
    except asyncio.CancelledError:
        raise

    logger.info(
        "问答完成 conv_id=%s citations=%s history=%s answer_len=%s",
        saved_id, len(citations), len(history), len(answer_text),
    )
    yield sse("done", {"conversation_id": saved_id})
