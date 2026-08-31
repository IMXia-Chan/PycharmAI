"""GitHub 数据集爬取脚本:爬取公开报错知识,写入公共库(只读)。

说明:
    本脚本是「公共库数据来源」的唯一入口 —— 公共库只读,只能通过这里写入。
    当前为骨架,真实爬取逻辑(网络请求 / GitHub API / 公开数据集仓库)
    待后续实现;核心的双库本地存储不依赖它,可以先跑通存储部分。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证从任意目录运行本脚本都能 import core
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import PublicRecord  # noqa: E402
from core.storage import PublicDatabase  # noqa: E402


def crawl_github(public_db: PublicDatabase, repos: list[str] | None = None) -> int:
    """从 GitHub 数据集爬取公开报错记录,写入公共库(去重追加)。

    参数:
        public_db: 要写入的公共库实例
        repos:     要爬取的仓库列表(如 ["owner/repo", ...]);None 表示后续再定
    返回:
        写入后公共库的记录总数(当前骨架直接返回现有数量)。
    """
    # TODO: 待实现真实爬取逻辑(如 GitHub API 搜索报错、解析公开数据集仓库)。
    # 当前为占位骨架,不发起任何网络请求,只返回公共库现有记录数。
    _ = repos
    return public_db.count()


if __name__ == "__main__":
    db = PublicDatabase()
    n = crawl_github(db)
    print(f"公共库当前记录数: {n}")
