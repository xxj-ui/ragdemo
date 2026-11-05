-- V002 回滚：恢复单轮约束、删除新增列与索引
-- 注意：只适用于「库中不存在多轮数据」；否则 ALTER TABLE ... UNIQUE 会失败。
ALTER TABLE messages ADD CONSTRAINT uq_messages_conversation_role UNIQUE (conversation_id, role);
DROP INDEX IF EXISTS idx_messages_conversation_id;
DROP INDEX IF EXISTS idx_conversations_updated_at;
ALTER TABLE conversations DROP COLUMN IF EXISTS updated_at;
