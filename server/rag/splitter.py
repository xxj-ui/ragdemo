"""第 2 步：切分

输入是 loaders.py 产出的单个文档单元 {"text", "source", "page"}。

策略：句子聚合
    1. 短文本（<= size）不切
    2. 按句子边界把文本拆开（。！？；换行 等）
    3. 贪心地把句子装进 size 大小的块里
    4. 相邻块之间保留 overlap 字的重叠
    5. 过短的块（< min_size）并入相邻块

只在单个文档单元内部切分，不跨页 / 跨行 / 跨文件。
"""

import re

# 句子结束符：中文标点 + 英文标点 + 换行；英文句号只在后面跟空白时才算
_SENTENCE_END = re.compile(
    r"[。！？；!?;…\n]+"                      # 中文/英文标点、省略号、换行
    r"|(?<=[a-zA-Z0-9\)])\.(?=\s|$)"          # 英文句号（避免切开 3.14、example.com）
)


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """把文本拆成句子，返回每句在原文本中的 (start, end) 位置。"""
    spans = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        spans.append((start, m.end()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))

    # 纯空白/纯换行的片段没有内容，丢掉
    return [(s, e) for s, e in spans if text[s:e].strip()]


def split_chunk(
    text: str,
    size: int = 500,
    overlap: int = 100,
    min_size: int = 80,
) -> list[dict]:
    """把一段文本切成若干块。

    参数:
        text:     一段完整文本（一个文档单元的 text）
        size:     每块最大长度（字符数，含重叠部分）
        overlap:  相邻块的重叠长度（字符数），每块实际新增 size - overlap 字
        min_size: 小于该长度的块并入相邻块（合并后可能略超 size）

    返回:
        [{"text": 块内容, "start": 起始位置, "end": 结束位置}, ...]
        start/end 是该块在原始 text 中的字符下标，方便追溯。
    """
    if not text or not text.strip():
        return []
    if size <= 0:
        raise ValueError("size 必须大于 0")

    text = text.strip()
    if len(text) <= size:
        return [{"text": text, "start": 0, "end": len(text)}]

    if not 0 <= overlap < size:
        raise ValueError("overlap 必须满足 0 <= overlap < size")

    chunks: list[dict] = []

    def emit(start: int, end: int) -> None:
        if start < end and text[start:end].strip():
            chunks.append({"text": text[start:end], "start": start, "end": end})

    buf_start = 0        # 当前缓冲区的起始位置
    buf_end = 0          # 当前缓冲区的结束位置（不包含）
    has_content = False  # 缓冲区里有没有句子

    for sent_start, sent_end in _sentence_spans(text):
        sent_len = sent_end - sent_start

        # 情况一：单句就超过 size，没有自然边界可用，只能硬切
        if sent_len > size:
            if has_content:
                emit(buf_start, buf_end)
                has_content = False
            pos = sent_start
            while sent_end - pos > size:
                emit(pos, pos + size)
                pos += size - overlap
            # 剩下的尾巴作为新缓冲区
            buf_start, buf_end, has_content = pos, sent_end, True
            continue

        # 情况二：缓冲区还是空的，直接放入这一句
        if not has_content:
            buf_start, buf_end, has_content = sent_start, sent_end, True
            continue

        # 情况三：这一句放不下 → 先收尾当前块，新块带上一块的尾部重叠
        if sent_end - buf_start > size:
            emit(buf_start, buf_end)
            # 新块起点 = 上一块结尾往前 overlap 字；同时保证不超过 size
            buf_start = max(buf_end - overlap, sent_end - size)
            buf_end = sent_end
        else:
            # 情况四：放得下，继续攒
            buf_end = sent_end

    if has_content:
        emit(buf_start, buf_end)

    # 合并过小的块：任何一块小于 min_size，都尽量并入相邻块
    # （合并后最多超出 size 约 min_size 字）
    merged: list[dict] = []
    for c in chunks:
        if merged:
            prev = merged[-1]
            length = c["end"] - c["start"]
            prev_len = prev["end"] - prev["start"]
            combined = c["end"] - prev["start"]
            if (length < min_size or prev_len < min_size) and combined <= size + min_size:
                merged[-1] = {
                    "text": text[prev["start"]:c["end"]],
                    "start": prev["start"],
                    "end": c["end"],
                }
                continue
        merged.append(c)

    return merged


def split_documents(
    docs: list[dict],
    size: int = 500,
    overlap: int = 100,
    min_size: int = 80,
) -> list[dict]:
    """对 loaders 的输出整体切分，并把 source / page 合并到每个 chunk 上。"""
    result = []
    for doc in docs:
        parts = split_chunk(
            doc.get("text", ""),
            size=size,
            overlap=overlap,
            min_size=min_size,
        )
        for index, part in enumerate(parts):
            result.append({
                "text": part["text"],
                "source": doc.get("source"),
                "page": doc.get("page"),
                "chunk_index": index,
                "start": part["start"],
                "end": part["end"],
            })
    return result
