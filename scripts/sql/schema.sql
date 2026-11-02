-- =====================================================================
-- ragdemo · 建表脚本
-- 文件：scripts/sql/schema.sql
-- 设计：docs/design/03.数据库设计.md v0.1
-- 目标：PostgreSQL + pgvector（本机 127.0.0.1:54328 / 库 ragdemo）
-- 用法：psql "$RAG_DB_DSN" -f scripts/sql/schema.sql
--       本脚本含 psql 元命令 `\set ON_ERROR_STOP on`；若改用 psycopg 等客户端执行，
--       请删除该行（事务已由 BEGIN/COMMIT 保证原子性）。
--
-- 约定
--   1. 幂等：可重复执行；第二次执行不产生变更，也不报错。
--   2. 不含破坏性语句：清空存量 rag_chunks 属一次性迁移动作，按设计 03
--      §6.3 手工执行，不写进本脚本（避免误跑清库）。
--   3. 前置条件：存量 rag_chunks 旧数据（无 document_id）必须先清空；
--      否则 §2.3 的守卫会中断脚本并给出提示。
--   4. 不建物理外键（database-rules §4.2）；级联删除由服务层在同一事务内保证。
--   5. 时间列统一 timestamptz，库内以 UTC 语义存储（database-rules §3.5）。
-- =====================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ---------------------------------------------------------------------
-- 0. 扩展
-- ---------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------
-- 1. documents：文档主表（一行 = 一份文件；同名覆盖沿用同一行）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id          bigserial   PRIMARY KEY,
    filename    text        NOT NULL,
    stored_path text        NOT NULL,
    file_type   text        NOT NULL,
    file_size   bigint      NOT NULL,
    chunk_count integer     NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_documents_filename_len CHECK (char_length(filename) BETWEEN 1 AND 255),
    CONSTRAINT ck_documents_file_type    CHECK (file_type IN ('pdf', 'docx', 'md', 'txt', 'xlsx', 'csv')),
    CONSTRAINT ck_documents_file_size    CHECK (file_size > 0),
    CONSTRAINT ck_documents_chunk_count  CHECK (chunk_count >= 0),
    CONSTRAINT ck_documents_updated_at   CHECK (updated_at >= created_at)
);

-- 文件名唯一：不区分大小写（SRS 6.1「Windows 下按不区分大小写处理」）
-- 用表达式唯一索引实现，保留 filename 的原始大小写用于展示
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_filename_lower
    ON documents (lower(filename));

-- 服务端生成的存储路径唯一（防止两次上传落到同一物理文件）
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_stored_path
    ON documents (stored_path);

-- 列表排序：最近更新倒序（FR-2 / Q5）；id 作为稳定次序键
CREATE INDEX IF NOT EXISTS idx_documents_updated_at
    ON documents (updated_at DESC, id DESC);

-- ---------------------------------------------------------------------
-- 2. rag_chunks：知识片段（存量表改造 + 全新建表兼容）
-- ---------------------------------------------------------------------
-- 2.1 全新库：直接按目标结构建表
CREATE TABLE IF NOT EXISTS rag_chunks (
    id          bigserial   PRIMARY KEY,
    document_id bigint      NOT NULL,
    source      text        NOT NULL,
    page        text,
    chunk_index integer     NOT NULL,
    content     text        NOT NULL,
    embedding   vector(512) NOT NULL,
    CONSTRAINT ck_rag_chunks_chunk_index CHECK (chunk_index >= 0),
    CONSTRAINT ck_rag_chunks_content_len CHECK (char_length(content) > 0)
);

-- 2.2 存量库：补逻辑关联列（幂等，已存在则跳过）
ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS document_id bigint;

-- 2.3 守卫：存量数据未清空时中断，避免静默写入 NULL 关联
DO $$
DECLARE
    null_doc     bigint;
    null_index   bigint;
    null_embed   bigint;
BEGIN
    EXECUTE 'SELECT count(*) FROM rag_chunks WHERE document_id IS NULL' INTO null_doc;
    EXECUTE 'SELECT count(*) FROM rag_chunks WHERE chunk_index IS NULL'  INTO null_index;
    EXECUTE 'SELECT count(*) FROM rag_chunks WHERE embedding IS NULL'    INTO null_embed;
    IF null_doc > 0 OR null_index > 0 OR null_embed > 0 THEN
        RAISE EXCEPTION
            'rag_chunks 存在无法满足 NOT NULL 的存量数据（document_id 空 % 行 / chunk_index 空 % 行 / embedding 空 % 行）。请先按设计 03 §6.3 清空旧数据（TRUNCATE rag_chunks）后重跑本脚本。',
            null_doc, null_index, null_embed;
    END IF;
END
$$;

-- 2.4 收紧列约束（仅当当前可空时执行，保证可重复运行）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'rag_chunks'
                  AND column_name = 'document_id' AND is_nullable = 'YES') THEN
        ALTER TABLE rag_chunks ALTER COLUMN document_id SET NOT NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'rag_chunks'
                  AND column_name = 'chunk_index' AND is_nullable = 'YES') THEN
        ALTER TABLE rag_chunks ALTER COLUMN chunk_index SET NOT NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'rag_chunks'
                  AND column_name = 'embedding' AND is_nullable = 'YES') THEN
        ALTER TABLE rag_chunks ALTER COLUMN embedding SET NOT NULL;
    END IF;
END
$$;

-- 2.5 补充 CHECK 约束（存量表在 2.1 被跳过时也需要）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_rag_chunks_chunk_index'
                      AND conrelid = 'rag_chunks'::regclass) THEN
        ALTER TABLE rag_chunks
            ADD CONSTRAINT ck_rag_chunks_chunk_index CHECK (chunk_index >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_rag_chunks_content_len'
                      AND conrelid = 'rag_chunks'::regclass) THEN
        ALTER TABLE rag_chunks
            ADD CONSTRAINT ck_rag_chunks_content_len CHECK (char_length(content) > 0);
    END IF;
END
$$;

-- 2.6 同一文档内片段序号唯一；该索引最左列即 document_id，
--     同时承担「按文档删除 / 按文档取片段」的访问路径，无需再建单列索引
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_rag_chunks_document_chunk'
                      AND conrelid = 'rag_chunks'::regclass) THEN
        ALTER TABLE rag_chunks
            ADD CONSTRAINT uq_rag_chunks_document_chunk UNIQUE (document_id, chunk_index);
    END IF;
END
$$;

-- 2.7 向量索引（HNSW，余弦距离）
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_hnsw
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);

-- 统一索引命名（database-rules §2.7）；旧名索引与新建索引等价，删除以免重复维护
-- [待确认 Q5] 若裁决保留旧命名，注释掉下一行
DROP INDEX IF EXISTS rag_chunks_embedding_idx;

-- ---------------------------------------------------------------------
-- 3. conversations：会话（一行 = 一次提问）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id         bigserial   PRIMARY KEY,
    title      text        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_conversations_title_len CHECK (char_length(title) BETWEEN 1 AND 30)
);

-- 历史列表：时间倒序（FR-6 / F-23），id 作为稳定次序键
CREATE INDEX IF NOT EXISTS idx_conversations_created_at
    ON conversations (created_at DESC, id DESC);

-- ---------------------------------------------------------------------
-- 4. messages：消息（一个会话固定一条 user + 一条 assistant）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id              bigserial   PRIMARY KEY,
    conversation_id bigint      NOT NULL,
    role            text        NOT NULL,
    content         text        NOT NULL,
    citations       jsonb       NOT NULL DEFAULT '[]'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_messages_role           CHECK (role IN ('user', 'assistant')),
    CONSTRAINT ck_messages_content_len    CHECK (char_length(content) > 0),
    CONSTRAINT ck_messages_citations_type CHECK (jsonb_typeof(citations) = 'array')
);

-- 单轮问答的完整性防线：同一会话内每种角色只能有一条
-- [待确认 Q2] 若裁决不锁定单轮，删除本约束并改回 SRS 6.4 的 (conversation_id, created_at) 索引
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_messages_conversation_role'
                      AND conrelid = 'messages'::regclass) THEN
        ALTER TABLE messages
            ADD CONSTRAINT uq_messages_conversation_role UNIQUE (conversation_id, role);
    END IF;
END
$$;

-- ---------------------------------------------------------------------
-- 5. 注释（随库保存，便于 psql 内自查）
-- ---------------------------------------------------------------------
COMMENT ON TABLE  documents                IS '文档主表：一行对应一份已入库文件，同名覆盖沿用同一行';
COMMENT ON COLUMN documents.filename       IS '原始文件名（保留大小写，唯一性按 lower() 判定）';
COMMENT ON COLUMN documents.stored_path    IS '服务端生成的存储路径，相对项目根，如 data/uploads/<uuid>.pdf';
COMMENT ON COLUMN documents.file_type      IS 'pdf / docx / md / txt / xlsx / csv';
COMMENT ON COLUMN documents.file_size      IS '字节数，入库文件恒 > 0（空文件在前置校验被拒）';
COMMENT ON COLUMN documents.chunk_count    IS '片段数冗余统计，与 rag_chunks 实际行数在同一事务内维护';
COMMENT ON COLUMN documents.created_at     IS '首次入库时间';
COMMENT ON COLUMN documents.updated_at     IS '最近覆盖时间，列表按此倒序';

COMMENT ON TABLE  rag_chunks               IS '知识片段：检索的最小单位，生命周期完全跟随 documents';
COMMENT ON COLUMN rag_chunks.document_id   IS '逻辑关联 documents(id)，无物理外键，级联删除由服务层保证';
COMMENT ON COLUMN rag_chunks.source        IS '冗余文件名快照（写入时等于 documents.filename），供检索结果直接带出';
COMMENT ON COLUMN rag_chunks.page          IS '位置原值：PDF 为页码，表格类为 Sheet 行标识，无页码为 NULL；展示层统一映射';
COMMENT ON COLUMN rag_chunks.chunk_index   IS '同一文档内从 0 开始的连续序号，与 document_id 组合唯一';
COMMENT ON COLUMN rag_chunks.embedding     IS 'bge-small-zh-v1.5 输出，512 维，已归一化，余弦距离检索';

COMMENT ON TABLE  conversations            IS '会话：一行对应一次提问及其回答';
COMMENT ON COLUMN conversations.title      IS '问题前 30 字，不含省略号（截断由展示层完成）';

COMMENT ON TABLE  messages                 IS '消息：每会话一条 user + 一条 assistant';
COMMENT ON COLUMN messages.citations       IS '引用快照（自包含，文档删除后仍完整展示），元素 {n, filename, page, snippet, chunk_id}；user 消息恒为 []';

-- ---------------------------------------------------------------------
-- 6. 自检：打印表 / 约束 / 索引数量，供执行后人工核对
-- ---------------------------------------------------------------------
SELECT c.relname AS table_name,
       (SELECT count(*) FROM pg_constraint k WHERE k.conrelid = c.oid) AS constraint_count,
       (SELECT count(*) FROM pg_index i WHERE i.indrelid = c.oid)     AS index_count
  FROM pg_class c
 WHERE c.relname IN ('documents', 'rag_chunks', 'conversations', 'messages')
 ORDER BY c.relname;

SELECT format_type(a.atttypid, a.atttypmod) AS embedding_type,
       a.attnotnull                         AS embedding_not_null
  FROM pg_attribute a
 WHERE a.attrelid = 'rag_chunks'::regclass
   AND a.attname  = 'embedding';

COMMIT;
