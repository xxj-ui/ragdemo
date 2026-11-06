"""P3：用 RAGAS 给 P2 采集的样本打分（只读冻结样本，不重新生成）。

跑法（**必须用隔离环境**，见 11 号文档 §7.1）：
    tools/eval/.venv/Scripts/python.exe -m tools.eval.ragas_runner --smoke            # 1 题验通 + 试判
    tools/eval/.venv/Scripts/python.exe -m tools.eval.ragas_runner --limit 1          # 1 题正式记录
    tools/eval/.venv/Scripts/python.exe -m tools.eval.ragas_runner                    # 全量 30 题

输入：evals/runs/<collect_run>/samples.jsonl（user_input / retrieved_contexts / response / reference）
输出：同一 run 目录下 ragas.jsonl / ragas-report.md / ragas-config.json

设计要点：
  * 裁判 = DeepSeek（`llm_factory` + OpenAI 兼容端点 + instructor `Mode.JSON`）；
  * 只跑不依赖 embedding 的两个指标：Faithfulness（2 次调用）、ContextRecall（1 次调用）；
  * 逐题独立打分（不用 `evaluate()` 批量），失败单题可重试、可记录，不拖垮整批；
  * 结果带 reason 落盘，便于人工抽检。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.eval import common  # noqa: E402  （只用它的落盘/估算工具，无 server 依赖）

DEFAULT_RUN = "e1-20261105-160518"
# 负向对照：故意编造与检索原文冲突的内容，用来看裁判是否真的会扣分
CONTROL_TEXT = ("根据资料，2023年8月16日湖北省市场监管局批准发布的地方标准全部属于医疗器械领域，"
                "其中《市场监管协同执法办案系统数据规范》已于当日废止，并由国家卫健委接管。")
JUDGE_MODEL = os.getenv("RAGAS_JUDGE_MODEL", "deepseek-chat")
JUDGE_BASE_URL = os.getenv("RAGAS_JUDGE_BASE_URL", "https://api.deepseek.com")
CONCURRENCY = int(os.getenv("RAGAS_CONCURRENCY", "4"))
RETRIES = 2
JUDGE_MAX_TOKENS = int(os.getenv("RAGAS_JUDGE_MAX_TOKENS", "4096"))


def build_judge():
    """DeepSeek 走 OpenAI 兼容端点。

    注意：ragas 0.4.3 内部已经固定 `instructor.from_openai(client, mode=Mode.JSON)`
    （site-packages/ragas/llms/base.py:556），**不能**再给 llm_factory 传 `mode=`，
    否则它会顺着 **kwargs 一路进到 `chat.completions.create(mode=...)` 并报 TypeError。
    """
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory

    common.load_deepseek_key()
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("缺少 DEEPSEEK_API_KEY（tools/eval/common.load_deepseek_key 也找不到）")
    client = AsyncOpenAI(base_url=JUDGE_BASE_URL, api_key=key)
    # max_tokens 必须给足：Faithfulness 第一步要把答案拆成断言列表，长答案（>400 字）
    # 在默认 1024 下会抛 IncompleteOutputException（2026-11-05 实测 15/30 题因此失败）。
    return llm_factory(JUDGE_MODEL, client=client, temperature=0, max_tokens=JUDGE_MAX_TOKENS)


def build_metrics(llm) -> dict:
    from ragas.metrics.collections import ContextRecall, Faithfulness

    return {
        "faithfulness": Faithfulness(llm=llm),          # 2 次调用，不需要 reference
        "context_recall": ContextRecall(llm=llm),        # 1 次调用，需要 reference
    }


async def score_one(metrics: dict, sample: dict, sem: asyncio.Semaphore) -> dict:
    """返回 {metric: {value, reason}} + error；单题失败只记录不抛。"""
    out = {"sample_id": sample["sample_id"], "subset_label": sample.get("subset_label"),
           "refusal": sample.get("refusal", False), "metrics": {}, "error": None}
    async with sem:
        for name, metric in metrics.items():
            for attempt in range(1, RETRIES + 2):
                t = time.perf_counter()
                try:
                    if name == "faithfulness":
                        r = await metric.ascore(user_input=sample["user_input"],
                                                response=sample["response"],
                                                retrieved_contexts=sample["retrieved_contexts"])
                    elif name == "context_recall":
                        r = await metric.ascore(user_input=sample["user_input"],
                                                retrieved_contexts=sample["retrieved_contexts"],
                                                reference=sample["reference"])
                    else:
                        raise ValueError(f"未知指标 {name}")
                    out["metrics"][name] = {
                        "value": None if r.value != r.value else round(float(r.value), 4),   # NaN → None
                        "reason": (r.reason or "")[:800] if getattr(r, "reason", None) else "",
                        "ms": round((time.perf_counter() - t) * 1000, 1),
                    }
                    break
                except Exception as exc:
                    if attempt > RETRIES:
                        out["metrics"][name] = {"value": None, "reason": "", "error": f"{type(exc).__name__}: {exc}"}
                        out["error"] = out["error"] or f"{name}: {type(exc).__name__}: {exc}"
                    else:
                        await asyncio.sleep(1.5 * attempt)
    return out


async def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="RAGAS 打分（P3）")
    ap.add_argument("--run", default=DEFAULT_RUN, help="evals/runs 下的采集 run 目录名")
    ap.add_argument("--smoke", action="store_true", help="只跑第 1 题，验通结构化输出并打印明细")
    ap.add_argument("--control", action="store_true",
                    help="负向对照：把第 1 题的回答换成编造内容，验裁判会不会扣分（应显著低于 smoke）")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（0 = 全部）")
    ap.add_argument("--sample", default="", help="只跑指定 sample_id")
    ap.add_argument("--metrics", default="faithfulness,context_recall")
    args = ap.parse_args(argv)

    run_dir = ROOT / "evals" / "runs" / args.run
    if not (run_dir / "samples.jsonl").exists():
        print(f"找不到 {run_dir / 'samples.jsonl'}", file=sys.stderr)
        return 2

    samples = common.load_samples(run_dir / "samples.jsonl")
    if args.control:
        samples = [dict(samples[0], response=CONTROL_TEXT, sample_id=samples[0]["sample_id"] + "/control")]
        args.metrics = "faithfulness"
    if args.sample:
        samples = [s for s in samples if s["sample_id"] == args.sample]
    if args.smoke:
        samples = samples[:1]
    elif args.limit:
        samples = samples[: args.limit]
    if not samples:
        print("没有匹配的样本", file=sys.stderr)
        return 2

    judge = build_judge()
    metrics = build_metrics(judge)
    wanted = [m.strip() for m in args.metrics.split(",") if m.strip()]
    metrics = {k: v for k, v in metrics.items() if k in wanted}
    print(f"裁判 {JUDGE_MODEL} @ {JUDGE_BASE_URL}｜temp=0 max_tokens={JUDGE_MAX_TOKENS}"
          f"｜指标 {list(metrics)}｜题数 {len(samples)}｜并发 {CONCURRENCY}")

    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.perf_counter()
    results = await asyncio.gather(*(score_one(metrics, s, sem) for s in samples))
    elapsed = time.perf_counter() - t0

    if args.smoke or args.control or args.limit == 1:
        print(json.dumps(results[0], ensure_ascii=False, indent=2))

    # 汇总
    def vals(name: str) -> list[float]:
        return [r["metrics"].get(name, {}).get("value") for r in results
                if r["metrics"].get(name, {}).get("value") is not None]

    summary = {}
    for name in metrics:
        v = vals(name)
        summary[name] = {
            "n": len(v),
            "nan_or_failed": len(results) - len(v),
            "mean": round(sum(v) / len(v), 4) if v else None,
            "min": round(min(v), 4) if v else None,
            "max": round(max(v), 4) if v else None,
        }

    config = {
        "run_id": f"ragas-{datetime.now():%Y%m%d-%H%M%S}",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "kind": "ragas-score",
        "input_run": args.run,
        "dataset_sha256": common.sha256_file(common.DATASET_E1),
        "judge": {"model": JUDGE_MODEL, "base_url": JUDGE_BASE_URL,
                  "mode": "instructor.Mode.JSON（ragas 内部强制，调用方不可覆盖）",
                  "temperature": 0, "max_tokens": JUDGE_MAX_TOKENS,
                  "same_family_as_sut": True,
                  "note": "裁判与被测同为 deepseek-chat：绝对值偏乐观，只作趋势与纵向对比"},
        "metrics": list(metrics),
        "n": len(samples),
        "elapsed_s": round(elapsed, 1),
        "summary": summary,
        "ragas_version": _version("ragas"),
    }

    # smoke / control 用小后缀单独落盘，免得被全量结果覆盖（它们是"裁判可用"的证据）
    suffix = "-smoke" if args.smoke else ("-control" if args.control else "")
    common.dump_json(run_dir / f"ragas-config{suffix}.json", config)
    common.dump_jsonl(run_dir / f"ragas{suffix}.jsonl", results)
    (run_dir / f"ragas-report{suffix}.md").write_text(build_report(config, results), encoding="utf-8")

    print("\n=== 汇总 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"用时 {elapsed:.1f} s，产物已写入 {run_dir}")
    return 0 if all(s["n"] > 0 for s in summary.values()) else 1


def _version(pkg: str) -> str:
    try:
        from importlib.metadata import version
        return version(pkg)
    except Exception:
        return "unknown"


def build_report(cfg: dict, results: list[dict]) -> str:
    s = cfg["summary"]
    L = [f"# RAGAS 打分报告（{cfg['input_run']}）", ""]
    L.append(f"> 裁判 `{cfg['judge']['model']}`（`{cfg['judge']['mode']}`）、ragas {cfg['ragas_version']}、"
             f"{cfg['n']} 题、用时 {cfg['elapsed_s']} s。")
    L.append("> 样本来自 P2 采集结果（冻结），本步骤不重新生成答案。")
    L.append("")
    L.append("## 1. 结论")
    L.append("")
    for name, d in s.items():
        if d["mean"] is None:
            L.append(f"- `{name}`：**全部失败**（{d['nan_or_failed']} 题无有效分）")
        else:
            L.append(f"- `{name}`：**{d['mean']:.3f}**（有效 {d['n']} 题，无有效分 {d['nan_or_failed']} 题，区间 {d['min']:.2f}~{d['max']:.2f}）")
    L.append("")
    L.append("**必须连读的三条限制**")
    L.append("")
    L.append("1. **同源偏差**：裁判与被测都是 `deepseek-chat`，绝对值偏乐观；只用于与自己比（改前/改后）。")
    L.append("2. **严格 gold 口径**：同事件的另一篇报道不算命中，`context_recall` 天生偏低。")
    L.append(f"3. **样本量**：{cfg['n']} 题在真值 0.8 时 95% 置信半宽约 ±{_ci(cfg['n']):.0f} pp，只报大差异。")
    L.append("")
    L.append("## 2. 逐题")
    L.append("")
    cols = list(s.keys())
    L.append("| # | sample | 子集 | " + " | ".join(cols) + " | 备注 |")
    L.append("|---|---|---|" + "---|" * len(cols) + "---|")
    for i, r in enumerate(results, 1):
        cells = []
        for c in cols:
            m = r["metrics"].get(c, {})
            cells.append("—" if m.get("value") is None else f"{m['value']:.3f}")
        note = []
        if r.get("refusal"):
            note.append("拒答")
        if r.get("error"):
            note.append("失败:" + r["error"][:40])
        L.append(f"| {i} | {r['sample_id']} | {r.get('subset_label') or ''} | " + " | ".join(cells) + f" | {'; '.join(note)} |")
    L.append("")
    L.append("## 3. 方法")
    L.append("")
    L.append(f"| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| 输入 run | `evals/runs/{cfg['input_run']}/samples.jsonl` |")
    L.append(f"| 数据集 sha256 | `{cfg['dataset_sha256'][:16]}…` |")
    L.append(f"| 指标 | {', '.join(cfg['metrics'])}（RAGAS collections API，逐题 `ascore`） |")
    L.append(f"| 裁判 | {cfg['judge']['model']} @ {cfg['judge']['base_url']}，{cfg['judge']['mode']} |")
    L.append(f"| 调用次数 | Faithfulness 2 次/题、ContextRecall 1 次/题（源码实测） |")
    L.append("| 无 reason 的原因 | RAGAS collections API 的 `MetricResult` 不回传判定理由，只有分数；"
             "人工校验靠负向对照（`--control`）与逐题分数分布 |")
    L.append("")
    L.append("## 4. 失效条件")
    L.append("")
    L.append("- 换采集 run（重新生成答案）→ 与本次分数不可比。")
    L.append("- 换裁判模型 / 换 `Mode` → 分数口径变了，不能混着比。")
    L.append("- 样本里 `retrieved_contexts` 若混入 100 字摘要（应为原文），faithfulness 会被系统性压低。")
    L.append("")
    return "\n".join(L)


def _ci(n: int) -> float:
    import math
    p = 0.8
    z = 1.96
    d = 1 + z * z / n
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return h * 100


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main(sys.argv[1:])))
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
