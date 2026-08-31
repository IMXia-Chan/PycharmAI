"""一键灌公共库:下载 → 灌库 → 重建索引 → 搜索校验。

一条命令跑完整个流程,适合在有网机器上首次灌库或补数据:

    python -m crawler.fill_public --year 2023 --limit 200000

复用 stackexchange_crawler 的下载/清洗/灌库逻辑(run_clickhouse),再补上:
    - 灌库后从 public_db.json 强制重建检索索引,确保索引与数据 100% 一致;
    - 用一组常见异常词做搜索自检,确认灌进去的数据能被搜到。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 保证从任意目录运行本脚本都能 import core / crawler
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.stackexchange_crawler import run_clickhouse  # noqa: E402
from core.indexer import get_public_index  # noqa: E402
from core.searcher import Searcher  # noqa: E402
from core.storage import PrivateDatabase, PublicDatabase  # noqa: E402

# 校验用的常见异常词(灌库后应能命中)
VERIFY_QUERIES = [
    "TypeError", "ValueError", "ModuleNotFoundError", "IndexError",
    "KeyError", "AttributeError", "ImportError",
]


def rebuild_index() -> None:
    """从 public_db.json 强制重建检索索引,确保索引与数据一致。"""
    db = PublicDatabase()
    index = get_public_index(db)
    n = db.count()
    print(f"\n[索引] 从 {n} 条记录重建索引…")
    index.rebuild(db.all())
    print("[索引] 重建完成")


def rebuild_vector() -> None:
    """从 public_db.json 重建向量索引(若已安装 fastembed,否则跳过)。"""
    db = PublicDatabase()
    try:
        from core.vector import reload_public_vector
    except ImportError:
        print("\n[向量] 未安装 fastembed,跳过(中文检索仍走 BM25;可 pip install fastembed 后跑 python -m core.vector)")
        return
    reload_public_vector(db)
    print("[向量] 重建完成")


def verify_search() -> int:
    """搜索自检:对一组常见异常词搜公共库,返回未命中的词数。"""
    db = PublicDatabase()
    searcher = Searcher(db, PrivateDatabase())
    print("\n[校验] 搜索自检:")
    miss = 0
    for q in VERIFY_QUERIES:
        hits = searcher.search_public(q)
        if hits:
            top = hits[0]
            print(f"  ✓ {q:<20} {len(hits):>6} 条命中 · top: {top.record.error_type}")
        else:
            miss += 1
            print(f"  ✗ {q:<20} 0 条命中(该异常词无数据)")
    return miss


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="一键灌公共库(下载→灌库→重建索引→校验)")
    parser.add_argument("--year", type=int, default=2023, help="SO 数据年份(默认 2023)")
    parser.add_argument("--limit", type=int, default=200000, help="最多灌入条数(默认 20 万)")
    args = parser.parse_args(argv)

    print("=" * 58)
    print(f" 一键灌公共库 · Stack Overflow {args.year} 年 · 上限 {args.limit} 条")
    print("=" * 58)

    # 1 + 2: 下载 + 灌库(带进度)
    run_clickhouse(args.year, args.limit)

    # 3: 重建索引(确保一致)
    rebuild_index()

    # 3.5: 重建向量索引(中文检索语义兜底,需 fastembed)
    rebuild_vector()

    # 4: 搜索校验
    miss = verify_search()

    db = PublicDatabase()
    print("\n" + "=" * 58)
    print(f" 完成! 公共库共 {db.count()} 条记录")
    print(f" 数据文件: {db.path}")
    if miss:
        print(f" 提示: 有 {miss} 个异常词未命中(可能该年份数据里没有对应异常)")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
