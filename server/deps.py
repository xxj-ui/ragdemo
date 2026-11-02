"""单例装配（02 §4.2 / §3.3）

容器只负责"把依赖接好"，不做业务判断：仓储、连接池、进程内索引、模型状态位。
"""
from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from server.config import Settings, load_settings
from server.conversation_repository import ConversationRepository
from server.document_repository import DocumentRepository
from server.rag.bm25_index import Bm25Index
from server.rag.chunk_repository import PgChunkRepository


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

    # ------------------------------------------------------------------
    # 连接池（S-09：min=1 / max=4 / timeout=5s，行工厂 dict_row）
    # ------------------------------------------------------------------
    def pool(self) -> Any:
        if self._pool is None:
            from psycopg_pool import ConnectionPool

            self._pool = ConnectionPool(
                conninfo=self.settings.db_dsn,
                min_size=self.settings.db_pool_min,
                max_size=self.settings.db_pool_max,
                timeout=self.settings.db_pool_timeout,
                kwargs={"row_factory": dict_row},
                open=True,
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
