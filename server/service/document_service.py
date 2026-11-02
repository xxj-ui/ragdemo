"""M1 文档管理 + M2 入库流水线的编排层（骨架）

实现要点（M1 落地时按此写，勿改顺序）：
  1. 校验由路由层完成；本层只做业务编排。
  2. 解析 → 切分 → 向量化全部成功后才动数据库（BR-2）。
  3. 文件先落到正式 stored_path → 一个事务内 upsert documents + 全量替换 chunks
     → 提交后删旧文件（02 v0.4 落盘顺序）。
  4. chunk_count 与片段写入同事务维护（03 §5.1）。
  5. 成功后 BM25 置失效（BR-4）。
"""
from __future__ import annotations

from typing import Any


async def upload(container: Any, upload_file: Any) -> dict:
    """处理单个文件，返回 04 §4.1 的 items[] 元素。"""
    raise NotImplementedError("M1 实现：见模块文档的 5 步")


def list_documents(container: Any) -> dict:
    raise NotImplementedError("M1 实现：DocumentRepository.list_all")


def delete_document(container: Any, document_id: int) -> None:
    """不存在 → DOCUMENT_NOT_FOUND；原文件删除失败只记日志（03 Q4）。"""
    raise NotImplementedError("M1 实现")
