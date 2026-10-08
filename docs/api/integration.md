# Web 接入约定与完整功能流程

[文档导航](README.md) · [字段字典](schemas.md) · [Web 调用对照](web-map.md)

## 基础请求

CampusMate HTTP 基础路径为 `/api/v1`。当前 Web 使用 `VITE_API_BASE_URL` 覆盖基础路径，默认同源 `/api/v1`；开发代理同时转发 `/api` 与 `/static`。新前端应把服务 Origin 放入配置，接口说明中的路径已经包含 `/api/v1`，不要重复拼接。

JSON 请求发送 `Content-Type: application/json`；上传使用 FormData；下载使用 Blob 或 ReadableStream；SSE 使用 authenticated fetch。普通 Axios 请求当前超时为 8 秒，任务拆解为 45 秒；异步任务创建后读取任务状态，不应把整个生成过程作为普通短请求等待。

```js
const base = "/api/v1";
const response = await fetch(`${base}/auth/me`, {
  headers: { Authorization: `Bearer ${accessToken}` },
  credentials: "include",
});
const payload = await response.json();
if (!response.ok) throw new Error(payload.message || "请求失败");
const user = payload.user;
```

响应没有全站统一的 `{data: ...}` 包装。普通对象、数组、`Page`、`{items,next_cursor}` 和二进制响应同时存在，按各接口契约读取。

<a id="auth"></a>
## 登录与凭据

1. 可选调用 `GET /health` 检查连接。注册用 `POST /auth/register`，只创建 student 用户，返回用户信息，不返回登录态。
2. `POST /auth/login` 发送 username/password，返回 TokenPair。保存 access_token 和 refresh_token，再 `GET /auth/me` 读取 `{user: ...}`。
3. 普通受保护接口带 `Authorization: Bearer <access_token>`。当前 Web 保存于 `campus_access_token`、`campus_refresh_token`；不要把 refresh token 发送到业务接口。
4. 本站 401 时用 `POST /auth/refresh` 的 `{refresh_token}` 换发一整对 token；旧 refresh token 被撤销。并发失败只发一次 refresh，失败清理登录态；旧请求不得覆盖后续登录的新账号。
5. `POST /auth/logout` 撤销 refresh token，并尝试撤销当前浏览器可信设备 cookie。可信设备相关请求带 cookie（当前 Axios `withCredentials:true`）；跨源接入需要服务端已有 CORS 配置允许该 Origin 和凭据。

扫码流程：浏览器 `POST /auth/qr/create` → 展示返回二维码并保留 browser_token → `GET /auth/qr/{session_id}/status`，头为 `x-browser-token` → 等待 CONFIRMED → `POST /auth/qr/exchange` 发送 session_id/browser_token → 保存 TokenPair。二维码只携带 session_id/scan_token，browser_token 只由创建二维码的浏览器持有；exchange 一次消费，不能重放。scan/confirm/cancel 也列在认证手册中，是配对协议的公开后端能力。

`POST /auth/trusted-device/auto-login` 使用 device_id 和 HttpOnly cookie；`GET /auth/trusted-devices`、revoke 管理已信任设备。扫码状态、错误和各字段见 [认证模块](01-auth.md)。

非法 access token（含非 ASCII 字符）在受保护 HTTP 接口返回 401，实时语音 WebSocket 握手关闭码为 1008。可信设备自动登录因凭据无效、撤销、过期或用户停用失败时，401 响应同时清除原 Cookie（`Path=/api/v1/auth`），浏览器仍须携带凭据接收响应，不能持续自动重试旧凭据。

系统仅提供 student 用户角色。历史 admin 账号和 Token 按普通用户权限解释，不具有跨用户、课程或学校特权。是否可操作资源还取决于所属用户、课程可见性、班级 active enrollment、发布状态等；有合法 token 不代表能访问任意 ID。旧 teacher 账号一般降级为 student，但 student_only 排除该兼容身份。

<a id="errors"></a>
## 统一错误与状态判断

普通业务异常与请求校验由 [全局异常处理器](../../backend/app/core/exceptions.py) 返回：

```json
{
  "code": "VALIDATION_FAILED",
  "message": "请求参数校验失败",
  "details": [{"type": "missing", "loc": ["body", "title"], "msg": "Field required"}],
  "request_id": "req_example"
}
```

| 字段 | 含义 |
| --- | --- |
| code | 稳定业务错误码；优先据此分支，避免匹配中文文案 |
| message | 可读错误描述；HTTPException.detail 在这里转换成 message，并非默认 `{detail:...}` |
| details | 可空对象 / 数组；校验失败为字段位置及原因，不回显输入 |
| request_id | 请求标识；同时读取 X-Request-ID 响应头以便定位 |

| HTTP | 前端处理 |
| --- | --- |
| 200 | 仍检查 mode/state/warnings/supported 等；HTTP 成功不能替代业务成功 |
| 201 | 资源创建成功；部分异步任务也在普通成功状态中返回 run，需要继续追踪 |
| 202 | 已接受任务；按返回的任务标识轮询，不表示生成完成 |
| 204 | 没有响应体；不要调用 response.json() |
| 400 / 422 | 参数、业务组合、格式或操作前置条件不满足；定位到具体字段 |
| 401 | 区分本站登录失效和学习通等外部连接失效 |
| 403 | 角色或资源权限不足 |
| 404 | 资源不存在，或为了隔离其他用户而返回不可见 |
| 409 | 重复、版本冲突、状态冲突、幂等冲突、同步进行中；回读资源并让用户重新决定 |
| 413 / 415 | 文件超限或格式不支持 |
| 429 | 频率限制；如存在 Retry-After 则使用该值 |
| 502 / 503 / 504 | 依赖服务失败、未配置或超时；保留其他功能并提供重试 |

例外：TTS 503 为兼容旧客户端会省略 body.request_id；壁纸代理直接构造 `{code,message,details}`；SSE 已建立后使用流内 error 事件；独立学习空间使用自己的响应信封。默认 OpenAPI 的 422 HTTPValidationError 并不代表真实全局错误响应。

正常业务错误与意外 500 响应均携带 `X-Request-ID`，允许的跨源请求也可读取 500 的 JSON 错误体。CORS 的端口通配只接受数字端口，域名通配只匹配一个 DNS 标签；精确 Origin 按字面匹配。

登录、注册及匿名聊天新增进程内限流，具体额度见 [认证](01-auth.md) 和 [AI 助手](10-assistant-knowledge.md)；429 返回 `RATE_LIMITED`、`details.retry_after_seconds` 与 `Retry-After`。测验保存的 409 统一为 `QUIZ_ATTEMPT_CONFLICT` 信封，见 [magic class](14-magicclass.md)。成功协议不变；源码核对覆盖四端调用，运行验证仅覆盖后端与 Web 调用对照，专门的重试倒计时和移动端真机流程尚未验证。

## 分页、时间、空值与表单

- 普通分页常见 `{items,total,page,page_size,has_more}`，page 从 1 开始；具体上限以接口参数表为准。社区分页没有 has_more，考试列表直接是数组。
- 受管工作台常用 `{items,next_cursor}` 与 limit/cursor；下一页使用返回的 cursor，不从本地索引构造。
- Agent 事件 REST 为数组，使用 **after_sequence / limit**。当前 Web 无 REST 事件封装；按手册发送 after_sequence，或复用 agentSseStream.js 的 SSE 订阅。
- 明确声明的 date-time 使用 ISO 8601 与时区；个人考试 exam_date/start_time/end_time 当前为字符串，建议发送 `YYYY-MM-DD` 与 `HH:mm`；部分舞台时间是毫秒数，按字段契约处理。
- PATCH 的“省略”和 null 不等价，例如 workspace.folder_id 省略为不修改、null 为取消归档、字符串为移动到文件夹。个人考试 PATCH 使用 ExamIn，必填字段与创建相同。
- unknown 字段是否拒绝由模型 additionalProperties 决定；Agent 契约普遍 `extra=forbid`，不能随意附带 UI 状态或调试信息。

## 首页、课程、待办与考试

首页用 `/dashboard/student`、`/agenda/today`、横幅接口及所需状态接口。首页、学习陪伴、任务总览和角标共用 `/agenda/today`，不要各自重新拼接出不同的“今日待办”。

课程详情先读 `/courses/{course_id}`、`/classes?course_id=...`，再读课程 content-summary/content、知识图谱及班级 assignments/announcements。远程内容和资源来自已同步资料；资源 open 返回外链，download 返回文件。先尊重 can_open/can_download、stale、warnings 等字段，再展示下载或重新同步。

个人待办 `/tasks` 与课程作业 `/assignments` 分开：个人待办有完成/恢复、导入分析/提交、重要度排序；作业有 draft submission、submit、附件及审核等独立状态。作业提交时先保存草稿取得 submission_id，再 `/submissions/{id}/submit`。公告已读调用 `/announcements/{id}/read`。前端不要用个人待办完成接口替代作业提交。

考试页面的手动记录来自 `/student/exams`；教务 `/edu/exam/items`、学习通远程考试和课程内容 exam_candidate 各有来源与状态，不把它们当成完全相同的数据模型。

## 通知提取与事务确认

简单通知流程：`POST /notices/extract` 提取原文 → 展示需确认字段 → 用户决定是否建立 `/tasks`。`/notices/ingest-batch` 是服务端批量文本接入，Web 可以查看处理后的记录，但当前 Web 不读取系统通知栏。

通知事务流程：`POST /notices/manual` 得到 notice_id → `POST /notices/{notice_id}/workflow` → 读 workflow 的动作及关联运行 → 对具体 action 调用 `/notice-workflow-actions/{action_id}/decision` → 获批准的 action 再调用 `/execute` → 回读结果。不能用旧 agentApi 的 `/notice-workflows/{id}/confirm` 或 `/execute`，这些路径未注册。

notification-sources 配置来源开关；workflow/reanalyze 支持重新分析。审批只表示授权某个动作，执行是另一个操作；拒绝、过期或不确定字段不能自动转换成执行。

## 学习陪伴、目标与计划

1. 日目标读写 `/study/goals/daily`；签到先确认 `/health` 的 study_checkins_supported，再读写 `/study/checkins`。
2. 进入页面先读 `/study/sessions/active`（无活动会话可返回 null），创建 session 后使用 pause/resume/finish，最终以服务端状态及持续时间为准。pause 的 reason 位于 query；finish 可携带主动自报等字段。
3. 任务拆解 `/study/task-breakdown` 可用 task_id 或 goal 文本，按请求字段及后端归属校验发送。拆解结果并不等于已建立待办，创建动作仍由用户触发。
4. 学习状态读 runs/snapshots/changes/evidence；显示投影范围、时间、来源和证据不足状态。预测读 forecasts，what-if 模拟调用 simulations，不把预测结果标为事实。
5. 通用目标使用 student-goals，记录进度、归档；计划使用 learning-plans generate → decision（ACCEPT/REJECT）→ execute，支持 undo/replan/feedback/evaluation/summary。生成和接受不等于已经执行；计划过期、状态陈旧或已有任务变化时按冲突码回读。
6. 异步 learning_goal Agent job 走 Agent 通道，不要误认为同步 learning-plans/generate 返回 run_id。自适应干预由服务端后台闭环产生，页面读取 interventions/outcome/decision 及实际采纳情况。
7. corrections、data-controls、delete-request/delete-status 提供用户的数据纠正、来源暂停与删除控制。按接口返回状态展示；请求删除不代表同步完成。

跨字段例：LearningPlanGenerateRequest 的 window_end 非空时必须同时给 window_start。所有枚举严格区分大小写，目标/计划与 Agent 运行的状态集合不通用。

<a id="chat"></a>
## 聊天 SSE 与数字人音频

`POST /counselor/chat` 与 `/assistant/chat` 是两个已注册别名，接受同一个 ChatRequest。stream=false 返回 [ChatFinalMeta](schemas.md#schema-chatfinalmeta)；stream=true 返回 `text/event-stream`：

| event | data |
| --- | --- |
| sources | `{sources:[ChatSource,...]}`；字段见 [ChatSource](schemas.md#schema-chatsource)，有来源才发，不保证出现 |
| chunk | `{text:"增量文本",mode:"..."}`，逐段拼接 text |
| done | 完整 ChatFinalMeta，包含 answer、来源、置信度、证据等级、需确认标记、建议动作、warnings 和 context 信息 |
| error | `{code:"RAG_ERROR",message:"..."}`；保留已收到文本并展示中断 |

```text
event: chunk
data: {"text":"你好","mode":"llm"}

event: done
data: {"answer":"你好", "sources":[], "mode":"llm", "warnings":[]}

```

上例仅示意 SSE 分帧，done 的完整字段以 ChatFinalMeta 为准。解码 UTF-8、处理跨网络块的 JSON、多行 data 和 CRLF；chunk 不保证与一次网络读取一一对应。done.answer 是最终权威文本，不要重复追加。当前聊天会检索知识库，LLM 未配置或失败可能降级；关注 mode、evidence_level、needs_human_confirmation。

recent_tasks 仅表示当前用户的 PersonalTask，后端重新读取权威字段；self_report 为自报。无权限上下文通常被忽略并返回 context_warnings；workspace_id 绑定要求已登录且带 course_id。课堂建议 suggested_actions 不自动生成课堂，需用户确认后创建对应 Agent job。

数字人文字转音频使用 `POST /assistant/tts`，请求 text/style；响应 `application/octet-stream`，PCM16LE、单声道。读取 X-Audio-Sample-Rate、X-Audio-Format、X-Audio-Channels；二进制流可能在一个 16bit 样本中间分块，播放端需缓存残留字节。数字人 Unity 资源位于 `/digital-human`；静音、重播和口型控制由 Web 完成。

<a id="agents"></a>
## Agent 运行与事件续传

先读取 `/agent-runtime/capabilities` 与 `/skills`；创建 `/agent-jobs` 得到关联 job/run，然后读取 job/runs/run 与事件。运行终态为 `SUCCEEDED/PARTIAL/FAILED/CANCELLED`，其他状态和阶段见 RunStatus/RunPhase；`PAUSED` 与 `AWAITING_APPROVAL` 不表示任务完成。`WAITING_FOR_APPROVAL` 是 phase，不能作为 status 使用。

过期租约的恢复会先领取执行权，无法恢复的运行进入 `FAILED`；`RUN_RECOVERY_STARTED` 作为普通事件消费。审批过期与用户决定并发时保留先落定的状态，决定落库时已达到 expires_at 则返回 410，不以请求发出时间延长有效期。客户端按幂等重放、409 冲突和 410 过期处理，详见 [运行时并发契约](12-agents.md#并发工具调用与执行归属)。

<a id="agent-input"></a>
### 创建任务的嵌套输入与可用入口

`POST /agent-jobs` 要求 student 身份；运行时停止接单返回 `503 AGENT_RUNTIME_UNAVAILABLE`。首次创建返回 202，同一幂等键与同一输入重放返回 200，响应均为 AgentJobOut。body.idempotency_key 优先于 `Idempotency-Key` 请求头；相同键、不同 job_kind/input_ref 返回 `409 AGENT_IDEMPOTENCY_CONFLICT`。

外层 AgentJobCreateIn 的 job_kind 正则允许五个值，但通过格式校验不表示已经注册了 Handler。当前 [容器注册](../../backend/app/services/container.py) 与 [Handler 注册器](../../backend/app/services/agent_runtime/handlers/registry.py) 的实际入口如下：

| job_kind / 功能 | 当前入口与 input_ref |
| --- | --- |
| `learning_goal` | 通用 `/agent-jobs` 可创建；input_ref 为 [LearningGoalInput](schemas.md#schema-learninggoalinput)：goal_id 必填，available_minutes 默认 60（1～1440），course_id/window_start/window_end/plan_id 可空 |
| `interactive_classroom` | 通用 `/agent-jobs` 可创建；input_ref 为 [InteractiveClassroomInput](schemas.md#schema-interactiveclassroominput)：course_id 必填，其余模式、学习目标、难点、时长、难度、练习与资料字段见字段字典；生成仍需审批 |
| `final_review` | 通用创建接口未注册这个名称，返回 `409 AGENT_CAPABILITY_DISABLED`；使用复习 campaign/plan/activate/adjustment-proposals 的专用接口 |
| `course_research` | 通用创建接口未注册这个名称，返回同上 409；使用 `POST /course-research/runs` |
| `notice_workflow` | 通用创建接口未注册这个名称，返回同上 409；使用通知事务与动作 decision/execute 接口 |
| 内部 `final_review_plan_activate` / `final_review_adjust_apply` | 容器注册了处理器，但名字不符合公开 AgentJobCreateIn 正则，不能通过通用接口提交；由复习专用接口创建 |

`input_ref` 的外层类型虽然是开放字典，路由还会执行对应 Handler 的 Pydantic 校验，失败为 `VALIDATION_FAILED`。这两个 Handler 输入模型均允许未知键透传；未知键不表示会被业务执行。互动课堂不能用客户端 approval_id 替代服务端审批，user_id 的归属以已认证用户为准。学习目标任务生成计划草案并回写 plan_id/intervention_id，成功不等于用户已经接受或执行计划。

```json
{
  "job_kind": "learning_goal",
  "input_ref": {"goal_id": "<当前用户的目标ID>", "available_minutes": 60},
  "idempotency_key": "<本次动作唯一键>"
}
```

事件流 `GET /agent-runs/{run_id}/events/stream` 用 fetch 带 Bearer，Accept 为 text/event-stream。每帧包含 id、event 和完整 [AgentEventOut](schemas.md#schema-agenteventout)：

```text
id: evt_example
event: RUN_STARTED
data: {"id":"evt_example","type":"RUN_STARTED","sequence":1,"run_id":"run_example","status":"RUNNING","phase":"CONTEXT_BUILDING","created_at":"2026-09-30T09:00:00+08:00"}

: keep-alive

```

示例包含必需字段，可空的可选字段省略；event 为实际 AgentEventType，且与 data.type 一致。重连发送 **Last-Event-ID（event id，不是 sequence）**；按 sequence 去重并保持顺序。心跳注释不改变业务状态；流断开不会取消运行。无效或不属于本 run 的游标返回 AGENT_CURSOR_INVALID，改用 REST `/events?after_sequence=0&limit=...` 归并，再续传。终态事件发送后流会关闭，不能把正常关闭当作任务失败。

pause/resume/retry/cancel 通过 run 控制接口执行。pause/resume/retry 每次独立动作生成新 idempotency_key，仅网络重试复用；body 的键优先于请求头，省略键会使后续相同动作不再执行。retry 首次成功返回新 run_id，但同键重放返回原运行，首次响应丢失时须回读任务的 runs 并检查 retry_of；多个候选时不能自动认定关联，也不能盲目换键重试。cancel 按状态机幂等，当前不消费控制键。完整规则见[运行控制与重试幂等](12-agents.md#run-controls)。

审批决策为 APPROVED/REJECTED；相同决策重放幂等，相反决策冲突，过期不等于批准。产物先读 `/agent-artifacts/{id}`，再 `/content` 获取文本（按 mime_type 读取 Markdown/JSON）；记忆的建立与 withdraw 独立管理。全局运行观测页面及管理接口已移除，客户端只追踪当前用户的任务与运行。

当前普通依赖支持 access_token query 回退，但 Web Agent SSE 明确使用 Authorization fetch，避免把 token 放进 URL；不要照搬原生 EventSource。

## 期末复习与课程研究

期末复习：创建 campaign → generate plans → 追踪关联 Agent run → 读 plan-versions/版本 → 明确选择 version activate → today agenda → daily-item complete 与 daily-checkins → adjustments/analyze → adjustment-proposals → 对 proposal decision。用户接受调整才允许切换计划；activate 请求应按当前 schema 提供 version，不能照搬旧 agentApi 的空请求。

课程研究：`POST /course-research/runs` → GET run → 追踪 agent_run_id → GET artifacts → 阅读有来源的产物；需要取消时调用 cancel。使用 source_policy、assistance_mode、academic_policy 等声明，不使用未注册的 `/course-research/sessions`。

<a id="magicclass"></a>
## 课程课堂、工作台、编辑与导出

课程内经典课堂与受管工作台是两种契约：经典接口用 session_id/classroom_id，受管接口用 workspace_id/stage_id/scene_id。导航栏独立学习空间又是第三条链路。

经典课堂：status → 只读 plan → generate（202）→ jobs/{session_id} 轮询 → composition 回读实际内容 → 历史与 retry。意图 adaptive/explain/quiz/simulation/visualization/mindmap/coding/pbl/review 是生成需求，不能保证每种 widget 都出现，实际以 composition 为准。

经典课堂从获取预占开始续租，并在发送上游请求前再次核验归属。提交取消、提交期间续租失效或遗留预占被接管时，尚无已知上游 job 的旧会话可能返回 `SUBMISSION_CANCELLED` / `SUBMISSION_OUTCOME_UNKNOWN` 失败码。提交活跃但尚无 job_id 的 queued 会话继续等待，已有上游 job 的任务继续轮询；请求取消时已完成提交中的有效 job_id 仍保存。结果未知时先提示用户确认再重试，避免上游重复课堂，详见 [经典课堂恢复说明](14-magicclass.md#经典课堂提交与恢复)。

受管工作台：fusion/status 与 providers → course magicclass-context → 文件夹、workspaces → stages → 生成 job → 轮询 job/events → 获取 stage、outline、playback 和 scene → 播放、编辑、测验、讲解与圆桌。状态四态 disabled/unavailable/degraded/ready；仅 ready 时 capabilities 非空，缺配置不应显示空内容冒充成功。

| 动作 | 关键协议 |
| --- | --- |
| 创建 workspace/stage/folder、生成、上传、导入、音频/讨论任务等 | 按接口携带 Idempotency-Key；同一次用户动作的网络重试复用同一个键 |
| workspace/stage/folder 条件更新、删除 | 按接口携带 If-Match，值为上次读取的 revision |
| stage commands | 同时要求两个头；commands 1～50 条；revision 正整数，拒绝 `*` |
| 命令语义错误 | 返回稳定 code/path，供编辑器标出问题；不把整个正文覆盖重试 |
| 版本冲突 | 上游 412 在网关转换为 409；重新读取版本并决定如何合并 |
| workspace folder_id | 省略不动、null 移出、字符串归档 |
| materials | 列表不返回全文；detail 返回 text；unsupported 不表示提取成功 |
| playback | render.kind 为 native / sandbox-* / unsupported 的唯一判据，unsupported 展示 reason |
| 课堂测验 | 读取服务端 attempt，提交答案按服务端评分和进度显示；浏览器本地评分不代替持久化结果 |
| narration / TTS / discussion | 创建异步任务 → 查 job → 按 artifact_id 下载音频或讨论记录 |
| .maic.zip、Markdown/DOCX/PPTX 导出 | 网关返回二进制；Content-Disposition 为文件名，读取 SHA256 等响应头 |
| 视频导出 | POST 建任务、轮询、下载产物；目前受管渲染器只输出标题文字画面，不能宣称完整课堂录屏 |

开放 document/commands/render/steps/metadata 字段的具体 DSL 与命令字段见 [扩展契约](response-contracts.md#dsl)；它们不是可以任意发送的自由 JSON。课程侧只连接 CampusMate 网关，不请求 magicclass-service 的 `/internal/*`，不在浏览器保存内部服务凭据。

独立学习空间先 `GET /magicclass/learning-space/status`，校验服务端返回的 embed_origin 后嵌入；不要从任意客户端输入构造 iframe URL。它自己的 API、cookie、功能开关和响应见 [学习空间手册](learning-space.md)。

## 学习通与教务同步

学习通：login → status → sync（按返回 sections/warnings 展示部分成功）→ 课程局部 sync → disconnect。局部同步 depth=fast/deep，sections 为逗号分隔；force_refresh 及支持分区见课程接口。reauth_required/verification_required 表示外部连接需重新认证，不能循环刷新本站 JWT。

教务两条入口：已知学校 detect/bind/binding/sync；未知网址 discovery/probe → connections/from-url → challenge（验证码）→ authenticate → connection sync → 读取 schedule/grade/exam items。需要额外验证时展示接口 action/status，不自动假定绑定完成。解绑与删除连接不同，按实际模型处理；来源未同步、失败或 stale 状态应可辨识。

课表同步包含时间和地点等完整内容的比较，字段变化会计入 `updated`；旧摘要首次刷新可能计入一次更新。课程资源内容重复同步保留有效缓存，远端资源身份变化后旧缓存失效并在下次下载重新获取。非流式下载途中被替换的资源最多尝试 3 次，旧下载不得作为新资源有效缓存；耗尽时按既有 502 `HTTP_ERROR` / `resource_metadata_error` 处理，稍后刷新内容再重试。请求和响应字段不需迁移。

`/academic/*` 是兼容路径；academic/bind 当前直接拒绝，用 `/edu/bind` 或 connections 流程。大学选择用 `/profile/university`，个人资料编辑使用 `/auth/me`。

## 上传、下载与静态资源

上传字段名各接口不同：社区 `image`，其他 file/material/attachment 以参数表为准。大小、MIME、扩展名和文件名还有服务端校验，不能只由浏览器 accept 限制。知识库保留只读能力，不提供在线导入入口；个人文件、课程资料、作业附件是不同资源。

下载先检查 HTTP 和 Content-Type，再读取 Blob；非 2xx 的 JSON 错误不能当作下载文件。当前 Web 部分下载封装只处理 /static/community_images 与通用 blob 文件名，跨 Origin 的 /static/banner-images、课程附件也须按服务 Origin 解析；不要将 /static 路径加到 /api/v1 后。

根 `GET /` 返回 `{name,version}`；`/docs`、`/redoc`、`/openapi.json` 是 FastAPI 文档入口。`/static/community_images/*`、`/static/banner-images/*`、`/digital-human/*` 是静态资源挂载，不列为业务 HTTP 操作。数字人目录存在时才挂载。

<a id="local-features"></a>
## 当前仅在 Web 本地实现的功能

主题、动效、导航布局、背景图、白噪声播放、静音、数字人重播、课堂面板尺寸、播放偏好、倒计时显示，以及部分助手会话/草稿偏好由当前 Web 的 localStorage、组件状态、静态文件或浏览器播放器管理。对应源码在 pages、features、magicclass 与 app；它们没有统一的服务端设置 CRUD API。

`/profile/:section`、`/study/plans`、`/study/docs`、`/study/statistics` 等页面会复用现有接口和前端聚合，不意味着后台有同名路由。社区分类中的 activity 是帖子分类，已移除的 `/activities/*` 业务接口没有注册。页面和全部封装的实际路径见 [Web 对照](web-map.md)，不要按页面名称臆造新接口。

## 可信反代与限流身份

限流按 ASGI `request.client.host` 区分客户端，不直接读取客户端提交的 `X-Forwarded-For`。Uvicorn 默认启用代理头处理，但只接受可信代理地址（缺省 `127.0.0.1`）。跨主机或容器反代必须在启动 Uvicorn 前设置进程环境 `FORWARDED_ALLOW_IPS`，或传入 `--forwarded-allow-ips`，内容仅为实际代理 IP/CIDR；不要设为 `*`。仅修改应用读取的 `backend/.env` 不保证 Uvicorn CLI 生效。代理必须覆盖/追加真实连接地址，不能把外部提交的头原样作为可信来源。

已验证可信代理后的两个客户端独立限流、未受信代理的伪造头被忽略，以及伪造转发链不能绕过已耗尽的客户端额度。

## 管理能力移除与平台适配

管理员角色及所有管理专用 API 已删除，包括账号管理、社区审核、横幅编辑、课程写入、教务配置/候选审核、知识库写入和全局 Agent 观测。删除的路径返回 404；同一路径仍保留其他方法时，删除的方法返回 405。不要把这些能力改为普通用户可调用的全局写入入口。

Web 已移除运行观测页面，并改为 `PATCH /auth/me` 编辑本人资料；社区举报功能及 `POST /community/reports` 已移除，Web、Android、HarmonyOS、微信小程序的入口或调用封装已同步清理；旧客户端须停止调用，删除的路径返回 404。其余学生接口保持兼容，源码核对未发现管理接口调用；移动端构建和真机流程尚未验证。共享课程、公告、横幅与知识库的已有数据和只读能力保留，由仓库的内部数据准备/同步工具提供内容，产品没有在线管理界面。

## 共同课堂邀请与消息

共同课堂使用 CampusMate Bearer 认证和本人 UID，按[共同课堂协议](14-magicclass.md#learning-rooms)完成上传 → 邀请 → 接受 → 下载 → 页码/消息轮询 → 离开。该通道属于 /api/v1/magicclass/learning-space，与独立 iframe 内的 /api 是不同服务。

动态对象字段见[实际响应](response-contracts.md#learning-rooms)。成员权限基于 accepted 状态，pending 不具备课件访问权；发起人结束会清空归档并撤销成员关系。客户端须处理 404/410 并停止轮询，204 不解析 JSON，消息重试复用同一 client_id。Web 已有调用封装；其他三端共同课堂流程尚未接入、未验证。
## 桌面设备与学习偏好接入补充

桌面设备使用[设备协议](15-devices.md)中的独立设备凭据，只能访问 `/devices/me/*`。设备凭据不能调用用户 JWT 接口，也不能作为已有实时语音 WebSocket 的 `access_token`；专用设备语音 WebSocket 使用 Authorization 请求头，流程见设备协议；用户凭据不能代替设备凭据。确认二维码绑定、列出设备和撤销设备由已登录学生执行。后端仅接收允许的结构化观察，不接收相机画面。

后续客户端设置学习偏好时，先 `GET /learner-state/preferences` 读取 `version`，再 `PUT` 完整配置并携带 `expected_version` 和操作唯一 `idempotency_key`。丢失响应时重放原请求和原键；`LEARNER_PREFERENCE_VERSION_CONFLICT` 后重新读取配置并由用户决定覆盖，不能自动用新版本重试覆盖。学期第一周的星期一由用户明确设置，后端不猜测学校校历。`configured=false` 的默认值只用于初始化界面，不能称为已观测用户偏好。

本轮只验证后端。Web、Android、HarmonyOS、微信小程序及桌面设备应用均尚未接入新增协议；旧调用继续兼容。详见[学习状态与计划](11-learner.md)和[设备协议](15-devices.md)。
