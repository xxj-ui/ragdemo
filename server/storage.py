"""原文件落盘（02 §4.2 支撑组件）

顺序约定（02 v0.4 / 03 §3.2）：
    临时文件 → rename 到正式路径（**事务提交前**）→ 事务 → 提交后删旧文件。
事务失败时删掉刚落盘的正式文件即可回到原状，旧文件从未被触碰。
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger("ragdemo.storage")

CHUNK = 1024 * 1024


class FileTooLarge(Exception):
    """流式写盘时超过上限。"""


def new_stored_path(upload_dir: Path, suffix: str) -> Path:
    """服务端生成的文件名：<uuid><ext>，与用户输入无关（AC-9）。"""
    return upload_dir / f"{uuid.uuid4().hex}{suffix.lower()}"


def save_stream(src: BinaryIO, dest: Path, max_bytes: int) -> int:
    """流式写盘；超过 max_bytes 立即中断并删除半成品。返回写入字节数。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with dest.open("wb") as out:
            while True:
                block = src.read(CHUNK)
                if not block:
                    break
                written += len(block)
                if written > max_bytes:
                    raise FileTooLarge(str(written))
                out.write(block)
    except FileTooLarge:
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return written


def promote(temp_path: Path, final_path: Path) -> None:
    """临时文件转正（同盘 rename，原子）。"""
    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_path, final_path)


def delete_quietly(path: Path) -> None:
    """删除原文件；ENOENT 视为成功，其它异常只记日志（03 Q4 已确认）。"""
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.error("删除原文件失败 path=%s err=%s", path, exc)
