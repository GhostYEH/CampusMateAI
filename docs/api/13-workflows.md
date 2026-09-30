# 期末复习与课程研究

> 对照日期：2026-09-30。本模块共 18 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/final-review/campaigns` | 创建 campaign。只接受 server /student/exams 返回的 exam_id |
| GET | `/api/v1/final-review/campaigns` | 列出复习活动 |
| GET | `/api/v1/final-review/campaigns/{campaign_id}` | 读取复习活动 |
| POST | `/api/v1/final-review/campaigns/{campaign_id}/plans/generate` | 生成首版或新版计划。使用 reasoning_primary 路由 |
| GET | `/api/v1/final-review/campaigns/{campaign_id}/plan-versions` | 列出计划版本 |
| GET | `/api/v1/final-review/campaigns/{campaign_id}/plan-versions/{version}` | 读取计划版本 |
| POST | `/api/v1/final-review/campaigns/{campaign_id}/activate` | 激活指定版本 |
| GET | `/api/v1/final-review/campaigns/{campaign_id}/agendas/today` | 获取今日议程。若不存在则按 active version 生成 |
| POST | `/api/v1/final-review/daily-items/{item_id}/complete` | 完成 agenda item |
| POST | `/api/v1/final-review/campaigns/{campaign_id}/daily-checkins` | 每日签到/晚间反馈。记录完成情况和反馈作为 evidence |
| POST | `/api/v1/final-review/campaigns/{campaign_id}/adjustments/analyze` | Analyzer 分析证据,产生 adjustment proposal。不直接改 active plan |
| GET | `/api/v1/final-review/campaigns/{campaign_id}/adjustment-proposals` | 列出调整建议 |
| POST | `/api/v1/final-review/adjustment-proposals/{proposal_id}/decision` | 审批 adjustment proposal |
| POST | `/api/v1/course-research/runs` | 创建课程研究 Run 并同步执行 |
| GET | `/api/v1/course-research/runs` | 列出当前用户的课程研究 Run |
| GET | `/api/v1/course-research/runs/{run_id}` | 获取单个课程研究 Run |
| POST | `/api/v1/course-research/runs/{run_id}/cancel` | 取消课程研究 Run |
| GET | `/api/v1/course-research/runs/{run_id}/artifacts` | 列出 Run 的产物与来源 |

## 接口契约

### `POST /api/v1/final-review/campaigns`

用途：创建 campaign。只接受 server /student/exams 返回的 exam_id。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`create_campaign`。

Web 封装：`createCampaign`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）；`createFinalReviewCampaign`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

创建 campaign。只接受 server /student/exams 返回的 exam_id。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[FinalReviewCampaignIn](schemas.md#schema-finalreviewcampaignin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `exam_ids` | array<string> | 是 | minItems=1; maxItems=20 | — |
| `daily_capacity_minutes` | integer | 是 | minimum=15.0; maximum=600.0 | — |
| `preferred_periods` | array<string> | 否 | maxItems=10 | — |
| `rest_days` | array<string> | 否 | maxItems=7 | — |
| `intensity` | string | 否 | default="medium"; pattern="^(low\|medium\|high)$" | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "exam_ids": [
    "<exam_ids>"
  ],
  "daily_capacity_minutes": 15.0
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FinalReviewCampaignOut](schemas.md#schema-finalreviewcampaignout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `campaign_id` | string | 是 | — | — |
| `user_id` | string | 是 | — | 所属用户标识 |
| `exam_ids` | array<string> | 是 | — | — |
| `daily_capacity_minutes` | integer | 是 | — | — |
| `preferred_periods` | array<string> | 是 | — | — |
| `rest_days` | array<string> | 是 | — | — |
| `intensity` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `active_version` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | VALIDATION_FAILED | '至少需要一个 exam_id' |
| 422 | VALIDATION_FAILED | f'exam_id 不存在或不属于当前用户: {sorted(missing)}' |

### `GET /api/v1/final-review/campaigns`

用途：列出复习活动。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`list_campaigns`。

Web 封装：`listCampaigns`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）；`getFinalReviewCampaigns`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[FinalReviewCampaignOut](schemas.md#schema-finalreviewcampaignout)> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/final-review/campaigns/{campaign_id}`

用途：读取复习活动。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`get_campaign`。

Web 封装：`getFinalReviewCampaign`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FinalReviewCampaignOut](schemas.md#schema-finalreviewcampaignout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `campaign_id` | string | 是 | — | — |
| `user_id` | string | 是 | — | 所属用户标识 |
| `exam_ids` | array<string> | 是 | — | — |
| `daily_capacity_minutes` | integer | 是 | — | — |
| `preferred_periods` | array<string> | 是 | — | — |
| `rest_days` | array<string> | 是 | — | — |
| `intensity` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `active_version` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'campaign 不存在' |

### `POST /api/v1/final-review/campaigns/{campaign_id}/plans/generate`

用途：生成首版或新版计划。使用 reasoning_primary 路由。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`generate_plan`。

Web 封装：`generatePlan`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）；`generateFinalReviewPlan`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

生成首版或新版计划。使用 reasoning_primary 路由。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[PlanGenerateIn](schemas.md#schema-plangeneratein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_edits` | object / null | 否 | — | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PlanGenerateOut](schemas.md#schema-plangenerateout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | — | 运行标识 |
| `version` | integer | 是 | — | — |
| `plan` | object | 是 | — | — |
| `risk_level` | string | 是 | — | — |
| `requires_approval` | boolean | 是 | — | — |
| `approval_id` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'campaign 不存在' |
| 409 | 'AGENT_INVALID_STATE' | '幂等请求仍在处理中' |
| 409 | AGENT_IDEMPOTENCY_CONFLICT | 幂等键已用于不同的请求。 |

### `GET /api/v1/final-review/campaigns/{campaign_id}/plan-versions`

用途：列出计划版本。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`list_plan_versions`。

Web 封装：`getFinalReviewPlanVersions`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[PlanVersionOut](schemas.md#schema-planversionout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/final-review/campaigns/{campaign_id}/plan-versions/{version}`

用途：读取计划版本。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`get_plan_version`。

Web 封装：`getFinalReviewPlanVersion`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |
| path | `version` | integer | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PlanVersionOut](schemas.md#schema-planversionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `campaign_id` | string | 是 | — | — |
| `version` | integer | 是 | — | — |
| `plan` | object | 是 | — | — |
| `source_snapshot_id` | string / null | 否 | — | — |
| `model_provider` | string | 是 | — | — |
| `route_policy` | string | 是 | — | — |
| `risk_level` | string | 是 | — | — |
| `approval_id` | string / null | 否 | — | — |
| `supersedes_version` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'plan version 不存在' |

### `POST /api/v1/final-review/campaigns/{campaign_id}/activate`

用途：激活指定版本。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`activate_campaign`。

Web 封装：`activatePlan`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）；`activateFinalReviewCampaign`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

激活指定版本。

路由只创建命令:审批后的实际激活由 Handler 经 `ToolInvocationGateway` 执行,
最终状态由 Worker 原子写入,进程在中间崩溃也能从 checkpoint 恢复且只激活一次。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[ActivateIn](schemas.md#schema-activatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | integer | 是 | minimum=1.0 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "version": 1.0
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ActivateOut](schemas.md#schema-activateout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `campaign_id` | string | 是 | — | — |
| `active_version` | integer | 是 | — | — |
| `activated` | boolean | 是 | — | — |
| `status` | string | 否 | default="ACTIVE" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `run_id` | string / null | 否 | — | 运行标识 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'plan version 不存在' |
| 409 | AGENT_APPROVAL_REQUIRED | 需要用户确认后继续。 |
| 404 | NOT_FOUND | 'campaign 不存在' |

### `GET /api/v1/final-review/campaigns/{campaign_id}/agendas/today`

用途：获取今日议程。若不存在则按 active version 生成。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`get_today_agenda`。

Web 封装：`todayAgenda`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）；`getTodayAgenda`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

获取今日议程。若不存在则按 active version 生成。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DailyAgendaOut](schemas.md#schema-dailyagendaout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `agenda_id` | string | 是 | — | — |
| `campaign_id` | string | 是 | — | — |
| `plan_version` | integer | 是 | — | — |
| `agenda_date` | string | 是 | — | — |
| `total_minutes` | integer | 是 | — | — |
| `items` | array<[DailyItemOut](schemas.md#schema-dailyitemout)> | 是 | — | 列表条目 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'campaign 不存在' |
| 409 | 'AGENT_INVALID_STATE' | 'campaign 尚未激活' |

### `POST /api/v1/final-review/daily-items/{item_id}/complete`

用途：完成 agenda item。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`complete_item`。

Web 封装：`completeDailyItem`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）；`completeFinalReviewItem`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

完成 agenda item。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `item_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[CompleteItemIn](schemas.md#schema-completeitemin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `difficulty` | string / null | 否 | string约束: pattern="^(easy\|medium\|hard)$" | — |
| `feedback` | string / null | 否 | string约束: maxLength=500 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CompleteItemOut](schemas.md#schema-completeitemout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `item_id` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `completed_at` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'item 不存在' |

### `POST /api/v1/final-review/campaigns/{campaign_id}/daily-checkins`

用途：每日签到/晚间反馈。记录完成情况和反馈作为 evidence。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`daily_checkin`。

Web 封装：`createDailyCheckin`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

每日签到/晚间反馈。记录完成情况和反馈作为 evidence。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[DailyCheckinIn](schemas.md#schema-dailycheckinin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `report_date` | string | 是 | minLength=1; maxLength=32 | — |
| `completed_item_ids` | array<string> | 否 | — | — |
| `insufficient_time` | boolean | 否 | default=false | — |
| `difficulty_notes` | string / null | 否 | string约束: maxLength=500 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "report_date": "<report_date>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DailyCheckinOut](schemas.md#schema-dailycheckinout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `recorded` | boolean | 是 | — | — |
| `evidence_count` | integer | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'campaign 不存在' |

### `POST /api/v1/final-review/campaigns/{campaign_id}/adjustments/analyze`

用途：Analyzer 分析证据,产生 adjustment proposal。不直接改 active plan。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`analyze_adjustments`。

Web 封装：`analyzeAdjustment`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

Analyzer 分析证据,产生 adjustment proposal。不直接改 active plan。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[AdjustmentAnalyzeIn](schemas.md#schema-adjustmentanalyzein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AdjustmentAnalyzeOut](schemas.md#schema-adjustmentanalyzeout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | — | 运行标识 |
| `proposal_id` | string | 是 | — | — |
| `risk_level` | string | 是 | — | — |
| `requires_approval` | boolean | 是 | — | — |
| `approval_id` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'campaign 不存在' |
| 409 | 'AGENT_INVALID_STATE' | 'campaign 尚未激活' |
| 409 | 'AGENT_INVALID_STATE' | '幂等请求仍在处理中' |
| 409 | AGENT_IDEMPOTENCY_CONFLICT | 幂等键已用于不同的请求。 |

### `GET /api/v1/final-review/campaigns/{campaign_id}/adjustment-proposals`

用途：列出调整建议。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`list_proposals`。

Web 封装：`getAdjustmentProposals`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `campaign_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[AdjustmentProposalOut](schemas.md#schema-adjustmentproposalout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/final-review/adjustment-proposals/{proposal_id}/decision`

用途：审批 adjustment proposal。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/final_review.py](../../backend/app/api/routes/final_review.py)，`proposal_decision`。

Web 封装：`resolveAdjustmentProposal`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

审批 adjustment proposal。

路由只解析用户审批并创建命令:批准后的新版本由 Handler 经 Gateway 创建并激活,
最终状态由 Worker 原子写入;拒绝则不创建任何命令,计划保持不变。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `proposal_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[AdjustmentDecisionIn](schemas.md#schema-adjustmentdecisionin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `decision` | string | 是 | pattern="^(APPROVED\|REJECTED)$" | 用户决定，严格按枚举大小写 |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "decision": "<decision>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AdjustmentDecisionOut](schemas.md#schema-adjustmentdecisionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `proposal_id` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `new_version` | integer / null | 否 | — | — |
| `active_version` | integer / null | 否 | — | — |
| `run_id` | string / null | 否 | — | 运行标识 |
| `pending` | boolean | 否 | default=false | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | 'proposal 不存在' |
| 410 if approval.status == ApprovalStatus.EXPIRED.value else 409 | 'AGENT_INVALID_STATE' | f'审批未通过({approval.status})，不能执行该调整' |

### `POST /api/v1/course-research/runs`

用途：创建课程研究 Run 并同步执行。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/course_research.py](../../backend/app/api/routes/course_research.py)，`create_run`。

Web 封装：`createCourseResearchRun`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

创建课程研究 Run 并同步执行。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[CourseResearchRunCreateIn](schemas.md#schema-courseresearchruncreatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string / null | 否 | string约束: maxLength=64 | 关联课程标识 |
| `question` | string | 是 | minLength=1; maxLength=2000 | — |
| `assistance_mode` | [AssistanceMode](schemas.md#schema-assistancemode) | 否 | default="EXPLAIN" | — |
| `academic_policy` | [AcademicPolicy](schemas.md#schema-academicpolicy) | 否 | default="UNKNOWN" | — |
| `source_policy` | [SourcePolicyIn](schemas.md#schema-sourcepolicyin) | 否 | — | — |
| `user_upload_refs` | array<string> | 否 | — | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "question": "<question>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CourseResearchRunOut](schemas.md#schema-courseresearchrunout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `session_id` | string | 是 | minLength=1; maxLength=64 | — |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `course_id` | string / null | 否 | string约束: maxLength=64 | 关联课程标识 |
| `question` | string | 是 | maxLength=2000 | — |
| `assistance_mode` | [AssistanceMode](schemas.md#schema-assistancemode) | 是 | — | — |
| `academic_policy` | [AcademicPolicy](schemas.md#schema-academicpolicy) | 是 | — | — |
| `effective_assistance_mode` | [AssistanceMode](schemas.md#schema-assistancemode) | 是 | — | — |
| `source_policy` | [SourcePolicyOut](schemas.md#schema-sourcepolicyout) | 是 | — | — |
| `status` | [RunStatus](schemas.md#schema-runstatus) | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `finished_at` | string / null | 否 | string约束: maxLength=64 | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `artifact_ids` | array<string> | 否 | — | — |
| `fallback_used` | boolean | 否 | default=false | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/course-research/runs`

用途：列出当前用户的课程研究 Run。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_research.py](../../backend/app/api/routes/course_research.py)，`list_runs`。

Web 封装：`getCourseResearchRuns`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

列出当前用户的课程研究 Run。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `limit` | integer | 否 | default=50; minimum=1; maximum=200 | — |
| query | `offset` | integer | 否 | default=0; minimum=0 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[CourseResearchRunOut](schemas.md#schema-courseresearchrunout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/course-research/runs/{run_id}`

用途：获取单个课程研究 Run。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_research.py](../../backend/app/api/routes/course_research.py)，`get_run`。

Web 封装：`getCourseResearchRun`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

获取单个课程研究 Run。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CourseResearchRunOut](schemas.md#schema-courseresearchrunout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `session_id` | string | 是 | minLength=1; maxLength=64 | — |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `course_id` | string / null | 否 | string约束: maxLength=64 | 关联课程标识 |
| `question` | string | 是 | maxLength=2000 | — |
| `assistance_mode` | [AssistanceMode](schemas.md#schema-assistancemode) | 是 | — | — |
| `academic_policy` | [AcademicPolicy](schemas.md#schema-academicpolicy) | 是 | — | — |
| `effective_assistance_mode` | [AssistanceMode](schemas.md#schema-assistancemode) | 是 | — | — |
| `source_policy` | [SourcePolicyOut](schemas.md#schema-sourcepolicyout) | 是 | — | — |
| `status` | [RunStatus](schemas.md#schema-runstatus) | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `finished_at` | string / null | 否 | string约束: maxLength=64 | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `artifact_ids` | array<string> | 否 | — | — |
| `fallback_used` | boolean | 否 | default=false | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |

### `POST /api/v1/course-research/runs/{run_id}/cancel`

用途：取消课程研究 Run。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_research.py](../../backend/app/api/routes/course_research.py)，`cancel_run`。

Web 封装：`cancelCourseResearchRun`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

取消课程研究 Run。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |

请求体：`application/json`，必填；[CourseResearchRunCancelIn](schemas.md#schema-courseresearchruncancelin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CourseResearchRunOut](schemas.md#schema-courseresearchrunout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `session_id` | string | 是 | minLength=1; maxLength=64 | — |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `course_id` | string / null | 否 | string约束: maxLength=64 | 关联课程标识 |
| `question` | string | 是 | maxLength=2000 | — |
| `assistance_mode` | [AssistanceMode](schemas.md#schema-assistancemode) | 是 | — | — |
| `academic_policy` | [AcademicPolicy](schemas.md#schema-academicpolicy) | 是 | — | — |
| `effective_assistance_mode` | [AssistanceMode](schemas.md#schema-assistancemode) | 是 | — | — |
| `source_policy` | [SourcePolicyOut](schemas.md#schema-sourcepolicyout) | 是 | — | — |
| `status` | [RunStatus](schemas.md#schema-runstatus) | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `finished_at` | string / null | 否 | string约束: maxLength=64 | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `artifact_ids` | array<string> | 否 | — | — |
| `fallback_used` | boolean | 否 | default=false | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |
| 403 | 'AGENT_PERMISSION_DENIED' | '无权取消' |

### `GET /api/v1/course-research/runs/{run_id}/artifacts`

用途：列出 Run 的产物与来源。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_research.py](../../backend/app/api/routes/course_research.py)，`list_artifacts`。

Web 封装：`getCourseResearchArtifacts`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

列出 Run 的产物与来源。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CourseResearchArtifactListOut](schemas.md#schema-courseresearchartifactlistout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `artifacts` | array<[CourseResearchArtifactOut](schemas.md#schema-courseresearchartifactout)> | 否 | — | — |
| `sources` | array<[ResearchSourceOut](schemas.md#schema-researchsourceout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |
