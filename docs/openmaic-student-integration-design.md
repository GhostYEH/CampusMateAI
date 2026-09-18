# OpenMAIC 学生侧整合 — 阶段 0：参考实现审计与详细设计

> 状态：**已批准（2026-09-16）**。D1–D6 决策已确认，阶段 1–7 执行中。
> 审计对象：只读参考仓库「OpenMAIC 参考源码」（本地只读副本，MIT，`Copyright (c) 2026 THU-MAIC`）
> 与本仓库 CampusMateAI（审计时 HEAD `6e0e63e5`，分支 `master`）。
> 审计期间**未修改参考目录任何文件**。

---

## 0.1 已批准决策（D1–D6，2026-09-16）

| # | 决策 | 结论 |
| --- | --- | --- |
| **D1** | 课堂页访问路径 | 采用**方案 A**：OpenMAIC 部署在独立可信子域；不改其源码、不用 `basePath`；`ACCESS_CODE` 留空；用 `ALLOWED_FRAME_ANCESTORS` 放行 CampusMate Web Origin；生成 API 只由 CampusMate 后端调用；子域由**网络层**（反代 / 校园网 / VPN / forward-auth）保护；**不把"课堂 ID 不可枚举"当作唯一授权**；CampusMate 后端仍按 `user_id/course_id/session_id` 校验全部生成、状态、历史与打开请求；浏览器只获得后端校验过的课堂地址 |
| **D2** | 学生生成意图 | 接受 **9 个意图**：`adaptive / explain / quiz / simulation / visualization / mindmap / coding / pbl / review`；保留旧值 `explore / practice / project` 并**归一化**到新意图，不破坏已有客户端与测试 |
| **D3** | CPM 生成路径 | 复用现有 **counselor + Agent Runtime**，不建第二套 CPM；新增 `job_kind=interactive_classroom`；走现有 Handler / `ToolInvocationGateway` / 权限 / 归属 / `RiskEngine` / `ApprovalGate` / 幂等 / 审计；LLM 与 counselor **不得**直接调用 `OpenMAICClient`；`inspect/list/propose/status/open` 为只读安全工具，`generate` 必须 `CONFIRM_REQUIRED`；"打开课堂"只返回 CampusMate 内部深链 |
| **D4** | 类型无法强制保证 | 接受。9 个 mode 是**生成意图**（受控 requirement 模板），UI 不承诺"必定生成 3D/思维导图/实验"；生成完成后必须调用真实 `GET /api/classroom?id=...`，解析真实 `scene.type` / `widgetType` / 白板 / TTS / 多智能体，用"已生成内容包含……"如实展示 |
| **D5** | MP4 导出 | **本轮不做**。不接 `render-service`、不展示无实现的 MP4 按钮，列入 backlog，不阻塞核心接入 |
| **D6** | 3D 外部依赖 | 接受对 `unpkg.com` 的依赖，但必须**显式降级**：新增运维开关 `OPENMAIC_EXTERNAL_3D_AVAILABLE`；关闭时 `adaptive` 不推荐 `visualization3d`、UI 标注 3D 不可用，`simulation/diagram/code/game` 仍可用；开启时提示学生 3D 需要访问外部 CDN；CDN 不可用不得把空白 iframe 说成成功；课堂整体成功但 3D 失败时报 `degraded`；不复制/修改其 3D 模板 |

---

## 0. 审计方法与结论摘要

方法：完整读取 OpenMAIC 的 `LICENSE` / `package.json` / `next.config.ts` / `middleware.ts` / 全部 `app/api/**/route.ts` /
`packages/@openmaic/{dsl,renderer,generation,storage,importer,editor}` / `components/{scene-renderers,classroom,stage,whiteboard,roundtable}` /
`render-service/` / `.env.example` / `docker-compose.yml` / `Dockerfile`；以及 CampusMate 的
`backend/app/services/openmaic/**`、`backend/app/api/routes/{openmaic_classroom,counselor,agent_runtime}.py`、
`backend/app/schemas/openmaic.py`、`backend/app/core/config.py`、`backend/app/services/{container,course_access}.py`、
`backend/app/services/agent_runtime/**`、`webreact/src/{components/interactive,pages,data}/**`、Android 相关代码与测试。
关键结论均已在源码中二次核对。

### 六个决定设计的发现

| # | 发现 | 影响 |
| --- | --- | --- |
| **F1** | OpenMAIC 的场景类型**只有 4 个**：`slide \| quiz \| interactive \| pbl`（`packages/@openmaic/dsl/src/stage.ts:22`）。任务书里的"13 种场景"并不存在——3D/模拟/游戏/思维导图/编程 是 `interactive` 内部的 6 个 `WidgetType`；白板/TTS/多智能体讨论是 `Stage` 字段与 `Action` 动作，不是场景类型。 | 生成模式**不能**按类型下单，只能映射为 requirement 提示词；类型组合由 OpenMAIC 的 LLM 决定。必须**事后读取**真实课堂文档才能如实报告"生成了什么"。 |
| **F2** | `POST /api/generate-classroom` 的请求体**只有一个必填字段 `requirement: string`**，加 4 个能力布尔（`enableWebSearch`/`enableImageGeneration`/`enableVideoGeneration`/`enableTTS`）和 `agentMode`。**没有**"生成思维导图"这类类型参数。 | 学生侧的 9 种内容形态 = 9 段受控提示词。UI 文案不得承诺"一定会生成 X"。 |
| **F3** | OpenMAIC **不支持 `basePath`**（`next.config.ts` 无 `basePath`/`assetPrefix`），且客户端请求全部是根绝对路径（`/api/...`、`/logos/...`、`/avatars/...`）。 | `https://campus.example.com/openmaic/...` 不可行（除非改 OpenMAIC 源码，禁止）。必须走**可信子域**。 |
| **F4** | 跨源 iframe 默认被阻断：`X-Frame-Options: SAMEORIGIN` + `CSP frame-ancestors 'self'`；仅当**构建期**设置 `ALLOWED_FRAME_ANCESTORS` 才放开（`next.config.ts:52-70`）。且 `openmaic_access` cookie 是 `HttpOnly + SameSite=Lax`，跨站 iframe **不会**自动携带。 | 见 §3 三个方案与推荐。当前代码"启用 ACCESS_CODE 时 `browser_embed_available=false`"是**正确**的 fail-closed 行为，应保留。 |
| **F5** | OpenMAIC **没有 classroom generation 的取消端点**，`ClassroomGenerationJobStatus` 只有 `queued\|running\|succeeded\|failed`（`render-service` 才多一个 `cancelled`）。也没有"重试/恢复"端点。 | 不发明接口。"取消"只能做成本地停止轮询；"重试"= 我方重新提交新任务；"恢复"= 用我方历史里的 classroomId 重新打开。 |
| **F6** | **CPM 的真实实现就是 counselor（AI 校园助手）**：后端 `POST /api/v1/counselor/chat`（别名 `/assistant/chat`），Web `CounselorPage.jsx`（标题"AI校园助手"），Android `CounselorScreen.kt`（唯一把 "CPM" 写在界面上的端）。它当前是 **RAG + LLM 直连，无工具、不经 Agent Runtime**。 | 复用，不新建平行 CPM。要加"生成课堂"动作，必须接入现有受管体系（§5）。 |

### 关键契约事实（供后续阶段引用）

- 统一响应信封：成功 `{ success: true, ...payload }`，失败 `{ success: false, errorCode, error, details? }`（`lib/server/api-response.ts:52-71`）。**但** `stages/*`、`folders/*`、`agent/*`、`stage-meta`、`stages/[id]/status`、`comms` 等家族**不用**信封，返回裸 JSON 或纯文本 404。不能一律按 `success` 字段判断。
- 全局**无 CORS**（全仓 `Access-Control-Allow-Origin` 零命中）。跨源浏览器直连必失败，必须由我方后端代理。
- 无 ACCESS_CODE 时全部放行；有 ACCESS_CODE 时 `/api/*`（除 `/api/access-code/*`、`/api/health`）无有效 cookie 一律 401。
- ACCESS_CODE 令牌 = `HMAC-SHA256(timestamp, ACCESS_CODE)`，**两个校验实现都不校验时间戳过期**，只有 cookie `maxAge` 约束浏览器侧。
- 教室生成是**唯一**带 `pollUrl` 的 202 作业族；`GET /api/generate-classroom/{jobId}` 的 `pollUrl` 是**按调用方 origin 现算**的（`classroom-storage.ts:31-35`），反代不转发 `x-forwarded-host` 就会返回内网地址。

---

## 1. OpenMAIC 能力清单（从真实 DSL / 类型 / 渲染器提取）

### 1.1 场景类型：4 个（唯一真源）

`packages/@openmaic/dsl/src/stage.ts:22` 与冻结集合 `:25-30`，并有双向穷尽性断言 `:35-37`：

```ts
export type SceneType = 'slide' | 'quiz' | 'interactive' | 'pbl';
```

| `scene.type` | 内容类型 | 判别字段 | 渲染组件 | 运行期依赖 |
| --- | --- | --- | --- | --- |
| `slide` | `SlideContent` | `canvas: Slide`（必填） | `components/slide-renderer/Editor/index.tsx` | 纯 React 画布，无 iframe |
| `quiz` | `QuizContent` | `questions: QuizQuestion[]`（必填） | `components/scene-renderers/quiz-view.tsx` | 本地判分 + 简答题异步 AI 判分 |
| `interactive` | `InteractiveContent` | `html?`（srcDoc）/ `url?`（回退）/ `widgetType?` / `widgetConfig?` | `components/scene-renderers/InteractiveIframeHost.tsx` | **iframe `srcDoc`**，`sandbox="allow-scripts allow-forms allow-popups"`（**刻意不含 `allow-same-origin`**，见 `InteractiveIframeHost.tsx:213-215`） |
| `pbl` | `PBLContent` | `projectV2?: PBLProject`（`projectConfig` 已 `@deprecated`） | `components/scene-renderers/pbl-renderer.tsx` → `pbl/v2/{hero,workspace,completion}.tsx` | `motion/react` + portal |

`SceneCore` 公共字段（`stage.ts:228-246`）：`id, stageId, title, order` 必填；`actions?, whiteboards?, multiAgent?, createdAt?, updatedAt?` 可选。

### 1.2 `interactive` 内部的 6 个 widgetType（任务书里的"3D/模拟/游戏/思维导图/编程"在这里）

`packages/@openmaic/dsl/src/interactive.ts:4-10`：

```
'simulation' | 'diagram' | 'code' | 'game' | 'visualization3d' | 'procedural-skill'
```

应用侧富字段定义在 `lib/types/widgets.ts:202-208`：

| widgetType | 应用类型 | 关键判别字段 | 取值 |
| --- | --- | --- | --- |
| `simulation` | `SimulationConfig` | — | `concept`, `description`, `variables[]` |
| `diagram` | `DiagramConfig` | `diagramType` | `flowchart \| mindmap \| hierarchy \| system` |
| `code` | `CodeConfig` | `language` | `python \| javascript \| typescript \| java \| cpp` |
| `game` | `GameConfig` | `gameType` | `quiz \| puzzle \| strategy \| card` |
| `visualization3d` | `Visualization3DConfig` | `visualizationType` | `molecular \| solar \| anatomy \| geometry \| physics \| custom` |
| `procedural-skill` | `ProceduralSkillConfig` | — | `task`, `steps[]`（受 `OPENMAIC_ENABLE_VOCATIONAL` 门控） |

> **3D 不是 npm 依赖**：生成的 widget HTML 在沙箱 iframe 内用 importmap 从 `unpkg.com` 加载 `three@0.160.0`
> （`packages/@openmaic/generation/templates/visualization3d-content/system.md:355-366`）。
> 即 **3D 场景要求学生浏览器能访问 `unpkg.com`**，且无本地回退。这是必须写进失败语义的约束。

### 1.3 不是场景类型的能力（由 Action / Stage 字段驱动）

| 任务书条目 | 真实形态 | 证据 |
| --- | --- | --- |
| 白板 | `Stage.whiteboard?: Whiteboard[]` + 15 个 `wb_*` 同步 Action | `stage.ts:51,151`；`action.ts:65-187` |
| 语音讲解 (TTS) | `speech` Action + `VoiceDesign` / `AgentVoiceConfig` | `action.ts:47-62`；`stage.ts:68-88` |
| AI 教师 + AI 同学讨论 / 圆桌 | `discussion` Action + `MultiAgentConfig{enabled,agentIds,directorPrompt?}` | `action.ts:196-201`；`stage.ts:129-136` |
| 导入 | PPTX（浏览器内）与 `.maic.zip`（浏览器内） | `lib/import/use-import-{pptx,classroom}.ts` |
| 导出 | `.maic.zip` / PPTX / Markdown|DOCX（**均在浏览器内**）；MP4 走服务端 `render-service` | `lib/export/**`；`app/api/export-video/**` |
| 历史课堂 | 服务端：`GET /api/stages`（需 `DATABASE_URL`+Agent Runtime）或 `GET /api/persistence/documents`；文件系统路径**无列表端点** | `app/api/stages/route.ts:35-43`；`app/api/classroom/route.ts:103-113` |

`Action` 联合共 21 个动词（`action.ts:235-256`），其中 `spotlight`/`laser` 仅幻灯片可用（`action.ts:264`）。

### 1.4 生成与作业契约（真实字段）

`POST /api/generate-classroom`（`app/api/generate-classroom/route.ts:14-73`），`maxDuration = 30`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `requirement` | `string` | **是** | 缺失 → 400 `MISSING_REQUIRED_FIELD` |
| `pdfContent` | `{text: string, images: string[]}` | 否 | 唯一的正文注入通道 |
| `enableWebSearch` / `enableImageGeneration` / `enableVideoGeneration` / `enableTTS` | `boolean` | 否 | 能力开关 |
| `webSearchProviderId` / `webSearchApiKey` / `webSearchModelId` / `baiduSubSources` | — | 否 | **我方永不传**（不持有也不得转发 Provider Key） |
| `agentMode` | `'default' \| 'generate'` | 否 | 我方固定 `generate` |

202 响应：`{ success:true, jobId, status, step, message, pollUrl, pollIntervalMs: 5000 }`。

`GET /api/generate-classroom/{jobId}`：`{ success:true, jobId, status, step, progress, message, pollUrl, pollIntervalMs, scenesGenerated, totalScenes, result, error, done }`；
`result = { classroomId, url, scenesCount }`；`done = status === 'succeeded' || 'failed'`；`running` 超 30 分钟无更新会被读侧自动判 `failed`（`classroom-job-store.ts:77-94`）。

**步骤 8 个**（`lib/server/classroom-generation.ts:62-70`）：
`initializing → researching → generating_outlines → generating_scenes → generating_media → generating_tts → persisting → completed`。
状态 4 个：`queued | running | succeeded | failed`。

### 1.5 读课堂内容（用于如实报告"到底生成了什么"）

`GET /api/classroom?id={id}` → `{ success:true, classroom: { id, stage, scenes[], createdAt } }`（`app/api/classroom/route.ts:103-141`）。
这是我方**唯一**能验证真实类型组合的只读端点，且返回的 HTML 字段已做净化。它是 §2 缺口"类型无法保证"的诚实补偿手段。

---

## 2. CampusMate 已有能力与缺口（五桶分类）

### 桶 A — 已实现且真实可用（不依赖 OpenMAIC 部署）

| 能力 | 位置 |
| --- | --- |
| OpenMAIC HTTP 客户端 + 错误映射 + 步骤/状态归一化 | `backend/app/services/openmaic/client.py` |
| 生成编排状态机（预占→落盘→提交→轮询→终态释放） | `services/openmaic/classroom_service.py:214-341` |
| 文件持久化 + 跨进程原子预占（`O_CREAT\|O_EXCL` + msvcrt/flock）+ 租约续租 + steal + 历史裁剪（只删最早终态） | `services/openmaic/result_store.py` |
| 课程上下文构建（章节/知识点/掌握率/资料/作业）+ 长度截断 | `services/openmaic/course_context.py:203-248` |
| CPM 课程上下文块 | `services/openmaic/course_context.py:251-294` |
| 课程可见性单一真源（admin / 选课 / 自有学习通课） | `services/course_access.py:36-44` |
| 5 个 HTTP 端点 + 鉴权 + 403/404 语义 | `api/routes/openmaic_classroom.py:41-172` |
| 失败即关闭：未配置 → 503 `OPENMAIC_NOT_ENABLED` | `errors.py:13-21` |
| ACCESS_CODE 换 cookie（仅后端持有） | `client.py:159-205` |
| URL fail-closed 校验（`urlparse` 比 `scheme+netloc`，路径必须是 `/classroom/{id}` 且尾段等于 classroomId） | `client.py:228-255` |
| Agent Runtime v2 全套受管设施（Gateway 12 步、审批、幂等、审计、硬拒绝、能力目录冻结） | `services/agent_runtime/**` |
| CPM/counselor 聊天（RAG + SSE/JSON） | `api/routes/counselor.py:570-792` |
| Web 面板（模式/目标/生成/轮询/历史/沙箱 iframe/新窗口回退） | `webreact/src/components/interactive/InteractiveClassroomPanel.jsx` |
| Web 可信 Origin 精确比对（含端口）+ 默认全禁 | `webreact/src/data/interactiveClassroom.js:39-110` |
| Android DTO + 契约测试（断言不含凭据） | `android/.../ApiService.kt:614-623`；`CourseChatContextContractTest.kt:66-92` |

### 桶 B — 只有 DTO / 接口壳层

| 项 | 位置 | 问题 |
| --- | --- | --- |
| `OpenMAICSubmitResult.status/.step` | `client.py:97-101` | 声明了但从 202 体读取（`client.py:343` 只取 `jobId`），会话恒为 `queued` |
| `OpenMAICGenerationFailed` | `errors.py:64-69` | 定义并导出，**全仓无抛出点** |
| Android `InteractiveClassroomDto` | `ApiService.kt:614-623` | 只建模 `enabled` + `items[].url`，6 个 item 字段只用 1 个 |
| `OPENMAIC_COURSE_CONTEXT_MAX_CHARS` | `config.py:155` | 真实读取，但 `.env.example` 未列 |

### 桶 C — 只有测试替身

- 全部上游 OpenMAIC 流量在测试中都是 `httpx.MockTransport`（`tests/test_openmaic_classroom.py:56-66`、`tests/test_openmaic_student_integration.py:118-178`）。**没有任何测试接触过真实 OpenMAIC 实例**。
- `tests/test_openmaic_classroom.py:455-459` 的 `test_no_permission_course_rejected` 是空壳（只有 `pass`）——**无课程权限的负例实际未被覆盖**。
- CPM 测试用 `llm_provider="none"`（`tests/test_counselor.py:25`）或 `RecordingLLM`（`test_counselor_knowledge_grounding.py:20-36`）。

### 桶 D — 必须部署 OpenMAIC 后才能使用

`OpenMAICClient.health/submit/poll` 及其上层全部路径。默认 `OPENMAIC_ENABLED=false` → 特性 fail-closed。
**当前无任何真实部署验证**：`status()`、`generate()`、真实 ACCESS_CODE 换取、真实 URL 返回、真实步骤推进，全部只在 mock 下跑过。

### 桶 E — 当前完全缺失

| 缺口 | 影响 |
| --- | --- |
| 内部 URL 与浏览器公开 Origin **未分离**：`embed_origin` 直接取 `OPENMAIC_BASE_URL` 的 origin（`classroom_service.py:91`、`config.py:165-174`） | 内网地址会被下发到学生浏览器；子域部署时完全错误 |
| 无版本/契约兼容探测 | 无法区分 `available` 与 `incompatible` |
| 无 `degraded` 语义 | 图像/TTS/ASR 不可用时仍报 `available` |
| 无真实课堂组成读取 | 无法如实告诉学生"生成了哪些类型" |
| 无 `review`（考前复习）等学生形态 | 学生形态只有 5 个，且与任务书 9 个不一致 |
| 学生输入（困难/时长/难度/是否需要更多练习）无字段 | `OpenMAICGenerateRequest` 只有 `mode` + `learning_objective` |
| 无 CPM → 生成的结构化提案与确认门 | CPM 完全无法触发课堂生成（当前也**不应该**直接触发） |
| `job_kind` 正则硬编码 `^(learning_goal\|final_review\|course_research\|notice_workflow)$`（`schemas/agent_runtime.py:132`） | 新增受管作业类型必须改这一处 |
| 课程详情页 Android 侧无智能辅导入口 | Android 只在 CPM 内、且发过消息后（`chatActive`）才出现课堂卡片 |
| Android 打开课堂 URL **无 Origin 白名单**（直接 `Intent.ACTION_VIEW`） | 安全缺口，必须修 |
| Web iframe `sandbox` 含 `allow-same-origin`（`InteractiveClassroomPanel.jsx:276-282`） | 需改为**有条件**启用并加硬断言（§6） |
| 无历史课堂的"继续/归档"契约 | 无对应后端端点（OpenMAIC 也无） |

> 勘误（阶段 1 复核）：课程上下文**已经**注入 `pdfContent.text` ——
> `classroom_service.generate()` 调用 `build_input_payload(..., pdf_text=course_context)`。
> 阶段 2 要做的是把它换成**裁剪到上限、带来源与更新时间**的资料正文，而不是"从无到有"。

---

## 3. 独立部署拓扑与课堂运行页访问路径

### 3.1 拓扑（推荐结构）

```
Browser / Android
      │  HTTPS，仅访问 campus.example.com（CampusMate）
      ▼
CampusMate Web (React 18)  /  Android App
      │  /api/v1/...（JWT）
      ▼
CampusMate FastAPI  ← 唯一权限与业务网关
   ├─ 认证 / 课程权限（course_access）
   ├─ 课程上下文裁剪与脱敏
   ├─ 生成请求编排（预占 / 幂等 / 轮询 / 历史）
   ├─ 审计与错误语义归一
   └─ OpenMAIC ACCESS_CODE 的唯一持有者
      │  内部网络，Cookie 只在此跳
      ▼
OpenMAIC 独立服务（Next.js，生成与运行）        ← 不在公网直连
      │
      ├─ LLM Provider
      ├─ 图像 / TTS / ASR Provider
      └─ render-service（可选，MP4 导出，compose 内网）
```

**浏览器与 OpenMAIC 的关系**：浏览器只在**打开课堂**时直连 OpenMAIC 的课堂页（iframe 或新窗口），
从不接触其 API 凭据；所有生成/查询/历史请求都回到 CampusMate。

### 3.2 访问路径：`basePath` 不可用（F3），因此给出三方案

#### 方案 A（推荐）— 可信子域 + 关闭 ACCESS_CODE + 网络层保护

- 部署地址：`https://classroom.example.com`（根路径，不涉及 basePath）。
- 构建期设 `ALLOWED_FRAME_ANCESTORS=https://campus.example.com`（`X-Frame-Options` 会被自动省略，只留 CSP）。
- **`ACCESS_CODE` 留空**：这样课堂页自身的数据请求（`/api/classroom?id=`、`/api/stage-meta/*`）不需要 cookie，
  跨源 iframe 的 `SameSite=Lax` 问题**自然消失**。
- 用网络层而非应用层做访问控制：`classroom.example.com` 只允许
  ① 反代（带 CampusMate 签发的短时签名路径或 mTLS）② 学生网络段。
  课堂 ID 是 `nanoid(10)` / `randomUUID()`，不可枚举。
- **代价**：任何能到 `classroom.example.com` 的人，只要猜到/拿到 classroom id 就能看那节课。
  需要在部署文档里明确写出这一残余风险与缓解（短时签名 URL、IP 段限制、或前置认证反代）。

#### 方案 B — 保留 ACCESS_CODE + 我方反代课堂页与其资源

由 CampusMate 后端在 `/api/v1/openmaic/embed/{session_id}` 下代理课堂页 HTML 与
`/api/classroom*`、`/api/classroom-media/*`、`/api/stage-meta/*`、`/_next/*`、`/logos/*`、`/avatars/*`，
并把 `openmaic_access` cookie 保留在服务端。
- 优点：ACCESS_CODE 保留、浏览器零凭据、同源（无 iframe 跨源问题）。
- 代价：等于**用反代自己实现 basePath**，要重写一整个 Next.js SPA 的请求图与资源路径；任何
  OpenMAIC 升级都可能打破重写规则。风险高、维护成本高。
- 定位：**仅在安全评审强制要求保留 ACCESS_CODE 时启用**，且必须在阶段 1 之前单独批准。

#### 方案 C — 同源子路径 `https://campus.example.com/openmaic/...`

**不可行**，除非修改 OpenMAIC 源码（违反约束）。理由已在 F3 记录：
无 `basePath`；约 40 处根绝对资源路径（`/logos/*`、`/avatars/*`、`/vendor/*`）；
所有 `fetch('/api/...')` 与 `new EventSource('/api/...')` 均为根绝对；
`middleware.ts` matcher 是根相对且不含前缀。

> **待批准决策 D1**：采用方案 A 还是方案 B。默认建议 A。

### 3.3 必须写进部署文档的 OpenMAIC 侧配置

| 变量 | 取值 | 作用 |
| --- | --- | --- |
| `ALLOWED_FRAME_ANCESTORS` | `https://campus.example.com` | **构建期**变量，改后必须重新构建 |
| `ACCESS_CODE` | 方案 A：留空；方案 B：设置 | 见上 |
| `DATABASE_URL` + `OPENMAIC_AGENT_RUNTIME_ENABLED` | 建议设置 | 打开 `GET /api/stages` 列表能力（可选，见 §4） |
| `RENDER_SERVICE_URL` | 由 compose 固定为 `http://render-service:9000` | MP4 导出（可选） |
| `DEFAULT_MODEL` + 至少一个 `*_API_KEY` | 必填 | 无则 `resolveModel` 直接抛错 |
| `TRUST_PROXY_HEADERS` | `true`（仅当反代可信） | 否则 `pollUrl` 与客户端标识会取错 origin |

我方新增配置（见 §8）：内部 `OPENMAIC_BASE_URL` 与浏览器 `OPENMAIC_EMBED_ORIGIN` **必须分离**。

---

## 4. API 对齐表（CampusMate 现有请求 → OpenMAIC 真实端点）

图例：✅ 已对齐 ｜ ⚠️ 存在但需修正 ｜ ❌ OpenMAIC **不存在**（不得发明）

| 我方能力 | CampusMate 端点（现有/拟定） | 对应 OpenMAIC 真实端点 | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| health / status | `GET /courses/{id}/interactive-classroom/status` | `GET /api/health` + `GET /api/access-code/status` + `GET /api/server-providers` | ⚠️ | 现只用 `/api/health`。需补契约指纹与能力明细；`/api/server-providers` 需 ACCESS_CODE |
| 创建课堂 | `POST /courses/{id}/interactive-classroom/generate` | `POST /api/generate-classroom` | ✅ | 请求体只发 `requirement`/`pdfContent`/4 个 enable*/`agentMode` |
| 获取任务 | `GET .../jobs/{session_id}` | `GET /api/generate-classroom/{jobId}` | ✅ | 轮询驱动，无后台 worker |
| 获取步骤进度 | 同上（同一响应内） | 同上（`step`/`progress`/`scenesGenerated`/`totalScenes`） | ✅ | 步骤白名单已对齐（8 步 + `queued`/`failed`） |
| 获取课堂 | **无** | `GET /api/classroom?id=` | ❌ | **新增**：只读拉取课堂文档，用于如实报告真实类型组合 |
| 列表 / 历史 | `GET /courses/{id}/interactive-classroom` | — （**不代理** OpenMAIC 的 `GET /api/stages`） | ✅ | 以我方 `result_store` 为唯一事实源：按 `user_id/course_id` 隔离、只列 `succeeded`。OpenMAIC 列表依赖 `DATABASE_URL`+Agent Runtime 且以匿名 owner cookie 分区，不可作为学生历史源 |
| 重试 | `POST .../{session_id}/retry` | ❌ 无对应端点 | ✅ | 我方**重新提交一个新 job**（非 OpenMAIC 能力） |
| 取消 | — | ❌ **无 cancel** | ❌ | 不做假取消。UI 只提供"停止查看"；已在途的 OpenMAIC 任务继续跑完并落进历史 |
| 恢复 | 复用 `GET .../jobs/{session_id}` / 历史列表打开 | `GET /api/classroom?id=` | ⚠️ | "恢复"= 用我方历史里的 `classroom_id` 重新打开课堂页 |
| 导出 | — | `POST /api/export-video/render`（202+jobId）／`GET .../render/{jobId}`／`.../download` | ❌ | 可选能力，需 `RENDER_SERVICE_URL`。`GET /api/export-video/capability` 先探。**阶段 1 不做**，列入 backlog |
| 课堂运行 URL | `session.url` | `result.url` = `{origin}/classroom/{classroomId}` | ⚠️ | 必须用**公开 Origin**（`OPENMAIC_EMBED_ORIGIN`）重写，禁止下发内部地址 |

**不使用**的 OpenMAIC 端点（明确记录，避免后续误接）：
`/api/stages*`（教师/工作台语义，需 Agent Runtime + `DATABASE_URL`，且 `publish` 在匿名 owner 下永远 401）、
`/api/persistence/*`（Bearer 是开发用令牌）、`/api/chat`、`/api/chat/pi`、`/api/pbl/v2/*`（前端运行时内部协议）、
`/api/generate/*`（细粒度生成，属 OpenMAIC 前端内部）、`/api/agent/*`（OpenMAIC 自己的运行时）。

---

## 5. 学生化信息架构

### 5.1 课程详情页「智能辅导」页签（Web 已有，需重做内容）

```
┌ 智能辅导 ────────────────────────────────────────────────┐
│ [状态条] 本课程智能辅导：可用 / 暂不可用（原因）· 服务版本 · 最近一次课堂│
│                                        [继续学习 ▸]        │
├ 生成区 ───────────────────────────────────────────────────┤
│ 内容形态（单选）：                                          │
│   自动推荐 · 概念讲解 · 练习测验 · 实验模拟 · 3D/可视化     │
│   思维导图 · 编程实验 · 项目式学习 · 考前复习                │
│ 学习目标 [____]  当前困惑 [____]  时长 [15/30/45/60 min]    │
│ 难度 [入门/标准/进阶]  □ 多给我一些练习                     │
│ 使用资料：[本课程资料标题多选，默认全选，可清空]              │
│                                        [生成互动课堂]       │
├ 进度区 ───────────────────────────────────────────────────┤
│ 真实 8 步（来自后端 step）· 排队/生成/完成/失败 · 可重试      │
│ 刷新页面后按 session_id 恢复轮询（不做假进度条）              │
├ 课堂区 ───────────────────────────────────────────────────┤
│ 可信 iframe（origin 精确匹配）或"安全新窗口打开"             │
├ 历史区 ───────────────────────────────────────────────────┤
│ 本课程历史课堂：形态 · 状态 · 生成时间 · [继续学习] [重试]    │
└───────────────────────────────────────────────────────────┘
```

**教师工作台语气清除**：不出现"课程名/班级/学员管理/发布/工作台/大纲编辑"等词；
`stages`/`publish`/`workbench` 相关能力一律不暴露（已在 §4 排除）。

**页面文案约束（因 F1/F2）**：形态按钮下方必须有统一说明——
"将由系统根据课程内容自主组合讲解、测验、实验、可视化等形式"，
不得写"生成一个思维导图"这类承诺。生成完成后，用 §4 的"获取课堂"结果展示**真实**组成：
"本节包含：幻灯片 ×N · 测验 ×N · 互动实验 ×N · 项目式学习 ×N"。

### 5.2 学生流程（与任务书一致）

进入课程 → 自动读取课程上下文（我方后端，不触网）→ 选择学习目标 → 选择/自动推荐内容形态
→ **明确点击生成** → 查看真实进度 → 打开课堂 → 回到历史继续 → CPM 依据当前课程与掌握情况继续指导。

### 5.3 九种学生形态 → 真实能力映射（适配层，不要求 OpenMAIC 改协议）

| 学生形态 | 我方 `mode` | 映射方式（requirement 提示词） | 期望产出（**仅用于 UI 提示与事后核对，不作保证**） |
| --- | --- | --- | --- |
| 自动推荐 | `adaptive` | 依据真实可用上下文选择并给出理由（§6.4） | 任意组合 |
| 概念讲解 | `explain` | 讲解 + 逐步推导 + 白板 | `slide` + `wb_*` actions |
| 练习测验 | `quiz` | 单选/多选/简答 + 解析 | `quiz` |
| 实验模拟 | `simulation` | 交互式模拟实验 | `interactive` + `widgetType=simulation` |
| 3D/可视化 | `visualization` | 3D 可视化 | `interactive` + `widgetType=visualization3d` |
| 思维导图 | `mindmap` | 知识结构图 | `interactive` + `widgetType=diagram, diagramType=mindmap` |
| 编程实验 | `coding` | 在线编程练习 | `interactive` + `widgetType=code` |
| 项目式学习 | `pbl` | PBL 目标/角色/里程碑/交付物 | `pbl` |
| 考前复习 | `review` | 覆盖薄弱点 + 高频考点 + 自测 | 任意组合 |

**向后兼容**：保留旧名 `explore → simulation`、`practice → quiz`、`project → pbl`，
在 schema 边界归一化并记 deprecation 日志；现有 Web/Android/后端测试不因改名而红。

---

## 6. 数据、安全与失败语义

### 6.1 权限与隔离

- 全部端点必须 `current_user`（未登录 401）。
- 课程可见性**只**经 `services/course_access.can_view_course`；非学生角色 → 403（沿用现有 `Forbidden("仅学生可生成互动课堂")`）。
- 存储隔离：`{user_id}/{course_id}/` 目录；`result_store.get_session` 会二次校验归属（`result_store.py:253`）。
- 生成预占：同一 `(user_id, course_id)` 同时只允许一个 active session；`O_CREAT|O_EXCL` 原子预占 + 租约 TTL + steal。
- 并发/幂等：相同 `(mode, objective, context_hash)` 的重复提交 → 复用 active session，不重复计费。

### 6.2 上下文（阶段 2）

复用 `build_course_context` / `build_cpm_course_block`，新增**每类集合的硬上限**与来源标注：

| 集合 | 上限 | 来源标注 |
| --- | --- | --- |
| 课程头部（名称/代码/学期/教师名） | 200 字符 | 本地 DB |
| 章节 | 20 条 | 学习通同步 |
| 知识点 + 本人掌握率 | 20 个点 / 8 个标签 | `chaoxing_knowledge_points`（**仅本人**） |
| 资料标题 + 类型 + 允许正文摘要 | 15 条 / 每份 ≤ 800 字符 | 课程资料 |
| 作业/考试主题 + 状态 + 截止 | 15 条 | 本地 DB |
| 学生自述（目标/困惑/时长/难度/练习需求） | 各 ≤ 500 字符 | 本次请求 |
| 总上限 | `OPENMAIC_COURSE_CONTEXT_MAX_CHARS`（默认 4000） | 超出截断并标 `[已截断]` |

**禁止发送**：其他学生数据、教师私人数据、ACCESS_CODE、登录 Cookie、JWT、无关课程、原始 DB 记录、
不受控大文件、学生私人对话全文。`requirement_builder` 的现有守卫句
"不得把生成内容当作学校官方规定或考试事实"保留。
**无真实资料时不伪造**：`pdfContent.text` 为空串，并在 requirement 中显式说明"本课程暂无可用资料正文"。

### 6.3 凭据与 URL 安全

- `OPENMAIC_ACCESS_CODE` 只被 `client.py` 读取；**不得**出现在任何响应模型、日志、`result_store` 落盘、前端产物、Android 模型中。
  阶段 7 增加自动扫描测试：遍历所有响应 JSON 与落盘 JSON，断言不含 access code / `Cookie` / `Authorization` / 内部 URL / Provider Key。
- 返回 URL 校验（已有，保留并强化）：`urlparse` 比 `scheme + netloc`（**含端口**）→ 路径必须 `/classroom/{id}` 单段且尾段 == `classroomId` → 无 query/fragment/params。
- **新增**：下发前用 `OPENMAIC_EMBED_ORIGIN` **重写** origin，禁止把内部 origin 交给浏览器。
- **新增**：SSRF 防护——`OPENMAIC_BASE_URL` 必须是 http(s) 且无用户名/密码/query/fragment（已有，`config.py:349-354`），
  并新增"不得为 `0.0.0.0`/元数据地址"的校验；我方**不做**任意 URL 代理（不使用 `/api/proxy-media`）。
- **浏览器永不接触 ACCESS_CODE**：方案 A 下浏览器只需课堂页；方案 B 下凭据留在服务端反代。

### 6.4 `adaptive` 的真实决策（不能永远固定一种）

输入：`weak_points`（本人掌握率最低的知识点）、`upcoming_exams`（14 天内）、`material_availability`、`recent_modes`（历史课堂形态分布）。
规则（确定性、可测试、可解释）：

1. 14 天内有考试且存在薄弱点 → `review`
2. 有薄弱知识点且该点存在可交互资料 → `simulation`（否则 `quiz`）
3. 无薄弱点但有章节且从未生成过 → `explain`
4. 其余 → 在未使用过的形态中按 `quiz > visualization > mindmap > coding > explain` 轮转

返回 `adaptive_reason`（人类可读，如"你在『极限的ε-δ定义』掌握率 32%，且 9 天后有期中考试"）
与 `chosen_mode`。**必须**在响应中回传，供 UI 显示"为什么推荐这个"。

### 6.5 失败语义（每一条都要有独立、可执行的 UI 提示）

| 场景 | 后端判定 | HTTP / 字段 | 学生提示 |
| --- | --- | --- | --- |
| 未配置 | `configured=false` | 200 `status`；`generate` → 503 `OPENMAIC_NOT_ENABLED` | "本课程尚未开启智能辅导" |
| 服务不可达 | 健康探测超时/连接失败 | `available=false, unavailable=true, reason` | "辅导服务暂时离线，课程其他功能不受影响" |
| 版本/契约不兼容 | 契约指纹不匹配 | `compatibility="incompatible"` | "辅导服务版本不匹配，已暂停生成（请联系管理员）" |
| 能力降级 | 健康通过但图像/TTS/ASR 部分不可用 | `degraded=true, capabilities{...}` | "部分能力不可用（无语音/无图像），仍可生成其他形式" |
| 登录态失效 | JWT 过期 | 401（沿用项目刷新语义） | 重新登录 |
| 无课程上下文 | 无章节/无知识点/无资料 | 200 + `context_state="empty"` | "该课程暂无可用学习资料，生成结果可能较泛" |
| 生成失败 | `status=failed` | `error_code` + `retryable=true` | 显示原因 + [重试] |
| 部分生成 | `scenesGenerated < totalScenes` 且终态成功 | `partial=true` | "部分内容生成失败，可查看已生成部分或重试" |
| 超时 | 轮询超过 `OPENMAIC_POLL_MAX_SECONDS` | 我方停止轮询，`status` 保留最后已知值 | "生成时间较长，可稍后回历史查看" |
| 不可信 embed origin | 返回 URL origin ∉ 白名单 | 后端**拒绝下发** URL；`embed_origin=null` | 只提供"安全新窗口打开"，不渲染 iframe |
| iframe 被拦截 | 前端 `iframe.onerror` / 超时未 load | 前端降级 | "浏览器阻止了内嵌，请在新窗口打开" |
| 3D 需外网 | — | 部署文档说明 | "3D 内容需要访问外部 CDN" |

**关键原则**：外部服务异常**不得**伪装成"空结果"。`status` 必须能区分
`configured / available / unavailable / incompatible / degraded / not_bound`。

### 6.6 iframe 沙箱策略（回应"不要无条件同时启用 allow-scripts 和 allow-same-origin"）

- 收紧为：`sandbox="allow-scripts allow-same-origin allow-forms"`，**移除** `allow-popups`、`allow-downloads`。
- `allow-same-origin` **必须**保留（OpenMAIC 课堂页是 Next.js 应用，需要自身 origin 的 storage/cookie），
  但它**仅在跨源时安全**。因此加一条**硬断言**：
  - 后端：`OPENMAIC_EMBED_ORIGIN` 必须 ≠ Web 站点 origin，否则启动即失败（配置校验）；
  - 前端：`assert(urlOrigin(safeUrl) !== window.location.origin)`，不满足则拒绝渲染 iframe。
- 附加：`referrerpolicy="no-referrer"`、`loading="lazy"`，不设 `allow="*"`。
- 学生私人数据不得进入课堂页 URL（无 query 参数，已有校验保证）。

---

## 7. 许可证与版本策略

### 7.1 记录在案的事实

| 项 | 结论 |
| --- | --- |
| 参考仓库 commit/tag | 该目录**不是 git 仓库**（无 `.git`），无法取 commit。可记录的版本标识：根 `package.json` `version: 1.0.1`；`CHANGELOG.md` 最新条目 `## [1.0.1] - 2026-09-06`；`.nvmrc` = `22` |
| 许可 | MIT，`Copyright (c) 2026 THU-MAIC`（`LICENSE:3`） |
| 历史许可 | **v0.3.0（2026-06-28）由 AGPL-3.0 改为 MIT**（`CHANGELOG.md:198`）。**若将来固定到 <0.3.0 的 tag，将继承 AGPL-3.0 义务** |
| 是否复制任何包/源码 | **本轮不复制任何代码、SDK、组件或素材**。仅独立部署 + HTTP 契约对齐 |
| 是否 vendor 整仓库 | 否。独立部署优先 |
| `@openmaic/*` SDK | **不使用**。npm 上确有 `dsl@0.11.1`/`generation@0.3.7`/`renderer@0.1.7`/`storage@0.29.1`/`editor@0.0.5`/`importer@0.2.0`（均 MIT），且 peer 允许 `react >=18`。**但**本轮只走 HTTP，不引入任何 npm 包 |
| React 版本冲突 | OpenMAIC 应用是 **React 19.2.3**，CampusMate Web 是 **React 18.3.1**。**禁止混装**其组件。本轮 Web 侧只做 iframe 嵌入，不 import 任何 `@openmaic/*` |

### 7.2 独立部署时下游必须履行的许可义务（写入部署文档）

1. 随部署分发根 `LICENSE`（MIT, © 2026 THU-MAIC）。
2. `mathml2omml` 是 **LGPL-3.0-or-later**，且经 `next.config.ts:29` `transpilePackages` **打包进应用 bundle** →
   需随附 LGPL 全文与该库源码，并允许替换。
3. `public/vendor/gsap.min.js` 是 **GreenSock Standard License**（非 OSI 许可），随镜像与每个导出 ZIP 分发 →
   需附 GSAP 许可说明。仓库内**没有**该许可文本。
4. 若自托管 CJK 字体，需原样保留 `packages/@openmaic/renderer/font-licenses/{ARPHIC-PL.txt, OFL.txt, ZcoolHappy-LICENSE.txt}`。
   注意：字体**二进制不在仓库里**，`fonts.css` 指向第三方主机 `https://file.maic.chat/fonts/*` —— 这是运行期外部依赖。
5. `public/logos/*`（35 个第三方商标）与 `public/avatars/*`（33 个图，**无任何许可/出处证据**）需自行评估。
6. 仓库**不提供** `NOTICE`/`THIRD-PARTY` 文件，需自建。

### 7.3 版本兼容策略（诚实版）

**问题**：Docker 镜像 `CMD ["node","server.js"]` 不经过 npm 脚本，`npm_package_version` 为空，
`GET /api/health` 会返回硬编码回落值 **`0.1.0`**，而非真实的 `1.0.1`。
因此**不能**用版本字符串做兼容判定。

**设计**：`incompatible` 由**契约指纹**决定，版本字符串只记录用于审计。

契约指纹 = 三个**只读、零成本、无副作用**的探针全部通过：

| # | 探针 | 期望 | 失败含义 |
| --- | --- | --- | --- |
| P1 | `GET /api/health` | 200，`success===true`，`status==='ok'`，`capabilities` 是 bool 字典 | 基础契约不匹配 |
| P2 | `GET /api/access-code/status` | 200，`success===true`，含 `enabled: boolean` | ACCESS_CODE 机制不匹配 |
| P3 | `GET /api/generate-classroom/__probe__` | **404** 且 `errorCode==='INVALID_REQUEST'` 且 `error` 含 `not found` | 作业族不存在或语义已变 |

P3 的设计依据：`app/api/generate-classroom/[jobId]/route.ts:20-27` 对非法/未知 id 明确返回
404 `INVALID_REQUEST` "Classroom generation job not found"，且**不创建任何作业**。
这是在不产生成本、不写数据的前提下证明该端点族存在与语义稳定的最稳办法。`__probe__` 满足
`/^[a-zA-Z0-9_-]+$/` 但必然不存在，因此走"not found"分支。探针结果缓存
`OPENMAIC_PROBE_TTL_SECONDS`（默认 60），不参与生成热路径。

**版本范围**：`OPENMAIC_ALLOWED_VERSIONS`（默认 `>=1.0.0 <2.0.0`，semver）。
`version` 能解析为 semver 且越界 → `incompatible`；
解析不出（如容器里的 `0.1.0` 之外的脏值）或为已知回落值 → 记 `version_source="unknown"`，
**不**判 `incompatible`，由契约指纹兜底。建议运维用 `pnpm start` 或显式 `ENV npm_package_version` 让版本可信。

---

## 8. 文件级变更计划（阶段 1–7）

> 提交切分：**阶段 1** = 部署/后端可观测性（1 个原子提交）；**阶段 2+3** = 后端编排与上下文（1 个）；
> **阶段 4** = Web（1 个）；**阶段 5** = CPM 受管作业（1 个，含 Web 确认卡）；**阶段 6** = Android（1 个）。
> 每次提交只 `git add` 本阶段明确路径。

### 阶段 1 — 部署与可观测状态

| 动作 | 文件 |
| --- | --- |
| 改 | `backend/app/core/config.py`（新增配置，见下） |
| 改 | `backend/.env.example` |
| 新 | `backend/app/services/openmaic/compatibility.py`（契约指纹 + 版本范围） |
| 改 | `backend/app/services/openmaic/client.py`（`probe()`、独立健康超时、能力明细） |
| 改 | `backend/app/services/openmaic/classroom_service.py`（`status()` 增加 `compatibility/degraded/capabilities/checked_at`） |
| 改 | `backend/app/schemas/openmaic.py`（`OpenMAICStatusOut` 扩展） |
| 新 | `docs/openmaic-deployment.md`（部署文档，**无本机路径**） |
| 新 | `deploy/openmaic/.env.openmaic.example`（脱敏模板） |
| 新 | `backend/tests/test_openmaic_observability.py` |

新增配置（全部 `OPENMAIC_` 前缀，复用现有 `Settings`，不造同义项）：

```
OPENMAIC_EMBED_ORIGIN              # 浏览器公开 Origin（与内部 BASE_URL 分离，必填才有 iframe）
OPENMAIC_EMBED_ENABLED             # 是否允许浏览器内嵌（默认 true；方案 B 下可关）
OPENMAIC_HEALTH_TIMEOUT_SECONDS    # 健康/探针超时（默认 5，与请求超时分离）
OPENMAIC_PROBE_TTL_SECONDS         # 契约指纹缓存（默认 60）
OPENMAIC_ALLOWED_VERSIONS          # 默认 ">=1.0.0 <2.0.0"
OPENMAIC_POLL_INTERVAL_MS          # 默认 5000（对齐 OpenMAIC）
OPENMAIC_POLL_MAX_SECONDS          # 默认 1800
OPENMAIC_ENABLE_IMAGE / _VIDEO / _TTS / _WEB_SEARCH   # 运维级能力总开关（与健康能力取与）
OPENMAIC_MATERIALS_MAX_ITEMS / OPENMAIC_MATERIAL_TEXT_MAX_CHARS
```

### 阶段 2 — 课程上下文与多样化生成

| 动作 | 文件 |
| --- | --- |
| 改 | `backend/app/services/openmaic/course_context.py`（每类集合上限、来源+更新时间、资料正文摘要） |
| 改 | `backend/app/services/openmaic/requirement_builder.py`（9 形态 + 3 旧名归一 + 学生输入 + `adaptive` 规则） |
| 改 | `backend/app/schemas/openmaic.py`（`OpenMAICGenerateRequest` 扩展） |
| 新 | `backend/tests/test_openmaic_generation_modes.py` |

### 阶段 3 — 编排、历史与真实组成

| 动作 | 文件 |
| --- | --- |
| 改 | `backend/app/services/openmaic/classroom_service.py`（`error_code`/`retryable`/`terminal`/`partial`） |
| 新 | `backend/app/services/openmaic/composition.py`（只读 `GET /api/classroom?id=` → 真实场景组成） |
| 改 | `backend/app/api/routes/openmaic_classroom.py`（新增"获取课堂"只读端点） |
| 改 | `backend/app/schemas/openmaic.py`（`OpenMAICClassroomCompositionOut`） |
| 改 | `backend/tests/test_openmaic_classroom.py`、`test_openmaic_student_integration.py`（含补上 `test_no_permission_course_rejected` 空壳） |

### 阶段 4 — Web 学生化体验

| 动作 | 文件 |
| --- | --- |
| 改 | `webreact/src/components/interactive/InteractiveClassroomPanel.jsx` |
| 新 | `webreact/src/components/interactive/ClassroomEmbed.jsx`（origin 硬断言 + 收紧 sandbox + 降级） |
| 改 | `webreact/src/data/interactiveClassroom.js`（9 形态 + 3 旧名归一 + 失败语义映射） |
| 改 | `webreact/src/data/api.js`（新增"获取课堂"） |
| 改 | `webreact/src/pages/CourseDetailPage.jsx`（状态条 / 继续学习） |
| 改 | `webreact/tests/interactive-classroom.test.mjs` |
| 新 | `webreact/tests/e2e/interactive-classroom-e2e.py`（当前**完全没有** mentoring 页签的 E2E） |

### 阶段 5 — CPM 受管作业

| 动作 | 文件 |
| --- | --- |
| 改 | `backend/app/schemas/agent_runtime.py`（`job_kind` 正则加 `interactive_classroom`） |
| 新 | `backend/app/services/agent_runtime/handlers/interactive_classroom.py` |
| 新 | `backend/app/services/agent_runtime/tools/interactive_classroom.py` |
| 改 | `backend/app/services/agent_runtime/capabilities.default.json`（新能力 + 工具声明） |
| 改 | `backend/app/services/container.py`（注册 handler + executor 工具，**必须在 `freeze()` 之前**） |
| 改 | `backend/app/api/routes/counselor.py`（结构化 `suggested_actions`，不新增生成入口） |
| 改 | `webreact/src/pages/CounselorPage.jsx`（提案确认卡 → 走 `/agent-jobs` → 深链） |
| 新 | `backend/tests/test_cpm_interactive_classroom.py` |

工具语义（最终名服从现有 `resource.action` 约定）：
`interactive_classroom.inspect_context`（AUTO_SAFE）、`interactive_classroom.list`（AUTO_SAFE）、
`interactive_classroom.propose`（AUTO_SAFE，只返回方案）、`interactive_classroom.generate`（**CONFIRM_REQUIRED + 审批门**）、
`interactive_classroom.status`（AUTO_SAFE）、`interactive_classroom.open`（AUTO_SAFE，只返回我方深链）。
**不重复注册**已有工具（现有 18 个，其中 16 个无 executor）。

### 阶段 6 — Android

| 动作 | 文件 |
| --- | --- |
| 新 | `android/app/src/main/java/com/example/campusai/data/remote/ClassroomUrlPolicy.kt`（Origin 白名单） |
| 改 | `.../data/remote/ApiService.kt`（status/generate/jobs/retry/classroom DTO 与端点） |
| 改 | `.../data/repository/AppRepository.kt` |
| 改 | `.../ui/screens/courses/CoursesScreen.kt`（课程详情加"智能辅导"区） |
| 改 | `.../ui/screens/counselor/CounselorScreen.kt`（提案卡/进度/深链；课堂打开改走策略校验） |
| 新 | `android/app/src/test/java/com/example/campusai/data/remote/ClassroomUrlPolicyTest.kt` 等 |

---

## 9. 状态机（CampusMate 侧，`session.status` 对外投影）

```
                     ┌──────────── (configured=false) ─────────► NOT_CONFIGURED (503 on generate)
                     │
   [请求生成] ──► RESERVED ──提交成功──► QUEUED ──► RUNNING ──► SUCCEEDED
                     │                     │           │
                     │                     │           ├──► FAILED (error_code, retryable)
                     │                     │           └──► (轮询超时) STALE_POLLING → 保留最后已知状态
                     │                     └──► FAILED
                     └──提交失败(OpenMAICUnavailable/Auth/Protocol) ──► FAILED + 释放预占
```

- `RESERVED` 不是对外状态，是 `result_store` 的 `.active.json` 预占（租约 TTL 600s，轮询续租，超时允许 steal）。
- 对外 `status` 取值：`queued | running | succeeded | failed`（与 OpenMAIC 一致，不新增虚构值）。
- 对外 `step` 取值：`queued | failed |` 8 个生成步骤（白名单外回落，**不伪造**）。
- 终态：`succeeded | failed`。`partial` 是 `succeeded` 上的附加标志（`scenesGenerated < totalScenes`）。
- 重试：只允许在终态上发起；非终态 → `accepted=false` + 当前状态（已有实现，保留）。
- 取消：**无**。UI 仅"停止查看"。

---

## 10. 测试计划

### 后端（pytest，按影响域子集跑，避免 basetemp 并发假失败）

必须覆盖：未登录 401；无课程权限 403/404（**补上现有空壳**）；跨用户/跨课程隔离；
`configured / available / unavailable / incompatible / degraded` 五态；契约指纹三探针各自失败路径；
真实请求字段对齐（只发 `requirement`/`pdfContent`/4×enable*/`agentMode`，**不含**任何 Key）；
9 形态 + 3 旧名归一 + `adaptive` 规则（多组输入产出不同 `chosen_mode`，且 `adaptive_reason` 非空）；
同请求幂等（并发只创建一个 active session，复用现有线程池用例）；失败保留已有结果；
retry / history / 裁剪不删运行中；不可信 URL（含同主机不同端口）被拒；`embed_origin` 重写为公开 Origin；
ACCESS_CODE 不进响应/日志/落盘；上下文限长与脱敏（不含他人知识点）；外部失败不伪装为空；
CPM 未确认不得生成 / 确认后才生成；LLM/工具不能绕过课程访问策略。

### Web

`node --test tests/*.test.mjs` 覆盖：全部状态真实渲染；9 形态；搜索/历史/恢复/重试；
可信与不可信 iframe（含 origin 等于父页面时必须拒绝）；点击生成→轮询→刷新恢复；
CPM 建议→确认→生成→完成深链；账号切换时在途请求不串数据；服务离线不影响其他页签。
新增 Playwright E2E 覆盖 mentoring 页签（当前缺失）。

### Android

`DTO 不含凭据`（扩展现有断言到新 DTO）；课程 ID 与 session ID 正确传递；CPM 确认门；
旋转/恢复不重复创建；**URL 白名单**（新）；WebView/外部浏览器安全；降级状态。

### 验证命令

- Backend：`cd backend && ./.venv/Scripts/python.exe -m pytest tests/<相关文件> -q`（给出精确文件与通过数）
- Web 单测：`cd webreact && node --test tests/*.test.mjs`
- Web 构建：`npx vite build --outDir <仓库外唯一目录> --emptyOutDir`
- Android：`cd android && JAVA_HOME=<repo>/android/.tools/jdk21-full/jdk-21.0.12+8 ./gradlew :app:testDebugUnitTest`，
  并检查 `app/build/test-results/testDebugUnitTest/*.xml` 的 failures/errors 数量
- 收尾：`git diff`、`git diff --cached`、`git status`；扫描密钥/本机路径/构建产物/临时文件

### 真实端到端联调（阶段 7）

按任务书 9 步执行。**当前已确认的阻塞**：本机无真实 OpenMAIC 部署、无 ACCESS_CODE、无独立 LLM Key 环境。
因此阶段 7 只能完成"代码 + 契约测试 + 可离线验证"，真实联调结果必须如实标注为**未执行**，
不得用 mock 课堂冒充真实生成。

---

## 11. 需要批准才能进入阶段 1 的决策点

| # | 决策 | 我的建议 |
| --- | --- | --- |
| **D1** | 课堂页访问路径：方案 A（可信子域 + 关 ACCESS_CODE + 网络层保护）vs 方案 B（保留 ACCESS_CODE + 我方反代整个 SPA） | **A**。B 的成本与脆弱性远超收益；A 的残余风险（能到子域即可按 id 看课）用短时签名路径/网段限制缓解 |
| **D2** | 学生形态集合：把 `mode` 从 5 个扩展为 9 个，并保留 `explore/practice/project` 作旧名归一 | **接受**。不改名会与任务书不一致；不保留旧名会打破现有测试 |
| **D3** | CPM 触发生成的路径：经 `/api/v1/agent-jobs` 新 `job_kind=interactive_classroom` + handler + 审批门（需改 `job_kind` 正则）vs 在 counselor 内直连服务 | **前者**。后者违反"必须过 ToolInvocationGateway、禁止 LLM 直连 OpenMAICClient" |
| **D4** | 是否接受"类型不可保证"这一事实，并把 UI 文案改为事后如实报告真实组成 | **接受**。这是 F1/F2 的必然结果；任何"点思维导图就得到思维导图"的承诺都是假的 |
| **D5** | 是否在阶段 1 一并实现 MP4 导出（需 `render-service`） | **不做**，列入 backlog。它对核心学习流程非必需，且会显著扩大验证面 |
| **D6** | 3D 依赖外网 `unpkg.com` 是否可接受 | 需你确认。若学生网络不可达外网，3D/可视化形态应在 UI 上标注"可能不可用"或直接隐藏 |

---

## 附：审计期间对参考目录的改动

**没有。** 全部操作均为只读（`ls` / `cat` / `sed -n` / 文件读取），未创建、修改、删除、格式化任何文件，
未在该目录执行任何写入型命令。
