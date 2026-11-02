"""M1 文档管理 + M2 入库流水线（02 §2.3 / 03 §3.2）

处理顺序（不可调换）：
  1. 逐文件校验（扩展名 / 文件名 / 大小 / 空文件）—— 失败是"这一项失败"，不是请求失败
  2. 流式落盘到临时文件（超限即中断）
  3. 解析（空结果视为失败）→ 切分 → 向量化
  4. 临时文件 rename 为正式路径（**事务提交之前**）
  5. 一个事务内：upsert documents → 全量替换 chunks → 更新 chunk_count
  6. 提交后删旧原文件；BM25 置失效
失败路径：任一步失败 → 删除刚写的文件、旧数据与旧原文件保持原样（BR-2）。
数据库完全不可用 → 抛 `DB_UNAVAILABLE`（请求级 503，不塞进 items[].error）。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

import psycopg
from psycopg_pool import PoolClosed, PoolTimeout

from server import storage
from server.config import PROJECT_ROOT
from server.errors import ERROR_CODES, DependencyUnavailable, NotFoundError
from server.rag import embedder, loaders, splitter
from server.timeutil import to_local_iso

logger = logging.getLogger("ragdemo.document_service")

# 数据库侧故障统一映射成 503：连接失败 / 池超时 / 池已关闭
DB_ERRORS = (psycopg.OperationalError, PoolTimeout, PoolClosed)

ALLOWED_SUFFIXES = {".pdf", ".docx", ".md", ".txt", ".xlsx", ".csv"}
TABLE_SUFFIXES = {".xlsx", ".csv"}


def _item_error(filename: str, code: str, message: str | None = None) -> dict:
    return {
        "filename": filename,
        "status": "failed",
        "document_id": None,
        "chunks": 0,
        "overwritten": False,
        "error": {"code": code, "message": message or ERROR_CODES[code][1]},
    }


def _validate_filename(name: str) -> str | None:
    """返回错误码；None 表示通过（AC-9：拒绝路径分隔符与 `..`）。"""
    if not name or len(name) > 255:
        return "INVALID_FILENAME"
    if "/" in name or "\\" in name or ".." in name:
        return "INVALID_FILENAME"
    if name.strip(". ") == "":
        return "INVALID_FILENAME"
    return None


def _drain(src, dest: Path, max_bytes: int) -> int:
    return storage.save_stream(src, dest, max_bytes)


def _doc_item(row: dict) -> dict:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "file_type": row["file_type"],
        "file_size": row["file_size"],
        "chunk_count": row["chunk_count"],
        "created_at": to_local_iso(row["created_at"]),
        "updated_at": to_local_iso(row["updated_at"]),
    }


async def upload(container: Any, upload_file: Any) -> dict:
    settings = container.settings
    filename = (upload_file.filename or "").strip()
    suffix = Path(filename).suffix.lower()

    bad = _validate_filename(filename)
    if bad:
        return _item_error(filename, bad)
    if suffix not in ALLOWED_SUFFIXES:
        return _item_error(filename, "UNSUPPORTED_FILE_TYPE", f"不支持的文件类型：{suffix or '（无扩展名）'}")

    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp = upload_dir / f".incoming-{uuid.uuid4().hex}{suffix}"

    try:
        size = await asyncio.to_thread(_drain, upload_file.file, temp, settings.max_file_size)
    except storage.FileTooLarge:
        return _item_error(filename, "FILE_TOO_LARGE")
    except OSError as exc:
        logger.warning("上传落盘失败 file=%s err=%s", filename, exc)
        temp.unlink(missing_ok=True)
        return _item_error(filename, "STORAGE_FAILED")
    if size == 0:
        temp.unlink(missing_ok=True)
        return _item_error(filename, "EMPTY_FILE")

    try:
        docs = await asyncio.to_thread(loaders.load, temp)
    except Exception as exc:
        logger.info("解析失败 file=%s err=%s", filename, exc)
        temp.unlink(missing_ok=True)
        code = "TABLE_EMPTY" if suffix in TABLE_SUFFIXES else "PARSE_FAILED"
        return _item_error(filename, code)

    if not any((d.get("text") or "").strip() for d in docs):
        temp.unlink(missing_ok=True)
        code = "TABLE_EMPTY" if suffix in TABLE_SUFFIXES else "PARSE_FAILED"
        return _item_error(filename, code)

    chunks = await asyncio.to_thread(
        splitter.split_documents,
        docs,
        settings.chunk_size,
        settings.chunk_overlap,
        settings.chunk_min_size,
    )
    texts = [c["text"] for c in chunks]
    try:
        vectors = await asyncio.to_thread(embedder.embed_documents, texts)
        container.model_state = "loaded"
    except Exception as exc:
        container.model_state = "failed"
        logger.error("向量化失败 file=%s err=%s", filename, exc)
        temp.unlink(missing_ok=True)
        return _item_error(filename, "EMBEDDING_FAILED")

    final = storage.new_stored_path(upload_dir, suffix)
    try:
        await asyncio.to_thread(storage.promote, temp, final)
    except OSError as exc:
        logger.error("文件转正失败 file=%s err=%s", filename, exc)
        temp.unlink(missing_ok=True)
        return _item_error(filename, "STORAGE_FAILED")

    stored_path = final.relative_to(PROJECT_ROOT).as_posix()
    file_type = suffix.lstrip(".")

    existing: dict | None = None
    try:
        with container.pool().connection() as conn:
            existing = container.documents.find_by_filename(filename, conn=conn)
            if existing is not None:
                document_id = existing["id"]
                container.documents.replace_meta(
                    document_id,
                    filename=filename,
                    stored_path=stored_path,
                    file_type=file_type,
                    file_size=size,
                    conn=conn,
                )
                container.chunks.delete_by_document(document_id, conn=conn)
            else:
                document_id = container.documents.insert(
                    filename=filename,
                    stored_path=stored_path,
                    file_type=file_type,
                    file_size=size,
                    conn=conn,
                )
            container.chunks.insert_for_document(document_id, filename, chunks, vectors, conn=conn)
            container.documents.update_chunk_count(document_id, len(chunks), conn=conn)
    except DB_ERRORS as exc:
        final.unlink(missing_ok=True)
        logger.error("入库失败（数据库不可用） file=%s err=%s", filename, exc)
        raise DependencyUnavailable("DB_UNAVAILABLE") from exc
    except Exception:
        final.unlink(missing_ok=True)
        logger.exception("入库失败 file=%s", filename)
        raise

    if existing is not None:
        storage.delete_quietly(PROJECT_ROOT / existing["stored_path"])
    container.bm25.invalidate()

    logger.info(
        "入库成功 file=%s doc_id=%s chunks=%s overwritten=%s size=%s",
        filename, document_id, len(chunks), existing is not None, size,
    )
    return {
        "filename": filename,
        "status": "success",
        "document_id": document_id,
        "chunks": len(chunks),
        "overwritten": existing is not None,
        "error": None,
    }


def list_documents(container: Any) -> dict:
    try:
        with container.pool().connection() as conn:
            rows = container.documents.list_all(conn=conn)
    except DB_ERRORS as exc:
        raise DependencyUnavailable("DB_UNAVAILABLE") from exc
    return {"items": [_doc_item(r) for r in rows]}


def delete_document(container: Any, document_id: int) -> None:
    try:
        with container.pool().connection() as conn:
            doc = container.documents.get(document_id, conn=conn)
            if doc is None:
                raise NotFoundError("DOCUMENT_NOT_FOUND")
            container.chunks.delete_by_document(document_id, conn=conn)
            container.documents.delete(document_id, conn=conn)
    except DB_ERRORS as exc:
        raise DependencyUnavailable("DB_UNAVAILABLE") from exc

    storage.delete_quietly(PROJECT_ROOT / doc["stored_path"])
    container.bm25.invalidate()
    logger.info("删除成功 doc_id=%s file=%s", document_id, doc["filename"])
