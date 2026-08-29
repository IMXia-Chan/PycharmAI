"""把学习笔记 + 深度分析导出成 PDF(fpdf2 + 中文字体)。

字体优先用 Windows 自带的 simhei.ttf;找不到则退回内置字体(中文会缺字,但不崩)。
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from fpdf import FPDF

_CJK_FONT = "C:/Windows/Fonts/simhei.ttf"
_PAGE_MARGIN = 16


def _strip_md(text: str) -> str:
    """把 Markdown 粗略转成纯文本,去掉代码围栏/粗体/标题等符号。"""
    text = re.sub(r"```[^\n]*\n?", "", text or "")
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"[*_#>]", "", text)
    return html.unescape(text)


def _lines(paragraphs: list[str]) -> list[str]:
    out: list[str] = []
    for p in paragraphs:
        for ln in _strip_md(p).splitlines():
            ln = ln.strip()
            if ln:
                out.append(ln)
    return out


def build_pdf(deep_analysis: str, notes: list[dict], records: list[dict], title: str = "Python 学习笔记") -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=_PAGE_MARGIN)
    pdf.set_margins(_PAGE_MARGIN, _PAGE_MARGIN, _PAGE_MARGIN)

    has_cjk = Path(_CJK_FONT).exists()
    if has_cjk:
        pdf.add_font("cjk", "", _CJK_FONT)
    font = "cjk" if has_cjk else "helvetica"

    def mc(h: float, txt: str):
        # new_x="LMARGIN":每次换行都把 x 回到左边距,避免 fpdf2 默认 new_x="RIGHT"
        # 让 x 卡在右边距,导致下一条 multi_cell 宽度算成 0 而报错。
        pdf.multi_cell(pdf.epw, h, txt, new_x="LMARGIN", new_y="NEXT")

    def heading(t: str, size: int = 14, gap: int = 6):
        pdf.set_font(font, "", size)
        pdf.set_text_color(30, 64, 175)
        mc(8, _strip_md(t))
        pdf.ln(gap)

    def body(lines_: list[str], size: int = 11, lh: float = 6.5):
        pdf.set_font(font, "", size)
        pdf.set_text_color(45, 45, 45)
        for ln in lines_:
            mc(lh, ln)
        pdf.ln(4)

    # 封面
    pdf.add_page()
    pdf.set_font(font, "", 22)
    pdf.set_text_color(30, 64, 175)
    mc(10, title)
    pdf.ln(2)
    pdf.set_font(font, "", 12)
    pdf.set_text_color(120, 120, 120)
    mc(6, "AI 深度分析 · 错误记录整理 · 自动生成")

    # 深度分析
    if deep_analysis.strip():
        pdf.add_page()
        heading("一、深度分析报告", 15)
        body(_lines([deep_analysis]))

    # AI 笔记
    if notes:
        pdf.add_page()
        heading("二、AI 学习笔记", 15)
        for n in notes:
            heading(n.get("title") or "学习笔记", 13, 4)
            body(_lines([n.get("content", "")]))

    # 错误记录
    if records:
        pdf.add_page()
        heading("三、错误记录明细", 15)
        for r in records:
            head = f"[{r.get('category')}/{r.get('severity')}] {r.get('title') or r.get('message')}"
            if r.get("filename"):
                head += f"  ({r['filename']}"
                head += f":{r['line']}" if r.get("line") else ""
                head += ")"
            pdf.set_font(font, "", 11)
            pdf.set_text_color(30, 64, 175)
            mc(7, _strip_md(head))
            if r.get("code"):
                pdf.set_font(font, "", 9.5)
                pdf.set_text_color(80, 80, 80)
                for ln in (r["code"] or "").splitlines():
                    if ln.strip():
                        mc(5.5, ln)
            pdf.ln(3)

    return bytes(pdf.output())


def build_markdown(deep_analysis: str, notes: list[dict], records: list[dict], title: str = "Python 学习笔记") -> str:
    """把学习笔记导出成 Markdown 文本(和 PDF 同源,方便在 Typora/VS Code 里看)。"""
    out: list[str] = ["# " + title, ""]

    if deep_analysis.strip():
        out += ["## 深度分析", "", deep_analysis.strip(), ""]

    if notes:
        out += ["## AI 学习笔记", ""]
        for n in notes:
            out.append(f"### {n.get('title') or '学习笔记'}")
            out.append("")
            out.append((n.get("content") or "").strip())
            out.append("")

    if records:
        out += ["## 错误记录明细", ""]
        for r in records:
            head = f"- [{r.get('category')}/{r.get('severity')}] {r.get('title') or r.get('message')}"
            if r.get("filename"):
                head += f" ({r['filename']}"
                head += f":{r['line']}" if r.get("line") else ""
                head += ")"
            out.append(head)
            if r.get("code"):
                out += ["", "```python", (r["code"] or "").strip(), "```", ""]
            else:
                out.append("")

    return "\n".join(out).strip() + "\n"
