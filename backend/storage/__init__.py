"""存储工厂:根据配置返回本地 SQLite 或远程云端存储。"""
from __future__ import annotations

from .. import config
from .base import Storage
from .remote import RemoteStorage
from .sqlite import SqliteStorage

_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        if config.STORAGE_MODE == "remote" and config.CLOUD_URL:
            _storage = RemoteStorage(config.CLOUD_URL, config.CLOUD_TOKEN)
        else:
            _storage = SqliteStorage(config.LOCAL_DB_PATH)
    return _storage
