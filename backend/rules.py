"""内置的常见 Python 错误/不规范规则(离线兜底,不依赖 AI)。

即使没有配置 DEEPSEEK_API_KEY,也能用这些规则给出基础提示。
规则用正则做启发式匹配,覆盖初学者最常见的几类问题。
"""
from __future__ import annotations

import re

# 每个规则:pattern / category / severity / title / message / suggestion
_RULES: list[dict] = []


def _rule(pattern: str, category: str, severity: str, title: str, message: str, suggestion: str) -> None:
    _RULES.append({
        "pattern": re.compile(pattern),
        "category": category,
        "severity": severity,
        "title": title,
        "message": message,
        "suggestion": suggestion,
    })


# 1. 条件判断里误用赋值 = 而不是 ==
_rule(r"\b(if|elif|while)\s+\w+\s*=[^=]", "error", "error",
      "条件判断里误用了赋值 `=`",
      "条件判断中应使用比较 `==`,把 `=` 改成 `==`。",
      "把 `=` 改成 `==`。")

# 2. 可变默认参数(空列表)
_rule(r"def\s+\w+\([^)]*=\s*\[\]", "nonstandard", "warning",
      "默认参数使用了可变对象(空列表)",
      "空列表作为默认参数会被所有调用共享,导致意外的状态累积。",
      "改成 `arg=None`,在函数体内再 `arg = []`。")

# 3. 可变默认参数(空字典)
_rule(r"def\s+\w+\([^)]*=\s*\{\}", "nonstandard", "warning",
      "默认参数使用了可变对象(空字典)",
      "空字典作为默认参数会被所有调用共享,导致意外的状态累积。",
      "改成 `arg=None`,在函数体内再 `arg = {}`。")

# 4. 用 is 比较字面量 True/False
_rule(r"\b\w+\s+is\s+(True|False)\b", "nonstandard", "warning",
      "用 `is` 比较 True/False",
      "`is` 比较的是身份(同一对象),应使用 `==` 比较布尔值;只有 None 才用 `is`。",
      "把 `is` 改成 `==`(与 None 比较时保留 `is`)。")

# 5. 用 == 比较 None
_rule(r"\b\w+\s*==\s*None\b", "nonstandard", "warning",
      "用 `==` 比较 None",
      "与 None 比较应使用 `is`,而不是 `==`。",
      "把 `== None` 改成 `is None`。")

# 6. 裸 except(吞掉所有异常)
_rule(r"\bexcept\s*:", "nonstandard", "warning",
      "使用了裸 `except:`",
      "裸 `except:` 会捕获所有异常(包括 KeyboardInterrupt),掩盖真实错误。",
      "改为捕获具体异常,如 `except ValueError:`。")

# 7. Python2 风格的 print 语句
_rule(r"\bprint\s+\"[^\"]*\"\s*$|\bprint\s+'[^']*'\s*$", "error", "error",
      "Python2 风格的 print 语句",
      "`print \"xx\"` 在 Python3 中是语法错误。",
      "改为 `print(\"xx\")`。")

# 8. range(len(...)) 遍历(应使用 enumerate)
_rule(r"\bfor\s+\w+\s+in\s+range\s*\(\s*len\s*\(", "nonstandard", "info",
      "用 range(len(...)) 遍历",
      "这种写法不够 Pythonic,可以用 enumerate 同时拿到下标和元素。",
      "改用 `for i, item in enumerate(seq):`。")

# 9. 比较链写成了多次比较(如 a < b < c 拆开无影响,跳过;改为检查 not in 写法)
_rule(r"\bif\s+not\s+\w+\s+in\b", "nonstandard", "info",
      "`not x in` 写法",
      "`not x in y` 可读性差,推荐 `x not in y`。",
      "改写为 `if x not in y:`。")


def check_code(code: str) -> list[dict]:
    """对代码做规则检查,返回与 Issue 结构一致的 dict 列表。"""
    issues: list[dict] = []
    for line_no, line in enumerate(code.splitlines(), start=1):
        for r in _RULES:
            if r["pattern"].search(line):
                issues.append({
                    "category": r["category"],
                    "title": r["title"],
                    "message": f"第 {line_no} 行:{r['message']}",
                    "suggestion": r["suggestion"],
                    "severity": r["severity"],
                    "line": line_no,
                })
    return issues
