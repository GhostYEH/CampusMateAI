# OpenMAIC 与 CampusMate 课程场景融合设计

**状态：** 已批准实施基线

**日期：** 2026-09-18

**正式来源：** `THU-MAIC/OpenMAIC` tag `v1.0.3`，commit `e693e11a81644f84c258df73dbda378643520a62`

**实施索引：** `docs/superpowers/plans/2026-09-18-openmaic-campus-fusion.md`

## 1. 目标

把 OpenMAIC 的内容生成、编辑、播放、材料处理、导入导出、白板、语音和多智能体能力融合进 CampusMate，而不是并排运行第二个网站。

用户最终获得两条入口：

1. CampusMate `/courses` 页面右侧显示“我的课程”，每门课程可直接发起询问并进入对应 OpenMAIC 工作台。
2. 课程作业详情页可基于课程、作业、附件和用户权限生成讲解，并可继续编辑、播放或追问。

OpenMAIC 原有功能布局先保持一致；颜色、字体、圆角、间距和响应式断点适配 CampusMate 主题。

## 2. 非目标与硬约束

- 不使用整站 `iframe`。
- 不保留第二套登录、用户、课程或权限体系。
- 不让浏览器同时加载 React 18 和 React 19。
- 不把本地参考目录作为运行时依赖或可发布来源。
- 不直接读取 CampusMate 数据库，也不修改 CampusMate 现有数据库结构。
- 不删除现有课程、作业、互动课堂或其他端能力。
- 不在浏览器暴露 Provider 密钥、内部服务密钥或原始文件路径。
- 功能默认受 `OPENMAIC_FUSION_ENABLED` 控制；关闭时现有路径保持原行为。

## 3. 来源与许可证门禁

正式迁移只以固定 commit 为基线。实施第一阶段必须完成：

1. 验证 tag 指向固定 commit。
2. 保存上游许可证、NOTICE、依赖许可证摘要和源码清单。
3. 对本地参考副本执行逐文件 `git diff --no-index`，把差异分类为视觉参考、可移植修改、未知来源和禁止复制。
4. 未通过来源或许可证审计的文件不得进入产品代码。

本地参考副本仅用于视觉和交互比对；它的版本号、依赖版本和文件内容不能替代正式来源。

## 4. 运行边界

### 4.1 Web 客户端

`webreact/` 是唯一浏览器入口和唯一浏览器 React 运行时。OpenMAIC 的页面与组件按文件级迁移到 `webreact/src/features/openmaic/`，并改为复用 CampusMate 的路由、主题、请求封装和登录状态。

Web 客户端负责：

- `/courses` 融合首页和右侧课程栏。
- 工作台、编辑器、播放器、材料、导入导出和设置界面。
- 作业讲解入口与讲解结果展示。
- 对后端公开 API 的调用和 SSE 消费。

### 4.2 FastAPI

FastAPI 是公开 API 网关和授权权威，负责：

- 校验 CampusMate 登录态。
- 校验用户对课程、作业和附件的访问权。
- 组装最小化课程上下文。
- 签发短期内部断言并代理到 OpenMAIC 服务。
- 统一错误模型、审计日志和限流。

### 4.3 OpenMAIC 服务

仓库新增受管的 `openmaic-service/`，使用 Node.js 22.19 或更高版本。它只承担服务端能力，不输出独立公开站点：

- 智能体运行、流式事件、取消和重试。
- Stage 文档、编辑命令、播放清单和版本冲突处理。
- 材料解析、导入导出、生成模式、白板、TTS、ASR 和多智能体编排。
- Provider 配置和独立持久化。

MP4 导出复用固定 upstream 中的 Chromium/FFmpeg 渲染能力，迁移到仅内网可达的 `openmaic-render-service/`。它只接受 OpenMAIC 服务签发的一次性 render job，不接受浏览器请求，也不拥有用户或课程权限逻辑。

## 5. 身份、课程绑定与授权

FastAPI 到 OpenMAIC 服务使用 HMAC-SHA256 内部断言。载荷固定为：

```ts
type ServiceAssertion = {
  iss: "campusmate-backend";
  aud: "openmaic-service";
  sub: string;
  course_id: string;
  scope: string[];
  iat: number;
  exp: number;
  jti: string;
};
```

断言有效期不超过 60 秒；服务端校验签名、受众、时间窗、课程、scope，并在高风险写操作中防止 `jti` 重放。

课程与 Stage 的绑定由服务端创建：

```ts
type StageBinding = {
  userId: string;
  courseId: string;
  stageId: string;
  createdAt: string;
  updatedAt: string;
};
```

唯一键为 `(userId, courseId)`。浏览器不能自行指定或覆盖 `stageId`。

## 6. 共享领域契约

### 6.1 Stage 文档与编辑命令

```ts
type StageDocument = {
  stageId: string;
  revision: number;
  title: string;
  scenes: Array<{
    id: string;
    kind: "slide" | "quiz" | "interactive" | "pbl";
    title: string;
    elements: RenderElement[];
    widget?: {
      kind: "visualization-3d" | "simulation" | "game" |
        "mind-map" | "online-code" | "procedural-skill";
      document: Record<string, unknown>;
    };
  }>;
  assets: AssetReference[];
  updatedAt: string;
};

type EditCommand = {
  commandId: string;
  baseRevision: number;
  kind: "scene.add" | "scene.remove" | "scene.move" |
    "element.add" | "element.update" | "element.remove" |
    "timeline.update" | "document.rename";
  payload: Record<string, unknown>;
};

type EditCommandResult = {
  commandId: string;
  revision: number;
  document: StageDocument;
};
```

`commandId` 提供幂等性。`baseRevision` 不匹配返回 HTTP 409 和当前 revision；客户端刷新后显式重放，禁止静默覆盖。

### 6.2 播放契约

```ts
type PlaybackManifest = {
  stageId: string;
  revision: number;
  durationMs: number;
  scenes: Array<{
    sceneId: string;
    startMs: number;
    durationMs: number;
    elements: RenderElement[];
    narration?: AssetReference;
  }>;
};
```

编辑器和播放器共同消费 `StageDocument`，播放器只使用服务端生成的 `PlaybackManifest`，避免两套解释器漂移。

### 6.3 会话与流式事件

```ts
type FusionSession = {
  id: string;
  userId: string;
  courseId: string;
  stageId: string;
  mode: "standard" | "deep";
  status: "idle" | "running" | "completed" | "failed" | "cancelled";
};

type FusionEvent = {
  id: string;
  sessionId: string;
  type: "message.delta" | "message.completed" | "stage.updated" |
    "tool.started" | "tool.completed" | "run.failed" | "run.cancelled";
  sequence: number;
  data: Record<string, unknown>;
};

type SessionMessageRequest = {
  commandId: string;
  content: string;
  sceneKind: "auto" | "slide" | "quiz" | "interactive" | "pbl";
};
```

SSE 支持 `Last-Event-ID` 恢复；同一 session 的 `sequence` 单调递增。取消和重试是显式 API，不通过关闭页面隐式表达。

## 7. 公开 API

所有路径位于现有 `/api/v1` 下，并使用 CampusMate 登录态：

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/openmaic/fusion/status` | 功能开关、依赖健康和可用能力 |
| GET | `/openmaic/fusion/home` | 最近项目、文件夹和首页摘要 |
| GET | `/openmaic/projects?query=` | 搜索本人项目 |
| POST | `/openmaic/folders` | 新建文件夹 |
| PATCH | `/openmaic/folders/{folder_id}` | 重命名文件夹 |
| DELETE | `/openmaic/folders/{folder_id}` | 删除空文件夹 |
| POST | `/courses/{course_id}/openmaic/binding` | 幂等获取课程 Stage |
| GET | `/courses/{course_id}/openmaic/sessions` | 会话列表 |
| POST | `/courses/{course_id}/openmaic/sessions` | 创建会话 |
| POST | `/openmaic/sessions/{session_id}/messages` | 发送消息 |
| GET | `/openmaic/sessions/{session_id}/events` | SSE 事件流 |
| POST | `/openmaic/sessions/{session_id}/cancel` | 取消运行 |
| POST | `/openmaic/sessions/{session_id}/retry` | 重试失败运行 |
| GET | `/openmaic/stages/{stage_id}` | 获取 StageDocument |
| POST | `/openmaic/stages/{stage_id}/commands` | 应用编辑命令 |
| GET | `/openmaic/stages/{stage_id}/playback` | 获取 PlaybackManifest |
| POST | `/openmaic/stages/{stage_id}/materials` | 上传材料并创建解析任务 |
| GET | `/openmaic/materials/{material_id}` | 查询材料解析状态 |
| POST | `/openmaic/stages/{stage_id}/materials/search` | 检索 Stage 材料 |
| POST | `/openmaic/stages/{stage_id}/imports` | 导入文件 |
| GET | `/openmaic/imports/{job_id}` | 查询导入任务 |
| POST | `/openmaic/stages/{stage_id}/exports` | 创建导出任务 |
| GET | `/openmaic/exports/{job_id}` | 查询导出任务 |
| GET | `/openmaic/exports/{job_id}/download` | 下载本人导出结果 |
| POST | `/openmaic/speech/tts` | 创建或复用语音合成资产 |
| POST | `/openmaic/speech/asr` | 转写受限音频输入 |
| POST | `/openmaic/jobs` | 为受信 Agent/Skill 提交异步生成任务 |
| GET | `/openmaic/jobs/{job_id}` | 查询本人异步任务 |
| POST | `/openmaic/jobs/{job_id}/cancel` | 取消本人异步任务 |
| GET | `/courses/{course_id}/assignments/{assignment_id}/explain/plan` | 获取脱敏讲解计划 |
| POST | `/courses/{course_id}/assignments/{assignment_id}/explain` | 执行讲解 |
| GET | `/admin/openmaic/settings` | 管理员读取配置摘要 |
| PUT | `/admin/openmaic/settings` | 管理员更新非密钥配置 |

公开错误格式沿用 CampusMate。服务端错误映射必须区分 400、401、403、404、409、422、429、502 和 503。

## 8. 页面融合

### 8.1 `/courses`

现有课程页重构为一个页面壳：左侧保留 OpenMAIC 首页原有主功能布局，右侧固定“我的课程”栏。课程栏使用 CampusMate 真实课程数据，支持搜索、选课、快捷提问和进入课程工作台。窄屏时课程栏变为抽屉，但信息层级不变。

### 8.2 工作台

工作台保留 OpenMAIC 的会话区、舞台区、材料区和工具区布局。导航、面包屑、主题、空态、错误态和权限提示使用 CampusMate 组件。刷新后通过 session、stage 和 SSE 游标恢复状态。

### 8.3 作业讲解

作业详情页先请求 `explain/plan` 展示将使用的题目、附件和课程资料摘要，再由用户触发执行。后端只转发用户有权访问且已脱敏的内容。生成结果可继续追问、打开工作台、编辑或播放。

## 9. 数据与运维

OpenMAIC 服务使用独立 PostgreSQL schema 保存 binding、session、event、stage、asset、job 和 provider configuration。对象文件使用可配置存储；记录只保存对象键，不保存本机绝对路径。

启动顺序：数据库与对象存储 → OpenMAIC render service → OpenMAIC 服务 → FastAPI → Web。健康检查分为存活、就绪和依赖状态。Provider 或渲染器不可用不得让课程页整体失效；相关按钮显示明确降级原因。

日志必须包含 `request_id`、`user_id`、`course_id`、`stage_id` 和 `session_id`，不得记录原始密钥、完整课程材料或断言。

## 10. 逐项能力矩阵

状态只允许 `planned`、`implemented`、`verified`。实施计划完成前所有条目为 `planned`。

| # | 能力 | 上游依据 | CampusMate 入口 | 服务归属 | 验收重点 | 状态 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | 首页提示输入 | 首页输入区 | `/courses` 主区 | Web/FastAPI | 可选课程并发送 | planned |
| 2 | 深度生成模式 | 深度交互切换 | 首页与工作台 | Web/Node | 模式写入 session | planned |
| 3 | 最近项目 | 首页项目列表 | `/courses` 主区 | Node | 仅显示本人项目 | planned |
| 4 | 文件夹列表 | 首页文件夹 | `/courses` 主区 | Node | 分页与空态 | planned |
| 5 | 文件夹新建 | 文件夹操作 | 首页 | Node | 幂等创建 | planned |
| 6 | 文件夹重命名 | 文件夹操作 | 首页 | Node | 权限与冲突 | planned |
| 7 | 文件夹删除 | 文件夹操作 | 首页 | Node | 非空保护 | planned |
| 8 | 项目搜索 | 首页搜索 | 首页 | Node | 防抖与分页 | planned |
| 9 | 我的课程栏 | CampusMate 扩展 | `/courses` 右栏 | Web/FastAPI | 真实课程与响应式 | planned |
| 10 | 课程快捷提问 | CampusMate 扩展 | 课程卡片 | 全链路 | 自动绑定课程 | planned |
| 11 | 课程 Stage 绑定 | CampusMate 扩展 | 后台流程 | FastAPI/Node | 用户课程唯一键 | planned |
| 12 | 工作台布局 | 上游工作台 | 课程工作台 | Web | 布局与主题适配 | planned |
| 13 | 会话创建 | 上游会话 | 工作台 | FastAPI/Node | 用户课程隔离 | planned |
| 14 | 会话列表 | 上游历史 | 工作台侧栏 | Node | 分页与排序 | planned |
| 15 | 消息发送 | 上游对话 | 工作台 | Node | 请求幂等 | planned |
| 16 | SSE 流式输出 | 上游流式运行 | 工作台 | 全链路 | 断线续传与顺序 | planned |
| 17 | 刷新恢复 | 上游持久化 | 工作台 | Web/Node | session 与 stage 恢复 | planned |
| 18 | 运行取消 | 上游运行控制 | 工作台 | Node | 状态一致 | planned |
| 19 | 失败重试 | 上游运行控制 | 工作台 | Node | 不重复副作用 | planned |
| 20 | 课程上下文引用 | CampusMate 扩展 | 提问与生成 | FastAPI | 最小化且有权限 | planned |
| 21 | 材料上传 | 上游材料区 | 工作台材料区 | 全链路 | 类型、大小、病毒门禁 | planned |
| 22 | 材料解析 | 上游解析 | 工作台 | Node | 异步状态与失败原因 | planned |
| 23 | 材料检索 | 上游知识使用 | 工作台 | Node | 来源引用 | planned |
| 24 | Web 搜索 | 上游工具 | 工作台 | Node | 开关、超时、引用 | planned |
| 25 | 文档材料解析 | 上游材料解析 | 材料区 | Node | PDF/DOCX/MD/TXT 来源与页序 | planned |
| 26 | 表格材料解析 | 上游材料解析 | 材料区 | Node | 工作表边界与大小限制 | planned |
| 27 | 音视频内容抽取 | 上游材料解析 | 材料区 | Node | 时长、转写、资源限制 | planned |
| 28 | PPTX 保真导入 | 上游 PPTX importer | 首页/工作台 | Node | 原页布局、资源、去重回执 | planned |
| 29 | 课堂 ZIP 导入 | 上游课堂包 | 首页/工作台 | Node | 版本、哈希、离线资源 | planned |
| 30 | 技能/项目包导入 | 上游技能包 | 管理/工作台 | Node | zip slip 与膨胀限制 | planned |
| 31 | PPTX 导出 | 上游导出 | 播放器/编辑器 | Node | 可编辑元素、公式和图表 | planned |
| 32 | 自包含 HTML 导出 | 上游导出 | 播放器 | Node | 交互可用且无公网依赖 | planned |
| 33 | 课堂 ZIP 导出 | 上游课堂包 | 工作台 | Node | 可再次导入、媒体齐全 | planned |
| 34 | PDF/图片导出 | 上游导出 | 编辑器 | Node | 字体、分页、清晰度 | planned |
| 35 | 讲稿 Markdown 导出 | 上游讲稿导出 | 工作台 | Node | 场景和旁白顺序 | planned |
| 36 | 讲稿 DOCX 导出 | 上游讲稿导出 | 工作台 | Node | 标题与段落样式 | planned |
| 37 | MP4 视频导出 | 上游 render-service | 播放器 | Node/Renderer | Chromium/FFmpeg、进度、取消 | planned |
| 38 | 大纲生成与编辑 | 上游两阶段生成 | 工作台 | Web/Node | 生成前可编辑且顺序稳定 | planned |
| 39 | 幻灯片场景生成 | 上游 Slides | 工作台 | Node | Stage 命令与旁白 | planned |
| 40 | 测验场景生成 | 上游 Quiz | 工作台 | Node | 题型、答案和反馈 | planned |
| 41 | HTML 交互场景生成 | 上游 Interactive | 工作台 | Node | 沙箱与离线捕获 | planned |
| 42 | PBL v2 场景生成 | 上游 PBL | 工作台 | Node | 角色、任务、里程碑 | planned |
| 43 | 单选/多选/简答 | 上游 Quiz | 播放器 | Web/Node | 作答与恢复 | planned |
| 44 | AI 判分与反馈 | 上游 Quiz | 播放器 | Node | 评分依据与重试幂等 | planned |
| 45 | 3D 可视化 | 上游深度互动 | 编辑器/播放器 | Web/Node | 资源隔离与响应式 | planned |
| 46 | 模拟实验 | 上游深度互动 | 编辑器/播放器 | Web/Node | 参数与结果可重复 | planned |
| 47 | 互动游戏 | 上游深度互动 | 编辑器/播放器 | Web/Node | 状态重置与持久化 | planned |
| 48 | 思维导图/流程图 | 上游深度互动 | 编辑器/播放器 | Web/Node | 布局与缩放 | planned |
| 49 | 在线编程 | 上游深度互动 | 播放器 | Web/Node | 受限执行与超时 | planned |
| 50 | 职业学习技能组件 | 上游 procedural skill | 播放器 | Web/Node | 任务步骤与证据 | planned |
| 51 | AI 教师操作互动界面 | 上游引导动作 | 播放器 | Web/Node | 高亮、设值、提示可回放 | planned |
| 52 | 文本/公式/表格元素 | 上游场景元素 | 编辑器 | Web/Node | 编辑与播放一致 | planned |
| 53 | 图片/媒体元素 | 上游场景元素 | 编辑器 | Web/Node | 资源授权和回收 | planned |
| 54 | 代码元素 | 上游场景元素 | 编辑器 | Web/Node | 沙箱与高亮 | planned |
| 55 | 图表元素 | 上游场景元素 | 编辑器 | Web/Node | 数据与渲染一致 | planned |
| 56 | 画布直接编辑 | 上游专业编辑器 | 工作台 | Web | 拖拽、缩放、旋转、多选 | planned |
| 57 | 场景增删复制排序 | 上游编辑器 | 工作台 | Web/Node | revision 冲突 | planned |
| 58 | 元素属性编辑 | 上游编辑器 | 工作台 | Web/Node | 命令幂等 | planned |
| 59 | 旁白时间轴与动作 | 上游时间轴 | 编辑器 | Web/Node | 时长、动作顺序、TTS 预览 | planned |
| 60 | 撤销重做 | 上游编辑器 | 工作台 | Web | 命令栈边界 | planned |
| 61 | Edit with AI | 上游编辑智能体 | 编辑器 | Node | 校验式 patch 与确认 | planned |
| 62 | 编辑智能体会话历史 | 上游专业模式 | 编辑器 | Node | 会话隔离与恢复 | planned |
| 63 | 播放器 | 上游播放器 | 工作台/讲解 | Web/Node | manifest 一致性 | planned |
| 64 | 动作执行引擎 | 上游 action engine | 播放器 | Web | 语音、白板、特效顺序 | planned |
| 65 | 聚光灯与激光笔 | 上游课堂动作 | 播放器 | Web | 定位、清除、回放 | planned |
| 66 | 白板 | 上游白板 | 工作台 | Web/Node | 图形、公式、代码、保存恢复 | planned |
| 67 | TTS | 上游语音 | 工作台/播放器 | Node | 队列、并行、缓存、取消 | planned |
| 68 | 音色选择与克隆 | 上游语音 | 工作台设置 | Node | 授权音频和稳定音色 | planned |
| 69 | ASR | 上游语音 | 工作台输入 | Node | 权限、语言和失败态 | planned |
| 70 | 图片生成 | 上游媒体工具 | 编辑器/智能体 | Node | Provider 路由与资产登记 | planned |
| 71 | 视频生成 | 上游媒体工具 | 编辑器/智能体 | Node | Provider 路由、超时、资产登记 | planned |
| 72 | 课堂讨论 | 上游多智能体 | 播放器 | Node | 用户插话与恢复 | planned |
| 73 | 圆桌辩论 | 上游多智能体 | 播放器 | Node | 角色轮次和取消 | planned |
| 74 | 自由问答 | 上游多智能体 | 播放器 | Node | 当前场景引用 | planned |
| 75 | 多智能体编排 | 上游智能体 | 工作台 | Node | 可取消与可观测 | planned |
| 76 | PBL 角色/任务/里程碑 | 上游 PBL v2 | 播放器 | Web/Node | 进度与交付物 | planned |
| 77 | PBL 评价与学习状态 | 上游 PBL v2 | 播放器 | Web/Node | 评价事件和重启恢复 | planned |
| 78 | Provider/模型路由设置 | 上游设置 | 管理设置 | FastAPI/Node | 密钥不回传、能力强制关闭 | planned |
| 79 | 健康与能力发现 | 上游服务 | 管理设置 | 全链路 | 降级可见 | planned |
| 80 | 独立持久化 | 上游数据层 | 后台 | Node | 文档、运行时、设置重启恢复 | planned |
| 81 | 国际化 | 上游 i18n | 融合页面 | Web | 11 种语言/12 区域与 CampusMate 语言 | planned |
| 82 | 暗色主题与多设备 | 上游主题/响应式 | 全部页面 | Web | 桌面、平板、手机 | planned |
| 83 | 异步生成 Job API | 上游 Skill/API | 内部/工作台 | Node | 提交、轮询、取消、结果链接 | planned |
| 84 | 作业讲解计划 | CampusMate 扩展 | 作业详情 | FastAPI | 脱敏预览 | planned |
| 85 | 作业讲解执行 | CampusMate 扩展 | 作业详情 | 全链路 | 权限、引用、追问 | planned |
| 86 | 课程详情入口 | CampusMate 扩展 | 课程详情 | Web | 不破坏现有功能 | planned |
| 87 | 离线与错误态 | 融合要求 | 全部页面 | Web | 可恢复且不白屏 | planned |
| 88 | 功能开关与回滚 | 融合要求 | 全链路 | 全链路 | 关闭后旧行为不变 | planned |
| 89 | 来源/许可证完整性 | 迁移门禁 | 构建阶段 | 工具链 | 未登记上游文件阻止发布 | planned |

## 11. 验收门禁

功能完成必须同时满足：

1. 能力矩阵对应行更新为 `verified`，并有自动化测试或明确的浏览器证据。
2. 关闭功能开关后现有 CampusMate 行为不变。
3. 没有整站 iframe、第二登录、双 React 或本地目录运行时依赖。
4. FastAPI 权限测试覆盖跨用户、跨课程、越权附件和过期断言。
5. OpenMAIC 服务通过单元测试、类型检查、构建和重启恢复测试。
6. Web 通过单元测试、构建和关键 Playwright 流程。
7. 使用契约 Provider 完成可重复 E2E；真实 Provider 只作为最终补充验收，不阻塞日常开发。
8. 来源、许可证、依赖和安全审计均有可复查产物；固定 commit 中每个产品路由、页面、组件包和服务能力都必须映射到矩阵行或明确列为由 CampusMate 等价替代，存在未分类文件即阻止“完整融合”验收。
