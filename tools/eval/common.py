"""评测脚本共用的小工具：环境、落盘、断言、账目。

只做"跑评测时到处都要用的机械动作"，不含任何指标逻辑（指标在 metrics.py）。
probe.py / collect.py 都从这里取，避免两份重复实现漂移。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATASET_E1 = ROOT / "evals" / "datasets" / "e1-dataset.jsonl"
TOKEN_PER_HANZI = 0.614      # 实测：DeepSeek 对中文正文约 0.614 token/汉字（见 11 号文档 §6.1）


# ---------------------------------------------------------------- 环境

def pg_dsn() -> str:
    """优先用环境变量；没有就从本机容器取（不落盘、不打印密码）。"""
    if os.getenv("RAG_DB_DSN"):
        return os.environ["RAG_DB_DSN"]
    out = subprocess.run(
        ["docker", "inspect", "ragdemo-pg", "--format", "{{range .Config.Env}}{{println .}}{{end}}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        raise SystemExit("未设置 RAG_DB_DSN，且无法从容器读取：" + out.stderr[:300])
    pw = next((ln.split("=", 1)[1] for ln in out.stdout.splitlines() if ln.startswith("POSTGRES_PASSWORD=")), None)
    if not pw:
        raise SystemExit("找不到 POSTGRES_PASSWORD")
    return f"postgresql://root:{pw}@127.0.0.1:54328/ragdemo"


def load_env_file() -> None:
    """把项目根 .env 的键值注入环境变量（已存在的不覆盖）。.env 不入库。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def prepare_env() -> None:
    """导入 server.* 之前必须完成：DSN、HF 缓存、项目根进 sys.path。"""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    load_env_file()
    os.environ["RAG_DB_DSN"] = pg_dsn()
    os.environ.setdefault("HF_HOME", os.path.expanduser("~/.cache/huggingface"))


def load_deepseek_key() -> None:
    """DEEPSEEK_API_KEY 由环境变量或项目根 .env 提供，都没有就跳过（由 llm 层报错）。"""
    load_env_file()


# ---------------------------------------------------------------- 落盘与账目

def new_run_dir(kind: str) -> tuple[str, Path]:
    run_id = f"{kind}-{datetime.now():%Y%m%d-%H%M%S}"
    out = ROOT / "evals" / "runs" / run_id
    out.mkdir(parents=True, exist_ok=True)
    return run_id, out


def setup_logging(log_path: Path) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_info() -> dict:
    def run(*args: str) -> str:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else ""

    return {"head": run("rev-parse", "HEAD") or "unknown", "dirty": bool(run("status", "--porcelain"))}


def resolve_dataset(name_or_path: str | None) -> Path:
    """接受文件名（evals/datasets/<name>.jsonl 的 name）或完整路径；None = E1。"""
    if not name_or_path:
        return DATASET_E1
    p = Path(name_or_path)
    if p.exists():
        return p
    cand = ROOT / "evals" / "datasets" / (name_or_path if name_or_path.endswith(".jsonl") else f"{name_or_path}.jsonl")
    if cand.exists():
        return cand
    raise SystemExit(f"找不到数据集：{name_or_path}")


def load_samples(path: Path | None = None) -> list[dict]:
    path = path or DATASET_E1
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def ensure_sample_ids(rows: list[dict]) -> list[dict]:
    """池子文件（crud-pool-usable）没有 sample_id，按行序补 p001…；有就原样保留。

    行序固定 → 同一文件在 P1/P2 得到同一批 id，交叉校验才成立。
    """
    for i, r in enumerate(rows, 1):
        r.setdefault("sample_id", f"p{i:03d}")
    return rows


def db_counts(container) -> dict:
    with container.pool().connection() as conn:      # 池的 row_factory=dict_row
        chunks = conn.execute("select count(*) as n from rag_chunks").fetchone()["n"]
        docs = conn.execute("select count(*) as n from documents").fetchone()["n"]
    return {"chunks": chunks, "docs": docs}


def est_tokens(text: str) -> int:
    """中文正文 token 估算（比例实测，不是 tiktoken）。tiktoken cl100k 会高估 ~77%。"""
    return int(len(text or "") * TOKEN_PER_HANZI)


def dump_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
