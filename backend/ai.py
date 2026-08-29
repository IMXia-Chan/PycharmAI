"""DeepSeek 调用封装(接口兼容 OpenAI)。支持每请求传入用户自己的 API key。"""
from openai import OpenAI

from . import config

# 按 API key 缓存客户端,避免每个请求都新建连接
_clients: dict[str, OpenAI] = {}


def _resolve_key(api_key: str | None) -> str:
    """优先用请求带来的 key,否则退回 backend/.env 的全局 key。"""
    return (api_key or "").strip() or config.DEEPSEEK_API_KEY


def is_available(api_key: str | None = None) -> bool:
    return bool(_resolve_key(api_key))


def get_client(api_key: str | None = None) -> OpenAI:
    key = _resolve_key(api_key)
    if not key:
        raise RuntimeError(
            "未配置 API key,请在插件的「接入你的 API」弹窗中填写,或在 backend/.env 填 DEEPSEEK_API_KEY"
        )
    if key not in _clients:
        _clients[key] = OpenAI(api_key=key, base_url=config.DEEPSEEK_BASE_URL)
    return _clients[key]


def chat(
    system: str,
    user: str,
    temperature: float = 0.3,
    json_mode: bool = False,
    max_tokens: int | None = None,
    api_key: str | None = None,
) -> str:
    """调用 DeepSeek,返回文本。json_mode=True 时要求模型返回 JSON 字符串。"""
    client = get_client(api_key)
    kwargs: dict = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""
