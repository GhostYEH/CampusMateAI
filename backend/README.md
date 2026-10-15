# CampusMate AI 后端

`backend/` 使用 FastAPI、SQLite 提供认证、个人事务、课程、通知、学习通同步、AI 对话和在线课堂服务。系统仅提供 `student` 用户角色；历史 `teacher` / `admin` 账号在认证时降为普通用户，不具有跨用户或跨学校权限。

## 能力与接口

| 能力 | 主要入口 | 当前实现 |
| --- | --- | --- |
| 健康检查 | `GET /api/v1/health` | 返回后端、知识库和 LLM 等运行状态 |
| 通知提取 | `POST /api/v1/notices/extract` | 手动输入通知原文，优先用已配置的 LLM，失败时规则降级；不确定字段标记需确认 |
| 手机消息整理 | `POST /api/v1/notices/ingest-batch` | 接收客户端筛选后的消息，去重，规则优先分类；模糊消息可批量交给 LLM，再生成通知和可执行待办 |
| 学习通 | `/api/v1/chaoxing/login`、`/status`、`/sync`、`/disconnect` | 连接账号并同步课程、通知、作业、考试等；登录态失效或需要验证时返回对应状态 |
| 学习通作业复习 | `GET /api/v1/tasks?status=completed`、`GET /api/v1/chaoxing/assignments/{task_id}/content`、`POST /api/v1/chaoxing/assignments/{task_id}/classroom` | 读取本人已提交作业、题干与选项，创建或复用受管讲解课堂及相似练习；生成后通过课程 job 接口查询进度 |
| 可选教务连接 | `/api/v1/edu/*` | 学校系统探测、用户绑定与课表、成绩、考试同步；真实数据取决于学校适配器及用户授权 |
| AI 对话 | `POST /api/v1/counselor/chat`，兼容别名 `/api/v1/assistant/chat` | SSE / 非流式回答，可带经过校验的个人任务、课程和学习状态上下文；课堂建议须用户确认后才执行 |
| 知识库 | `/api/v1/knowledge/status`、`/documents` | 只读查询知识库状态和文档；当前聊天链路仍使用内部 BM25 检索，资料导入由内部数据准备/同步流程提供 |
| 课程内互动课堂 | `/api/v1/courses/{course_id}/interactive-classroom/*` 及课程 workspace 路由 | 按课程权限读取上下文、生成、查询进度和真实内容组成；由 `magicclass-service` 提供受管能力 |
| 学习空间状态 | `GET /api/v1/magicclass/learning-space/status` | 返回独立 `magicclass-app` 的可用性与公开 Origin，供 Web 导航入口使用 |
| 学习空间共同课堂 | `/api/v1/magicclass/learning-space/identity`、`/rooms`、`/invitations` | 复用账号唯一 ID 作为 UID，保存课堂文件、邀请、成员、翻页和文字消息；接受邀请后才允许读取内容 |
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

1. `GET /api/v1/tasks?status=completed&page=1&page_size=200`，按 `has_more` 翻页，再筛选 `source=chaoxing`、未删除条目。使用返回的本站 `id` 作为 task_id。
2. `GET /api/v1/chaoxing/assignments/{task_id}/content` 读取题干和选项；`can_generate` 只表示提交状态、课程关联与题目状态匹配，不包含课堂服务可用性检测。
3. 用户点击进入时 `POST /api/v1/chaoxing/assignments/{task_id}/classroom`。服务端按本人、课程、作业、题目需求计算幂等键，创建或复用讲解任务。每日同步只采集作业，不主动生成课堂。
4. 对 queued/running 用 `GET /api/v1/courses/{course_id}/jobs/{job_id}` 查询；失败/取消可用对应 `/retry` 接口重试；completed 后进入返回工作台学习。Web 在题目未就绪时尝试一次同步，生成成功后自动进入播放。

生成内容包含逐题讲解及至少 3 道可作答的相似练习，可复用原选项并按新条件确定答案；这是模型生成的学习内容，不是学习通官方批阅。未识别的图片、过长题目或模型不可用会返回明确错误，不生成替代模板。

运行依赖见 [backend/.env.example](.env.example) 与 [受管服务配置](../magicclass-service/.env.example)：后端设置 `MAGICCLASS_FUSION_ENABLED=true`、可达的 `MAGICCLASS_SERVICE_URL`，两服务使用一致的 `MAGICCLASS_INTERNAL_SECRET`；受管服务另需配置 `MAGICCLASS_PROVIDER_BASE_URL`、`MAGICCLASS_PROVIDER_API_KEY`、`MAGICCLASS_PROVIDER_MODEL`。只设置后端通用 LLM 不代表课堂生成模型已配置。独立学习空间的 `MAGICCLASS_ENABLED` / `MAGICCLASS_EMBED_ORIGIN` 控制另一条内嵌链路，不代替受管课堂配置。

持久化涉及后端的 `chaoxing_credentials`（加密 Cookie）、`personal_tasks`（列表与提交状态）、`chaoxing_assignment_content`（题目快照及尝试时间）、`chaoxing_auto_sync`（下次尝试时间、租约与最近错误），以及受管服务自己的工作台、任务和幂等数据。新增表由数据库初始化建立；部署时保留两服务的数据目录及稳定密钥。没有公开的每日同步配置、立即执行后台 tick、下次执行时间或租约查询 API；维护时通过受控数据库诊断和日志排查，不手工改业务状态来伪造提交。

排查时先看本人 `/chaoxing/status` 是否需重新连接，再检查手动 `/chaoxing/sync` 的分区结果与题目快照。`chaoxing_daily_sync_tick_failed` 表示后台轮次异常，`chaoxing_daily_sync_failed` 表示单账号执行异常；日志中的 error_type 只用于定位，不能当作前端协议。作业复习接口的错误码、请求/响应示例、跨端适配与联调步骤见[外部连接](../docs/api/09-integrations.md#assignment-review-flow)。

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_chaoxing_assignment_review.py tests/test_chaoxing_sync_service.py tests/test_chaoxing_sync_sections.py tests/test_app_lifespan.py tests/test_openapi_docs.py -q
```

自动化测试覆盖用户隔离、提交门槛、题目采集与保留、后台租约与重启恢复、幂等生成和服务不可用分支。真实学习通页面解析、有效账号登录态以及外部模型生成质量仍需在实际部署验证。Web 已适配一键进入；Android、HarmonyOS 和微信小程序尚未接入该作业复习入口。

## 在线课堂

### Android 多人音视频共同课堂

Android 的“课程 → 同学一起学”已接入共同课堂身份、创建讨论课堂、UID 邀请/接受、成员、文字消息与火山 RTC 音视频。已有上传课件课堂也可接受邀请后加入通话；完整课件播放仍在 Web 学习空间，Android 显示共享页码。每堂最多 8 人（含发起人及待接受邀请），每位发起人最多 20 个活动课堂。

后端使用现有 `VOLC_RTC_APP_ID`（24 位）与 `VOLC_RTC_APP_KEY`，从已开通实时音视频服务的火山 RTC 应用取得后填入本地环境配置。AppKey 只留在后端，不要写入 APK、源码、日志或提交。此功能不需要 AI VoiceChat 配置、Seeduplex Key 或 AK/SK；与 Focus AI 语音独立。配置检查不等于云账号余额、真实连通性或通话质量已经通过验证。

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

这些入口依赖 `magicclass-service` 和相应模型提供方。服务未启用、不可达或缺少所需配置时，接口会返回真实的不可用状态；仓库中的页面和测试并不等于每台机器都能生成课堂。

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
