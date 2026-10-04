# magic class 模块现状与安卓端接入参考

> 代码审阅日期：2026-09-29。依据当前工作区源码整理，未启动服务或使用真实模型做端到端验收。工作区已有其他会话的未提交修改；本文描述的是审阅时可见的实现，不能代替部署环境的能力检测。

## 1. 先分清三条链路

项目里“magic class”指向三条有关联、但数据和身份并未统一的链路：

| 链路 | 用户入口 | 数据与调用路径 | 安卓端现状 |
| --- | --- | --- | --- |
| 独立学习空间 | Web 导航 `/learning-space` | Web 获取 CampusMate 状态后，跨源 iframe 直连 `magicclass-app/`（Next.js，上游版本 `1.0.3`）；本站不代理其 `/api/*` | 没有独立学习空间页面或同等原生实现 |
| 课程内经典互动课堂 | 课程详情中的生成、历史课堂 | Android/Web → FastAPI `/api/v1/courses/{course_id}/interactive-classroom/*` → `magicclass-app` 的 `/api/generate-classroom`、`/api/classroom` | 已有生成前计划、确认、生成、轮询、重试、组成说明、历史和系统浏览器打开 |
| CampusMate 受管工作台 | Web `/courses`、课程工作台 | Web → FastAPI `/api/v1/courses/{course_id}/workspaces/*` 等 → `magicclass-service/` 内部接口；由 CampusMate JWT、课程权限和服务断言约束 | 尚无工作台、舞台编辑器与播放器的原生界面/API 封装 |

`magicclass-app` 与 `magicclass-service` 是两个进程。前者是完整上游产品，后者是本仓库开发的课程绑定服务。`workspace_id`、`stage_id`、`scene_id` 是受管工作台的层级标识；经典课堂使用 `session_id`、`classroom_id`，不能混用。独立学习空间使用自己的浏览器状态/匿名 owner cookie 和可选 `ACCESS_CODE`，并不会自动继承 CampusMate JWT、课程归属和历史记录。[入口代码](../webreact/src/pages/LearningSpacePage.jsx)、[经典课堂网关](../backend/app/api/routes/magicclass_classroom.py)、[受管服务入口](../magicclass-service/src/main.ts)。

## 2. 已有功能到底能做什么

### 2.1 上游独立应用 `magicclass-app/`

- 首页输入主题或上传材料，先生成大纲，再生成各场景内容和教学动作；已有服务端整课异步任务接口。普通生成界面在浏览器中编排多段 `/api/generate/*` 调用，不能把一个 `/api/generate-classroom` 误认为所有 UI 流程的唯一入口。
- 课堂有 **4 种 scene type**：`slide`（幻灯片）、`quiz`（测验）、`interactive`（交互）和 `pbl`（项目学习）。模拟、思维导图、编程、游戏、3D、程序性技能是 `interactive` 场景内的 widget 类型，不是第 5～10 种 scene type。[DSL 定义](../magicclass-app/packages/@magicclass/dsl/src/stage.ts)、[widget 定义](../magicclass-app/lib/types/widgets.ts)。
- 播放场景、白板和教学动作；AI 教师/智能体讨论与问答；选择题等交互作答，简答可调用模型评分。PBL v2 有导师引导、模拟器、评价及任务状态接口。
- 可选的搜索、图片/视频生成、TTS、ASR、PDF/多格式文档解析、语音克隆，以及多个模型/媒体提供方。能力依赖实际配置，`GET /api/health` 只声明 `webSearch`、`imageGeneration`、`videoGeneration`、`tts` 四项可用性；该声明不能代表所有路线、模型和外部服务都可用。
- 上游 README 描述了 PPTX、HTML 和课堂 ZIP 导出；MP4 导出还依赖独立渲染服务和功能开关。上游 `/api/stages/*`、`/api/folders/*`、`/api/materials/*` 与 Agent 会话路由均要求 `MAGICCLASS_AGENT_RUNTIME_ENABLED` 和 `DATABASE_URL`；`/api/stage-meta/*` 只要求服务端持久化，即 `DATABASE_URL`；`/workspace` 页面还受前端 Pro 工作台开关约束。未满足相应条件时多条路由返回 404。[功能说明](../magicclass-app/README-zh.md)、[功能开关](../magicclass-app/lib/config/feature-flags.ts)。

### 2.2 CampusMate 课程侧

- **经典课堂**：从后端读取课程与获授权资料，向学生展示只读计划，再按 9 个学习意图生成课堂：`adaptive`、`explain`、`quiz`、`simulation`、`visualization`、`mindmap`、`coding`、`pbl`、`review`。意图是对生成器的要求，实际内容应以 `/composition` 回读为准。历史会话和重试保留学生输入快照。[需求构造](../backend/app/services/magicclass/requirement_builder.py)。
- **受管工作台**：按用户和课程管理文件夹、工作台、舞台、资料；搜索与最近内容；生成任务及产物；舞台 DSL 编辑命令、场景大纲和播放计划；测验作答状态；按场景讲解音频、自由文本 TTS、圆桌讨论；`.maic.zip`、PPTX 导入和 Markdown/DOCX/PPTX/视频导出。这里的部分动作是异步任务，是否可用应以 `/magicclass/fusion/status` 和 `/providers` 的实时结果为准。**当前受管视频导出只把舞台名、场景标题绘制成 MP4 文字画面**，没有把舞台的幻灯片、交互内容、白板或音频真正录制进去。[受管服务路由](../magicclass-service/src/main.ts)、[受管渲染器](../render-service/src/renderer.ts)、[网关路由](../backend/app/api/router.py)。
- **Web 页面**：课程内有生成入口、工作台和播放器/编辑器组件；导航中的 `/learning-space` 则承载整份上游应用。两处 UI 不是同一个课堂库。[Web 路由](../webreact/src/App.jsx)。

## 3. 对安卓端最重要的 CampusMate 公开接口

以下均以 `/api/v1` 为前缀；`C` 表示 `/api/v1/courses/{course_id}`，`W` 表示 `C/workspaces/{workspace_id}`，`S` 表示 `W/stages/{stage_id}`，`X` 表示 `S/scenes/{scene_id}`。所有接口均由 FastAPI 提供，安卓端应走现有 CampusMate 登录态。课程内路由检查课程可见性，受管服务再校验服务断言、用户/课程/工作台归属；不要让 App 直接连接 `magicclass-service` 的 `/internal/*`。[公开路由汇总](../backend/app/api/router.py)、[服务认证](../magicclass-service/src/server.ts)。

### 3.1 全量路由清单（54 条）

| 分类 | 方法与路径（省略共同 `/api/v1` 前缀） | 用途 |
| --- | --- | --- |
| 全局状态 | `GET /magicclass/learning-space/status` | 独立上游应用是否可达及公开 `embed_origin`；不绑定课程 |
| 受管状态 | `GET /magicclass/fusion/status`；`GET /magicclass/fusion/providers`；`GET /magicclass/fusion/recent` | 受管服务四态、提供方布尔能力、当前用户可见课程的最近课堂 |
| 经典课堂 | `GET C/interactive-classroom/status`；`GET C/interactive-classroom/plan`；`POST C/interactive-classroom/generate`；`GET C/interactive-classroom/jobs/{session_id}`；`GET C/interactive-classroom/{session_id}/composition`；`GET C/interactive-classroom`；`POST C/interactive-classroom/{session_id}/retry` | 服务状态、只读计划、异步生成、进度、真实组成、历史、重新提交 |
| 课程上下文 | `GET C/magicclass-context` | 当前课程可用于课堂的名称、知识点、章节、资料概况 |
| 工作台 | `GET C/workspaces`；`POST C/workspaces`；`GET W`；`PATCH W`；`DELETE W` | 分页列表、创建、读取、修改和删除工作台 |
| 舞台文档 | `GET W/stages`；`POST W/stages`；`GET S`；`PUT S`；`DELETE S` | 分页列表、创建、读取 DSL 文档、整体替换和删除 |
| 文件夹/搜索 | `GET C/folders`；`POST C/folders`；`GET C/folders/{folder_id}`；`PATCH C/folders/{folder_id}`；`DELETE C/folders/{folder_id}`；`GET C/search` | 目录与课程内搜索 |
| 资料 | `GET C/materials`；`POST C/materials`；`POST C/materials/resolve`；`GET C/materials/{material_id}`；`DELETE C/materials/{material_id}` | 列表、上传、批量解析引用、正文详情、删除 |
| 生成/任务 | `POST W/generate`；`POST C/home-generate`；`GET C/jobs/{job_id}`；`POST C/jobs/{job_id}/cancel`；`POST C/jobs/{job_id}/retry`；`GET C/artifacts/{artifact_id}` | 创建舞台/首页生成、进度、取消或重试、下载音频/JSON/MP4 产物 |
| 编辑/播放 | `POST S/commands`；`GET S/outline`；`GET S/playback`；`GET X` | 有版本控制的 DSL 命令、大纲、播放计划、单场景内容 |
| 测验 | `GET X/quiz-attempt`；`POST X/quiz-attempt` | 读取和保存当前学生的作答阶段、答案、结果 |
| 讲解/语音/讨论 | `GET X/narration`；`POST X/narration`；`POST C/tts`；`POST C/discussion` | 场景讲解音频状态/排队、自由文本语音、圆桌讨论任务 |
| 导入导出 | `GET S/export`；`GET S/export/{format}`；`POST S/export/video`；`POST W/import`；`POST W/import/pptx` | 单舞台 `.maic.zip`；`markdown`/`docx`/`pptx`；视频任务；档案/PPTX 文件导入 |

受管服务另有 `/internal/health/live`（唯一匿名探活）和需要 `X-CampusMate-Service-Assertion` 的 `/internal/health/ready` 与业务路由。内部业务接口按工作台、文件夹、资料、生成/任务、编辑/播放、导入导出、语音/讨论及提供方分组，与上述网关路径大体对应；服务使用 `:courseId` 等动态段，网关使用 `{course_id}` 等动态段。**另外两条仅存在于受管服务的写接口**：`POST /internal/courses/:courseId/jobs` 可凭 `kind/mode` 创建通用任务；`POST /internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/whiteboard` 可凭 `board` 增加舞台白板。这两条均没有对应的 FastAPI 公开路由，安卓端不可直接调用。[服务路由装配](../magicclass-service/src/main.ts)、[任务路由](../magicclass-service/src/jobs/routes.ts)、[白板路由](../magicclass-service/src/whiteboard/routes.ts)。

### 3.2 安卓可直接沿用的经典课堂契约

| 步骤 | 请求与关键字段 | 响应与 UI 处理 |
| --- | --- | --- |
| 查状态 | `GET C/interactive-classroom/status` | `enabled/configured/available/unavailable/incompatible/degraded`、`capabilities`、`reason`、`poll_interval_ms`、`browser_embed_available`、`embed_origin`。区分未启用、不可达、版本不兼容和可选能力降级 |
| 预览 | `GET C/interactive-classroom/plan?mode=adaptive` | `mode`、`requested_mode`、`adaptive_reason`、课程名、候选资料、上下文警告、`can_generate`；只读，无生成费用 |
| 用户确认后提交 | `POST C/interactive-classroom/generate` | JSON 可带 `mode`、`learning_objective`（≤500 字）、`current_difficulty`（≤500 字）、`desired_duration_minutes`（5～180）、`difficulty_level`（`beginner/standard/advanced`）、`wants_more_practice`、`selected_material_ids`（≤20）。返回 HTTP 202、`session.session_id`、`poll_interval_ms` |
| 轮询与恢复 | `GET C/interactive-classroom/jobs/{session_id}` | `status`：`queued/running/succeeded/failed`，并有 `step/progress/terminal/retryable/partial/error_code`；以 `session_id` 恢复，不能把“停止轮询”当成取消生成 |
| 结果 | `GET C/interactive-classroom/{session_id}/composition`；`GET C/interactive-classroom` | 真实场景与 widget 计数、白板/TTS/多智能体标志、历史；不要从请求 mode 推断最终课堂组成 |
| 失败重试 | `POST C/interactive-classroom/{session_id}/retry` | 成功后得到**新** `session_id`；若旧任务仍进行中则返回 `accepted=false`。优先使用原任务保存的个性化快照，可能忽略本次 body，并在 `request_source_note` 中解释 |

后端只信任自己重新读取的课程资料正文与课程权限；客户端仅选择资料 ID。`session.url` 需要公开 Origin 且满足浏览器准入条件才可打开。接口的服务端状态和可打开状态应分别展示。[请求/响应模型](../backend/app/schemas/magicclass.py)、[路由实现](../backend/app/api/routes/magicclass_classroom.py)。

### 3.3 受管工作台的关键数据与请求约束

- `WorkspaceOut` 有 `id/course_id/name/description/folder_id/revision`；`StageOut` 另有 `workspace_id/title/dsl_version/document/revision`。列表返回 `items/next_cursor`；通常支持 `limit`（默认 20，上限 50）和 `cursor`。安卓端保存三层 ID，切课程时丢弃旧请求的响应。[模型](../backend/app/schemas/magicclass_fusion.py)。
- 创建工作台/舞台/文件夹、生成、编辑命令、导入和异步媒体任务需 `Idempotency-Key`；修改/删除工作台、舞台、文件夹或资料，以及提交舞台编辑命令时需 `If-Match: <revision>`。编辑器发送 `commands`（1～50 条）而非任意替换；收到版本冲突后重新读取并让用户处理。具体写接口以各路由参数为准。[工作台路由](../backend/app/api/routes/magicclass_workspaces.py)、[文件夹路由](../backend/app/api/routes/magicclass_discovery.py)、[编辑路由](../backend/app/api/routes/magicclass_editor.py)。
- `POST W/generate` 接受 `mode/prompt/role_mode/selected_role_ids`：`prompt` ≤2000 字，`role_mode` 为 `preset/auto`，最多 7 个角色 ID；`mode` 限 `slide/quiz/interactive/pbl/simulation/diagram/code/game/visualization3d/procedural-skill`，这是 **10 种生成意图，不是 10 种 scene type**。`POST C/home-generate` 的 `prompt` ≤750 字，`mode` 默认 `slide`，会解析或创建首页工作台并启动生成。查询 `GET C/jobs/{job_id}`，任务状态为 `queued/running/completed/failed/cancelled`；成功产物用 `GET C/artifacts/{artifact_id}` 获取。[生成路由](../backend/app/api/routes/magicclass_generation.py)、[生成模式](../magicclass-service/src/generation/generator.ts)、[任务状态](../magicclass-service/src/jobs/repository.ts)。
- 上传资料用 `multipart/form-data` 的 `file`，单文件上限 **2 MiB**；目前可提取正文的是 `.txt/.md/.markdown/.pdf/.docx`，其它已识别格式会标为 `unsupported`。资料列表不含正文，详情才有 `text`；`resolve` 返回 `resolved/unresolved`，后者不会泄露未解析原因。[上传路由](../backend/app/api/routes/magicclass_materials.py)、[提取策略](../backend/app/services/magicclass/material_extraction.py)。
- `GET S/export` 返回 `.maic.zip` 文件字节，`GET S/export/{format}` 的格式限 `markdown/docx/pptx`；`POST W/import` 和 `/import/pptx` 是 multipart，分别限约 **2.5 MiB** 和 **3 MiB**；视频导出返回任务引用，最终到 artifact 下载，但受管服务只有配置自己的渲染服务时才注册内部视频导出路由。受管网关目前没有 HTML 导出路由。[档案路由](../backend/app/api/routes/magicclass_archive.py)、[受管服务视频路由](../magicclass-service/src/archive/routes.ts)。
- `POST X/narration` 不收讲稿正文，讲稿由服务端从场景派生，返回任务；重载可先 `GET X/narration`。`POST C/tts` 则是自由文本合成。`POST C/discussion` 提交讨论任务，转录通过产物读取。[讲解路由](../backend/app/api/routes/magicclass_narration.py)。

### 3.4 补充的请求与响应细节

| 接口组 | 安卓端容易漏掉的契约 |
| --- | --- |
| `GET /magicclass/fusion/status`、`GET /magicclass/fusion/providers` | 状态接口以 `state=disabled/unavailable/degraded/ready` 为主判据，只有 `ready` 时 `capabilities` 才可信。提供方接口返回 `{state,providers}`，`providers` 仅有 `llm/web_search/image/video/tts/render/external_3d` 布尔值，不下发密钥；关闭时为 `{state:"disabled",providers:{}}`。 |
| `GET /magicclass/fusion/recent`、`GET C/magicclass-context` | 前者用 `limit`（1～50，默认 20）返回 `items/limit/has_more`；目前 `items.kind` 只有 `classroom`，`href` 是 CampusMate 站内深链，外部课堂地址在可选的 `classroom_url`。后者返回 `knowledge_points/chapters/materials/sources/warnings/synced`；`synced=false` 与读取失败的 `warnings` 要分开提示。 |
| `GET C/search`、文件夹读写 | 搜索必须传非空 `q`（最多 200 字），返回 `items/next_cursor/query`；命中项的 `kind` 是 `workspace/stage`，`path` 是站内深链。创建文件夹传 `name/parent_id`；更新 `parent_id:null` 表示移到根目录，工作台更新 `folder_id:null` 表示取消归档。 |
| 舞台列表、编辑和播放 | `GET W/stages` 的条目是 `StageSummaryOut`，**不含 `document`**；`GET S` 才取完整 DSL。`POST S/commands` 返回新 `revision/applied_commands/migrated`；`GET S/outline` 仅有场景目录；`GET S/playback?scene_id=...` 用 `start_index` 恢复，并按各场景 `render.kind`（`native/sandbox-html/sandbox-url/unsupported`）处理；`GET X` 取场景正文。 |
| `GET,POST X/quiz-attempt` | `GET` 返回 `attempt_id` 和可能为 `null` 的 `state`；`POST` 请求体是 `attempt_id/phase/answers/results/start_new_attempt`，阶段为 `draft/submitted/reviewed`。`start_new_attempt=true` 创建重试记录；旧阶段回退返回 409。此存储在 FastAPI，本路由只检查课程可访问，不能把路径里的工作台/舞台/场景 ID 校验当成已实现的保证。 |
| `POST X/narration`、`POST C/tts`、`POST C/discussion` | 讲解请求体仍须带与路径一致的 `stage_id/scene_id` 和幂等键；`tts` 请求体是 `text`（≤20000 字）、可选 `instruction/voice`；讨论请求体是 `prompt`（≤4000 字）。写接口异步返回任务，轮询 `GET C/jobs/{job_id}` 后按 `artifact_id` 下载；任务响应有 `status/progress/error_code/artifact_id`，讲解任务还带 `scene_id`。 |
| 文件下载 | `GET C/artifacts/{artifact_id}` 返回文件字节，媒体类型只放行 WAV/JSON/MP4；导出也返回文件字节与 `Content-Disposition`，`.maic.zip`/格式化导出含 `X-Archive-Sha256`。不要按 JSON DTO 解析文件响应。 |

[数据模型](../backend/app/schemas/magicclass_fusion.py)、[测验模型与路由](../backend/app/schemas/magicclass_quiz.py)、[播放决策](../magicclass-service/src/player/playback.ts)、[任务路由](../backend/app/api/routes/magicclass_generation.py)。

### 3.5 跨模块的课堂入口（不计入上述 54 条专用路由）

| 接口 | 与 magic class 的关系 |
| --- | --- |
| `POST /api/v1/counselor/chat`、`POST /api/v1/assistant/chat` | 通用 AI 导员聊天；携带 `course_id` 可得到 `interactiveClassroomProposal` 建议，**只读、不创建课堂任务**。携带 `workspace_id` 时必须同时携带有权限的 `course_id`，服务端会核对受管工作台归属。流式请求返回 SSE。 |
| `POST /api/v1/agent-jobs` | 通用 Agent 任务入口；`job_kind=interactive_classroom`、`input_ref`（至少 `course_id`，可带经典课堂生成参数）提交课堂任务；新建返回 202 和 `job_id/latest_run_id`，幂等重放返回 200。生成动作还会经过独立审批门，与 `POST C/interactive-classroom/generate` 是不同的提交路径。 |
| `GET /api/v1/agent-jobs/{job_id}`、`GET /api/v1/agent-jobs/{job_id}/runs`、`GET /api/v1/agent-runs/{run_id}`、`POST /api/v1/agent-approvals/{approval_id}/decision` | 查询 Agent 任务和运行状态；待审批时 `pending_approval_id` 指向决策接口，请求体 `decision=APPROVED/REJECTED`。Agent 任务 ID、Run ID 与经典课堂 `session_id` 是不同标识。 |
| `GET /api/v1/agent-runs/{run_id}/events`、`GET /api/v1/agent-runs/{run_id}/events/stream` | 分页查询运行事件（`after_sequence/limit`）或订阅 SSE；SSE 支持 `Last-Event-ID` 续传，断开连接不会取消运行。安卓若采用 Agent 路径，需在审批、后台切换和断线后恢复此状态流。 |

[导员路由](../backend/app/api/routes/counselor.py)、[Agent 路由](../backend/app/api/routes/agent_runtime.py)、[互动课堂 Handler](../backend/app/services/agent_runtime/handlers/interactive_classroom.py)。

## 4. 上游 Next.js API 目录（独立应用自身使用）

源码中共有 **69 个 `route.ts` 路径、86 个 HTTP 方法绑定**。下列 `[id]` 是 Next.js 动态段，`[...path]` 是尾部通配段。上游多数 JSON 路由采用 `{success:true,...}` / `{success:false,errorCode,error}`，但 Agent Runtime、SSE、文件下载和持久化路由各有自己的响应形式，移动端不能按统一 JSON 封装直接接入。[路由目录](../magicclass-app/app/api)、[公共 JSON 封装](../magicclass-app/lib/server/api-response.ts)。

| 方法与路径 | 用途及条件 |
| --- | --- |
| `GET /api/health`；`GET /api/access-code/status`；`POST /api/access-code/verify` | 版本/可用媒体能力、访问码状态、用访问码换 `magicclass_access` Cookie；`ACCESS_CODE` 未设时无需该门禁 |
| `POST /api/generate-classroom`；`GET /api/generate-classroom/[jobId]` | 服务端整课生成任务：提交 `requirement` 等得到 202 `jobId/pollUrl`，随后轮询状态、步骤、进度和课堂结果；经典课堂网关使用这一组 |
| `POST /api/classroom`；`GET /api/classroom?id=...`；`GET /api/classroom-media/[classroomId]/[...path]` | 保存/读取可分享的课堂与其媒体；`POST` 由服务端分配课堂 ID |
| `POST /api/generate/scene-outlines-stream`；`POST /api/generate/scene-content`；`POST /api/generate/scene-actions`；`POST /api/generate/agent-profiles` | 普通 UI 的分段生成：大纲 SSE、场景内容、教学动作和角色配置 |
| `POST /api/generate/image`；`POST /api/generate/video`；`POST /api/generate/tts`；`POST /api/generate/voice` | 图片、视频、语音和音色生成/管理，取决于提供方 |
| `POST /api/chat`；`POST /api/chat/pi`；`POST /api/chat/pi/whiteboard-visibility`；`POST /api/quiz-grade` | 课堂聊天（前两者有 SSE 形式）、实验性 Pi 聊天/白板可见性、简答题模型评分；Pi 受功能开关控制 |
| `POST /api/pbl/v2/open-task`；`POST /api/pbl/v2/instructor`；`POST /api/pbl/v2/simulator`；`POST /api/pbl/v2/evaluate`；`POST /api/pbl/v2/task/update` | PBL v2 导师、模拟、评价与任务更新；其中导师类接口返回 SSE |
| `POST /api/extract-document`；`POST /api/parse-pdf`；`POST /api/transcription`；`POST /api/proxy-media`；`POST /api/web-search` | 文档/PDF 解析、语音转写、受控媒体代理与搜索 |
| `GET /api/server-providers`；`POST /api/provider/probe-models`；`POST /api/verify-model`；`POST /api/verify-image-provider`；`POST /api/verify-video-provider`；`POST /api/verify-pdf-provider`；`POST /api/azure-voices`；`GET /api/comfyui-workflows` | 提供方能力清单、连接验证、语音/工作流发现；服务端密钥与客户端私有配置的边界不同于 CampusMate |
| `GET /api/usage`；`GET /api/export-video/capability`；`POST /api/export-video/render`；`GET,DELETE /api/export-video/render/[jobId]`；`GET /api/export-video/render/[jobId]/download` | 使用量汇总及可选 MP4 渲染任务、取消和下载；渲染需独立服务 |
| `GET,POST /api/stages`；`GET,PATCH,PUT,DELETE /api/stages/[id]`；`GET /api/stages/[id]/scenes`；`GET /api/stages/[id]/manifest`；`GET /api/stages/[id]/freshness`；`GET /api/stages/[id]/status`；`POST /api/stages/[id]/generation-complete`；`POST /api/stages/[id]/publish`；`POST /api/stages/[id]/unpublish`；`GET /api/stage-meta/[stageId]` | 上游 Pro/Agent Runtime 的 owner 课堂文档、场景和发布状态；部分读路由仅要求服务端持久化，其余需 Agent Runtime 与数据库 |
| `GET,POST /api/folders`；`PATCH,DELETE /api/folders/[id]`；`POST /api/folders/members`；`GET,POST /api/materials`；`GET /api/materials/[id]` | 上游自己的文件夹与资料库；通过匿名 owner cookie 分区，和 CampusMate 课程资料不是同一库 |
| `GET /api/agent/runtime`；`GET,POST /api/agent/sessions`；`GET,PATCH /api/agent/sessions/[id]`；`POST /api/agent/sessions/[id]/messages`；`POST /api/agent/sessions/[id]/cancel`；`GET /api/agent/sessions/[id]/events`；`GET /api/agent/sessions/status`；`GET /api/agent/owner-events` | Pro/Agent Runtime 可用性、会话和 SSE 事件流；会话/事件需运行时开关和数据库 |
| `GET,POST /api/agent/skills`；`GET,DELETE /api/agent/skills/[id]`；`GET /api/skills/[id]` | 智能体技能查询、上传和删除；最后一条下载内置或当前 owner 技能的 ZIP 包 |
| `GET,POST,PUT,PATCH,DELETE /api/persistence/[...path]` | 上游存储抽象的 HTTP 适配层，要求数据库及相应的开发令牌配置；不是 CampusMate 对外业务契约 |

### 4.1 独立渲染服务的内部 HTTP 接口

`magicclass-app/render-service` 是**上游独立应用**可选的 MP4/场景预览进程，**不属于**上表 69 个 Next.js 路径，也不经 CampusMate 公开网关。Next.js 的 `/api/export-video/*` 将视频请求转发给它，Agent 场景预览工具可调用 `/preview`。它与仓库根目录的 `render-service/` 是不同实现和契约，不能互换。[服务说明](../magicclass-app/render-service/README.md)、[服务实现](../magicclass-app/render-service/src/main.ts)。

| 方法与路径 | 输入与结果 |
| --- | --- |
| `GET /health` | 返回资源配置、运行版本和是否接受视频任务的 `accepting` 状态；不代表预览容量。 |
| `POST /render` | multipart `project`（自包含 ZIP）、`fps/quality/format`，返回 202 `jobId`；容量限制时可返回 429。 |
| `POST /preview` | JSON 场景、舞台上下文和视口，同步返回 PNG；场景资源需自包含，不符合时返回 422，容量限制时返回 429。 |
| `GET /render/:jobId` | 查询 `queued/running/succeeded/failed/cancelled`、0～1 进度与运行指标。 |
| `DELETE /render/:jobId` | 取消排队或运行中的渲染。 |
| `GET /render/:jobId/download` | 成功后下载 MP4，或 302 跳转到签名地址。 |

### 4.2 CampusMate 受管视频导出的渲染服务

仓库根目录的 `render-service/` 是 `magicclass-service` 的私有依赖。安卓发起 `POST S/export/video` 后，受管服务先排队，Worker 再调用这里；安卓仍只轮询 CampusMate `GET C/jobs/{job_id}` 并下载 `GET C/artifacts/{artifact_id}`。当前渲染器用 FFmpeg 生成舞台名与场景标题的文字画面，最长 120 秒；它不接受上游 Hyperframes ZIP，也不提供上游的异步渲染任务接口。[调用方](../magicclass-service/src/provider/client.ts)、[渲染器](../render-service/src/renderer.ts)。

| 方法与路径 | 输入与结果 |
| --- | --- |
| `GET /internal/health` | 返回 200 `{status:"ok"}`；服务探活。 |
| `POST /internal/render` | 私有请求头 `x-render-service-token`，JSON `{document}`（需 1～50 个 `scenes`，请求体上限 2 MiB）；同步返回 `video/mp4` 字节。缺少或错误令牌为 401，过大为 413，解析/渲染失败为 422。 |

[受管渲染服务入口](../render-service/src/server.ts)、[配置](../render-service/src/config.ts)。

## 5. 安卓端现状、缺口和接入顺序

现有 [Android Retrofit 接口](../android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt)只接了经典课堂的 7 条路由；[课程页](../android/app/src/main/java/com/example/campusai/ui/screens/courses/InteractiveClassroomSection.kt)已有确认门、状态/计划展示、会话轮询与恢复、失败重试、真实组成及历史。课堂通过 `Intent.ACTION_VIEW` 交给系统浏览器，**尚无原生 slide/quiz/interactive/PBL 播放器、受管工作台编辑器，也没有独立学习空间的 Android 入口**。打开前使用 [ClassroomUrlPolicy](../android/app/src/main/java/com/example/campusai/data/remote/ClassroomUrlPolicy.kt) 只接受公开 HTTPS 且 Origin 精确匹配的地址；本地 HTTP 调试地址不会被它放行。

后续做安卓原生前端，建议按以下顺序复用现有契约：

1. 先确定页面目标：若是**课程内原生工作台**，以 CampusMate `/api/v1/courses/*` 及 `/api/v1/magicclass/fusion/*` 为唯一业务入口；若是**独立上游学习空间**，它目前是跨源网页产品，需另行设计身份、数据和文件同步，不能假设经典课堂或受管工作台的 ID 能直接打开它。仓库要求 `magicclass-app/` 的本地改动进入品牌规则、可逆功能补丁或逐项说明的已声明偏离，并通过 `check` / `verify` 来源校验；新增对接契约应优先放在 CampusMate 后端和受管服务层。
2. 在 Retrofit/Repository 增加受管状态、课程上下文、最近内容、工作台/舞台/文件夹、资料、生成任务和产物 DTO。先实现只读列表与恢复，再实现带 `Idempotency-Key`、`If-Match` 的写操作。`document` 是版本化 DSL；原生渲染前应按四种场景类型和 widget 分发，对未知类型显示不支持状态。
3. 播放器依次消费 `GET S/outline`、`GET S/playback`、`GET X`，按播放计划中的渲染决定处理；测验单独持久化 attempt。语音按 scene 查询/发起 narration，再通过 job/artifact 拿音频，不要只依赖一段自由文本 TTS。
4. 上传与导出按文件流处理，分页按 `next_cursor` 继续；显示提供方不可用、模型缺失、版本冲突、任务失败、公开 URL 不可打开等真实状态。生成是否成功与能否在浏览器打开是两件事。

**目前需要补/核的契约**：Web 的 [API 封装](../webreact/src/data/api.js) 调用了 `POST C/workspaces/{workspace_id}/stages/{stage_id}/whiteboard`，`magicclass-service` 有同名内部路由，但 FastAPI `magicclass_*` 公开路由里没有对应 POST，按现有路由清单移动端不可直接使用。原生白板写入前需补齐或确认公开网关。另，上游 Pro 的 `/api/stages/*` 使用匿名 owner cookie，与 CampusMate 用户/课程数据不贯通，不能用来补这个缺口。

## 6. 如何判断“能用”

- `MAGICCLASS_ENABLED` + `MAGICCLASS_BASE_URL` 控制经典课堂/独立应用服务端连接；`MAGICCLASS_EMBED_ORIGIN` 控制浏览器公开 Origin。前者通了不代表后者能打开。[配置](../backend/app/core/config.py)。
- `MAGICCLASS_FUSION_ENABLED` + `MAGICCLASS_SERVICE_URL` + 服务断言密钥控制受管工作台；其 `/status` 的 `disabled/unavailable/degraded/ready` 与经典课堂的 `enabled/available/incompatible` 是两套状态。[受管状态](../backend/app/api/routes/magicclass_fusion.py)。
- 受管 MP4 还要求 `magicclass-service` 配置 `MAGICCLASS_RENDER_SERVICE_URL` 与 `MAGICCLASS_RENDER_SERVICE_TOKEN`，并单独运行仓库根目录的 `render-service/`；上游独立应用的 `RENDER_SERVICE_URL` 与其 `magicclass-app/render-service/` 是另一套配置。[受管渲染配置](../magicclass-service/src/config.ts)、[上游渲染服务说明](../magicclass-app/render-service/README.md)。
- 上游 `ACCESS_CODE` 只保护上游应用：FastAPI 可在服务器内完成访问码交换，Android/Web 浏览器不会自动得到该 Cookie。`browser_embed_available=false` 时不要展示可点击的“打开课堂”。[上游门禁](../magicclass-app/middleware.ts)、[经典状态](../backend/app/services/magicclass/classroom_service.py)。
- 接口存在仅说明源码提供了入口；模型、TTS、图像、视频、数据库、渲染服务、公开 HTTPS Origin 必须在目标部署中分别验证。本文未作真实设备、真实 Provider 或浏览器联调结论。
