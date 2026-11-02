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
    """基于 BM25 的关键词索引。构造时一次性算好语料统计。"""

    def __init__(self, docs: list[dict]) -> None:
        # docs 来自 PgChunkRepository.fetch_all()：
        # [{"id", "source", "page", "chunk_index", "content"}, ...]
        self._docs = docs
        self._tokenized = [tokenize(d.get("content", "")) for d in docs]
        self._tf = [Counter(tokens) for tokens in self._tokenized]
        self._doc_len = [len(tokens) for tokens in self._tokenized]
        self._n = len(docs)
        self._avgdl = sum(self._doc_len) / self._n if self._n else 0.0

        # df(t)：有多少条文档包含词 t（同一文档里出现多次只算一次）
        self._df: Counter = Counter()
        for tokens in self._tokenized:
            self._df.update(set(tokens))

    # ------------------------------------------------------------------
    # 打分
    # ------------------------------------------------------------------

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def _score(self, tf: Counter, doc_len: int, query_tf: Counter) -> float:
        if self._avgdl <= 0:
            return 0.0

        score = 0.0
        for term, q_count in query_tf.items():
            freq = tf.get(term, 0)
            if freq == 0:
                continue                      # 文档里没这个词，跳过
            idf = self._idf(term)
            if idf <= 0:
                continue
            denom = freq + K1 * (1 - B + B * doc_len / self._avgdl)
            # q_count：查询里重复出现的词加权，避免重复提问被淡化
            score += q_count * idf * freq * (K1 + 1) / denom
        return score

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """返回相似度最高的 top_k 条，结构同 PgChunkRepository.search()。"""
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_tokens = tokenize(query)
        if not query_tokens or not self._docs:
            return []

        query_tf = Counter(query_tokens)
        scored = []
        for i, (tf, doc_len) in enumerate(zip(self._tf, self._doc_len)):
            score = self._score(tf, doc_len, query_tf)
            if score > 0:                     # 一个查询词都没命中的文档直接丢掉
                scored.append((score, i))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [
            {
                "id": self._docs[i].get("id"),
                "source": self._docs[i].get("source"),
                "filename": self._docs[i].get("filename"),
                "page": self._docs[i].get("page"),
                "chunk_index": self._docs[i].get("chunk_index"),
                "content": self._docs[i].get("content"),
                "score": score,
            }
            for score, i in scored[:top_k]
        ]
