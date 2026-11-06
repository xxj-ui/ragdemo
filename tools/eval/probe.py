"""P1：检索层基线（30 题，零 LLM 成本，只读不写库）。

跑法（项目根目录）：
    D:/develop/python/python.exe -m tools.eval.probe

产物（evals/runs/ret-<ts>/）：
    config.json          参数 + 库快照 + 数据集 sha256 + git 版本
    samples.jsonl        逐题：top-5 明细、top-40 id 序列、三路名次、延迟
    gold-chunk-map.json  每题 gold → 正确块集合 + 覆盖率
    report.md            对外结论（唯一对外口径）
    run.log              stdout 全量

红线：
    1) 旁路自融的 top-5 必须与生产 retrieve() 完全一致（等价性断言）；
    2) 跑前跑后各断言一次库规模，变了就作废；
    3) 不写库、不建会话、不改 server/ 一行。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.eval import common, goldmap, metrics, report  # noqa: E402

DATASET = ROOT / "evals" / "datasets" / "e1-dataset.jsonl"   # 默认 E1；--dataset 可覆盖
EVAL_TOP_K = 40          # 评测口径候选深度
SENSITIVITY = goldmap.SENSITIVITY

logger = logging.getLogger("tools.eval.probe")


# ---------------------------------------------------------------- 环境准备

def pg_dsn() -> str:
    """优先用已有环境变量；没有就从容器里取（本机 PostgreSQL 跑在 zhiwen-pg）。"""
    if os.getenv("RAG_DB_DSN"):
        return os.environ["RAG_DB_DSN"]
    out = subprocess.run(
        ["docker", "inspect", "zhiwen-pg", "--format", "{{range .Config.Env}}{{println .}}{{end}}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        raise SystemExit("未设置 RAG_DB_DSN，且无法从容器读取：" + out.stderr[:300])
    pw = next((ln.split("=", 1)[1] for ln in out.stdout.splitlines() if ln.startswith("POSTGRES_PASSWORD=")), None)
    if not pw:
        raise SystemExit("找不到 POSTGRES_PASSWORD")
    return f"postgresql://root:{pw}@127.0.0.1:54328/zhiwen"


def git_info() -> dict:
    def run(*args: str) -> str:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else ""

    head = run("rev-parse", "HEAD")
    dirty = bool(run("status", "--porcelain"))
    return {"head": head or "unknown", "dirty": dirty}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def db_counts(container) -> dict:
    with container.pool().connection() as conn:      # 池的 row_factory=dict_row
        chunks = conn.execute("select count(*) as n from rag_chunks").fetchone()["n"]
        docs = conn.execute("select count(*) as n from documents").fetchone()["n"]
    return {"chunks": chunks, "docs": docs}


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


# ---------------------------------------------------------------- 主流程

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P1 检索基线")
    ap.add_argument("--dataset", default="", help="数据集文件名（evals/datasets/<name>.jsonl）或完整路径")
    args, _ = ap.parse_known_args(argv)
    dataset_path = common.resolve_dataset(args.dataset) if args.dataset else DATASET

    os.environ["RAG_DB_DSN"] = pg_dsn()
    os.environ.setdefault("HF_HOME", os.path.expanduser("~/.cache/huggingface"))

    run_id = f"ret-{datetime.now():%Y%m%d-%H%M%S}"
    out_dir = ROOT / "evals" / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(out_dir / "run.log")
    logger.info("run_id=%s out=%s", run_id, out_dir)

    from server.api.deps import Container
    from server.core.config import load_settings
    from server.rag.embedder import embed_query
    from server.rag.rrf import rrf_fuse
    from server.services import retrieval

    samples = common.ensure_sample_ids(common.load_samples(dataset_path))
    logger.info("数据集 %s，%d 题", dataset_path.name, len(samples))

    settings = load_settings()
    container = Container(settings)
    exit_code = 0
    try:
        db_before = db_counts(container)
        logger.info("库快照（跑前）：%s", db_before)

        t = time.perf_counter(); embed_query("预热"); warm_embed = time.perf_counter() - t
        t = time.perf_counter(); index = container.bm25.ensure_built(container.chunks.fetch_all)
        warm_bm25 = time.perf_counter() - t
        logger.info("预热：嵌入模型 %.2f s，BM25 构建 %.2f s（%d 块）", warm_embed, warm_bm25, index.size)

        chunks = container.chunks.fetch_all()
        t = time.perf_counter()
        gm = goldmap.build(chunks, samples)
        gm_seconds = time.perf_counter() - t
        n_correct = sum(len(v["correct_union"]) for v in gm.values())
        logger.info("gold→正确块映射完成（%.1f s），正确块合计 %d（阈值 %.1f）", gm_seconds, n_correct, goldmap.HIT_COVERAGE)

        rows, samples_out, equiv_bad = [], [], []
        for i, s in enumerate(samples, 1):
            sid = s["sample_id"]
            q = s["user_input"]
            correct = set(gm[sid]["correct_union"])

            t = time.perf_counter()
            prod = retrieval.retrieve(container, q)               # 生产口径：top_k / recall_k 取 Settings
            latency_ms = (time.perf_counter() - t) * 1000

            dense40 = container.chunks.search(embed_query(q), top_k=EVAL_TOP_K)
            kw40 = index.search(q, top_k=EVAL_TOP_K)

            # 生产等价：两路各取 recall_k（默认 20）再融合，只是把 top_k 放大到 40 便于算 Recall@k
            hybrid_prod = rrf_fuse([("dense", dense40[: settings.recall_k]),
                                    ("bm25", kw40[: settings.recall_k])],
                                   k=settings.rrf_k, top_k=EVAL_TOP_K)
            hybrid40 = rrf_fuse([("dense", dense40), ("bm25", kw40)], k=settings.rrf_k, top_k=EVAL_TOP_K)

            prod_ids = [c["id"] for c in prod]
            local_ids = [c["id"] for c in hybrid_prod[: len(prod_ids)]]
            equiv = prod_ids == local_ids
            if not equiv:
                equiv_bad.append({"sample_id": sid, "prod": prod_ids, "local": local_ids})
                logger.error("等价性不一致 %s：prod=%s local=%s", sid, prod_ids, local_ids)

            dense_ids = [d["id"] for d in dense40]
            kw_ids = [d["id"] for d in kw40]
            hp_ids = [d["id"] for d in hybrid_prod]
            h40_ids = [d["id"] for d in hybrid40]

            for key, ranked in (("hybrid_prod", hp_ids), ("dense", dense_ids), ("bm25", kw_ids), ("hybrid_40", h40_ids)):
                rows.append({"sample_id": sid, "route": key, "ranked": ranked, "correct": correct})

            first_hit = metrics.first_hit_rank(hp_ids, correct, 10)
            samples_out.append({
                "sample_id": sid, "id": s["id"], "subset_label": s["subset_label"], "idx": i,
                "user_input": q, "n_gold": s.get("n_gold"), "n_correct": len(correct),
                "latency_ms": round(latency_ms, 2),
                "recall@5": metrics.recall_at(hp_ids, correct, 5),
                "first_hit_rank": first_hit,
                "ranked": {
                    "hybrid_prod": hp_ids,
                    "dense": dense_ids,
                    "bm25": kw_ids,
                    "hybrid_40": h40_ids,
                },
                "top5_detail": [
                    {"n": n, "chunk_id": c["id"], "chunk_index": c.get("chunk_index"),
                     "filename": c.get("filename"), "rrf_score": round(c.get("rrf_score", 0.0), 6),
                     "routes": c.get("routes"), "is_correct": c["id"] in correct}
                    for n, c in enumerate(prod, 1)
                ],
            })
            logger.info("[%02d/%02d] %s %s Recall@5=%.2f 首个命中=%s %.0f ms",
                        i, len(samples), sid, s["subset_label"],
                        metrics.recall_at(hp_ids, correct, 5), first_hit, latency_ms)

        # 分路汇总
        def agg_route(key: str, th: float | None = None) -> dict:
            rs = []
            for s in samples:
                sid = s["sample_id"]
                cr = set(gm[sid]["correct_union"]) if th is None else goldmap.correct_ids_at(gm[sid], th)
                ranked = next(r["ranked"] for r in rows if r["sample_id"] == sid and r["route"] == key)
                rs.append({"ranked": ranked, "correct": cr})
            return metrics.summarize(rs)

        agg = {
            "hybrid_prod": agg_route("hybrid_prod"),
            "dense": agg_route("dense"),
            "bm25": agg_route("bm25"),
            "hybrid_40": agg_route("hybrid_40"),
        }
        sensitivity = {}
        for th in SENSITIVITY:
            m = agg_route("hybrid_prod", th)
            m["n_correct"] = sum(len(goldmap.correct_ids_at(gm[s["sample_id"]], th)) for s in samples)
            sensitivity[str(th)] = m
        agg["sensitivity"] = sensitivity

        db_after = db_counts(container)
        logger.info("库快照（跑后）：%s", db_after)
        db_stable = db_before == db_after
        if not db_stable:
            logger.error("库规模变化，本次结果作废：%s → %s", db_before, db_after)
            exit_code = 1
        if equiv_bad:
            exit_code = 1

        lat = {
            "p50_ms": metrics.percentile([r["latency_ms"] for r in samples_out], 50),
            "p95_ms": metrics.percentile([r["latency_ms"] for r in samples_out], 95),
            "min_ms": min(r["latency_ms"] for r in samples_out),
            "max_ms": max(r["latency_ms"] for r in samples_out),
        }

        config = {
            "run_id": run_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "kind": "retrieval-baseline",
            "dataset": {"file": str(dataset_path.relative_to(ROOT)).replace("\\", "/"),
                        "sha256": sha256_file(dataset_path), "records": len(samples)},
            "params": {"top_k": settings.top_k, "recall_k": settings.recall_k, "rrf_k": settings.rrf_k,
                       "chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap,
                       "chunk_min_size": settings.chunk_min_size,
                       "embedding": settings.embedding_model,
                       "eval_top_k": EVAL_TOP_K, "hit_coverage": goldmap.HIT_COVERAGE,
                       "gold_window": goldmap.WIN, "gold_stride": goldmap.STRIDE},
            "db": db_before,
            "warmup": {"embedder_s": round(warm_embed, 2), "bm25_s": round(warm_bm25, 2)},
            "git": git_info(),
            "assertions": {"db_stable": db_stable, "db_after": db_after,
                           "equiv_ok": not equiv_bad, "equiv_ok_n": len(samples) - len(equiv_bad),
                           "n": len(samples), "equiv_mismatch": equiv_bad},
            "timing": {"goldmap_s": round(gm_seconds, 1)},
        }
        ctx = {
            "config": config, "goldmap": gm, "rows": samples_out, "agg": agg,
            "latency": lat, "assertions": config["assertions"],
        }

        report.dump_json(out_dir / "config.json", config)
        report.dump_json(out_dir / "gold-chunk-map.json", gm)
        with (out_dir / "samples.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for rec in samples_out:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        report.write(out_dir / "report.md", report.build(ctx))

        logger.info("主指标 Recall@5=%.3f MRR@10=%.3f Hit@5=%.3f（n=%d）",
                    agg["hybrid_prod"]["recall@5"], agg["hybrid_prod"]["mrr@10"], agg["hybrid_prod"]["hit@5"], len(samples))
        logger.info("分路 Recall@5：稠密 %.3f / BM25 %.3f / 混合 %.3f / 混合40 %.3f",
                    agg["dense"]["recall@5"], agg["bm25"]["recall@5"],
                    agg["hybrid_prod"]["recall@5"], agg["hybrid_40"]["recall@5"])
        logger.info("产物已写入 %s", out_dir)
    finally:
        container.close()
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
