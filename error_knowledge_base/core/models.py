"""数据模型定义:公共库记录与个人库记录。

两个库都是纯本地 JSON 存储,本模块只定义「一条记录长什么样」,
不涉及任何读写逻辑(读写见 core/storage.py)。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def _now() -> str:
    """当前本地时间的 ISO 格式字符串,精确到秒。"""
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class PublicRecord:
    """公共库记录:从 GitHub 爬取,只读,不可修改。

    字段:
        error_type:    报错类型,如 ModuleNotFoundError
        error_message: 报错信息,如 No module named 'requests'
        language:      编程语言,如 Python
        solution:      解决方案
        tags:          标签列表,如 ["import", "pip", "dependency"]
        source:        数据来源,如 github/username/repo
    """

    error_type: str
    error_message: str
    language: str
    solution: str
    tags: list[str] = field(default_factory=list)
    source: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "PublicRecord":
        return cls(
            error_type=str(d.get("error_type", "")),
            error_message=str(d.get("error_message", "")),
            language=str(d.get("language", "")),
            solution=str(d.get("solution", "")),
            tags=list(d.get("tags", [])),
            source=str(d.get("source", "")),
        )


@dataclass
class PrivateRecord:
    """个人库记录:用户自己的报错记录,可增删改查。

    字段:
        error_type:        报错类型
        error_message:     报错信息
        language:          编程语言
        solution:          解决方案
        code_context:      触发报错的代码上下文
        file_path:         文件路径
        solution_verified: 解决方案是否经过验证
        timestamp:         记录时间
        is_shared:         是否已共享(预留,默认 False,当前不实现共享)
        shared_at:         共享时间(预留,默认 None)
        id:                内部唯一标识,便于增删改查定位(非业务字段)
    """

    error_type: str
    error_message: str
    language: str
    solution: str
    code_context: str = ""
    file_path: str = ""
    solution_verified: bool = False
    timestamp: str = field(default_factory=_now)
    is_shared: bool = False
    shared_at: Optional[str] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @classmethod
    def from_dict(cls, d: dict) -> "PrivateRecord":
        return cls(
            error_type=str(d.get("error_type", "")),
            error_message=str(d.get("error_message", "")),
            language=str(d.get("language", "")),
            solution=str(d.get("solution", "")),
            code_context=str(d.get("code_context", "")),
            file_path=str(d.get("file_path", "")),
            solution_verified=bool(d.get("solution_verified", False)),
            timestamp=str(d.get("timestamp", _now())),
            is_shared=bool(d.get("is_shared", False)),
            shared_at=d.get("shared_at"),
            id=str(d.get("id", uuid.uuid4().hex)),
        )
