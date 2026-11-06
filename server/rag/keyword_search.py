"""第 5 步：关键词检索（BM25）

只做一件事：问题 → jieba 分词 → BM25 打分 → top_k。
不涉及向量、RRF、rerank。

BM25 打分公式（k1=1.5, b=0.75）:

    score(D, Q) = Σ IDF(t) · (tf(t,D)·(k1+1)) / (tf(t,D) + k1·(1 - b + b·|D|/avgdl))
                  t∈Q

    IDF(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

    tf(t,D) 词 t 在文档 D 中出现的次数
    df(t)   包含词 t 的文档数
    |D|     文档 D 的长度（词数）
    avgdl   所有文档的平均长度
    N       文档总数

IDF 里那个 "+1" 让结果恒为正，省掉了经典公式在 df > N/2 时 IDF 变负的问题。
"""

import math
from collections import Counter

K1 = 1.5   # 词频饱和系数：越大，词频的影响越持久
B = 0.75   # 长度归一化系数：0 不归一化，1 完全归一化

_jieba = None


def _get_jieba():
    """延迟导入 jieba，并屏蔽它首次加载词典时的日志。"""
    global _jieba
    if _jieba is None:
        import logging
        import warnings

        # jieba 内部还在用 pkg_resources，新版 setuptools 会告警，和用法无关。
        # 必须在 import jieba 之前设置，否则告警已经打出来了。
        warnings.filterwarnings(
            "ignore", message="pkg_resources is deprecated", category=UserWarning
        )

        import jieba

        jieba.setLogLevel(logging.ERROR)
        _jieba = jieba
    return _jieba


def tokenize(text: str) -> list[str]:
    """把文本切成词（精确模式 lcut），英文统一转小写。

    这里刻意不用 lcut_for_search（搜索模式）。它会额外产出子词
    （"计算机网络" → 计算 / 算机 / 网络 / 计算机 / 计算机网络），实测这些
    子词会去匹配无关内容：查询"计算机网络"时，"计算机楼"里的"计算机"
    给无关块贡献了大量分数。

    代价是查"计算机"匹配不到"计算机网络"，但语义召回由稠密向量负责。
    """
    if not text or not text.strip():
        return []
    return [t for t in _get_jieba().lcut(text.lower()) if t.strip()]


class BM25KeywordSearch:
    """基于 BM25 的关键词索引（后端：bm25s 的稀疏矩阵实现）。

    打分公式与上一版完全一致（k1=1.5 / b=0.75 / Lucene IDF），变化只在实现：
    从「Python 里逐块遍历 Counter 求和」换成 numpy 稀疏矩阵打分，实测查询快约
    100 倍、索引内存降到 1/5~1/8。分词仍走本模块的 jieba —— bm25s 自带的
    切分是按英文空白/正则做的，直接喂中文会切坏。
    """

    def __init__(self, docs: list[dict]) -> None:
        import bm25s

        # docs 来自 PgChunkRepository.fetch_all()：
        # [{"id", "source", "page", "chunk_index", "content"}, ...]
        self._docs = docs
        self._n = len(docs)
        self._bm25 = bm25s.BM25(k1=K1, b=B, method="lucene")
        if docs:
            tokens = [tokenize(d.get("content", "")) for d in docs]
            self._bm25.index(tokens, show_progress=False)

    # ------------------------------------------------------------------
    # 打分
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """索引里的文档（片段）数。"""
        return self._n

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """返回相似度最高的 top_k 条，结构同 PgChunkRepository.search()。"""
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_tokens = tokenize(query)
        if not query_tokens or not self._docs:
            return []

        import numpy as np

        scores = self._bm25.get_scores(query_tokens)         # 全量打分在 numpy 层完成
        cand = np.nonzero(scores > 0)[0]                     # 与上一版一致：只回命中的块
        if cand.size == 0:
            return []
        # 主键是分数（降序），次键是块序 —— 同分时保持稳定顺序，和旧实现逐位一致
        order = np.lexsort((cand, -scores[cand]))
        picked = cand[order[:top_k]]
        return [
            {
                "id": self._docs[int(i)].get("id"),
                "source": self._docs[int(i)].get("source"),
                "filename": self._docs[int(i)].get("filename"),
                "page": self._docs[int(i)].get("page"),
                "chunk_index": self._docs[int(i)].get("chunk_index"),
                "content": self._docs[int(i)].get("content"),
                "score": float(scores[i]),
            }
            for i in picked
        ]
