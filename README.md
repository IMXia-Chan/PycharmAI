# Python 代码助手(PyCharm 插件)

面向 Python 初学者的 AI 代码助手,采用**混合架构**:

- **Kotlin 插件**(`plugin/`)负责 IDE 内的一切交互:代码旁内联提示、快捷键、文件库窗口、Edge 搜索。
- **Python 后端**(`backend/`)是"AI 大脑":调用 DeepSeek 做错误检测、中文搜函数、函数对比、AI 笔记,并有内置规则兜底(无 API key 也能用基础提示)。
- **云端服务**(`server/`)是真云端文件库:把不规范代码记录和 AI 笔记持久化到服务器。

## 四个功能对应关系

| 需求 | 实现位置 |
|---|---|
| ① 记录不规范代码 + 云端文件库 + AI 笔记 | `backend` `/api/record` `/api/notes` + `server/` + 插件右侧「Python 代码助手」窗口 |
| ② 输入时后端搜常见错误 + 代码旁提示 | `backend` `/api/analyze` + 插件 `LiveIssueHintProvider` 内联 Inlay |
| ③ 中文描述函数 → 候选 + 定义 + 点击 Edge 搜索 | `backend` `/api/search-functions` + 插件 `SearchFunctionAction` |
| ④ 快捷键对比相似函数 + 差异说明 + 点击 Edge 搜索 | `backend` `/api/compare` + 插件 `CompareFunctionAction`(快捷键 `Ctrl+Alt+F`) |

## 目录结构

```
ai-code-assistant/
├── backend/            # Python AI 后端(FastAPI + DeepSeek)
│   ├── main.py         # 所有 API 端点
│   ├── ai.py           # DeepSeek 封装
│   ├── rules.py        # 内置常见错误规则(离线兜底)
│   ├── prompts.py      # 提示词
│   ├── models.py       # 数据模型
│   ├── config.py       # 配置
│   └── storage/        # 存储抽象(local / remote)
├── server/             # 真云端文件库(FastAPI + SQLite)
│   └── main.py
├── plugin/             # IntelliJ/PyCharm 插件(Kotlin)
│   └── src/main/kotlin/com/assistant/
└── .env.example        # 环境变量模板
```

## 环境要求

- **Python 3.10+**(你已有 3.14,OK)
- **后端**:`pip install -r backend/requirements.txt`
- **云端**:`pip install -r server/requirements.txt`
- **插件构建**:IntelliJ IDEA **Community 版(免费)** 或 JDK 17 + Gradle 8.5(插件不能在 PyCharm 里直接构建,但构建出的 jar 可以装进 PyCharm)

## 快速开始(先本地跑通)

### 第 1 步:配置 DeepSeek API Key

```powershell
copy D:\ai-code-assistant\.env.example D:\ai-code-assistant\backend\.env
```

编辑 `backend\.env`,填入你的 `DEEPSEEK_API_KEY`(在 https://platform.deepseek.com 申请)。
> 没有 key 也能先跑通:内置规则会让 ② 功能可用,但 ①③④ 的 AI 部分会降级/返回提示。

### 第 2 步:启动后端

```powershell
cd D:\ai-code-assistant\backend
pip install -r requirements.txt
python main.py        # 或: uvicorn main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000/health 看到 `{"status":"ok","ai":true,...}` 即成功。

### 第 3 步:构建并安装插件

1. 用 **IntelliJ IDEA Community** 打开 `D:\ai-code-assistant\plugin`(作为 Gradle 项目打开)。
2. 等待 Gradle 同步完成后,运行 `buildPlugin` 任务(Gradle 面板 → Tasks → build → buildPlugin)。
3. 产物在 `plugin\build\distributions\python-assistant-1.0.0.zip`。
4. 在 PyCharm 里:**Settings → Plugins → ⚙ → Install Plugin from Disk…**,选择该 zip 重启。

> 若想直接调试:在 IDEA 里运行 `runIde` 任务,会启动一个带插件的沙箱 IDE。

## 使用说明

- **输入时错误提示**:打开任意 `.py` 文件,输入代码后停顿约 1.2 秒,当前行若命中常见错误,会在行尾内联显示 `⚠ 问题 → 建议`。默认只查内置规则(快);后端收到 `deep=true` 才会追加 AI 深分析,可在 `BackendClient.kt` 里调整。
- **中文搜函数**:菜单 **Tools → 中文搜函数/指令**,输入中文描述 → 选择候选 → 双击或点「用 Edge 搜索」自动用 Edge 打开搜索。
- **对比函数**:菜单 **Tools → 对比函数/指令**(快捷键 `Ctrl+Alt+F`),填两个函数名 → 「开始对比」→ 逐项看差异,「Edge 搜 A / 搜 B」一键搜索。
- **文件库**:右侧工具窗口「Python 代码助手」→「刷新」加载云端记录与笔记;「生成 AI 笔记」让 AI 归纳最近的高频错误。

## 部署真云端(可选,实现多设备同步)

`backend` 默认不填 `CLOUD_URL` 时用本地 SQLite。要真正上云:

1. 把 `server\` 目录放到一台云服务器,复制 `server\.env.example` 为 `server\.env`,改一个强密码 `CLOUD_TOKEN`,然后:
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8001
   ```
2. 在本地 `backend\.env` 里填:
   ```
   CLOUD_URL=http://<服务器IP>:8001
   CLOUD_TOKEN=<与服务器一致的令牌>
   ```
3. 重启后端,`/health` 里 `cloud` 变 `true` 即打通。

> 生产环境建议给 `server` 套一层 HTTPS(如 Nginx + 证书),因为 `CLOUD_TOKEN` 目前是明文走 HTTP。

## 常见问题

- **插件提示"请求失败,请确认后端已启动"**:先确认 `python main.py` 在跑、端口 8000 未被占用;插件默认连 `http://127.0.0.1:8000`,可在 IDEA 沙箱里改(设置持久化于 `python-assistant.xml`)。
- **插件构建报错**:确认用 JDK 17、Gradle 8.x;`intellij` 插件首次会下载 ~1GB 的 IDEA 发行版。
- **Edge 没打开 / 打开的不是 Edge**:插件会按常见路径找 `msedge.exe`,找不到则回退默认浏览器;可把 Edge 加入 PATH。
- **换模型**:编辑 `backend\.env` 的 `DEEPSEEK_MODEL`(`deepseek-chat` 为 V3,`deepseek-reasoner` 为 R1 深度思考)。

## 关于"混合架构"的取舍(重要)

真正的内联提示/快捷键只能用 Kotlin 插件实现,因此选了混合架构:Python 负责所有"智能",Kotlin 只做薄薄的展示与交互。这带来一个代价——**插件需要 IntelliJ IDEA Community 来构建**(PyCharm 本身不带插件 DevKit)。如果觉得构建插件太重,`backend/` 完全可以独立使用:你仍可通过 HTTP 直接调用它的四个接口,或用任意脚本/网页调用。
