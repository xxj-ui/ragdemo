"""集中配置（NFR-6）

所有可调参数只在这里出现：检索/切分/上传上限/超时/连接池。
本模块**不导入**任何 Web 或数据库库，保持可被 CLI 复用。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# 本文件在 server/core/config.py → 上溯 3 层才是项目根（server/core → server → 根）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 目录一挪就会静默指错地方（上传文件会写进 server/ 里），启动即失败更安全
if not (PROJECT_ROOT / "requirements.txt").exists():
    raise RuntimeError(f"PROJECT_ROOT 解析错误：{PROJECT_ROOT} 下没有 requirements.txt")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw in (None, "") else int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw in (None, "") else float(raw)


@dataclass(frozen=True)
class Settings:
    """运行期配置。凡是"魔法数字"都应该是这里的字段。"""

    db_dsn: str

    # 服务（SRS 2.3 / D-8：只监听本机）
    host: str = "127.0.0.1"
    port: int = 8000

    # 数据库连接池（02 S-09 / 06 A4）
    db_pool_min: int = 1
    db_pool_max: int = 4
    db_pool_timeout: float = 5.0

    # 检索（SRS 5.2 / NFR-6）
    recall_k: int = 20
    top_k: int = 5
    rrf_k: int = 60

    # 切分（SRS FR-1）
    chunk_size: int = 500
    chunk_overlap: int = 100
    chunk_min_size: int = 80

    # 上传（SRS BR-8 / 04 V-8）
    max_file_size: int = 50 * 1024 * 1024
    max_request_size: int = 55 * 1024 * 1024
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"

    # 大模型（04 §3.7 / 06 A1）
    llm_model: str = "deepseek-chat"
    llm_timeout_first_byte: float = 15.0
    llm_timeout_total: float = 60.0

    # 健康检查
    health_probe_timeout: float = 2.0

    # 嵌入模型（SRS 2.4.4）
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dim: int = 512


def load_settings() -> Settings:
    """从环境变量装配配置；缺 RAG_DB_DSN 直接抛错（SRS 2.4.3 / P-3）。"""
    dsn = os.getenv("RAG_DB_DSN")
    if not dsn:
        raise RuntimeError(
            "未配置数据库连接串：请设置环境变量 RAG_DB_DSN，"
            "形如 postgresql://<user>:<password>@127.0.0.1:54328/ragdemo"
        )
    return Settings(
        db_dsn=dsn,
        port=_env_int("RAG_PORT", 8000),
        db_pool_min=_env_int("RAG_DB_POOL_MIN", 1),
        db_pool_max=_env_int("RAG_DB_POOL_MAX", 4),
        db_pool_timeout=_env_float("RAG_DB_POOL_TIMEOUT", 5.0),
        llm_timeout_first_byte=_env_float("RAG_LLM_TIMEOUT_FIRST_BYTE", 15.0),
        llm_timeout_total=_env_float("RAG_LLM_TIMEOUT_TOTAL", 60.0),
    )
