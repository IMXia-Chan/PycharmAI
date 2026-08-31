"""HTML 清洗:把 Stack Exchange 帖子的 HTML Body 转成纯文本。

纯函数模块,不依赖网络,只做「HTML → 干净纯文本」这一件事:
    - 剥离 <script> / <style>(防止恶意内容混入);
    - 保留 <pre><code> 代码块(报错 traceback 常在这里);
    - 块级元素(<p>/<div>/<br>/<li> 等)转成换行,行内元素原样拼接;
    - html.unescape 反转义实体(&gt; → > 等);
    - 超长文本按 MAX_LEN 截断,控制入库体积。

供 crawler/stackexchange_crawler.py 调用。
"""
from __future__ import annotations

import html
import re

from lxml import html as lxml_html

# 单条字段(正文/解决方案)的文本长度上限,超出截断
MAX_LEN = 4000

# 块级标签:这些标签结束后换行
_BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "table", "tr", "hr",
}

# 需要整体丢弃的标签(可能夹带脚本/样式/链接等内容)
_DROP_TAGS = {"script", "style", "noscript", "iframe", "object", "embed"}


def html_to_text(raw: str, max_len: int = MAX_LEN) -> str:
    """把一段 HTML 转成纯文本。

    - 输入为空/None 返回空串;
    - 剥离脚本/样式类标签,块级标签换行,代码块保留换行;
    - 反转义实体;按 max_len 截断(截断处尽量落在单词/字符边界)。
    """
    if not raw:
        return ""
    try:
        tree = lxml_html.fromstring(raw)
    except Exception:
        # 解析失败就退化为粗暴去标签(仍先剥 script/style)
        return _fallback_strip(raw, max_len)

    # 先去掉要丢弃的标签
    for tag in _DROP_TAGS:
        for el in tree.iter(tag):
            el.drop_tree()

    # 块级标签前后补换行,让代码块/段落保留结构
    for el in tree.iter():
        if el.tag in _BLOCK_TAGS:
            el.tail = ("\n" if not el.tail else el.tail)
            # 前置换行:文本内容前补一个换行(仅当尚无)
            if el.text is None:
                el.text = "\n"

    # <code> 行内片段两侧加空格,避免词粘连
    for el in tree.iter("code"):
        el.text = (el.text or "")
        el.tail = (" " + (el.tail or "") if el.tail else " ")

    text = tree.text_content()
    text = html.unescape(text)
    return _normalize(text, max_len)


def _fallback_strip(raw: str, max_len: int) -> str:
    """无 lxml 解析时兜底:去标签 + 反转义 + 规整。"""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", "\n", text)
    text = html.unescape(text)
    return _normalize(text, max_len)


def _normalize(text: str, max_len: int) -> str:
    """压掉连续空白/换行,截断到 max_len。"""
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = text.strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + " …"
    return text
