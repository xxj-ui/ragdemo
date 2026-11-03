"""第 4 步：向量存储（pgvector 数据访问层）

职责和老项目里的 Mapper / Repository 一致：
    只负责和数据库打交道，不关心向量是怎么算出来的。

连接串只从显式参数或环境变量读取（SRS 2.4.3：不得硬编码密码）：
    RAG_DB_DSN=postgresql://<user>:<password>@127.0.0.1:54328/ragdemo
缺失即抛错，不做任何默认值兜底。
"""

import os
from contextlib import contextmanager

TABLE_NAME = "rag_chunks"

def _require_dsn(explicit: str | None = None) -> str:
    """返回数据库连接串；缺失即抛错（P-3：RAG_DB_DSN 必填）。"""
    dsn = explicit or os.getenv("RAG_DB_DSN")
    if not dsn:
        raise RuntimeError(
            "未配置数据库连接串：请设置环境变量 RAG_DB_DSN，"
            "形如 postgresql://<user>:<password>@127.0.0.1:54328/ragdemo"
        )
    return dsn




def _to_vector_literal(vector: list[float]) -> str:
    """把 Python 列表转成 pgvector 接受的字符串格式：[1,2,3]。"""
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


class PgChunkRepository:
    """rag_chunks 表的数据访问对象。"""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = _require_dsn(dsn)

    def _connect(self):
        try:
            import psycopg
        except ImportError as e:
            raise ImportError(
                "缺少数据库驱动，请先安装：pip install 'psycopg[binary]'"
            ) from e
        return psycopg.connect(self.dsn)

    # ------------------------------------------------------------------
    # 建表
    # ------------------------------------------------------------------

    def delete_by_source(self, source: str) -> int:
        """删除某个文件的旧数据（重新建库时用，保证幂等）。"""
        with self._connect() as conn:
            cur = conn.execute(
                f"DELETE FROM {TABLE_NAME} WHERE source = %s", (source,)
            )
            return cur.rowcount

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict]:
        """按余弦相似度返回 top_k 个 chunk（相似度从高到低）。

        注意：
            - 查询向量必须和建库时用同一个模型、同样归一化
            - `<=>` 是余弦距离（越小越近），1 - 距离 = 相似度
        """
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        literal = _to_vector_literal(query_vector)
        # filename 统一取 documents.filename（04 §7 数据映射），source 只作兜底
        sql = f"""
            SELECT c.id, c.source, c.page, c.chunk_index, c.content,
                   d.filename AS filename,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM {TABLE_NAME} c
            LEFT JOIN documents d ON d.id = c.document_id
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (literal, literal, top_k)).fetchall()

        return [
            {
                "id": row[0],
                "source": row[1],
                "page": row[2],
                "chunk_index": row[3],
                "content": row[4],
                "filename": row[5],
                "score": float(row[6]),
            }
            for row in rows
        ]

    def fetch_all(self) -> list[dict]:
        """读出全部 chunk（不带向量），给 BM25 这类内存索引使用。"""
        sql = f"""
            SELECT c.id, c.source, c.page, c.chunk_index, c.content,
                   d.filename AS filename
            FROM {TABLE_NAME} c
            LEFT JOIN documents d ON d.id = c.document_id
            ORDER BY c.id
        """
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()

        return [
            {
                "id": row[0],
                "source": row[1],
                "page": row[2],
                "chunk_index": row[3],
                "content": row[4],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(f"SELECT count(*) FROM {TABLE_NAME}").fetchone()
        return row[0]


    # ------------------------------------------------------------------
    # 按文档维度写入（M1：documents 表引入 document_id 之后）
    # ------------------------------------------------------------------
    @contextmanager
    def _using(self, conn=None):
        """复用外部事务连接；未传入则自开连接。"""
        if conn is not None:
            yield conn
            return
        with self._connect() as own:
            yield own

    def insert_for_document(
        self,
        document_id: int,
        source: str,
        rows: list[dict],
        vectors: list[list[float]],
        conn=None,
    ) -> int:
        """给某个文档批量写入片段；rows 元素形如 {"text","page","chunk_index"}。"""
        if len(rows) != len(vectors):
            raise ValueError(f"片段数({len(rows)})与向量数({len(vectors)})不一致")
        if not rows:
            return 0
        params = [
            (
                document_id,
                source,
                None if row.get("page") is None else str(row["page"]),
                row["chunk_index"],
                row["text"],
                _to_vector_literal(vector),
            )
            for row, vector in zip(rows, vectors)
        ]
        sql = f"""
            INSERT INTO {TABLE_NAME}
                (document_id, source, page, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s, %s, %s::vector)
        """
        with self._using(conn) as c:
            with c.cursor() as cur:
                cur.executemany(sql, params)
        return len(params)

    def delete_by_document(self, document_id: int, conn=None) -> int:
        """删除某文档的全部片段（BR-3：先删片段，再删文档行）。"""
        with self._using(conn) as c:
            cur = c.execute(f"DELETE FROM {TABLE_NAME} WHERE document_id = %s", (document_id,))
            return cur.rowcount

    # ------------------------------------------------------------------
    # 按文档维度只读（文档预览，FR-8）
    # ------------------------------------------------------------------

    def count_for_document(self, document_id: int, conn=None) -> int:
        with self._using(conn) as c:
            row = c.execute(
                f"SELECT count(*) AS n FROM {TABLE_NAME} WHERE document_id = %s", (document_id,)
            ).fetchone()
        # 连接池给的是 dict_row，自开连接是元组行
        return row["n"] if isinstance(row, dict) else row[0]

    def list_for_document(
        self, document_id: int, offset: int = 0, limit: int = 20, conn=None
    ) -> list[dict]:
        """按 chunk_index 顺序分页读片段（不带向量，预览用）。"""
        sql = f"""
            SELECT id, chunk_index, page, content
            FROM {TABLE_NAME}
            WHERE document_id = %s
            ORDER BY chunk_index
            OFFSET %s LIMIT %s
        """
        with self._using(conn) as c:
            rows = c.execute(sql, (document_id, offset, limit)).fetchall()
        # 外部传入的连接来自连接池（dict_row），自开的连接是元组行——两种都要吃得下
        def pick(row, idx, key):
            return row[key] if isinstance(row, dict) else row[idx]

        return [
            {
                "id": pick(row, 0, "id"),
                "chunk_index": pick(row, 1, "chunk_index"),
                "page": pick(row, 2, "page"),
                "content": pick(row, 3, "content"),
            }
            for row in rows
        ]
