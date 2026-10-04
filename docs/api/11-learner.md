# 学习状态、预测、模拟、目标与自适应计划

> 对照日期：2026-09-30。本模块共 36 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

> 2026-10-03 补充：状态历史支持 `projection_kind`，学业快照修复分页与元信息，计划与模拟修复预测接线、只读性和缓存。六层完成情况、实际局限与联调顺序见[六层世界模型后端接入](../world-model-backend.md)。

> 接口闭环补充：计划条目的 `execution_task_id` 返回执行创建的真实待办 ID，原 `task_id` 保留生成时的任务关联。任务完成、专注关联与反馈的完整 HTTP 顺序见[前端完整调用顺序](../world-model-backend.md#前端完整调用顺序)。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 学习计划生成的并发重放

`POST /api/v1/learning-plans/generate` 在同一用户、同一 `idempotency_key` 并发生成时，写事务内再次检查输入摘要。相同输入返回同一份完整计划，包含已有条目、证据和 `execution_task_id`，不会重复建立替代关系；不同输入仍返回 409 `LEARNING_PLAN_IDEMPOTENCY_CONFLICT`。请求路径和成功响应字段不变。

Web、Android、HarmonyOS、微信小程序继续按既有幂等键及错误码接入；本次验证后端并发回归和 Web 调用对照，移动端原生构建未验证。

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/student-goals` | 创建目标 |
| GET | `/api/v1/student-goals` | 列出目标 |
| GET | `/api/v1/student-goals/{goal_id}` | 读取目标 |
| PATCH | `/api/v1/student-goals/{goal_id}` | 更新目标 |
| POST | `/api/v1/student-goals/{goal_id}/progress` | 添加进度 |
| POST | `/api/v1/student-goals/{goal_id}/archive` | 归档目标 |
| GET | `/api/v1/learner-state/runs` | 列出运行 |
| GET | `/api/v1/learner-state/changes` | 列出状态变化 |
| GET | `/api/v1/learner-state/snapshots` | 列出状态快照 |
| GET | `/api/v1/learner-state/snapshots/{snapshot_id}/evidence` | 列出快照证据 |
| GET | `/api/v1/learner-state/academic` | 获取 ACADEMIC 投影快照：教务事实安全投影到学生状态世界模型 |
| GET | `/api/v1/learner-state/forecasts` | 获取校园生活与目标执行风险预测 |
| POST | `/api/v1/learner-state/simulations` | 反事实方案模拟 — 只读地比较校园行动方案的影响 |
| POST | `/api/v1/learning-plans/generate` | 生成学习计划 |
| GET | `/api/v1/learning-plans` | 列出学习计划 |
| GET | `/api/v1/learning-plans/{plan_id}` | 读取学习计划 |
| POST | `/api/v1/learning-plans/{plan_id}/decision` | 决定学习计划 |
| POST | `/api/v1/learning-plans/{plan_id}/execute` | 执行学习计划 |
| POST | `/api/v1/learning-plans/{plan_id}/undo` | 撤回执行学习计划 |
| POST | `/api/v1/learning-plans/{plan_id}/replan` | 重新规划学习计划 |
| POST | `/api/v1/learning-plans/{plan_id}/feedback` | 记录反馈学习计划 |
| GET | `/api/v1/learning-plans/{plan_id}/evaluation` | 评估学习计划 |
| GET | `/api/v1/learning-plans/{plan_id}/summary` | 阶段总结 + 候选模型只读金丝雀注解 |
| GET | `/api/v1/adaptive-interventions` | 列出自适应干预 |
| GET | `/api/v1/adaptive-interventions/{intervention_id}` | 读取自适应干预 |
| GET | `/api/v1/adaptive-interventions/{intervention_id}/outcome` | 读取自适应干预效果评估 |
| POST | `/api/v1/learner-state/corrections` | 创建纠正记录 |
| GET | `/api/v1/learner-state/corrections` | 列出纠正记录 |
| POST | `/api/v1/learner-state/corrections/{correction_id}/revoke` | 撤销纠正记录 |
| GET | `/api/v1/learner-state/data-controls` | 列出数据来源控制 |
| PUT | `/api/v1/learner-state/data-controls/{source_key}` | 更新数据来源控制 |
| POST | `/api/v1/learner-state/delete-request` | request数据删除 |
| GET | `/api/v1/learner-state/delete-status` | 读取数据删除状态 |
| GET | `/api/v1/learner-state/data-summary` | 读取数据概况 |
| GET | `/api/v1/learner-state/model-transparency` | 读取模型透明度信息 |
| GET | `/api/v1/learner-state/canary-gate/{capability_name}` | 检查模型只读门禁 |

## 接口契约

### `POST /api/v1/student-goals`

用途：创建目标。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/student_goals.py](../../backend/app/api/routes/student_goals.py)，`create_goal`。

Web 封装：`createStudentGoal`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[StudentGoalCreate](schemas.md#schema-studentgoalcreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=200 | 名称 |
| `category` | enum ["academic", "research", "competition", "certificate", "job_search", "internship", "campus_affair", "health_habit", "personal_growth"] | 是 | — | — |
| `target_date` | string / null | 否 | string约束: maxLength=32 | — |
| `idempotency_key` | string / null | 否 | string约束: maxLength=128 | — |
| `initial_progress_percent` | number | 否 | default=0.0; minimum=0.0; maximum=100.0 | — |
| `milestone_count` | integer | 否 | default=0; minimum=0.0; maximum=100.0 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "name": "<name>",
  "category": "academic"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudentGoalCreateResult](schemas.md#schema-studentgoalcreateresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal` | [StudentGoalOut](schemas.md#schema-studentgoalout) | 是 | — | — |
| `created` | boolean | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/student-goals`

用途：列出目标。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/student_goals.py](../../backend/app/api/routes/student_goals.py)，`list_goals`。

Web 封装：`getStudentGoals`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `status` | string / null | 否 | string约束: pattern="^(active\|archived)$" | — |
| query | `category` | string / null | 否 | — | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=200 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudentGoalPage](schemas.md#schema-studentgoalpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[StudentGoalOut](schemas.md#schema-studentgoalout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/student-goals/{goal_id}`

用途：读取目标。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/student_goals.py](../../backend/app/api/routes/student_goals.py)，`get_goal`。

Web 封装：当前无封装；按本节后端契约调用。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `goal_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudentGoalOut](schemas.md#schema-studentgoalout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal_id` | string | 是 | — | — |
| `user_id` | string | 是 | — | 所属用户标识 |
| `name` | string | 是 | — | 名称 |
| `category` | enum ["academic", "research", "competition", "certificate", "job_search", "internship", "campus_affair", "health_habit", "personal_growth"] | 是 | — | — |
| `status` | enum ["active", "archived"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `target_date` | string / null | 否 | — | — |
| `archived_at` | string / null | 否 | — | — |
| `progress_percent` | number | 是 | — | — |
| `milestone_count` | integer | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | STUDENT_GOAL_NOT_FOUND | 学生目标不存在。 |

### `PATCH /api/v1/student-goals/{goal_id}`

用途：更新目标。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/student_goals.py](../../backend/app/api/routes/student_goals.py)，`update_goal`。

Web 封装：`updateStudentGoal`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `goal_id` | string | 是 | — | — |

请求体：`application/json`，必填；[StudentGoalUpdate](schemas.md#schema-studentgoalupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=200 | 名称 |
| `category` | enum ["academic", "research", "competition", "certificate", "job_search", "internship", "campus_affair", "health_habit", "personal_growth"] / null | 否 | — | — |
| `target_date` | string / null | 否 | string约束: maxLength=32 | — |
| `milestone_count` | integer / null | 否 | integer约束: minimum=0.0; maximum=100.0 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudentGoalOut](schemas.md#schema-studentgoalout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal_id` | string | 是 | — | — |
| `user_id` | string | 是 | — | 所属用户标识 |
| `name` | string | 是 | — | 名称 |
| `category` | enum ["academic", "research", "competition", "certificate", "job_search", "internship", "campus_affair", "health_habit", "personal_growth"] | 是 | — | — |
| `status` | enum ["active", "archived"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `target_date` | string / null | 否 | — | — |
| `archived_at` | string / null | 否 | — | — |
| `progress_percent` | number | 是 | — | — |
| `milestone_count` | integer | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | STUDENT_GOAL_NOT_FOUND | 学生目标不存在。 |

### `POST /api/v1/student-goals/{goal_id}/progress`

用途：添加进度。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/student_goals.py](../../backend/app/api/routes/student_goals.py)，`add_progress`。

Web 封装：`recordGoalProgress`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `goal_id` | string | 是 | — | — |

请求体：`application/json`，必填；[StudentGoalProgressCreate](schemas.md#schema-studentgoalprogresscreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `progress_percent` | number | 是 | minimum=0.0; maximum=100.0 | — |
| `milestone_reached` | string / null | 否 | string约束: maxLength=128 | — |
| `idempotency_key` | string / null | 否 | string约束: maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "progress_percent": 0.0
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudentGoalProgressResult](schemas.md#schema-studentgoalprogressresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal` | [StudentGoalOut](schemas.md#schema-studentgoalout) | 是 | — | — |
| `progress` | [StudentGoalProgressOut](schemas.md#schema-studentgoalprogressout) | 是 | — | 进度；对象或数值范围按字段类型 |
| `created` | boolean | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | STUDENT_GOAL_NOT_FOUND | 学生目标不存在。 |
| 409 | STUDENT_GOAL_CONFLICT | 学生目标当前状态不允许该操作。 |

### `POST /api/v1/student-goals/{goal_id}/archive`

用途：归档目标。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/student_goals.py](../../backend/app/api/routes/student_goals.py)，`archive_goal`。

Web 封装：`archiveStudentGoal`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `goal_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudentGoalOut](schemas.md#schema-studentgoalout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal_id` | string | 是 | — | — |
| `user_id` | string | 是 | — | 所属用户标识 |
| `name` | string | 是 | — | 名称 |
| `category` | enum ["academic", "research", "competition", "certificate", "job_search", "internship", "campus_affair", "health_habit", "personal_growth"] | 是 | — | — |
| `status` | enum ["active", "archived"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `target_date` | string / null | 否 | — | — |
| `archived_at` | string / null | 否 | — | — |
| `progress_percent` | number | 是 | — | — |
| `milestone_count` | integer | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | STUDENT_GOAL_NOT_FOUND | 学生目标不存在。 |
| 409 | STUDENT_GOAL_CONFLICT | 学生目标当前状态不允许该操作。 |

### `GET /api/v1/learner-state/runs`

用途：列出运行。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/learner_state.py](../../backend/app/api/routes/learner_state.py)，`list_runs`。

可选 query `projection_kind`：默认 CORE，允许 CORE/ACADEMIC/WORLD；只列出该类型运行，查询时会更新当前投影。现有 Web 封装尚未透传该参数。

Web 封装：`getLearnerStateRuns`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `projection_kind` | string | 否 | default="CORE"; pattern="^(CORE\|ACADEMIC\|WORLD)$" | 选择运行历史所属投影 |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearnerStateRunPage](schemas.md#schema-learnerstaterunpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearnerStateRunOut](schemas.md#schema-learnerstaterunout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | minimum=0.0 | 总数 |
| `page` | integer | 是 | minimum=1.0 | 当前页，从 1 开始 |
| `page_size` | integer | 是 | minimum=1.0 | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/changes`

用途：列出状态变化。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/learner_state.py](../../backend/app/api/routes/learner_state.py)，`list_changes`。

可选 query `projection_kind`：默认 CORE，允许 CORE/ACADEMIC/WORLD。未传 `to_run_id` 时选择该类型的当前投影；显式传入时以运行的实际类型为准。比较的两个运行必须属于本人且同一投影类型。现有 Web 封装尚未透传新增参数。

Web 封装：`getLearnerStateChanges`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `from_run_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| query | `to_run_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| query | `projection_kind` | string | 否 | default="CORE"; pattern="^(CORE\|ACADEMIC\|WORLD)$" | 未传 to_run_id 时选择当前投影 |
| query | `scope_type` | string / null | 否 | string约束: pattern="^(USER\|COURSE\|TASK\|SOURCE\|KNOWLEDGE_COMPONENT\|SEMESTER)$" | — |
| query | `state_type` | string / null | 否 | string约束: pattern="^(?:observed_learning_activity\|task_workload\|deadline_exposure\|course_participation\|data_source_health\|academic_course_load\|grade_observation\|knowledge_mastery_observation\|credit_progress\|exam_exposure\|schedule_load\|goal_state\|workload_pressure\|schedule_conflict\|academic_progress\|focus_rhythm\|goal_progress\|execution_consistency\|growth_momentum\|preference_profile)$" | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=100 | — |
| query | `include_unchanged` | boolean | 否 | default=false | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearnerStateChangePage](schemas.md#schema-learnerstatechangepage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `from_run_id` | string / null | 是 | — | — |
| `to_run_id` | string | 是 | — | — |
| `estimator_changed` | boolean | 是 | — | — |
| `changes` | array<[LearnerStateChangeOut](schemas.md#schema-learnerstatechangeout)> | 是 | — | — |
| `total` | integer | 是 | minimum=0.0 | 总数 |
| `page` | integer | 是 | minimum=1.0 | 当前页，从 1 开始 |
| `page_size` | integer | 是 | minimum=1.0 | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 资源不存在。 |

### `GET /api/v1/learner-state/snapshots`

用途：列出状态快照。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/learner_state.py](../../backend/app/api/routes/learner_state.py)，`list_snapshots`。

Web 封装：`getLearnerStateSnapshots`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `scope_type` | string / null | 否 | string约束: pattern="^(USER\|COURSE\|TASK\|SOURCE\|KNOWLEDGE_COMPONENT\|SEMESTER)$" | — |
| query | `state_type` | string / null | 否 | string约束: pattern="^(?:observed_learning_activity\|task_workload\|deadline_exposure\|course_participation\|data_source_health\|academic_course_load\|grade_observation\|knowledge_mastery_observation\|credit_progress\|exam_exposure\|schedule_load\|goal_state\|workload_pressure\|schedule_conflict\|academic_progress\|focus_rhythm\|goal_progress\|execution_consistency\|growth_momentum\|preference_profile)$" | — |
| query | `course_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| query | `projection_kind` | string | 否 | default="CORE"; pattern="^(CORE\|ACADEMIC\|WORLD)$" | — |
| query | `projection_scope` | string | 否 | default="__user__"; pattern="^__user__$" | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearnerStateSnapshotPage](schemas.md#schema-learnerstatesnapshotpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearnerStateSnapshotOut](schemas.md#schema-learnerstatesnapshotout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/snapshots/{snapshot_id}/evidence`

用途：列出快照证据。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/learner_state.py](../../backend/app/api/routes/learner_state.py)，`list_snapshot_evidence`。

Web 封装：`getSnapshotEvidence`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `snapshot_id` | string | 是 | — | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearnerStateEvidencePage](schemas.md#schema-learnerstateevidencepage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearnerStateEvidenceOut](schemas.md#schema-learnerstateevidenceout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 资源不存在。 |

### `GET /api/v1/learner-state/academic`

用途：获取 ACADEMIC 投影快照：教务事实安全投影到学生状态世界模型。

分页使用完整总数，`has_more = page * page_size < total`；条目包含 `estimator_version/input_digest/as_of/warning_codes/evidence_count`，与通用 snapshots 接口一致。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/learner_state.py](../../backend/app/api/routes/learner_state.py)，`get_academic_state`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

获取 ACADEMIC 投影快照：教务事实安全投影到学生状态世界模型。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearnerStateSnapshotPage](schemas.md#schema-learnerstatesnapshotpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearnerStateSnapshotOut](schemas.md#schema-learnerstatesnapshotout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/forecasts`

用途：获取校园生活与目标执行风险预测。

`course_id` 对工作负载/日程冲突预测只纳入明确归属该课程的记录。教务 course_code 尚未映射到本站 course_id，未知归属排除并降级；不据此承诺真实课表冲突已完整实现。详情见[预测边界](../world-model-backend.md#预测)。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/forecasts.py](../../backend/app/api/routes/forecasts.py)，`list_forecasts`。

Web 封装：`getForecasts`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

获取校园生活与目标执行风险预测。

确定性、版本化、可重复的基线估计器。
数据不足时返回 UNAVAILABLE，不捏造概率。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `forecast_type` | string / null | 否 | string约束: pattern="^(DEADLINE_COMPLETION_RISK\|UPCOMING_WORKLOAD\|SCHEDULE_CONFLICT_RISK\|GOAL_PROGRESS_OUTLOOK\|ROUTINE_CONTINUITY)$" | — |
| query | `horizon_days` | integer | 否 | default=7; minimum=1; maximum=30 | — |
| query | `goal_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| query | `course_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ForecastPage](schemas.md#schema-forecastpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[ForecastOut](schemas.md#schema-forecastout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | minimum=0.0 | 总数 |
| `page` | integer | 是 | minimum=1.0 | 当前页，从 1 开始 |
| `page_size` | integer | 是 | minimum=1.0 | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/learner-state/simulations`

模拟不写投影、快照、证据或任务。无幂等键时事实变化会刷新结果；显式幂等键用于当前进程内限期重放，接受计划的缓存也受计划状态和有效期约束。历史 baseline_run_id 只校验归属并锚定摘要，事实仍使用当前数据。具体干预语义与局限见[模拟接入](../world-model-backend.md#反事实模拟)。

用途：反事实方案模拟 — 只读地比较校园行动方案的影响。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/simulations.py](../../backend/app/api/routes/simulations.py)，`create_simulation`。

Web 封装：`createSimulation`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

反事实方案模拟 — 只读地比较校园行动方案的影响。

不创建任务、不修改目标、不执行计划、不暂停真实数据源。
结果是"方案估计,不是因果保证"。
跨用户 baseline_run_id 返回 404。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[SimulationRequest](schemas.md#schema-simulationrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `baseline_run_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| `intervention` | [AllocateFocusMinutesIntervention](schemas.md#schema-allocatefocusminutesintervention) / [RescheduleTaskIntervention](schemas.md#schema-rescheduletaskintervention) / [AcceptPlanIntervention](schemas.md#schema-acceptplanintervention) / [ReduceDailyLoadIntervention](schemas.md#schema-reducedailyloadintervention) / [PauseDataSourceIntervention](schemas.md#schema-pausedatasourceintervention) / [AdjustGoalDeadlineIntervention](schemas.md#schema-adjustgoaldeadlineintervention) | 是 | — | — |
| `horizon_days` | integer | 否 | default=7; minimum=1.0; maximum=30.0 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "intervention": {
    "focus_minutes": 0.0
  }
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [SimulationResponse](schemas.md#schema-simulationresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `simulation_id` | string | 是 | — | — |
| `baseline_digest` | string | 是 | — | — |
| `intervention` | [AllocateFocusMinutesIntervention](schemas.md#schema-allocatefocusminutesintervention) / [RescheduleTaskIntervention](schemas.md#schema-rescheduletaskintervention) / [AcceptPlanIntervention](schemas.md#schema-acceptplanintervention) / [ReduceDailyLoadIntervention](schemas.md#schema-reducedailyloadintervention) / [PauseDataSourceIntervention](schemas.md#schema-pausedatasourceintervention) / [AdjustGoalDeadlineIntervention](schemas.md#schema-adjustgoaldeadlineintervention) | 是 | — | — |
| `changed_forecasts` | array<[ChangedForecastSummary](schemas.md#schema-changedforecastsummary)> | 否 | maxItems=32 | — |
| `changed_state_estimates` | array<[ChangedStateEstimateSummary](schemas.md#schema-changedstateestimatesummary)> | 否 | maxItems=64 | — |
| `unchanged_states` | array<[UnchangedStateSummary](schemas.md#schema-unchangedstatesummary)> | 否 | maxItems=128 | — |
| `assumptions` | array<enum ["intervention_applied_in_memory_only", "baseline_state_unchanged", "linear_local_response", "no_second_order_effects", "plan_acceptance_assumed", "source_pause_assumed"]> | 否 | maxItems=16 | — |
| `limitations` | array<enum ["baseline_estimator_only", "no_causal_claim", "correlation_not_causation", "counterfactual_estimate_not_cause", "single_user_scope", "no_psychological_inference", "no_dropout_prediction", "no_employment_prediction", "no_personality_prediction", "synthetic_calibration_only", "not_measured_against_real_outcomes", "intervention_not_executed", "missing_baseline_data", "plan_not_simulatable", "plan_expired", "no_movable_tasks", "simulation_no_change"]> | 否 | maxItems=16 | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `data_quality` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `estimator_version` | string | 是 | — | — |
| `expires_at` | string (date-time) | 是 | format="date-time" | — |
| `causal_claim` | const false | 否 | default=false | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 资源不存在。 |

### `POST /api/v1/learning-plans/generate`

用途：生成学习计划。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`generate_learning_plan`。

Web 封装：`generateLearningPlan`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| header | `Idempotency-Key` | string / null | 否 | string约束: maxLength=128 | — |

请求体：`application/json`，必填；[LearningPlanGenerateRequest](schemas.md#schema-learningplangeneraterequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `available_minutes` | integer | 是 | minimum=1.0; maximum=1440.0 | — |
| `goal_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| `course_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | 关联课程标识 |
| `window_start` | string / null | 否 | string约束: maxLength=64 | — |
| `window_end` | string / null | 否 | string约束: maxLength=64 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| `enhance_with_llm` | boolean | 否 | default=false | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "available_minutes": 1.0
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanOut](schemas.md#schema-learningplanout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `goal_id` | string / null | 否 | — | — |
| `planner_version` | string | 是 | — | — |
| `input_digest` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `as_of` | string | 是 | — | — |
| `valid_until` | string | 是 | — | — |
| `available_minutes` | integer | 是 | — | — |
| `allocated_minutes` | integer | 是 | — | — |
| `warning_codes` | array<string> | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `items` | array<[LearningPlanItemOut](schemas.md#schema-learningplanitemout)> | 是 | — | 列表条目 |
| `llm_summary` | string / null | 否 | — | — |
| `supersedes_plan_id` | string / null | 否 | — | — |
| `superseded_by_plan_id` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | VALIDATION_FAILED | str(exc) |

### `GET /api/v1/learning-plans`

用途：列出学习计划。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`list_learning_plans`。

Web 封装：`getLearningPlans`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanPage](schemas.md#schema-learningplanpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearningPlanOut](schemas.md#schema-learningplanout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learning-plans/{plan_id}`

用途：读取学习计划。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`get_learning_plan`。

Web 封装：`getLearningPlan`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `plan_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanOut](schemas.md#schema-learningplanout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `goal_id` | string / null | 否 | — | — |
| `planner_version` | string | 是 | — | — |
| `input_digest` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `as_of` | string | 是 | — | — |
| `valid_until` | string | 是 | — | — |
| `available_minutes` | integer | 是 | — | — |
| `allocated_minutes` | integer | 是 | — | — |
| `warning_codes` | array<string> | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `items` | array<[LearningPlanItemOut](schemas.md#schema-learningplanitemout)> | 是 | — | 列表条目 |
| `llm_summary` | string / null | 否 | — | — |
| `supersedes_plan_id` | string / null | 否 | — | — |
| `superseded_by_plan_id` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 依业务分支 | NotFoundError | — |

### `POST /api/v1/learning-plans/{plan_id}/decision`

用途：决定学习计划。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`decide_learning_plan`。

Web 封装：`decideLearningPlan`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `plan_id` | string | 是 | — | — |

请求体：`application/json`，必填；[LearningPlanDecisionRequest](schemas.md#schema-learningplandecisionrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `decision` | string | 是 | pattern="^(ACCEPT\|REJECT)$" | 用户决定，严格按枚举大小写 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "decision": "<decision>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanOut](schemas.md#schema-learningplanout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `goal_id` | string / null | 否 | — | — |
| `planner_version` | string | 是 | — | — |
| `input_digest` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `as_of` | string | 是 | — | — |
| `valid_until` | string | 是 | — | — |
| `available_minutes` | integer | 是 | — | — |
| `allocated_minutes` | integer | 是 | — | — |
| `warning_codes` | array<string> | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `items` | array<[LearningPlanItemOut](schemas.md#schema-learningplanitemout)> | 是 | — | 列表条目 |
| `llm_summary` | string / null | 否 | — | — |
| `supersedes_plan_id` | string / null | 否 | — | — |
| `superseded_by_plan_id` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/learning-plans/{plan_id}/execute`

用途：执行学习计划。

执行成功返回完整计划；创建待办的条目通过 `items[].execution_task_id` 返回新待办 ID。未创建时为 null，休息和反思条目不创建待办。原 `items[].task_id` 仍是生成时关联的原任务，执行不会自动完成它。

前端用新待办 ID 调用 `GET /api/v1/tasks/{task_id}`、`POST /api/v1/tasks/{task_id}/complete`，或传入 `POST /api/v1/study/sessions` 的 `related_task_id`。重复执行不重复创建；详情、列表及撤销响应保持相同 ID。撤销后应结合 `execution_status=UNDONE` 判断历史关联。真实完成数量读取 evaluation 的 `completed_plan_task_count`；EXECUTED 仅表示执行动作成功。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`execute_learning_plan`。

Web 封装：`executeLearningPlan`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `plan_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanOut](schemas.md#schema-learningplanout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `goal_id` | string / null | 否 | — | — |
| `planner_version` | string | 是 | — | — |
| `input_digest` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `as_of` | string | 是 | — | — |
| `valid_until` | string | 是 | — | — |
| `available_minutes` | integer | 是 | — | — |
| `allocated_minutes` | integer | 是 | — | — |
| `warning_codes` | array<string> | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `items` | array<[LearningPlanItemOut](schemas.md#schema-learningplanitemout)> | 是 | — | 列表条目 |
| `llm_summary` | string / null | 否 | — | — |
| `supersedes_plan_id` | string / null | 否 | — | — |
| `superseded_by_plan_id` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/learning-plans/{plan_id}/undo`

用途：撤回执行学习计划。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`undo_learning_plan`。

Web 封装：`undoLearningPlan`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `plan_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanOut](schemas.md#schema-learningplanout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `goal_id` | string / null | 否 | — | — |
| `planner_version` | string | 是 | — | — |
| `input_digest` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `as_of` | string | 是 | — | — |
| `valid_until` | string | 是 | — | — |
| `available_minutes` | integer | 是 | — | — |
| `allocated_minutes` | integer | 是 | — | — |
| `warning_codes` | array<string> | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `items` | array<[LearningPlanItemOut](schemas.md#schema-learningplanitemout)> | 是 | — | 列表条目 |
| `llm_summary` | string / null | 否 | — | — |
| `supersedes_plan_id` | string / null | 否 | — | — |
| `superseded_by_plan_id` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/learning-plans/{plan_id}/replan`

用途：重新规划学习计划。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`replan_learning_plan`。

Web 封装：`replanLearningPlan`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `plan_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | string约束: maxLength=128 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanOut](schemas.md#schema-learningplanout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `goal_id` | string / null | 否 | — | — |
| `planner_version` | string | 是 | — | — |
| `input_digest` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `as_of` | string | 是 | — | — |
| `valid_until` | string | 是 | — | — |
| `available_minutes` | integer | 是 | — | — |
| `allocated_minutes` | integer | 是 | — | — |
| `warning_codes` | array<string> | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `items` | array<[LearningPlanItemOut](schemas.md#schema-learningplanitemout)> | 是 | — | 列表条目 |
| `llm_summary` | string / null | 否 | — | — |
| `supersedes_plan_id` | string / null | 否 | — | — |
| `superseded_by_plan_id` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/learning-plans/{plan_id}/feedback`

用途：记录反馈学习计划。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`feedback_learning_plan`。

Web 封装：`submitPlanFeedback`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `plan_id` | string | 是 | — | — |

请求体：`application/json`，必填；[LearningPlanFeedbackRequest](schemas.md#schema-learningplanfeedbackrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `feedback` | string | 是 | pattern="^(HELPFUL\|NOT_HELPFUL\|TOO_LONG\|TOO_SHORT\|WRONG_PRIORITY\|ALREADY_DONE\|MISSING_CONTEXT)$" | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "feedback": "<feedback>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanFeedbackOut](schemas.md#schema-learningplanfeedbackout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `feedback` | string | 是 | — | — |
| `recorded` | boolean | 否 | default=true | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learning-plans/{plan_id}/evaluation`

用途：评估学习计划。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`evaluate_learning_plan`。

Web 封装：`getPlanEvaluation`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `plan_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanEvaluationOut](schemas.md#schema-learningplanevaluationout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `evaluation_status` | string | 是 | — | — |
| `baseline_as_of` | string | 是 | — | — |
| `evaluated_as_of` | string | 是 | — | — |
| `planned_item_count` | integer | 是 | — | — |
| `executed_item_count` | integer | 是 | — | — |
| `completed_plan_task_count` | integer | 是 | — | — |
| `evidence_coverage` | number | 是 | — | — |
| `warning_codes` | array<string> | 是 | — | — |
| `evaluator_version` | string | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learning-plans/{plan_id}/summary`

用途：阶段总结 + 候选模型只读金丝雀注解。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learning_plans.py](../../backend/app/api/routes/learning_plans.py)，`summarize_learning_plan`。

Web 封装：`getPlanSummary`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

阶段总结 + 候选模型只读金丝雀注解。

这是候选模型在生产链路上的**唯一业务接线点**：

- 门禁全过时，`candidate_annotation` 携带可识别、可降级、可追溯的只读结果；
- 其余任何情形（未启用/未配置/采样未命中/熔断/超时/非法输出/策略违规），
  注解降级为 `available=false` + 稳定 reason，并改走纯影子观测
  （`BackgroundTasks`，结果只落影子表），本响应继续返回确定性结果。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `plan_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [LearningPlanSummaryOut](schemas.md#schema-learningplansummaryout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `goal_id` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `stage` | string | 是 | — | — |
| `headline` | string | 是 | — | — |
| `completion_percent` | integer | 是 | minimum=0.0; maximum=100.0 | — |
| `planned_item_count` | integer | 是 | minimum=0.0 | — |
| `executed_item_count` | integer | 是 | minimum=0.0 | — |
| `planned_minutes` | integer | 是 | minimum=0.0 | — |
| `next_action` | string | 是 | — | — |
| `recommendations` | array<string> | 否 | — | — |
| `warning_codes` | array<string> | 否 | — | — |
| `generated_at` | string | 是 | — | — |
| `candidate_annotation` | [CandidateAnnotationOut](schemas.md#schema-candidateannotationout) / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/adaptive-interventions`

用途：列出自适应干预。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/adaptive_interventions.py](../../backend/app/api/routes/adaptive_interventions.py)，`list_adaptive_interventions`。

Web 封装：`getAdaptiveInterventions`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AdaptiveInterventionPage](schemas.md#schema-adaptiveinterventionpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[AdaptiveInterventionOut](schemas.md#schema-adaptiveinterventionout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/adaptive-interventions/{intervention_id}`

用途：读取自适应干预。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/adaptive_interventions.py](../../backend/app/api/routes/adaptive_interventions.py)，`get_adaptive_intervention`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `intervention_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AdaptiveInterventionOut](schemas.md#schema-adaptiveinterventionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `intervention_id` | string | 是 | — | — |
| `goal_id` | string | 是 | — | — |
| `plan_id` | string / null | 否 | — | — |
| `scope_type` | string | 否 | default="GOAL" | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `strategy_code` | string | 是 | — | — |
| `strategy_version` | string | 是 | — | — |
| `rationale_codes` | array<string> | 否 | — | — |
| `expected_outcomes` | array<string> | 否 | — | — |
| `baseline_core_run_id` | string / null | 否 | — | — |
| `baseline_academic_run_id` | string / null | 否 | — | — |
| `baseline_world_run_id` | string / null | 否 | — | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `problem_types` | array<string> | 否 | — | — |
| `data_quality` | string / null | 否 | — | — |
| `warning_codes` | array<string> | 否 | — | — |
| `observation_started_at` | string / null | 否 | — | — |
| `observation_due_at` | string / null | 否 | — | — |
| `evaluated_at` | string / null | 否 | — | — |
| `outcome_verdict` | string / null | 否 | — | — |
| `supersedes_intervention_id` | string / null | 否 | — | — |
| `superseded_by_intervention_id` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 资源不存在。 |

### `GET /api/v1/adaptive-interventions/{intervention_id}/outcome`

用途：读取自适应干预效果评估。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/adaptive_interventions.py](../../backend/app/api/routes/adaptive_interventions.py)，`get_adaptive_intervention_outcome`。

Web 封装：`getAdaptiveInterventionOutcome`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `intervention_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AdaptiveInterventionOutcomeOut](schemas.md#schema-adaptiveinterventionoutcomeout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `evaluation_id` | string | 是 | — | — |
| `intervention_id` | string | 是 | — | — |
| `goal_id` | string | 是 | — | — |
| `plan_id` | string / null | 否 | — | — |
| `scope_type` | string | 否 | default="GOAL" | — |
| `as_of` | string | 是 | — | — |
| `window_start` | string / null | 否 | — | — |
| `window_end` | string / null | 否 | — | — |
| `observation_status` | string | 是 | — | — |
| `execution_signal` | string | 是 | — | — |
| `adoption` | string | 是 | — | — |
| `plan_fidelity` | string | 是 | — | — |
| `verdict` | string | 是 | — | — |
| `observed_outcome` | string | 否 | default="INSUFFICIENT_EVIDENCE" | — |
| `causal_claim` | string | 否 | default="NOT_ESTIMATED" | — |
| `state_comparison` | object | 否 | — | — |
| `decision` | string / null | 否 | — | 用户决定，严格按枚举大小写 |
| `decision_reason_codes` | array<string> | 否 | — | — |
| `suggested_adjustments` | array<string> | 否 | — | — |
| `decision_confidence` | number / null | 否 | number约束: minimum=0.0; maximum=1.0 | — |
| `decision_status` | string / null | 否 | — | — |
| `lineage` | map<string, string / null> | 否 | additionalProperties={"anyOf": [{"type": "string"}, {"type": "null"}]} | — |
| `observation_due_at` | string / null | 否 | — | — |
| `outcome_checks` | array<map<string, string>> | 否 | — | — |
| `execution_signals` | map<string, number / integer / string / boolean / null> | 否 | additionalProperties={"anyOf": [{"type": "number"}, {"type": "integer"}, {"type": "string"}, {"type": "boolean"}, {"type": "null"}]} | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `data_quality` | string / null | 否 | — | — |
| `warning_codes` | array<string> | 否 | — | — |
| `evaluator_version` | string | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 资源不存在。 |

### `POST /api/v1/learner-state/corrections`

用途：创建纠正记录。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`create_correction`。

Web 封装：`createCorrection`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[CorrectionCreate](schemas.md#schema-correctioncreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `projection_kind` | enum ["CORE", "KNOWLEDGE"] | 是 | — | 投影类型 |
| `projection_scope` | string | 是 | minLength=1; maxLength=128 | 投影范围标识 |
| `scope_type` | enum ["USER", "COURSE", "TASK", "SOURCE", "KNOWLEDGE_COMPONENT"] | 是 | — | 快照 scope 类型 |
| `scope_id` | string | 是 | minLength=1; maxLength=128 | 快照 scope 标识 |
| `state_type` | enum ["observed_learning_activity", "task_workload", "deadline_exposure", "course_participation", "data_source_health", "academic_course_load", "grade_observation", "credit_progress", "exam_exposure", "schedule_load", "goal_state"] | 是 | — | 被纠正的状态类型 |
| `target_snapshot_id` | string | 是 | minLength=1; maxLength=128 | 目标快照 ID |
| `correction_type` | enum ["MARK_INACCURATE", "NOT_APPLICABLE", "SOURCE_OUTDATED", "ALREADY_RESOLVED", "REQUEST_RECOMPUTE"] | 是 | — | 纠正类型 |
| `reason_code` | enum ["TASK_ALREADY_COMPLETED", "DEADLINE_CHANGED", "COURSE_NO_LONGER_ACTIVE", "KNOWLEDGE_ESTIMATE_TOO_HIGH", "KNOWLEDGE_ESTIMATE_TOO_LOW", "EVIDENCE_NOT_RELEVANT", "SOURCE_DATA_STALE", "OTHER_CONTROLLED_REASON"] | 是 | — | 纠正原因码 |
| `idempotency_key` | string | 是 | minLength=1; maxLength=128 | 幂等键 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "projection_kind": "CORE",
  "projection_scope": "<projection_scope>",
  "scope_type": "USER",
  "scope_id": "<scope_id>",
  "state_type": "observed_learning_activity",
  "target_snapshot_id": "<target_snapshot_id>",
  "correction_type": "MARK_INACCURATE",
  "reason_code": "TASK_ALREADY_COMPLETED",
  "idempotency_key": "<idempotency_key>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [CorrectionOut](schemas.md#schema-correctionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `correction_id` | string | 是 | — | — |
| `projection_kind` | enum ["CORE", "KNOWLEDGE"] | 是 | — | — |
| `projection_scope` | string | 是 | — | — |
| `scope_type` | enum ["USER", "COURSE", "TASK", "SOURCE", "KNOWLEDGE_COMPONENT"] | 是 | — | — |
| `scope_id` | string | 是 | — | — |
| `state_type` | enum ["observed_learning_activity", "task_workload", "deadline_exposure", "course_participation", "data_source_health", "academic_course_load", "grade_observation", "credit_progress", "exam_exposure", "schedule_load", "goal_state"] | 是 | — | — |
| `target_snapshot_id` | string | 是 | — | — |
| `correction_type` | enum ["MARK_INACCURATE", "NOT_APPLICABLE", "SOURCE_OUTDATED", "ALREADY_RESOLVED", "REQUEST_RECOMPUTE"] | 是 | — | — |
| `reason_code` | enum ["TASK_ALREADY_COMPLETED", "DEADLINE_CHANGED", "COURSE_NO_LONGER_ACTIVE", "KNOWLEDGE_ESTIMATE_TOO_HIGH", "KNOWLEDGE_ESTIMATE_TOO_LOW", "EVIDENCE_NOT_RELEVANT", "SOURCE_DATA_STALE", "OTHER_CONTROLLED_REASON"] | 是 | — | — |
| `status` | enum ["ACTIVE", "REVOKED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `created_at` | string (date-time) | 是 | format="date-time" | 创建时间 |
| `revoked_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `correction_version` | integer | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/corrections`

用途：列出纠正记录。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`list_corrections`。

Web 封装：`getCorrections`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=100 | — |
| query | `status` | string / null | 否 | string约束: pattern="^(ACTIVE\|REVOKED)$" | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CorrectionPage](schemas.md#schema-correctionpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[CorrectionOut](schemas.md#schema-correctionout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/learner-state/corrections/{correction_id}/revoke`

用途：撤销纠正记录。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`revoke_correction`。

Web 封装：`revokeCorrection`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `correction_id` | string | 是 | — | — |

请求体：`application/json`，必填；[CorrectionRevokeRequest](schemas.md#schema-correctionrevokerequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string | 是 | minLength=1; maxLength=128 | 幂等键 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "idempotency_key": "<idempotency_key>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CorrectionOut](schemas.md#schema-correctionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `correction_id` | string | 是 | — | — |
| `projection_kind` | enum ["CORE", "KNOWLEDGE"] | 是 | — | — |
| `projection_scope` | string | 是 | — | — |
| `scope_type` | enum ["USER", "COURSE", "TASK", "SOURCE", "KNOWLEDGE_COMPONENT"] | 是 | — | — |
| `scope_id` | string | 是 | — | — |
| `state_type` | enum ["observed_learning_activity", "task_workload", "deadline_exposure", "course_participation", "data_source_health", "academic_course_load", "grade_observation", "credit_progress", "exam_exposure", "schedule_load", "goal_state"] | 是 | — | — |
| `target_snapshot_id` | string | 是 | — | — |
| `correction_type` | enum ["MARK_INACCURATE", "NOT_APPLICABLE", "SOURCE_OUTDATED", "ALREADY_RESOLVED", "REQUEST_RECOMPUTE"] | 是 | — | — |
| `reason_code` | enum ["TASK_ALREADY_COMPLETED", "DEADLINE_CHANGED", "COURSE_NO_LONGER_ACTIVE", "KNOWLEDGE_ESTIMATE_TOO_HIGH", "KNOWLEDGE_ESTIMATE_TOO_LOW", "EVIDENCE_NOT_RELEVANT", "SOURCE_DATA_STALE", "OTHER_CONTROLLED_REASON"] | 是 | — | — |
| `status` | enum ["ACTIVE", "REVOKED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `created_at` | string (date-time) | 是 | format="date-time" | 创建时间 |
| `revoked_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `correction_version` | integer | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/data-controls`

用途：列出数据来源控制。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`list_data_controls`。

Web 封装：`getDataControls`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DataSourceControlList](schemas.md#schema-datasourcecontrollist) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[DataSourceControlOut](schemas.md#schema-datasourcecontrolout)> | 是 | — | 列表条目 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `PUT /api/v1/learner-state/data-controls/{source_key}`

用途：更新数据来源控制。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`update_data_control`。

Web 封装：`updateDataControl`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `source_key` | string | 是 | — | — |

请求体：`application/json`，必填；[DataSourceControlUpdate](schemas.md#schema-datasourcecontrolupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | enum ["ENABLED", "PAUSED"] | 是 | — | 新状态 |
| `idempotency_key` | string | 是 | minLength=1; maxLength=128 | 幂等键 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "status": "ENABLED",
  "idempotency_key": "<idempotency_key>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DataSourceControlOut](schemas.md#schema-datasourcecontrolout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `source_key` | enum ["CORE_STUDY", "PERSONAL_TASK", "CHAOXING", "EDU", "MODEL_SHADOW", "PROACTIVE_SUGGESTIONS"] | 是 | — | — |
| `status` | enum ["ENABLED", "PAUSED", "DISCONNECTED", "DELETE_REQUESTED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `updated_at` | string (date-time) | 是 | format="date-time" | 最近更新时间 |
| `can_pause` | boolean | 否 | default=true | — |
| `can_resume` | boolean | 否 | default=true | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/learner-state/delete-request`

用途：request数据删除。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`request_deletion`。

Web 封装：`requestDeletion`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[DeleteRequestCreate](schemas.md#schema-deleterequestcreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `scope` | enum ["STATE_ONLY", "EVENTS_AND_STATE", "KNOWLEDGE_ONLY", "PLANS_ONLY", "MODEL_SHADOW_ONLY", "ALL_LEARNER_MODEL_DATA"] | 是 | — | 删除范围 |
| `idempotency_key` | string | 是 | minLength=1; maxLength=128 | 幂等键 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "scope": "STATE_ONLY",
  "idempotency_key": "<idempotency_key>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DeleteRequestOut](schemas.md#schema-deleterequestout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `request_id` | string | 是 | — | — |
| `scope` | enum ["STATE_ONLY", "EVENTS_AND_STATE", "KNOWLEDGE_ONLY", "PLANS_ONLY", "MODEL_SHADOW_ONLY", "ALL_LEARNER_MODEL_DATA"] | 是 | — | — |
| `status` | enum ["COMPLETED", "IN_PROGRESS", "FAILED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `before_counts` | [DeleteCountSummary](schemas.md#schema-deletecountsummary) | 是 | — | — |
| `after_counts` | [DeleteCountSummary](schemas.md#schema-deletecountsummary) | 是 | — | — |
| `created_at` | string (date-time) | 是 | format="date-time" | 创建时间 |
| `completed_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/delete-status`

用途：读取数据删除状态。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`get_delete_status`。

Web 封装：`getDeleteStatus`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DeleteStatusOut](schemas.md#schema-deletestatusout) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `latest` | [DeleteRequestOut](schemas.md#schema-deleterequestout) / null | 否 | — | — |
| `history` | array<[DeleteRequestOut](schemas.md#schema-deleterequestout)> | 否 | default=[] | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/data-summary`

用途：读取数据概况。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`get_data_summary`。

Web 封装：`getDataSummary`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DataSummaryOut](schemas.md#schema-datasummaryout) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `event_count` | integer | 是 | — | — |
| `snapshot_count` | integer | 是 | — | — |
| `correction_count` | integer | 是 | — | — |
| `learning_plan_count` | integer | 是 | — | — |
| `plan_feedback_count` | integer | 是 | — | — |
| `plan_evaluation_count` | integer | 是 | — | — |
| `shadow_run_count` | integer | 是 | — | — |
| `enabled_sources` | array<enum ["CORE_STUDY", "PERSONAL_TASK", "CHAOXING", "EDU", "MODEL_SHADOW", "PROACTIVE_SUGGESTIONS"]> | 是 | — | — |
| `paused_sources` | array<enum ["CORE_STUDY", "PERSONAL_TASK", "CHAOXING", "EDU", "MODEL_SHADOW", "PROACTIVE_SUGGESTIONS"]> | 是 | — | — |
| `oldest_recorded_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `newest_recorded_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `estimator_versions` | array<string> | 是 | — | — |
| `planner_versions` | array<string> | 是 | — | — |
| `evaluator_versions` | array<string> | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/model-transparency`

用途：读取模型透明度信息。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`get_model_transparency`。

Web 封装：`getModelTransparency`（[webreact/src/data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ModelTransparencyOut](schemas.md#schema-modeltransparencyout) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `capabilities` | array<[ModelCapabilityTransparencyOut](schemas.md#schema-modelcapabilitytransparencyout)> | 是 | — | — |
| `campusmate_lm_enabled` | boolean | 是 | — | — |
| `campusmate_lm_affects_production` | boolean | 否 | default=false | — |
| `shadow_results_modify_plans` | boolean | 否 | default=false | — |
| `read_only_canary_active` | boolean | 否 | default=false | — |
| `uses_real_model_inference` | boolean | 否 | default=false | — |
| `uses_fixed_prediction_file` | boolean | 否 | default=true | — |
| `real_inference_observed` | boolean | 否 | default=false | — |
| `last_real_inference_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `fixture_only` | boolean | 否 | default=false | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/learner-state/canary-gate/{capability_name}`

用途：检查模型只读门禁。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/learner_control.py](../../backend/app/api/routes/learner_control.py)，`check_canary_gate`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `capability_name` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
result
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。
