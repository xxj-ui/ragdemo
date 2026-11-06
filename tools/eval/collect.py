"""P2：采集生成层的原料（30 题，真实链路，只读不写库）。

跑法（项目根目录）：
    D:/develop/python/python.exe -m tools.eval.collect
    D:/develop/python/python.exe -m tools.eval.collect --report-only evals/runs/e1-<ts>   # 只重排报告

产物（evals/runs/e1-<ts>/）：
    config.json    参数 + 库快照 + 数据集 sha256 + git 版本 + 模型名
    samples.jsonl  每题：user_input / retrieved_contexts（原文 5 条）/ response / reference
                   + retrieved_context_ids + 耗时 + token 估算（P3 直接喂 RAGAS）
    report.md      采集摘要（成功数、兜底数、延迟、与 P1 检索结果的一致性）
    run.log        stdout 全量

为什么要单独一步：
    RAGAS 需要的是「系统实际拿到的证据」和「系统实际给出的答案」，
    这两样必须由真实链路产生并冻结，不能事后补；冻结之后 P3 才可复现、可对比。
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import cast

from tools.eval import common, report

logger = logging.getLogger("tools.eval.collect")


def latest_retrieval_run() -> dict | None:
    """找最近一次 ret-* run，用来交叉校验本次采样到的检索结果是否与 P1 一致。"""
    runs = sorted((common.ROOT / "evals" / "runs").glob("ret-*"), reverse=True)
    if not runs:
        return None
    samples = runs[0] / "samples.jsonl"
    if not samples.exists():
        return None
    rows = common.load_samples(samples)
    return {"run_id": runs[0].name,
            "by_sample": {r["sample_id"]: r["ranked"]["hybrid_prod"][:5] for r in rows}}


async def collect(container, samples: list[dict]) -> tuple[list[dict], dict]:
    from server.rag import llm
    from server.rag.embedder import embed_query
    from server.services import retrieval
    from server.services.chat import FALLBACK_TEXT

    settings = container.settings
    t = time.perf_counter(); embed_query("预热"); warm_embed = time.perf_counter() - t
    t = time.perf_counter(); index = container.bm25.ensure_built(container.chunks.fetch_all)
    warm_bm25 = time.perf_counter() - t
    logger.info("预热：嵌入模型 %.2f s，BM25 %.2f s（%d 块）", warm_embed, warm_bm25, index.size)

    rows, failures = [], 0
    for i, s in enumerate(samples, 1):
        sid, q = s["sample_id"], s["user_input"]
        rec: dict = {"sample_id": sid, "id": s.get("id"), "subset_label": s.get("subset_label"),
                     "user_input": q, "reference": s.get("reference"), "n_gold": s.get("n_gold")}

        t = time.perf_counter()
        chunks = retrieval.retrieve(container, q)
        t_ret = (time.perf_counter() - t) * 1000

        rec["retrieved_contexts"] = [c.get("content") or "" for c in chunks]
        rec["retrieved_context_ids"] = [c.get("id") for c in chunks]
        rec["retrieved_chunk_index"] = [c.get("chunk_index") for c in chunks]
        rec["retrieval_ms"] = round(t_ret, 1)

        prompt_chars = sum(len(m.get("content") or "") for m in llm.build_messages(q, chunks))
        t = time.perf_counter()
        try:
            # stream=False 时返回 str；签名的 union 只是给流式路径留的口，这里显式收窄
            answer = cast(str, await llm.answer(q, chunks, stream=False, timeout_total=settings.llm_timeout_total))
            if not isinstance(answer, str):
                raise TypeError("非流式调用返回了生成器")
            rec["error"] = None
        except Exception as exc:                       # 单题失败不打断整批，留给报告统计
            answer = ""
            rec["error"] = f"{type(exc).__name__}: {exc}"
            failures += 1
            logger.error("[%02d/%02d] %s 生成失败：%s", i, len(samples), sid, rec["error"])
        t_gen = (time.perf_counter() - t) * 1000

        rec["response"] = answer
        rec["generation_ms"] = round(t_gen, 1)
        # 两种"没答"要分开记（11 号文档 §8.6）：
        #   fallback_exact = 代码分支（检索为空 → 固定话术），当前语料下永远是 0
        #   refusal        = 模型自己决定不答（话术可能是固定话术 + 一段解释）
        rec["fallback_exact"] = (not chunks) or answer.strip() == FALLBACK_TEXT
        rec["refusal"] = FALLBACK_TEXT in answer[:40]
        rec["prompt_chars"] = prompt_chars
        rec["response_chars"] = len(answer)
        rec["est_tokens_in"] = common.est_tokens("x" * prompt_chars)      # 按字符数估算，口径见 common.TOKEN_PER_HANZI
        rec["est_tokens_out"] = common.est_tokens(answer)
        rows.append(rec)

        logger.info("[%02d/%02d] %s %s 检索 %.0f ms / 生成 %.0f ms / 答案 %d 字%s",
                    i, len(samples), sid, s.get("subset_label"), t_ret, t_gen, len(answer),
                    "（拒答）" if rec["refusal"] else "")
        print(f"  Q: {q[:60]}\n  A: {answer[:120]}\n")

    warmup = {"embedder_s": round(warm_embed, 2), "bm25_s": round(warm_bm25, 2), "bm25_chunks": index.size}
    return rows, {"warmup": warmup, "failures": failures}


def rebuild_report_only(run_dir: Path) -> int:
    """只重排 report.md（改文案/排版时用），不重跑检索与生成，数字一个不变。"""
    config_path, samples_path = run_dir / "config.json", run_dir / "samples.jsonl"
    if not (config_path.exists() and samples_path.exists()):
        print(f"缺少产物：{config_path} 或 {samples_path}", file=sys.stderr)
        return 2
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rows = common.load_samples(samples_path)
    report.write(run_dir / "report.md", report.build_collect({"config": config, "rows": rows}))
    print(f"已重排 {run_dir / 'report.md'}（{len(rows)} 题，未调用模型）")
    return 0


async def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--report-only":
        return rebuild_report_only(Path(argv[1]).resolve())

    dataset_path = common.DATASET_E1
    if "--dataset" in argv:
        dataset_path = common.resolve_dataset(argv[argv.index("--dataset") + 1])

    common.prepare_env()
    common.load_deepseek_key()

    run_id, out_dir = common.new_run_dir("e1")
    common.setup_logging(out_dir / "run.log")
    logger.info("run_id=%s out=%s", run_id, out_dir)

    from server.api.deps import Container
    from server.core.config import load_settings

    samples = common.ensure_sample_ids(common.load_samples(dataset_path))
    logger.info("数据集 %s，%d 题", dataset_path.name, len(samples))

    settings = load_settings()
    container = Container(settings)
    exit_code = 0
    try:
        before = common.db_counts(container)
        logger.info("库快照（跑前）：%s", before)

        rows, meta = await collect(container, samples)

        after = common.db_counts(container)
        logger.info("库快照（跑后）：%s", after)
        db_stable = before == after

        # 与最近一次 P1 交叉校验：同一问题应召回同一批块（检索是确定性的）
        p1 = latest_retrieval_run()
        cross = {"checked": False}
        if p1:
            mism = [r["sample_id"] for r in rows
                    if p1["by_sample"].get(r["sample_id"]) != r["retrieved_context_ids"]]
            cross = {"checked": True, "p1_run": p1["run_id"], "mismatch": mism,
                     "ok": not mism, "n": len(rows)}
            logger.info("与 %s 的检索结果比对：%d/%d 一致", p1["run_id"], len(rows) - len(mism), len(rows))

        config = {
            "run_id": run_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "kind": "generation-collect",
            "dataset": {"file": str(dataset_path.relative_to(common.ROOT)).replace("\\", "/"),
                        "sha256": common.sha256_file(dataset_path), "records": len(samples)},
            "params": {"top_k": settings.top_k, "recall_k": settings.recall_k, "rrf_k": settings.rrf_k,
                       "chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap,
                       "llm_model": settings.llm_model,
                       "llm_timeout_total": settings.llm_timeout_total,
                       "temperature": 0.3, "max_tokens": 1024,
                       "token_per_hanzi": common.TOKEN_PER_HANZI},
            "db": before,
            "warmup": meta["warmup"],
            "git": common.git_info(),
            "assertions": {"db_stable": db_stable, "db_after": after,
                           "failures": meta["failures"], "cross_check": cross},
        }
        ctx = {"config": config, "rows": rows}

        common.dump_json(out_dir / "config.json", config)
        common.dump_jsonl(out_dir / "samples.jsonl", rows)
        report.write(out_dir / "report.md", report.build_collect(ctx))

        if not db_stable or meta["failures"]:
            exit_code = 1
        logger.info("采集完成：成功 %d / 失败 %d，模型拒答 %d，产物 %s",
                    len(rows) - meta["failures"], meta["failures"],
                    sum(1 for r in rows if r["refusal"]), out_dir)
    finally:
        container.close()
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main(sys.argv[1:])))
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
