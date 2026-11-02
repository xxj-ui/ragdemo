"""第 3 步：向量化（只负责 文字 → 向量）

使用本地缓存的 BAAI/bge-small-zh-v1.5（512 维），不联网。
模型懒加载：第一次调用时才加载，之后复用同一个实例。
"""

import os

# 模型缓存放在 D 盘，避免占用系统盘。
# setdefault：如果系统里已经设了 HF_HOME，以系统值为准。
os.environ.setdefault("HF_HOME", r"D:\models\huggingface")

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EMBED_DIM = 512

# BGE 官方建议：检索时给 query 加指令前缀，文档侧不加
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

_model = None


def _get_model():
    """延迟加载模型。import 也放在函数里，避免没用到时拖慢导入。"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME, local_files_only=True)
        # 模型最大输入 512 token，超出的部分会被截断（不会报错）
        _model.max_seq_length = 512
    return _model


def embed_documents(
    texts: list[str],
    batch_size: int = 32,
    show_progress: bool = False,
) -> list[list[float]]:
    """把一批文档块编码成向量。

    参数:
        texts:         文档块文本列表
        batch_size:    每批编码多少条（CPU 上 32 左右比较稳）
        show_progress: 是否显示进度条（文档多时建议开）

    返回:
        list[list[float]]，每条 512 维，已归一化（点积 = 余弦相似度）
    """
    if not texts:
        return []

    vectors = _get_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,   # 归一化：后续点积直接等于余弦相似度
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """把用户问题编码成查询向量。

    和 embed_documents 的区别：问题前面会加 BGE 的检索指令，
    这样它和库里文档向量的匹配才能达到模型训练时的效果。
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("查询内容不能为空")

    vector = _get_model().encode(
        QUERY_INSTRUCTION + text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vector.tolist()
