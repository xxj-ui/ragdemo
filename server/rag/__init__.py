"""RAG 领域内核（02 §2.2）：解析 / 切分 / 嵌入 / 分词打分 / 融合 / 生成。

**依赖方向（硬约定）**：本包只允许 import 标准库、第三方算法库（sentence-transformers、
jieba、openai）与包内模块。**禁止** import `psycopg`、`fastapi`，禁止 import
`server.api` / `server.services` / `server.db` / `server.app`。

理由：内核要能被单元测试直接调用（给字符串、出结果），换存储或换 Web 框架都不该改它。
"取哪些数据、按什么顺序、事务边界在哪"属于 `services/`，SQL 属于 `db/`。
"""
