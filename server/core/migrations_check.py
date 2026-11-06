"""启动期迁移版本校验（03 §6.7 规则 4）

只做**只读比对**：磁盘上的迁移文件 vs 库里的 `_yoyo_migration`。
落后只记 warning，绝不在启动时执行 DDL —— 迁移统一由 `scripts/migrate.py` 手动触发。
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("zhiwen.migrations")


def _migration_ids(migrations_dir: Path) -> list[str]:
    """迁移文件的 id（去扩展名），排除 `.rollback.sql`。"""
    ids = []
    for path in sorted(migrations_dir.glob("V*.sql")):
        if path.name.endswith(".rollback.sql"):
            continue
        ids.append(path.stem)
    return ids


def warn_if_behind(dsn: str, migrations_dir: Path) -> None:
    """比对版本，落后/超前只告警。任何异常都吞掉，不能影响启动。"""
    files = _migration_ids(migrations_dir)
    if not files:
        logger.warning("迁移目录为空或不存在：%s", migrations_dir)
        return

    try:
        import psycopg

        with psycopg.connect(dsn) as conn:
            exists = conn.execute("SELECT to_regclass('public._yoyo_migration')").fetchone()[0]
            if exists is None:
                logger.warning(
                    "未初始化迁移版本表（未跑过 scripts/migrate.py）；磁盘上有 %d 个迁移文件", len(files)
                )
                return
            applied = {row[0] for row in conn.execute("SELECT migration_id FROM _yoyo_migration").fetchall()}
    except Exception as exc:  # 数据库不可用在启动别处已处理，这里只跳过校验
        logger.warning("迁移版本校验跳过：%s", type(exc).__name__)
        return

    pending = [name for name in files if name not in applied]
    if pending:
        logger.warning(
            "数据库结构落后于代码：未执行的迁移 %s（执行 `python scripts/migrate.py apply`）",
            ", ".join(pending),
        )

    missing = sorted(applied - set(files))
    if missing:
        logger.warning(
            "库中记录但磁盘上不存在的迁移 %s（可能漏拉迁移文件，结构可能与代码不一致）",
            ", ".join(missing),
        )
