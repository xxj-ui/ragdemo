"""依赖装配（02 §4.2 / §3.3）

容器只负责"把依赖接好"，不做业务判断：仓储、连接池、进程内索引、模型状态位。
请求级与进程级都从这里取，`app.py` 只管装配与横切。
"""
from __future__ import annotations

from typing import Any

from server.core.config import Settings, load_settings
from server.db import pool as db_pool
from server.db.chunks import PgChunkRepository
from server.db.conversations import ConversationRepository
from server.db.documents import DocumentRepository
from server.rag.bm25_index import Bm25Index


class Container:
    """进程内单例集合（单 worker，02 S-01）。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pool: Any = None
        self.documents = DocumentRepository(settings.db_dsn)
        self.conversations = ConversationRepository(settings.db_dsn)
        self.chunks = PgChunkRepository(settings.db_dsn)
        self.bm25 = Bm25Index()
        # 进程内状态位，供 /api/health 读取（02 §2.6）
        self.model_state: str = "loading"

    def pool(self) -> Any:
        if self._pool is None:
            self._pool = db_pool.create_pool(
                self.settings.db_dsn,
                self.settings.db_pool_min,
                self.settings.db_pool_max,
                self.settings.db_pool_timeout,
            )
        return self._pool

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container(load_settings())
    return _container


def set_container(container: Container | None) -> None:
    """测试用：注入/清空容器。"""
    global _container
    _container = container
