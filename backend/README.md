# CampusMate AI 后端

`backend/` 使用 FastAPI、SQLite 提供认证、个人事务、课程、通知、学习通同步、AI 对话和在线课堂服务。系统仅提供 `student` 用户角色；历史 `teacher` / `admin` 账号在认证时降为普通用户，不具有跨用户或跨学校权限。

## 能力与接口

| 能力 | 主要入口 | 当前实现 |
| --- | --- | --- |
| 健康检查 | `GET /api/v1/health` | 返回后端、知识库和 LLM 等运行状态 |
| 通知提取 | `POST /api/v1/notices/extract` | 手动输入通知原文，优先用已配置的 LLM，失败时规则降级；不确定字段标记需确认 |
| 手机消息整理 | `POST /api/v1/notices/ingest-batch` | 接收客户端筛选后的消息，去重，规则优先分类；模糊消息可批量交给 LLM，再生成通知和可执行待办 |
| 学习通 | `/api/v1/chaoxing/login`、`/status`、`/sync`、`/disconnect` | 连接账号并同步课程、通知、作业、考试等；登录态失效或需要验证时返回对应状态 |
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

## 在线课堂

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
