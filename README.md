# Python 代码助手（PyCharm 插件）

面向 Python 初学者的 AI 代码助手，采用**本地优先的混合架构**：

- **Kotlin 插件**（`plugin/`）：IDE 内的一切交互 —— 代码旁内联提示、快捷键、文件库窗口（记录 + 代码片段）。
- **Python 后端**（`backend/`）：AI 大脑 —— 调用 DeepSeek 做错误检测 / 中文搜函数 / 函数对比 / AI 问答 / 代码解释 / 自动修复等；并有内置规则兜底，无 API key 也能用基础提示。
- **本地报错知识库**（`error_knowledge_base/`）：纯本地双库（公共只读 + 个人增删改查）+ 自研检索，配合 RAG 让 AI 回答报错问题时有真实案例可查。
- **云端服务**（`server/`，可选）：可选的多用户文件库。**默认不使用**，数据存在本机。

## 功能一览

| 功能 | 快捷键 | 说明 |
|---|---|---|
| 输入时错误提示 | — | 输入后停顿片刻，行尾内联显示 `⚠ 问题 → 建议` |
| 网页端 AI 深度搜索 | `Ctrl+Alt+A` | AI 问答 / 中文搜函数 / 学习笔记 / 函数对比 / 导出 PDF |
| 解释代码 | `Ctrl+Alt+E` | 用中文解释选中的代码 |
| 生成注释 | `Ctrl+Alt+G` | 给选中代码自动加中文注释 |
| 自动修复代码 | `Ctrl+Alt+R` | 找错误并自动修复 |
| 报错解释 | `Ctrl+Alt+X` | 粘贴运行时报错，AI 解释原因与改法 |
| 记录错误代码 | `Ctrl+Alt+N` | 把当前选中（或整个文件）记录到本地文件库 |
| 保存代码片段 | `Ctrl+Alt+K` | 把选中代码存进「文件库」 |
| 知识库搜索 | — | 搜本地知识库（公共/个人）的报错解决方案 |
| 重载知识库索引 | — | 灌库后点一下，让后端读到新数据（免重启） |

> 菜单入口在 PyCharm 的 **Tools** 菜单里；右键菜单也挂了部分项。

## 本地报错知识库

一个**纯本地、双库**的报错知识库，让 AI 回答报错问题时「有据可依」：

- **公共库**（只读）：从 Stack Overflow 爬取的报错 + 真实解决方案（CC BY-SA 4.0 署名）。
- **个人库**（增删改查）：你自己的报错记录。
- **检索**：自研 BM25 + 结巴分词 + 字段加权 + 布尔查询 + 高亮，索引落盘、可重建；并有多语言向量检索兜底，中文关键词也能命中英文库。
- **RAG 增强**：问答 / 报错解释 / 自动修复时，会自动先检索知识库，把命中的真实案例作为上下文喂给 AI。

> 公共库数据来自 Stack Overflow（CC BY-SA 4.0），可通过项目自带的爬虫脚本灌入；数据与索引都在 `error_knowledge_base/data/`，已被 `.gitignore` 忽略、不入库。

## 快速开始（先本地跑通）

### 第 1 步：配置 API key

复制配置模板（`.env.example`）为后端目录下的配置文件，填入你自己的 DeepSeek API key；也可以先不填，等插件首次启动时在弹出的「接入你的 API」窗口里填。

> 没有 key 也能先跑通：内置规则让「输入时错误提示」可用，其余 AI 功能会降级 / 返回提示。

### 第 2 步：启动后端

安装依赖（见「环境要求」）后，运行仓库根目录的启动脚本（`启动后端.bat`），或手动 `python -m backend.main`。

### 第 3 步：构建并安装插件

1. 用 IntelliJ IDEA 打开 `plugin/`（作为 Gradle 项目）。
2. 运行 `buildPlugin` 任务（Gradle 面板 → Tasks → build → buildPlugin）。
3. 产物在 `plugin/build/distributions/` 下，用 PyCharm 的「Settings → Plugins → ⚙ → Install Plugin from Disk…」安装并重启。

> 构建需要 `JAVA_HOME` 指向 JDK（IDEA 自带的 `jbr` 目录即可）。

## 数据与隐私

- **默认本地优先**：记录 / 笔记 / 代码片段都存本机，不上传。
- 云端同步是**可选的独立功能**，默认关闭。

## 目录结构

```
ai-code-assistant/
├── backend/              # Python AI 后端（FastAPI + DeepSeek）
├── error_knowledge_base/ # 本地报错知识库（双库 + 自研检索）
│   ├── core/             # 数据模型 / 存储 / 分词 / 检索
│   ├── crawler/          # 数据爬虫 + 一键灌库
│   ├── tools/            # 数据归档等维护脚本
│   └── data/             # 本地数据（.gitignore 忽略，不入库）
├── server/               # 可选云端服务（多用户文件库）
├── plugin/               # IntelliJ/PyCharm 插件（Kotlin）
└── .env.example          # 配置模板
```

## 环境要求

- **Python 3.10+**（3.14 可用）
- 后端依赖：`pip install -r backend/requirements.txt`
- 知识库依赖（仅灌库/爬虫需要）：`pip install -r error_knowledge_base/requirements.txt`
- 插件构建：IntelliJ IDEA + Kotlin + Gradle（wrapper 已带）

## 关于「混合架构」的取舍

真正的内联提示 / 快捷键只能用 Kotlin 插件实现，所以选了混合架构：Python 负责所有「智能」，Kotlin 只做薄薄的展示与交互。代价是**插件需要 IntelliJ IDEA 来构建**（PyCharm 本身不带插件 DevKit）。如果觉得构建插件太重，`backend/` 也可以独立使用。

## 许可

[MIT](LICENSE)
