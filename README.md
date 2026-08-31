# Python 代码助手（PyCharm 插件）

面向 Python 初学者的 AI 代码助手，采用**本地优先的混合架构**：

- **Kotlin 插件**（`plugin/`）：IDE 内的一切交互 —— 代码旁内联提示、快捷键、文件库窗口（记录 + 代码片段）。
- **Python 后端**（`backend/`）：AI 大脑 —— 调用 DeepSeek 做错误检测 / 中文搜函数 / 函数对比 / AI 问答 / 代码解释 / 自动修复等；并有内置规则兜底，无 API key 也能用基础提示。
- **云端服务**（`server/`，可选）：可选的多用户文件库 / 版本更新提示。**默认不使用**，数据存在本机。
- **本地报错知识库**（`error_knowledge_base/`）：纯本地双库（公共只读 + 个人增删改查）+ 自研 BM25 检索，配合 RAG 让 AI 回答报错问题时有真实案例可查。

## 功能一览

| 功能 | 快捷键 | 说明 |
|---|---|---|
| 输入时错误提示 | — | 输入后停顿约 1.2s，行尾内联显示 `⚠ 问题 → 建议` |
| 网页端 AI 深度搜索 | `Ctrl+Alt+A` | AI 问答 / 中文搜函数 / 学习笔记 / 函数对比 / 导出 PDF |
| 解释代码 | `Ctrl+Alt+E` | 用中文解释选中的代码 |
| 生成注释 | `Ctrl+Alt+G` | 给选中代码自动加中文注释 |
| 自动修复代码 | `Ctrl+Alt+R` | 找错误并自动修复 |
| 报错解释 | `Ctrl+Alt+X` | 粘贴运行时报错，AI 解释原因与改法 |
| 记录错误代码 | `Ctrl+Alt+N` | 把当前选中（或整个文件）记录到本地文件库 |
| 保存代码片段 | `Ctrl+Alt+K` | 把选中代码存进「文件库」，和错误记录一起上传网页 |
| 知识库搜索 | — | 搜本地知识库（公共/个人）的报错解决方案 |
| 重载知识库索引 | — | 灌库后点一下，让后端读到新数据（免重启） |

> 菜单入口在 PyCharm 的 **Tools** 菜单里；右键菜单也挂了部分项。

## 本地文件库 + 候选库

「记录错误代码 / 解释代码 / 报错解释 / 保存代码片段」的结果**存在插件本机**（`~/.python-assistant/library.json`），不自动发后端：

1. 右侧「**文件库**」窗口，一个列表同时显示错误记录（📄）和代码片段（📌），可多选、删除。
2. 把想上传的条目「**加入候选库**」，或直接拖进右侧候选库。
3. 点「**上传网页**」→ 错误记录和片段分别发到后端（错误记录进「错误记录」区、片段进「代码片段」区），成功后自动打开网页笔记页。
4. 在网页端把内容拖进「**文件库**」（候选库，最多 5 个），点「生成笔记」整理成学习笔记。

> 「本地文件库」和「网页文件库」是两回事：本地库是你在 IDE 里攒的原始记录，网页文件库是拖拽生成笔记的容器。

## 网页端工作台

浏览器打开的网页端（`/web`）有四个页签：AI 问答、中文搜索、学习笔记、函数对比。其中「学习笔记」页汇总三类内容：

- **AI 笔记**：点「生成 AI 笔记」根据错误记录自动整理，可删除、导出 PDF / Markdown。
- **错误记录**：按文件分组展示，**每条可单独删除**，也可**拖进文件库**生成笔记。
- **代码片段**：从插件「上传网页」的片段会出现在这里，**可删除**、**可拖进文件库**生成笔记。

把错误记录或代码片段拖进「文件库」（候选库）后点「生成笔记」，会按内容类型分别处理：

- **错误记录** → 用 AI 生成四部分讲解：❌ 错误代码原文、✅ 正确代码、💡 为什么错、🔁 举一反三。
- **代码片段** → **原样导出**（本地代码什么样，笔记里就是什么样，不经过 AI）。

生成的笔记可在文件库内「导出 PDF / Markdown」。

## 本地报错知识库（ErrorKnowledgeBase）

一个**纯本地、双库**的报错知识库，让 AI 回答报错问题时「有据可依」：

- **公共库**（只读）：从 Stack Overflow 爬取的报错 + 真实解决方案（CC BY-SA 4.0 署名）。
- **个人库**（增删改查）：你自己的报错记录。
- **检索内核**：自研 BM25 + 结巴分词 + 字段加权 + 布尔查询 + 高亮，索引 pickle 落盘、可重建。
- **RAG 增强**：`/api/chat`、`/api/explain-error`、`/api/fix` 三个端点会自动先检索知识库，把命中案例喂给 DeepSeek。

### 用法

| 入口 | 怎么用 |
|---|---|
| 主动搜索 | Tools → **知识库搜索…**，输入 `TypeError` 等关键词 |
| 重载索引 | Tools → **重载知识库索引**（灌库后点一下，免重启后端） |
| RAG 增强 | **报错解释** / **自动修复** 时自动携带知识库上下文 |

### 灌库（一次性，可选）

官方 ClickHouse 托管的 Stack Overflow Posts Parquet（按年、免账号、CC BY-SA 4.0）：

```bash
cd error_knowledge_base
pip install -r requirements.txt
python -m crawler.fill_public --year 2023 --limit 200000   # 下载→清洗→灌库→重建索引→搜索自检
```

> 数据与索引都在 `error_knowledge_base/data/`，已被 `.gitignore` 忽略、不入库。公共库只读、个人库可增删改查、纯本地无网络。

## 目录结构

```
ai-code-assistant/
├── backend/            # Python AI 后端（FastAPI + DeepSeek）
│   ├── main.py         # 所有 API 端点
│   ├── ai.py           # DeepSeek 封装
│   ├── rules.py        # 内置常见错误规则（离线兜底）
│   ├── prompts.py      # 提示词
│   ├── config.py       # 配置（存储模式、模型等）
│   ├── pdf_export.py   # PDF / Markdown 导出
│   ├── storage/        # 存储抽象（本地 SQLite / 远程云端）
│   └── web/            # 网页工作台（AI 问答、笔记、文件库、导出）
├── error_knowledge_base/  # 本地报错知识库（双库 + 自研检索内核）
│   ├── core/              # 数据模型 / 存储 / 分词 / BM25 检索
│   ├── crawler/           # Stack Exchange 爬虫 + 一键灌库
│   ├── data/              # 本地数据（.gitignore 忽略，不入库）
│   └── main.py            # 演示入口
├── server/             # 可选云端服务（多用户文件库 / 版本）
├── plugin/             # IntelliJ/PyCharm 插件（Kotlin）
└── .env.example        # 环境变量模板
```

## 环境要求

- **Python 3.10+**（3.14 可用）
- 后端依赖：`pip install -r backend/requirements.txt`
- 知识库依赖（仅灌库/爬虫需要）：`pip install -r error_knowledge_base/requirements.txt`
- 插件构建：IntelliJ IDEA + **Kotlin 2.3.20 + Gradle 9.6**（wrapper 已带）+ IntelliJ Platform Gradle 插件 2.18.1

## 快速开始（先本地跑通）

### 第 1 步：配置 DeepSeek API Key

```powershell
copy .env.example backend\.env
```

编辑 `backend\.env`，填入 `DEEPSEEK_API_KEY`（在 https://platform.deepseek.com 申请）。

> 没有 key 也能先跑通：内置规则让「输入时错误提示」可用，其余 AI 功能会降级 / 返回提示。

### 第 2 步：启动后端

在**仓库根目录**下：

```powershell
pip install -r backend\requirements.txt
python -m backend.main        # 或 uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

> 后端用了相对导入，必须从根目录用 `-m backend.main` 启动（直接 `python main.py` 会报错）。也可以直接双击根目录的 `启动后端.bat`。

打开 http://127.0.0.1:8000/health 看到 `{"status":"ok","ai":true,...}` 即成功。

### 第 3 步：构建并安装插件

1. 用 IntelliJ IDEA 打开 `plugin/`（作为 Gradle 项目）。
2. 运行 `buildPlugin` 任务（Gradle 面板 → Tasks → build → buildPlugin）。
3. 产物在 `plugin\build\distributions\python-assistant-1.1.0.zip`。
4. PyCharm → **Settings → Plugins → ⚙ → Install Plugin from Disk…**，选该 zip 重启。

> 构建需要 `JAVA_HOME` 指向 JDK（IDEA 自带的 `jbr` 目录即可）。
> `build.gradle.kts` 里用 `local(...)` 直接指向本机 IDEA 平台，以免下载 1GB 发行版；**换机器请把它改成你自己的 IDEA 路径**（或改用官方 `intellijPlatform { create(...) }` 下载方式）。

## 数据存储

**默认存本机**：`backend/.env` 的 `STORAGE_MODE=local`（默认值）时，记录 / 笔记 / 代码片段都存在本地 `assistant.db`。

只有把 `STORAGE_MODE=remote` 并填好 `CLOUD_URL`，才走云端同步（见下）。

## 部署真云端（可选）

1. 把 `server/` 放到一台云服务器，复制 `server\.env.example` 为 `server\.env`，把 `CLOUD_TOKEN` 改成随机长串：
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8001
   ```
2. 本地 `backend\.env` 填：
   ```
   CLOUD_URL=http://<服务器IP>:8001
   CLOUD_TOKEN=<与服务器一致的令牌>
   STORAGE_MODE=remote
   ```
3. 重启后端，`/health` 里 `cloud` 变 `true` 即打通。

> 生产环境建议给 `server` 套 HTTPS（如 Nginx + 证书），因为 `CLOUD_TOKEN` 目前明文走 HTTP。

## 常见问题

- **插件提示「请求失败，请确认后端已启动」**：先确认后端在跑、端口 8000 未被占用；插件默认连 `http://127.0.0.1:8000`。
- **构建报错「JAVA_HOME 未设置」**：设 `JAVA_HOME` 指向 JDK（IDEA 的 `jbr` 目录）。
- **同名版本 zip 装不上 / 不覆盖**：先卸载旧插件，或把 `build.gradle.kts` 的 `version` 升一下。
- **AI 功能全部失效**：先看 `backend.err.log`，若提示 `api key ... is invalid`，是 DeepSeek key 失效了（去官网确认余额 > 0、只保留一个有效 key），不是代码 bug。
- **Edge 没打开**：插件按常见路径找 `msedge.exe`，找不到则回退默认浏览器。
- **换模型**：编辑 `backend\.env` 的 `DEEPSEEK_MODEL`（`deepseek-chat` 为 V3，`deepseek-reasoner` 为 R1 深度思考）。

## 关于「混合架构」的取舍

真正的内联提示 / 快捷键只能用 Kotlin 插件实现，所以选了混合架构：Python 负责所有「智能」，Kotlin 只做薄薄的展示与交互。代价是**插件需要 IntelliJ IDEA 来构建**（PyCharm 本身不带插件 DevKit）。如果觉得构建插件太重，`backend/` 完全可以独立使用：你可以直接 HTTP 调它的接口，或用任意脚本 / 网页调用。

## 许可

[MIT](LICENSE)
