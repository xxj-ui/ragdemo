# ragdemo · 本机知识库问答（RAG）

单用户、仅本机运行的 Web 知识库问答：批量上传文档 → 基于知识库提问 → 流式回答 + 引用来源 → 历史回看。

> **当前状态**：**设计已定稿，Web 层与前端尚未开始**。
> 已具备：RAG 内核（解析 / 切分 / 嵌入 / BM25 / RRF / DeepSeek 流式）+ 4 张表已落地 + 建表脚本 + 完整设计文档。
> 下一步：M1（`server/app.py`、`config.py`、`errors.py`、仓储层、8 个路由骨架）。

## 环境要求

| 项 | 要求 | 本机实测 |
| --- | --- | --- |
| Python | 3.11+ | 3.13.9（`D:\develop\python`，依赖已全装） |
| PostgreSQL | 15+ 且安装 pgvector | 17.10 + pgvector 0.8.5，容器 `pgvector`，端口 **54328** |
| Node.js | 18+（M3 用） | 24.16.0 |
| 模型缓存 | `BAAI/bge-small-zh-v1.5`（离线） | `D:\models\huggingface` |

## 快速开始

```bash
# 1) 安装依赖
pip install -r requirements.txt

# 2) 配置环境变量（不要把任何密钥提交进版本库）
export RAG_DB_DSN='postgresql://<user>:<password>@127.0.0.1:54328/ragdemo'   # 必填，缺失即启动失败
export DEEPSEEK_API_KEY='sk-...'                                             # 问答需要

# 3) 建表（幂等，可重复执行）
psql "$RAG_DB_DSN" -f scripts/sql/schema.sql

# 4) 启动后端（单 worker，不要加 --workers）
scripts/run_dev.sh        # Windows: scripts\run_dev.bat
```

启动后：接口文档 `http://127.0.0.1:8000/docs`，健康检查 `http://127.0.0.1:8000/api/health`。

> `server/app.py` 是 M1 交付物，当前还不存在——`run_dev.*` 会提示"未就绪"并退出，这是预期行为。

## CLI（现在就能用）

```bash
python -m server.main <文件或目录>            # 预览解析与切分结果
python -m server.main --build <文件或目录>    # 向量化并入库
python -m server.main --ask "问题"            # 检索 + 大模型回答
```

## 环境变量

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `RAG_DB_DSN` | ✅ | PostgreSQL 连接串；缺失时构造仓储层即抛错（SRS 2.4.3） |
| `DEEPSEEK_API_KEY` | 问答必填 | 只从环境变量读取，不进日志/响应/前端 |
| `HF_HOME`（可选） | — | 模型缓存位置，默认已指向 `D:\models\huggingface` |

## 目录

```text
ragdemo/
├── server/          # 后端单包：领域内核 + （M1 起）Web 层
├── docs/            # 需求、SRS、设计 01~06、规范
├── prototype/       # 高保真原型（交互蓝本，只读参照）
├── scripts/         # sql/schema.sql、run_dev.*、run_web.*
├── data/uploads/    # 原文件落盘（运行期生成，不进版本库）
└── tests/           # pytest（M1 起）
```

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [docs/00.需求分析.md](docs/00.需求分析.md) | 角色 / 场景 / 用例 / 优先级 |
| [docs/SRS.md](docs/SRS.md) | FR / NFR / BR / AC + 接口与数据契约 |
| [docs/design/01.功能模块梳理.md](docs/design/01.功能模块梳理.md) | 功能清单、7 个模块、核心流程 |
| [docs/design/02.整体架构设计.md](docs/design/02.整体架构设计.md) | 技术选型、分层、目录、主链路时序、决策 |
| [docs/design/03.数据库设计.md](docs/design/03.数据库设计.md) | 4 张表、约束、索引、迁移 |
| [docs/design/04.API接口设计.md](docs/design/04.API接口设计.md) | 8 个接口、20 个错误码、SSE 事件 |
| [docs/design/05.设计方案评审结果.md](docs/design/05.设计方案评审结果.md) | 四阶段一致性评审与修订记录 |
| [docs/design/06.遗留问题清单.md](docs/design/06.遗留问题清单.md) | 开放项与销号记录 |
| [docs/design/07.测试用例清单.md](docs/design/07.测试用例清单.md) | 29 条用例（AC-1~13 + 边界 + 内核单测） |
| [docs/design/08.性能基线实测.md](docs/design/08.性能基线实测.md) | 解析/切分/嵌入/冷启动实测值与未测项 |
| [docs/rules/](docs/rules/) | API 与数据库设计规范 |

## 验收

按 [SRS 第 10 节](docs/SRS.md) 的 AC-1 ~ AC-13 逐条验；用例清单见 [docs/design/07.测试用例清单.md](docs/design/07.测试用例清单.md)。
