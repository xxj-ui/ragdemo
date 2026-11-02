"""单例装配（02 §4.2 / §3.3）

框架期只装配"空壳"：连接池与仓储按需创建，不在这里做任何查询。
"""
from __future__ import annotations

from typing import Any

from server.config import Settings, load_settings
from server.conversation_repository import ConversationRepository
from server.document_repository import DocumentRepository


class Container:
    """进程内单例集合（单 worker，02 S-01）。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pool: Any = None
        self.documents = DocumentRepository(self)
        self.conversations = ConversationRepository(self)
        # 进程内状态位，供 /api/health 读取（02 §2.6）
        self.model_state: str = "loading"

    def pool(self) -> Any:
        """惰性创建连接池（S-09：min=1 / max=4 / timeout=5s）。"""
        if self._pool is None:
            from psycopg_pool import ConnectionPool  # 惰性导入：未安装时不影响 CLI

            self._pool = ConnectionPool(
                conninfo=self.settings.db_dsn,
                min_size=self.settings.db_pool_min,
                max_size=self.settings.db_pool_max,
                timeout=self.settings.db_pool_timeout,
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
