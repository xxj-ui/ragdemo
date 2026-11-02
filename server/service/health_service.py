"""M7 系统状态（骨架）

三项探测：数据库（SELECT 1，带短超时）/ 嵌入模型（进程内状态位）/ 大模型 Key（环境变量）。
判定：任一不满足 → status="degraded"（02 S-08 恒返 200）。
"""
from __future__ import annotations

from typing import Any


def probe(container: Any) -> dict:
    raise NotImplementedError("M1 实现：三项探测，单次总耗时 ≤ health_probe_timeout")
