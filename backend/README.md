# CampusMate AI 后端

`backend/` 使用 FastAPI、SQLite 提供认证、个人事务、课程、通知、学习通同步、AI 对话和在线课堂服务。系统仅提供 `student` 用户角色；历史 `teacher` / `admin` 账号在认证时降为普通用户，不具有跨用户或跨学校权限。

## 能力与接口

| 能力 | 主要入口 | 当前实现 |
| --- | --- | --- |
| 健康检查 | `GET /api/v1/health` | 返回后端、知识库和 LLM 等运行状态 |
| 通知提取 | `POST /api/v1/notices/extract` | 手动输入通知原文，优先用已配置的 LLM，失败时规则降级；不确定字段标记需确认 |
| 手机消息整理 | `POST /api/v1/notices/ingest-batch` | 接收客户端筛选后的消息，去重，规则优先分类；模糊消息可批量交给 LLM，再生成通知和可执行待办 |
| 学习通 | `/api/v1/chaoxing/login`、`/status`、`/sync`、`/disconnect` | 连接账号并同步课程、通知、作业、考试等；登录态失效或需要验证时返回对应状态 |
| 学习通作业复习 | `GET /api/v1/tasks`（不传 status）、`GET /api/v1/chaoxing/assignments/{task_id}/content`、`POST /api/v1/chaoxing/assignments/{task_id}/classroom` | 读取本人已截止作业、题干与选项，创建或复用练习优先的受管课堂；生成后通过课程 job 接口查询进度 |
| 可选教务连接 | `/api/v1/edu/*` | 学校系统探测、用户绑定与课表、成绩、考试同步；真实数据取决于学校适配器及用户授权 |
| AI 对话 | `POST /api/v1/counselor/chat`，兼容别名 `/api/v1/assistant/chat` | SSE / 非流式回答，可带经过校验的个人任务、课程和学习状态上下文；课堂建议须用户确认后才执行 |
| 知识库 | `/api/v1/knowledge/status`、`/documents` | 只读查询知识库状态和文档；当前聊天链路仍使用内部 BM25 检索，资料导入由内部数据准备/同步流程提供 |
| 课程内互动课堂 | `/api/v1/courses/{course_id}/interactive-classroom/*` 及课程 workspace 路由 | 按课程权限读取上下文、生成、查询进度和真实内容组成；由 `magicclass-service` 提供受管能力 |
| 自主选题课堂 | `/api/v1/self-classroom/status`、`/materials`、`/generate`、`/jobs/{session_id}`、`/self-classroom` 历史 | 学生输入主题，可上传本人资料；复用经典生成服务，以当前用户及 __self_study__ 隔离，完整契约见课堂模块 |
| 学习空间状态 | `GET /api/v1/magicclass/learning-space/status` | 返回独立 `magicclass-app` 的可用性与公开 Origin，供 Web 导航入口使用 |
| 学习空间共同课堂 | `/api/v1/magicclass/learning-space/identity`、`/rooms`、`/invitations` | 复用账号 UID，保存课件/原生讨论课堂、邀请、成员、翻页和文字消息；接受邀请后才允许读取内容 |
| Android 共同课堂音视频 | `/api/v1/magicclass/learning-space/rtc/status`、`/rooms/{room_id}/rtc-token` | 为 accepted 成员签发短期 RTC 凭证；客户端分别选择麦克风/摄像头，媒体由火山 RTC 传输 |
| Agent Runtime | `/api/v1/agent-jobs`、`/agent-runs` 等 | 持久化任务、运行事件、审批及产物接口；与普通聊天接口不同 |

完整路径以 [`app/api/router.py`](app/api/router.py) 中实际注册的路由为准；完整请求/响应与接入流程见[接口文档](../docs/api/README.md)，FastAPI `/docs` 和对应 schema 提供声明快照。

## Agent Runtime 运行与故障处理

Agent Runtime 的新 Job 通过 SQLite 持久化后由后台 Worker 执行。运行状态和事件以数据库记录为准；SSE 用于传递事件和断线续接，不负责保存任务。Worker 仅领取绑定了已注册 Handler 的运行；其他既有业务流程按各自的领域路由推进。当前没有管理员观测 API，维护时使用应用日志、健康检查以及用户本人有权读取的 Job/Run 接口，不应依赖管理员页面或跨用户查询。

`backend/.env.example` 中的 Worker 配置如下。修改模式或租约参数后需重启后端进程：

| 配置 | 默认值 | 用途 |
| --- | --- | --- |
| `AGENT_RUNTIME_MODE` | `worker` | `worker` 接受新 Job 并处理队列；`drain` 拒绝新 Job、继续处理现有队列；`disabled` 拒绝新 Job 且不领取任务。 |
| `AGENT_WORKER_CONCURRENCY` | `1` | 单进程并发 Worker 数。 |
| `AGENT_WORKER_LEASE_SECONDS` | `30` | 单次领取的租约时长。 |
| `AGENT_WORKER_HEARTBEAT_SECONDS` | `10` | Worker 续租间隔，必须小于租约时长。 |
| `AGENT_WORKER_POLL_MS` | `500` | 空队列轮询间隔；`0` 表示不等待。 |

排空时先将 `AGENT_RUNTIME_MODE` 设为 `drain` 并重启服务。新建 Job 会得到 `503 AGENT_RUNTIME_UNAVAILABLE`；Worker 仍会处理已有队列。通过 Job/Run 状态确认队列已收口后，再停止服务或部署新版本。若需暂时停止所有领取，使用 `disabled`；已入队任务会保留在数据库中，恢复 `worker` 模式并重启后继续处理。不要删除队列表或手工改状态来“清空”任务。

正常关闭时，Worker 停止领取并等待正在执行的处理器完成当前工作，再退出。若进程被强制终止，运行保留为非终态并保留租约与 checkpoint；租约过期后，后续 Worker 会调用对应 Handler 的恢复决策，从安全 checkpoint 重新排队，或以明确错误码结束。处理器按至少一次语义设计，领域副作用需具备幂等保护；系统不承诺 exactly-once。审批等待状态会释放租约，不会被 Worker 持续占用；审批通过后任务重新入队。

排查单个任务时，使用该用户自己的 `GET /api/v1/agent-jobs/{job_id}`、`GET /api/v1/agent-jobs/{job_id}/runs`、`GET /api/v1/agent-runs/{run_id}/events` 和 `/api/v1/agent-runs/{run_id}/events/stream` 检查状态、错误码及事件序号。遇到客户端断线可在 SSE 请求中用 `Last-Event-ID` 续接；未知或不属于该 Run 的游标会返回 `409 AGENT_CURSOR_INVALID`，客户端应改读事件列表后再续接。检查服务端日志中的 `agent_worker_poll_failed` 等错误时，先确认数据库可读写、Worker 模式有效、租约持续更新，再查看 Run 的稳定错误码。不要通过提高重试次数、清除租约或重放领域写操作来掩盖失败；修复原因后让运行时按租约和 checkpoint 语义恢复。

自动化故障演练可运行 `python -m pytest tests/test_agent_runtime_failure_drills.py tests/test_agent_worker.py tests/test_agent_event_recovery.py -q`。这些测试验证代码对故障的处理，不代表生产灰度已通过；真实发布仍需单独记录连续观察时长、非测试 Run 数量、重复副作用和事件缺失情况。

## AI 对话的现状

CampusMate AI 的产品方向是通用型助手，不要求绑定某所学校。**当前实现还不是纯通用聊天**：Web 和 Android 仍调用 `counselor/chat`，该路由在非问候问题上调用 `RagService.stream_answer()`，后者执行 `RetrievalService.search()`。配置 LLM 后，普通问题可以借助模型知识作答；有检索结果时也会传入校园资料。未配置 LLM 时走 `retrieval_summary` 降级，资料不足时可能提示人工核实。

因此，知识库只应被描述为**现存后端能力和历史聊天链路**，不能说它是整个产品的定位，也不能声称当前聊天已经完全停止检索。若要实现纯通用助手，需要修改聊天编排、提示词、降级行为及测试。

项目没有内置真实学校的正式制度资料。可选教务连接属于用户授权的数据同步，不是聊天的前置条件。涉及具体学校的规定、截止时间、地点或材料时，当前检索结果和普通模型回答都不能替代官方信息。

## 通知数据流

1. Android 在用户授予通知访问权限后，从系统通知栏接收微信、企业微信、QQ/TIM 和学习通等来源实际展示的消息；端侧按来源开关、群白名单、内容规则过滤并存入本地队列。
2. Android 的 WorkManager 将通过筛选的消息批量发往 `/notices/ingest-batch`。后端先去重与规则分类，再对模糊内容使用可用的 LLM；普通聊天会被忽略，可执行通知可转成待办。
3. 学习通账号同步通过独立的 `/chaoxing/*` 路由获取课程、通知、作业和考试；它与系统通知监听不是同一种接入。手动粘贴通知继续走 `/notices/extract` 等页面流程。

服务端接收的是客户端提交的文本，不具备读取微信、QQ 私有聊天记录的能力。Android、HarmonyOS 和小程序的系统权限也不相同，详见[主 README](../README.md)。

## 学习通每日同步与作业复习

连接学习通后，`ChaoxingDailySyncWorker` 随 FastAPI lifespan 启动，不依赖 Web 页面或手机保持打开。后台轮询在一批账号处理结束后等待 60 秒，再扫描到期账号；成功同步后从本轮结束时间起间隔 24 小时，普通失败或部分成功 30 分钟后重试。需要重新认证或凭据损坏时，重新连接会使账号重新进入待同步队列，否则下一天再尝试。首次连接、重启补同步的实际执行时间还受前面账号耗时影响，不是固定每天零点执行，也不保证连接后 60 秒内完成。

每轮最多读取 25 个到期账号，逐个执行；持久化租约为 15 分钟，单账号执行预算为 10 分钟。同进程内后台同步、手动同步、登录、解绑共用用户互斥锁；后台任务在共享同一 SQLite 数据库时通过租约避免多进程重复领取。该租约不覆盖其他进程的手动同步和账号修改，不能据此承诺所有跨进程操作全局串行。正常关闭取消后台任务，强制退出后租约到期可再次领取。停止后端期间不会执行同步。

作业列表、提交状态、成绩和题目快照分别处理。单次题目获取最多 12 份、并发 3、每份预算 12 秒；缺失、提交状态变化或采集超过 24 小时的快照进入队列，按最近尝试时间轮转。部分题目失败时保留已有快照，sync 返回 HTTP 200 也可能 `complete=false`，须查看 `sections.assignments` 与 `warnings`。`completed` 包括已交、待批阅等平台观测，不要求已评分；它表示最近同步结果，不是访问列表时再次向学习通确认。

Web 在线课堂首页、学习空间侧栏及作业详情复用同一组后端接口：

1. `GET /api/v1/tasks?page=1&page_size=200`，不传 status，按 `has_more` 翻页，再筛选 `source=chaoxing`、未删除且有效截止时间已到期的 pending/completed 条目。使用返回的本站 `id` 作为 task_id。
2. `GET /api/v1/chaoxing/assignments/{task_id}/content` 读取题干和选项；`can_generate` 要求有效截止时间已到期、课程关联与题目状态匹配，未提交也可复习，不包含课堂服务可用性检测。
3. 用户点击进入时 `POST /api/v1/chaoxing/assignments/{task_id}/classroom`。服务端按本人、课程、作业、题目需求计算幂等键，创建或复用讲解任务。每日同步只采集作业，不主动生成课堂。
4. 对 queued/running 用 `GET /api/v1/courses/{course_id}/jobs/{job_id}` 查询；失败/取消可用对应 `/retry` 接口重试；completed 后进入返回工作台学习。Web 在题目未就绪时尝试一次同步，生成成功后自动进入播放。

生成采用作业专用 quiz 策略：先重做全部原题，再做每题对应的变式（总数至少 3 道），至少三分之二场景为练习；学生自由选题、跳过、逐步求助，提交后主动展开解析，简答/证明题自行核对；这是模型生成的学习内容，不是学习通官方批阅。未识别的图片、过长题目或模型不可用会返回明确错误，不生成替代模板。

运行依赖见 [backend/.env.example](.env.example) 与 [受管服务配置](../magicclass-service/.env.example)：后端设置 `MAGICCLASS_FUSION_ENABLED=true`、可达的 `MAGICCLASS_SERVICE_URL`，两服务使用一致的 `MAGICCLASS_INTERNAL_SECRET`；受管服务另需配置 `MAGICCLASS_PROVIDER_BASE_URL`、`MAGICCLASS_PROVIDER_API_KEY`、`MAGICCLASS_PROVIDER_MODEL`。只设置后端通用 LLM 不代表课堂生成模型已配置。独立学习空间的 `MAGICCLASS_ENABLED` / `MAGICCLASS_EMBED_ORIGIN` 控制另一条内嵌链路，不代替受管课堂配置。

持久化涉及后端的 `chaoxing_credentials`（加密 Cookie）、`personal_tasks`（列表与提交状态）、`chaoxing_assignment_content`（题目快照及尝试时间）、`chaoxing_auto_sync`（下次尝试时间、租约与最近错误），以及受管服务自己的工作台、任务和幂等数据。新增表由数据库初始化建立；部署时保留两服务的数据目录及稳定密钥。没有公开的每日同步配置、立即执行后台 tick、下次执行时间或租约查询 API；维护时通过受控数据库诊断和日志排查，不手工改业务状态来伪造提交。

排查时先看本人 `/chaoxing/status` 是否需重新连接，再检查手动 `/chaoxing/sync` 的分区结果与题目快照。`chaoxing_daily_sync_tick_failed` 表示后台轮次异常，`chaoxing_daily_sync_failed` 表示单账号执行异常；日志中的 error_type 只用于定位，不能当作前端协议。作业复习接口的错误码、请求/响应示例、跨端适配与联调步骤见[外部连接](../docs/api/09-integrations.md#assignment-review-flow)。

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_chaoxing_assignment_review.py tests/test_chaoxing_sync_service.py tests/test_chaoxing_sync_sections.py tests/test_app_lifespan.py tests/test_openapi_docs.py -q
```

自动化测试覆盖用户隔离、截止门槛、题目采集与保留、后台租约与重启恢复、幂等生成和服务不可用分支。真实学习通页面解析、有效账号登录态以及外部模型生成质量仍需在实际部署验证。Web 已适配一键进入；Android、HarmonyOS 和微信小程序尚未接入该作业复习入口。

## 在线课堂

### Android 多人音视频共同课堂

Android 的“课程 → 同学一起学”已接入共同课堂身份、创建讨论课堂、UID 邀请/接受、成员、文字消息与火山 RTC 音视频。已有上传课件课堂也可接受邀请后加入通话；完整课件播放仍在 Web 学习空间，Android 显示共享页码。每堂最多 8 人（含发起人及待接受邀请），每位发起人最多 20 个活动课堂。

后端使用现有 `VOLC_RTC_APP_ID`（24 位）与 `VOLC_RTC_APP_KEY`，从已开通实时音视频服务的火山 RTC 应用取得后填入本地环境配置。AppKey 只留在后端，不要写入 APK、源码、日志或提交。此功能不需要 AI VoiceChat 配置、Seeduplex Key 或 AK/SK；与 Focus AI 语音独立。配置检查不等于云账号余额、真实连通性或通话质量已经通过验证。

部署时按以下顺序检查：

1. 按[本地启动](#本地启动)准备后端，在其环境配置中设置同一 RTC 应用的 `VOLC_RTC_APP_ID`、`VOLC_RTC_APP_KEY`，重启后端使配置生效。不要复制示例 AppId 作为真实配置。
2. 用已登录账号的 Bearer access token 请求 `GET /api/v1/magicclass/learning-space/rtc/status`；`available=false` 时检查 AppId 是否为 24 位字母数字、AppKey 是否为空。`available=true` 后仍需真机验证密钥匹配及云服务状态。
3. 用两个不同账号完成创建 → 邀请 → 接受 → 各自获取 RTC 凭证，按[双账号联调步骤](../docs/api/14-magicclass.md#classroom-rtc-handoff)接入 Android；不能把两台设备登录同一账号作为双人测试。

原生讨论课堂只依赖本站后端、账号数据库及云端 RTC；创建与文字消息不要求配置 RTC，也不依赖 `magicclass-service`、独立 `magicclass-app` 或课堂生成模型。需要生成、播放完整课件时，再按下文配置对应服务。`VOLC_RTC_TOKEN_TTL_SECONDS` 和 `VOLC_RTC_AGENT_USER_ID` 属于 Focus AI 语音配置项，共同课堂不读取它们，固定使用 120 秒凭证及 60 秒续期规则。

新增接口为 `GET /api/v1/magicclass/learning-space/rtc/status`、`POST /api/v1/magicclass/learning-space/rooms/native` 和 `POST /api/v1/magicclass/learning-space/rooms/{room_id}/rtc-token`。完整请求/响应、权限、错误和跨端接入见[共同课堂音视频协议](../docs/api/14-magicclass.md#classroom-rtc)。后端只处理控制请求，音视频通过 RTC SDK/云服务传输，不经 HTTP 轮询、Python 转发或 SQLite。

RTC 凭证绑定服务端确定的课堂与本人 UID，120 秒过期，客户端每 60 秒续期并处理 SDK 的到期提醒。续期重新检查 accepted 成员关系；离开/结束后拒绝续期。**离开不调用云端即时封禁接口，已签发凭证最多仍可使用 120 秒**；官方客户端通过课堂状态轮询及时断开。需要强制即时回收时，应另接云端房间/用户封禁，不能把短期凭证描述为即时撤销。

课堂详情、课件下载与消息读取将权限校验和结果放在同一 SQLite WAL 读取快照中；发起人并发结束课堂时，已经获准的在途读取仍返回完整内容，后续请求拒绝访问，不会成功返回空 ZIP 或半更新的成员列表。读取不占用写锁，也不提交或回滚调用者已有的写事务。

安卓入会默认关闭采集，两项权限分别申请；后台通过前台服务保留通话声音并关闭摄像头，返回前台不会自动重新开摄像头。视频以 640×360/15fps 发送，订阅小画面并启用弱网音频优先。SDK 入会回调成功后才显示通话中；支持凭证续期、断线提示/重连、通知栏断开及离开释放。网络 RTT 不等于真实端到端语音延迟。

Android 等前台服务确实启动成功后才初始化通话/开启麦克风，服务按当前页面的通话归属管理，旧页面不能停止新通话。网络恢复仍需房间入会成功回调；重连时可以立即关闭已有麦克风/摄像头。独立的凭证到期计时器使用设备单调时钟，超时停止通话并取消续期任务。

部署验收须使用真实 RTC 配置和至少两台 Android 设备，覆盖不同运营商/Wi-Fi、锁屏、前后台、权限拒绝、反复开关、凭证续期和发起人结束；再进行 8 人持续通话与丢包/切网测试。当前自动化测试覆盖后端凭证/权限/并发边界，不代替真机音视频与延迟验收。

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_learning_rooms.py tests/test_learning_room_rtc.py tests/test_openapi_docs.py -q
```

课程内互动课堂会先检查课程访问权限及受管服务状态，生成前可查看计划，提交后可查询进度、内容组成和历史会话。Web 的课堂工作台还通过课程 workspace 接口管理场景、播放、编辑与导出。导航栏“学习空间”则承载以独立进程运行的上游 `magicclass-app`。

课程课堂生成与受管工作台依赖 `magicclass-service` 和相应模型提供方；导航栏独立学习空间依赖 `magicclass-app`。服务未启用、不可达或缺少所需配置时，接口会返回真实的不可用状态；仓库中的页面和测试并不等于每台机器都能生成课堂。

## 本地启动

在仓库根目录运行 `start_backend.bat`，或手动进入本目录：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

默认 `LLM_PROVIDER=none`；配置示例和其他变量见 [`.env.example`](.env.example)。不要把包含密钥的 `.env` 提交到仓库。接口文档位于 `http://localhost:8000/docs`，健康检查位于 `http://localhost:8000/api/v1/health`。

仅启动后端无法运行在线课堂的受管服务与独立“学习空间”；在 Windows 仓库根目录运行 `start_all.bat` 可按依赖顺序启动完整链路。

Docker 镜像仅分发 `data/universities.json`、`data/edu_system_candidates.json` 和 `data/banner_images/` 这三类发布资源，保存于数据卷外的 `/opt/campusmate-release-data`。容器启动时会向 `/app/data` 补齐缺失资源，包括已有卷内缺失的文件；已有同名文件、数据库和用户数据保持原样，重复启动不会覆盖。更新已有发布资源须由维护者单独处理；不要为补齐资源删除数据卷。初始化后入口进程直接执行 Uvicorn，保留可信代理环境变量和正常停止信号。

## 本地语音输入与评测

公开数据下载、VAD 参数扫描、INT8／FP32 和增强对照集中在 [`ml/speech_recognition/`](../ml/speech_recognition/README.md)。该目录提供独立的可复现实验流程，数据、模型和结果不会纳入应用源码或自动改写运行参数。

`POST /api/v1/assistant/asr` 在后端机器运行 SenseVoice INT8，不上传第三方，区别于手机系统语音识别或专注会话实时语音。Android、iOS 已接入但未真机验收；Web、HarmonyOS、微信小程序仍待适配。完整约定见[语音输入接口](../docs/api/10-assistant-knowledge.md#post-apiv1assistantasr)。

在 `backend/` 的虚拟环境中执行以下命令获取声学模型及可选 Silero VAD，模型保存在已由根 `.gitignore` 忽略的 `data/asr_models/`，不提交仓库。下载时需要网络，推理时不需要；Windows 将 `python` 换成 `.venv\\Scripts\\python.exe`：

```powershell
python scripts/download_asr_model.py --with-vad
python scripts/download_asr_model.py --with-vad --check
```

默认 `ASR_VAD_MODEL_PATH=data/asr_models/silero_vad.onnx`，文件存在时用 VAD 判断是否含语音，阈值 `ASR_VAD_THRESHOLD=0.4`；通过后保留整段录音，避免裁掉轻声起音。文件缺失或路径留空会兼容旧能量门控，仍可能漏掉小声和长留白，已有文件损坏则返回 503。Android/iOS 不按固定正音量阈值丢弃录音；编码前做低通重采样，后端非 16k 输入使用 sherpa-onnx 原生重采样。VAD 不能分离背景人声或消除混响，强噪声下仍需实录验证。

单次请求的上传体积和音频时长由 `ASR_MAX_UPLOAD_MB=10`、`ASR_MAX_AUDIO_SECONDS=60` 限制；声明 `Content-Length` 超限（含约 4KiB multipart 余量）的请求在 multipart 解析前返回 413，无长度的分块上传返回 411 `ASR_LENGTH_REQUIRED`。解码前另有 200 万采样点硬上限，避免恶意 WAV 头在 `readframes` 阶段分配巨量内存。`ASR_MAX_CONCURRENCY=2` 限制同时读取/解码/推理的请求数，超过 `ASR_QUEUE_TIMEOUT_SECONDS` 仍无空位时返回 503 `ASR_BUSY`，避免多个 10MB 音频同时放大浮点采样点。VAD 降采样使用 NumPy 低通+插值，`numpy` 已作为直接依赖固定。

0.4 现作为实际试用的默认方案，原 0.5 路线保留为历史对照，不再优先推荐。已有 20 句新留出集上，总体 CER 从 11.71% 降至 10.37%，1% 幅度条件从 20.90% 降至 12.85%，非语音非空输出均为 3/60；成对置信区间仍触及 0，不能据此声称普遍稳健或统计显著。决策依据、局限和历史实验见[语音识别实验说明](../ml/speech_recognition/README.md)。已有环境或 `.env` 中显式设置的 `ASR_VAD_THRESHOLD=0.5` 会覆盖新默认；如需采用新默认，改为 0.4 或移除该显式配置后重启后端。阈值仍可在 `(0, 1)` 内按需配置。

`ASR_VAD_RECHECK_ENABLED` 默认开启，使用受限参数（目标 RMS 0.005、最大增益 20、峰值上限 0.95）：首次按配置阈值拒绝且输入可受限增响时，只对分析副本沿用同一阈值再检测一次，识别仍使用完整原音。该默认由新独立验证集决定——24 条未使用中文原句、20 个未使用 ESC-50 fold 5 噪声源、3 个未使用实测 RIR，共 204 条变体，按推理前冻结的协议通过全部门槛：总体 CER 12.97%→10.93%，1% 幅度 CER 21.97%→9.75%，空转写 4→0，噪声非空输出 1→1，clean/10% 幅度/两档噪声/混响零退化，总体分组 95% CI `[-4.33, -0.41]` 个百分点不触零，P95 中位数 +6.4%。历史 0.5 阈值 + 0.02/100 宽增益复检未通过其自身门槛，保持为已停止采用的对照，不能与本次受限组合混同。GTCRN 仍默认关闭；说话人不相交无法证明，真实麦克风与远场待验证，详见[验证结果与复现](../ml/speech_recognition/README.md)。

在 0.4 基线上，受限分析复检（目标 RMS 0.005、最大增益 20，峰值上限 0.95）先在开发集改善小声漏检、通过已查看数据回归，随后在新独立验证集上按预先冻结协议通过全部门槛，因此已成为应用默认。现有实验 CLI 仍支持单独比较检测时长、复检参数和语言模式，不改变应用的 0.1 秒最短语音时长及中文语言默认。最大复检增益必须是大于等于 1 的有限数。

方法依据：[FunAudioLLM / SenseVoice 技术报告（2024）](https://arxiv.org/abs/2407.04051)用于核对现有模型能力；[WhisperX（Interspeech 2023）](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.html)提供 VAD 辅助转写的研究依据，但其 Whisper 分段/批处理收益不能直接移用于本项目；具体检测器复用 [Silero VAD](https://github.com/snakers4/silero-vad) 与现有 sherpa-onnx，不新增训练或推理依赖。本实现只检测语音存在，不宣称复现 WhisperX 的分段算法。

准确率用人工或数据集标注衡量，不能拿模型自己的输出作真值。准备 UTF-8 JSONL，每行 `{"audio":"recording.wav","text":"人工参考转写"}`，音频路径相对清单文件解析；纯噪声样本的 `text` 设为空字符串。录音须为 PCM16LE 单声道 WAV，并与 `ASR_USE_ITN` 的数字格式一致。使用自己有权处理的录音，音频、标注和报告保存在仓库外或被忽略的数据目录。

```powershell
python scripts/evaluate_asr.py --manifest data/asr_models/evaluation/manifest.jsonl --output data/asr_models/evaluation/report.json
# 同一份标注对比旧能量门控；空参数显式禁用 VAD
python scripts/evaluate_asr.py --manifest data/asr_models/evaluation/manifest.jsonl --vad-model-path=
```

工具报告逐条和微平均字错率 CER、非语音误报率、预热时间及热推理实时率 RTF（推理秒数/音频秒数，越低越快）。评分统一 Unicode NFKC、小写并去掉标点/空白，不自动把口述数字改成阿拉伯数字。冷启动与 WAV 读取不计入热推理 RTF。未安装模型时报告失败，不自动下载。正式评估应覆盖多说话人、实际距离、混响和真实环境噪声；同一句样例的衰减/加噪变体只能定位问题，不能代表真实场景准确率。

### 可选增强：GTCRN 与 Observation Adding

[GTCRN（ICASSP 2024）](https://ieeexplore.ieee.org/document/10448310)提供轻量语音增强，但听感改善不能直接等同于识别改善。[Iwamoto 等（Interspeech 2022）](https://www.isca-archive.org/interspeech_2022/iwamoto22_interspeech.html)及[后续研究（2023）](https://arxiv.org/abs/2311.11599)分析了增强伪影导致 ASR 退化的问题，并用 Observation Adding 混合原音减轻失真。本项目提供同类推理路径：`mixed = w * observed + (1-w) * enhanced`，使用现有 sherpa-onnx 的 GTCRN，不新增 Python 依赖、不训练模型。它是论文方法在当前模型上的可选实验，不是原论文实验的复现。

`ASR_DENOISE_ENABLED=false` 为默认值，`ASR_DENOISE_MODEL_PATH` 默认 `data/asr_models/gtcrn_simple.onnx`。用下载脚本的 `--with-denoiser` 获取约 0.54MB 模型并校验 SHA256；文件存在也不会自动启用。原音先通过 VAD/兼容门控，再进入增强；不根据增强结果再次做 VAD，不裁剪静音或语音片段。`ASR_DENOISE_OBSERVATION_WEIGHT` 范围 `[0,1]`，默认实验值 0.5；0 为纯增强，1 完全使用原音且不要求增强模型。增强输出按 16kHz 与原音对齐，短尾用原音补齐，防止吞掉句尾。显式启用且权重小于 1 时，缺失/损坏模型返回安全 503，推理异常返回 500，不静默改变处理策略。

先按原始录音划分开发集与留出集，同一句的加噪变体必须属于同一划分。在开发集选择权重后，再固定参数测留出集，并逐项查看纯净、小声和不同噪声下的错字，避免总体均值掩盖回退：

```powershell
python scripts/download_asr_model.py --with-vad --with-denoiser --check
python scripts/evaluate_asr.py --manifest data/asr_models/evaluation/manifest.jsonl --no-denoise --output data/asr_models/evaluation/raw.json
python scripts/evaluate_asr.py --manifest data/asr_models/evaluation/manifest.jsonl --denoise --observation-weight 0 --output data/asr_models/evaluation/enhanced.json
python scripts/evaluate_asr.py --manifest data/asr_models/evaluation/manifest.jsonl --denoise --observation-weight 0.5 --output data/asr_models/evaluation/oa.json
```

评测报告补充模型、词表、已启用可选模型的 SHA256 和 sherpa-onnx 版本；哈希计算不计入热推理 RTF。`configuration.enhancement_active` 区分配置启用与权重为 1 的原音旁路。增强会增加 CPU 时延，不能仅按听感或降噪模型的 PESQ/STOI 指标决定上线。若使用 [FLEURS](https://huggingface.co/datasets/google/fleurs)等公开样本，保留版本、官方参考、许可证和转换过程；小规模确定性抽样不代表完整公开基准或真实远距离场景。

2026-10-24 的本地诊断使用 FLEURS `cmn_hans_cn/test`、固定版本 `70bb2e84b976b7e960aa89f1c648e09c59f894dd`（CC-BY-4.0）。取官方压缩包前 10 条不同文本，按采集索引偶/奇预先划分 5 条开发、5 条留出；官方 float32/16k 原音直接量化 PCM16，未用识别输出生成标注。每句产生原音、1% 音量、10/0dB 白噪声及 5dB 粉红噪声共五种条件，噪声为固定种子的合成信号，SNR 按整句 RMS 计算。开发集 25 个变体中原音总体 CER 9.94%，纯增强 15.97%，OA 原音权重 0.5 为 11.07%，没有足够依据默认开启。固定该候选权重后，留出集结果如下（208 个参考字符按五种条件重复评分，共 1040 字符）：

| 留出条件 | 原音 CER | 纯增强 CER | OA 原音权重 0.5 CER |
| --- | ---: | ---: | ---: |
| 原音 | 6.25% | 6.25% | 6.25% |
| 1% 音量 | 16.35% | 16.83% | 16.35% |
| 10dB 白噪声 | 7.69% | 8.17% | 6.73% |
| 0dB 白噪声 | 13.46% | 26.44% | 13.94% |
| 5dB 粉红噪声 | 9.62% | 17.31% | 11.06% |
| 全部变体 | 10.67% | 15.00% | 10.87% |

OA 在中等白噪声的这 5 句中少错 2 字，但总体多错 2 字，不能据此声称普遍提升；该样本规模也不足以给出真实场景准确率。留出变体共约 299 秒，原音热推理约 7.71 秒，OA 约 20.42 秒；时延受 CPU 和负载影响。GTCRN SHA256 为 `e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534`，本轮使用 sherpa-onnx 1.13.8。诊断材料位于被忽略的 `data/asr_models/evaluation_public_v2/`，不作为应用或 CI 依赖。因此保留默认原音路径，需用实际麦克风、噪声和距离另行验证增强是否值得启用。

## 验证

数据库启动会恢复旧教务绑定及学习反馈表原本声明的外键 / CHECK 约束；历史记录违反约束时会使升级整体回滚并停止启动，保留原数据，不自动删除或猜测修正。内存库借用连接未提交的写入会回滚，组合仓储事务须使用 `Database.transaction()` / `query()` 共享连接，嵌套事务使用保存点。

用户、会话、课程、班级、选课、公告、作业和提交仓库分别维护在 `app/repositories/` 的对应领域模块中；`multi_role_repository.py` 仅保留旧导入的兼容入口。调整数据访问时优先修改对应领域模块。

个人考试的请求模型维护在 `app/schemas/student_exam.py`，用户隔离的数据访问维护在 `app/repositories/student_exam_repository.py`，路由与复习上下文复用同一仓库。状态分析按工作量、学习行为、目标、预测与证据质量拆分规则，入口负责按固定顺序编排。新增代码继续复用这些职责边界，避免在路由中重复 SQL 或复制分析规则。

```powershell
cd backend
python -m ruff check .
python -m pytest
```

学习通同步需要可用的外部登录态；LLM 回答和课堂生成需要相应服务配置。自动化测试中的假提供方与演示资料只验证代码路径，不代表已连接真实学校或已完成移动设备验收。

Ruff 启用 `E9` 与完整 `F` 规则，检查语法、未定义变量、重复定义和未使用导入等问题。不要用全局忽略绕过检查；兼容导出应显式声明，删除未使用变量时保留原有初始化或写入副作用。修改的 Python 模块使用 `python -m ruff format <文件>` 统一格式，再运行相关测试；接口行为变更同时维护 `docs/api/` 并执行根目录的文档同步与检查脚本。

## 反向代理限流

Uvicorn 默认处理可信代理的 `X-Forwarded-For` / `X-Forwarded-Proto`，可信名单缺省为 `127.0.0.1`。跨主机或容器反代需在启动前设置进程环境 `FORWARDED_ALLOW_IPS`，或使用 `--forwarded-allow-ips`，只信任实际代理 IP/CIDR；禁止通过 `*` 无差别信任外部请求。只写入应用的 `.env` 不保证 Uvicorn CLI 读取到这个变量。代理应追加或覆盖真实客户端地址，限流使用处理后的 ASGI 地址。

系统没有管理员 API：共享演示内容由内部数据准备工具生成，真实内容继续通过已有同步流程读取；普通用户不能跨用户修改数据。
