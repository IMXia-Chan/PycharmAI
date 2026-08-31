"""中文分词与检索字段权重定义。

只做两件事:
    1. tokenize(text) —— 中英文混合分词(中文用 jieba,英文/数字按词切,统一转小写);
    2. 字段权重表 —— BM25 字段加权用的 boost 值(报错类型/信息最重,解决方案次之)。
"""
from __future__ import annotations

import logging
import re

import jieba

# 关闭 jieba 首次加载词典时向 stderr 打印的日志
jieba.setLogLevel(logging.WARNING)

# 连续中文字段
_CJK_RE = re.compile(r"([一-鿿]+)")
# 英文/数字/下划线(代码符号、报错名等)
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """把一段文本切成检索词。中文段走 jieba,非中文段按 [A-Za-z0-9_]+ 切,统一转小写。"""
    if not text:
        return []
    tokens: list[str] = []
    for seg in _CJK_RE.split(text):
        if not seg:
            continue
        if _CJK_RE.fullmatch(seg):
            tokens.extend(w for w in jieba.cut(seg) if w.strip())
        else:
            tokens.extend(_WORD_RE.findall(seg))
    return [t.lower() for t in tokens]


# 字段权重(boost):值越大,该字段命中对相关度贡献越高
PUBLIC_FIELDS = {
    "error_type": 3.0,
    "error_message": 3.0,
    "solution": 2.0,
    "tags": 1.5,
    "language": 1.0,
    "source": 0.5,
}

PRIVATE_FIELDS = {
    "error_type": 3.0,
    "error_message": 3.0,
    "solution": 2.0,
    "code_context": 1.5,
    "file_path": 1.0,
    "language": 1.0,
}
