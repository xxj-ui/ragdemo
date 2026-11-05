-- v002: 多轮会话（删单轮唯一约束、补索引、给会话加 updated_at）
-- depends: V001__init_schema
-- 设计：docs/design/10.多轮会话设计.md §4.2 / 03.数据库设计.md v0.8
-- yoyo 把每个迁移放在单个事务里执行，文件内不写 BEGIN/COMMIT。

ALTER TABLE messages DROP CONSTRAINT IF EXISTS uq_messages_conversation_role;

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
    ON messages (conversation_id, id);

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS updated_at timestamptz;
UPDATE conversations SET updated_at = created_at WHERE updated_at IS NULL;
ALTER TABLE conversations ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE conversations ALTER COLUMN updated_at SET DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
    ON conversations (updated_at DESC, id DESC);

-- 回填：现有会话的 updated_at 取最后一条消息时间（没有消息则保持 created_at）
UPDATE conversations c
   SET updated_at = m.last_at
  FROM (SELECT conversation_id, max(created_at) AS last_at
          FROM messages GROUP BY conversation_id) m
 WHERE m.conversation_id = c.id AND m.last_at > c.updated_at;
