"""CLI 入口（开发/运维工具，不属于 Web 请求链路）

解析预览走 `rag/` 纯算法；`--build` 与 HTTP 上传共用 `db/` 仓储与同一事务边界；
`--ask` 走 `services/retrieval.py`，和未来的 `/api/chat` 是同一条检索链路。

用法（在项目根目录 ragdemo/ 下）:
    python -m server.main <文件或目录>            # 预览：加载 + 切分
    python -m server.main --build <文件或目录>    # 建库：加载 + 切分 + 向量化 + 入库
    python -m server.main --ask "问题"            # 问答：检索 + 大模型回答

预览模式只依赖标准库；建库和问答需要 sentence-transformers、psycopg、openai。
"""

import sys
import time
from pathlib import Path

from server.rag.loaders import load_all
from server.rag.splitter import split_documents


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
    """按文件逐个入库，写入路径与 HTTP 上传一致（documents + rag_chunks 同事务）。

    不再自建表：DDL 只有 scripts/sql/schema.sql 一处（02 §4.3 / 03 §2）。
    """
    from psycopg.rows import dict_row
    import psycopg

    from server.core.config import PROJECT_ROOT
    from server.db.documents import DocumentRepository
    from server.db.chunks import PgChunkRepository
    from server.rag.embedder import embed_documents
    from server.rag.loaders import LOADERS, load

    root = Path(path)
    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = [f for f in sorted(root.rglob("*")) if f.is_file() and f.suffix.lower() in LOADERS]
    else:
        raise FileNotFoundError(f"路径不存在: {root}")

    repo = PgChunkRepository()
    doc_repo = DocumentRepository(repo.dsn)

    t0 = time.perf_counter()
    total = 0
    for f in files:
        try:
            docs = load(f)
        except Exception as exc:
            print(f"跳过 {f.name}：加载失败 {exc}")
            continue
        chunks = split_documents(docs, size=size, overlap=overlap)
        if not chunks:
            print(f"跳过 {f.name}：无可入库内容")
            continue

        t1 = time.perf_counter()
        vectors = embed_documents([c["text"] for c in chunks], batch_size=batch_size, show_progress=False)
        t2 = time.perf_counter()

        try:
            stored_path = f.resolve().relative_to(PROJECT_ROOT).as_posix()
        except ValueError:                      # 项目外文件，存绝对路径
            stored_path = str(f.resolve())

        suffix = f.suffix.lower()
        with psycopg.connect(repo.dsn) as conn:
            conn.row_factory = dict_row
            existing = doc_repo.find_by_filename(f.name, conn=conn)
            if existing is not None:
                doc_id = existing["id"]
                doc_repo.replace_meta(
                    doc_id, filename=f.name, stored_path=stored_path,
                    file_type=suffix.lstrip("."), file_size=f.stat().st_size, conn=conn,
                )
                repo.delete_by_document(doc_id, conn=conn)
            else:
                doc_id = doc_repo.insert(
                    filename=f.name, stored_path=stored_path,
                    file_type=suffix.lstrip("."), file_size=f.stat().st_size, conn=conn,
                )
            repo.insert_for_document(doc_id, f.name, chunks, vectors, conn=conn)
            doc_repo.update_chunk_count(doc_id, len(chunks), conn=conn)

        total += len(chunks)
        print(f"入库 {f.name}：doc_id={doc_id} 片段={len(chunks)} 向量化={t2 - t1:.1f}s")

    print(f"\n入库完成：{total} 条片段，总耗时 {time.perf_counter() - t0:.1f}s")
    return total



# ------------------------------------------------------------------
# 问答：问题 → 两路召回 + RRF 融合 → 大模型回答
# ------------------------------------------------------------------


def ask(question: str, top_k: int = 5) -> tuple[list[dict], str]:
    """完整 RAG 链路：检索 + 生成。

    返回 (chunks, answer_text)，方便以后 FastAPI 复用；
    命令行使用时结果已经打印出来了。
    """
    # 延迟导入：预览模式不需要模型和数据库
    from server.api.deps import get_container
    from server.rag.llm import answer
    from server.services.retrieval import retrieve

    print(f"问题: {question}\n")

    t0 = time.perf_counter()
    chunks = retrieve(get_container(), question, top_k=top_k)
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
