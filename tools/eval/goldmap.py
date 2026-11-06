"""gold → 正确块映射（严格 gold 匹配口径）。

为什么要有这一步：
    gold 是整篇新闻（几百字），库里的单位是 500 字片段，两者不是包含关系，
    也没有 chunk 级 gold。要算 Recall@k 必须先离线回答「这道题该召回哪几块」。

口径（写进 report.md 方法节）：
    窗口   gold 归一化后取 30 字窗、步长 10
    覆盖   某片段内容里能找到的 gold 窗比例
    正确块 coverage ≥ HIT_COVERAGE(0.5) 的片段记入该 gold 的正确集合

    候选片段用 5 个探针（首/1/4/中/3/4/尾窗）粗筛：一个片段若覆盖 ≥50% 的连续
    gold，必然包含这些探针之一，所以不会漏掉 ≥0.5 的块（0.3 以下的块会漏，
    因此阈值敏感性只报 ≥0.5 的档位）。

用法：
    from tools.eval import goldmap
    gm = goldmap.build(chunks, samples)
"""
from __future__ import annotations

import re

WIN = 30
STRIDE = 10
HIT_COVERAGE = 0.5
PROBE_POINTS = (0.0, 0.25, 0.5, 0.75, 1.0)
SENSITIVITY = (0.5, 0.6, 0.7)      # 只报探针能保证覆盖到的档位


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def windows(text: str) -> list[str]:
    t = norm(text)
    return [t[i:i + WIN] for i in range(0, max(0, len(t) - WIN + 1), STRIDE)] or ([t] if t else [])


def _probes(wins: list[str]) -> list[str]:
    n = len(wins)
    return list({wins[min(n - 1, int(round((n - 1) * p)))] for p in PROBE_POINTS if n})


def coverage_by_chunk(gold: str, chunk_normed: list[tuple[int, str]]) -> dict[int, float]:
    """返回 {chunk_id: 覆盖率}，只含覆盖 >0 的片段。"""
    wins = windows(gold)
    if not wins:
        return {}
    probes = _probes(wins)
    candidates = [(cid, t) for cid, t in chunk_normed if any(p in t for p in probes)]
    out = {}
    for cid, t in candidates:
        cov = sum(1 for w in wins if w in t) / len(wins)
        if cov > 0:
            out[cid] = round(cov, 4)
    return out


def build(chunks: list[dict], samples: list[dict], hit_coverage: float = HIT_COVERAGE) -> dict:
    """为每个样本算出「每篇 gold 的正确块集合」。

    返回 {sample_id: {"golds": [{gold_index, chars, windows, coverage, correct_chunk_ids,
                                 best_coverage, hit_coverage_threshold}], "correct_union": [...]}}
    """
    chunk_normed = [(c["id"], norm(c["content"])) for c in chunks]
    result = {}
    for s in samples:
        golds = []
        union: set[int] = set()
        for gi, gold in enumerate(s.get("gold_news") or [], 1):
            cov = coverage_by_chunk(gold, chunk_normed)
            correct = sorted([cid for cid, c in cov.items() if c >= hit_coverage])
            union.update(correct)
            golds.append({
                "gold_index": gi,
                "chars": len(norm(gold)),
                "windows": len(windows(gold)),
                "coverage": cov,
                "correct_chunk_ids": correct,
                "best_coverage": max(cov.values()) if cov else 0.0,
                "hit_coverage_threshold": hit_coverage,
            })
        result[s["sample_id"]] = {"golds": golds, "correct_union": sorted(union)}
    return result


def correct_ids_at(gm_sample: dict, threshold: float) -> set[int]:
    """按另一个覆盖率阈值取正确块集合（敏感性分析用）。"""
    ids: set[int] = set()
    for g in gm_sample["golds"]:
        ids.update(cid for cid, cov in g["coverage"].items() if cov >= threshold)
    return ids
