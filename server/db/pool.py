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
        # 出池前探活：数据库重启 / 容器重建后，池里会留着死连接。
        # psycopg_pool 默认不校验，死连接会被反复发出去，每个请求都是
        # OperationalError → 被统一映射成 DB_UNAVAILABLE，只能重启进程才好。
        # check_connection 在交给调用方之前探一次，坏了就丢弃并补一条新连接。
        check=ConnectionPool.check_connection,
        open=True,
    )
