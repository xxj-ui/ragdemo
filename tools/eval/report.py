"""把 probe 的结果拼成 report.md（唯一对外口径）。

报告结构固定：结论 → 主指标 → 分路对照 → 阈值敏感性 → 延迟 → 逐题附录 → 方法 → 失效条件。
所有数字必须能由 run 目录里的 config.json / samples.jsonl / gold-chunk-map.json 复算。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _ci_pp(n: int, p: float = 0.8) -> float:
    """Wilson 95% 半宽（百分点）。真值取 0.8 作为参照点。"""
    import math
    z = 1.96
    d = 1 + z * z / n
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return h * 100


def _pct(v: float) -> str:
    return "—" if v != v else f"{v:.1%}"


def _num(v: float, nd: int = 3) -> str:
    return "—" if v != v else f"{v:.{nd}f}"


def _table_metrics(main: dict, label: str) -> str:
    ks = (1, 3, 5, 10, 20)
    head = "| 策略 | " + " | ".join(f"Recall@{k}" for k in ks) + " | Hit@5 | AllHit@5 | MRR@10 | nDCG@10 |"
    sep = "|" + "---|" * (len(ks) + 5)
    cells = " | ".join(_pct(main[f"recall@{k}"]) for k in ks)
    return "\n".join([
        head, sep,
        f"| {label} | {cells} | {_pct(main['hit@5'])} | {_pct(main['allhit@5'])} | {_num(main['mrr@10'])} | {_num(main['ndcg@10'])} |",
    ])


def build(ctx: dict) -> str:
    """ctx 需要的键见 probe.py 末尾的组装；这里只负责排版。"""
    cfg = ctx["config"]
    gm = ctx["goldmap"]
    rows = ctx["rows"]
    agg = ctx["agg"]
    lat = ctx["latency"]
    asserts = ctx["assertions"]
    ds = cfg["dataset"]
    ds_path = Path(ds["file"])

    main = agg["hybrid_prod"]
    dense = agg["dense"]
    bm25 = agg["bm25"]
    hybrid40 = agg["hybrid_40"]

    # 一段自动结论：只陈述测得的东西，不下价值判断
    best_route = max((("混合(dense+BM25)", main), ("纯稠密", dense), ("纯BM25", bm25)),
                     key=lambda kv: kv[1]["recall@5"])
    zero_hit = [r["sample_id"] for r in rows if r["first_hit_rank"] is None]

    L: list[str] = []
    L.append(f"# 检索基线报告（{cfg['run_id']}）")
    L.append("")
    ds_name = ds_path.name
    L.append(f"> 题数 **{main['n']}**（`{ds_name}`）、检索库 **{cfg['db']['chunks']} 块 / {cfg['db']['docs']} 文档**、"
             f"生成时间 {datetime.now().astimezone().isoformat(timespec='seconds')}。")
    L.append("> 所有数字为**实测**；指标口径见 §6 方法。")
    L.append("")
    L.append("## 1. 结论")
    L.append("")
    L.append(f"- 生产链路（稠密 top20 + BM25 top20 → RRF k={cfg['params']['rrf_k']} → top{cfg['params']['top_k']}）："
             f"**Recall@5 = {_pct(main['recall@5'])}**、MRR@10 = {_num(main['mrr@10'])}、Hit@5 = {_pct(main['hit@5'])}。")
    L.append(f"- 三路里 Recall@5 最高的是 **{best_route[0]}**（{_pct(best_route[1]['recall@5'])}）。")
    if zero_hit:
        L.append(f"- **{len(zero_hit)}/{main['n']} 题在 top-10 内没有任何正确块**：{', '.join(zero_hit)}。")
    else:
        L.append("- 全部题目在 top-10 内至少命中一个正确块。")
    L.append(f"- 生产检索延迟 P50 = {lat['p50_ms']:.0f} ms / P95 = {lat['p95_ms']:.0f} ms（含查询嵌入）。")
    L.append(f"- 等价性断言：旁路自融的 top-5 与生产 `retrieve()` **{'完全一致' if asserts['equiv_ok'] else '存在不一致'}**"
             f"（{asserts['equiv_ok_n']}/{asserts['n']} 题一致）。")
    L.append("")

    L.append("## 2. 主指标（生产口径：recall_k=20 / rrf_k=60）")
    L.append("")
    L.append(_table_metrics(main, "混合（生产）"))
    L.append("")

    L.append("## 3. 分路对照（同一批题、同一正确块集合）")
    L.append("")
    L.append("| 策略 | Recall@5 | Recall@10 | Recall@20 | MRR@10 | nDCG@10 |")
    L.append("|---|---|---|---|---|---|")
    for label, m in (("纯稠密（top40 余弦）", dense), ("纯 BM25（top40）", bm25),
                     ("混合 recall_k=20（生产）", main), ("混合 recall_k=40（更宽召回）", hybrid40)):
        L.append(f"| {label} | {_pct(m['recall@5'])} | {_pct(m['recall@10'])} | {_pct(m['recall@20'])} | "
                 f"{_num(m['mrr@10'])} | {_num(m['ndcg@10'])} |")
    L.append("")
    L.append(f"> 纯路线的候选深度同为 40，与混合路线的比较是公平的；"
             f"本批 n={main['n']}，差异 < {max(3.0, _ci_pp(main['n']) / 3):.0f} pp 的不要当结论。")
    L.append("")

    L.append("## 4. 口径敏感性（正确块的覆盖率阈值）")
    L.append("")
    L.append("| 阈值 | 正确块数（合计） | Recall@5 | Recall@10 | MRR@10 |")
    L.append("|---|---|---|---|---|")
    for th, m in agg["sensitivity"].items():
        L.append(f"| cov ≥ {th} | {m['n_correct']} | {_pct(m['recall@5'])} | {_pct(m['recall@10'])} | {_num(m['mrr@10'])} |")
    L.append("")
    L.append("> 阈值越高，正确块集合越小、指标越高。**主指标固定取 0.5**；本表只用来判断结论是否被阈值左右。")
    L.append("")

    L.append("## 5. 延迟（生产检索一次，含查询嵌入）")
    L.append("")
    L.append("> 分位数按线性插值（pandas 同款口径），n=%d。" % main["n"])
    L.append("")
    L.append("| 指标 | 值 |")
    L.append("|---|---|")
    L.append(f"| P50 | {lat['p50_ms']:.0f} ms |")
    L.append(f"| P95 | {lat['p95_ms']:.0f} ms |")
    L.append(f"| min / max | {lat['min_ms']:.0f} / {lat['max_ms']:.0f} ms |")
    L.append(f"| 预热（模型加载 + BM25 构建） | {cfg['warmup']['embedder_s']:.2f} s + {cfg['warmup']['bm25_s']:.2f} s |")
    L.append("")

    L.append("## 6. 方法（复算所需）")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| 数据集 | `{ds['file']}`，sha256 `{ds['sha256'][:16]}…`，{main['n']} 题 |")
    L.append(f"| 库快照 | chunks **{cfg['db']['chunks']}**、documents **{cfg['db']['docs']}**（跑前跑后断言一致） |")
    L.append(f"| 参数 | top_k={cfg['params']['top_k']}、recall_k={cfg['params']['recall_k']}、rrf_k={cfg['params']['rrf_k']}、"
             f"chunk_size={cfg['params']['chunk_size']}、embedding={cfg['params']['embedding']} |")
    L.append(f"| 代码版本 | HEAD `{cfg['git']['head'][:8]}`，工作区{'有改动' if cfg['git']['dirty'] else '干净'} |")
    L.append(f"| gold 匹配 | 30 字窗 / 步长 10；片段覆盖 ≥ **{cfg['params']['hit_coverage']}** 记为该 gold 的正确块；正确块取并集 |")
    L.append(f"| 指标 | Recall@k = \\|top-k ∩ 正确块\\| / \\|正确块\\|；Hit/AllHit@5；MRR@10；nDCG@10（二值相关度） |")
    L.append(f"| 候选深度 | 两路各 40，融合上限 40 → k ≤ 40 |")
    L.append("")
    L.append("**已知噪声（写进结论前必须看）**")
    L.append("")
    L.append("- **严格 gold 口径**：同事件的另一篇报道不算命中，所以 Recall 会低于人眼直觉；只用于纵向对比，不对外宣称绝对值。")
    L.append("- **语料形态**：CRUD-RAG 的 txt 是 1,930 条新闻首尾相接、被当作一个文档单元切分，实测 **7.8%（697/8,935）** 的块跨两条新闻，"
             "指代可能被污染（详见 11.RAG评测设计 §8 风险 8.5b）。")
    ci = _ci_pp(main["n"])
    L.append(f"- **样本量**：{main['n']} 题在真值 0.8 时 95% 置信半宽约 **±{ci:.1f} pp**；"
             f"只报 ≥{max(5.0, round(ci / 9) * 10):.0f} pp 的差异。")
    L.append("")

    L.append("## 7. 逐题明细（附录）")
    L.append("")
    L.append("| # | sample | 子集 | 正确块 | Recall@5 | 首个命中名次 | 延迟 ms |")
    L.append("|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(f"| {r['idx']} | {r['sample_id']} | {r['subset_label']} | {r['n_correct']} | "
                 f"{_pct(r['recall@5'])} | {r['first_hit_rank'] or '未命中'} | {r['latency_ms']:.0f} |")
    L.append("")
    L.append("## 8. 失效条件")
    L.append("")
    L.append("- 换语料 / 重新导入 → 块 id 全变，正确块映射作废，必须重跑本 run。")
    L.append("- 改 `chunk_size` / `overlap` / embedding 模型 → 与旧 run 不可比。")
    L.append("- 库在跑测期间被写入（断言会失败）→ 本次结果作废。")
    L.append("- RAGAS 生成层指标不在本报告范围（需要 P2 采集 + P3 打分）。")
    L.append("")
    return "\n".join(L)


FB_TEXT = "根据已有资料无法回答"


def build_collect(ctx: dict) -> str:
    """P2 采集摘要（不是质量结论——质量要等 P3 打分）。"""
    from tools.eval import metrics

    cfg, rows = ctx["config"], ctx["rows"]
    n = len(rows)
    failures = cfg["assertions"]["failures"]
    fallback_exact = sum(1 for r in rows if r["fallback_exact"])
    refusal = sum(1 for r in rows if r["refusal"])
    cross = cfg["assertions"]["cross_check"]
    ret = [r["retrieval_ms"] for r in rows if r.get("retrieval_ms") is not None]
    gen = [r["generation_ms"] for r in rows if r.get("generation_ms") is not None and not r.get("error")]
    ans_len = [r["response_chars"] for r in rows]
    tok_in = sum(r["est_tokens_in"] for r in rows)
    tok_out = sum(r["est_tokens_out"] for r in rows)
    ctx_n = [len(r["retrieved_contexts"]) for r in rows]

    L = []
    L.append(f"# 采集报告（{cfg['run_id']}）")
    L.append("")
    L.append(f"> {n} 题真实链路采集，模型 `{cfg['params']['llm_model']}`，库 {cfg['db']['chunks']} 块 / {cfg['db']['docs']} 文档，"
             f"生成时间 {cfg['created_at']}。")
    L.append("> 本报告只说明「采到了什么」，**不含质量结论**——质量要等 P3（RAGAS 打分）。")
    L.append("")
    L.append("## 1. 结论")
    L.append("")
    L.append(f"- 成功 **{n - failures}** / 失败 **{failures}**。")
    hedged = [r["sample_id"] for r in rows if FB_TEXT in r["response"] and not r["refusal"]]
    L.append(f"- **代码兜底 {fallback_exact} 题**（检索为空才触发，当前语料下应为 0）；"
             f"**模型自述拒答 {refusal} 题**（回答开头就是固定话术）。")
    L.append("")
    L.append("> 两者的区别是 11 号文档 §8.6 的要点：没有相似度阈值时，代码兜底走不到，只能靠模型自觉。")
    if hedged:
        L.append(f"> 另有 **{len(hedged)} 题**（{', '.join(hedged)}）正文答完后附了\"根据已有资料无法回答……\"的补充声明，"
                 f"不计入拒答（它们给了答案），P3 打分时需要单独看。")
    L.append(f"- 每题平均带 **{sum(ans_len) / n:.0f} 字**答案、**{sum(ctx_n) / n:.1f} 条**检索原文。")
    L.append(f"- 检索 P50 {metrics.percentile(ret, 50):.0f} ms / 生成 P50 {metrics.percentile(gen, 50):.0f} ms；"
             f"整轮墙钟约 {sum(ret + gen) / 1000 / 60:.1f} min。")
    L.append(f"- token 账（**推算**，{cfg['params']['token_per_hanzi']} token/汉字）：输入 ≈ **{tok_in / 1000:.0f}k**、输出 ≈ **{tok_out / 1000:.1f}k**。")
    if cross.get("checked"):
        L.append(f"- 与 `{cross['p1_run']}` 的检索结果交叉校验：**{cross['n'] - len(cross['mismatch'])}/{cross['n']} 一致**"
                 f"{'（' + ', '.join(cross['mismatch']) + ' 不一致）' if cross['mismatch'] else ''}——检索是确定性的。")
    L.append("")
    L.append("## 2. 延迟")
    L.append("")
    L.append("> 分位数按线性插值（pandas 同款口径），n=%d。预热 %.2f s（模型）+ %.2f s（BM25）已排除。" % (
        n, cfg["warmup"]["embedder_s"], cfg["warmup"]["bm25_s"]))
    L.append("")
    L.append("| 指标 | 检索 (ms) | 生成 (ms) |")
    L.append("|---|---|---|")
    L.append(f"| P50 | {metrics.percentile(ret, 50):.0f} | {metrics.percentile(gen, 50):.0f} |")
    L.append(f"| P95 | {metrics.percentile(ret, 95):.0f} | {metrics.percentile(gen, 95):.0f} |")
    L.append(f"| min / max | {min(ret):.0f} / {max(ret):.0f} | {min(gen):.0f} / {max(gen):.0f} |")
    L.append("")
    L.append("## 3. 逐题附录")
    L.append("")
    L.append("| # | sample | 子集 | 上下文条数 | 答案字数 | 检索 ms | 生成 ms | 备注 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        L.append(f"| {i} | {r['sample_id']} | {r['subset_label']} | {len(r['retrieved_contexts'])} | "
                 f"{r['response_chars']} | {r['retrieval_ms']:.0f} | {r['generation_ms']:.0f} | "
                 f"{'拒答' if r['refusal'] else ''} |")
    L.append("")
    L.append("## 4. 方法")
    L.append("")
    L.append(f"| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| 数据集 | `{cfg['dataset']['file']}`，sha256 `{cfg['dataset']['sha256'][:16]}…`，{cfg['dataset']['records']} 题 |")
    L.append(f"| 库快照 | chunks **{cfg['db']['chunks']}**、documents **{cfg['db']['docs']}**（跑前跑后断言一致：{cfg['assertions']['db_stable']}） |")
    L.append(f"| 检索参数 | top_k={cfg['params']['top_k']}、recall_k={cfg['params']['recall_k']}、rrf_k={cfg['params']['rrf_k']}、chunk_size={cfg['params']['chunk_size']} |")
    L.append(f"| 生成参数 | model={cfg['params']['llm_model']}、temperature={cfg['params']['temperature']}、max_tokens={cfg['params']['max_tokens']}、总超时 {cfg['params']['llm_timeout_total']:.0f} s |")
    L.append(f"| 代码版本 | HEAD `{cfg['git']['head'][:8]}`，工作区{'有改动' if cfg['git']['dirty'] else '干净'} |")
    L.append("| 落盘字段 | `user_input` / `retrieved_contexts`（原文，非 snippet）/ `response` / `reference` + `retrieved_context_ids` + 耗时 |")
    L.append("")
    L.append("**本批数据的用法**")
    L.append("")
    L.append("- `retrieved_contexts` 是**送进模型的原片段**，不是引用卡片的 100 字摘要（用摘要算 Faithfulness 会系统性偏低）。")
    L.append("- `reference` 只在打分时打开；`response` 必须来自本 run，换参数要重新采集。")
    L.append("- token 数是**按 0.614 token/汉字推算**的，不是 API 返回的 usage；真实用量以 DeepSeek 后台为准。")
    L.append("- 本 run 不评价好坏：Faithfulness / ContextRecall / AnswerRelevancy 属 P3。")
    L.append("")
    return "\n".join(L)


def write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def dump_json(path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
