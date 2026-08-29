"""全局配置:从环境变量 / backend/.env 读取。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- DeepSeek ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# --- 真云端文件库(server/) ---
# 填了 CLOUD_URL 就走远程同步服务;留空则退回本地 SQLite(方便先跑通)
CLOUD_URL = os.getenv("CLOUD_URL", "").rstrip("/")
CLOUD_TOKEN = os.getenv("CLOUD_TOKEN", "dev-token")

# --- 数据存储:默认「本地」(记录/笔记/片段都存本机)。
# 以后若想恢复多用户云端同步,把 backend/.env 里设 STORAGE_MODE=remote 即可。 ---
STORAGE_MODE = os.getenv("STORAGE_MODE", "local")

# --- 本地 ---
LOCAL_DB_PATH = os.getenv("LOCAL_DB_PATH", "assistant.db")
PORT = int(os.getenv("PORT", "8000"))
