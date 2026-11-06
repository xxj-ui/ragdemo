"""M7 系统状态（04 §4.8）

三项探测：数据库（SELECT 1，带短超时）/ 嵌入模型（进程内状态位）/ 大模型 Key（环境变量）。
任一不满足 → status="degraded"；接口恒返 200（02 S-08）。
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("zhiwen.health")

DB_PROBE_SQL = "SELECT 1"


def probe(container: Any) -> dict:
    settings = container.settings

    database = "ok"
    try:
        with container.pool().connection(timeout=settings.health_probe_timeout) as conn:
            conn.execute(DB_PROBE_SQL)
    except Exception as exc:  # 池超时、连接失败、查询失败都算不可用
        logger.warning("健康检查：数据库探测失败 err=%s", type(exc).__name__)
        database = "error"

    model = getattr(container, "model_state", "loading")
    warmup = getattr(container, "warmup_state", "idle")
    llm_key = "configured" if os.getenv("DEEPSEEK_API_KEY") else "missing"

    ok = database == "ok" and model == "loaded" and llm_key == "configured"
    return {
        "status": "ok" if ok else "degraded",
        "database": database,
        "embedding_model": model,
        "warmup": warmup,
        "llm_key": llm_key,
    }
