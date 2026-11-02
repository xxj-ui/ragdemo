"""命令行入口

用法（在项目根目录 ragdemo/ 下）:
    python -m server.main <文件或目录>            # 预览：加载 + 切分
    python -m server.main --build <文件或目录>    # 建库：加载 + 切分 + 向量化 + 入库
    python -m server.main --ask "问题"            # 问答：检索 + 大模型回答

预览模式只依赖标准库；建库和问答需要 sentence-transformers、psycopg、openai。
"""

import sys
import time

from .loaders import load_all
from .splitter import split_documents


# ------------------------------------------------------------------
# 预览：加载 + 切分，打印出来检查效果
# ------------------------------------------------------------------


def inspect(path: str) -> None:
    documents = load_all(path)
    print(f"\n共加载 {len(documents)} 个文档单元")
    for d in documents[:3]:
        print("-" * 60)
        print(f"来源: {d['source']}   位置: {d['page']}   长度: {len(d['text'])}")
        print(d["text"][:200])

    chunks = split_documents(documents)
    if not chunks:
        return

    lengths = [len(c["text"]) for c in chunks]
    print("-" * 60)
    print(f"共切出 {len(chunks)} 个 chunk")
    print(f"长度: 最小 {min(lengths)} / 平均 {sum(lengths) // len(lengths)} / 最大 {max(lengths)}")

    for i, c in enumerate(chunks[:3]):
        print("-" * 60)
        print(f"[块{i}] 来源: {c['source']}  位置: {c['page']}  区间: {c['start']}~{c['end']}")
        print(c["text"][:200])

    # 检查相邻块的重叠：下一块的起点应该落在上一块结尾之前
    for a, b in zip(chunks, chunks[1:]):
        if a["source"] == b["source"] and a["page"] == b["page"]:
            print(f"重叠检查: 块 {a['chunk_index']} 结尾 {a['end']} → 块 {b['chunk_index']} 起点 {b['start']}"
                  f"（重叠 {a['end'] - b['start']} 字）")
            break


# ------------------------------------------------------------------
# 建库：加载 + 切分 + 向量化 + 入库
# ------------------------------------------------------------------


def build_index(
    path: str,
    size: int = 500,
    overlap: int = 100,
    batch_size: int = 32,
) -> int:
    # 延迟导入：预览模式下不需要模型库和数据库驱动
    from .chunk_repository import PgChunkRepository
    from .embedder import embed_documents

    t0 = time.perf_counter()

    documents = load_all(path)
    chunks = split_documents(documents, size=size, overlap=overlap)
    print(f"加载 {len(documents)} 个文档单元，切出 {len(chunks)} 个 chunk")

    if not chunks:
        print("没有可入库的内容")
        return 0

    t1 = time.perf_counter()
    vectors = embed_documents(
        [c["text"] for c in chunks],
        batch_size=batch_size,
        show_progress=True,
    )
    t2 = time.perf_counter()
    print(f"向量化完成：{len(vectors)} 条，维度 {len(vectors[0])}，耗时 {t2 - t1:.1f}s")

    repo = PgChunkRepository()
    repo.init_table(dim=len(vectors[0]))

    # 同一份文件重复入库时，先删旧数据，保证幂等
    for source in sorted({c["source"] for c in chunks}):
        deleted = repo.delete_by_source(source)
        if deleted:
            print(f"清除 {source} 的旧数据 {deleted} 条")

    inserted = repo.insert_chunks(chunks, vectors)
    t3 = time.perf_counter()
    print(f"入库完成：{inserted} 条，耗时 {t3 - t2:.1f}s")
    print(f"表 {repo.count()} 条记录，总耗时 {t3 - t0:.1f}s")
    return inserted


# ------------------------------------------------------------------
# 问答：问题 → 两路召回 + RRF 融合 → 大模型回答
# ------------------------------------------------------------------


def ask(question: str, top_k: int = 5) -> tuple[list[dict], str]:
    """完整 RAG 链路：检索 + 生成。

    返回 (chunks, answer_text)，方便以后 FastAPI 复用；
    命令行使用时结果已经打印出来了。
    """
    # 延迟导入：预览模式不需要模型和数据库
    from .llm import answer
    from .rrf import retrieve

    print(f"问题: {question}\n")

    t0 = time.perf_counter()
    chunks = retrieve(question, top_k=top_k)
    t1 = time.perf_counter()

    if not chunks:
        print("没有检索到相关资料，无法回答")
        return [], ""

    # 打印引用了哪些块，方便核对回答有没有依据
    print(f"召回 {len(chunks)} 条资料（{t1 - t0:.2f}s）：")
    for i, c in enumerate(chunks, 1):
        source = c.get("source") or "未知来源"
        routes = "+".join(c.get("routes") or [])
        preview = " ".join((c.get("content") or "").split())[:50]
        print(f"  [{i}] {source} 块 {c.get('chunk_index')} ({routes}) {preview}")
    print()

    print("回答: ", end="", flush=True)
    pieces: list[str] = []
    try:
        for piece in answer(question, chunks, stream=True):
            pieces.append(piece)
            print(piece, end="", flush=True)
    except Exception as e:
        print(f"\n\n调用大模型失败: {e}")
        return chunks, ""

    text = "".join(pieces)
    t2 = time.perf_counter()
    print(f"\n\n[检索 {t1 - t0:.2f}s / 生成 {t2 - t1:.2f}s / 引用 {len(chunks)} 条]")
    return chunks, text


# ------------------------------------------------------------------
# 入口
# ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    # Windows 控制台默认 GBK，中文容易乱码，统一按 UTF-8 输出
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = list(sys.argv[1:] if argv is None else argv)
    build = "--build" in args
    ask_mode = "--ask" in args
    paths = [a for a in args if not a.startswith("-")]

    if not paths:
        print(
            "用法（在项目根目录 ragdemo/ 下）:\n"
            "  python -m server.main <文件或目录>            # 预览加载与切分\n"
            "  python -m server.main --build <文件或目录>    # 向量化并入库\n"
            "  python -m server.main --ask \"问题\"            # 检索 + 大模型回答"
        )
        return

    if build:
        build_index(paths[0])
    elif ask_mode:
        ask(paths[0])
    else:
        inspect(paths[0])


if __name__ == "__main__":
    main()
