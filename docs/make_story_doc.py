# -*- coding: utf-8 -*-
"""生成《从 0 到 1 开发全记录》的 Markdown 与 PDF（对外公开版）。

一份内容源，同时输出 .md 和 .pdf，保证两者一致。
技术细节尽量挖到底(编码/数据/缓存等通用工程坑)，但不含任何可攻击内容:
接口路径 / 认证头 / 令牌机制 / 密钥 / 真实本机路径 / 端口 / 爬虫实现。
"""
import os
from fpdf import FPDF

_BASE = os.path.dirname(os.path.abspath(__file__))
FONT = "C:/Windows/Fonts/simhei.ttf"  # Windows 中文字体(其他系统换成对应字体)
MD_OUT = os.path.join(_BASE, "从0到1开发手记.md")
PDF_OUT = os.path.join(_BASE, "从0到1开发手记.pdf")

TITLE = "Python 代码助手 · 从 0 到 1 开发全记录"
SUBTITLE = "一个 Python 初学者给自己写的 AI 助教"

# ---------------------------------------------------------------- 内容
C = []
def h1(t): C.append(("h1", t))
def h2(t): C.append(("h2", t))
def h3(t): C.append(("h3", t))
def p(t): C.append(("p", t))
def b(t): C.append(("bullet", t))
def code(t): C.append(("code", t))
def table(hdr, rows): C.append(("table", hdr, rows))

# ===== 一、缘起 =====
h1("一、缘起：为什么给自己写一个 AI 助教")
p("事情的起点很朴素：一个正在学 Python 的人，几乎每天都卡在同样几件事上——报错看不懂、别人的代码读不懂、"
  "注释懒得写、学过的东西转头就忘。市面上虽有不少 AI 编程助手，但要么必须联网上传、要么不是为初学者设计、"
  "要么数据不在自己手里。")
p("于是萌生一个念头：能不能给自己做一个「装在 IDE 里、随叫随到、数据留在本机」的 AI 助教？目标因此定得很具体——"
  "一个 PyCharm 插件，能即时纠错、能解释代码、能把每一次报错沉淀成学习笔记，而且敏感信息不出自己的电脑。")
b("报错信息又长又全是英文，初学者根本看不懂")
b("看别人的代码，不知道每一行到底在干什么")
b("想整理学习笔记，却没有趁手、能自动归纳的工具")
b("不希望自己的代码和笔记被传到别人家的服务器")

# ===== 二、总体思路与技术选型 =====
h1("二、总体思路与技术选型")
h2("2.1 为什么是「三层混合架构」")
p("一个关键判断：IDE 里的交互（菜单、快捷键、行内提示）只能用 Kotlin 写插件才能实现；而「智能」——调大模型、"
  "做检索、导出文件——用 Python 写最顺手。于是定下清晰的三层结构：")
b("交互层：Kotlin 插件 + 网页工作台，负责「你点哪里、看什么结果」")
b("服务层：本机运行的 Python 服务，负责调度模型、读写数据、内置规则兜底")
b("智能层：大语言模型（DeepSeek），负责真正的理解与生成")
p("三者只在本机之间通信，个人数据不离开自己的电脑，这是贯穿始终的一条底线。")
h2("2.2 两个关键取舍")
b("本地优先：不依赖任何远程服务器，密钥自己填、自己管，数据只存本机")
b("混合语言：Python 包下所有「智能」，Kotlin 只做薄薄的展示层——代价是插件得用 IDEA 构建，好处是后端可以独立复用")

# ===== 三、一步步怎么搞出来的 =====
h1("三、一步步怎么搞出来的")
h2("3.1 后端骨架：先让「智能」跑起来")
p("第一步不碰插件，先把后端写出来。用一个轻量 Web 框架把大模型调用封装成统一入口，同时内置了一套「常见错误规则」"
  "做离线兜底——这样哪怕还没配密钥，也能给出基础的纠错提示，不会「一没网就全哑火」。")
h2("3.2 第一个插件动作：从「解释代码」切入")
p("插件侧从最简单的功能破冰：选中一段代码，右键点「解释代码」，弹窗显示中文解释。这一步把「插件 → 发请求 → 展示结果」"
  "整条链路打通，后面所有功能（生成注释、自动修复、报错解释……）都是在这个模板上复制粘贴、换提示词而已。")
h2("3.3 输入时的内联纠错")
p("接着做最有「助教感」的功能：输入停顿约一秒后，在代码行尾内联提示「问题 → 建议」。它由内置规则和模型分析共同完成，"
  "所以离线时也能报基础错误，联网时更聪明。")
h2("3.4 插件与后端自动联动")
p("为了让体验顺滑，做了「启动插件时自动拉起本地后端，并用健康检查确认就绪」。用户装完插件直接能用，不必再手动开命令行。")
h2("3.5 网页工作台")
p("有些操作（连续问答、整理笔记）在更大的画布上更舒服，于是加了一个网页工作台，和插件共享同一份本地数据，"
  "适合静下心来慢慢整理。")
h2("3.6 本地文件库与学习笔记")
p("把「记录错误代码」「保存代码片段」沉淀到本地文件库，再让 AI 把错误记录整理成结构化笔记——"
  "「错误代码 / 正确代码 / 为什么错 / 举一反三」四段式，可导出 PDF / Markdown 供复习。")
h2("3.7 报错知识库：让 AI「有据可依」")
p("通用大模型回答报错问题时容易空泛。于是做了本地报错知识库：双库设计（公共只读 + 个人增删改查），"
  "再配一个自研检索内核（关键词加权检索 + 分词 + 字段加权 + 高亮）。")
h2("3.8 RAG 检索增强")
p("把知识库接进 AI 回答链路：报错解释、自动修复等场景，先检索本地知识库，把命中的真实案例作为参考喂给模型，"
  "让回答既有通用能力、又有真实案例的支撑。")
h2("3.9 灌库：从 0 到上万条")
p("用公开的社区问答数据做了一次批量导入，把公共库从零灌到上万条，并完成索引构建与搜索自检。这一步踩的坑最多，"
  "详见下一章。")
h2("3.10 1.1.0 大版本与发布")
p("加上「知识库搜索」「一键重载索引」两个入口，版本升到 1.1.0，构建插件包、写好说明文档、推上代码托管平台，"
  "并做了一次彻底的安全清理（密钥、内部实现细节一个不留）。")

# ===== 四、Bug 与 Debug 实录 =====
h1("四、Bug 与 Debug 实录（最有意思的一章）")
p("下面按「现象 → 定位 → 根因 → 修复 → 教训」的顺序，把这一路踩过的坑原样记录下来。"
  "它们大多不是多玄乎的 bug，而是非常典型的工程陷阱——编码、类型、缓存、导入规则。")

h2("4.1 中文跨协议传递乱码")
b("现象：需要跨系统传递的中文字段，服务端收到的却是乱码或空串。")
b("定位：这类通道（比如 HTTP 头）只允许 ASCII 字符，中文直接塞进去会被环境截断或打乱。")
b("根因：字节流通道没有统一的非 ASCII 编码约定，中文字符不是合法内容。")
b("修复：把中文字段先做 Base64 编码再传递，接收方再解码还原。")
code("中文 '张三' → Base64 → 可安全通过 ASCII 通道 → 解码回 '张三'")
b("教训：凡是「中文/非 ASCII 要跨协议传」的地方，先想清楚编码，别指望通道帮你处理。")

h2("4.2 灌库报「tzdata 缺失」")
b("现象：跑灌库脚本时，程序直接抛出异常：")
code("ArrowInvalid: The zoneinfo module or pytz package must be installed")
b("定位：报错来自时间戳解析——数据里的「创建时间」是带时区的时间戳。")
b("根因：Windows 系统没有自带的时区数据库；而 Python 在 Windows 上解析带时区的时间，需要 tzdata 这个包提供时区数据。")
b("修复：把 tzdata 加进依赖清单，重新安装即可。")
b("教训：典型的跨平台坑——同样的代码在 Linux 上没事，换到 Windows 就缺系统时区库。环境差异，先看报错里的线索。")

h2("4.3 parquet 的文本列是 bytes 不是 str（最隐蔽的一个）")
b("现象：灌库脚本跑完了，日志显示一切正常，结果却解析出 0 条记录——可数据里明明有几万行。")
b("定位：先别猜，直接看数据本身的「结构」（schema），发现文本列的类型是 binary（字节），不是 string；"
  "再打印一条值，看到的是 b'12345' 这种带 b 前缀的东西。")
b("根因：把 bytes 直接套 str()，得到的是 \"b'12345'\"，永远不可能和字符串 ID \"12345\" 相等，"
  "于是后续筛选全部落空、静默地一条都不剩。")
code("str(b'12345')  ->  \"b'12345'\"   ← 永远不等于 '12345'\n正确做法：b'12345'.decode('utf-8')  ->  '12345'")
b("修复：在数据管道里统一做 bytes → str 解码（decode utf-8，出错则替换）。")
b("教训：数据工程里最坑的不是「值不对」，而是「类型对不上」——它不报错，只让你得到 0 条结果。先看 schema、再采样值。")

h2("4.4 标签分隔符踩坑")
b("现象：标签字段解析出来是空的，或者格式怪异。")
b("定位：原以为标签是尖括号格式，实际采样一看，是竖线分隔。")
code("实际：|python|django|flask|   (竖线分隔)\n以为：<python><django>   (尖括号)")
b("根因：数据源的真实格式和预期不同。")
b("修复：改成按竖线拆分并清理空串，同时保留尖括号格式作为兜底。")
b("教训：永远不要假设数据格式，先抽几条真实数据看清楚再动手。")

h2("4.5 灌库后搜不到新数据（缓存单例的锅）")
b("现象：灌库明明成功、数据文件也更新了，但搜索出来的还是旧结果。")
b("定位：怀疑索引被缓存了——检查发现检索索引被做成了「模块级单例」，进程启动时加载一次后就不再读盘。")
b("根因：为了省掉重复加载的时间做了缓存，却忘了「数据是会变的」。")
b("修复：加一个「重载索引」的一键入口，让它重新从磁盘加载最新数据，免去重启进程的麻烦。")
b("教训：缓存一定要想清楚失效时机。「只加载一次」的优化，往往埋下「永远看不到更新」的雷。")

h2("4.6 接口报「缺 count 方法」")
b("现象：新加的统计功能一调用就抛异常：")
code("AttributeError: 'PrivateDatabase' object has no attribute 'count'")
b("定位：报错已经把话说得很清楚了——某个数据访问对象没有 count 这个方法。")
b("根因：给上层加了统计能力，却忘了给底层的数据访问类补上对应的实现。")
b("修复：补上 count() 实现，再测一遍。")
b("教训：改上层之前先想想下层有没有对应的能力。这类报错其实最友好——它把缺什么说得明明白白。")

h2("4.7 启动方式踩坑：相对导入")
b("现象：直接运行某个入口文件，报导入错误，找不到模块。")
b("根因：代码里用了相对导入，相对导入只认「作为模块运行」的方式，不认「直接运行脚本文件」的方式。")
b("修复：统一改成「作为模块启动」的方式，并写了一个一键启动脚本。")
code("python -m 包名.模块名    ← 正确\npython 模块名.py        ← 相对导入会报错")
b("教训：Python 的包导入规则——只要用相对导入，就必须「作为模块」运行，这是绕不过去的。")

# ===== 五、产品详细介绍 =====
h1("五、产品详细介绍")
h2("5.1 产品定位")
p("「Python 代码助手」是一款面向 Python 初学者与自学者的智能编程辅助插件，运行于 PyCharm 与 IntelliJ 平台。"
  "它把编程学习中最高频、最耗时的几类任务——读懂代码、写出规范代码、排查运行报错、沉淀学习笔记——统一交给大模型在本地完成。")
h2("5.2 目标用户")
b("Python 初学者 / 自学者：需要即时解释、即时纠错")
b("在校学生：需要把零散报错整理成可复习的笔记")
b("需要快速排查报错的开发者：一键看懂报错、一键得到修复建议")
h2("5.3 核心功能")
table(
    ["功能", "说明"],
    [
        ["输入时错误提示", "输入停顿后行内提示「问题 → 建议」，规则 + 模型共同完成"],
        ["解释代码", "用中文把选中代码「在做什么」讲清楚"],
        ["生成注释", "为选中代码自动补充逐行中文注释"],
        ["自动修复", "找出错误并给出修复后的代码"],
        ["报错解释", "粘贴运行时报错，解释原因与改法"],
        ["AI 问答 / 中文搜函数", "直接提问，或用中文关键词查函数与用法"],
        ["本地文件库", "记录错误代码、保存代码片段，一键整理成学习笔记"],
        ["学习笔记导出", "AI 生成四段式笔记，导出 PDF / Markdown"],
        ["网页工作台", "更大画布上集中做问答、笔记、函数对比"],
        ["报错知识库", "本地双库 + 检索，让 AI 回答报错有据可依"],
    ],
)
h2("5.4 报错知识库（亮点）")
p("通用大模型回答报错问题时容易「看似合理实则空泛」。本产品的报错知识库解决了这个问题：")
b("双库设计：公共库（只读，社区公开案例）+ 个人库（增删改查，只属于自己）")
b("检索增强（RAG）：回答报错类问题前，先在本地检索最相关的历史案例，作为参考一并交给模型")
b("一键扩充：支持从公开数据源批量导入高质量报错解决方案，一条命令完成下载、清洗、入库、索引、自检")
b("全程本地：检索与问答都在本机完成，结果不离开设备")
h2("5.5 安全与隐私")
b("数据本地化：笔记、记录、片段、知识库数据全部存本机，不上传云端")
b("密钥自理：AI 能力通过使用者自己的密钥调用，系统不代管、不收集")
b("最小暴露：本机服务只面向使用者本人，对外不提供访问入口")
h2("5.6 快速上手")
b("第一步：安装插件（从本地文件安装插件包，重启 IDE）")
b("第二步：填入自己的 AI 密钥（一次即可，保存在本机）")
b("第三步：选中代码用右键菜单或快捷键发起「解释 / 注释 / 修复 / 报错解释」，或打开网页工作台")
b("进阶：执行一次数据扩充命令，让 AI 回答报错时自动带上知识库参考")
h2("5.7 系统要求")
table(
    ["项目", "要求"],
    [
        ["运行环境", "PyCharm / IntelliJ IDEA（较新版本）"],
        ["本地服务", "Python 3.10 及以上"],
        ["AI 能力", "使用者自备大模型服务密钥（按需）"],
        ["联网", "核心 AI 功能需联网；基础规则检测可离线"],
    ],
)

# ===== 六、回顾与展望 =====
h1("六、回顾与展望")
p("回头看，这个项目最大的收获不是某一行代码，而是完整走通了一条「从想法到可用产品」的路：定需求 → 选架构 → "
  "先打通最小链路 → 一个功能一个功能往上加 → 踩坑、定位、修复 → 发布、做安全收尾。")
p("下一步还能往几个方向走：扩充更多知识库数据、把可选的多用户云端服务真正部署起来、让插件的交互更顺手。"
  "但无论往哪走，「本地优先、密钥自理、数据不出本机」这三条底线，值得一直守住。")

# ---------------------------------------------------------------- 渲染
class Doc(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)
        self.add_font("cjk", "", FONT)

    def _mc(self, h, txt):
        self.multi_cell(self.epw, h, txt, new_x="LMARGIN", new_y="NEXT")

    def h1(self, t):
        self.ln(4); self.set_font("cjk", "", 16); self.set_text_color(30, 64, 175)
        self._mc(8, t); self.ln(1)
        self.set_draw_color(30, 64, 175)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y()); self.ln(4)

    def h2(self, t):
        self.ln(3); self.set_font("cjk", "", 13); self.set_text_color(30, 64, 175); self._mc(7, t); self.ln(2)

    def h3(self, t):
        self.ln(2); self.set_font("cjk", "", 11.5); self.set_text_color(70, 70, 70); self._mc(6.5, t); self.ln(1.5)

    def p(self, t):
        self.set_font("cjk", "", 10.5); self.set_text_color(45, 45, 45); self._mc(6, t); self.ln(1.5)

    def bullet(self, t):
        self.set_font("cjk", "", 10.5); self.set_text_color(45, 45, 45)
        self.set_x(self.l_margin + 5)
        self.multi_cell(self.epw - 5, 6, "·  " + t, new_x="LMARGIN", new_y="NEXT"); self.ln(0.8)

    def code(self, t):
        self.set_font("cjk", "", 9); self.set_text_color(50, 50, 50)
        for line in t.splitlines():
            self.set_x(self.l_margin + 4)
            self.multi_cell(self.epw - 8, 5.3, line if line else " ", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def _wrap(self, w, t):
        return self.multi_cell(w, 5.3, str(t), output="LINES")

    def table(self, hdr, rows):
        self.set_font("cjk", "", 9); lh = 5.3; pad = 2
        widths = [46, 150] if len(hdr) == 2 else [60, 60, 76]

        def draw(cells, head):
            wrapped = [self._wrap(w, c) for w, c in zip(widths, cells)]
            rh = max(len(x) for x in wrapped) * lh + pad * 2
            if self.get_y() + rh > self.h - self.b_margin:
                self.add_page()
            y0 = self.get_y(); x = self.l_margin
            for i, (w, c) in enumerate(zip(widths, cells)):
                self.set_xy(x, y0)
                if head:
                    self.set_fill_color(232, 238, 248); self.set_text_color(30, 64, 175)
                else:
                    self.set_fill_color(255, 255, 255); self.set_text_color(45, 45, 45)
                self.multi_cell(w, lh, str(c), border=1, new_x="RIGHT", new_y="TOP", fill=head)
                x += w
            self.set_y(y0 + rh)

        draw(hdr, True)
        for r in rows:
            draw(r, False)
        self.ln(3)


def render_md(blocks):
    out = []
    out.append("# " + TITLE)
    out.append("")
    out.append("> " + SUBTITLE)
    out.append("")
    out.append("公开版 · 不含密钥与内部实现细节")
    out.append("")
    for blk in blocks:
        k = blk[0]
        if k == "h1":
            out.append("## " + blk[1])
        elif k == "h2":
            out.append("### " + blk[1])
        elif k == "h3":
            out.append("#### " + blk[1])
        elif k == "p":
            out.append(blk[1])
        elif k == "bullet":
            out.append("- " + blk[1])
        elif k == "code":
            out.append("```")
            out.append(blk[1])
            out.append("```")
        elif k == "table":
            hdr, rows = blk[1], blk[2]
            out.append("| " + " | ".join(hdr) + " |")
            out.append("|" + "---|" * len(hdr))
            for r in rows:
                out.append("| " + " | ".join(r) + " |")
        out.append("")
    return "\n".join(out)


def render_pdf(blocks):
    d = Doc()
    # 封面
    d.add_page()
    d.set_font("cjk", "", 23); d.set_text_color(30, 64, 175); d.ln(10)
    d._mc(12, TITLE); d.ln(3)
    d.set_font("cjk", "", 14); d.set_text_color(90, 90, 90); d._mc(8, SUBTITLE); d.ln(4)
    d.set_font("cjk", "", 11); d.set_text_color(120, 120, 120)
    d._mc(6, "开发全记录 · 公开版"); d.ln(8)
    d._mc(6, "版本：1.1.0"); d._mc(6, "日期：2026-08-31"); d._mc(6, "密级：公开")
    d.add_page()
    for blk in blocks:
        k = blk[0]
        if k == "h1":
            d.h1(blk[1])
        elif k == "h2":
            d.h2(blk[1])
        elif k == "h3":
            d.h3(blk[1])
        elif k == "p":
            d.p(blk[1])
        elif k == "bullet":
            d.bullet(blk[1])
        elif k == "code":
            d.code(blk[1])
        elif k == "table":
            d.table(blk[1], blk[2])
    return d


md_text = render_md(C)
with open(MD_OUT, "w", encoding="utf-8") as f:
    f.write(md_text)

pdf = render_pdf(C)
pdf.output(PDF_OUT)

print("Markdown ->", MD_OUT, "(" + str(len(md_text)) + " 字符)")
print("PDF      ->", PDF_OUT, "(" + str(round(os.path.getsize(PDF_OUT) / 1024)) + " KB)")
