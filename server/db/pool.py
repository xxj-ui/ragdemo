"""数据库连接池（02 S-09）：min=1 / max=4 / timeout=5 s，行工厂统一 `dict_row`。

池只在 `Container.pool()` 里惰性创建一次；进程退出时由 `Container.close()` 关闭。
"""
from __future__ import annotations

from typing import Any


def create_pool(dsn: str, min_size: int, max_size: int, timeout: float) -> Any:
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    return ConnectionPool(
        conninfo=dsn,
        min_size=min_size,
        max_size=max_size,
        timeout=timeout,
        kwargs={"row_factory": dict_row},
        open=True,
    )
