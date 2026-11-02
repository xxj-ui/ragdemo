"""M4 问答生成 + M5 引用组装（04 §4.4 事件序列）

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
from typing import Any, AsyncIterator

import psycopg
from psycopg_pool import PoolClosed, PoolTimeout

from server.core.errors import ERROR_CODES
from server.rag import llm
from server.services import retrieval

logger = logging.getLogger("ragdemo.chat")

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


def _save(container: Any, question: str, answer_text: str, citations: list[dict]) -> int:
    title = " ".join(question.split())[:TITLE_MAX]
    with container.pool().connection() as conn:
        return container.conversations.create_with_messages(
            title=title,
            question=question,
            answer=answer_text,
            citations=citations,
            conn=conn,
        )


async def ask_stream(container: Any, question: str) -> AsyncIterator[bytes]:
    """返回 SSE 字节流（每个事件已编码）。"""
    settings = container.settings

    # 1) 检索（同步阻塞，放线程池）
    try:
        chunks = await retrieval.aretrieve(container, question)
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
            agen = await llm.answer(
                question,
                chunks,
                stream=True,
                timeout_first=settings.llm_timeout_first_byte,
                timeout_total=settings.llm_timeout_total,
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
        conversation_id = await asyncio.to_thread(_save, container, question, answer_text, citations)
    except DB_ERRORS as exc:
        logger.error("保存历史失败 err=%s", type(exc).__name__)
        yield error_event("DB_UNAVAILABLE")
        return
    except asyncio.CancelledError:
        raise

    logger.info(
        "问答完成 conv_id=%s citations=%s answer_len=%s",
        conversation_id, len(citations), len(answer_text),
    )
    yield sse("done", {"conversation_id": conversation_id})
