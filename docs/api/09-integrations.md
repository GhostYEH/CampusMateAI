# 学习通、教务连接与兼容接口

> 对照日期：2026-10-15。本模块共 34 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 学习通状态错误与缓存

`GET /api/v1/chaoxing/status` 的正常 HTTP/网络不可达仍返回 `status="unavailable"`，结果去重缓存 30 秒。意外服务端程序错误进入统一 500 `INTERNAL_ERROR` 信封，不把错误缓存为不可达，也不覆盖最近已知的登录态；可通过 `X-Request-ID` 定位。成功响应及过期登录态协议不变，客户端应区分 HTTP 错误和成功响应中的 status。Web、Android、HarmonyOS、微信小程序的状态接入源码已核对，本次运行验证仅覆盖后端与 Web 调用对照，移动端未进行原生构建或真机验收。

## 课表同步的内容更新

教务课表同步会比较完整的持久化内容，包括起止时间、校区、楼栋、教室、备注、教师与扩展信息。上述字段变化时更新记录并计入 `updated`，再次同步相同内容计入 `unchanged`。旧记录首次使用完整摘要同步可能计入一次 `updated`，不增加重复课表项；已有学期回填和空课表校验保持兼容。Web、Android、HarmonyOS、微信小程序均读取教务课表，响应字段和分页方式无需迁移；本次仅验证后端和调用源码，未进行移动端构建或真机验证。

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/chaoxing/login` | 登录学习通 |
| GET | `/api/v1/chaoxing/status` | 读取学习通状态 |
| POST | `/api/v1/chaoxing/sync` | 同步学习通 |
| POST | `/api/v1/chaoxing/disconnect` | 断开连接学习通 |
| GET | `/api/v1/chaoxing/assignments/{task_id}/content` | 读取本人学习通作业题干与选项快照 |
| POST | `/api/v1/chaoxing/assignments/{task_id}/classroom` | 生成已提交作业讲解与相似练习 |
| GET | `/api/v1/academic/providers` | [deprecated] 委托 EduConnector.detect |
| GET | `/api/v1/academic/status` | [deprecated] 委托 EduConnector.get_binding |
| POST | `/api/v1/academic/bind` | [deprecated] 委托 EduConnector.bind |
| DELETE | `/api/v1/academic/binding` | [deprecated] 委托 EduConnector.unbind |
| GET | `/api/v1/edu/detect` | 探测学校教务厂商与系统类型（不编造 URL） |
| GET | `/api/v1/edu/config/{university_id}` | 获取学校教务系统配置 |
| GET | `/api/v1/edu/binding` | 获取当前用户教务绑定（不含凭证） |
| POST | `/api/v1/edu/bind` | [deprecated] 兼容旧版一次性绑定接口 |
| DELETE | `/api/v1/edu/binding` | 解绑教务账号 |
| POST | `/api/v1/edu/sync/profile` | 同步profile |
| POST | `/api/v1/edu/sync/schedule` | 同步课表 |
| POST | `/api/v1/edu/sync/grade` | 同步成绩 |
| POST | `/api/v1/edu/sync/exam` | 同步考试 |
| GET | `/api/v1/edu/sync/records` | 列出同步记录 |
| GET | `/api/v1/edu/schedule/semesters` | 列出已同步课表的所有学期 |
| GET | `/api/v1/edu/schedule/items` | 读取已持久化的课表条目 |
| GET | `/api/v1/edu/grade/semesters` | 列出已同步成绩的所有学期 |
| GET | `/api/v1/edu/grade/items` | 读取已持久化的成绩条目 |
| GET | `/api/v1/edu/exam/semesters` | 列出已同步考试安排的所有学期 |
| GET | `/api/v1/edu/exam/items` | 读取已持久化的考试安排，补考通过 exam_type 区分 |
| GET | `/api/v1/edu/systems/{university_id}` | 列出学校的所有教务系统（1:N） |
| POST | `/api/v1/edu/connections` | 创建教务连接（返回 connection_id + 初始状态） |
| GET | `/api/v1/edu/connections/{connection_id}` | 读取教务连接 |
| POST | `/api/v1/edu/connections/{connection_id}/pre-login` | 预登录：获取验证码图片等预登录数据 |
| POST | `/api/v1/edu/connections/{connection_id}/continue` | 推进连接状态 |
| POST | `/api/v1/edu/connections/from-url` | 从教务系统 URL 创建连接（便捷流程） |
| POST | `/api/v1/edu/discovery/probe` | 探测教务系统 URL（不需要 university_id） |
| POST | `/api/v1/edu/discovery/submit-url` | 用户手动提交教务系统 URL |

<a id="assignment-review-flow"></a>
## 已提交作业与一键讲解接入

所有下列 API 均以 `/api/v1` 为前缀并携带本站 Bearer access token。列表来源是个人待办 `/tasks`，不是班级作业 `/student/assignments`，也不是独立学习空间自身 Origin 下的 `/api/*`。每天自动同步只采集数据；点击“一键进入讲解”才创建或恢复生成任务，点击前不应批量 POST 为整个列表生成课堂。

| 步骤 | 请求 / 处理 | 接入要求 |
| --- | --- | --- |
| 读取已提交作业 | `GET /api/v1/tasks?status=completed&page=1&page_size=200` | 接口没有 source 筛选参数；读取每页 items，再保留 source=chaoxing、status=completed 且 deleted_at=null 的作业。total/has_more 是所有符合 completed 筛选的个人待办统计，不能当作学习通作业数量。 |
| 读取剩余页 | 按返回的 has_more 递增 page，直到 false | 后续页即使没有学习通作业也应继续；不要仅筛选第一页。服务端按 deadline 升序、无截止时间置后，再按 created_at 降序；它不是提交时间排序。 |
| 展示作业 | id/title/source_name/course_id/completed_at/remote_submitted_at/last_synced_at | id 是后续路径中的 task_id，external_id 只是远端引用。completed_at 是本站确认完成的时间，不能冒充学习通精确提交时间；`remote_submitted_at` 是可空的远端提交时间，未观测到时为 null；成绩字段仍不返回。 |
| 可选查看题目 | `GET /api/v1/chaoxing/assignments/{task_id}/content` | 只读已同步快照，不会隐式触发学习通网络访问；不必为列表中每份作业预请求题目。 |
| 点击进入讲解 | `POST /api/v1/chaoxing/assignments/{task_id}/classroom` | 无需请求体或客户端幂等键；仅 completed 且题目状态匹配的本人作业允许生成。保留返回 course_id/workspace_id/job.id，按原始任务继续查询。 |
| 补同步题目 | POST 返回 409 且 message=assignment_content_not_current 时，`POST /api/v1/chaoxing/sync` 后重试原请求 | Web 自动尝试一次；同步可能部分成功或返回 sync_in_progress，再次失败应提示用户，不无限同步。复习接口本身不会替客户端同步。 |
| 等待生成 | `GET /api/v1/courses/{course_id}/jobs/{job_id}` | queued/running 时显示 progress；Web 每约 2 秒查询，最长查看 30 分钟。HTTP 201 表示已接受或复用任务，不代表已生成完成。 |
| 重试失败 | `POST /api/v1/courses/{course_id}/jobs/{job_id}/retry` | failed/cancelled 才显式重试；该接口返回 job 对象，更新本地状态后继续轮询。同一次点击不要无限重试。 |
| 进入学习 | job.status=completed 后打开 `/courses/{course_id}/workspaces/{workspace_id}?mode=playback` | 这是 Web 路由，不是后端 API。已有 completed 任务直接进入；新任务须等待完成，不把 failed/cancelled 当作可播放。 |
| 离开后回来 | 停止页面轮询；再次点击调用原 classroom POST | 页面离开不会自动取消服务端任务。相同需求重放会返回同一任务当前状态；无需保存 JWT、内部服务地址或题目正文到跳转参数。 |

列表脱敏示例（已省略其他 PersonalTaskOut 字段，完整字段见[字段字典](schemas.md#schema-personaltaskout)）：

```json
{
  "items": [
    {
      "id": "ptask_demo", "title": "函数练习", "source": "chaoxing",
      "external_id": "remote_work_demo", "source_name": "高等数学",
      "course_id": "course_demo", "status": "completed", "deleted_at": null,
      "completed_at": "2026-10-15T01:00:00+00:00",
      "last_synced_at": "2026-10-15T01:00:00+00:00"
    }
  ],
  "total": 1, "page": 1, "page_size": 200, "has_more": false
}
```

列表能展示不意味着一定能生成。course_id=null 时提示重新同步课程关联；pending 状态只能到学习通提交后再同步，本站完成/恢复/编辑接口对学习通来源只读。登录态过期时，列表和已有快照仍可能可读；同步失败不得清空列表或改成“没有作业”。若只希望显示本次新数据，可根据 last_synced_at/fetched_at 提醒用户刷新，但不可把 `current` 当作时效判断。

错误恢复按 HTTP 与 message/details 共同处理。HTTPException 使用 `{code:"HTTP_ERROR",message:"assignment_content_not_current",details:null,request_id:"req_demo"}` 这类信封；部分中文 AppException 有独立 code，不要只读旧的 detail，也不要按 HTTP_ERROR 一种 code 区分全部业务分支。

| HTTP / 信号 | 含义 | 恢复方式 |
| --- | --- | --- |
| 401 本站认证无效 | 本站会话不可用 | 按本站认证流程刷新或登录；区分第三方同步中的 reauth_required。 |
| 404 chaoxing_assignment_not_found | 其他用户、非学习通、已删除或不存在的个人待办 | 刷新列表，不用 external_id 或班级作业 ID 重试。 |
| 409 assignment_not_submitted | 最近同步的作业仍为 pending | 到学习通提交并重新同步。 |
| 409 assignment_course_unavailable | 作业无 course_id | 重新同步课程关联，继续显示可读的作业信息。 |
| 409 assignment_content_not_current | 题目缺失或快照提交状态不匹配 | 同步一次后重试；仍失败时检查 assignments 分区警告。 |
| 409 sync_in_progress | 同进程内已有该用户的同步或账号操作 | 稍后重新查看，不并发堆积同步请求。 |
| 422 assignment_images_require_text | 题目图片没有可读文字描述 | 当前链路没有 OCR 补录接口；等待资料适配，不把图片占位当作完整题目。 |
| 422 assignment_content_too_large | 整份生成需求超出 24,000 UTF-16 code units | 当前接口不支持选题或分批生成；提示内容超限，不在客户端截题后绕过。 |
| 503 MAGICCLASS_FUSION_UNAVAILABLE | 受管服务关闭、不可达、鉴权或模型配置不可用 | 检查 details.reason 和两服务配置；保留作业和当前任务信息。 |
| job.status=failed/cancelled | 异步生成未完成 | 展示 job.error_code；由用户触发上述 retry，不能当作 HTTP 成功即课堂成功。 |

同步题目阶段的 warnings 中也可能出现 `assignment_content:assignment_content_too_large`，它表示远端单页响应超过 4 MiB，与生成 POST 的 24,000 单元限制是两个环节。网络/页面变化可能映射为 assignment_content_unavailable；要结合分区状态、登录状态和日志定位，不能凭警告假定题目为空或平台已提交。

部署与联调顺序：先通过本人 login/status/sync 确认学习通有效、作业列表与内容快照存在，再检查 `GET /api/v1/magicclass/fusion/providers` 中 `providers.llm` 和 `GET /api/v1/magicclass/fusion/status` 的受管服务状态，最后发起单份作业生成、查询 job 并播放 quiz。分别验证首次生成、重复进入复用、未提交拒绝、无题目补同步、模型不可用、任务失败重试及跨用户 404。自动化结果不代替真实账号页面解析和真实模型产物检查。配置、调度、持久化及日志入口见[后端说明](../../backend/README.md#学习通每日同步与作业复习)。

## 接口契约

已连接账号由 FastAPI 后台任务每日同步，首次连接或重新连接后进入下一轮待同步队列；成功后从本轮结束起间隔 24 小时，服务重启后补执行已到期账号。轮询在本批账号处理结束后等待 60 秒，不保证账号连接后 60 秒内执行，也不固定每天零点。普通失败或部分成功 30 分钟后重试，需要重新认证或凭据损坏则等待重新连接或下一天重查。断开连接后不再领取新的后台任务；已在其他进程执行的请求可能仍完成，旧同步不会重新创建已删除凭据或覆盖新登录的 Cookie。后端必须持续运行；浏览器不需要保持打开。

后台同步使用持久化 15 分钟租约和 10 分钟单账号执行预算，重启或共享同一数据库的多进程不会立即重复领取同一账号后台任务；与同进程手动同步、登录和解绑共用用户互斥锁。租约仅覆盖后台领取，不保证其他进程的手动操作与后台任务全局串行。每轮最多处理 25 个账号，单次题目抓取最多 12 份、并发 3、每份预算 12 秒；缺失、采集超过 24 小时或提交状态变化的题目按最近尝试时间轮转，后续重试继续补齐，不保证变化的作业一定在本批内完成。失败不清空已经同步的题目。

`POST /chaoxing/sync` 保留既有结构；题目缺失/抓取失败时 `sections.assignments.status=partial`、`complete=false`，warnings 增加 `assignment_content:<reason>`，包括 `assignment_content_pending`、`assignment_questions_unavailable`、`assignment_content_unavailable`、`network_error`、`reauth_required`、`verification_required`、`assignment_url_not_allowed` 等。`error_message` 为“作业列表已同步，部分题目暂未获取，将在下次同步重试”。列表和提交状态仍可成功同步，不把题目不可读当成没有作业。

### `GET /api/v1/chaoxing/assignments/{task_id}/content`

用途：读取本人学习通作业题干和原始选项，不触发外部请求。

鉴权：Bearer access token；当前活跃用户，仅限本人的 `source=chaoxing` 且未删除的个人待办。`task_id` 是本站个人待办 ID，不是学习通远端作业编号或班级作业 ID。其他用户、普通待办和不存在的作业均返回 404。

Web 封装：`getChaoxingAssignmentContent`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

实现：[chaoxing_assignments.py](../../backend/app/api/routes/chaoxing_assignments.py)，`get_content`。

参数：path `task_id: string`，必填。请求体：无。

响应：200 `application/json` 动态对象，所有下列顶层字段都会出现：`task_id: string`、`course_id: string|null`、`status: string`（学习通观测映射后的 pending/completed）、`available: boolean`（是否有可读题目）、`current: boolean`（快照采集时的提交状态是否与当前一致）、`can_generate: boolean`（completed、有课程且 current）、`fetched_at: string|null`、`questions: array`。

每个 question 是 `{number: integer, stem: string, options: string[]}`；number 从 1 连续编号。题干、数学文本和选项保留可读文字，不返回原始 HTML、脚本、Cookie、学生答案或官方评分。未采集到内容时 `available/current/can_generate=false`、`questions=[]`、`fetched_at=null`。旧快照可查看，但未同步提交后快照时不可用于生成；`can_generate` 仅反映数据前置条件，课堂服务可用性仍由生成接口决定。

`current` 仅比较快照采集时保存的 pending/completed 与待办当前状态，不表示刚刚刷新过、与学习通实时一致或已取得最终版本。`fetched_at` 是成功采集该快照的同步轮次时间；采集失败保留此时间和旧题目。`can_generate=true` 仍可能因题目中未识别图片、完整需求过长、课程无权访问或模型不可用而被 POST 拒绝。

脱敏示例：

```json
{"task_id":"ptask_demo","course_id":"course_demo","status":"completed","available":true,"current":true,"can_generate":true,"fetched_at":"2026-10-15T01:00:00+00:00","questions":[{"number":1,"stem":"x=2时，x+1是多少？","options":["A. 2","B. 3","C. 4"]}]}
```

异常：401 本站登录无效；404 `message=chaoxing_assignment_not_found`；公共错误信封见接入约定。

### `POST /api/v1/chaoxing/assignments/{task_id}/classroom`

用途：调用现有受管在线课堂，为已在学习通提交的作业生成逐题讲解和至少 3 道可作答的相似练习。

鉴权：Bearer access token；本人未删除的学习通个人待办，并检查所关联课程的访问权限。服务端从已同步的真实状态判断是否已提交；不接受客户端伪造提交状态、题目、答案或课程归属。

Web 封装：`generateChaoxingAssignmentClassroom`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

实现：[chaoxing_assignments.py](../../backend/app/api/routes/chaoxing_assignments.py)，`generate_review`。

参数：path `task_id: string`，必填。请求体：无；无需 `Idempotency-Key` 请求头，服务端按本人、课程、作业和题目内容生成稳定幂等键。例：`POST /api/v1/chaoxing/assignments/ptask_demo/classroom`。

业务前置条件：学习通已同步为 completed（包含已交、待批阅等观测），存在该提交状态下的题目快照，存在可访问课程，并已启用受管课堂与生成模型。题目仅使用文字与带文字描述的图片；无法识别的图片题和超过 24,000 UTF-16 code units 的整份需求返回 422，避免遗漏题目后生成不完整讲解。服务端需求指定独立推导和 AI 讲解标记，不冒充官方答案；相似题改变条件、情境或数据，可复用部分原题选项但重新确定答案。

响应：201 `application/json`，包含 `task_id/course_id/workspace_id: string`、`question_count: integer`，以及既有受管生成结果 `source="provider"`、`job: object`（id/status/progress/artifact_id/mode/error_code）、可选 `job_id/stage_id/stage`。异步返回不代表内容已经生成，须按 job.status 处理。例：

```json
{"task_id":"ptask_demo","course_id":"course_demo","workspace_id":"ws_demo","question_count":1,"source":"provider","job_id":"job_demo","job":{"id":"job_demo","status":"queued","progress":0,"artifact_id":null,"mode":"slide","error_code":null}}
```

工作台按本人/课程/作业复用。相同题目重复点击、刷新或跨客户端请求会复用同一生成任务；题目或标题发生变化会创建新任务。失败/取消后重复 POST 仍返回同一任务，使用 `POST /courses/{course_id}/jobs/{job_id}/retry` 重试；用 `GET /courses/{course_id}/jobs/{job_id}` 轮询，直到 completed/failed/cancelled，断网后可重复 POST 恢复查询。完成后进入 `/courses/{course_id}/workspaces/{workspace_id}?mode=playback`；工作台的 quiz 场景使用现有答题、解析和学习记录流程。

异常：401 本站登录无效；403 课程权限不足；404 作业不可见或课程不存在；409 的 `message` 为 `assignment_not_submitted`（先到学习通提交并同步）、`assignment_course_unavailable`（重新同步课程关联）或 `assignment_content_not_current`（同步提交后的题目）。422 的 message 为 `assignment_images_require_text` 或 `assignment_content_too_large`。503 为受管服务或模型不可用，沿用 `MAGICCLASS_FUSION_UNAVAILABLE`；受管服务的权限、资源、限流与幂等错误沿用 [课堂契约](14-magicclass.md)。不会用本地模板伪装生成成功。

兼容性：现有 login/status/sync/disconnect 请求和响应字段保留。每日服务端同步对所有已连接客户端生效；Web 已接入题目查看、生成、进度、重试及播放入口。在线课堂首页和学习空间侧栏通过 `GET /tasks?status=completed` 分页读取并筛选 source=chaoxing 的已提交作业；一键进入会复用上述生成接口、必要时同步缺失题目、重试已有失败任务，完成后自动跳转播放器，无需再次确认进入。Android/HarmonyOS/微信小程序尚未接入新增作业复习入口，也未做本次原生端验证；它们可按上述新增接口适配。

### `POST /api/v1/chaoxing/login`

用途：登录学习通。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/chaoxing.py](../../backend/app/api/routes/chaoxing.py)，`login_chaoxing`。

Web 封装：`loginChaoxing`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

学习通错误属于第三方账号连接状态，不能因第三方 401 清除 CampusMate 登录态；同步返回分区状态及警告，见 [响应补充](response-contracts.md#sync)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[ChaoxingLoginRequest](schemas.md#schema-chaoxingloginrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | — | 登录用户名 |
| `password` | string | 是 | — | 登录密码，仅请求使用 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "username": "<username>",
  "password": "<password>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'status': 'success'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 401 | HTTPException | f'Chaoxing login failed: {msg}' |
| 403 | HTTPException | 'reauth_required / verification_required' |

### `GET /api/v1/chaoxing/status`

用途：读取学习通状态。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/chaoxing.py](../../backend/app/api/routes/chaoxing.py)，`get_chaoxing_status`。

Web 封装：`getChaoxingStatus`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

学习通错误属于第三方账号连接状态，不能因第三方 401 清除 CampusMate 登录态；同步返回分区状态及警告，见 [响应补充](response-contracts.md#sync)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ChaoxingSyncStatus](schemas.md#schema-chaoxingsyncstatus) |
| 503 | application/json | `code: CHAOXING_CREDENTIALS_UNAVAILABLE`；已有连接信息无法解密或损坏，保留已同步数据，重新登录学习通或解除连接后重绑；等待和自动重试无法修复 |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `last_synced_at` | string / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `courses` | integer | 否 | default=0 | — |
| `teachers` | integer | 否 | default=0 | — |
| `pending_assignments` | integer | 否 | default=0 | — |
| `notices` | integer | 否 | default=0 | — |
| `warnings` | array<string> | 否 | — | 警告列表；成功也需展示降级或缺失数据 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/chaoxing/sync`

用途：同步学习通。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/chaoxing.py](../../backend/app/api/routes/chaoxing.py)，`sync_chaoxing`。

Web 封装：`syncChaoxing`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

学习通错误属于第三方账号连接状态，不能因第三方 401 清除 CampusMate 登录态；同步返回分区状态及警告，见 [响应补充](response-contracts.md#sync)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
await _perform_sync_chaoxing(user, container)
```

```python
{'status': 'sync completed', 'notice_sync': 'available' if notice_sync_available else 'unavailable', 'source': 'chaoxing_live', 'complete': all((section['status'] == 'complete' for section in sections.values())), 'warnings': warnings, 'stats': stats, 'sections': sections}
```

```python
container.notice_extraction.extract_bounded(content, source_name=course['name'], published_at=published_at)
```

自动同步使用有界规则提取，不调用外部 LLM。空文本、超过 5000 字及其他提取失败会保留通知原文，继续处理后续通知，但 `sections.notices` 不会标记为 `complete`，并在警告与错误码中说明处理失败；后续同步可在原通知上重试生成待办。

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | HTTPException | 'sync_in_progress' |
| 503 | CHAOXING_CREDENTIALS_UNAVAILABLE | 连接信息无法读取，请重新连接学习通；不应自动反复重试 |
| 401 | HTTPException | 'Chaoxing credentials not found' |
| 401 | HTTPException | 'reauth_required' |
| 403 | HTTPException | 'verification_required' |
| 502 | HTTPException | f'Sync failed: {error_msg}' |
| 依业务分支 | _fetch_http_exception | error |

### `POST /api/v1/chaoxing/disconnect`

用途：断开连接学习通。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/chaoxing.py](../../backend/app/api/routes/chaoxing.py)，`disconnect_chaoxing`。

Web 封装：`disconnectChaoxing`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

学习通错误属于第三方账号连接状态，不能因第三方 401 清除 CampusMate 登录态；同步返回分区状态及警告，见 [响应补充](response-contracts.md#sync)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'status': 'disconnected'}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/academic/providers`

用途：[deprecated] 委托 EduConnector.detect。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/academic.py](../../backend/app/api/routes/academic.py)，`providers`。

Web 封装：`getAcademicProviders`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

[deprecated] 委托 EduConnector.detect。

兼容接口，建议新前端使用 `/edu/*`。POST /academic/bind 始终返回 ACADEMIC_UNSUPPORTED（409），并未完成绑定。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'items': [{'university_id': university.id, 'provider': detect.provider, 'status': 'available' if supported else 'unsupported', 'supports': ['courses', 'schedule', 'grades', 'exams'] if supported else []}], '_deprecated': 'Use GET /api/v1/edu/detect instead'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `GET /api/v1/academic/status`

用途：[deprecated] 委托 EduConnector.get_binding。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/academic.py](../../backend/app/api/routes/academic.py)，`status`。

Web 封装：`getAcademicStatus`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

[deprecated] 委托 EduConnector.get_binding。

兼容接口，建议新前端使用 `/edu/*`。POST /academic/bind 始终返回 ACADEMIC_UNSUPPORTED（409），并未完成绑定。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'status': binding.connection_status, 'provider': binding.provider, 'last_synced_at': binding.last_synced_at, 'external_student_id': binding.external_student_id, '_deprecated': 'Use GET /api/v1/edu/binding instead'}
```

```python
{'status': 'unsupported' if not detect.detected else 'unbound', 'provider': detect.provider, 'last_synced_at': None, 'external_student_id': None, '_deprecated': 'Use GET /api/v1/edu/binding instead'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `POST /api/v1/academic/bind`

用途：[deprecated] 委托 EduConnector.bind。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/academic.py](../../backend/app/api/routes/academic.py)，`bind`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

[deprecated] 委托 EduConnector.bind。

兼容接口，建议新前端使用 `/edu/*`。POST /academic/bind 始终返回 ACADEMIC_UNSUPPORTED（409），并未完成绑定。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[AcademicBindRequest](schemas.md#schema-academicbindrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=1; maxLength=128 | 登录用户名 |
| `password` | string (password) | 是 | format="password"; writeOnly=true | 登录密码，仅请求使用 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "username": "<username>",
  "password": "<password>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | ACADEMIC_UNSUPPORTED | 当前学校暂未支持自动教务同步 |

### `DELETE /api/v1/academic/binding`

用途：[deprecated] 委托 EduConnector.unbind。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/academic.py](../../backend/app/api/routes/academic.py)，`disconnect`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

[deprecated] 委托 EduConnector.unbind。

兼容接口，建议新前端使用 `/edu/*`。POST /academic/bind 始终返回 ACADEMIC_UNSUPPORTED（409），并未完成绑定。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True, '_deprecated': 'Use DELETE /api/v1/edu/binding instead'}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/detect`

用途：探测学校教务厂商与系统类型（不编造 URL）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`detect_university`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

探测学校教务厂商与系统类型（不编造 URL）。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `university_id` | string | 是 | minLength=1; maxLength=128 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduDetectResult](schemas.md#schema-edudetectresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `system_type` | string | 是 | — | — |
| `detected` | boolean | 是 | — | — |
| `confidence` | number | 否 | default=0.0 | — |
| `evidence` | array<object> | 否 | — | — |
| `detection_source` | string | 否 | default="UNKNOWN" | — |
| `reason` | string / null | 否 | — | 原因 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/config/{university_id}`

用途：获取学校教务系统配置。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`get_config`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

获取学校教务系统配置。

若不存在，自动创建默认配置（所有 URL=null, url_status=not_discovered）。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `university_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSystemConfigOut](schemas.md#schema-edusystemconfigout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `university_id` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `system_type` | string | 是 | — | — |
| `academic_system_url` | string / null | 否 | — | — |
| `academic_system_url_status` | string | 是 | — | — |
| `undergrad_system_url` | string / null | 否 | — | — |
| `undergrad_system_url_status` | string | 是 | — | — |
| `postgrad_system_url` | string / null | 否 | — | — |
| `postgrad_system_url_status` | string | 是 | — | — |
| `sso_url` | string / null | 否 | — | — |
| `sso_url_status` | string | 是 | — | — |
| `cas_url` | string / null | 否 | — | — |
| `cas_url_status` | string | 是 | — | — |
| `webvpn_url` | string / null | 否 | — | — |
| `webvpn_url_status` | string | 是 | — | — |
| `login_method` | string | 是 | — | — |
| `captcha_type` | string | 是 | — | — |
| `requires_campus_network` | boolean / null | 否 | — | — |
| `supported_features` | array<string> | 否 | — | — |
| `school_code` | string / null | 否 | — | 学校代码 |
| `notes` | string / null | 否 | — | — |
| `data_source` | string | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/binding`

用途：获取当前用户教务绑定（不含凭证）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`get_binding`。

Web 封装：`getEduBinding`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

获取当前用户教务绑定（不含凭证）。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduBindingOut](schemas.md#schema-edubindingout) / null |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/bind`

用途：[deprecated] 兼容旧版一次性绑定接口。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`bind`。

Web 封装：`bindEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

[deprecated] 兼容旧版一次性绑定接口。

新客户端应使用 EduConnection：创建连接后调用 continue，认证成功再生成 EduBinding。
本兼容端点仍委托同一个 EduConnector/Session/Binding 存储链路，并通过响应头提示迁移。

需要先选择大学（PUT /profile/university）。
username/password 仅用于一次认证，不会明文存储。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduBindRequest](schemas.md#schema-edubindrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=1; maxLength=128 | 登录用户名 |
| `password` | string (password) | 是 | format="password"; writeOnly=true | 登录密码，仅请求使用 |
| `system_type` | string | 否 | default="undergrad" | undergrad / postgrad |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "username": "<username>",
  "password": "<password>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduBindingOut](schemas.md#schema-edubindingout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string / null | 否 | — | — |
| `university_id` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `supported_features` | array<string> | 否 | — | — |
| `system_type` | string | 是 | — | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `connection_status` | string | 是 | — | — |
| `session_type` | string / null | 否 | — | — |
| `last_authenticated_at` | string / null | 否 | — | — |
| `session_expires_at` | string / null | 否 | — | — |
| `last_synced_at` | string / null | 否 | — | — |
| `last_sync_status` | string / null | 否 | — | — |
| `last_error` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |
| 401 | 'EDU_LOGIN_FAILED' | 服务器内部错误 |
| 503 | 'EDU_ADAPTER_UNAVAILABLE' | 服务器内部错误 |

### `DELETE /api/v1/edu/binding`

用途：解绑教务账号。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`unbind`。

Web 封装：`unbindEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

解绑教务账号。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/sync/profile`

用途：同步profile。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`sync_profile`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSyncResult](schemas.md#schema-edusyncresult) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 否 | default=0 | — |
| `error_message` | string / null | 否 | — | — |
| `profile` | [EduProfile](schemas.md#schema-eduprofile) / null | 否 | — | — |
| `schedule` | [EduSchedule](schemas.md#schema-eduschedule) / null | 否 | — | — |
| `grade` | [EduGrade](schemas.md#schema-edugrade) / null | 否 | — | — |
| `exam` | [EduExam](schemas.md#schema-eduexam) / null | 否 | — | — |
| `inserted` | integer | 否 | default=0 | — |
| `updated` | integer | 否 | default=0 | — |
| `unchanged` | integer | 否 | default=0 | — |
| `removed` | integer | 否 | default=0 | — |
| `failed` | integer | 否 | default=0 | — |
| `sync_batch_id` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `persisted` | boolean | 否 | default=false | — |
| `stage` | string / null | 否 | — | — |
| `previous_schedule_preserved` | boolean / null | 否 | — | — |
| `requires_user_action` | string / null | 否 | — | — |
| `protocol_source` | string / null | 否 | — | — |

未绑定教务账号时**不返回 404**：接口仍是 HTTP 200，`status="failed"`、`error_message="未绑定教务账号"`，其余字段为默认值。客户端必须检查业务 `status`，不能只看 HTTP 状态码。

```json
{
  "sync_type": "profile",
  "status": "failed",
  "items_count": 0,
  "error_message": "未绑定教务账号",
  "inserted": 0,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "failed": 0,
  "persisted": false
}
```

契约未变更：这里刻意保持 HTTP 200 + `status=failed`，**没有**为匹配错误字典改成 404；客户端不能只按 HTTP 状态码判断成功。四个 sync 接口的实际调用方为 Web（`syncEdu`）、Android（`ApiService` 的 `edu/sync/*`）、HarmonyOS（`ApiClient` 的 `eduSync`）和微信小程序（`repository.ts`），本轮仅核对了源码调用点与既有 `status` 分支，未做四端运行时验收。

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/sync/schedule`

用途：同步课表。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`sync_schedule`。

Web 封装：`syncEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | string约束: maxLength=64 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSyncResult](schemas.md#schema-edusyncresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 否 | default=0 | — |
| `error_message` | string / null | 否 | — | — |
| `profile` | [EduProfile](schemas.md#schema-eduprofile) / null | 否 | — | — |
| `schedule` | [EduSchedule](schemas.md#schema-eduschedule) / null | 否 | — | — |
| `grade` | [EduGrade](schemas.md#schema-edugrade) / null | 否 | — | — |
| `exam` | [EduExam](schemas.md#schema-eduexam) / null | 否 | — | — |
| `inserted` | integer | 否 | default=0 | — |
| `updated` | integer | 否 | default=0 | — |
| `unchanged` | integer | 否 | default=0 | — |
| `removed` | integer | 否 | default=0 | — |
| `failed` | integer | 否 | default=0 | — |
| `sync_batch_id` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `persisted` | boolean | 否 | default=false | — |
| `stage` | string / null | 否 | — | — |
| `previous_schedule_preserved` | boolean / null | 否 | — | — |
| `requires_user_action` | string / null | 否 | — | — |
| `protocol_source` | string / null | 否 | — | — |

未绑定教务账号时**不返回 404**：接口仍是 HTTP 200，`status="failed"`、`error_message="未绑定教务账号"`，其余字段为默认值。客户端必须检查业务 `status`，不能只看 HTTP 状态码。

```json
{
  "sync_type": "schedule",
  "status": "failed",
  "items_count": 0,
  "error_message": "未绑定教务账号",
  "inserted": 0,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "failed": 0,
  "persisted": false
}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/sync/grade`

用途：同步成绩。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`sync_grade`。

Web 封装：`syncEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | string约束: maxLength=64 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSyncResult](schemas.md#schema-edusyncresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 否 | default=0 | — |
| `error_message` | string / null | 否 | — | — |
| `profile` | [EduProfile](schemas.md#schema-eduprofile) / null | 否 | — | — |
| `schedule` | [EduSchedule](schemas.md#schema-eduschedule) / null | 否 | — | — |
| `grade` | [EduGrade](schemas.md#schema-edugrade) / null | 否 | — | — |
| `exam` | [EduExam](schemas.md#schema-eduexam) / null | 否 | — | — |
| `inserted` | integer | 否 | default=0 | — |
| `updated` | integer | 否 | default=0 | — |
| `unchanged` | integer | 否 | default=0 | — |
| `removed` | integer | 否 | default=0 | — |
| `failed` | integer | 否 | default=0 | — |
| `sync_batch_id` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `persisted` | boolean | 否 | default=false | — |
| `stage` | string / null | 否 | — | — |
| `previous_schedule_preserved` | boolean / null | 否 | — | — |
| `requires_user_action` | string / null | 否 | — | — |
| `protocol_source` | string / null | 否 | — | — |

未绑定教务账号时**不返回 404**：接口仍是 HTTP 200，`status="failed"`、`error_message="未绑定教务账号"`，其余字段为默认值。客户端必须检查业务 `status`，不能只看 HTTP 状态码。

```json
{
  "sync_type": "grade",
  "status": "failed",
  "items_count": 0,
  "error_message": "未绑定教务账号",
  "inserted": 0,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "failed": 0,
  "persisted": false
}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/sync/exam`

用途：同步考试。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`sync_exam`。

Web 封装：`syncEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | string约束: maxLength=64 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSyncResult](schemas.md#schema-edusyncresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 否 | default=0 | — |
| `error_message` | string / null | 否 | — | — |
| `profile` | [EduProfile](schemas.md#schema-eduprofile) / null | 否 | — | — |
| `schedule` | [EduSchedule](schemas.md#schema-eduschedule) / null | 否 | — | — |
| `grade` | [EduGrade](schemas.md#schema-edugrade) / null | 否 | — | — |
| `exam` | [EduExam](schemas.md#schema-eduexam) / null | 否 | — | — |
| `inserted` | integer | 否 | default=0 | — |
| `updated` | integer | 否 | default=0 | — |
| `unchanged` | integer | 否 | default=0 | — |
| `removed` | integer | 否 | default=0 | — |
| `failed` | integer | 否 | default=0 | — |
| `sync_batch_id` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `persisted` | boolean | 否 | default=false | — |
| `stage` | string / null | 否 | — | — |
| `previous_schedule_preserved` | boolean / null | 否 | — | — |
| `requires_user_action` | string / null | 否 | — | — |
| `protocol_source` | string / null | 否 | — | — |

未绑定教务账号时**不返回 404**：接口仍是 HTTP 200，`status="failed"`、`error_message="未绑定教务账号"`，其余字段为默认值。客户端必须检查业务 `status`，不能只看 HTTP 状态码。

```json
{
  "sync_type": "exam",
  "status": "failed",
  "items_count": 0,
  "error_message": "未绑定教务账号",
  "inserted": 0,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "failed": 0,
  "persisted": false
}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/sync/records`

用途：列出同步记录。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_sync_records`。

Web 封装：`getEduSyncRecords`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `limit` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[EduSyncRecordOut](schemas.md#schema-edusyncrecordout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/schedule/semesters`

用途：列出已同步课表的所有学期。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_schedule_semesters`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出已同步课表的所有学期。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<string> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/schedule/items`

用途：读取已持久化的课表条目。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_schedule_items`。

Web 封装：`getScheduleItems`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

读取已持久化的课表条目。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | — | — |
| query | `include_stale` | boolean | 否 | default=false | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'semester': semester, 'items_count': len(items), 'items': [{'id': it.id, 'semester': it.semester, 'course_code': it.course_code, 'course_name': it.course_name, 'teacher': it.teacher, 'teachers': it.teachers, 'location': it.location, 'campus': it.campus, 'building': it.building, 'classroom': it.classroom, 'weekday': it.weekday, 'start_section': it.start_section, 'end_section': it.end_section, 'start_time': it.start_time, 'end_time': it.end_time, 'weeks': it.weeks, 'week_text': it.week_text, 'credit': it.credit, 'course_nature': it.course_nature, 'course_category': it.course_category, 'course_type': it.course_type, 'teaching_class': it.teaching_class, 'class_name': it.class_name, 'college': it.college, 'department': it.department, 'assessment_method': it.assessment_method, 'exam_type': it.exam_type, 'total_hours': it.total_hours, 'theory_hours': it.theory_hours, 'practice_hours': it.practice_hours, 'language': it.language, 'note': it.note, 'semester_id': it.semester_id, 'extra_info': it.extra_info, 'is_stale': it.is_stale, 'last_seen_at': it.last_seen_at} for it in items]}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/grade/semesters`

用途：列出已同步成绩的所有学期。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_grade_semesters`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出已同步成绩的所有学期。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<string> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/grade/items`

用途：读取已持久化的成绩条目。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_grade_items`。

Web 封装：`getGradeItems`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

读取已持久化的成绩条目。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | — | — |
| query | `include_stale` | boolean | 否 | default=false | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'semester': semester, 'items_count': len(items), 'items': [{'id': it.id, 'semester': it.semester, 'course_code': it.course_code, 'course_name': it.course_name, 'credit': it.credit, 'score': it.score, 'grade_point': it.grade_point, 'category': it.category, 'status': it.status, 'is_stale': it.is_stale, 'last_seen_at': it.last_seen_at} for it in items]}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/exam/semesters`

用途：列出已同步考试安排的所有学期。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_exam_semesters`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出已同步考试安排的所有学期。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<string> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/exam/items`

用途：读取已持久化的考试安排，补考通过 exam_type 区分。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_exam_items`。

Web 封装：`getExamItems`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

读取已持久化的考试安排，补考通过 exam_type 区分。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | — | — |
| query | `include_stale` | boolean | 否 | default=false | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'semester': semester, 'items_count': len(items), 'items': [{'id': item.id, 'semester': item.semester, 'course_code': item.course_code, 'course_name': item.course_name, 'exam_type': item.exam_type, 'location': item.location, 'seat': item.seat, 'starts_at': item.starts_at, 'ends_at': item.ends_at, 'notes': item.notes, 'is_stale': item.is_stale, 'last_seen_at': item.last_seen_at} for item in items]}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/systems/{university_id}`

用途：列出学校的所有教务系统（1:N）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_systems`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出学校的所有教务系统（1:N）。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `university_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[EduSystemOut](schemas.md#schema-edusystemout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/connections`

用途：创建教务连接（返回 connection_id + 初始状态）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`create_connection`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

创建教务连接（返回 connection_id + 初始状态）。

不默认上传账号密码。后续通过 /connections/{id}/continue 推进状态。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduConnectionCreate](schemas.md#schema-educonnectioncreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `edu_system_id` | string | 是 | minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "edu_system_id": "<edu_system_id>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduConnectionOut](schemas.md#schema-educonnectionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string | 是 | — | — |
| `university_id` | string | 是 | — | — |
| `state` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `portal_url` | string / null | 否 | — | — |
| `allowed_origins` | array<string> | 否 | maxItems=8 | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | 'EDU_SYSTEM_NOT_FOUND' | 服务器内部错误 |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `GET /api/v1/edu/connections/{connection_id}`

用途：读取教务连接。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`get_connection`。

Web 封装：`getEduConnection`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `connection_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduConnectionOut](schemas.md#schema-educonnectionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string | 是 | — | — |
| `university_id` | string | 是 | — | — |
| `state` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `portal_url` | string / null | 否 | — | — |
| `allowed_origins` | array<string> | 否 | maxItems=8 | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | 'EDU_CONNECTION_NOT_FOUND' | 服务器内部错误 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `POST /api/v1/edu/connections/{connection_id}/pre-login`

用途：预登录：获取验证码图片等预登录数据。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`pre_login`。

Web 封装：`preLoginEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

预登录：获取验证码图片等预登录数据。

流程：
1. 后端 GET 教务登录页，提取验证码图片
2. 返回 pre_login_token + captcha_image_base64
3. 客户端展示验证码图片，用户输入验证码
4. 客户端调用 /continue(action=SUBMIT_WITH_CAPTCHA, pre_login_token, username, password, captcha)

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `connection_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduPreLoginResult](schemas.md#schema-edupreloginresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `pre_login_token` | string | 是 | — | — |
| `verification_session_id` | string / null | 否 | — | — |
| `captcha_required` | boolean | 是 | — | — |
| `captcha_type` | string | 否 | default="none" | — |
| `challenge_type` | string | 否 | default="none" | — |
| `captcha_image_base64` | string / null | 否 | — | — |
| `captcha_mime_type` | string / null | 否 | — | — |
| `captcha_image_url` | string / null | 否 | — | — |
| `expires_at` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | 'EDU_CONNECTION_NOT_FOUND' | 服务器内部错误 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `POST /api/v1/edu/connections/{connection_id}/continue`

用途：推进连接状态。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`continue_connection`。

Web 封装：`continueEduConnection`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

推进连接状态。

支持两种路径：
- server_credentials: username + password
- client_webview: action=CLIENT_WEBVIEW_COMPLETE + cookies + current_url + user_agent
- action=POLL: 轮询当前状态
- action=CANCEL: 取消连接
- action=SUBMIT_WITH_CAPTCHA: 携带验证码提交登录（需配合 pre_login_token + captcha）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `connection_id` | string | 是 | — | — |

请求体：`application/json`，必填；[EduConnectionContinue](schemas.md#schema-educonnectioncontinue)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string / null | 否 | — | 登录用户名 |
| `password` | string (password) / null | 否 | string约束: format="password"; writeOnly=true | 登录密码，仅请求使用 |
| `captcha` | string / null | 否 | — | — |
| `sms_code` | string / null | 否 | — | — |
| `mfa_code` | string / null | 否 | — | — |
| `action` | string / null | 否 | — | — |
| `cookies` | map<string, string> / null | 否 | object约束: additionalProperties={"type": "string"} | — |
| `cookie_jar` | array<[EduCookie](schemas.md#schema-educookie)> | 否 | maxItems=64 | — |
| `current_url` | string / null | 否 | — | — |
| `user_agent` | string / null | 否 | string约束: maxLength=512 | — |
| `pre_login_token` | string / null | 否 | — | — |
| `verification_session_id` | string / null | 否 | — | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduConnectionOut](schemas.md#schema-educonnectionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string | 是 | — | — |
| `university_id` | string | 是 | — | — |
| `state` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `portal_url` | string / null | 否 | — | — |
| `allowed_origins` | array<string> | 否 | maxItems=8 | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | 'EDU_CONNECTION_NOT_FOUND' | 服务器内部错误 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `POST /api/v1/edu/connections/from-url`

用途：从教务系统 URL 创建连接（便捷流程）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`create_connection_from_url`。

Web 封装：`createEduConnection`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

从教务系统 URL 创建连接（便捷流程）。

1. probe URL 检测 provider
2. ensure_default_system 创建/复用 edu_system
3. create_connection
返回 connection（初始 state=idle），客户端再调 /continue 推进。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduConnectionFromUrlRequest](schemas.md#schema-educonnectionfromurlrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `portal_url` | string | 是 | minLength=1; maxLength=512 | — |
| `university_id` | string / null | 否 | — | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "portal_url": "<portal_url>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduConnectionOut](schemas.md#schema-educonnectionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string | 是 | — | — |
| `university_id` | string | 是 | — | — |
| `state` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `portal_url` | string / null | 否 | — | — |
| `allowed_origins` | array<string> | 否 | maxItems=8 | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `POST /api/v1/edu/discovery/probe`

用途：探测教务系统 URL（不需要 university_id）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`discovery_probe`。

Web 封装：`probeEduPortal`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

探测教务系统 URL（不需要 university_id）。

只检测 provider/可达性/建议登录模式，不持久化任何数据。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduProbeRequest](schemas.md#schema-eduproberequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `portal_url` | string | 是 | minLength=1; maxLength=512 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "portal_url": "<portal_url>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduProbeResult](schemas.md#schema-eduproberesult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `portal_url` | string | 是 | — | — |
| `provider` | string | 否 | default="unknown" | — |
| `provider_confidence` | number | 否 | default=0.0 | — |
| `reachable` | boolean | 否 | default=false | — |
| `http_status` | integer / null | 否 | — | — |
| `final_url` | string / null | 否 | — | — |
| `title` | string / null | 否 | — | 标题 |
| `is_edu_page` | boolean | 否 | default=false | — |
| `suggested_login_mode` | string | 否 | default="backend_http" | — |
| `challenge_type` | string | 否 | default="none" | — |
| `evidence` | array<object> | 否 | — | — |
| `error` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/discovery/submit-url`

用途：用户手动提交教务系统 URL。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`discovery_submit_url`。

Web 封装：当前无封装；按本节后端契约调用。

用户手动提交教务系统 URL。

检测 Provider → 尝试 HTTP 连接 → 保存为 USER_SUBMITTED 候选。
不自动升级 VERIFIED，仅标 CANDIDATE（或 VERIFIED_LIVE 若检测到强信号）。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduDiscoverySubmitUrlRequest](schemas.md#schema-edudiscoverysubmiturlrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string | 是 | — | — |
| `candidate_url` | string | 是 | minLength=1; maxLength=512 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "university_id": "<university_id>",
  "candidate_url": "<candidate_url>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduDiscoverySubmitUrlResult](schemas.md#schema-edudiscoverysubmiturlresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `school_code` | string / null | 否 | — | 学校代码 |
| `school_name` | string / null | 否 | — | — |
| `candidate_url` | string | 是 | — | — |
| `provider` | string | 否 | default="UNKNOWN" | — |
| `provider_confidence` | number | 否 | default=0.0 | — |
| `reachable` | boolean | 否 | default=false | — |
| `http_status` | integer / null | 否 | — | — |
| `final_url` | string / null | 否 | — | — |
| `title` | string / null | 否 | — | 标题 |
| `is_edu_page` | boolean | 否 | default=false | — |
| `evidence` | array<object> | 否 | — | — |
| `verification_status` | string | 否 | default="CANDIDATE" | — |
| `saved` | boolean | 否 | default=false | — |
| `error` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。


## 学校 HTTP 请求安全边界

学校 URL 在首次请求及每个重定向处校验。建立 TCP 连接时再次解析并校验全部 DNS 地址，实际连接固定为此次校验通过的 IP；保留原域名的 HTTP Host、TLS SNI 和证书检查，不能通过二次 DNS 解析切换到私网。任一 DNS 地址为 loopback、链路本地、保留地址或默认禁止的私网地址时拒绝连接；解析无有效地址以网络错误处理。已建立的连接池按原 Origin 复用，备用合法 IP 使用同一有界连接超时预算。学校客户端不使用进程的 HTTP(S) 代理变量。

现有仅非生产环境的 `EDU_ALLOW_INSECURE_SSL` 开关仍按原契约控制 TLS 兼容回退，不放松 IP 检查。Web、Android、HarmonyOS、微信小程序请求格式不变，无需端侧适配此连接层修复。

课程资料同步同时扫描独立“资料”页和章节资源；资料文件夹最多递归3层，收集最多300项。一个来源失败时保留另一个来源已取得的资源并标记 partial，不能把部分同步当作完整覆盖。安全的 coursedata/downloadData 链接即使没有 remote_object_id 也可通过本人课程文件代理下载，仍遵循资源域名、归属、缓存一致性与大小限制。
