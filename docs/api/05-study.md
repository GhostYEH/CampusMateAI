# 专注学习、签到与专注 AI

> 对照日期：2026-09-30。本模块共 31 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/study/goals/daily` | 读取每日学习目标 |
| PUT | `/api/v1/study/goals/daily` | 更新每日学习目标 |
| POST | `/api/v1/study/checkins` | 创建签到 |
| GET | `/api/v1/study/checkins` | 列出签到 |
| POST | `/api/v1/study/sessions` | 创建学习会话。开始时间为服务端时间,不接受客户端传入 |
| GET | `/api/v1/study/sessions` | 列出当前用户的会话(按开始时间倒序) |
| GET | `/api/v1/study/sessions/active` | 获取当前未结束会话(active 或 paused) |
| GET | `/api/v1/study/sessions/{session_id}` | 获取会话详情(含休息记录) |
| POST | `/api/v1/study/sessions/{session_id}/pause` | 暂停会话(开启一条休息记录) |
| POST | `/api/v1/study/sessions/{session_id}/resume` | 恢复会话(关闭最近一条休息记录,累加 pause_seconds) |
| POST | `/api/v1/study/sessions/{session_id}/finish` | 结束会话 |
| PATCH | `/api/v1/study/sessions/{session_id}` | 部分更新会话 |
| POST | `/api/v1/study/task-breakdown` | 任务拆解 |
| POST | `/api/v1/focus/ai/ask` | 回答用户主动语音转写后的文本；不接收音频、视觉或会话上下文 |
| POST | `/api/v1/focus/realtime-voice/sessions` | 创建会话 |
| DELETE | `/api/v1/focus/realtime-voice/sessions/{session_id}` | 停止会话 |
| GET | `/api/v1/study/rooms/identity` | 读取自习室身份（UID 与显示名） |
| GET | `/api/v1/study/rooms/students/{uid}` | 校验可邀请的同学 |
| GET | `/api/v1/study/rooms/` | 列出我加入的活动自习室 |
| GET | `/api/v1/study/rooms/invitations` | 列出待接受的自习室邀请 |
| POST | `/api/v1/study/rooms/` | 创建自习室 |
| GET | `/api/v1/study/rooms/{room_id}` | 读取自习室详情（成员/在线状态/计时器） |
| POST | `/api/v1/study/rooms/{room_id}/invitations` | 邀请同学加入自习室 |
| POST | `/api/v1/study/rooms/invitations/{room_id}/accept` | 接受自习室邀请 |
| POST | `/api/v1/study/rooms/invitations/{room_id}/decline` | 拒绝自习室邀请 |
| PATCH | `/api/v1/study/rooms/{room_id}/state` | 更新本人学习状态 |
| POST | `/api/v1/study/rooms/{room_id}/heartbeat` | 上报在线心跳 |
| POST | `/api/v1/study/rooms/{room_id}/timer` | 操作共享计时器（仅发起人） |
| GET | `/api/v1/study/rooms/{room_id}/messages` | 读取房内交流记录 |
| POST | `/api/v1/study/rooms/{room_id}/messages` | 发送房内消息 |
| POST | `/api/v1/study/rooms/{room_id}/leave` | 离开自习室 |

## 接口契约

### `GET /api/v1/study/goals/daily`

用途：读取每日学习目标。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`get_daily_goal`。

Web 封装：`getDailyStudyGoal`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudyGoalOut](schemas.md#schema-studygoalout) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `target_minutes` | integer | 是 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `PUT /api/v1/study/goals/daily`

用途：更新每日学习目标。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`update_daily_goal`。

Web 封装：`updateDailyStudyGoal`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[StudyGoalUpdate](schemas.md#schema-studygoalupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `target_minutes` | integer | 是 | minimum=15.0; maximum=480.0 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "target_minutes": 15.0
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudyGoalOut](schemas.md#schema-studygoalout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `target_minutes` | integer | 是 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/study/checkins`

用途：创建签到。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`create_checkin`。

Web 封装：`createStudyCheckin`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

运行时成功状态：本日首次签到为 **201**（created=true），重复签到为 **200**（created=false），结构相同。不能只接受 201。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[StudyCheckinCreate](schemas.md#schema-studycheckincreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `scene` | enum ["rain", "snow", "cloud"] | 否 | default="rain" | — |
| `mood` | string / null | 否 | string约束: maxLength=100 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [StudyCheckinResponse](schemas.md#schema-studycheckinresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |
| 200 | application/json | [StudyCheckinResponse](schemas.md#schema-studycheckinresponse) |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `checkin` | [StudyCheckinOut](schemas.md#schema-studycheckinout) | 是 | — | — |
| `created` | boolean | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/study/checkins`

用途：列出签到。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`list_checkins`。

Web 封装：`getStudyCheckins`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudyCheckinSummary](schemas.md#schema-studycheckinsummary) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[StudyCheckinOut](schemas.md#schema-studycheckinout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `streak` | integer | 是 | — | — |
| `longest_streak` | integer | 是 | — | — |
| `week_count` | integer | 是 | — | — |
| `today_checked` | boolean | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/study/sessions`

用途：创建学习会话。开始时间为服务端时间,不接受客户端传入。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`create_session`。

Web 封装：`startStudySession`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

创建学习会话。开始时间为服务端时间,不接受客户端传入。

若用户已存在未结束会话(active 或 paused),仍允许新建 — 由前端提示用户。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[StudySessionCreate](schemas.md#schema-studysessioncreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | enum ["focus", "short_break", "long_break"] | 否 | default="focus" | — |
| `experience_mode` | enum ["QUIET", "AI_COMPANION", "SMART_GUARD"] | 否 | default="QUIET" | — |
| `planned_duration_seconds` | integer / null | 否 | integer约束: minimum=300.0; maximum=14400.0 | — |
| `goal` | string / null | 否 | string约束: maxLength=500 | 本次学习目标(自由文本) |
| `related_task_id` | string / null | 否 | string约束: maxLength=128 | 关联的个人待办 ID(PersonalTask ID,需属于当前用户且未软删除) |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [StudySessionOut](schemas.md#schema-studysessionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `mode` | string | 是 | — | — |
| `experience_mode` | enum ["QUIET", "AI_COMPANION", "SMART_GUARD"] | 否 | default="QUIET" | — |
| `goal` | string / null | 否 | — | — |
| `related_task_id` | string / null | 否 | — | — |
| `started_at` | string | 是 | — | — |
| `paused_at` | string / null | 否 | — | — |
| `ended_at` | string / null | 否 | — | — |
| `planned_duration_seconds` | integer | 否 | default=0 | — |
| `duration_seconds` | integer | 否 | default=0 | — |
| `pause_seconds` | integer | 否 | default=0 | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `self_report` | string / null | 否 | — | — |
| `self_report_tags` | array<string> | 否 | — | — |
| `expression_signal` | any / null | 否 | — | — |
| `behavior_summary` | [StudyBehaviorSummary](schemas.md#schema-studybehaviorsummary) / null | 否 | — | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `breaks` | array<[StudyBreakOut](schemas.md#schema-studybreakout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | VALIDATION_FAILED | 'goal 不能为空白字符串' |

### `GET /api/v1/study/sessions`

用途：列出当前用户的会话(按开始时间倒序)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`list_sessions`。

Web 封装：`getStudySessions`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

列出当前用户的会话(按开始时间倒序)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `status` | string / null | 否 | string约束: pattern="^(active\|paused\|completed)$" | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[StudySessionOut](schemas.md#schema-studysessionout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/study/sessions/active`

用途：获取当前未结束会话(active 或 paused)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`get_active_session`。

Web 封装：`getActiveStudySession`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

获取当前未结束会话(active 或 paused)。

应用重启后调用此接口恢复未结束会话。若无则返回 null。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudySessionOut](schemas.md#schema-studysessionout) / null |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/study/sessions/{session_id}`

用途：获取会话详情(含休息记录)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`get_session`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

获取会话详情(含休息记录)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `session_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudySessionOut](schemas.md#schema-studysessionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `mode` | string | 是 | — | — |
| `experience_mode` | enum ["QUIET", "AI_COMPANION", "SMART_GUARD"] | 否 | default="QUIET" | — |
| `goal` | string / null | 否 | — | — |
| `related_task_id` | string / null | 否 | — | — |
| `started_at` | string | 是 | — | — |
| `paused_at` | string / null | 否 | — | — |
| `ended_at` | string / null | 否 | — | — |
| `planned_duration_seconds` | integer | 否 | default=0 | — |
| `duration_seconds` | integer | 否 | default=0 | — |
| `pause_seconds` | integer | 否 | default=0 | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `self_report` | string / null | 否 | — | — |
| `self_report_tags` | array<string> | 否 | — | — |
| `expression_signal` | any / null | 否 | — | — |
| `behavior_summary` | [StudyBehaviorSummary](schemas.md#schema-studybehaviorsummary) / null | 否 | — | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `breaks` | array<[StudyBreakOut](schemas.md#schema-studybreakout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | STUDY_SESSION_NOT_FOUND | 学习会话不存在。 |

### `POST /api/v1/study/sessions/{session_id}/pause`

用途：暂停会话(开启一条休息记录)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`pause_session`。

Web 封装：`pauseStudySession`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

暂停会话(开启一条休息记录)。

Query 参数:
    reason: 休息原因(可选,最长 200 字)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `session_id` | string | 是 | — | — |
| query | `reason` | string / null | 否 | string约束: maxLength=200 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudySessionOut](schemas.md#schema-studysessionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `mode` | string | 是 | — | — |
| `experience_mode` | enum ["QUIET", "AI_COMPANION", "SMART_GUARD"] | 否 | default="QUIET" | — |
| `goal` | string / null | 否 | — | — |
| `related_task_id` | string / null | 否 | — | — |
| `started_at` | string | 是 | — | — |
| `paused_at` | string / null | 否 | — | — |
| `ended_at` | string / null | 否 | — | — |
| `planned_duration_seconds` | integer | 否 | default=0 | — |
| `duration_seconds` | integer | 否 | default=0 | — |
| `pause_seconds` | integer | 否 | default=0 | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `self_report` | string / null | 否 | — | — |
| `self_report_tags` | array<string> | 否 | — | — |
| `expression_signal` | any / null | 否 | — | — |
| `behavior_summary` | [StudyBehaviorSummary](schemas.md#schema-studybehaviorsummary) / null | 否 | — | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `breaks` | array<[StudyBreakOut](schemas.md#schema-studybreakout)> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/study/sessions/{session_id}/resume`

用途：恢复会话(关闭最近一条休息记录,累加 pause_seconds)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`resume_session`。

Web 封装：`resumeStudySession`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

恢复会话(关闭最近一条休息记录,累加 pause_seconds)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `session_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudySessionOut](schemas.md#schema-studysessionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `mode` | string | 是 | — | — |
| `experience_mode` | enum ["QUIET", "AI_COMPANION", "SMART_GUARD"] | 否 | default="QUIET" | — |
| `goal` | string / null | 否 | — | — |
| `related_task_id` | string / null | 否 | — | — |
| `started_at` | string | 是 | — | — |
| `paused_at` | string / null | 否 | — | — |
| `ended_at` | string / null | 否 | — | — |
| `planned_duration_seconds` | integer | 否 | default=0 | — |
| `duration_seconds` | integer | 否 | default=0 | — |
| `pause_seconds` | integer | 否 | default=0 | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `self_report` | string / null | 否 | — | — |
| `self_report_tags` | array<string> | 否 | — | — |
| `expression_signal` | any / null | 否 | — | — |
| `behavior_summary` | [StudyBehaviorSummary](schemas.md#schema-studybehaviorsummary) / null | 否 | — | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `breaks` | array<[StudyBreakOut](schemas.md#schema-studybreakout)> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/study/sessions/{session_id}/finish`

用途：结束会话。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`finish_session`。

Web 封装：`finishStudySession`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

结束会话。

self_report 必须由用户主动输入,后端不会根据 expression_signal 替用户填写。
服务端计算 duration_seconds = (ended_at - started_at) - pause_seconds,
不接受客户端传入的结束时间。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `session_id` | string | 是 | — | — |

请求体：`application/json`，必填；[StudySessionFinish](schemas.md#schema-studysessionfinish)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `self_report` | string / null | 否 | string约束: maxLength=2000 | — |
| `self_report_tags` | array<string> / null | 否 | array约束: maxItems=20 | — |
| `behavior_summary` | [StudyBehaviorSummary](schemas.md#schema-studybehaviorsummary) / null | 否 | — | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudySessionOut](schemas.md#schema-studysessionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `mode` | string | 是 | — | — |
| `experience_mode` | enum ["QUIET", "AI_COMPANION", "SMART_GUARD"] | 否 | default="QUIET" | — |
| `goal` | string / null | 否 | — | — |
| `related_task_id` | string / null | 否 | — | — |
| `started_at` | string | 是 | — | — |
| `paused_at` | string / null | 否 | — | — |
| `ended_at` | string / null | 否 | — | — |
| `planned_duration_seconds` | integer | 否 | default=0 | — |
| `duration_seconds` | integer | 否 | default=0 | — |
| `pause_seconds` | integer | 否 | default=0 | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `self_report` | string / null | 否 | — | — |
| `self_report_tags` | array<string> | 否 | — | — |
| `expression_signal` | any / null | 否 | — | — |
| `behavior_summary` | [StudyBehaviorSummary](schemas.md#schema-studybehaviorsummary) / null | 否 | — | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `breaks` | array<[StudyBreakOut](schemas.md#schema-studybreakout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | VALIDATION_FAILED | 'self_report 不能为空白字符串(若填写需有内容)' |

### `PATCH /api/v1/study/sessions/{session_id}`

用途：部分更新会话。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`update_session`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

部分更新会话。

- goal / related_task_id: 仅未结束会话可改(repo 层校验)。
- self_report / self_report_tags / expression_signal: 任意状态可改。
- 未传字段(None)不更新。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `session_id` | string | 是 | — | — |

请求体：`application/json`，必填；[StudySessionUpdate](schemas.md#schema-studysessionupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal` | string / null | 否 | string约束: maxLength=500 | — |
| `related_task_id` | string / null | 否 | string约束: maxLength=128 | 关联的个人待办 ID(需属于当前用户且未软删除) |
| `self_report` | string / null | 否 | string约束: maxLength=2000 | 用户主动填写的文字感受 |
| `self_report_tags` | array<string> / null | 否 | array约束: maxItems=20 | — |
| `expression_signal` | any / null | 否 | — | 预留 CNN 表情信号(本轮不实现 CNN,仅透传存储) |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudySessionOut](schemas.md#schema-studysessionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `mode` | string | 是 | — | — |
| `experience_mode` | enum ["QUIET", "AI_COMPANION", "SMART_GUARD"] | 否 | default="QUIET" | — |
| `goal` | string / null | 否 | — | — |
| `related_task_id` | string / null | 否 | — | — |
| `started_at` | string | 是 | — | — |
| `paused_at` | string / null | 否 | — | — |
| `ended_at` | string / null | 否 | — | — |
| `planned_duration_seconds` | integer | 否 | default=0 | — |
| `duration_seconds` | integer | 否 | default=0 | — |
| `pause_seconds` | integer | 否 | default=0 | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `self_report` | string / null | 否 | — | — |
| `self_report_tags` | array<string> | 否 | — | — |
| `expression_signal` | any / null | 否 | — | — |
| `behavior_summary` | [StudyBehaviorSummary](schemas.md#schema-studybehaviorsummary) / null | 否 | — | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `breaks` | array<[StudyBreakOut](schemas.md#schema-studybreakout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | VALIDATION_FAILED | 'goal 不能为空白字符串' |
| 422 | VALIDATION_FAILED | 'self_report 不能为空白字符串' |

### `POST /api/v1/study/task-breakdown`

用途：任务拆解。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/study.py](../../backend/app/api/routes/study.py)，`task_breakdown`。

Web 封装：`breakdownStudyTask`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

任务拆解。

输入 task_id(个人待办 PersonalTask ID,必须是当前用户所有且未软删除;
不接受教师 Assignment ID) 或自由文本 goal,可同时提供。

输出结构化步骤,mode 标注 llm | rule_fallback。响应的 goal 只返回展示用目标,
不包含任务说明、通知原文等内部生成上下文。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[TaskBreakdownRequest](schemas.md#schema-taskbreakdownrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | string / null | 否 | string约束: maxLength=128 | — |
| `goal` | string / null | 否 | string约束: maxLength=500 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [TaskBreakdownResponse](schemas.md#schema-taskbreakdownresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | enum ["llm", "rule_fallback"] | 是 | — | llm=模型生成成功; rule_fallback=规则降级 |
| `steps` | array<[TaskBreakdownStep](schemas.md#schema-taskbreakdownstep)> | 是 | — | — |
| `goal` | string | 是 | — | 展示用目标文本(display_goal) |
| `related_task_id` | string / null | 否 | — | — |
| `related_task_title` | string / null | 否 | — | — |
| `warnings` | array<string> | 否 | — | 警告列表；成功也需展示降级或缺失数据 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/focus/ai/ask`

用途：回答用户主动语音转写后的文本；不接收音频、视觉或会话上下文。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/focus_ai.py](../../backend/app/api/routes/focus_ai.py)，`ask_focus_ai`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

回答用户主动语音转写后的文本；不接收音频、视觉或会话上下文。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[FocusAiAskRequest](schemas.md#schema-focusaiaskrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | minLength=1; maxLength=800 | 文本 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "text": "<text>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FocusAiAskResponse](schemas.md#schema-focusaiaskresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `answer` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| status.HTTP_503_SERVICE_UNAVAILABLE | HTTPException | 'AI 学习陪伴服务暂不可用，请稍后重试。' |
| status.HTTP_504_GATEWAY_TIMEOUT | HTTPException | 'AI 回答超时，请稍后重试。' |
| status.HTTP_502_BAD_GATEWAY | HTTPException | 'AI 暂时无法回答，请稍后重试。' |

### `POST /api/v1/focus/realtime-voice/sessions`

用途：创建会话。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/focus_realtime_voice.py](../../backend/app/api/routes/focus_realtime_voice.py)，`create_session`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [FocusRealtimeVoiceSessionResponse](schemas.md#schema-focusrealtimevoicesessionresponse) |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `websocket_path` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | HTTPException | '实时语音服务尚未配置，请稍后再试。' |

### `DELETE /api/v1/focus/realtime-voice/sessions/{session_id}`

用途：删除本人会话的内存登记，阻止后续 WebSocket 握手。已连接的中继不会被本接口主动断开；客户端须先停止采集与播放，并发送 `{"type":"stop"}` 或关闭 WebSocket，见[实时语音协议](response-contracts.md#实时语音-websocket)。中继退出也会清理登记，因此随后 DELETE 可能返回 404，应按已结束处理。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/focus_realtime_voice.py](../../backend/app/api/routes/focus_realtime_voice.py)，`stop_session`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `session_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FocusRealtimeVoiceStopResponse](schemas.md#schema-focusrealtimevoicestopresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `stopped` | boolean | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HTTPException | '实时语音会话不存在。' |

完成专注会话时，有正数 planned_duration_seconds 的会话按计划时长封顶；暂停时间先扣除，防止后台恢复或延迟结束放大实际专注时长。未设置正数计划时长的会话仍按实际有效时间记录。

## 多人在线自习室（互相监督）

一组同学进入同一「自习室」，通过 HTTP 轮询互相看到各自在专注/休息/离开、共用一个由发起人控制的番茄钟、并可发送房内文字鼓励。**不含音视频与摄像头互看**：监督以“状态可见 + 同步计时 + 文字鼓励”的形式进行，隐私友好且各端都能稳定接入。

- 与 [共同课堂(learning-space)](14-magicclass.md#classroom-rtc) 是两套独立能力：自习室没有课件、归档与 RTC。
- 轮询模型：客户端每约 15 秒调用 `heartbeat` 保活，并定期读取 `GET /rooms/{room_id}` 获取全量成员与计时器；每次读取返回 `timer.server_time`，客户端据此外推本地倒计时，避免依赖设备本地时钟。超过 45 秒无心跳的成员对他人显示为离开（`online=false`、`study_state=away`）。
- 成员上限 8，每位发起人最多 20 个活动自习室；发起人离开即结束整个自习室。
- 无 SSE / WebSocket；消息用 `after` 游标增量读取，每页 ≤100 条。

客户端适配：Web（webreact 专注页「和同学一起自习」）、Android（专注页「多人自习室」，路由 `study_rooms`）、iOS（专注自习页「多人自习室」）已实现本协议；HarmonyOS、微信小程序尚未适配。均为纯 HTTP 轮询实现，不依赖 RTC 或独立学习空间。

### `GET /api/v1/study/rooms/identity`

用途：读取当前登录账号的 UID 与显示名，供邀请同学时核对。

鉴权：Bearer access token；仅要求登录。实现：[backend/app/api/routes/study_rooms.py](../../backend/app/api/routes/study_rooms.py)，`identity`。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

响应：`200 application/json`，顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `uid` | string | 是 | — | 账号唯一 ID |
| `name` | string | 是 | — | 显示名，缺省回退用户名 |

异常：401 `UNAUTHORIZED`。

### `GET /api/v1/study/rooms/students/{uid}`

用途：按 UID 校验邀请对象是否存在且启用。

鉴权：Bearer access token。实现：`student`。

参数：path `uid`（string，必填）；无 query / header 参数。

响应：`200`，`{ "uid": string, "name": string }`。异常：404 `STUDY_ROOM_ERROR`（未找到该 UID 对应的同学）；422 `STUDY_ROOM_ERROR`（邀请自己）。

### `GET /api/v1/study/rooms/`

用途：列出本人已加入且活动的自习室，按创建时间降序，最多 100 条。

鉴权：Bearer access token。实现：`rooms`。

参数：无。

响应：`200`，`items` 数组元素字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 自习室 ID |
| `title` | string | 是 | — | 标题 |
| `host_uid` | string | 是 | — | 发起人 UID |
| `created_at` | string | 是 | — | 创建时间(ISO8601) |
| `member_count` | integer | 是 | — | 已接受成员数 |

异常：401 `UNAUTHORIZED`。

### `GET /api/v1/study/rooms/invitations`

用途：列出本人待接受的自习室邀请，仅含活动自习室。

鉴权：Bearer access token。实现：`invitations`。

参数：无。

响应：`200`，`items` 数组元素字段：`room_id` string、`title` string、`host_uid` string、`host_name` string、`updated_at` string。异常：401 `UNAUTHORIZED`。

### `POST /api/v1/study/rooms/`

用途：创建自习室，发起人自动成为 accepted 成员。

鉴权：Bearer access token。实现：`create`。

请求体：`application/json`，必填；[StudyRoomCreateIn](schemas.md#schema-studyroomcreatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=200 | 去除首尾空白后不能为空 |
| `focus_minutes` | integer | 否 | default=25; minimum=1; maximum=180 | 专注时长(分钟) |
| `break_minutes` | integer | 否 | default=5; minimum=1; maximum=60 | 休息时长(分钟) |

请求结构示例：

```json
{"title": "期末冲刺自习室", "focus_minutes": 25, "break_minutes": 5}
```

响应：`201 application/json`（自习室详情，结构见 `GET /api/v1/study/rooms/{room_id}` 顶层字段）；`409` `STUDY_ROOM_ERROR`（活动自习室达 20 个上限）；`422` 校验错误。

### `GET /api/v1/study/rooms/{room_id}`

用途：accepted 成员读取自习室详情、成员在线状态与同步计时器。

鉴权：Bearer access token + 当前 accepted 成员关系。实现：`room`。

参数：path `room_id`（string，必填）。

响应：`200`，顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 自习室 ID |
| `title` | string | 是 | — | 标题 |
| `host_uid` | string | 是 | — | 发起人 UID |
| `active` | integer | 是 | — | 1=活动 |
| `created_at` | string | 是 | — | 创建时间 |
| `focus_minutes` | integer | 是 | — | 当前专注时长 |
| `break_minutes` | integer | 是 | — | 当前休息时长 |
| `timer` | object | 是 | — | 见下 `timer` 字段 |
| `members` | array<object> | 是 | — | 见下 `members` 元素字段 |

`timer` 字段：`phase` enum["idle","focus","break"]、`running` boolean、`paused` boolean、`remaining_seconds` integer、`server_time` string。

`members` 元素字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `uid` | string | 是 | — | 成员 UID |
| `name` | string | 是 | — | 显示名 |
| `status` | enum["pending","accepted"] | 是 | — | 成员状态 |
| `study_state` | enum["focus","break","away","idle"] | 是 | — | 学习状态；离线成员强制为 away |
| `online` | boolean | 是 | — | 45 秒内是否有心跳 |
| `last_seen_at` | string / null | 否 | — | 最近心跳时间 |
| `status_message` | string | 是 | maxLength=140 | 状态语 |

异常：404 `STUDY_ROOM_ERROR`（不存在/pending/非成员/已离开）；410 `STUDY_ROOM_ERROR`（自习室已结束但仍为 accepted）。

### `POST /api/v1/study/rooms/{room_id}/invitations`

用途：发起人按 UID 邀请同学加入。

鉴权：Bearer access token + 仅发起人。实现：`invite`。

请求体：`application/json`，必填；[StudyRoomInvitationIn](schemas.md#schema-studyroominvitationin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `uid` | string | 是 | minLength=1; maxLength=128 | 去除首尾空白 |

请求结构示例：

```json
{"uid": "usr_guest_example"}
```

响应：`200`，`{ "uid": string, "status": "pending" }`（重复邀请 pending/accepted 返回原状态）。异常：403 `STUDY_ROOM_ERROR`（非发起人）；404（自习室不存在/目标不存在）；409（成员已达 8 人上限）；422（邀请自己）。

### `POST /api/v1/study/rooms/invitations/{room_id}/accept`

用途：本人接受有效邀请，返回自习室详情。

鉴权：Bearer access token。实现：`accept`。

参数：path `room_id`（string，必填）；无请求体。

响应：`200`，自习室详情（结构同 `GET /api/v1/study/rooms/{room_id}`）。异常：404（邀请已失效/非待接受）。

### `POST /api/v1/study/rooms/invitations/{room_id}/decline`

用途：本人拒绝待接受邀请。

鉴权：Bearer access token。实现：`decline`。

参数：path `room_id`（string，必填）；无请求体。

响应：`204`，无响应体。异常：404（邀请已失效）；409（已加入，须改用 leave）。

### `PATCH /api/v1/study/rooms/{room_id}/state`

用途：accepted 成员上报本人学习状态与可选状态语。

鉴权：Bearer access token + accepted 成员。实现：`set_state`。

请求体：`application/json`，必填；[StudyRoomStateIn](schemas.md#schema-studyroomstatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `study_state` | string | 是 | minLength=1; maxLength=16 | 取值 focus/break/away/idle |
| `status_message` | string / null | 否 | string约束: maxLength=140 | 省略则保留原状态语 |

请求结构示例：

```json
{"study_state": "focus", "status_message": "冲刺数学"}
```

响应：`204`，无响应体。异常：404；410；422（状态非法）。

### `POST /api/v1/study/rooms/{room_id}/heartbeat`

用途：accepted 成员上报在线心跳。

鉴权：Bearer access token + accepted 成员。实现：`heartbeat`。

参数：path `room_id`（string，必填）；无请求体。

响应：`200`，`{ "last_seen_at": string, "presence_ttl_seconds": 45 }`。异常：404；410。

### `POST /api/v1/study/rooms/{room_id}/timer`

用途：发起人操作共享番茄钟。

鉴权：Bearer access token + 仅发起人。实现：`timer`。

请求体：`application/json`，必填；[StudyRoomTimerIn](schemas.md#schema-studyroomtimerin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `action` | string | 是 | minLength=1; maxLength=16 | start_focus/start_break/pause/resume/reset |
| `focus_minutes` | integer / null | 否 | integer约束: minimum=1; maximum=180 | 省略则沿用当前值 |
| `break_minutes` | integer / null | 否 | integer约束: minimum=1; maximum=60 | 省略则沿用当前值 |

请求结构示例：

```json
{"action": "start_focus"}
```

响应：`200`，更新后的自习室详情（结构同 `GET /api/v1/study/rooms/{room_id}`，含最新 `timer`）。异常：403（非发起人）；404；410；409（pause/resume 状态不符）；422（未知 action 或时长越界）。

### `GET /api/v1/study/rooms/{room_id}/messages`

用途：accepted 成员增量读取房内消息。

鉴权：Bearer access token + accepted 成员。实现：`messages`。

参数：path `room_id`（必填）；query `after`（integer，默认 0，≥0），仅返回 id > after，按 id 升序，每次 ≤100 条。

响应：`200`，`items` 元素字段：`id` integer、`uid` string、`name` string、`content` string、`created_at` string。异常：404；410。

### `POST /api/v1/study/rooms/{room_id}/messages`

用途：accepted 成员发送文字鼓励。

鉴权：Bearer access token + accepted 成员。实现：`send`。

请求体：`application/json`，必填；[StudyRoomMessageIn](schemas.md#schema-studyroommessagein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | minLength=1; maxLength=2000 | 去除首尾空白后不能为空 |
| `client_id` | string | 是 | minLength=1; maxLength=128 | 幂等去重键 |

请求结构示例：

```json
{"content": "一起加油", "client_id": "msg_example"}
```

响应：`201`，`{ "id": integer, "content": string, "created_at": string }`。异常：404；410；409（同一 client_id 用于不同正文）；422。

### `POST /api/v1/study/rooms/{room_id}/leave`

用途：accepted 成员离开；发起人离开会结束整个自习室。

鉴权：Bearer access token + accepted 成员。实现：`leave`。

参数：path `room_id`（必填）；无请求体。

响应：`204`，无响应体。异常：404；410。
