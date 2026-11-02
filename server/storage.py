"""原文件落盘（02 §4.2 支撑组件 / 03 §3.2 落盘顺序）

骨架：只定契约，M1 实现。
顺序约定（02 v0.4）：临时文件 → rename 到正式路径（事务提交前）→ 事务 → 提交后删旧文件。
"""
from __future__ import annotations

from pathlib import Path


def new_stored_path(upload_dir: Path, suffix: str) -> Path:
    """服务端生成的文件名：<uuid>.<ext>，与用户输入无关（AC-9）。"""
    raise NotImplementedError("M1 实现：生成 data/uploads/<uuid>.<ext>")


def save_stream(src, dest: Path, max_bytes: int) -> int:
    """流式写盘，超过 max_bytes 立即中断；返回写入字节数。"""
    raise NotImplementedError("M1 实现：流式落盘 + 超限中断")


def delete_quietly(path: Path) -> None:
    """删除原文件；ENOENT 视为成功，其它异常只记日志（03 Q4 已确认）。"""
    raise NotImplementedError("M1 实现")
