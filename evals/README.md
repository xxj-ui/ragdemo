# evals/ 目录约定

两类东西，**永远分开放**：

```
evals/
├── datasets/                       # 评测问题 + 参考答案（输入）
│   ├── e1-dataset.jsonl            # E1 用的 30 题：user_input / reference / gold_news / coverage
│   ├── crud-pool-usable.jsonl      # 全部合格题（259 道），E2/E3 从这里抽
│   ├── e1-dataset.meta.json        # 筛选口径、来源 sha256、池子统计、抽样 seed、作废记录
│   └── _superseded/
│       └── e1-dataset.v1.jsonl     # 作废版（v1「4 偏移」口径），只留追溯、不参与评测
└── runs/                           # 每次跑测的产物（输出）
    ├── <run_id>/                   # 例：ret-20261105-154157（检索基线）/ e1-20261105-160518（采集）
    └── _superseded/<run_id>/       # 口径或代码改过而作废的 run，只留档、不作输入
        ├── config.json             # 本次参数：top_k / recall_k / rrf_k / chunk_size / 题数 / 裁判模型
        ├── samples.jsonl           # P2：逐题 user_input / retrieved_contexts / response / reference
        ├── ragas.jsonl             # P3：逐题 faithfulness / context_recall
        ├── report.md               # P1 结论 / P2 采集摘要
        └── ragas-report.md         # P3 打分报告（对外结论）
```

## 筛选口径（v2，当前有效）

一道题算「可测」必须同时满足：

| 判据 | 定义 | 阈值 |
|---|---|---|
| `backable` | gold 的 40 字不重叠窗中，能在两份语料正文里找到的比例 | ≥ 0.80 |
| `best_chunk` | 单个库内片段能覆盖该 gold（30 字窗、步长 10）的最高比例 | ≥ 0.50 |

**每篇 gold 都要满足**（2/3 文档题有 2~3 篇）。v1 用的是「30 字窗 × 4 偏移命中任意一处」，会把只有片段重合的题误判为可测（e1-001 实测只覆盖 45%），已作废。

## 三条不能破的规矩

1. **`datasets/` 只给评测脚本读，绝不导入知识库**。里面有 `reference` 和 gold 原文，一旦入库，检索能直接命中答案，Recall / Faithfulness 全部虚高，整轮评测作废（`.json` 也被后端白名单拒收，但改名绕过同样不行）。
2. **`runs/` 按时间戳一跑一目录**，跑前跑后各断言一次库规模（`rag_chunks` / `documents` 条数）；库变了就不是同一个实验，不能与旧 run 比数。
3. **`_superseded/` 只读不改**：口径变了就新建版本，旧的不删不动，方便对账。

## 数据流

```
datasets/<x>.jsonl ──user_input──▶ 检索 + 生成 ──▶ runs/<run_id>/result.json
                          │                              │
                          └──gold_news──▶ 命中判定 ──────┤
datasets/<x>.jsonl ──reference──────────▶ 打分（RAGAS / 自算指标）
```

设计依据见 [docs/design/11.RAG评测设计.md](../docs/design/11.RAG评测设计.md) §3（样本契约）、§7（执行与产出）、§11（首轮实跑与重筛记录）。
