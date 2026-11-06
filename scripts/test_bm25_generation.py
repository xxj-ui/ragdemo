"""Bm25Index 脏读修复的确定性单测（不依赖数据库/模型）。

模拟"构建期间发生写入"：fetch_all 在返回后立刻调用 invalidate()，
使 generation 变化 —— 旧实现会把这份作废快照 return 给调用方。
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.rag.bm25_index import Bm25Index

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

OLD = [
    {"chunk_id": 1, "document_id": 1, "filename": "a.md", "content": "旧文档 甲方案 结论 8 月"},
    {"chunk_id": 2, "document_id": 1, "filename": "a.md", "content": "旧文档 乙方案 结论 9 月"},
]
NEW = OLD + [
    {"chunk_id": 3, "document_id": 2, "filename": "b.md", "content": "新文档 丙方案 独有词 火星车"},
]

ok = 0
fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✅ {name} {extra}")
    else:
        fail += 1
        print(f"  ❌ {name} {extra}")


# ---- 1. 正常路径：只构建一次并缓存
print("[1] 正常路径")
idx = Bm25Index()
calls = []


def fetch_old():
    calls.append(1)
    return OLD


built = idx.ensure_built(fetch_old)
check("fetch 只调用一次", len(calls) == 1, f"calls={len(calls)}")
check("已缓存 (built=True)", idx.built)
check("片段数=2", idx.size == 2, f"size={idx.size}")
check("第二次调用不再 fetch", len(calls) == 1 and idx.ensure_built(fetch_old) is built)


# ---- 2. 构建期间写入一次：丢弃首份、重试一次、缓存的是新数据
print("[2] 首次构建期间写入（应重试一次并缓存新数据）")
idx2 = Bm25Index()
calls2 = []
state = {"n": 0}


def fetch_racy():
    """第 1 次返回旧数据并模拟写入（invalidate），第 2 次返回新数据。"""
    state["n"] += 1
    calls2.append(state["n"])
    if state["n"] == 1:
        idx2.invalidate()          # 构建读到旧快照后，写入落库并置失效
        return OLD
    return NEW


built2 = idx2.ensure_built(fetch_racy)
check("fetch 调用两次（重试）", len(calls2) == 2, f"calls={calls2}")
check("返回的是重试后的新索引", built2.size == 3, f"size={built2.size}")
check("新索引已缓存", idx2.built and idx2.size == 3, f"built={idx2.built} size={idx2.size}")
hits = built2.search("火星车", 5)
check("新文档能被检索到", len(hits) > 0)


# ---- 3. 两次都撞上写入：不缓存，下一次调用会重建
print("[3] 两次构建期间都写入（用最后一次应急，但不缓存）")
idx3 = Bm25Index()
calls3 = []


def fetch_always_racy():
    calls3.append(1)
    idx3.invalidate()              # 每次构建期间都有写入
    return NEW


built3 = idx3.ensure_built(fetch_always_racy)
check("fetch 调用两次（重试用尽）", len(calls3) == 2, f"calls={len(calls3)}")
check("仍返回可用索引（应急）", built3.size == 3, f"size={built3.size}")
check("未缓存 (built=False)", not idx3.built)
idx3.ensure_built(fetch_always_racy)
check("下次调用会重新构建", len(calls3) == 4, f"calls={len(calls3)}")


# ---- 4. rebuild() 同样重试
print("[4] rebuild() 撞上写入")
idx4 = Bm25Index()
calls4 = []
state4 = {"n": 0}


def fetch_racy4():
    state4["n"] += 1
    calls4.append(state4["n"])
    if state4["n"] == 1:
        idx4.invalidate()
        return OLD
    return NEW


built4 = idx4.rebuild(fetch_racy4)
check("fetch 调用两次", len(calls4) == 2, f"calls={calls4}")
check("缓存的是新索引", idx4.built and idx4.size == 3, f"built={idx4.built} size={idx4.size}")
check("rebuid 返回值=缓存值", built4 is idx4.ensure_built(lambda: NEW))


# ---- 5. 构建抛异常要向上传播（不能被重试逻辑吞掉）
print("[5] 构建异常向上传播")
idx5 = Bm25Index()


def boom():
    raise RuntimeError("db down")


try:
    idx5.ensure_built(boom)
    check("异常被吞（不应发生）", False)
except RuntimeError:
    check("异常正常抛出", True)


print(f"\n结果：{ok} 项通过，{fail} 项失败")
sys.exit(0 if fail == 0 else 1)
