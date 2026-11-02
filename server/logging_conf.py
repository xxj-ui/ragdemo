"""日志与 request_id（02 §3.3 / AGENTS §7.6）

只记录结构化关键字段：request_id / 方法 / 路径 / 状态码 / 耗时 / 业务标识。
不打印全文、不打印密钥或 DSN。
"""
from __future__ import annotations

import contextvars
import logging
import sys
import uuid

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(_RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
