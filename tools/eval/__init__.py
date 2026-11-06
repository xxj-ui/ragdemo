"""11.RAG评测设计 §7.1 的执行层：probe / goldmap / metrics / report。

约定：
  * 只读项目：不发写请求、不建会话、不改库；
  * 结果一律落 `evals/runs/<run_id>/`，一跑一目录；
  * 所有指标口径写在 report.md 的「方法」节，数字标「实测」。
"""
