"""RAG 领域内核（02 §2.2）：解析 / 切分 / 嵌入 / 检索 / 融合 / 生成 / 片段读写。

**依赖方向（硬约定）**：本包只能 import 标准库、第三方库与本包内部模块。
禁止 import `server.app` / `server.routes` / `server.service` / `server.deps` / `fastapi`。
—— 内核保持可被 CLI（`server.rag.cli`）单独复用，不感知 Web 层。
"""
