# magic class 课堂 UI 移植 — 交接文档

本目录是**唯一有效的交接说明**。接手方（人或 AI）读这一个目录就够了，不需要任何
先前会话记录。

## 怎么用

1. 先读本文件（README）拿到全局。
2. 然后按需读下面五个主题文档。
3. 开始干活前，**必读** `01-约束.md` 与 `04-陷阱.md`——这两份能省你几小时。
4. 要复制给 Codex / GPT 的提示词在 `PROMPT.md`。

## 参考项目在哪（`$REF`）

本目录用 **`$REF`** 指代参考项目根目录：magic class v1.0.x 源码
（Next.js 16 / React 19 / TypeScript / Tailwind 4），**只读**。

该路径属于**本机路径**，按仓库规则（`AGENTS.md`：禁止在共享文件中写入盘符与本机路径）
**不写进本目录**。取值方式二选一：

- 见 `PROMPT.md` 开头的占位符（使用者粘贴前填入）；
- 或直接问使用者。

本目录里所有路径都相对于**仓库根目录**，命令也一律从仓库根目录执行。

## 文档索引

| 文件 | 内容 | 什么时候读 |
| --- | --- | --- |
| `PROMPT.md` | 给 AI 的启动提示词 | 复制粘贴用 |
| `01-约束.md` | 架构边界与红线（违反等于白做） | **动手前必读** |
| `02-现状.md` | 已完成清单、移植层索引、关键文件 | 想改某处之前 |
| `03-待办.md` | 剩余工作与切片计划 | 决定做什么之前 |
| `04-陷阱.md` | 已踩过的坑（12 条） | **动手前必读** |
| `05-工程规范.md` | 测试 / 验收 / 提交 / 交付 | 写代码与交付时 |
| `06-参考实现地图.md` | 参考项目怎么找文件、哪些目录对应什么 | 找参考实现时 |
| `PROGRESS.md` | **进度账本**：切片状态、提交号、下一步 | 每次开工与收工时**必更新** |

> `PROGRESS.md` 是执行者跨上下文存活的唯一凭据。上下文被截断或会话被重开之后，
> 从它继续，不要从零重来。

## 一句话现状

**完整迁移仍为部分完成**：「我的课程 → 进入课堂」现在直接进入学习态，左侧场景栏
带真实幻灯片缩略图，中间是真实的 16:9 幻灯片 / 测验 / 互动 / 项目式学习，底部是参考
项目那条 192px 圆桌面板（能真跑多智能体讨论）。

**剩下的**包括「工作台编辑器」（现在还是 JSON 文本框）、版式与课堂行为，
以及模板后台的 PBL 工作区、实时会话、学习记录、媒体与资源等运行时闭环。
用户已明确要求前后端完整迁入，不能把缺运行时视为永久排除项。
详见 `03-待办.md`。

## 快速开始

以下命令都从**仓库根目录**执行：

```powershell
# 1) 先体检（只读，不改任何配置）
node scripts/magicclass-local.mjs doctor

# 2) 一键起四服务（按依赖顺序拉起 magicclass-service → FastAPI → magicclass-app → Vite；Ctrl+C 四个一起停）
node scripts/magicclass-local.mjs start

# 浏览器打开，用 student_demo / Demo123456 登录
# http://127.0.0.1:5174/courses  →  点「进入课堂」
```

端口固定为：Vite `5174` / FastAPI `8000` / magicclass-service `4010` / magicclass-app `3000`。

`magicclass-app` 是导航栏「学习空间」承载的上游应用（独立进程、独立 Origin），
首次使用前要先在 `magicclass-app/` 里执行一次 `pnpm install`。

### ⚠️ 如果 `start` 起不来：先看端口是不是被占了

`start` 是**全有或全无**的：任一端口被占，对应子进程会退出，启动器随即把另外三个也一起关掉
（表现为"跑了一下就退出"，而日志里只有 Vite 的 HMR 输出，看不到明显报错）。

先跑 `doctor` 看「端口占用」一节。**最容易被占的是 `:4010`**——
如果这个仓库同时有别的会话/终端在跑受管服务，它就会先把 4010 占住。

这种情况下**不要反复重试 `start`**，只把缺的那两个单独起起来即可：

```powershell
# 只起 Vite（:5174）
cd webreact
npm run dev

# 只起 FastAPI（:8000），另开一个终端
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前提是 `:4010` 上已经有一个健康实例。确认方式：

```powershell
Invoke-WebRequest -Uri 'http://127.0.0.1:4010/internal/health/live' -UseBasicParsing
# 期望 200 {"status":"ok"}
```

（注意：`http://127.0.0.1:4010/` 一定返回 404 —— 受管服务只暴露 `/internal/*`，
404 不代表它没在跑。）

## 当前基线

| 项 | 值 |
| --- | --- |
| 分支 | `master` |
| 能力提交 | 7 个（`fb9c6be9` → `dd3a8015`），逐条见 `02-现状.md` |
| 前端单测 | `npm test`（在 `webreact/`）→ 877 passed / 0 failed |
| 受管服务单测 | `npm test`（在 `magicclass-service/`）→ 279 passed / 0 failed |
| 后端 magicclass 用例 | `pytest tests -k magicclass`（在 `backend/`）→ 370 个用例 |
| 浏览器验收 | `run_magicclass_workbench_e2e.py` → 11 步全过 |

> 这些数字是**本目录成稿时**的基线。数字会随后续提交变化，不用当契约；
> 真正的契约是「改完必须全绿」。

## 术语

| 词 | 指什么 |
| --- | --- |
| **参考项目 / `$REF`** | magic class v1.0.x 源码，见上文。**只读**。 |
| **受管服务** | `magicclass-service`，仓库内自带的 Node 运行时（:4010），承载 DSL / 编辑 / 播放 / 生成 / 讨论。 |
| **网关** | `backend`，FastAPI（:8000），负责身份、课程权限与短时断言签发。 |
| **移植层** | `webreact/src/maic/**`，从参考项目逐字搬过来的界面代码。 |
| **集成层** | `webreact/src/components/magicclass/**`，把移植层接到 CampusMate 真实数据上。 |
| **切片** | 一次可独立验收的改动单元。每个切片一次提交 + 一次真实浏览器验收。 |

