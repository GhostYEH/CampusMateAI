# CampusMate AI 后端

`backend/` 使用 FastAPI、SQLite 提供认证、个人事务、课程、通知、学习通同步、AI 对话和在线课堂服务。系统角色为 `student` 与 `admin`；历史 `teacher` 命名和测试数据不代表有独立教师角色。

## 能力与接口

| 能力 | 主要入口 | 当前实现 |
| --- | --- | --- |
| 健康检查 | `GET /api/v1/health` | 返回后端、知识库和 LLM 等运行状态 |
| 通知提取 | `POST /api/v1/notices/extract` | 手动输入通知原文，优先用已配置的 LLM，失败时规则降级；不确定字段标记需确认 |
| 手机消息整理 | `POST /api/v1/notices/ingest-batch` | 接收客户端筛选后的消息，去重，规则优先分类；模糊消息可批量交给 LLM，再生成通知和可执行待办 |
| 学习通 | `/api/v1/chaoxing/login`、`/status`、`/sync`、`/disconnect` | 连接账号并同步课程、通知、作业、考试等；登录态失效或需要验证时返回对应状态 |
| 可选教务连接 | `/api/v1/edu/*` | 学校系统探测、用户绑定与课表、成绩、考试同步；真实数据取决于学校适配器及用户授权 |
| AI 对话 | `POST /api/v1/counselor/chat`，兼容别名 `/api/v1/assistant/chat` | SSE / 非流式回答，可带经过校验的个人任务、课程和学习状态上下文；课堂建议须用户确认后才执行 |
| 知识库 | `/api/v1/knowledge/*` | MD/TXT/PDF/DOCX 导入、去重、BM25 检索与管理；当前聊天链路仍会使用它 |
| 课程内互动课堂 | `/api/v1/courses/{course_id}/interactive-classroom/*` 及课程 workspace 路由 | 按课程权限读取上下文、生成、查询进度和真实内容组成；由 `magicclass-service` 提供受管能力 |
| 学习空间状态 | `GET /api/v1/magicclass/learning-space/status` | 返回独立 `magicclass-app` 的可用性与公开 Origin，供 Web 导航入口使用 |
| 学习空间共同课堂 | `/api/v1/magicclass/learning-space/identity`、`/rooms`、`/invitations` | 复用账号唯一 ID 作为 UID，保存课堂文件、邀请、成员、翻页和文字消息；接受邀请后才允许读取内容 |
| Agent Runtime | `/api/v1/agent-jobs`、`/agent-runs` 等 | 持久化任务、运行事件、审批及产物接口；与普通聊天接口不同 |

完整路径以 [`app/api/router.py`](app/api/router.py) 中实际注册的路由为准；请求/响应契约以 FastAPI `/docs` 和对应 schema 为准。

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

## 验证

数据库启动会恢复旧教务绑定及学习反馈表原本声明的外键 / CHECK 约束；历史记录违反约束时会使升级整体回滚并停止启动，保留原数据，不自动删除或猜测修正。内存库借用连接未提交的写入会回滚，组合仓储事务须使用 `Database.transaction()` / `query()` 共享连接，嵌套事务使用保存点。

用户、会话、课程、班级、选课、公告、作业和提交仓库分别维护在 `app/repositories/` 的对应领域模块中；`multi_role_repository.py` 仅保留旧导入的兼容入口。调整数据访问时优先修改对应领域模块。

```powershell
cd backend
pytest
```

学习通同步需要可用的外部登录态；LLM 回答和课堂生成需要相应服务配置。自动化测试中的假提供方与演示资料只验证代码路径，不代表已连接真实学校或已完成移动设备验收。
