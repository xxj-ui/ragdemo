"""数据库迁移入口（yoyo-migrations，见 03.数据库设计 §6.7）

用法（在项目根目录执行，连接串从 RAG_DB_DSN 读）：
    python scripts/migrate.py status                  # 列出每个迁移：A=已执行 / U=未执行
    python scripts/migrate.py mark V001__init_schema  # 只写版本记录、不执行（存量库 baseline）
    python scripts/migrate.py apply                   # 执行所有未执行迁移（单事务）
    python scripts/migrate.py rollback V002__multiturn_conversations

约定：
  - 不接收 --database 参数，密码只经环境变量传递，避免进 shell 历史与日志；
  - 应用启动**不**隐式迁移（03 §6.7 规则 4），迁移只由本脚本手动触发；
  - 已执行过的迁移文件禁止修改（yoyo 校验和不符会报错），修正只能追加新迁移。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from yoyo import get_backend, read_migrations

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "scripts" / "sql" / "migrations"


def _dsn() -> str:
    """RAG_DB_DSN → yoyo 需要的 driver 形式（postgresql+psycopg://…）。"""
    raw = (os.getenv("RAG_DB_DSN") or "").strip()
    if not raw:
        sys.exit("未配置 RAG_DB_DSN（形如 postgresql://user:pass@127.0.0.1:54328/zhiwen）")
    if raw.startswith("postgresql+psycopg://"):
        return raw
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://"):]
    sys.exit("RAG_DB_DSN 需为 postgresql:// 形式")


def _pick(migrations, name: str):
    """按完整 id 或唯一前缀找迁移。"""
    hits = [m for m in migrations if m.id == name or m.id.startswith(name)]
    if len(hits) != 1:
        ids = ", ".join(m.id for m in migrations)
        sys.exit(f"找不到唯一的迁移 {name!r}；现有：{ids}")
    return hits[0]


def main(argv: list[str]) -> int:
    cmd = (argv[0] if argv else "status").lower()
    migrations = read_migrations(str(MIGRATIONS_DIR))
    if not migrations:
        sys.exit(f"目录里没有迁移文件：{MIGRATIONS_DIR}")

    backend = get_backend(_dsn())
    try:
        pending = {m.id for m in backend.to_apply(migrations)}

        if cmd == "status":
            print(f"迁移目录：{MIGRATIONS_DIR}")
            for m in migrations:
                print(f"  {'A' if m.id not in pending else 'U'}  {m.id}")
            print(f"\n已执行 {len(migrations) - len(pending)} / 共 {len(migrations)}；"
                  f"未执行 {len(pending)}")
            return 0

        if cmd == "mark":
            if len(argv) < 2:
                sys.exit("用法：python scripts/migrate.py mark <迁移 id 或唯一前缀>")
            target = _pick(migrations, argv[1])
            if target.id not in pending:
                print(f"{target.id} 已是已执行状态，无需 mark")
                return 0
            backend.mark_migrations([target])
            print(f"已标记为已执行（未执行 SQL）：{target.id}")
            return 0

        if cmd == "apply":
            todo = backend.to_apply(migrations)
            if not todo:
                print("没有待执行的迁移")
                return 0
            for m in todo:
                print(f"执行：{m.id}")
            backend.apply_migrations(todo)
            print(f"完成，共执行 {len(todo)} 个迁移")
            return 0

        if cmd == "rollback":
            if len(argv) < 2:
                sys.exit("用法：python scripts/migrate.py rollback <迁移 id 或唯一前缀>")
            target = _pick(migrations, argv[1])
            if target.id in pending:
                print(f"{target.id} 尚未执行，无需回滚")
                return 0
            backend.rollback_migrations([target])
            print(f"已回滚：{target.id}（执行同名的 .rollback.sql）")
            return 0

        sys.exit(f"未知命令 {cmd!r}；支持：status / mark / apply / rollback")
    finally:
        conn = getattr(backend, "connection", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
