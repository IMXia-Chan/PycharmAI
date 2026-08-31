"""ErrorKnowledgeBase 入口:纯本地双库知识库系统。

直接运行 `python main.py` 会跑一遍演示(个人库增删改查 + 搜索 + 公共库只读),
证明两个库和存储逻辑能正常工作。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证从任意目录运行都能 import core
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.models import PrivateRecord, PublicRecord  # noqa: E402
from core.searcher import Searcher  # noqa: E402
from core.storage import PrivateDatabase, PublicDatabase  # noqa: E402


def demo() -> None:
    public = PublicDatabase()
    private = PrivateDatabase()
    searcher = Searcher(public, private)

    print("=" * 54)
    print(" ErrorKnowledgeBase · 纯本地双库知识库演示")
    print("=" * 54)

    # 1. 个人库:新增
    rec = private.add(PrivateRecord(
        error_type="ModuleNotFoundError",
        error_message="No module named 'requests'",
        language="Python",
        solution="在终端执行: pip install requests",
        code_context="import requests",
        file_path="demo.py",
    ))
    print(f"\n[1 新增] 个人库新增一条记录  id={rec.id[:8]}")
    print(f"         timestamp={rec.timestamp}")

    # 2. 个人库:按 id 查询
    got = private.get(rec.id)
    print(f"\n[2 查询] 按 id 查回: {got.error_type if got else '未找到'}")

    # 3. 个人库:修改
    private.update(rec.id, solution_verified=True, solution="pip install requests")
    got = private.get(rec.id)
    print(f"\n[3 修改] solution_verified={got.solution_verified}  solution={got.solution}")

    # 4. 搜索(两个库都搜,BM25 相关度排序,带高亮)
    hits = searcher.search_all("requests")
    print(f"\n[4 搜索] 关键词 'requests' → 公共库 {len(hits['public'])} 条, 个人库 {len(hits['private'])} 条")
    for h in hits["public"][:1]:
        print(f"         公共库 top1: score={h.score:.3f}  {h.highlights}")
    for h in hits["private"][:1]:
        print(f"         个人库 top1: score={h.score:.3f}  {h.highlights}")

    # 5. 公共库:只读 + 模拟爬虫写入(去重)
    print(f"\n[5 公共库] 当前 {public.count()} 条(只读,仅爬虫可写)")
    public.write_from_crawler([PublicRecord(
        error_type="ModuleNotFoundError",
        error_message="No module named 'requests'",
        language="Python",
        solution="pip install requests",
        tags=["import", "pip", "dependency"],
        source="github/example/demo",
    )])
    print(f"         模拟爬虫写入 → {public.count()} 条")
    public.write_from_crawler([PublicRecord(
        error_type="ModuleNotFoundError",
        error_message="No module named 'requests'",
        language="Python",
        solution="pip install requests",
        tags=["import"],
        source="github/example/demo",
    )])
    print(f"         重复写同一条 → 仍 {public.count()} 条(按 类型+信息+来源 去重)")

    # 6. 个人库:删除(清理演示记录)
    private.delete(rec.id)
    print(f"\n[6 删除] 清理演示记录后,个人库剩 {len(private.all())} 条")

    print("\n" + "=" * 54)
    print(" 跑通了! 数据都在本地 data/ 目录下")
    print(" 提示:公共库留了 1 条示例数据(来源 github/example/demo)")
    print("      便于你看格式;不需要可清空 data/public_db.json 的 records")
    print("=" * 54)


if __name__ == "__main__":
    demo()
