"""第 4 步：向量存储（pgvector 数据访问层）

职责和老项目里的 Mapper / Repository 一致：
    只负责和数据库打交道，不关心向量是怎么算出来的。

连接串只从显式参数或环境变量读取（SRS 2.4.3：不得硬编码密码）：
    RAG_DB_DSN=postgresql://<user>:<password>@127.0.0.1:54328/ragdemo
缺失即抛错，不做任何默认值兜底。
"""

import os

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

    def init_table(self, dim: int = 512) -> None:
        """创建扩展、表和向量索引（已存在则跳过）。"""
        if not isinstance(dim, int) or dim <= 0:
            raise ValueError(f"非法的向量维度: {dim}")

        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id          bigserial PRIMARY KEY,
                    source      text NOT NULL,
                    page        text,
                    chunk_index integer,
                    content     text NOT NULL,
                    embedding   vector({dim})
                )
            """)
            # HNSW 索引：数据量大时加速检索；几百条数据加不加都行
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx
                ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops)
            """)

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def insert_chunks(
        self,
        chunks: list[dict],
        vectors: list[list[float]],
        batch_size: int = 100,
    ) -> int:
        """批量写入。chunks 和 vectors 必须一一对应。"""
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunk 数量({len(chunks)}) 和 向量数量({len(vectors)}) 不一致"
            )
        if not chunks:
            return 0

        dim = len(vectors[0])
        for i, v in enumerate(vectors):
            if len(v) != dim:
                raise ValueError(f"第 {i} 条向量维度是 {len(v)}，与第一条({dim})不一致")

        rows = [
            (
                chunk.get("source"),
                None if chunk.get("page") is None else str(chunk.get("page")),
                chunk.get("chunk_index"),
                chunk["text"],
                _to_vector_literal(vector),
            )
            for chunk, vector in zip(chunks, vectors)
        ]

        sql = f"""
            INSERT INTO {TABLE_NAME}
                (source, page, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s, %s::vector)
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows, returning=False)
        return len(rows)

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
        sql = f"""
            SELECT id, source, page, chunk_index, content,
                   1 - (embedding <=> %s::vector) AS score
            FROM {TABLE_NAME}
            ORDER BY embedding <=> %s::vector
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
                "score": float(row[5]),
            }
            for row in rows
        ]

    def fetch_all(self) -> list[dict]:
        """读出全部 chunk（不带向量），给 BM25 这类内存索引使用。"""
        sql = f"""
            SELECT id, source, page, chunk_index, content
            FROM {TABLE_NAME}
            ORDER BY id
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
