"""CLI 兼容入口

真实实现在 `server/rag/cli.py`（原 `server/main.py`）。保留本文件是为了让
`python -m server.main ...` 这条已写进 README / 设计文档的命令继续可用；
新代码请直接调用 `server.rag` 里的模块。

用法（在项目根目录 ragdemo/ 下）:
    python -m server.main <文件或目录>            # 预览：加载 + 切分
    python -m server.main --build <文件或目录>    # 建库：加载 + 切分 + 向量化 + 入库
    python -m server.main --ask "问题"            # 问答：检索 + 大模型回答
"""
from __future__ import annotations

from server.rag.cli import main

if __name__ == "__main__":
    main()
