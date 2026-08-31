"""数据存取逻辑:公共库(只读) + 个人库(增删改查),纯本地 JSON 存储。

约定:
    - 公共库(public_db.json)只读,只能由爬虫 write_from_crawler() 写入;
    - 个人库(private_db.json)支持 add / update / delete / get;
    - 所有数据都在本地 data/ 目录,不涉及任何网络上传;
    - share_to_public() 已预留,待接入云服务器后实现共享逻辑。

写时索引:每个写方法在落盘 JSON 后,同步增量更新检索索引(indexer 单例),
保证数据与索引一致,调用方无需关心索引。
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from core.indexer import get_private_index, get_public_index
from core.models import PrivateRecord, PublicRecord

# 以本文件位置定位项目根目录与数据目录,不依赖运行时 cwd
BASE_DIR = Path(__file__).resolve().parent.parent   # error_knowledge_base/
DATA_DIR = BASE_DIR / "data"
PUBLIC_DB_PATH = DATA_DIR / "public_db.json"
PRIVATE_DB_PATH = DATA_DIR / "private_db.json"


def _load_records(path: Path) -> list[dict]:
    """从 JSON 文件读出一批原始 dict 记录;文件不存在或损坏则返回空列表。"""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("records", [])
    return []


def _save_records(path: Path, records: list[dict]) -> None:
    """把一批 dict 记录写入 JSON 文件(自动建父目录,中文不转义,缩进 2)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"records": records}, f, ensure_ascii=False, indent=2)


class PublicDatabase:
    """公共库:从 GitHub 爬取的公开报错知识,只读。

    不提供 add / update / delete,防止误改公共数据;唯一写入入口是
    write_from_crawler(),留给爬虫脚本调用。
    """

    def __init__(self, path: Path = PUBLIC_DB_PATH):
        self.path = Path(path)
        # 文件不存在才创建(避免每次实例化都重写文件)
        if not self.path.exists():
            _save_records(self.path, [])

    def all(self) -> list[PublicRecord]:
        """返回公共库全部记录。"""
        return [PublicRecord.from_dict(d) for d in _load_records(self.path)]

    def count(self) -> int:
        """返回公共库记录总数。"""
        return len(_load_records(self.path))

    def write_from_crawler(self, records: list[PublicRecord]) -> int:
        """仅供爬虫调用:把爬取到的记录写入公共库(按来源去重后追加)。

        去重键为 (error_type, error_message, source),避免同一来源的
        同一条报错被重复写入。返回写入后公共库的记录总数。
        """
        index = get_public_index(self)
        existing = _load_records(self.path)
        seen = {
            (d.get("error_type"), d.get("error_message"), d.get("source"))
            for d in existing
        }
        new_records: list[PublicRecord] = []
        for r in records:
            key = (r.error_type, r.error_message, r.source)
            if key in seen:
                continue
            seen.add(key)
            new_records.append(r)
        if new_records:
            _save_records(self.path, existing + [asdict(r) for r in new_records])
            index.upsert_many(new_records)
        return len(existing) + len(new_records)


class PrivateDatabase:
    """个人库:用户自己的报错记录,支持增删改查。"""

    def __init__(self, path: Path = PRIVATE_DB_PATH):
        self.path = Path(path)
        # 文件不存在才创建(避免每次实例化都重写文件)
        if not self.path.exists():
            _save_records(self.path, [])

    def all(self) -> list[PrivateRecord]:
        """返回个人库全部记录(按记录时间倒序,新的在前)。"""
        records = [PrivateRecord.from_dict(d) for d in _load_records(self.path)]
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records

    def count(self) -> int:
        """返回个人库记录总数。"""
        return len(_load_records(self.path))

    def get(self, record_id: str) -> Optional[PrivateRecord]:
        """按 id 查一条记录;不存在返回 None。"""
        for r in self.all():
            if r.id == record_id:
                return r
        return None

    def add(self, record: PrivateRecord) -> PrivateRecord:
        """新增一条记录,返回该记录(含自动生成的 id)。"""
        index = get_private_index(self)
        records = _load_records(self.path)
        records.append(asdict(record))
        _save_records(self.path, records)
        index.upsert(record)
        return record

    def update(self, record_id: str, **changes) -> Optional[PrivateRecord]:
        """按 id 修改记录;传入要改的字段名与值,返回更新后的记录,不存在返回 None。"""
        index = get_private_index(self)
        records = _load_records(self.path)
        for i, d in enumerate(records):
            if d.get("id") == record_id:
                for key, value in changes.items():
                    if key != "id":  # id 是唯一标识,不允许改
                        d[key] = value
                _save_records(self.path, records)
                updated = PrivateRecord.from_dict(d)
                index.upsert(updated)
                return updated
        return None

    def delete(self, record_id: str) -> bool:
        """按 id 删除记录;删除成功返回 True,不存在返回 False。"""
        index = get_private_index(self)
        records = _load_records(self.path)
        remaining = [d for d in records if d.get("id") != record_id]
        if len(remaining) == len(records):
            return False
        _save_records(self.path, remaining)
        index.remove(record_id)
        return True

    def share_to_public(self, record_id: str) -> None:
        # TODO: 待接入云服务器后实现共享逻辑
        pass
