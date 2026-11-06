"""检索层指标：全部基于「有序 chunk id 列表」与「正确块集合」，不调任何模型。

定义（与 11.RAG评测设计 §4.1 一致）：
    Recall@k   |top-k ∩ 正确块| / |正确块|，逐题计算后对题平均（正确块取并集）
    Hit@k      该题 top-k 里至少命中一块 → 1/0，对题平均
    AllHit@k   该题全部正确块都在 top-k → 1/0，对题平均
    MRR@k      第一个正确块的 1/名次（无命中记 0），对题平均
    nDCG@k     二值相关度（正确=1）的 DCG 与 IDCG 之比，k 处截断

约束：k 不能超过候选深度（本次候选深度 40 → k ≤ 40）。
"""
from __future__ import annotations

import math

KS = (1, 3, 5, 10, 20)
MAIN_K = 5          # 主指标阈值（同时决定 Hit/AllHit 的 k）
MRR_K = 10
NDCG_K = 10


def recall_at(ranked: list, correct: set, k: int) -> float:
    if not correct:
        return float("nan")
    return len(set(ranked[:k]) & correct) / len(correct)


def hit_at(ranked: list, correct: set, k: int) -> int:
    return 1 if set(ranked[:k]) & correct else 0


def all_hit_at(ranked: list, correct: set, k: int) -> int:
    return 1 if correct and correct <= set(ranked[:k]) else 0


def first_hit_rank(ranked: list, correct: set, k: int = 10) -> int | None:
    for i, cid in enumerate(ranked[:k], 1):
        if cid in correct:
            return i
    return None


def reciprocal_rank(ranked: list, correct: set, k: int = MRR_K) -> float:
    r = first_hit_rank(ranked, correct, k)
    return 1.0 / r if r else 0.0


def ndcg_at(ranked: list, correct: set, k: int = NDCG_K) -> float:
    """二值相关度的 nDCG。idcg = 前 min(|正确|, k) 个位置全中时的 DCG。"""
    if not correct:
        return float("nan")
    dcg = sum(1.0 / math.log2(i + 1) for i, cid in enumerate(ranked[:k], 1) if cid in correct)
    ideal_hits = min(len(correct), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def mean(values: list[float]) -> float:
    vals = [v for v in values if v == v]          # 去掉 NaN
    return sum(vals) / len(vals) if vals else float("nan")


def percentile(values: list[float], p: float) -> float:
    """线性插值分位数（p 取 0~100）。样本少的场合也能给出稳定值。"""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return float("nan")
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * p / 100.0
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def summarize(rows: list[dict], correct_key: str = "correct") -> dict:
    """rows: [{那题的 ranked 列表在 ranked_key 下, correct_key 下是 set}]。

    返回一个可直接打进报告的指标字典。
    """
    out: dict = {}
    for k in KS:
        out[f"recall@{k}"] = mean([recall_at(r["ranked"], r[correct_key], k) for r in rows])
    out[f"hit@{MAIN_K}"] = mean([hit_at(r["ranked"], r[correct_key], MAIN_K) for r in rows])
    out[f"allhit@{MAIN_K}"] = mean([all_hit_at(r["ranked"], r[correct_key], MAIN_K) for r in rows])
    out[f"mrr@{MRR_K}"] = mean([reciprocal_rank(r["ranked"], r[correct_key], MRR_K) for r in rows])
    out[f"ndcg@{NDCG_K}"] = mean([ndcg_at(r["ranked"], r[correct_key], NDCG_K) for r in rows])
    out["n"] = len(rows)
    return out
