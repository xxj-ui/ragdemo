# ragdemo · 本机知识库问答（RAG）

单用户、仅本机运行的 Web 知识库问答：批量上传文档 → 基于知识库提问 → 流式回答 + 引用来源 → 历史回看。

> **当前状态**：**设计已定稿 + 前后端骨架已搭建，业务逻辑待实现**。
> 已具备：RAG 内核（解析 / 切分 / 嵌入 / BM25 / RRF / DeepSeek 流式）+ 4 张表已落地 + 建表脚本 + 完整设计文档（01~08）+ FastAPI 骨架（8 个接口已注册、统一信封、错误码、请求体上限）+ React/Vite/TS 前端骨架（可构建、Vite 代理已打通）。
> **接口目前统一返回 `501 NOT_IMPLEMENTED`**，这是骨架期的预期行为。
> 下一步：M1（`config` 参数落地 → 仓储层实现 → 文档管理 3 个接口真正可用）。

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

# 5) 启动前端（另开一个终端；Vite 代理 /api → 127.0.0.1:8000）
scripts/run_web.sh         # Windows: scripts\run_web.bat
```

打开 `http://127.0.0.1:5173` 即可使用界面（问答 / 知识库两页）。

> 首次问答要等向量模型加载（约 20 s），状态胶囊会显示「部分能力不可用」，加载完成后自动回到「知识库就绪」。

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
├── server/          # 后端单包（地图见 server/README.md）
│   ├── core/        #   横切：config / errors / logging / timeutil / storage
│   ├── rag/         #   领域内核：解析/切分/嵌入/打分/融合/生成（纯算法）
│   ├── db/          #   数据访问：pool / documents / chunks / conversations
│   ├── api/         #   契约层：routes / schemas / deps
│   └── services/    #   编排：documents / retrieval / chat / history / health
├── web/             # 前端：React + Vite + TS（问答 / 知识库两页）
├── docs/            # 需求、SRS、设计 01~09、规范
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
