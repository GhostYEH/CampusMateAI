# 请求与响应字段字典

> `必须出现` 表示 JSON 字段是否必需；是否允许 null 由类型决定，二者不同。类型 any/object 的开放属性不能视为固定字段。默认值、枚举、长度和格式来自 Pydantic/OpenAPI；跨字段校验及状态转换另见模块文档、接入流程和模型源码。

[文档导航](README.md) · [OpenAPI](openapi.json)

<a id="schema-academicbindrequest"></a>
## AcademicBindRequest

模型定义：[backend/app/schemas/academic.py](../../backend/app/schemas/academic.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=1; maxLength=128 | 登录用户名 |
| `password` | string (password) | 是 | format="password"; writeOnly=true | 登录密码，仅请求使用 |

<a id="schema-academiccourseloadvalue"></a>
## AcademicCourseLoadValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `current_semester_course_count` | integer | 是 | minimum=0.0 | — |
| `effective_credit_load` | number | 是 | minimum=0.0 | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-academicpolicy"></a>
## AcademicPolicy

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

学术策略(§8.2)。客户端输入不得强制 ALLOWED。


类型：enum ["ALLOWED", "LIMITED", "EXAM_RESTRICTED", "AI_PROHIBITED", "UNKNOWN"]。

```json
{
  "type": "string",
  "enum": [
    "ALLOWED",
    "LIMITED",
    "EXAM_RESTRICTED",
    "AI_PROHIBITED",
    "UNKNOWN"
  ],
  "title": "AcademicPolicy",
  "description": "学术策略(§8.2)。客户端输入不得强制 ALLOWED。"
}
```

对象级约束：

```json
{
  "enum": [
    "ALLOWED",
    "LIMITED",
    "EXAM_RESTRICTED",
    "AI_PROHIBITED",
    "UNKNOWN"
  ]
}
```

<a id="schema-academicprogressvalue"></a>
## AcademicProgressValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_course_count` | integer | 是 | minimum=0.0 | — |
| `observed_credit_count` | number | 是 | minimum=0.0 | — |
| `observed_passed_count` | integer | 是 | minimum=0.0 | — |
| `platform_grade_count` | integer | 否 | default=0; minimum=0.0 | — |
| `platform_average_score` | number / null | 否 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-acceptplanintervention"></a>
## AcceptPlanIntervention

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `intervention_type` | const "ACCEPT_PLAN" | 否 | default="ACCEPT_PLAN" | — |
| `plan_id` | string | 是 | minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-actiondecisionin"></a>
## ActionDecisionIn

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

POST /notice-workflow-actions/{action_id}/decision。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `decision` | string | 是 | pattern="^(APPROVED\|REJECTED)$" | 用户决定，严格按枚举大小写 |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-actionexecutein"></a>
## ActionExecuteIn

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

POST /notice-workflow-actions/{action_id}/execute。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-actionresultout"></a>
## ActionResultOut

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `action_id` | string | 是 | minLength=1; maxLength=64 | — |
| `status` | string | 是 | maxLength=16 | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `external_ref` | string / null | 否 | string约束: maxLength=128 | — |
| `result` | object / null | 否 | — | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `error_message` | string / null | 否 | string约束: maxLength=256 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-activatein"></a>
## ActivateIn

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | integer | 是 | minimum=1.0 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-activateout"></a>
## ActivateOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `campaign_id` | string | 是 | — | — |
| `active_version` | integer | 是 | — | — |
| `activated` | boolean | 是 | — | — |
| `status` | string | 否 | default="ACTIVE" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `run_id` | string / null | 否 | — | 运行标识 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-adaptiveinterventionout"></a>
## AdaptiveInterventionOut

模型定义：[backend/app/schemas/adaptive_intervention.py](../../backend/app/schemas/adaptive_intervention.py)。

学生本人可读的干预记录视图：不含 user_id、原始 JSON 或敏感证据。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-adaptiveinterventionoutcomeout"></a>
## AdaptiveInterventionOutcomeOut

模型定义：[backend/app/schemas/adaptive_intervention.py](../../backend/app/schemas/adaptive_intervention.py)。

学生本人可读的结果评估视图：不含 user_id、证据引用或原始 JSON。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-adaptiveinterventionpage"></a>
## AdaptiveInterventionPage

模型定义：[backend/app/schemas/adaptive_intervention.py](../../backend/app/schemas/adaptive_intervention.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[AdaptiveInterventionOut](schemas.md#schema-adaptiveinterventionout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

<a id="schema-adjustgoaldeadlineintervention"></a>
## AdjustGoalDeadlineIntervention

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `intervention_type` | const "ADJUST_GOAL_DEADLINE" | 否 | default="ADJUST_GOAL_DEADLINE" | — |
| `goal_id` | string | 是 | minLength=1; maxLength=128 | — |
| `new_target_date` | string (date-time) | 是 | format="date-time" | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-adjustmentanalyzein"></a>
## AdjustmentAnalyzeIn

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-adjustmentanalyzeout"></a>
## AdjustmentAnalyzeOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

Analyzer 结果。只产生 proposal,不直接改 active plan。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | — | 运行标识 |
| `proposal_id` | string | 是 | — | — |
| `risk_level` | string | 是 | — | — |
| `requires_approval` | boolean | 是 | — | — |
| `approval_id` | string / null | 否 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-adjustmentdecisionin"></a>
## AdjustmentDecisionIn

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `decision` | string | 是 | pattern="^(APPROVED\|REJECTED)$" | 用户决定，严格按枚举大小写 |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-adjustmentdecisionout"></a>
## AdjustmentDecisionOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

审批决策结果。

决策被受理后只创建命令:新版本由 Worker 经 Gateway 创建并激活,
因此 `new_version` 在命令完成前为 None,客户端应据 `run_id` 观察进展。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `proposal_id` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `new_version` | integer / null | 否 | — | — |
| `active_version` | integer / null | 否 | — | — |
| `run_id` | string / null | 否 | — | 运行标识 |
| `pending` | boolean | 否 | default=false | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-adjustmentproposalout"></a>
## AdjustmentProposalOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `proposal_id` | string | 是 | — | — |
| `campaign_id` | string | 是 | — | — |
| `source_version` | integer | 是 | — | — |
| `proposal` | object | 是 | — | — |
| `risk_level` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `approval_id` | string / null | 否 | — | — |
| `target_version` | integer / null | 否 | — | — |
| `reason` | string / null | 否 | — | 原因 |
| `created_at` | string | 是 | — | 创建时间 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agendaitemout"></a>
## AgendaItemOut

模型定义：[backend/app/schemas/agenda.py](../../backend/app/schemas/agenda.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `source` | string | 是 | — | 来源 |
| `kind` | string | 是 | — | — |
| `source_id` | string | 是 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `course_name` | string / null | 否 | — | — |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `starts_at` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `status` | string | 否 | default="pending" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `priority` | string | 否 | default="medium" | — |
| `editable` | boolean | 否 | default=false | — |
| `completable` | boolean | 否 | default=false | — |
| `route` | string / null | 否 | — | — |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |

<a id="schema-agendasourcestate"></a>
## AgendaSourceState

模型定义：[backend/app/schemas/agenda.py](../../backend/app/schemas/agenda.py)。

单个数据来源的健康状态，用于区分"真的没有"与"取不到"。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `state` | string | 否 | default="ok" | — |
| `message` | string / null | 否 | — | — |
| `item_count` | integer | 否 | default=0 | — |
| `last_synced_at` | string / null | 否 | — | — |
| `auth_state` | string | 否 | default="unknown" | — |

<a id="schema-agendasourcesout"></a>
## AgendaSourcesOut

模型定义：[backend/app/schemas/agenda.py](../../backend/app/schemas/agenda.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `chaoxing` | [AgendaSourceState](schemas.md#schema-agendasourcestate) | 否 | — | — |
| `personal` | [AgendaSourceState](schemas.md#schema-agendasourcestate) | 否 | — | — |
| `schedule` | [AgendaSourceState](schemas.md#schema-agendasourcestate) | 否 | — | — |

<a id="schema-agendasummaryout"></a>
## AgendaSummaryOut

模型定义：[backend/app/schemas/agenda.py](../../backend/app/schemas/agenda.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total` | integer | 否 | default=0 | 总数 |
| `pending` | integer | 否 | default=0 | — |
| `completed` | integer | 否 | default=0 | — |
| `overdue` | integer | 否 | default=0 | — |

<a id="schema-agentapprovaldecisionin"></a>
## AgentApprovalDecisionIn

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

审批决策请求体。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `decision` | string | 是 | pattern="^(APPROVED\|REJECTED)$" | 用户决定，严格按枚举大小写 |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentapprovalout"></a>
## AgentApprovalOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

审批记录(§5.5)。过期绝不等于批准。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `approval_id` | string | 是 | minLength=1; maxLength=64 | — |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `status` | [ApprovalStatus](schemas.md#schema-approvalstatus) | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `risk_level` | [RiskLevel](schemas.md#schema-risklevel) | 是 | — | — |
| `action_summary` | string | 是 | maxLength=256 | — |
| `expires_at` | string | 是 | minLength=1; maxLength=64 | — |
| `resolved_at` | string / null | 否 | string约束: maxLength=64 | — |
| `decision_reason` | string / null | 否 | string约束: maxLength=256 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentartifactout"></a>
## AgentArtifactOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

产物(§5.9)。读取/下载时重新校验所有权。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `artifact_id` | string | 是 | minLength=1; maxLength=64 | — |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `artifact_type` | [ArtifactType](schemas.md#schema-artifacttype) | 是 | — | — |
| `version` | integer | 是 | minimum=1.0 | — |
| `mime_type` | string | 是 | maxLength=64 | 媒体类型 |
| `size_bytes` | integer | 是 | minimum=0.0 | — |
| `content_hash` | string | 是 | minLength=8; maxLength=128 | — |
| `download_url` | string / null | 否 | string约束: maxLength=512 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentcapabilitiesout"></a>
## AgentCapabilitiesOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

能力清单 + 契约版本。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `contract_version` | string | 否 | default="v1" | — |
| `capabilities` | array<[AgentCapabilityOut](schemas.md#schema-agentcapabilityout)> | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentcapabilityout"></a>
## AgentCapabilityOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

单个能力声明(/capabilities 端点)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=64 | 名称 |
| `version` | string | 是 | minLength=1; maxLength=32 | — |
| `route_policy` | [ModelRoutePolicy](schemas.md#schema-modelroutepolicy) | 是 | — | — |
| `risk_level` | [RiskLevel](schemas.md#schema-risklevel) | 是 | — | — |
| `requires_approval` | boolean | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agenterrorcode"></a>
## AgentErrorCode

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

稳定错误码(§9.2)。HTTP 状态码表达传输/鉴权/冲突语义,客户端按 code 分支。


类型：enum ["AGENT_INVALID_STATE", "AGENT_PERMISSION_DENIED", "AGENT_TOOL_REJECTED", "AGENT_APPROVAL_REQUIRED", "AGENT_PROVIDER_UNAVAILABLE", "AGENT_CONTEXT_EXPIRED", "AGENT_IDEMPOTENCY_CONFLICT", "AGENT_RUN_NOT_FOUND", "AGENT_RUN_CANCELLED", "AGENT_OUTPUT_SCHEMA_INVALID", "AGENT_SOURCE_POLICY_VIOLATION", "AGENT_ACADEMIC_POLICY_RESTRICTED", "AGENT_CAPABILITY_DISABLED", "AGENT_RUNTIME_UNAVAILABLE", "AGENT_CURSOR_INVALID"]。

```json
{
  "type": "string",
  "enum": [
    "AGENT_INVALID_STATE",
    "AGENT_PERMISSION_DENIED",
    "AGENT_TOOL_REJECTED",
    "AGENT_APPROVAL_REQUIRED",
    "AGENT_PROVIDER_UNAVAILABLE",
    "AGENT_CONTEXT_EXPIRED",
    "AGENT_IDEMPOTENCY_CONFLICT",
    "AGENT_RUN_NOT_FOUND",
    "AGENT_RUN_CANCELLED",
    "AGENT_OUTPUT_SCHEMA_INVALID",
    "AGENT_SOURCE_POLICY_VIOLATION",
    "AGENT_ACADEMIC_POLICY_RESTRICTED",
    "AGENT_CAPABILITY_DISABLED",
    "AGENT_RUNTIME_UNAVAILABLE",
    "AGENT_CURSOR_INVALID"
  ],
  "title": "AgentErrorCode",
  "description": "稳定错误码(§9.2)。HTTP 状态码表达传输/鉴权/冲突语义,客户端按 code 分支。"
}
```

对象级约束：

```json
{
  "enum": [
    "AGENT_INVALID_STATE",
    "AGENT_PERMISSION_DENIED",
    "AGENT_TOOL_REJECTED",
    "AGENT_APPROVAL_REQUIRED",
    "AGENT_PROVIDER_UNAVAILABLE",
    "AGENT_CONTEXT_EXPIRED",
    "AGENT_IDEMPOTENCY_CONFLICT",
    "AGENT_RUN_NOT_FOUND",
    "AGENT_RUN_CANCELLED",
    "AGENT_OUTPUT_SCHEMA_INVALID",
    "AGENT_SOURCE_POLICY_VIOLATION",
    "AGENT_ACADEMIC_POLICY_RESTRICTED",
    "AGENT_CAPABILITY_DISABLED",
    "AGENT_RUNTIME_UNAVAILABLE",
    "AGENT_CURSOR_INVALID"
  ]
}
```

<a id="schema-agenterrorenvelope"></a>
## AgentErrorEnvelope

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

统一错误响应。

`details` 仅承载非敏感业务标识(run_id / approval_id 等),
禁止包含 prompt、完整模型响应、凭据或敏感工具参数。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | [AgentErrorCode](schemas.md#schema-agenterrorcode) | 是 | — | — |
| `message` | string | 是 | maxLength=256 | — |
| `request_id` | string | 是 | minLength=1; maxLength=128 | — |
| `details` | object / null | 否 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agenteventout"></a>
## AgentEventOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

SSE 事件(§5.7)。

`summary` 为安全摘要,绝不包含 prompt、隐藏推理、完整模型响应、凭据或敏感工具参数。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | minLength=1; maxLength=64 | 当前资源标识 |
| `type` | [AgentEventType](schemas.md#schema-agenteventtype) | 是 | — | — |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `sequence` | integer | 是 | minimum=0.0 | — |
| `status` | [RunStatus](schemas.md#schema-runstatus) | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `phase` | [RunPhase](schemas.md#schema-runphase) | 是 | — | — |
| `role` | string / null | 否 | string约束: maxLength=64 | — |
| `summary` | string / null | 否 | string约束: maxLength=512 | — |
| `progress` | [AgentProgressOut](schemas.md#schema-agentprogressout) / null | 否 | — | 进度；对象或数值范围按字段类型 |
| `artifact_id` | string / null | 否 | string约束: maxLength=64 | — |
| `approval_id` | string / null | 否 | string约束: maxLength=64 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agenteventtype"></a>
## AgentEventType

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

SSE 事件类型(§5.7)。


类型：enum ["RUN_QUEUED", "RUN_STARTED", "CONTEXT_READY", "MODEL_STARTED", "MODEL_COMPLETED", "MODEL_FALLBACK", "TOOL_STARTED", "TOOL_COMPLETED", "TOOL_FAILED", "APPROVAL_REQUIRED", "APPROVAL_RESOLVED", "ARTIFACT_CREATED", "RUN_PARTIAL", "RUN_COMPLETED", "RUN_FAILED", "RUN_CANCELLED", "RUN_PAUSED", "RUN_RESUMED", "RUN_RETRIED", "RUN_RETRY_SCHEDULED", "RUN_RECOVERY_STARTED", "RUN_RECOVERED", "APPROVAL_GRANTED", "STATE_ANALYZED", "STRATEGY_SELECTED", "INTERVENTION_RECORDED", "PLAN_GENERATED"]。

```json
{
  "type": "string",
  "enum": [
    "RUN_QUEUED",
    "RUN_STARTED",
    "CONTEXT_READY",
    "MODEL_STARTED",
    "MODEL_COMPLETED",
    "MODEL_FALLBACK",
    "TOOL_STARTED",
    "TOOL_COMPLETED",
    "TOOL_FAILED",
    "APPROVAL_REQUIRED",
    "APPROVAL_RESOLVED",
    "ARTIFACT_CREATED",
    "RUN_PARTIAL",
    "RUN_COMPLETED",
    "RUN_FAILED",
    "RUN_CANCELLED",
    "RUN_PAUSED",
    "RUN_RESUMED",
    "RUN_RETRIED",
    "RUN_RETRY_SCHEDULED",
    "RUN_RECOVERY_STARTED",
    "RUN_RECOVERED",
    "APPROVAL_GRANTED",
    "STATE_ANALYZED",
    "STRATEGY_SELECTED",
    "INTERVENTION_RECORDED",
    "PLAN_GENERATED"
  ],
  "title": "AgentEventType",
  "description": "SSE 事件类型(§5.7)。"
}
```

对象级约束：

```json
{
  "enum": [
    "RUN_QUEUED",
    "RUN_STARTED",
    "CONTEXT_READY",
    "MODEL_STARTED",
    "MODEL_COMPLETED",
    "MODEL_FALLBACK",
    "TOOL_STARTED",
    "TOOL_COMPLETED",
    "TOOL_FAILED",
    "APPROVAL_REQUIRED",
    "APPROVAL_RESOLVED",
    "ARTIFACT_CREATED",
    "RUN_PARTIAL",
    "RUN_COMPLETED",
    "RUN_FAILED",
    "RUN_CANCELLED",
    "RUN_PAUSED",
    "RUN_RESUMED",
    "RUN_RETRIED",
    "RUN_RETRY_SCHEDULED",
    "RUN_RECOVERY_STARTED",
    "RUN_RECOVERED",
    "APPROVAL_GRANTED",
    "STATE_ANALYZED",
    "STRATEGY_SELECTED",
    "INTERVENTION_RECORDED",
    "PLAN_GENERATED"
  ]
}
```

<a id="schema-agentjobcreatein"></a>
## AgentJobCreateIn

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

创建 Job 请求。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `job_kind` | string | 是 | pattern="^(learning_goal\|final_review\|course_research\|notice_workflow\|interactive_classroom)$" | — |
| `input_ref` | object | 否 | — | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentjobout"></a>
## AgentJobOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

Job 概览。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `job_id` | string | 是 | minLength=1; maxLength=64 | 任务标识 |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `job_kind` | string | 是 | maxLength=64 | — |
| `status` | [RunStatus](schemas.md#schema-runstatus) | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `latest_run_id` | string / null | 否 | string约束: maxLength=64 | — |
| `pending_approval_id` | string / null | 否 | string约束: maxLength=64 | — |
| `input_ref` | object | 否 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentmemorycreatein"></a>
## AgentMemoryCreateIn

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

创建显式记忆。只有用户明确确认且允许消费时才会进入模型上下文。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | string | 是 | pattern="^(CONFIRMED_PREFERENCE\|CONFIRMED_STUDY_GOAL\|CONFIRMED_CONSTRAINT\|USER_APPROVED_SUMMARY)$" | — |
| `content_summary` | string | 是 | minLength=1; maxLength=512 | — |
| `sensitivity` | string | 否 | default="low"; pattern="^(low\|medium\|high)$" | — |
| `confirmed` | boolean | 否 | default=false | — |
| `model_may_consume` | boolean | 否 | default=false | — |
| `provenance` | string / null | 否 | string约束: maxLength=128 | — |
| `valid_until` | string / null | 否 | string约束: maxLength=64 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentmemoryout"></a>
## AgentMemoryOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

显式记忆记录(§5.2)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `memory_id` | string | 是 | minLength=1; maxLength=64 | — |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `kind` | string | 是 | pattern="^(CONFIRMED_PREFERENCE\|CONFIRMED_STUDY_GOAL\|CONFIRMED_CONSTRAINT\|USER_APPROVED_SUMMARY)$" | — |
| `content_summary` | string | 是 | maxLength=512 | — |
| `sensitivity` | string | 是 | pattern="^(low\|medium\|high)$" | — |
| `confirmed` | boolean | 是 | — | — |
| `withdrawn` | boolean | 否 | default=false | — |
| `model_may_consume` | boolean | 否 | default=false | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentprogressout"></a>
## AgentProgressOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

Run 进度(§5.7 SSE event.progress)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `current` | integer | 是 | minimum=0.0 | — |
| `total` | integer | 是 | minimum=0.0 | 总数 |
| `percent` | integer | 是 | minimum=0.0; maximum=100.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentruncancelin"></a>
## AgentRunCancelIn

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

取消 Run 请求。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentruncontrolin"></a>
## AgentRunControlIn

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

暂停、恢复和重试的统一控制请求。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentrunout"></a>
## AgentRunOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

Run 详情(§5.6)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `job_id` | string | 是 | minLength=1; maxLength=64 | 任务标识 |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `status` | [RunStatus](schemas.md#schema-runstatus) | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `phase` | [RunPhase](schemas.md#schema-runphase) | 是 | — | — |
| `risk_level` | [RiskLevel](schemas.md#schema-risklevel) / null | 否 | — | — |
| `started_at` | string / null | 否 | string约束: maxLength=64 | — |
| `finished_at` | string / null | 否 | string约束: maxLength=64 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `error` | [AgentErrorEnvelope](schemas.md#schema-agenterrorenvelope) / null | 否 | — | — |
| `artifact_ids` | array<string> | 否 | — | — |
| `retry_of` | string / null | 否 | string约束: maxLength=64 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentruntraceout"></a>
## AgentRunTraceOut

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

单 Run 时间线。只包含安全摘要、状态、耗时与业务标识。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run` | [RunTraceHeader](schemas.md#schema-runtraceheader) | 是 | — | — |
| `events` | array<[RunTraceEvent](schemas.md#schema-runtraceevent)> | 否 | — | — |
| `tool_calls` | array<[RunTraceToolCall](schemas.md#schema-runtracetoolcall)> | 否 | — | — |
| `model_calls` | array<[RunTraceModelCall](schemas.md#schema-runtracemodelcall)> | 否 | — | — |
| `approvals` | array<[RunTraceApproval](schemas.md#schema-runtraceapproval)> | 否 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentruntimeoverviewout"></a>
## AgentRuntimeOverviewOut

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

队列、成功率、耗时、Token、工具、重试与审批等待的聚合视图。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `window_hours` | integer | 是 | minimum=1.0 | — |
| `since` | string | 是 | — | — |
| `queue_depth` | integer | 否 | default=0; minimum=0.0 | — |
| `stale_lease_count` | integer | 否 | default=0; minimum=0.0 | — |
| `run_count` | integer | 否 | default=0; minimum=0.0 | — |
| `status_distribution` | map<string, integer> | 否 | additionalProperties={"type": "integer"} | — |
| `success_rate` | number / null | 否 | number约束: minimum=0.0; maximum=1.0 | — |
| `duration_ms` | [DurationStats](schemas.md#schema-durationstats) | 是 | — | — |
| `model_latency_ms` | [ModelLatencyStats](schemas.md#schema-modellatencystats) | 是 | — | — |
| `token_usage` | [TokenUsage](schemas.md#schema-tokenusage) | 是 | — | — |
| `tool_failure_count` | integer | 否 | default=0; minimum=0.0 | — |
| `tool_call_count` | integer | 否 | default=0; minimum=0.0 | — |
| `retry_count` | integer | 否 | default=0; minimum=0.0 | — |
| `approval` | [ApprovalStats](schemas.md#schema-approvalstats) | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentskillout"></a>
## AgentSkillOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

声明式 Skill 元数据；不暴露执行地址或凭据。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `skill_code` | string | 是 | minLength=1; maxLength=64 | — |
| `version` | string | 是 | minLength=1; maxLength=32 | — |
| `description` | string | 否 | default=""; maxLength=256 | 说明 |
| `capabilities` | array<string> | 否 | — | — |
| `tools` | array<string> | 否 | — | — |
| `transport` | string | 是 | pattern="^(internal\|mcp_manifest)$" | — |
| `permission_policy` | string | 是 | maxLength=64 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-agentskillsout"></a>
## AgentSkillsOut

模型定义：[backend/app/schemas/agent_runtime.py](../../backend/app/schemas/agent_runtime.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `contract_version` | string | 否 | default="v1" | — |
| `skills` | array<[AgentSkillOut](schemas.md#schema-agentskillout)> | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-allocatefocusminutesintervention"></a>
## AllocateFocusMinutesIntervention

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `intervention_type` | const "ALLOCATE_FOCUS_MINUTES" | 否 | default="ALLOCATE_FOCUS_MINUTES" | — |
| `focus_minutes` | integer | 是 | minimum=0.0; maximum=480.0 | — |
| `target_date` | string (date-time) / null | 否 | string约束: format="date-time" | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-announcementout"></a>
## AnnouncementOut

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `class_group_id` | string | 是 | — | — |
| `author_id` | string | 是 | — | — |
| `author_name` | string / null | 否 | — | — |
| `title` | string | 是 | — | 标题 |
| `content` | string | 是 | — | 正文或业务内容，嵌套结构按类型 |
| `require_read` | boolean | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `published_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `has_read` | boolean / null | 否 | — | 当前学生视角是否已读(教师/管理员为 null) |

<a id="schema-approvalstats"></a>
## ApprovalStats

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `pending` | integer | 否 | default=0; minimum=0.0 | — |
| `resolved` | integer | 否 | default=0; minimum=0.0 | — |
| `expired` | integer | 否 | default=0; minimum=0.0 | — |
| `wait_p50_ms` | number / null | 否 | number约束: minimum=0.0 | — |
| `wait_p95_ms` | number / null | 否 | number约束: minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-approvalstatus"></a>
## ApprovalStatus

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

审批状态(§5.5)。过期绝不等于批准。


类型：enum ["PENDING", "APPROVED", "REJECTED", "EXPIRED"]。

```json
{
  "type": "string",
  "enum": [
    "PENDING",
    "APPROVED",
    "REJECTED",
    "EXPIRED"
  ],
  "title": "ApprovalStatus",
  "description": "审批状态(§5.5)。过期绝不等于批准。"
}
```

对象级约束：

```json
{
  "enum": [
    "PENDING",
    "APPROVED",
    "REJECTED",
    "EXPIRED"
  ]
}
```

<a id="schema-artifacttype"></a>
## ArtifactType

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

产物类型(§5.9)。


类型：enum ["FINAL_REVIEW_PLAN", "DAILY_AGENDA", "NOTICE_CHECKLIST", "COURSE_RESEARCH_REPORT", "CITATION_BUNDLE"]。

```json
{
  "type": "string",
  "enum": [
    "FINAL_REVIEW_PLAN",
    "DAILY_AGENDA",
    "NOTICE_CHECKLIST",
    "COURSE_RESEARCH_REPORT",
    "CITATION_BUNDLE"
  ],
  "title": "ArtifactType",
  "description": "产物类型(§5.9)。"
}
```

对象级约束：

```json
{
  "enum": [
    "FINAL_REVIEW_PLAN",
    "DAILY_AGENDA",
    "NOTICE_CHECKLIST",
    "COURSE_RESEARCH_REPORT",
    "CITATION_BUNDLE"
  ]
}
```

<a id="schema-assignmentattachmentout"></a>
## AssignmentAttachmentOut

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `assignment_id` | string | 是 | — | — |
| `author_id` | string | 是 | — | — |
| `original_filename` | string | 是 | — | — |
| `stored_filename` | string | 是 | — | — |
| `mime_type` | string / null | 否 | — | 媒体类型 |
| `size_bytes` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |

<a id="schema-assignmentout"></a>
## AssignmentOut

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `class_group_id` | string | 是 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `author_id` | string | 是 | — | — |
| `author_name` | string / null | 否 | — | — |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `deadline` | string / null | 否 | — | 截止时间 |
| `submission_types` | array<string> | 否 | — | — |
| `max_score` | number / null | 否 | — | — |
| `allow_resubmit` | boolean | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `published_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `submission_status` | string / null | 否 | — | 当前学生的提交状态；教师和管理员为 null |
| `attachments` | array<[AssignmentAttachmentOut](schemas.md#schema-assignmentattachmentout)> | 否 | — | — |

<a id="schema-assistancemode"></a>
## AssistanceMode

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

课程研究辅助模式(§8.2)。FULL_SOLUTION 仅在策略允许的普通练习中可用。


类型：enum ["HINT", "EXPLAIN", "REVIEW", "FULL_SOLUTION"]。

```json
{
  "type": "string",
  "enum": [
    "HINT",
    "EXPLAIN",
    "REVIEW",
    "FULL_SOLUTION"
  ],
  "title": "AssistanceMode",
  "description": "课程研究辅助模式(§8.2)。FULL_SOLUTION 仅在策略允许的普通练习中可用。"
}
```

对象级约束：

```json
{
  "enum": [
    "HINT",
    "EXPLAIN",
    "REVIEW",
    "FULL_SOLUTION"
  ]
}
```

<a id="schema-attachmentout"></a>
## AttachmentOut

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `submission_id` | string | 是 | — | — |
| `original_filename` | string | 是 | — | — |
| `stored_filename` | string | 是 | — | — |
| `mime_type` | string / null | 否 | — | 媒体类型 |
| `size_bytes` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |

<a id="schema-authmeresponse"></a>
## AuthMeResponse

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user` | [UserPublic](schemas.md#schema-userpublic) | 是 | — | — |
| `access_token` | string / null | 否 | — | 业务访问令牌 |
| `expires_in` | integer / null | 否 | — | — |

<a id="schema-body_import_pptx_stage_api_v1_courses__course_id__workspaces__workspace_id__import_pptx_post"></a>
## Body_import_pptx_stage_api_v1_courses__course_id__workspaces__workspace_id__import_pptx_post

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |

<a id="schema-body_import_stage_api_v1_courses__course_id__workspaces__workspace_id__import_post"></a>
## Body_import_stage_api_v1_courses__course_id__workspaces__workspace_id__import_post

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |

<a id="schema-body_upload_attachment_api_v1_submissions__submission_id__attachments_post"></a>
## Body_upload_attachment_api_v1_submissions__submission_id__attachments_post

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |

<a id="schema-body_upload_document_api_v1_knowledge_documents_post"></a>
## Body_upload_document_api_v1_knowledge_documents_post

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |
| `title` | string / null | 否 | — | 标题 |
| `source_department` | string / null | 否 | — | — |
| `source_type` | string / null | 否 | — | — |
| `published_at` | string / null | 否 | — | — |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `effective_from` | string / null | 否 | — | — |
| `effective_to` | string / null | 否 | — | — |
| `version` | string / null | 否 | — | — |
| `applicable_students` | string / null | 否 | — | — |
| `is_official` | boolean | 否 | default=false | — |

<a id="schema-body_upload_expression_sample_api_v1_contributions_expression_samples_post"></a>
## Body_upload_expression_sample_api_v1_contributions_expression_samples_post

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `image` | string (binary) | 是 | format="binary" | — |
| `label` | string | 是 | — | — |
| `consent` | boolean | 是 | — | — |
| `model_version` | string | 否 | default="unknown" | — |

<a id="schema-body_upload_home_banner_image_api_v1_admin_home_banners_images_post"></a>
## Body_upload_home_banner_image_api_v1_admin_home_banners_images_post

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `image` | string (binary) | 是 | format="binary" | — |

<a id="schema-body_upload_image_api_v1_community_upload_image_post"></a>
## Body_upload_image_api_v1_community_upload_image_post

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `image` | string (binary) | 是 | format="binary" | — |

<a id="schema-body_upload_material_api_v1_courses__course_id__materials_post"></a>
## Body_upload_material_api_v1_courses__course_id__materials_post

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |

<a id="schema-candidateannotationout"></a>
## CandidateAnnotationOut

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

CampusMate-LM 只读金丝雀注解。

三个必须成立的性质：

- **可识别**：`capability_name` / `model_key` / `prompt_version` / `inference_source`
  明确标出"这段文字来自候选模型"，绝不与确定性结果混为一谈。
- **可降级**：门禁未过、未配置、采样未命中、熔断、超时、非法 JSON、策略违规
  一律 `available=False` + 稳定 `reason`，生产响应继续使用确定性结果。
- **可追溯**：`shadow_run_id` + `input_digest` 指向影子表里的那一次观测。

`read_only` / `affects_production` 恒为 `True` / `False`：它是展示字段，
不参与任何状态、计划、任务或决策的写入。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `available` | boolean | 是 | — | 当前能力是否可用 |
| `capability_name` | string | 是 | — | — |
| `capability_version` | string | 是 | — | — |
| `reason` | string / null | 否 | — | 原因 |
| `inference_source` | string | 否 | default="DETERMINISTIC_FALLBACK" | — |
| `model_key` | string / null | 否 | — | — |
| `model_version` | string / null | 否 | — | — |
| `prompt_version` | string / null | 否 | — | — |
| `input_digest` | string / null | 否 | — | — |
| `shadow_run_id` | string / null | 否 | — | — |
| `used_fallback` | boolean | 否 | default=false | — |
| `claim_codes` | array<string> | 否 | — | — |
| `summary` | string / null | 否 | — | — |
| `read_only` | boolean | 否 | default=true | — |
| `affects_production` | boolean | 否 | default=false | — |

<a id="schema-changedforecastsummary"></a>
## ChangedForecastSummary

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `forecast_type` | string | 是 | — | — |
| `scope_type` | string | 是 | — | — |
| `scope_id` | string | 是 | — | — |
| `baseline_probability` | number / null | 否 | number约束: minimum=0.0; maximum=1.0 | — |
| `intervention_probability` | number / null | 否 | number约束: minimum=0.0; maximum=1.0 | — |
| `baseline_risk_band` | string / null | 否 | — | — |
| `intervention_risk_band` | string / null | 否 | — | — |
| `baseline_value` | object / null | 否 | — | — |
| `intervention_value` | object / null | 否 | — | — |
| `delta` | map<string, number> | 否 | additionalProperties={"type": "number"} | — |
| `direction` | enum ["increased", "decreased", "unchanged", "unknown"] | 是 | — | — |
| `magnitude` | number | 否 | default=0.0; minimum=-1.0; maximum=1.0 | — |
| `explanation_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-changedstateestimatesummary"></a>
## ChangedStateEstimateSummary

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `state_type` | string | 是 | — | — |
| `scope_type` | string | 是 | — | — |
| `scope_id` | string | 是 | — | — |
| `change_type` | enum ["updated", "added", "removed", "degraded"] | 是 | — | — |
| `baseline_value` | object / null | 否 | — | — |
| `intervention_value` | object / null | 否 | — | — |
| `baseline_data_quality` | enum ["verified", "partial", "stale", "unavailable"] / null | 否 | — | — |
| `intervention_data_quality` | enum ["verified", "partial", "stale", "unavailable"] / null | 否 | — | — |
| `explanation_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-chaoxingloginrequest"></a>
## ChaoxingLoginRequest

模型定义：[backend/app/schemas/chaoxing.py](../../backend/app/schemas/chaoxing.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | — | 登录用户名 |
| `password` | string | 是 | — | 登录密码，仅请求使用 |

<a id="schema-chaoxingsyncstatus"></a>
## ChaoxingSyncStatus

模型定义：[backend/app/schemas/chaoxing.py](../../backend/app/schemas/chaoxing.py)。

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

<a id="schema-chatfinalmeta"></a>
## ChatFinalMeta

模型定义：[backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)。

非流式响应 / SSE 最终事件携带的元数据。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `answer` | string | 是 | — | — |
| `sources` | array<[ChatSource](schemas.md#schema-chatsource)> | 否 | — | — |
| `confidence` | number | 否 | default=0.0; minimum=0.0; maximum=1.0 | — |
| `evidence_level` | string | 否 | default="low" | high\|medium\|low\|none |
| `needs_human_confirmation` | boolean | 否 | default=false | — |
| `suggested_actions` | array<[SuggestedAction](schemas.md#schema-suggestedaction)> | 否 | — | — |
| `conversation_id` | string | 是 | — | — |
| `mode` | string | 是 | — | llm\|retrieval_summary\|no_knowledge\|chat |
| `warnings` | array<string> | 否 | — | 警告列表；成功也需展示降级或缺失数据 |
| `context_used` | object | 否 | — | 实际采纳的上下文摘要。推荐字段: recent_tasks_count / recent_tasks_accepted_count / recent_tasks_ignored_count / self_report_present。不回传 self_report 原文,不回传 expression_signal 内容。 |
| `context_warnings` | array<string> | 否 | — | 上下文相关告警(越权/不存在/草稿/expression_signal 已忽略等) |

<a id="schema-chatrequest"></a>
## ChatRequest

模型定义：[backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)。

AI 导员聊天请求 — 统一上下文 API Schema。

前端必须在 JSON Body 中发送独立上下文字段,不得把上下文编码进 conversation_id。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | string | 是 | minLength=1 | 用户问题 |
| `conversation_id` | string / null | 否 | — | 会话 ID(仅作会话标识) |
| `workspace_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | 原生 magic class workspace 会话归属；必须与 course_id 一起提供并通过服务端归属校验 |
| `recent_tasks` | array<[CounselorRecentTask](schemas.md#schema-counselorrecenttask)> | 否 | — | 最近待办(仅 PersonalTask,id 为必填,其他字段为 hint),后端会通过 PersonalTaskRepository 校验归属,越权/不存在/已删除的条目会被忽略 |
| `stream` | boolean | 否 | default=true | 是否使用 SSE 流式响应 |
| `web_search` | boolean | 否 | default=false | 是否检索公开网页并将结果作为非官方辅助上下文 |
| `attachment` | [CounselorAttachment](schemas.md#schema-counselorattachment) / null | 否 | — | 本轮用户选择的文本附件；作为不可信上下文使用，不得覆盖系统规则 |
| `course_id` | string / null | 否 | — | 课程 ID(需有权限) |
| `class_id` | string / null | 否 | — | 班级 ID(需有权限) |
| `assignment_id` | string / null | 否 | — | 任务 ID(需有权限) |
| `announcement_id` | string / null | 否 | — | 通知 ID(需有权限) |
| `study_session_id` | string / null | 否 | — | 当前学习会话 ID(可选,用于学习陪伴场景) |
| `self_report` | string / null | 否 | string约束: maxLength=500 | 用户自报状态(如'有些疲惫'),仅作个性化参考,不得作为校园规则事实,不得绕过 RAG 拒答规则 |
| `expression_signal` | [ExpressionSignal](schemas.md#schema-expressionsignal) / null | 否 | — | CNN 观察到的可见表情信号。后端会白名单校验并仅用于调整措辞，不用于心理或医学判断，不保存原始图像 |

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator('self_report', mode='before')
@classmethod
def _normalize_self_report(cls, v: Any) -> Optional[str]:
    """self_report 后端 Schema 必须满足:
        - Optional
        - 最大 500 字(由 max_length 强制,Pydantic 在 strip 前校验长度,
          故客户端应在发送前自行 trim;此处再 strip 一次以保证存储一致)
        - strip 首尾空白
        - 空字符串转换为 null
        """
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError('self_report 必须是字符串')
    s = v.strip()
    if not s:
        return None
    return s
```

<a id="schema-chatsource"></a>
## ChatSource

模型定义：[backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)。

知识库引用来源(对齐移动端 KnowledgeSource + 扩展字段)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `document_id` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `section` | string / null | 否 | default=null | — |
| `source_department` | string / null | 否 | default=null | — |
| `published_at` | string (date-time) / null | 否 | default=null; string约束: format="date-time" | — |
| `version` | string / null | 否 | default=null | — |
| `applicable_students` | string / null | 否 | default=null | — |
| `excerpt` | string | 是 | — | 引用片段(已截断) |
| `relevance_score` | number | 否 | default=0.0; minimum=0.0; maximum=1.0 | — |
| `is_official` | boolean | 否 | default=false | — |
| `is_expired` | boolean | 否 | default=false | — |
| `is_demo` | boolean | 否 | default=false | — |

<a id="schema-classjoinrequest"></a>
## ClassJoinRequest

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `invite_code` | string | 是 | minLength=1; maxLength=32 | — |

<a id="schema-classmemberout"></a>
## ClassMemberOut

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | string | 是 | — | 所属用户标识 |
| `username` | string | 是 | — | 登录用户名 |
| `display_name` | string / null | 否 | default=null | — |
| `student_number` | string / null | 否 | default=null | — |
| `teacher_number` | string / null | 否 | default=null | — |
| `college` | string / null | 否 | default=null | — |
| `major` | string / null | 否 | default=null | — |
| `grade` | string / null | 否 | default=null | — |
| `avatar_url` | string / null | 否 | default=null | — |
| `role` | string | 是 | — | — |
| `enrollment_id` | string | 是 | — | — |
| `member_role` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `joined_at` | string | 是 | — | — |

<a id="schema-classout"></a>
## ClassOut

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `class_code` | string / null | 否 | — | — |
| `invite_code` | string | 是 | — | — |
| `description` | string / null | 否 | — | 说明 |
| `capacity` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

<a id="schema-commentcreate"></a>
## CommentCreate

模型定义：[backend/app/schemas/community.py](../../backend/app/schemas/community.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | minLength=1; maxLength=2000 | 正文或业务内容，嵌套结构按类型 |
| `parent_comment_id` | string / null | 否 | — | — |
| `is_anonymous` | boolean | 否 | default=false | — |

<a id="schema-completeitemin"></a>
## CompleteItemIn

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `difficulty` | string / null | 否 | string约束: pattern="^(easy\|medium\|hard)$" | — |
| `feedback` | string / null | 否 | string约束: maxLength=500 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-completeitemout"></a>
## CompleteItemOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `item_id` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `completed_at` | string | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-correctioncreate"></a>
## CorrectionCreate

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

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

<a id="schema-correctionout"></a>
## CorrectionOut

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

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

<a id="schema-correctionpage"></a>
## CorrectionPage

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[CorrectionOut](schemas.md#schema-correctionout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

<a id="schema-correctionrevokerequest"></a>
## CorrectionRevokeRequest

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string | 是 | minLength=1; maxLength=128 | 幂等键 |

<a id="schema-counselorattachment"></a>
## CounselorAttachment

模型定义：[backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)。

Small text attachment supplied by the user for one assistant turn.

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=160 | 名称 |
| `type` | string | 否 | default="text/plain"; maxLength=80 | — |
| `size` | integer | 否 | default=0; minimum=0.0; maximum=1000000.0 | — |
| `content` | string | 是 | minLength=1; maxLength=20000 | 正文或业务内容，嵌套结构按类型 |

<a id="schema-counselorrecenttask"></a>
## CounselorRecentTask

模型定义：[backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)。

AI 导员上下文中的"最近待办"条目 — 仅表示 PersonalTask。

重要(对齐用户要求):
- recent_tasks 现在只表示 PersonalTask(用户个人待办),不表示 Assignment。
- 教师作业只能通过 assignment_id 传递。
- 客户端传入的 title/deadline/priority/status 一律视为 hint,
  后端不得作为事实使用;后端必须通过 PersonalTaskRepository 重新查询,
  使用数据库权威字段覆盖。
- 未登录用户: 全部忽略 + warning。
- 已登录用户: 后端按 user_id 查询;不存在 / 越权 / 已软删除的任务不得进入上下文。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | minLength=1 | PersonalTask ID |
| `title` | string / null | 否 | — | 客户端 hint,后端不信任,仅作 debug 用途 |
| `deadline` | string / null | 否 | — | 客户端 hint,后端不信任 |
| `priority` | string / null | 否 | — | 客户端 hint,后端不信任 |
| `status` | string / null | 否 | — | 客户端 hint,后端不信任 |

<a id="schema-coursecontentitemout"></a>
## CourseContentItemOut

模型定义：[backend/app/schemas/course_content.py](../../backend/app/schemas/course_content.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `external_id` | string | 是 | — | — |
| `kind` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `parent_external_id` | string / null | 否 | — | — |
| `description` | string / null | 否 | — | 说明 |
| `author_name` | string / null | 否 | — | — |
| `position` | integer | 否 | default=0 | — |
| `depth` | integer | 否 | default=0 | — |
| `status` | string | 否 | default="unknown" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `starts_at` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `published_at` | string / null | 否 | — | — |
| `mime_type` | string / null | 否 | — | 媒体类型 |
| `file_size` | integer / null | 否 | — | — |
| `cached` | boolean | 否 | default=false | — |
| `can_download` | boolean | 否 | default=false | — |
| `can_open` | boolean | 否 | default=true | — |
| `metadata` | object / null | 否 | — | — |

<a id="schema-coursecontentpage"></a>
## CourseContentPage

模型定义：[backend/app/schemas/course_content.py](../../backend/app/schemas/course_content.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[CourseContentItemOut](schemas.md#schema-coursecontentitemout)> | 否 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

<a id="schema-coursecontentsummaryout"></a>
## CourseContentSummaryOut

模型定义：[backend/app/schemas/course_content.py](../../backend/app/schemas/course_content.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | — | 关联课程标识 |
| `provider` | string / null | 否 | — | — |
| `cover_url` | string / null | 否 | — | — |
| `teacher_name` | string / null | 否 | — | — |
| `school_name` | string / null | 否 | — | — |
| `class_name` | string / null | 否 | — | — |
| `student_count` | integer / null | 否 | — | — |
| `starts_at` | string / null | 否 | — | — |
| `ends_at` | string / null | 否 | — | — |
| `last_synced_at` | string / null | 否 | — | — |
| `sections` | array<[CourseSectionStatusOut](schemas.md#schema-coursesectionstatusout)> | 否 | — | — |

<a id="schema-coursecontextout"></a>
## CourseContextOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

一门课在生成前可用的真实事实。

这个响应的唯一用途是让界面**如实**说明"这次能拿什么去生成"，所以它刻意
把"没同步"与"没读到"拆成两个字段：`synced=False` 且 `warnings` 为空，才
表示这门课确实还没有资料，下一步是去做同步；`warnings` 非空表示这次读不到，
下一步是重试。合并成一个布尔值会让界面无法给出正确的下一步。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `code` | string | 否 | default="" | — |
| `semester` | string | 否 | default="" | — |
| `description` | string | 否 | default="" | 说明 |
| `knowledge_points` | array<[CourseKnowledgePointOut](schemas.md#schema-courseknowledgepointout)> | 否 | — | — |
| `chapters` | array<string> | 否 | — | — |
| `materials` | array<map<string, string>> | 否 | — | — |
| `sources` | map<string, string> | 否 | additionalProperties={"type": "string"} | — |
| `warnings` | array<string> | 否 | — | 警告列表；成功也需展示降级或缺失数据 |
| `synced` | boolean | 否 | default=false | — |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

<a id="schema-coursecreate"></a>
## CourseCreate

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=128 | 名称 |
| `code` | string / null | 否 | string约束: maxLength=64 | — |
| `semester` | string / null | 否 | string约束: maxLength=32 | — |
| `description` | string / null | 否 | string约束: maxLength=2000 | 说明 |
| `status` | string | 否 | default="draft"; pattern="^(draft\|active\|archived)$" | 业务状态，合法取值和操作前置条件见枚举及流程 |

<a id="schema-courseknowledgepointout"></a>
## CourseKnowledgePointOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

生成前展示的一个知识点。只有名字，没有掌握率——掌握率属于课程图谱页。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | — | 名称 |

<a id="schema-courseout"></a>
## CourseOut

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `name` | string | 是 | — | 名称 |
| `code` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `description` | string / null | 否 | — | 说明 |
| `teacher_id` | string / null | 否 | — | — |
| `teacher_name` | string / null | 否 | — | — |
| `provider` | string / null | 否 | — | — |
| `external_id` | string / null | 否 | — | — |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `owner_user_id` | string / null | 否 | — | — |

<a id="schema-courseparticipationvalue"></a>
## CourseParticipationValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_chapters_completed` | integer | 是 | minimum=0.0 | — |
| `observed_assignments_discovered` | integer | 是 | minimum=0.0 | — |
| `observed_assignments_completed` | integer | 是 | minimum=0.0 | — |
| `last_observed_course_activity_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `evidence_quality` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-courseresearchartifactlistout"></a>
## CourseResearchArtifactListOut

模型定义：[backend/app/schemas/course_research.py](../../backend/app/schemas/course_research.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `artifacts` | array<[CourseResearchArtifactOut](schemas.md#schema-courseresearchartifactout)> | 否 | — | — |
| `sources` | array<[ResearchSourceOut](schemas.md#schema-researchsourceout)> | 否 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-courseresearchartifactout"></a>
## CourseResearchArtifactOut

模型定义：[backend/app/schemas/course_research.py](../../backend/app/schemas/course_research.py)。

研究报告产物。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `artifact_id` | string | 是 | minLength=1; maxLength=64 | — |
| `run_id` | string | 是 | minLength=1; maxLength=64 | 运行标识 |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `artifact_type` | string | 是 | maxLength=64 | — |
| `version` | integer | 是 | minimum=1.0 | — |
| `mime_type` | string | 是 | maxLength=64 | 媒体类型 |
| `size_bytes` | integer | 是 | minimum=0.0 | — |
| `content_hash` | string | 是 | minLength=8; maxLength=128 | — |
| `download_url` | string / null | 否 | string约束: maxLength=512 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `content` | string / null | 否 | — | 正文或业务内容，嵌套结构按类型 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-courseresearchruncancelin"></a>
## CourseResearchRunCancelIn

模型定义：[backend/app/schemas/course_research.py](../../backend/app/schemas/course_research.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-courseresearchruncreatein"></a>
## CourseResearchRunCreateIn

模型定义：[backend/app/schemas/course_research.py](../../backend/app/schemas/course_research.py)。

POST /api/v1/course-research/runs 请求体。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string / null | 否 | string约束: maxLength=64 | 关联课程标识 |
| `question` | string | 是 | minLength=1; maxLength=2000 | — |
| `assistance_mode` | [AssistanceMode](schemas.md#schema-assistancemode) | 否 | default="EXPLAIN" | — |
| `academic_policy` | [AcademicPolicy](schemas.md#schema-academicpolicy) | 否 | default="UNKNOWN" | — |
| `source_policy` | [SourcePolicyIn](schemas.md#schema-sourcepolicyin) | 否 | — | — |
| `user_upload_refs` | array<string> | 否 | — | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-courseresearchrunout"></a>
## CourseResearchRunOut

模型定义：[backend/app/schemas/course_research.py](../../backend/app/schemas/course_research.py)。

课程研究 Run 概览。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-coursesectionstatusout"></a>
## CourseSectionStatusOut

模型定义：[backend/app/schemas/course_content.py](../../backend/app/schemas/course_content.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `section` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `item_count` | integer | 是 | — | — |
| `last_synced_at` | string | 是 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |

<a id="schema-courseupdate"></a>
## CourseUpdate

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=128 | 名称 |
| `code` | string / null | 否 | string约束: maxLength=64 | — |
| `semester` | string / null | 否 | string约束: maxLength=32 | — |
| `description` | string / null | 否 | string约束: maxLength=2000 | 说明 |
| `status` | string / null | 否 | string约束: pattern="^(draft\|active\|archived)$" | 业务状态，合法取值和操作前置条件见枚举及流程 |

<a id="schema-creditprogressvalue"></a>
## CreditProgressValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_credits` | number | 是 | minimum=0.0 | — |
| `current_semester_credits` | number | 是 | minimum=0.0 | — |
| `total_required_credits` | number / null | 否 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-dailyagendaout"></a>
## DailyAgendaOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `agenda_id` | string | 是 | — | — |
| `campaign_id` | string | 是 | — | — |
| `plan_version` | integer | 是 | — | — |
| `agenda_date` | string | 是 | — | — |
| `total_minutes` | integer | 是 | — | — |
| `items` | array<[DailyItemOut](schemas.md#schema-dailyitemout)> | 是 | — | 列表条目 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-dailycheckinin"></a>
## DailyCheckinIn

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

每日签到/晚间反馈。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `report_date` | string | 是 | minLength=1; maxLength=32 | — |
| `completed_item_ids` | array<string> | 否 | — | — |
| `insufficient_time` | boolean | 否 | default=false | — |
| `difficulty_notes` | string / null | 否 | string约束: maxLength=500 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-dailycheckinout"></a>
## DailyCheckinOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `recorded` | boolean | 是 | — | — |
| `evidence_count` | integer | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-dailyitemout"></a>
## DailyItemOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `item_id` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `course_name` | string / null | 否 | — | — |
| `scheduled_minutes` | integer | 是 | — | — |
| `sort_order` | integer | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `personal_task_id` | string / null | 否 | — | — |
| `difficulty` | string / null | 否 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-datamanagementresponse"></a>
## DataManagementResponse

模型定义：[backend/app/schemas/knowledge.py](../../backend/app/schemas/knowledge.py)。

数据清理操作响应。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | 是 | — | — |
| `action` | string | 是 | — | 执行的清理动作 |
| `affected_count` | integer | 否 | default=0 | — |
| `message` | string | 是 | — | — |

<a id="schema-datasourcecontrollist"></a>
## DataSourceControlList

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[DataSourceControlOut](schemas.md#schema-datasourcecontrolout)> | 是 | — | 列表条目 |

<a id="schema-datasourcecontrolout"></a>
## DataSourceControlOut

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `source_key` | enum ["CORE_STUDY", "PERSONAL_TASK", "CHAOXING", "EDU", "MODEL_SHADOW", "PROACTIVE_SUGGESTIONS"] | 是 | — | — |
| `status` | enum ["ENABLED", "PAUSED", "DISCONNECTED", "DELETE_REQUESTED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `updated_at` | string (date-time) | 是 | format="date-time" | 最近更新时间 |
| `can_pause` | boolean | 否 | default=true | — |
| `can_resume` | boolean | 否 | default=true | — |

<a id="schema-datasourcecontrolupdate"></a>
## DataSourceControlUpdate

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | enum ["ENABLED", "PAUSED"] | 是 | — | 新状态 |
| `idempotency_key` | string | 是 | minLength=1; maxLength=128 | 幂等键 |

<a id="schema-datasourcehealthvalue"></a>
## DataSourceHealthValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | enum ["FRESH", "PARTIAL", "STALE", "UNAVAILABLE"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `last_successful_observation_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `valid_until` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@model_validator(mode='after')
def require_observation_for_stale(self) -> 'DataSourceHealthValue':
    if self.status == 'STALE' and self.last_successful_observation_at is None:
        raise ValueError('stale source health requires an observation time')
    if self.status == 'FRESH' and self.last_successful_observation_at is None:
        raise ValueError('fresh source health requires an observation time')
    return self
```

<a id="schema-datasummaryout"></a>
## DataSummaryOut

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

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

<a id="schema-deadlinecompletionriskvalue"></a>
## DeadlineCompletionRiskValue

模型定义：[backend/app/schemas/forecast.py](../../backend/app/schemas/forecast.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `pending_task_count` | integer | 是 | minimum=0.0 | — |
| `overdue_task_count` | integer | 是 | minimum=0.0 | — |
| `tasks_within_horizon` | integer | 是 | minimum=0.0 | — |
| `risk_band` | enum ["LOW", "MODERATE", "HIGH", "VERY_HIGH"] | 是 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-deadlineexposurevalue"></a>
## DeadlineExposureValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `bucket` | enum ["OVERDUE", "DUE_24H", "DUE_7D", "LATER", "NO_DEADLINE", "UNKNOWN"] | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-deletecountsummary"></a>
## DeleteCountSummary

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

表意类别计数，不暴露内部表名。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `projection_runs` | integer | 否 | default=0 | — |
| `snapshots` | integer | 否 | default=0 | — |
| `evidence` | integer | 否 | default=0 | — |
| `learner_events` | integer | 否 | default=0 | — |
| `corrections` | integer | 否 | default=0 | — |
| `learning_plans` | integer | 否 | default=0 | — |
| `plan_items` | integer | 否 | default=0 | — |
| `plan_feedback` | integer | 否 | default=0 | — |
| `plan_evaluations` | integer | 否 | default=0 | — |
| `shadow_runs` | integer | 否 | default=0 | — |

<a id="schema-deleterequestcreate"></a>
## DeleteRequestCreate

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `scope` | enum ["STATE_ONLY", "EVENTS_AND_STATE", "KNOWLEDGE_ONLY", "PLANS_ONLY", "MODEL_SHADOW_ONLY", "ALL_LEARNER_MODEL_DATA"] | 是 | — | 删除范围 |
| `idempotency_key` | string | 是 | minLength=1; maxLength=128 | 幂等键 |

<a id="schema-deleterequestout"></a>
## DeleteRequestOut

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `request_id` | string | 是 | — | — |
| `scope` | enum ["STATE_ONLY", "EVENTS_AND_STATE", "KNOWLEDGE_ONLY", "PLANS_ONLY", "MODEL_SHADOW_ONLY", "ALL_LEARNER_MODEL_DATA"] | 是 | — | — |
| `status` | enum ["COMPLETED", "IN_PROGRESS", "FAILED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `before_counts` | [DeleteCountSummary](schemas.md#schema-deletecountsummary) | 是 | — | — |
| `after_counts` | [DeleteCountSummary](schemas.md#schema-deletecountsummary) | 是 | — | — |
| `created_at` | string (date-time) | 是 | format="date-time" | 创建时间 |
| `completed_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |

<a id="schema-deleteresponse"></a>
## DeleteResponse

模型定义：[backend/app/schemas/knowledge.py](../../backend/app/schemas/knowledge.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | 是 | — | — |
| `document_id` | string | 是 | — | — |

<a id="schema-deletestatusout"></a>
## DeleteStatusOut

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `latest` | [DeleteRequestOut](schemas.md#schema-deleterequestout) / null | 否 | — | — |
| `history` | array<[DeleteRequestOut](schemas.md#schema-deleterequestout)> | 否 | default=[] | — |

<a id="schema-discussionin"></a>
## DiscussionIn

模型定义：[backend/app/api/routes/magicclass_discussion.py](../../backend/app/api/routes/magicclass_discussion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `prompt` | string | 是 | minLength=1; maxLength=4000 | — |

<a id="schema-documentsummary"></a>
## DocumentSummary

模型定义：[backend/app/schemas/knowledge.py](../../backend/app/schemas/knowledge.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `document_id` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `source_department` | string / null | 否 | — | — |
| `source_type` | string / null | 否 | — | — |
| `original_filename` | string / null | 否 | — | — |
| `content_hash` | string | 是 | — | — |
| `published_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `updated_at` | string (date-time) / null | 否 | string约束: format="date-time" | 最近更新时间 |
| `effective_from` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `effective_to` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `version` | string / null | 否 | — | — |
| `applicable_students` | string / null | 否 | — | — |
| `is_official` | boolean | 是 | — | — |
| `is_expired` | boolean | 是 | — | — |
| `is_demo` | boolean | 否 | default=false | — |
| `file_size` | integer / null | 否 | — | — |
| `file_ext` | string / null | 否 | — | — |
| `imported_at` | string (date-time) | 是 | format="date-time" | — |

<a id="schema-duplicatenoticecheckrequest"></a>
## DuplicateNoticeCheckRequest

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

重复通知检测请求。

服务端无状态,客户端应将本地已保存的通知列表作为 recent_notices 传入。
若 recent_notices 为空,则返回 is_duplicate=false(无对比基准)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | — | 通知原文 |
| `source_name` | string / null | 否 | — | 来源名称 |
| `task_name` | string / null | 否 | — | 已抽取的任务名(可选) |
| `deadline` | string (date-time) / null | 否 | string约束: format="date-time" | 已抽取的截止时间(可选) |
| `recent_notices` | array<[RecentNoticeItem](schemas.md#schema-recentnoticeitem)> | 否 | — | 客户端本地已保存的通知列表(用于服务端对比) |

对象级约束：

```json
{
  "example": {
    "content": "请2024级学生于7月30日前提交实践申请表...",
    "recent_notices": [
      {
        "deadline": "2026-07-30T23:59:00+08:00",
        "notice_id": "task_001",
        "source_name": "信息工程学院通知",
        "source_text": "请2024级学生于7月30日前提交实践申请表...",
        "title": "提交实践申请表"
      }
    ],
    "source_name": "信息工程学院通知",
    "task_name": "提交实践申请表"
  }
}
```

<a id="schema-duplicatenoticecheckresponse"></a>
## DuplicateNoticeCheckResponse

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `is_duplicate` | boolean | 是 | — | 是否可能重复 |
| `matches` | array<[DuplicateNoticeMatch](schemas.md#schema-duplicatenoticematch)> | 否 | — | — |
| `content_hash` | string | 是 | — | 当前通知的内容哈希(SHA256) |
| `note` | string | 否 | default="仅提示可能重复,不会自动覆盖原待办。请人工确认后决定是否继续保存。" | 说明文案 |

<a id="schema-duplicatenoticematch"></a>
## DuplicateNoticeMatch

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

重复检测命中的已存在通知项。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `notice_id` | string | 是 | — | 已存在通知 ID |
| `title` | string | 是 | — | 已存在通知标题 |
| `source_name` | string / null | 否 | — | — |
| `deadline` | string (date-time) / null | 否 | string约束: format="date-time" | 截止时间 |
| `similarity` | number | 是 | minimum=0.0; maximum=1.0 | 相似度 0~1 |
| `reasons` | array<string> | 否 | — | 判定为重复的原因(content_hash/source_name/task/deadline) |

<a id="schema-durationstats"></a>
## DurationStats

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `p50` | number / null | 否 | number约束: minimum=0.0 | — |
| `p95` | number / null | 否 | number约束: minimum=0.0 | — |
| `samples` | integer | 否 | default=0; minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-edubindrequest"></a>
## EduBindRequest

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

学生绑定教务账号。

username/password 仅用于一次认证，不会明文存储；
认证成功后由 SessionManager 保存 session，credential_ref 引用安全存储。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=1; maxLength=128 | 登录用户名 |
| `password` | string (password) | 是 | format="password"; writeOnly=true | 登录密码，仅请求使用 |
| `system_type` | string | 否 | default="undergrad" | undergrad / postgrad |

<a id="schema-edubindingout"></a>
## EduBindingOut

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

edu_bindings 出参（不含凭证）。

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

<a id="schema-educonnectioncontinue"></a>
## EduConnectionContinue

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

推进连接状态请求。

支持两种登录路径：
1. backend_http: username + password（后端代理登录）
2. client_webview: cookies + current_url + user_agent（客户端 WebView 登录完成后回传）

action 可选值：
- CLIENT_WEBVIEW_COMPLETE: 客户端 WebView 登录完成，回传 cookies
- POLL: 客户端轮询当前状态（不推进）
- CANCEL: 取消连接
- SUBMIT_WITH_CAPTCHA: 携带验证码提交登录（需配合 pre_login_token + captcha）

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

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator('user_agent')
@classmethod
def validate_user_agent(cls, value: Optional[str]) -> Optional[str]:
    if value is not None and _has_control_characters(value):
        raise ValueError('user_agent contains control characters')
    return value
```

```python
@field_validator('cookies')
@classmethod
def validate_legacy_cookies(cls, value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    if value is None:
        return None
    if len(value) > 64:
        raise ValueError('too many cookies')
    for name, cookie_value in value.items():
        EduCookie(name=name, value=cookie_value)
    return value
```

<a id="schema-educonnectioncreate"></a>
## EduConnectionCreate

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

创建连接请求。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `edu_system_id` | string | 是 | minLength=1; maxLength=128 | — |

<a id="schema-educonnectionfromurlrequest"></a>
## EduConnectionFromUrlRequest

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

从教务系统 URL 创建连接（便捷流程，不需预先 edu_system_id）。

university_id 可选；若未提供则使用当前用户的 university_id。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `portal_url` | string | 是 | minLength=1; maxLength=512 | — |
| `university_id` | string / null | 否 | — | — |

<a id="schema-educonnectionout"></a>
## EduConnectionOut

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

edu_connections 出参。

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

<a id="schema-educookie"></a>
## EduCookie

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

A scoped browser cookie without pretending unavailable attributes are known.

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=256 | 名称 |
| `value` | string | 是 | maxLength=4096 | — |
| `domain` | string / null | 否 | string约束: maxLength=253 | — |
| `source_url` | string / null | 否 | string约束: maxLength=2048 | 来源链接 |
| `host_only` | boolean / null | 否 | — | — |
| `path` | string / null | 否 | string约束: maxLength=1024 | — |
| `secure` | boolean / null | 否 | — | — |
| `http_only` | boolean / null | 否 | — | — |
| `same_site` | enum ["Lax", "Strict", "None"] / null | 否 | — | — |
| `expires` | integer / null | 否 | integer约束: minimum=0.0; maximum=253402300799.0 | — |

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator('name')
@classmethod
def validate_name(cls, value: str) -> str:
    if any((char in value for char in '()<>@,;:\\"/[]?={} \t')) or _has_control_characters(value):
        raise ValueError('cookie name contains invalid characters')
    return value
```

```python
@field_validator('value')
@classmethod
def validate_value(cls, value: str) -> str:
    if _has_control_characters(value) or any((char in value for char in ';,\\"')):
        raise ValueError('cookie value contains control characters')
    return value
```

```python
@field_validator('domain')
@classmethod
def validate_domain(cls, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.lower().lstrip('.')
    if not normalized or '/' in normalized or _has_control_characters(normalized) or (not re.fullmatch('[a-z0-9.-]+', normalized)):
        raise ValueError('cookie domain is invalid')
    return normalized
```

```python
@field_validator('path')
@classmethod
def validate_path(cls, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not value.startswith('/') or '?' in value or '#' in value or _has_control_characters(value):
        raise ValueError('cookie path is invalid')
    return value
```

```python
@field_validator('source_url')
@classmethod
def validate_source_url(cls, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or _has_control_characters(value):
        raise ValueError('cookie source_url must be an https URL without userinfo')
    return value
```

<a id="schema-edudetectresult"></a>
## EduDetectResult

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

SystemDetector 探测结果。

根据学校信息识别教务厂商与系统类型，但不编造 URL。
confidence 为 0.0~1.0 的浮点数，evidence 标注探测依据。

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

<a id="schema-edudiscoverycandidateout"></a>
## EduDiscoveryCandidateOut

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

候选数据库条目出参（管理后台用）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `school_code` | string | 是 | — | 学校代码 |
| `school_name` | string | 是 | — | — |
| `candidate_url` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `source_type` | string | 是 | — | — |
| `source_url` | string / null | 否 | — | 来源链接 |
| `confidence` | number | 否 | default=0.0 | — |
| `verification_status` | string | 是 | — | — |
| `http_status` | integer / null | 否 | — | — |
| `final_url` | string / null | 否 | — | — |
| `title` | string / null | 否 | — | 标题 |
| `evidence` | array<object> | 否 | — | — |
| `last_checked_at` | string / null | 否 | — | — |
| `province` | string / null | 否 | — | — |
| `level` | string / null | 否 | — | — |
| `official_domain` | string / null | 否 | — | — |
| `wakeup_supported` | boolean | 否 | default=false | — |
| `wakeup_source_date` | string / null | 否 | — | — |
| `discovered_at` | string / null | 否 | — | — |
| `reason` | string / null | 否 | — | 原因 |
| `review_action` | string / null | 否 | — | — |

<a id="schema-edudiscoveryreviewrequest"></a>
## EduDiscoveryReviewRequest

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

管理后台审核操作。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `action` | string | 是 | — | confirm\|reject\|mark_historical\|mark_intranet\|reverify |

<a id="schema-edudiscoverystatsout"></a>
## EduDiscoveryStatsOut

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

发现统计。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `universities_total` | integer | 否 | default=0 | — |
| `candidates_total` | integer | 否 | default=0 | — |
| `by_status` | object | 否 | — | — |
| `by_provider` | object | 否 | — | — |
| `wakeup_supported` | integer | 否 | default=0 | — |
| `verified_official` | integer | 否 | default=0 | — |
| `verified_live` | integer | 否 | default=0 | — |
| `candidate` | integer | 否 | default=0 | — |
| `not_discovered` | integer | 否 | default=0 | — |
| `dead` | integer | 否 | default=0 | — |

<a id="schema-edudiscoverysubmiturlrequest"></a>
## EduDiscoverySubmitUrlRequest

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

用户手动提交教务系统 URL。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string | 是 | — | — |
| `candidate_url` | string | 是 | minLength=1; maxLength=512 | — |

<a id="schema-edudiscoverysubmiturlresult"></a>
## EduDiscoverySubmitUrlResult

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

用户提交 URL 后的检测结果。

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

<a id="schema-eduexam"></a>
## EduExam

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

考试安排（归一化后）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `semester` | string / null | 否 | — | — |
| `items` | array<[EduExamItem](schemas.md#schema-eduexamitem)> | 否 | — | 列表条目 |

<a id="schema-eduexamitem"></a>
## EduExamItem

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

考试单条。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_name` | string / null | 否 | — | — |
| `course_code` | string / null | 否 | — | — |
| `exam_type` | string / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `seat` | string / null | 否 | — | — |
| `starts_at` | string / null | 否 | — | — |
| `ends_at` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `notes` | string / null | 否 | — | — |

<a id="schema-edugrade"></a>
## EduGrade

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

成绩（归一化后）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `semester` | string / null | 否 | — | — |
| `gpa` | number / null | 否 | — | — |
| `items` | array<[EduGradeItem](schemas.md#schema-edugradeitem)> | 否 | — | 列表条目 |

<a id="schema-edugradeitem"></a>
## EduGradeItem

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

成绩单条。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_name` | string / null | 否 | — | — |
| `course_code` | string / null | 否 | — | — |
| `credit` | number / null | 否 | — | — |
| `score` | string / null | 否 | — | — |
| `grade_point` | number / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `category` | string / null | 否 | — | — |
| `status` | string / null | 否 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |

<a id="schema-edupreloginresult"></a>
## EduPreLoginResult

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

预登录结果（获取验证码图片等预登录数据）。

流程：
1. 客户端调用 pre-login，后端 GET 登录页并提取验证码图片
2. 后端将 cookie + csrftoken 绑定到 pre_login_token，返回图片 base64
3. 客户端展示图片，用户输入验证码
4. 客户端调用 continue(action=SUBMIT_WITH_CAPTCHA, pre_login_token, username, password, captcha)
5. 后端复用预登录 cookie + csrftoken + 验证码完成登录 POST

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

<a id="schema-eduproberequest"></a>
## EduProbeRequest

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

教务系统 URL 探测请求（不需要 university_id）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `portal_url` | string | 是 | minLength=1; maxLength=512 | — |

<a id="schema-eduproberesult"></a>
## EduProbeResult

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

教务系统 URL 探测结果。

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

<a id="schema-eduprofile"></a>
## EduProfile

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

学生基本信息（归一化后）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `external_student_id` | string / null | 否 | — | — |
| `name` | string / null | 否 | — | 名称 |
| `gender` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `class_name` | string / null | 否 | — | — |
| `enrollment_year` | string / null | 否 | — | — |
| `schooling_length` | string / null | 否 | — | — |

<a id="schema-eduschedule"></a>
## EduSchedule

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

课表（归一化后）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `semester` | string / null | 否 | — | — |
| `items` | array<[EduScheduleItem](schemas.md#schema-eduscheduleitem)> | 否 | — | 列表条目 |

<a id="schema-eduscheduleitem"></a>
## EduScheduleItem

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

课表单条。

字段策略：教务系统能提供多少有效信息就保存多少。
所有字段可选 nullable，不同学校差异由 DataNormalizer 归一化。
extra_info 保存标准模型未覆盖但对用户有意义的业务字段（已脱敏）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_name` | string / null | 否 | — | — |
| `course_code` | string / null | 否 | — | — |
| `teacher` | string / null | 否 | — | — |
| `teachers` | array<string> / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `campus` | string / null | 否 | — | — |
| `building` | string / null | 否 | — | — |
| `classroom` | string / null | 否 | — | — |
| `weekday` | integer / null | 否 | integer约束: minimum=1.0; maximum=7.0 | — |
| `start_section` | integer / null | 否 | — | — |
| `end_section` | integer / null | 否 | — | — |
| `start_time` | string / null | 否 | — | — |
| `end_time` | string / null | 否 | — | — |
| `weeks` | string / null | 否 | — | — |
| `week_text` | string / null | 否 | — | — |
| `credit` | number / null | 否 | — | — |
| `course_nature` | string / null | 否 | — | — |
| `course_category` | string / null | 否 | — | — |
| `course_type` | string / null | 否 | — | — |
| `teaching_class` | string / null | 否 | — | — |
| `class_name` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `department` | string / null | 否 | — | — |
| `assessment_method` | string / null | 否 | — | — |
| `exam_type` | string / null | 否 | — | — |
| `total_hours` | number / null | 否 | — | — |
| `theory_hours` | number / null | 否 | — | — |
| `practice_hours` | number / null | 否 | — | — |
| `language` | string / null | 否 | — | — |
| `note` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `semester_id` | string / null | 否 | — | — |
| `extra_info` | object / null | 否 | — | — |

<a id="schema-edusyncrecordout"></a>
## EduSyncRecordOut

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `binding_id` | string | 是 | — | — |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 是 | — | — |
| `error_message` | string / null | 否 | — | — |
| `started_at` | string | 是 | — | — |
| `finished_at` | string / null | 否 | — | — |

<a id="schema-edusyncresult"></a>
## EduSyncResult

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

同步操作结果。

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

<a id="schema-edusystemconfigout"></a>
## EduSystemConfigOut

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

edu_system_configs 出参。

所有 URL 字段都附带 url_status，明确标注是 verified / unverified / not_discovered，
严禁编造 URL。

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

<a id="schema-edusystemconfigupsert"></a>
## EduSystemConfigUpsert

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

管理员 upsert edu_system_configs 入参。

university_id 必填，其余字段可选；未提供的字段保持原值。
严禁编造 URL：若不确定，应留空并将对应 url_status 设为 not_discovered。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string | 是 | minLength=1; maxLength=128 | — |
| `provider` | string / null | 否 | — | — |
| `system_type` | string / null | 否 | — | — |
| `academic_system_url` | string / null | 否 | — | — |
| `academic_system_url_status` | string / null | 否 | — | — |
| `undergrad_system_url` | string / null | 否 | — | — |
| `undergrad_system_url_status` | string / null | 否 | — | — |
| `postgrad_system_url` | string / null | 否 | — | — |
| `postgrad_system_url_status` | string / null | 否 | — | — |
| `sso_url` | string / null | 否 | — | — |
| `sso_url_status` | string / null | 否 | — | — |
| `cas_url` | string / null | 否 | — | — |
| `cas_url_status` | string / null | 否 | — | — |
| `webvpn_url` | string / null | 否 | — | — |
| `webvpn_url_status` | string / null | 否 | — | — |
| `login_method` | string / null | 否 | — | — |
| `captcha_type` | string / null | 否 | — | — |
| `requires_campus_network` | boolean / null | 否 | — | — |
| `supported_features` | array<string> / null | 否 | — | — |
| `school_code` | string / null | 否 | — | 学校代码 |
| `notes` | string / null | 否 | — | — |
| `data_source` | string / null | 否 | — | — |

<a id="schema-edusystemout"></a>
## EduSystemOut

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

edu_systems 出参（1:N）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `university_id` | string | 是 | — | — |
| `system_key` | string | 是 | — | — |
| `school_code` | string / null | 否 | — | 学校代码 |
| `name` | string / null | 否 | — | 名称 |
| `system_type` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `provider_version` | string / null | 否 | — | — |
| `base_url` | string / null | 否 | — | — |
| `login_url` | string / null | 否 | — | — |
| `sso_url` | string / null | 否 | — | — |
| `vpn_url` | string / null | 否 | — | — |
| `auth_type` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `captcha_type` | string | 是 | — | — |
| `requires_campus_network` | boolean | 否 | default=false | — |
| `requires_vpn` | boolean | 否 | default=false | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `verification_status` | string | 是 | — | — |
| `supported_features` | array<string> | 否 | — | — |
| `last_verified_at` | string / null | 否 | — | — |
| `source` | string | 是 | — | 来源 |
| `notes` | string / null | 否 | — | — |
| `is_mock` | boolean | 否 | default=false | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

<a id="schema-edusystemupsert"></a>
## EduSystemUpsert

模型定义：[backend/app/schemas/edu.py](../../backend/app/schemas/edu.py)。

管理员 upsert edu_systems 入参。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `system_key` | string | 是 | minLength=1; maxLength=128 | — |
| `school_code` | string / null | 否 | — | 学校代码 |
| `name` | string / null | 否 | — | 名称 |
| `system_type` | string / null | 否 | — | — |
| `provider` | string / null | 否 | — | — |
| `provider_version` | string / null | 否 | — | — |
| `base_url` | string / null | 否 | — | — |
| `login_url` | string / null | 否 | — | — |
| `sso_url` | string / null | 否 | — | — |
| `vpn_url` | string / null | 否 | — | — |
| `auth_type` | string / null | 否 | — | — |
| `login_execution_mode` | string / null | 否 | — | — |
| `captcha_type` | string / null | 否 | — | — |
| `requires_campus_network` | boolean / null | 否 | — | — |
| `requires_vpn` | boolean / null | 否 | — | — |
| `status` | string / null | 否 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `verification_status` | string / null | 否 | — | — |
| `supported_features` | array<string> / null | 否 | — | — |
| `adapter_config` | object / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `notes` | string / null | 否 | — | — |
| `is_mock` | boolean / null | 否 | — | — |

<a id="schema-errandextra"></a>
## ErrandExtra

模型定义：[backend/app/schemas/community.py](../../backend/app/schemas/community.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `price` | number / null | 否 | default=null; number约束: minimum=0.0 | — |
| `location` | string / null | 否 | default=null; string约束: maxLength=200 | — |
| `deadline` | string / null | 否 | default=null; string约束: maxLength=32 | 截止时间 |

<a id="schema-examexposurevalue"></a>
## ExamExposureValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `upcoming_exam_count` | integer | 是 | minimum=0.0 | — |
| `edu_exam_count` | integer | 否 | default=0; minimum=0.0 | — |
| `platform_exam_count` | integer | 否 | default=0; minimum=0.0 | — |
| `time_bucket_distribution` | map<string, integer> | 否 | additionalProperties={"type": "integer"} | — |
| `unknown_time_exam_count` | integer | 是 | minimum=0.0 | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-examin"></a>
## ExamIn

模型定义：[backend/app/api/routes/student_tools.py](../../backend/app/api/routes/student_tools.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_name` | string | 是 | minLength=1; maxLength=200 | — |
| `exam_date` | string | 是 | minLength=1; maxLength=32 | — |
| `start_time` | string / null | 否 | string约束: maxLength=16 | — |
| `end_time` | string / null | 否 | string约束: maxLength=16 | — |
| `location` | string / null | 否 | string约束: maxLength=200 | — |
| `seat_number` | string / null | 否 | string约束: maxLength=32 | — |
| `exam_type` | string / null | 否 | string约束: maxLength=64 | — |
| `reminder_enabled` | boolean | 否 | default=true | — |
| `notes` | string / null | 否 | string约束: maxLength=2000 | — |

<a id="schema-executionconsistencyvalue"></a>
## ExecutionConsistencyValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `planned_task_count` | integer | 是 | minimum=0.0 | — |
| `executed_task_count` | integer | 是 | minimum=0.0 | — |
| `consistency_ratio` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `consistency_band` | enum ["none", "low", "moderate", "high", "no_plan"] | 是 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-expressioncontributionresponse"></a>
## ExpressionContributionResponse

模型定义：[backend/app/api/routes/contributions.py](../../backend/app/api/routes/contributions.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sample_id` | string | 是 | — | — |
| `label` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `message` | string | 是 | — | — |

<a id="schema-expressionsignal"></a>
## ExpressionSignal

模型定义：[backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)。

端侧表情模型的瞬时观察结果；不包含也不允许包含图像数据。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `label` | string | 是 | minLength=1; maxLength=24 | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `is_stable` | boolean | 否 | default=false | — |
| `timestamp` | integer | 是 | exclusiveMinimum=0.0 | Unix epoch milliseconds |
| `model_version` | string | 是 | minLength=1; maxLength=80 | — |

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator('label', mode='before')
@classmethod
def _normalize_label(cls, value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError('label 必须是字符串')
    return value.strip().upper()
```

<a id="schema-favoritecreate"></a>
## FavoriteCreate

模型定义：[backend/app/schemas/personal_hub.py](../../backend/app/schemas/personal_hub.py)。

添加收藏。`id` 为客户端逻辑标识(如 "file:abc")。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | minLength=1; maxLength=128 | 当前资源标识 |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `type` | string / null | 否 | string约束: maxLength=32 | — |
| `subtitle` | string / null | 否 | string约束: maxLength=256 | — |
| `saved_at` | string / null | 否 | — | — |
| `source_route` | string / null | 否 | string约束: maxLength=64 | — |

<a id="schema-favoriteout"></a>
## FavoriteOut

模型定义：[backend/app/schemas/personal_hub.py](../../backend/app/schemas/personal_hub.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `title` | string | 是 | — | 标题 |
| `type` | string / null | 否 | — | — |
| `subtitle` | string / null | 否 | — | — |
| `saved_at` | string / null | 否 | — | — |
| `source_route` | string / null | 否 | — | — |

<a id="schema-filefavoritetoggle"></a>
## FileFavoriteToggle

模型定义：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `favorite` | boolean | 是 | — | — |

<a id="schema-finalreviewcampaignin"></a>
## FinalReviewCampaignIn

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

创建 campaign 请求。exam_ids 只接受 server /student/exams 返回的字符串。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `exam_ids` | array<string> | 是 | minItems=1; maxItems=20 | — |
| `daily_capacity_minutes` | integer | 是 | minimum=15.0; maximum=600.0 | — |
| `preferred_periods` | array<string> | 否 | maxItems=10 | — |
| `rest_days` | array<string> | 否 | maxItems=7 | — |
| `intensity` | string | 否 | default="medium"; pattern="^(low\|medium\|high)$" | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-finalreviewcampaignout"></a>
## FinalReviewCampaignOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-focusaiaskrequest"></a>
## FocusAiAskRequest

模型定义：[backend/app/schemas/focus_ai.py](../../backend/app/schemas/focus_ai.py)。

来自 Android ASR 的用户主动提问；当前版本没有视觉或会话上下文。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | minLength=1; maxLength=800 | 文本 |

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator('text')
@classmethod
def normalize_text(cls, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError('问题不能为空')
    return normalized
```

<a id="schema-focusaiaskresponse"></a>
## FocusAiAskResponse

模型定义：[backend/app/schemas/focus_ai.py](../../backend/app/schemas/focus_ai.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `answer` | string | 是 | — | — |

<a id="schema-focusrealtimevoicesessionresponse"></a>
## FocusRealtimeVoiceSessionResponse

模型定义：[backend/app/schemas/focus_ai.py](../../backend/app/schemas/focus_ai.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `websocket_path` | string | 是 | — | — |

<a id="schema-focusrealtimevoicestopresponse"></a>
## FocusRealtimeVoiceStopResponse

模型定义：[backend/app/schemas/focus_ai.py](../../backend/app/schemas/focus_ai.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `stopped` | boolean | 是 | — | — |

<a id="schema-focusrhythmvalue"></a>
## FocusRhythmValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_session_count` | integer | 是 | minimum=0.0 | — |
| `common_time_slots` | array<string> | 否 | maxItems=8 | — |
| `median_duration_minutes` | integer | 是 | minimum=0.0 | — |
| `rhythm_stability` | enum ["stable", "variable", "unknown"] | 是 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-foldercreatein"></a>
## FolderCreateIn

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=120 | 名称 |
| `parent_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | — |

<a id="schema-folderlistout"></a>
## FolderListOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[FolderOut](schemas.md#schema-folderout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |

<a id="schema-folderout"></a>
## FolderOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

一个用户可见的文件夹。

与 workspace 一样，`revision` 是并发控制的唯一凭据；`parent_id` 为 `None`
表示位于根层。`workspace_count` 只统计调用者自己、仍然存活的工作台。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `parent_id` | string / null | 否 | — | — |
| `name` | string | 是 | — | 名称 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `workspace_count` | integer / null | 否 | — | — |

<a id="schema-folderupdatein"></a>
## FolderUpdateIn

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=120 | 名称 |
| `parent_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | — |

<a id="schema-forecastevidencesummary"></a>
## ForecastEvidenceSummary

模型定义：[backend/app/schemas/forecast.py](../../backend/app/schemas/forecast.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_session_count` | integer | 否 | default=0; minimum=0.0 | — |
| `observed_task_count` | integer | 否 | default=0; minimum=0.0 | — |
| `observed_goal_count` | integer | 否 | default=0; minimum=0.0 | — |
| `observed_schedule_count` | integer | 否 | default=0; minimum=0.0 | — |
| `observed_exam_count` | integer | 否 | default=0; minimum=0.0 | — |
| `history_window_days` | integer | 否 | default=0; minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-forecastout"></a>
## ForecastOut

模型定义：[backend/app/schemas/forecast.py](../../backend/app/schemas/forecast.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `forecast_id` | string | 是 | — | — |
| `forecast_type` | enum ["DEADLINE_COMPLETION_RISK", "UPCOMING_WORKLOAD", "SCHEDULE_CONFLICT_RISK", "GOAL_PROGRESS_OUTLOOK", "ROUTINE_CONTINUITY"] | 是 | — | — |
| `scope_type` | enum ["USER", "COURSE", "TASK", "GOAL", "SEMESTER"] | 是 | — | — |
| `scope_id` | string | 是 | — | — |
| `horizon_start` | string (date-time) | 是 | format="date-time" | — |
| `horizon_end` | string (date-time) | 是 | format="date-time" | — |
| `probability` | number / null | 否 | number约束: minimum=0.0; maximum=1.0 | — |
| `value` | [DeadlineCompletionRiskValue](schemas.md#schema-deadlinecompletionriskvalue) / [UpcomingWorkloadValue](schemas.md#schema-upcomingworkloadvalue) / [ScheduleConflictRiskValue](schemas.md#schema-scheduleconflictriskvalue) / [GoalProgressOutlookValue](schemas.md#schema-goalprogressoutlookvalue) / [RoutineContinuityValue](schemas.md#schema-routinecontinuityvalue) | 是 | — | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `data_quality` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `estimator_version` | string | 是 | — | — |
| `input_digest` | string | 是 | — | — |
| `as_of` | string (date-time) | 是 | format="date-time" | — |
| `valid_until` | string (date-time) | 是 | format="date-time" | — |
| `explanation_codes` | array<enum ["insufficient_history", "deadline_within_horizon", "deadline_outside_horizon", "high_pending_density", "low_pending_density", "exam_collision", "schedule_overlap", "goal_active", "goal_archived", "routine_stable", "routine_variable", "input_truncated", "no_observed_sessions", "no_observed_tasks", "no_observed_goals", "no_observed_schedule", "projection_failed", "stale_input_rejected", "horizon_too_short", "horizon_too_long"]> | 否 | maxItems=16 | — |
| `evidence_summary` | [ForecastEvidenceSummary](schemas.md#schema-forecastevidencesummary) | 是 | — | — |
| `limitations` | array<enum ["baseline_estimator_only", "no_causal_claim", "correlation_not_causation", "short_history", "single_user_scope", "no_psychological_inference", "no_dropout_prediction", "no_employment_prediction", "no_personality_prediction", "synthetic_calibration_only", "not_measured_against_real_outcomes"]> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@model_validator(mode='after')
def validate_value_for_type(self) -> 'ForecastOut':
    expected = {'DEADLINE_COMPLETION_RISK': DeadlineCompletionRiskValue, 'UPCOMING_WORKLOAD': UpcomingWorkloadValue, 'SCHEDULE_CONFLICT_RISK': ScheduleConflictRiskValue, 'GOAL_PROGRESS_OUTLOOK': GoalProgressOutlookValue, 'ROUTINE_CONTINUITY': RoutineContinuityValue}[self.forecast_type]
    if not isinstance(self.value, expected):
        raise ValueError('value does not match forecast_type')
    if self.data_quality == 'unavailable':
        if self.confidence != 0:
            raise ValueError('unavailable forecast confidence must be zero')
        if self.probability is not None:
            raise ValueError('unavailable forecast must not carry a probability')
    if self.data_quality == 'stale' and self.confidence > 0.25:
        raise ValueError('stale forecast confidence is capped at 0.25')
    if self.data_quality == 'partial' and self.confidence > 0.6:
        raise ValueError('partial forecast confidence is capped at 0.6')
    if self.horizon_end <= self.horizon_start:
        raise ValueError('horizon_end must be after horizon_start')
    return self
```

<a id="schema-forecastpage"></a>
## ForecastPage

模型定义：[backend/app/schemas/forecast.py](../../backend/app/schemas/forecast.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[ForecastOut](schemas.md#schema-forecastout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | minimum=0.0 | 总数 |
| `page` | integer | 是 | minimum=1.0 | 当前页，从 1 开始 |
| `page_size` | integer | 是 | minimum=1.0 | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-fusionrecentitem"></a>
## FusionRecentItem

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

一条"最近学习内容"，已按服务端权限过滤。

``href`` 是 **CampusMate 站内**深链（不是 magic class 地址），学生点击后
回到课程详情的智能辅导栏目；``classroom_url`` 才是可选的外部课堂地址，
且仅在公开 Origin 已配置时才下发。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | const "classroom" | 是 | — | — |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `course_name` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `mode` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `scenes_count` | integer / null | 否 | — | — |
| `href` | string | 是 | — | — |
| `classroom_url` | string / null | 否 | — | — |
| `classroom_url_unavailable_reason` | string / null | 否 | — | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

<a id="schema-fusionrecentout"></a>
## FusionRecentOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[FusionRecentItem](schemas.md#schema-fusionrecentitem)> | 否 | — | 列表条目 |
| `limit` | integer | 是 | — | 本次读取上限 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

<a id="schema-fusionstate"></a>
## FusionState

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

受管服务的单一状态判据（客户端只需 switch 这一个字段）。

- ``disabled``：融合开关关闭，网关**不会**尝试调用受管服务。
- ``unavailable``：开关开启，但受管服务不可达/未配置/拒绝我们的断言。
- ``degraded``：受管服务在线，但自身依赖（数据库等）未就绪。
- ``ready``：受管服务与依赖都就绪，``capabilities`` 可信。


类型：enum ["disabled", "unavailable", "degraded", "ready"]。

```json
{
  "type": "string",
  "enum": [
    "disabled",
    "unavailable",
    "degraded",
    "ready"
  ],
  "title": "FusionState",
  "description": "受管服务的单一状态判据（客户端只需 switch 这一个字段）。\n\n- ``disabled``：融合开关关闭，网关**不会**尝试调用受管服务。\n- ``unavailable``：开关开启，但受管服务不可达/未配置/拒绝我们的断言。\n- ``degraded``：受管服务在线，但自身依赖（数据库等）未就绪。\n- ``ready``：受管服务与依赖都就绪，``capabilities`` 可信。"
}
```

对象级约束：

```json
{
  "enum": [
    "disabled",
    "unavailable",
    "degraded",
    "ready"
  ]
}
```

<a id="schema-fusionstatus"></a>
## FusionStatus

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

网关对受管 magicclass 服务的公开状态。

``state`` 是唯一判据；``enabled`` / ``available`` 保留为便捷布尔量，
供只关心"能不能用"的旧客户端使用。``capabilities`` 只在 ``state=ready``
时非空 —— 依赖没就绪时不得声称任何能力可用。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | 是 | — | 是否启用 |
| `available` | boolean | 是 | — | 当前能力是否可用 |
| `state` | [FusionState](schemas.md#schema-fusionstate) | 是 | — | — |
| `capabilities` | array<string> | 否 | — | — |
| `reason` | string | 是 | — | 原因 |

<a id="schema-generationin"></a>
## GenerationIn

模型定义：[backend/app/api/routes/magicclass_generation.py](../../backend/app/api/routes/magicclass_generation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 是 | minLength=1; maxLength=80 | — |
| `prompt` | string | 是 | minLength=1; maxLength=2000 | — |
| `role_mode` | string | 否 | default="preset"; pattern="^(preset\|auto)$" | — |
| `selected_role_ids` | array<string> | 否 | maxItems=7 | — |

<a id="schema-goalprogressoutlookvalue"></a>
## GoalProgressOutlookValue

模型定义：[backend/app/schemas/forecast.py](../../backend/app/schemas/forecast.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `active_goal_count` | integer | 是 | minimum=0.0 | — |
| `average_progress_percent` | number | 是 | minimum=0.0; maximum=100.0 | — |
| `goals_with_recent_progress` | integer | 是 | minimum=0.0 | — |
| `outlook_band` | enum ["rising", "steady", "declining", "insufficient_data"] | 是 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-goalprogressvalue"></a>
## GoalProgressValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `active_goal_count` | integer | 是 | minimum=0.0 | — |
| `archived_goal_count` | integer | 是 | minimum=0.0 | — |
| `goals_with_milestones` | integer | 是 | minimum=0.0 | — |
| `average_progress_percent` | number | 是 | minimum=0.0; maximum=100.0 | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-goalstatevalue"></a>
## GoalStateValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `active_daily_goals` | integer | 是 | minimum=0.0 | — |
| `session_goals_summary` | map<string, integer> | 否 | additionalProperties={"type": "integer"} | — |
| `accepted_plan_goals` | integer | 是 | minimum=0.0 | — |
| `source_labels` | array<enum ["student_initiated", "system_suggested", "plan_accepted"]> | 否 | maxItems=16 | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-gradeobservationvalue"></a>
## GradeObservationValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_grade_count` | integer | 是 | minimum=0.0 | — |
| `edu_grade_count` | integer | 否 | default=0; minimum=0.0 | — |
| `platform_grade_count` | integer | 否 | default=0; minimum=0.0 | — |
| `score_band_distribution` | map<string, integer> | 否 | additionalProperties={"type": "integer"} | — |
| `has_observed_grades` | boolean | 是 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-growthmomentumvalue"></a>
## GrowthMomentumValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal_count` | integer | 是 | minimum=0.0 | — |
| `goals_with_recent_progress` | integer | 是 | minimum=0.0 | — |
| `momentum_band` | enum ["rising", "steady", "declining", "insufficient_data"] | 是 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-httpvalidationerror"></a>
## HTTPValidationError

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `detail` | array<[ValidationError](schemas.md#schema-validationerror)> | 否 | — | — |

<a id="schema-homebannerfeed"></a>
## HomeBannerFeed

模型定义：[backend/app/schemas/home_banner.py](../../backend/app/schemas/home_banner.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[HomeBannerOut](schemas.md#schema-homebannerout)> | 是 | — | 列表条目 |
| `updated_at` | string / null | 否 | — | 最近更新时间 |

<a id="schema-homebannerimageout"></a>
## HomeBannerImageOut

模型定义：[backend/app/schemas/home_banner.py](../../backend/app/schemas/home_banner.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `image_url` | string | 是 | — | — |
| `filename` | string | 是 | — | 文件名 |
| `size` | integer | 是 | — | — |

<a id="schema-homebannerout"></a>
## HomeBannerOut

模型定义：[backend/app/schemas/home_banner.py](../../backend/app/schemas/home_banner.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `eyebrow` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `subtitle` | string | 是 | — | — |
| `cta_label` | string | 是 | — | — |
| `image_url` | string | 是 | — | — |
| `action_key` | enum ["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"] | 是 | — | — |
| `theme_key` | enum ["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"] | 是 | — | — |
| `sort_order` | integer | 是 | — | — |
| `status` | enum ["DRAFT", "PUBLISHED", "ARCHIVED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `starts_at` | string / null | 否 | — | — |
| `ends_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

<a id="schema-homebannerwrite"></a>
## HomeBannerWrite

模型定义：[backend/app/schemas/home_banner.py](../../backend/app/schemas/home_banner.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `eyebrow` | string | 是 | minLength=1; maxLength=60 | — |
| `title` | string | 是 | minLength=1; maxLength=80 | 标题 |
| `subtitle` | string | 是 | minLength=1; maxLength=160 | — |
| `cta_label` | string | 是 | minLength=1; maxLength=30 | — |
| `image_url` | string | 是 | minLength=1; maxLength=500 | — |
| `action_key` | enum ["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"] | 是 | — | — |
| `theme_key` | enum ["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"] | 是 | — | — |
| `sort_order` | integer | 否 | default=0; minimum=-10000.0; maximum=10000.0 | — |
| `starts_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `ends_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@model_validator(mode='after')
def validate_window(self) -> 'HomeBannerWrite':
    if self.starts_at is not None and self.ends_at is not None and (self.ends_at <= self.starts_at):
        raise ValueError('ends_at must be later than starts_at')
    return self
```

<a id="schema-homegenerationin"></a>
## HomeGenerationIn

模型定义：[backend/app/api/routes/magicclass_generation.py](../../backend/app/api/routes/magicclass_generation.py)。

The single homepage write contract.

Resolving the workspace and enqueueing its first stage here keeps a browser
retry from racing two separate create calls.

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 否 | default="slide"; minLength=1; maxLength=80 | — |
| `prompt` | string | 是 | minLength=1; maxLength=750 | — |

<a id="schema-importancerankitem"></a>
## ImportanceRankItem

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

单个任务的重要程度评定结果。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | string | 是 | — | — |
| `importance` | string | 是 | pattern="^(urgent\|high\|important\|normal\|low\|unknown)$" | — |
| `reason` | string / null | 否 | — | 评定理由 |
| `mode` | string | 是 | — | 评定模式: llm\|rules |

<a id="schema-importancerankrequest"></a>
## ImportanceRankRequest

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

批量重排任务重要程度请求。

不传 task_ids 时，对当前用户所有 pending 任务评定(最多 50 条)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_ids` | array<string> / null | 否 | array约束: maxItems=50 | 指定任务 ID 列表(为空则评定全部 pending 任务) |

<a id="schema-importancerankresponse"></a>
## ImportanceRankResponse

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

批量重排响应。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `updated` | array<[ImportanceRankItem](schemas.md#schema-importancerankitem)> | 否 | — | — |
| `skipped` | array<string> | 否 | — | 跳过的任务 ID(LLM 不可用或任务不存在) |
| `mode` | string | 是 | — | 本次评定实际使用模式: llm\|rules |
| `total` | integer | 否 | default=0 | 本次评定任务数 |

<a id="schema-interactiveclassroominput"></a>
## InteractiveClassroomInput

模型定义：[backend/app/services/agent_runtime/handlers/interactive_classroom.py](../../backend/app/services/agent_runtime/handlers/interactive_classroom.py)。

`interactive_classroom` 命令输入。未知键保持透传，不破坏旧客户端。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | minLength=1; maxLength=128 | 关联课程标识 |
| `mode` | string | 否 | default="adaptive"; maxLength=32 | — |
| `learning_objective` | string / null | 否 | default=null; string约束: maxLength=500 | — |
| `current_difficulty` | string / null | 否 | default=null; string约束: maxLength=500 | — |
| `desired_duration_minutes` | integer / null | 否 | default=null; integer约束: minimum=5; maximum=180 | — |
| `difficulty_level` | string / null | 否 | default=null; string约束: maxLength=16 | — |
| `wants_more_practice` | boolean | 否 | default=false | — |
| `selected_material_ids` | array<string> | 否 | maxItems=20 | — |
| `user_id` | string / null | 否 | default=null | 所属用户标识 |

对象级约束：

```json
{
  "additionalProperties": true
}
```

<a id="schema-knowledgegraphout"></a>
## KnowledgeGraphOut

模型定义：[backend/app/schemas/course_content.py](../../backend/app/schemas/course_content.py)。

课程知识图谱：课程级统计 + 知识点清单。

掌握率/完成率是平台发布的课程级平均值（0-100），不是逐知识点值。
`available=False` 表示该课程尚未同步过知识图谱（需 depth=deep 同步）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | — | 关联课程标识 |
| `available` | boolean | 否 | default=false | 当前能力是否可用 |
| `synced_at` | string / null | 否 | — | — |
| `knowledge_point_count` | integer | 否 | default=0 | — |
| `own_mastery_rate` | number / null | 否 | — | — |
| `class_mastery_rate` | number / null | 否 | — | — |
| `mastery_gap_vs_class` | number / null | 否 | — | — |
| `own_completion_rate` | number / null | 否 | — | — |
| `class_completion_rate` | number / null | 否 | — | — |
| `tags` | array<string> | 否 | — | — |
| `points` | array<[KnowledgePointOut](schemas.md#schema-knowledgepointout)> | 否 | — | — |

<a id="schema-knowledgemasteryobservationvalue"></a>
## KnowledgeMasteryObservationValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

课程知识图谱观测 —— 知识点体系与掌握率(来自学习通课程图谱页)。

与 C 时代被删除的"平台自造知识点推断"不同: 这里是课程/学校发布的
知识点体系 + 平台统计的真实掌握率，属于外部数据源观测。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `knowledge_point_count` | integer | 是 | minimum=0.0 | — |
| `own_mastery_rate` | number / null | 否 | — | — |
| `class_mastery_rate` | number / null | 否 | — | — |
| `mastery_gap_vs_class` | number / null | 否 | — | — |
| `own_completion_rate` | number / null | 否 | — | — |
| `class_completion_rate` | number / null | 否 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-knowledgepointout"></a>
## KnowledgePointOut

模型定义：[backend/app/schemas/course_content.py](../../backend/app/schemas/course_content.py)。

单个课程知识点（外部数据源观测，非本地推断）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `external_id` | string | 是 | — | — |
| `name` | string | 是 | — | 名称 |
| `tags` | array<string> | 否 | — | — |
| `position` | integer | 否 | default=0 | — |

<a id="schema-knowledgestatus"></a>
## KnowledgeStatus

模型定义：[backend/app/schemas/knowledge.py](../../backend/app/schemas/knowledge.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `document_count` | integer | 是 | — | — |
| `chunk_count` | integer | 是 | — | — |
| `last_updated` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `index_status` | string | 是 | — | ready\|empty\|error |
| `retrieval_method` | string | 是 | — | bm25\|vector\|hybrid |
| `is_available` | boolean | 是 | — | — |
| `knowledge_base_path` | string | 是 | — | — |
| `knowledge_base_type` | string | 是 | — | demo\|user\|hybrid\|empty |
| `demo_document_count` | integer | 否 | default=0 | — |
| `user_document_count` | integer | 否 | default=0 | — |
| `llm_available` | boolean | 否 | default=false | — |
| `qa_mode` | string | 否 | default="no_knowledge" | retrieval_summary\|llm_rag\|no_knowledge |

<a id="schema-learnerstatechangeout"></a>
## LearnerStateChangeOut

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `scope_type` | enum ["USER", "COURSE", "TASK", "SOURCE", "SEMESTER"] | 是 | — | — |
| `scope_id` | string | 是 | — | — |
| `state_type` | enum ["observed_learning_activity", "task_workload", "deadline_exposure", "course_participation", "data_source_health", "academic_course_load", "grade_observation", "knowledge_mastery_observation", "credit_progress", "exam_exposure", "schedule_load", "goal_state", "workload_pressure", "schedule_conflict", "academic_progress", "focus_rhythm", "goal_progress", "execution_consistency", "growth_momentum", "preference_profile"] | 是 | — | — |
| `change_type` | enum ["ADDED", "UPDATED", "REMOVED", "UNCHANGED"] | 是 | — | — |
| `previous_value` | [ObservedLearningActivityValue](schemas.md#schema-observedlearningactivityvalue) / [TaskWorkloadValue](schemas.md#schema-taskworkloadvalue) / [DeadlineExposureValue](schemas.md#schema-deadlineexposurevalue) / [CourseParticipationValue](schemas.md#schema-courseparticipationvalue) / [DataSourceHealthValue](schemas.md#schema-datasourcehealthvalue) / [AcademicCourseLoadValue](schemas.md#schema-academiccourseloadvalue) / [GradeObservationValue](schemas.md#schema-gradeobservationvalue) / [KnowledgeMasteryObservationValue](schemas.md#schema-knowledgemasteryobservationvalue) / [CreditProgressValue](schemas.md#schema-creditprogressvalue) / [ExamExposureValue](schemas.md#schema-examexposurevalue) / [ScheduleLoadValue](schemas.md#schema-scheduleloadvalue) / [GoalStateValue](schemas.md#schema-goalstatevalue) / [WorkloadPressureValue](schemas.md#schema-workloadpressurevalue) / [ScheduleConflictValue](schemas.md#schema-scheduleconflictvalue) / [AcademicProgressValue](schemas.md#schema-academicprogressvalue) / [FocusRhythmValue](schemas.md#schema-focusrhythmvalue) / [GoalProgressValue](schemas.md#schema-goalprogressvalue) / [ExecutionConsistencyValue](schemas.md#schema-executionconsistencyvalue) / [GrowthMomentumValue](schemas.md#schema-growthmomentumvalue) / [PreferenceProfileValue](schemas.md#schema-preferenceprofilevalue) / null | 否 | — | — |
| `current_value` | [ObservedLearningActivityValue](schemas.md#schema-observedlearningactivityvalue) / [TaskWorkloadValue](schemas.md#schema-taskworkloadvalue) / [DeadlineExposureValue](schemas.md#schema-deadlineexposurevalue) / [CourseParticipationValue](schemas.md#schema-courseparticipationvalue) / [DataSourceHealthValue](schemas.md#schema-datasourcehealthvalue) / [AcademicCourseLoadValue](schemas.md#schema-academiccourseloadvalue) / [GradeObservationValue](schemas.md#schema-gradeobservationvalue) / [KnowledgeMasteryObservationValue](schemas.md#schema-knowledgemasteryobservationvalue) / [CreditProgressValue](schemas.md#schema-creditprogressvalue) / [ExamExposureValue](schemas.md#schema-examexposurevalue) / [ScheduleLoadValue](schemas.md#schema-scheduleloadvalue) / [GoalStateValue](schemas.md#schema-goalstatevalue) / [WorkloadPressureValue](schemas.md#schema-workloadpressurevalue) / [ScheduleConflictValue](schemas.md#schema-scheduleconflictvalue) / [AcademicProgressValue](schemas.md#schema-academicprogressvalue) / [FocusRhythmValue](schemas.md#schema-focusrhythmvalue) / [GoalProgressValue](schemas.md#schema-goalprogressvalue) / [ExecutionConsistencyValue](schemas.md#schema-executionconsistencyvalue) / [GrowthMomentumValue](schemas.md#schema-growthmomentumvalue) / [PreferenceProfileValue](schemas.md#schema-preferenceprofilevalue) / null | 否 | — | — |
| `previous_quality` | enum ["verified", "partial", "stale", "unavailable"] / null | 否 | — | — |
| `current_quality` | enum ["verified", "partial", "stale", "unavailable"] / null | 否 | — | — |
| `previous_confidence` | number / null | 否 | number约束: minimum=0.0; maximum=1.0 | — |
| `current_confidence` | number / null | 否 | number约束: minimum=0.0; maximum=1.0 | — |
| `explanation_codes` | array<enum ["state_added", "state_removed", "observed_value_changed", "data_quality_changed", "deadline_bucket_changed", "source_freshness_changed", "authoritative_task_changed", "event_projection_gap", "input_truncated"]> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@model_validator(mode='after')
def validate_values(self) -> 'LearnerStateChangeOut':
    expected = STATE_VALUE_MODELS[self.state_type]
    if self.previous_value is not None and (not isinstance(self.previous_value, expected)):
        raise ValueError('previous_value does not match state_type')
    if self.current_value is not None and (not isinstance(self.current_value, expected)):
        raise ValueError('current_value does not match state_type')
    return self
```

<a id="schema-learnerstatechangepage"></a>
## LearnerStateChangePage

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-learnerstateevidenceout"></a>
## LearnerStateEvidenceOut

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `evidence_kind` | enum ["EVENT", "SOURCE_ROW", "SYNC_STATUS"] | 是 | — | — |
| `source_category` | enum ["study_session", "personal_task", "course_content", "course_sync", "core_learning_record", "chaoxing", "edu_schedule", "edu_grade", "edu_exam", "self_report", "ai_learning_feedback", "unknown"] | 是 | — | — |
| `event_id` | string / null | 否 | — | — |
| `event_type` | string / null | 否 | — | — |
| `occurred_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `data_quality` | enum ["verified", "partial", "stale", "unavailable"] / null | 否 | — | — |
| `role` | enum ["SUPPORTS", "LIMITS", "INVALIDATES"] | 是 | — | — |
| `explanation_code` | enum ["completed_study_session", "current_pending_task", "observed_platform_completion", "chapter_sync_complete", "chapter_data_stale", "source_disconnected", "event_projection_gap", "input_truncated", "historical_submission_not_current", "orphan_assignment_submitted", "platform_event_observed", "state_observed", "edu_schedule_observed", "edu_grade_observed", "edu_exam_observed", "academic_data_unavailable", "goal_student_initiated", "goal_system_suggested"] | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-learnerstateevidencepage"></a>
## LearnerStateEvidencePage

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearnerStateEvidenceOut](schemas.md#schema-learnerstateevidenceout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-learnerstaterunout"></a>
## LearnerStateRunOut

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | — | 运行标识 |
| `as_of` | string (date-time) | 是 | format="date-time" | — |
| `computed_at` | string (date-time) | 是 | format="date-time" | — |
| `estimator_version` | string | 是 | — | — |
| `trigger` | string | 是 | — | — |
| `is_current` | boolean | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=32 | — |
| `snapshot_count` | integer | 是 | minimum=0.0 | — |
| `projection_kind` | enum ["CORE", "ACADEMIC", "WORLD"] | 否 | default="CORE" | — |
| `projection_scope` | string | 否 | default="__user__" | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-learnerstaterunpage"></a>
## LearnerStateRunPage

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearnerStateRunOut](schemas.md#schema-learnerstaterunout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | minimum=0.0 | 总数 |
| `page` | integer | 是 | minimum=1.0 | 当前页，从 1 开始 |
| `page_size` | integer | 是 | minimum=1.0 | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-learnerstatesnapshotout"></a>
## LearnerStateSnapshotOut

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `snapshot_id` | string | 是 | — | — |
| `run_id` | string | 是 | — | 运行标识 |
| `scope_type` | enum ["USER", "COURSE", "TASK", "SOURCE", "SEMESTER"] | 是 | — | — |
| `scope_id` | string | 是 | — | — |
| `state_type` | enum ["observed_learning_activity", "task_workload", "deadline_exposure", "course_participation", "data_source_health", "academic_course_load", "grade_observation", "knowledge_mastery_observation", "credit_progress", "exam_exposure", "schedule_load", "goal_state", "workload_pressure", "schedule_conflict", "academic_progress", "focus_rhythm", "goal_progress", "execution_consistency", "growth_momentum", "preference_profile"] | 是 | — | — |
| `value` | [ObservedLearningActivityValue](schemas.md#schema-observedlearningactivityvalue) / [TaskWorkloadValue](schemas.md#schema-taskworkloadvalue) / [DeadlineExposureValue](schemas.md#schema-deadlineexposurevalue) / [CourseParticipationValue](schemas.md#schema-courseparticipationvalue) / [DataSourceHealthValue](schemas.md#schema-datasourcehealthvalue) / [AcademicCourseLoadValue](schemas.md#schema-academiccourseloadvalue) / [GradeObservationValue](schemas.md#schema-gradeobservationvalue) / [KnowledgeMasteryObservationValue](schemas.md#schema-knowledgemasteryobservationvalue) / [CreditProgressValue](schemas.md#schema-creditprogressvalue) / [ExamExposureValue](schemas.md#schema-examexposurevalue) / [ScheduleLoadValue](schemas.md#schema-scheduleloadvalue) / [GoalStateValue](schemas.md#schema-goalstatevalue) / [WorkloadPressureValue](schemas.md#schema-workloadpressurevalue) / [ScheduleConflictValue](schemas.md#schema-scheduleconflictvalue) / [AcademicProgressValue](schemas.md#schema-academicprogressvalue) / [FocusRhythmValue](schemas.md#schema-focusrhythmvalue) / [GoalProgressValue](schemas.md#schema-goalprogressvalue) / [ExecutionConsistencyValue](schemas.md#schema-executionconsistencyvalue) / [GrowthMomentumValue](schemas.md#schema-growthmomentumvalue) / [PreferenceProfileValue](schemas.md#schema-preferenceprofilevalue) | 是 | — | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `data_quality` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `observed_from` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `observed_through` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `valid_until` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `computed_at` | string (date-time) | 是 | format="date-time" | — |
| `estimator_version` | string | 否 | default="" | — |
| `projection_kind` | enum ["CORE", "ACADEMIC", "WORLD"] | 否 | default="CORE" | — |
| `projection_scope` | string | 否 | default="__user__" | — |
| `input_digest` | string | 否 | default="" | — |
| `as_of` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `warning_codes` | array<string> | 否 | maxItems=32 | — |
| `evidence_count` | integer | 否 | default=0; minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@model_validator(mode='after')
def validate_value_for_state(self) -> 'LearnerStateSnapshotOut':
    expected = STATE_VALUE_MODELS[self.state_type]
    if not isinstance(self.value, expected):
        raise ValueError('value does not match state_type')
    if self.data_quality == 'unavailable' and self.confidence != 0:
        raise ValueError('unavailable state confidence must be zero')
    if self.data_quality == 'stale' and self.confidence > 0.25:
        raise ValueError('stale state confidence is capped at 0.25')
    if self.data_quality == 'partial' and self.confidence > 0.6:
        raise ValueError('partial state confidence is capped at 0.6')
    return self
```

<a id="schema-learnerstatesnapshotpage"></a>
## LearnerStateSnapshotPage

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearnerStateSnapshotOut](schemas.md#schema-learnerstatesnapshotout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-learninggoalinput"></a>
## LearningGoalInput

模型定义：[backend/app/services/agent_runtime/handlers/learning_goal.py](../../backend/app/services/agent_runtime/handlers/learning_goal.py)。

`learning_goal` 的输入模型。未知键保持透传,不破坏旧客户端。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal_id` | string | 是 | minLength=1; maxLength=128 | — |
| `available_minutes` | integer | 否 | default=60; minimum=1; maximum=1440 | — |
| `course_id` | string / null | 否 | default=null | 关联课程标识 |
| `window_start` | string / null | 否 | default=null | — |
| `window_end` | string / null | 否 | default=null | — |
| `plan_id` | string / null | 否 | default=null | — |

对象级约束：

```json
{
  "additionalProperties": true
}
```

<a id="schema-learningplandecisionrequest"></a>
## LearningPlanDecisionRequest

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `decision` | string | 是 | pattern="^(ACCEPT\|REJECT)$" | 用户决定，严格按枚举大小写 |

<a id="schema-learningplanevaluationout"></a>
## LearningPlanEvaluationOut

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

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

<a id="schema-learningplanevidenceout"></a>
## LearningPlanEvidenceOut

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `evidence_type` | string | 是 | — | — |
| `relation` | string | 是 | — | — |
| `relevance_score` | number / null | 否 | — | — |

<a id="schema-learningplanfeedbackout"></a>
## LearningPlanFeedbackOut

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `plan_id` | string | 是 | — | — |
| `feedback` | string | 是 | — | — |
| `recorded` | boolean | 否 | default=true | — |

<a id="schema-learningplanfeedbackrequest"></a>
## LearningPlanFeedbackRequest

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `feedback` | string | 是 | pattern="^(HELPFUL\|NOT_HELPFUL\|TOO_LONG\|TOO_SHORT\|WRONG_PRIORITY\|ALREADY_DONE\|MISSING_CONTEXT)$" | — |

<a id="schema-learningplangeneraterequest"></a>
## LearningPlanGenerateRequest

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `available_minutes` | integer | 是 | minimum=1.0; maximum=1440.0 | — |
| `goal_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| `course_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | 关联课程标识 |
| `window_start` | string / null | 否 | string约束: maxLength=64 | — |
| `window_end` | string / null | 否 | string约束: maxLength=64 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| `enhance_with_llm` | boolean | 否 | default=false | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator('window_end')
@classmethod
def _window_requires_start(cls, value: str | None, info):
    if value and (not info.data.get('window_start')):
        raise ValueError('window_end requires window_start')
    return value
```

<a id="schema-learningplanitemout"></a>
## LearningPlanItemOut

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `item_id` | string | 是 | — | — |
| `item_type` | enum ["TASK_FOCUS", "EXAM_PREPARATION", "CAMPUS_AFFAIRS", "GOAL_PROGRESS", "RESEARCH_OR_COMPETITION", "CAREER_PREPARATION", "RECOVERY_BUFFER", "REVIEW_AND_REFLECT"] | 是 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `task_id` | string / null | 否 | — | — |
| `estimated_minutes` | integer | 是 | — | — |
| `priority_score` | number | 是 | — | — |
| `priority_components` | map<string, number> | 是 | additionalProperties={"type": "number"} | — |
| `explanation_codes` | array<string> | 是 | — | — |
| `evidence` | array<[LearningPlanEvidenceOut](schemas.md#schema-learningplanevidenceout)> | 是 | — | — |
| `execution_status` | string | 是 | — | — |

<a id="schema-learningplanout"></a>
## LearningPlanOut

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-learningplanpage"></a>
## LearningPlanPage

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[LearningPlanOut](schemas.md#schema-learningplanout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

<a id="schema-learningplansummaryout"></a>
## LearningPlanSummaryOut

模型定义：[backend/app/schemas/learning_plan.py](../../backend/app/schemas/learning_plan.py)。

面向三端的阶段总结；内容是可解释的观测，不宣称因果效果。

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

<a id="schema-loginrequest"></a>
## LoginRequest

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=1; maxLength=64 | 登录用户名 |
| `password` | string | 是 | minLength=1; maxLength=128 | 登录密码，仅请求使用 |

<a id="schema-logoutrequest"></a>
## LogoutRequest

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `refresh_token` | string / null | 否 | — | 换发令牌；不是业务访问凭据 |

<a id="schema-magicclassclassroomout"></a>
## MagicClassClassroomOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `classroom_id` | string / null | 否 | — | — |
| `url` | string / null | 否 | — | — |
| `url_unavailable_reason` | string / null | 否 | — | — |
| `mode` | string | 是 | — | — |
| `scenes_count` | integer / null | 否 | — | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `composition` | [MagicClassCompositionOut](schemas.md#schema-magicclasscompositionout) / null | 否 | — | — |

<a id="schema-magicclassclassroomsout"></a>
## MagicClassClassroomsOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | 是 | — | 是否启用 |
| `items` | array<[MagicClassClassroomOut](schemas.md#schema-magicclassclassroomout)> | 否 | — | 列表条目 |

<a id="schema-magicclasscompositionout"></a>
## MagicClassCompositionOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

**真实**课堂组成（读取 GET /api/classroom?id= 后统计）。

必须如实反映生成结果，不得根据请求 mode 推断。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `classroom_id` | string | 是 | — | — |
| `scene_total` | integer | 否 | default=0 | — |
| `scenes` | array<[MagicClassSceneCountOut](schemas.md#schema-magicclassscenecountout)> | 否 | — | — |
| `widget_types` | array<[MagicClassWidgetCountOut](schemas.md#schema-magicclasswidgetcountout)> | 否 | — | — |
| `has_whiteboard` | boolean | 否 | default=false | — |
| `has_tts` | boolean | 否 | default=false | — |
| `has_multi_agent` | boolean | 否 | default=false | — |
| `has_unknown_scene_type` | boolean | 否 | default=false | — |
| `has_unknown_widget_type` | boolean | 否 | default=false | — |
| `requires_external_3d` | boolean | 否 | default=false | — |
| `external_3d_available` | boolean | 否 | default=true | — |
| `degraded` | boolean | 否 | default=false | — |
| `read_at` | string | 否 | default="" | — |
| `error` | string / null | 否 | — | — |

<a id="schema-magicclassgenerateout"></a>
## MagicClassGenerateOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `accepted` | boolean | 否 | default=true | — |
| `session` | [MagicClassSessionOut](schemas.md#schema-magicclasssessionout) | 是 | — | — |
| `poll_interval_ms` | integer | 否 | default=5000 | — |
| `mode` | string | 是 | — | — |
| `requested_mode` | string / null | 否 | — | — |
| `adaptive_reason` | string / null | 否 | — | — |
| `materials` | array<[MagicClassMaterialOut](schemas.md#schema-magicclassmaterialout)> | 否 | — | — |
| `request_source` | string / null | 否 | — | — |
| `request_source_note` | string / null | 否 | — | — |
| `materials_unresolved` | array<string> | 否 | — | — |
| `materials_warning` | string / null | 否 | — | — |

<a id="schema-magicclassgeneraterequest"></a>
## MagicClassGenerateRequest

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

学生发起一次课堂生成。

所有补充信息都是可选的；`selected_material_ids` 只用于筛选服务端已授权的资料，
客户端提交的任何资料标题或正文都不被信任。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 否 | default="adaptive" | 生成意图：adaptive/explain/quiz/simulation/visualization/mindmap/coding/pbl/review |
| `learning_objective` | string / null | 否 | string约束: maxLength=500 | 学生明确选择的学习目标(可选) |
| `current_difficulty` | string / null | 否 | string约束: maxLength=500 | 学生当前卡在哪里(可选) |
| `desired_duration_minutes` | integer / null | 否 | integer约束: minimum=5.0; maximum=180.0 | 期望学习时长(分钟，可选) |
| `difficulty_level` | string / null | 否 | — | 难度：beginner/standard/advanced(可选) |
| `wants_more_practice` | boolean | 否 | default=false | 是否需要更多练习 |
| `selected_material_ids` | array<string> | 否 | maxItems=20 | 希望使用的课程资料 ID 列表 |

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator('mode')
@classmethod
def _mode_valid(cls, v: str) -> str:
    return normalize_mode(v)
```

```python
@field_validator('difficulty_level')
@classmethod
def _difficulty_valid(cls, v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    normalized = str(v).strip().lower()
    if not normalized:
        return None
    if normalized not in VALID_DIFFICULTY_LEVELS:
        raise ValueError(f'不支持的难度: {v}')
    return normalized
```

```python
@field_validator('selected_material_ids')
@classmethod
def _materials_valid(cls, v: List[str]) -> List[str]:
    out: List[str] = []
    for item in v or []:
        text = str(item or '').strip()
        if text and text not in out:
            out.append(text)
    return out[:20]
```

<a id="schema-magicclassmaterialout"></a>
## MagicClassMaterialOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

学生可选用的课程资料（只暴露 id/标题/类型）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `title` | string | 是 | — | 标题 |
| `kind` | string | 否 | default="资料" | — |

<a id="schema-magicclassplanout"></a>
## MagicClassPlanOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

生成**之前**给学生看的信息：会用什么课程、哪些资料、为什么推荐这个形态。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | — | 关联课程标识 |
| `course_name` | string | 是 | — | — |
| `mode` | string | 是 | — | — |
| `mode_label` | string | 是 | — | — |
| `requested_mode` | string | 是 | — | — |
| `adaptive_reason` | string / null | 否 | — | — |
| `intent_note` | string | 否 | default="内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。" | — |
| `materials` | array<[MagicClassMaterialOut](schemas.md#schema-magicclassmaterialout)> | 否 | — | — |
| `selected_material_ids` | array<string> | 否 | — | — |
| `context_sources` | map<string, string> | 否 | additionalProperties={"type": "string"} | — |
| `context_updated_at` | map<string, string> | 否 | additionalProperties={"type": "string"} | — |
| `context_truncated` | boolean | 否 | default=false | — |
| `context_warnings` | array<string> | 否 | — | — |
| `capabilities` | map<string, boolean> | 否 | additionalProperties={"type": "boolean"} | — |
| `external_3d_available` | boolean | 否 | default=true | — |
| `can_generate` | boolean | 否 | default=false | — |
| `reason` | string / null | 否 | — | 原因 |

<a id="schema-magicclassscenecountout"></a>
## MagicClassSceneCountOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

真实课堂里某一种 scene.type 的数量。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `type` | string | 是 | — | — |
| `count` | integer | 否 | default=0 | — |

<a id="schema-magicclasssessionout"></a>
## MagicClassSessionOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `course_id` | string | 是 | — | 关联课程标识 |
| `mode` | string | 是 | — | — |
| `requested_mode` | string / null | 否 | — | — |
| `adaptive_reason` | string / null | 否 | — | — |
| `job_id` | string / null | 否 | — | 任务标识 |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `step` | string | 是 | — | — |
| `progress` | integer | 否 | default=0 | 进度；对象或数值范围按字段类型 |
| `message` | string | 否 | default="" | — |
| `error` | string / null | 否 | — | — |
| `classroom_id` | string / null | 否 | — | — |
| `url` | string / null | 否 | — | — |
| `url_unavailable_reason` | string / null | 否 | — | — |
| `scenes_count` | integer / null | 否 | — | — |
| `terminal` | boolean | 否 | default=false | — |
| `retryable` | boolean | 否 | default=false | — |
| `partial` | boolean | 否 | default=false | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

<a id="schema-magicclassstatusout"></a>
## MagicClassStatusOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

互动课堂状态契约。

- configured: 后端是否配置了 magicclass（MAGICCLASS_ENABLED + BASE_URL）。
- available:  目标服务**真实可达**且契约指纹通过（不因配置非空就为真）。
- enabled:    == configured and available，客户端据此决定是否展示生成入口。
- unavailable: 配置了但当前连不上（瞬时故障，可重试）。
- incompatible: 能连上但接口契约/版本不匹配（部署问题，重试无用）。
- degraded:   可用，但部分可选能力不可用（见 unavailable_capabilities）。
- embed_origin: **浏览器公开 Origin**，与内部 BASE_URL 分离；未配置时为 None（fail-closed）。
- browser_embed_available: 学生浏览器能否安全内嵌课堂；服务端可认证不代表浏览器可认证。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | 是 | — | 是否启用 |
| `configured` | boolean | 否 | default=false | — |
| `available` | boolean | 否 | default=false | 当前能力是否可用 |
| `incompatible` | boolean | 否 | default=false | — |
| `degraded` | boolean | 否 | default=false | — |
| `compatibility` | string | 否 | default="unknown" | — |
| `compatibility_reason` | string / null | 否 | — | — |
| `service` | string | 否 | default="magicclass" | — |
| `version` | string | 否 | default="" | — |
| `version_source` | string | 否 | default="unknown" | — |
| `version_out_of_range` | boolean | 否 | default=false | — |
| `capabilities` | map<string, boolean> | 否 | additionalProperties={"type": "boolean"} | — |
| `unavailable_capabilities` | array<string> | 否 | — | — |
| `unavailable` | boolean | 否 | default=false | — |
| `embed_origin` | string / null | 否 | — | — |
| `browser_embed_available` | boolean | 否 | default=false | — |
| `browser_embed_reason` | string / null | 否 | — | — |
| `external_3d_available` | boolean | 否 | default=true | — |
| `poll_interval_ms` | integer | 否 | default=5000 | — |
| `poll_max_seconds` | integer | 否 | default=1800 | — |
| `checked_at` | string | 否 | default="" | — |
| `reason` | string / null | 否 | — | 原因 |

<a id="schema-magicclasswidgetcountout"></a>
## MagicClassWidgetCountOut

模型定义：[backend/app/schemas/magicclass.py](../../backend/app/schemas/magicclass.py)。

interactive 场景内部 widgetType 的分布。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `widget_type` | string | 是 | — | — |
| `count` | integer | 否 | default=0 | — |

<a id="schema-manualnoticein"></a>
## ManualNoticeIn

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

POST /notices/manual — 粘贴文本持久化为服务端 notice_id。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `content` | string | 是 | minLength=1; maxLength=5000 | 正文或业务内容，嵌套结构按类型 |
| `source_name` | string / null | 否 | string约束: maxLength=64 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-manualnoticeout"></a>
## ManualNoticeOut

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `notice_id` | string | 是 | minLength=1; maxLength=64 | — |
| `title` | string | 是 | maxLength=256 | 标题 |
| `duplicate` | boolean | 否 | default=false | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-materialdetailout"></a>
## MaterialDetailOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

单份资料，含正文。只有这一条路径会带正文。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `filename` | string | 是 | — | 文件名 |
| `media_type` | string | 否 | default="application/octet-stream" | — |
| `byte_size` | integer | 否 | default=0 | 字节大小 |
| `sha256` | string | 否 | default="" | 内容 SHA256 |
| `extraction_status` | string | 否 | default="unsupported" | — |
| `text_chars` | integer | 否 | default=0 | — |
| `revision` | integer | 否 | default=1 | 当前版本号，条件写入回传 If-Match |
| `created_at` | string / null | 否 | — | 创建时间 |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `deduplicated` | boolean | 否 | default=false | — |
| `text` | string | 否 | default="" | 文本 |

<a id="schema-materialitem"></a>
## MaterialItem

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 材料 ID(便于客户端引用) |
| `name` | string | 是 | — | 材料名称 |
| `required` | boolean | 否 | default=true | — |

<a id="schema-materiallistout"></a>
## MaterialListOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[MaterialOut](schemas.md#schema-materialout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |

<a id="schema-materialout"></a>
## MaterialOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

一份课程资料的元数据。

列表接口**不返回正文**：列表是导航面，把每份文档的正文都带上会让一次列表
的开销随语料规模增长。`text_chars` 是列表真正需要的那个数。
`extraction_status` 只有三种取值，且 `unsupported` 一定没有正文——解析
失败绝不能被伪装成"已提取"。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `filename` | string | 是 | — | 文件名 |
| `media_type` | string | 否 | default="application/octet-stream" | — |
| `byte_size` | integer | 否 | default=0 | 字节大小 |
| `sha256` | string | 否 | default="" | 内容 SHA256 |
| `extraction_status` | string | 否 | default="unsupported" | — |
| `text_chars` | integer | 否 | default=0 | — |
| `revision` | integer | 否 | default=1 | 当前版本号，条件写入回传 If-Match |
| `created_at` | string / null | 否 | — | 创建时间 |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `deduplicated` | boolean | 否 | default=false | — |

<a id="schema-materialreferenceout"></a>
## MaterialReferenceOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

可以被 stage 引用的资料：够渲染和跳转，不含正文。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `filename` | string | 是 | — | 文件名 |
| `media_type` | string | 否 | default="application/octet-stream" | — |
| `extraction_status` | string | 否 | default="unsupported" | — |
| `text_chars` | integer | 否 | default=0 | — |
| `updated_at` | string / null | 否 | — | 最近更新时间 |

<a id="schema-materialresolvein"></a>
## MaterialResolveIn

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

批量解析引用。

上限与服务端的 `MAX_REFERENCE_COUNT` 一致：超限在网关就得到 400，
而不是变成一次昂贵的内部调用。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `material_ids` | array<string> | 否 | maxItems=50 | — |

<a id="schema-materialresolveout"></a>
## MaterialResolveOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

`unresolved` 只说明"没解析到"，不说明为什么。

异用户、异课程、已删除、不存在在这里是同一个答案，否则这个批量接口
就成了"这个 id 是否存在"的探测器。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `resolved` | array<[MaterialReferenceOut](schemas.md#schema-materialreferenceout)> | 否 | — | — |
| `unresolved` | array<string> | 否 | — | — |

<a id="schema-modelcapabilitytransparencyout"></a>
## ModelCapabilityTransparencyOut

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `capability_name` | string | 是 | — | — |
| `capability_version` | string | 是 | — | — |
| `production_method` | string | 是 | — | — |
| `campusmate_lm_status` | enum ["SHADOW_ONLY", "BLOCKED", "ELIGIBLE_FOR_CANARY", "REVOKED"] | 是 | — | — |
| `quality_gate_passed` | boolean | 是 | — | — |
| `performance_gate_passed` | boolean | 是 | — | — |
| `performance_measured` | boolean | 是 | — | — |
| `last_evaluated_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `uses_real_model_inference` | boolean | 是 | — | — |
| `uses_fixed_prediction_file` | boolean | 是 | — | — |

<a id="schema-modellatencystats"></a>
## ModelLatencyStats

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `p50` | number / null | 否 | number约束: minimum=0.0 | — |
| `p95` | number / null | 否 | number约束: minimum=0.0 | — |
| `samples` | integer | 否 | default=0; minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-modelroutepolicy"></a>
## ModelRoutePolicy

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

模型路由策略(§6)。


类型：enum ["reasoning_primary", "fast_structured", "dual_review"]。

```json
{
  "type": "string",
  "enum": [
    "reasoning_primary",
    "fast_structured",
    "dual_review"
  ],
  "title": "ModelRoutePolicy",
  "description": "模型路由策略(§6)。"
}
```

对象级约束：

```json
{
  "enum": [
    "reasoning_primary",
    "fast_structured",
    "dual_review"
  ]
}
```

<a id="schema-modeltransparencyout"></a>
## ModelTransparencyOut

模型定义：[backend/app/schemas/learner_control.py](../../backend/app/schemas/learner_control.py)。

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

<a id="schema-multinoticeextractresponse"></a>
## MultiNoticeExtractResponse

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

多任务抽取响应。

当 allow_multi_task=true 且通知中可识别出多个独立任务时,
返回多个 [NoticeExtractResponse]。无法可靠拆分时返回单个。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `tasks` | array<[NoticeExtractResponse](schemas.md#schema-noticeextractresponse)> | 否 | — | 抽取的任务列表(1 个或多个) |
| `split_reason` | string | 否 | default="" | 拆分说明(如'识别到 2 个独立截止时间'或'合并为单任务') |
| `needs_user_confirmation` | boolean | 否 | default=false | 是否建议用户人工确认拆分结果 |

<a id="schema-narrationin"></a>
## NarrationIn

模型定义：[backend/app/api/routes/magicclass_narration.py](../../backend/app/api/routes/magicclass_narration.py)。

Only identifiers: the script is derived server-side from the scene body.

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `scene_id` | string | 是 | minLength=1; maxLength=192 | 场景标识 |
| `stage_id` | string | 是 | minLength=1; maxLength=192 | 舞台标识 |

<a id="schema-noticebatchingestrequest"></a>
## NoticeBatchIngestRequest

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[NoticeBatchItem](schemas.md#schema-noticebatchitem)> | 是 | minItems=1; maxItems=20 | 列表条目 |

<a id="schema-noticebatchingestresponse"></a>
## NoticeBatchIngestResponse

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[NoticeBatchItemResult](schemas.md#schema-noticebatchitemresult)> | 否 | — | 列表条目 |
| `stats` | map<string, integer> | 否 | additionalProperties={"type": "integer"} | — |

<a id="schema-noticebatchitem"></a>
## NoticeBatchItem

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `client_id` | string | 是 | minLength=1; maxLength=200 | — |
| `client_fingerprint` | string | 是 | minLength=16; maxLength=128 | — |
| `source_name` | string | 是 | minLength=1; maxLength=200 | — |
| `published_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `messages` | array<[NoticeBatchMessage](schemas.md#schema-noticebatchmessage)> | 是 | minItems=1; maxItems=20 | — |

<a id="schema-noticebatchitemresult"></a>
## NoticeBatchItemResult

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `client_id` | string | 是 | — | — |
| `client_fingerprint` | string | 是 | — | — |
| `status` | string | 是 | pattern="^(completed\|ignored\|retryable\|failed)$" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `semantic_type` | [NoticeSemanticType](schemas.md#schema-noticesemantictype) | 是 | — | — |
| `notice_created` | boolean | 否 | default=false | — |
| `tasks_created` | integer | 否 | default=0 | — |
| `duplicate` | boolean | 否 | default=false | — |
| `extraction` | [MultiNoticeExtractResponse](schemas.md#schema-multinoticeextractresponse) / null | 否 | — | — |
| `reason` | string / null | 否 | — | 原因 |

<a id="schema-noticebatchmessage"></a>
## NoticeBatchMessage

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | minLength=1; maxLength=5000 | 文本 |
| `published_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |

<a id="schema-noticeextractrequest"></a>
## NoticeExtractRequest

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | — | 校园通知原文 |
| `published_at` | string (date-time) / null | 否 | string约束: format="date-time" | 通知发布时间(ISO 8601，带时区) |
| `source_name` | string / null | 否 | — | 来源单位/系统名称 |
| `allow_multi_task` | boolean | 否 | default=true | 是否允许拆分为多个任务(默认 True,无法可靠拆分时返回单任务) |

对象级约束：

```json
{
  "example": {
    "allow_multi_task": true,
    "content": "请2024级学生于7月30日前填写实践申请表,并将申请表和证明材料提交至学院办公室。",
    "published_at": "2026-07-20T09:00:00+08:00",
    "source_name": "信息工程学院通知"
  }
}
```

<a id="schema-noticeextractresponse"></a>
## NoticeExtractResponse

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | — | 通知标题/任务名(可为空字符串) |
| `task` | string | 是 | — | 任务名(对齐移动端 taskName) |
| `actionable` | boolean | 否 | default=false | 是否是明确需要学生执行的行动型通知(普通公告为 false) |
| `target_students` | string / null | 否 | — | 面向对象 |
| `deadline` | string (date-time) / null | 否 | string约束: format="date-time" | 截止时间(ISO 8601) |
| `materials` | array<[MaterialItem](schemas.md#schema-materialitem)> | 否 | — | — |
| `submission_method` | string / null | 否 | — | 提交方式 |
| `location` | string / null | 否 | — | 办理地点 |
| `source_name` | string / null | 否 | — | 来源单位 |
| `source_text` | string | 是 | — | 通知原文(便于人工复核) |
| `importance` | string | 否 | default="unknown" | 重要程度: urgent\|high\|important\|normal\|low\|unknown |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | 抽取置信度 0~1 |
| `needs_confirmation` | boolean | 是 | — | 是否需要人工确认(年份缺失/对象不明等) |
| `warnings` | array<string> | 否 | — | 需要确认的原因列表(温和提示，非错误) |
| `extracted_at` | string (date-time) | 是 | format="date-time" | 抽取完成时间(ISO 8601) |
| `extractor_mode` | string | 是 | — | 抽取器模式: llm\|rules (便于客户端区分) |

对象级约束：

```json
{
  "example": {
    "confidence": 0.82,
    "deadline": "2026-07-30T23:59:00+08:00",
    "extracted_at": "2026-07-25T10:00:00+08:00",
    "extractor_mode": "rules",
    "importance": "important",
    "location": "学院办公室",
    "materials": [
      {
        "id": "m_1",
        "name": "申请表",
        "required": true
      },
      {
        "id": "m_2",
        "name": "证明材料",
        "required": true
      }
    ],
    "needs_confirmation": false,
    "source_name": "信息工程学院通知",
    "source_text": "...",
    "submission_method": "提交纸质版",
    "target_students": "2024级",
    "task": "提交实践申请",
    "title": "提交实践申请",
    "warnings": []
  }
}
```

<a id="schema-noticeout"></a>
## NoticeOut

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

校园通知列表项 —— 聚合自当前用户可见班级的已发布通知。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `title` | string | 是 | — | 标题 |
| `source` | string / null | 否 | default=null | 来源(班级名 / 课程名 / 作者) |
| `time` | string / null | 否 | default=null | 发布时间(ISO 8601) |
| `unread` | boolean | 否 | default=false | 当前学生视角是否未读 |
| `category` | string / null | 否 | default=null | 分类(课程名等) |
| `content` | string / null | 否 | default=null | 通知正文 |
| `kind` | string | 否 | default="announcement"; pattern="^(announcement\|unified)$" | — |
| `source_url` | string / null | 否 | default=null | 原始通知链接 |

<a id="schema-noticesemantictype"></a>
## NoticeSemanticType

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。


类型：enum ["CHAT", "NOTICE", "ACTIONABLE_NOTICE", "AMBIGUOUS"]。

```json
{
  "type": "string",
  "enum": [
    "CHAT",
    "NOTICE",
    "ACTIONABLE_NOTICE",
    "AMBIGUOUS"
  ],
  "title": "NoticeSemanticType"
}
```

对象级约束：

```json
{
  "enum": [
    "CHAT",
    "NOTICE",
    "ACTIONABLE_NOTICE",
    "AMBIGUOUS"
  ]
}
```

<a id="schema-notificationsourceout"></a>
## NotificationSourceOut

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `source_id` | string | 是 | minLength=1; maxLength=64 | — |
| `code` | string | 是 | minLength=1; maxLength=64 | — |
| `display_name` | string | 是 | maxLength=128 | — |
| `kind` | string | 是 | maxLength=32 | — |
| `automation_enabled` | boolean | 否 | default=false | — |
| `permission_scope` | string / null | 否 | string约束: maxLength=256 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-notificationsourcepatchin"></a>
## NotificationSourcePatchIn

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `automation_enabled` | boolean / null | 否 | — | — |
| `display_name` | string / null | 否 | string约束: maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-observedlearningactivityvalue"></a>
## ObservedLearningActivityValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_sessions_7d` | integer | 是 | minimum=0.0 | — |
| `observed_sessions_30d` | integer | 是 | minimum=0.0 | — |
| `observed_study_seconds_7d` | integer | 是 | minimum=0.0 | — |
| `observed_study_seconds_30d` | integer | 是 | minimum=0.0 | — |
| `observed_completed_tasks_7d` | integer | 是 | minimum=0.0 | — |
| `observed_completed_tasks_30d` | integer | 是 | minimum=0.0 | — |
| `last_observed_activity_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-page"></a>
## Page

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

统一分页响应。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<any> | 否 | — | 列表条目 |
| `total` | integer | 否 | default=0 | 总数 |
| `page` | integer | 否 | default=1 | 当前页，从 1 开始 |
| `page_size` | integer | 否 | default=20 | 每页数量 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

<a id="schema-pausedatasourceintervention"></a>
## PauseDataSourceIntervention

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `intervention_type` | const "PAUSE_DATA_SOURCE" | 否 | default="PAUSE_DATA_SOURCE" | — |
| `source_category` | enum ["academic", "chaoxing", "notice", "study_session", "manual"] | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-personalfilecreate"></a>
## PersonalFileCreate

模型定义：[backend/app/schemas/personal_hub.py](../../backend/app/schemas/personal_hub.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=256 | 名称 |
| `category` | string / null | 否 | string约束: maxLength=64 | — |
| `source` | string / null | 否 | string约束: maxLength=128 | 来源 |
| `size_label` | string / null | 否 | string约束: maxLength=32 | — |

<a id="schema-personalfileout"></a>
## PersonalFileOut

模型定义：[backend/app/schemas/personal_hub.py](../../backend/app/schemas/personal_hub.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `name` | string | 是 | — | 名称 |
| `category` | string / null | 否 | — | — |
| `size_label` | string / null | 否 | — | — |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `source` | string / null | 否 | — | 来源 |
| `is_favorite` | boolean | 否 | default=false | — |

<a id="schema-personalfileupdate"></a>
## PersonalFileUpdate

模型定义：[backend/app/schemas/personal_hub.py](../../backend/app/schemas/personal_hub.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=256 | 名称 |
| `category` | string / null | 否 | string约束: maxLength=64 | — |
| `source` | string / null | 否 | string约束: maxLength=128 | 来源 |
| `size_label` | string / null | 否 | string约束: maxLength=32 | — |

<a id="schema-personaltaskcreate"></a>
## PersonalTaskCreate

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

创建个人待办请求。

`source_text` 强烈建议保留(用于原文追溯),但允许手动创建场景下为空。
`id` 由后端生成,客户端不传;客户端临时 ID 可通过 `client_request_id` 去重(预留)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `description` | string / null | 否 | string约束: maxLength=4000 | 说明 |
| `target_students` | string / null | 否 | string约束: maxLength=512 | 通知面向对象(如 '2024级各班') |
| `deadline` | string / null | 否 | — | ISO 8601 截止时间(带时区) |
| `materials` | array<string> / null | 否 | array约束: maxItems=50 | 所需材料名称列表 |
| `submission_method` | string / null | 否 | string约束: maxLength=256 | — |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `source_name` | string / null | 否 | string约束: maxLength=256 | 通知来源(如 '教务处') |
| `source_text` | string / null | 否 | string约束: maxLength=10000 | 原通知全文(用于追溯) |
| `source_notice_id` | string / null | 否 | string约束: maxLength=128 | 关联通知 ID(可为空) |
| `priority` | string | 否 | default="medium"; pattern="^(low\|medium\|high)$" | — |
| `importance` | string / null | 否 | default="unknown"; string约束: pattern="^(urgent\|high\|important\|normal\|low\|unknown)$" | AI 评定的重要程度标签(交作业=high,填表=low) |
| `reminder_minutes` | integer / null | 否 | integer约束: minimum=0.0; maximum=43200.0 | 提前提醒分钟数(0 表示按 deadline 精确触发) |

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator(*_TEXT_FIELDS)
@classmethod
def validate_text_integrity(cls, value: Optional[str]) -> Optional[str]:
    return _validate_text_integrity(value)
```

```python
@field_validator('materials')
@classmethod
def validate_materials_integrity(cls, value: Optional[List[str]]) -> Optional[List[str]]:
    return _validate_materials_integrity(value)
```

<a id="schema-personaltaskout"></a>
## PersonalTaskOut

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

个人待办响应。

`status` 取值: pending / completed / deleted。
`materials` 解析为字符串数组返回(后端以 JSON 字符串存储)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `target_students` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> | 否 | — | — |
| `submission_method` | string / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `source_name` | string / null | 否 | — | — |
| `source_text` | string / null | 否 | — | — |
| `source_notice_id` | string / null | 否 | — | — |
| `priority` | string | 是 | — | — |
| `importance` | string | 否 | default="unknown" | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `reminder_minutes` | integer / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `external_id` | string / null | 否 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `completed_at` | string / null | 否 | — | — |
| `deleted_at` | string / null | 否 | — | — |

<a id="schema-personaltaskupdate"></a>
## PersonalTaskUpdate

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

部分更新。所有字段可选。

注意: `completed_at` / `deleted_at` / `status` 不通过此接口修改,
请使用 `/complete` / `/restore` / `DELETE` 接口。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string / null | 否 | string约束: minLength=1; maxLength=256 | 标题 |
| `description` | string / null | 否 | string约束: maxLength=4000 | 说明 |
| `target_students` | string / null | 否 | string约束: maxLength=512 | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> / null | 否 | array约束: maxItems=50 | — |
| `submission_method` | string / null | 否 | string约束: maxLength=256 | — |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `source_name` | string / null | 否 | string约束: maxLength=256 | — |
| `source_text` | string / null | 否 | string约束: maxLength=10000 | — |
| `source_notice_id` | string / null | 否 | string约束: maxLength=128 | — |
| `priority` | string / null | 否 | string约束: pattern="^(low\|medium\|high)$" | — |
| `importance` | string / null | 否 | string约束: pattern="^(urgent\|high\|important\|normal\|low\|unknown)$" | — |
| `reminder_minutes` | integer / null | 否 | integer约束: minimum=0.0; maximum=43200.0 | — |

补充业务校验（OpenAPI 字段约束之外，直接列出模型校验规则）：

```python
@field_validator(*_TEXT_FIELDS)
@classmethod
def validate_text_integrity(cls, value: Optional[str]) -> Optional[str]:
    return _validate_text_integrity(value)
```

```python
@field_validator('materials')
@classmethod
def validate_materials_integrity(cls, value: Optional[List[str]]) -> Optional[List[str]]:
    return _validate_materials_integrity(value)
```

<a id="schema-plangeneratein"></a>
## PlanGenerateIn

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

生成计划请求。可选编辑偏好。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_edits` | object / null | 否 | — | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-plangenerateout"></a>
## PlanGenerateOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

生成计划结果。可能需要审批。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | — | 运行标识 |
| `version` | integer | 是 | — | — |
| `plan` | object | 是 | — | — |
| `risk_level` | string | 是 | — | — |
| `requires_approval` | boolean | 是 | — | — |
| `approval_id` | string / null | 否 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-planversionout"></a>
## PlanVersionOut

模型定义：[backend/app/schemas/final_review.py](../../backend/app/schemas/final_review.py)。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-postcreate"></a>
## PostCreate

模型定义：[backend/app/schemas/community.py](../../backend/app/schemas/community.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=120 | 标题 |
| `content` | string | 是 | minLength=1; maxLength=10000 | 正文或业务内容，嵌套结构按类型 |
| `category` | string | 否 | default="campus"; pattern="^(campus\|study\|life\|secondhand\|question\|activity\|experience\|recruit\|errand\|other)$" | — |
| `images` | array<string> | 否 | maxItems=9 | — |
| `is_anonymous` | boolean | 否 | default=false | — |
| `extra` | object / null | 否 | — | — |

<a id="schema-postupdate"></a>
## PostUpdate

模型定义：[backend/app/schemas/community.py](../../backend/app/schemas/community.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string / null | 否 | string约束: minLength=1; maxLength=120 | 标题 |
| `content` | string / null | 否 | string约束: minLength=1; maxLength=10000 | 正文或业务内容，嵌套结构按类型 |
| `category` | string / null | 否 | string约束: pattern="^(campus\|study\|life\|secondhand\|question\|activity\|experience\|recruit\|errand\|other)$" | — |
| `images` | array<string> / null | 否 | array约束: maxItems=9 | — |
| `is_anonymous` | boolean / null | 否 | — | — |
| `extra` | object / null | 否 | — | — |

<a id="schema-preferenceprofilevalue"></a>
## PreferenceProfileValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `reminder_frequency` | enum ["unset", "minimal", "normal", "frequent"] | 否 | default="unset" | — |
| `quiet_hours_enabled` | boolean | 否 | default=false | — |
| `daily_plan_capacity_minutes` | integer | 否 | default=0; minimum=0.0; maximum=1440.0 | — |
| `preferred_focus_slot` | enum ["unset", "morning", "afternoon", "evening", "night"] | 否 | default="unset" | — |
| `detail_level` | enum ["unset", "brief", "standard", "detailed"] | 否 | default="unset" | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-profileuniversityout"></a>
## ProfileUniversityOut

模型定义：[backend/app/schemas/university.py](../../backend/app/schemas/university.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string / null | 否 | — | — |
| `university` | [UniversityOut](schemas.md#schema-universityout) / null | 否 | — | — |

<a id="schema-profileuniversityupdate"></a>
## ProfileUniversityUpdate

模型定义：[backend/app/schemas/university.py](../../backend/app/schemas/university.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string / null | 是 | string约束: minLength=1; maxLength=128 | — |

<a id="schema-qrcancelrequest"></a>
## QrCancelRequest

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | minLength=16; maxLength=64 | — |
| `scan_token` | string | 是 | minLength=32; maxLength=128 | — |

<a id="schema-qrconfirmrequest"></a>
## QrConfirmRequest

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | minLength=16; maxLength=64 | — |
| `scan_token` | string | 是 | minLength=32; maxLength=128 | — |
| `trust_device` | boolean | 否 | default=false | — |

<a id="schema-qrconfirmresponse"></a>
## QrConfirmResponse

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `status` | string | 否 | default="CONFIRMED" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `trust_device` | boolean | 是 | — | — |

<a id="schema-qrcreaterequest"></a>
## QrCreateRequest

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `device_id` | string / null | 否 | string约束: maxLength=128 | 浏览器生成的设备标识 |
| `browser_name` | string / null | 否 | string约束: maxLength=64 | — |
| `os_name` | string / null | 否 | string约束: maxLength=64 | — |

<a id="schema-qrcreateresponse"></a>
## QrCreateResponse

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `qr_payload` | string | 是 | — | 二维码内容字符串 |
| `browser_token` | string | 是 | — | 浏览器兑换凭据，不写入二维码 |
| `status` | string | 否 | default="PENDING" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `expires_at` | string | 是 | — | — |
| `expires_in` | integer | 是 | — | 剩余有效期(秒) |

<a id="schema-qrexchangerequest"></a>
## QrExchangeRequest

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | minLength=16; maxLength=64 | — |
| `browser_token` | string | 是 | minLength=32; maxLength=128 | — |

<a id="schema-qrscanrequest"></a>
## QrScanRequest

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | minLength=16; maxLength=64 | — |
| `scan_token` | string | 是 | minLength=32; maxLength=128 | — |

<a id="schema-qrscanresponse"></a>
## QrScanResponse

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `browser_name` | string / null | 否 | — | — |
| `os_name` | string / null | 否 | — | — |
| `device_label` | string / null | 否 | — | — |
| `expires_at` | string | 是 | — | — |
| `status` | string | 否 | default="SCANNED" | 业务状态，合法取值和操作前置条件见枚举及流程 |

<a id="schema-qrstatusresponse"></a>
## QrStatusResponse

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `expires_at` | string | 是 | — | — |

<a id="schema-quizattemptin"></a>
## QuizAttemptIn

模型定义：[backend/app/schemas/magicclass_quiz.py](../../backend/app/schemas/magicclass_quiz.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `attempt_id` | string | 是 | minLength=1; maxLength=128 | — |
| `phase` | enum ["draft", "submitted", "reviewed"] | 是 | — | — |
| `answers` | map<string, string / array<string>> | 否 | additionalProperties={"anyOf": [{"type": "string"}, {"items": {"type": "string"}, "type": "array"}]} | — |
| `results` | array<object> | 否 | — | — |
| `start_new_attempt` | boolean | 否 | default=false | — |

<a id="schema-quizattemptstateout"></a>
## QuizAttemptStateOut

模型定义：[backend/app/schemas/magicclass_quiz.py](../../backend/app/schemas/magicclass_quiz.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `attempt_id` | string | 是 | — | — |
| `state` | object / null | 否 | — | — |

<a id="schema-rebuildresponse"></a>
## RebuildResponse

模型定义：[backend/app/schemas/knowledge.py](../../backend/app/schemas/knowledge.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | 是 | — | — |
| `document_count` | integer | 是 | — | — |
| `chunk_count` | integer | 是 | — | — |
| `message` | string | 是 | — | — |

<a id="schema-recentnoticeitem"></a>
## RecentNoticeItem

模型定义：[backend/app/schemas/notice.py](../../backend/app/schemas/notice.py)。

客户端传入的最近通知项(用于重复检测对比)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `notice_id` | string | 是 | — | 已存在通知 ID |
| `title` | string / null | 否 | — | 已存在通知标题 |
| `task` | string / null | 否 | — | 已存在任务名 |
| `source_name` | string / null | 否 | — | — |
| `source_text` | string / null | 否 | — | 通知原文(用于内容哈希对比) |
| `deadline` | string (date-time) / null | 否 | string约束: format="date-time" | 截止时间 |

<a id="schema-recruitextra"></a>
## RecruitExtra

模型定义：[backend/app/schemas/community.py](../../backend/app/schemas/community.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `headcount` | integer / null | 否 | default=null; integer约束: minimum=1; maximum=100 | — |
| `deadline` | string / null | 否 | default=null; string约束: maxLength=32 | 截止时间 |
| `location` | string / null | 否 | default=null; string约束: maxLength=200 | — |

<a id="schema-reducedailyloadintervention"></a>
## ReduceDailyLoadIntervention

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `intervention_type` | const "REDUCE_DAILY_LOAD" | 否 | default="REDUCE_DAILY_LOAD" | — |
| `reduce_minutes_per_day` | integer | 是 | minimum=0.0; maximum=480.0 | — |
| `target_date` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `movable_task_policy` | const "PERSONAL_ONLY" | 否 | default="PERSONAL_ONLY" | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-refreshrequest"></a>
## RefreshRequest

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `refresh_token` | string | 是 | minLength=1 | 换发令牌；不是业务访问凭据 |

<a id="schema-registerrequest"></a>
## RegisterRequest

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

公开注册请求(无需鉴权,仅限 student 自注册)。

约束:
- username: 3-64 字符,仅字母/数字/下划线
- password: 8-128 字符
- role: 仅允许 student(admin 必须由管理员创建)
- display_name: 选填,≤128 字符
- student_number: 选填,学生学号
- college / major / grade: 选填,学生常用

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=3; maxLength=64; pattern="^[a-zA-Z0-9_]+$" | 登录用户名 |
| `password` | string | 是 | minLength=8; maxLength=128 | 登录密码，仅请求使用 |
| `role` | string | 否 | default="student"; pattern="^(student)$" | — |
| `display_name` | string / null | 否 | string约束: maxLength=128 | — |
| `student_number` | string / null | 否 | string约束: maxLength=32 | — |
| `teacher_number` | string / null | 否 | string约束: maxLength=32 | 已废弃,仅为兼容旧数据保留 |
| `college` | string / null | 否 | string约束: maxLength=64 | — |
| `major` | string / null | 否 | string约束: maxLength=64 | — |
| `grade` | string / null | 否 | string约束: maxLength=32 | — |

<a id="schema-reportcreate"></a>
## ReportCreate

模型定义：[backend/app/schemas/community.py](../../backend/app/schemas/community.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `target_type` | string | 是 | pattern="^(post\|comment)$" | — |
| `target_id` | string | 是 | minLength=1; maxLength=128 | — |
| `reason` | string | 是 | pattern="^(垃圾广告\|辱骂攻击\|色情低俗\|违法违规\|隐私泄露\|诈骗\|其它)$" | 原因 |
| `details` | string / null | 否 | string约束: maxLength=1000 | — |

<a id="schema-rescheduletaskintervention"></a>
## RescheduleTaskIntervention

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `intervention_type` | const "RESCHEDULE_TASK" | 否 | default="RESCHEDULE_TASK" | — |
| `task_id` | string | 是 | minLength=1; maxLength=128 | — |
| `new_deadline` | string (date-time) | 是 | format="date-time" | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-researchsourceout"></a>
## ResearchSourceOut

模型定义：[backend/app/schemas/course_research.py](../../backend/app/schemas/course_research.py)。

研究来源输出。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `source_id` | string | 是 | minLength=1; maxLength=64 | — |
| `source_type` | string | 是 | pattern="^(course_material\|web\|user_upload)$" | — |
| `title` | string | 是 | maxLength=512 | 标题 |
| `url` | string / null | 否 | string约束: maxLength=2048 | — |
| `snippet` | string / null | 否 | string约束: maxLength=2000 | — |
| `source_ref` | string / null | 否 | string约束: maxLength=512 | — |
| `accessed_at` | string | 是 | minLength=1; maxLength=64 | — |
| `is_verified` | boolean | 否 | default=false | — |
| `verification_note` | string / null | 否 | string约束: maxLength=512 | — |
| `supports_claim` | boolean / null | 否 | — | — |
| `is_fabricated` | boolean | 否 | default=false | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-risklevel"></a>
## RiskLevel

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

动作风险分级(§5.5)。


类型：enum ["AUTO_SAFE", "CONFIRM_REQUIRED", "MANUAL_ONLY"]。

```json
{
  "type": "string",
  "enum": [
    "AUTO_SAFE",
    "CONFIRM_REQUIRED",
    "MANUAL_ONLY"
  ],
  "title": "RiskLevel",
  "description": "动作风险分级(§5.5)。"
}
```

对象级约束：

```json
{
  "enum": [
    "AUTO_SAFE",
    "CONFIRM_REQUIRED",
    "MANUAL_ONLY"
  ]
}
```

<a id="schema-routinecontinuityvalue"></a>
## RoutineContinuityValue

模型定义：[backend/app/schemas/forecast.py](../../backend/app/schemas/forecast.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_session_count` | integer | 是 | minimum=0.0 | — |
| `median_interval_hours` | number | 是 | minimum=0.0 | — |
| `continuity_band` | enum ["stable", "variable", "unknown"] | 是 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-runphase"></a>
## RunPhase

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

Run 当前阶段,独立于 RunStatus(§5.6)。


类型：enum ["CONTEXT_BUILDING", "WAITING_FOR_MODEL", "VALIDATING_OUTPUT", "WAITING_FOR_TOOL", "WAITING_FOR_APPROVAL", "PERSISTING_RESULT", "RECOVERY_CHECKING", "IDLE", "STATE_ANALYSIS", "STRATEGY_SELECTION", "INTERVENTION_RECORD", "PLAN_GENERATION"]。

```json
{
  "type": "string",
  "enum": [
    "CONTEXT_BUILDING",
    "WAITING_FOR_MODEL",
    "VALIDATING_OUTPUT",
    "WAITING_FOR_TOOL",
    "WAITING_FOR_APPROVAL",
    "PERSISTING_RESULT",
    "RECOVERY_CHECKING",
    "IDLE",
    "STATE_ANALYSIS",
    "STRATEGY_SELECTION",
    "INTERVENTION_RECORD",
    "PLAN_GENERATION"
  ],
  "title": "RunPhase",
  "description": "Run 当前阶段,独立于 RunStatus(§5.6)。"
}
```

对象级约束：

```json
{
  "enum": [
    "CONTEXT_BUILDING",
    "WAITING_FOR_MODEL",
    "VALIDATING_OUTPUT",
    "WAITING_FOR_TOOL",
    "WAITING_FOR_APPROVAL",
    "PERSISTING_RESULT",
    "RECOVERY_CHECKING",
    "IDLE",
    "STATE_ANALYSIS",
    "STRATEGY_SELECTION",
    "INTERVENTION_RECORD",
    "PLAN_GENERATION"
  ]
}
```

<a id="schema-runstatus"></a>
## RunStatus

模型定义：[backend/app/schemas/agent_contract_enums.py](../../backend/app/schemas/agent_contract_enums.py)。

Run 生命周期状态(§5.6)。


类型：enum ["QUEUED", "RUNNING", "AWAITING_APPROVAL", "PAUSED", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"]。

```json
{
  "type": "string",
  "enum": [
    "QUEUED",
    "RUNNING",
    "AWAITING_APPROVAL",
    "PAUSED",
    "SUCCEEDED",
    "PARTIAL",
    "FAILED",
    "CANCELLED"
  ],
  "title": "RunStatus",
  "description": "Run 生命周期状态(§5.6)。"
}
```

对象级约束：

```json
{
  "enum": [
    "QUEUED",
    "RUNNING",
    "AWAITING_APPROVAL",
    "PAUSED",
    "SUCCEEDED",
    "PARTIAL",
    "FAILED",
    "CANCELLED"
  ]
}
```

<a id="schema-runtraceapproval"></a>
## RunTraceApproval

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `approval_id` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `risk_level` | string | 是 | — | — |
| `action_summary` | string | 是 | — | — |
| `wait_ms` | number / null | 否 | number约束: minimum=0.0 | — |
| `expires_at` | string | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-runtraceevent"></a>
## RunTraceEvent

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sequence` | integer | 是 | minimum=0.0 | — |
| `type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `phase` | string | 是 | — | — |
| `role` | string / null | 否 | — | — |
| `summary` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-runtraceheader"></a>
## RunTraceHeader

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | string | 是 | — | 运行标识 |
| `job_id` | string | 是 | — | 任务标识 |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `phase` | string | 是 | — | — |
| `risk_level` | string / null | 否 | — | — |
| `handler_code` | string / null | 否 | — | — |
| `handler_version` | string / null | 否 | — | — |
| `attempt_no` | integer | 否 | default=0; minimum=0.0 | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `started_at` | string / null | 否 | — | — |
| `finished_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `duration_ms` | number / null | 否 | number约束: minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-runtracemodelcall"></a>
## RunTraceModelCall

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `call_id` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `model` | string | 是 | — | — |
| `route_policy` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `latency_ms` | integer / null | 否 | — | — |
| `total_tokens` | integer / null | 否 | — | — |
| `started_at` | string | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-runtracetoolcall"></a>
## RunTraceToolCall

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `call_id` | string | 是 | — | — |
| `tool_name` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `started_at` | string | 是 | — | — |
| `finished_at` | string / null | 否 | — | — |
| `duration_ms` | number / null | 否 | number约束: minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-sceneoutlineout"></a>
## SceneOutlineOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

场景目录项：**不含场景正文**（列表是导航面）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `type` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `order` | integer | 是 | — | — |
| `actions` | integer | 否 | default=0 | — |
| `updated_at` | integer / null | 否 | — | 最近更新时间 |

<a id="schema-sceneplaybackout"></a>
## ScenePlaybackOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

一个场景的播放决定。

`render.kind` 是**唯一**判据：`native` 由 CampusMate 自己渲染，
`sandbox-*` 才允许放进受限 iframe，`unsupported` 表示这一次真的渲染不了，
必须带上 `reason` 说明缺什么，而不是显示成空白。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `type` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `order` | integer | 是 | — | — |
| `render` | object | 是 | — | — |
| `steps` | array<object> | 否 | — | — |
| `dropped_actions` | array<object> | 否 | — | — |
| `whiteboards` | integer | 否 | default=0 | — |
| `multi_agent` | boolean | 否 | default=false | — |

<a id="schema-scheduleconflictitem"></a>
## ScheduleConflictItem

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | enum ["overlap", "gap"] | 是 | — | — |
| `start` | string (date-time) | 是 | format="date-time" | — |
| `end` | string (date-time) | 是 | format="date-time" | — |
| `overlap_minutes` | integer | 是 | minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-scheduleconflictriskvalue"></a>
## ScheduleConflictRiskValue

模型定义：[backend/app/schemas/forecast.py](../../backend/app/schemas/forecast.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `conflict_count` | integer | 是 | minimum=0.0 | — |
| `exam_collision_count` | integer | 是 | minimum=0.0 | — |
| `schedule_overlap_count` | integer | 是 | minimum=0.0 | — |
| `available_window_count` | integer | 是 | minimum=0.0 | — |
| `risk_band` | enum ["LOW", "MODERATE", "HIGH", "VERY_HIGH"] | 是 | — | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-scheduleconflictvalue"></a>
## ScheduleConflictValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `conflict_count` | integer | 是 | minimum=0.0 | — |
| `conflicts` | array<[ScheduleConflictItem](schemas.md#schema-scheduleconflictitem)> | 否 | maxItems=16 | — |
| `available_window_count` | integer | 是 | minimum=0.0 | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-scheduleloadvalue"></a>
## ScheduleLoadValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `future_7d_course_density` | number | 是 | minimum=0.0 | — |
| `high_density_periods` | array<string> | 否 | maxItems=16 | — |
| `density_description` | string | 否 | default="observed"; maxLength=64 | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-searchhitout"></a>
## SearchHitOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

一条搜索命中。

`path` 是 CampusMate 站内深链，服务端生成，客户端不得自行拼接。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | enum ["workspace", "stage"] | 是 | — | — |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `stage_id` | string / null | 否 | — | 舞台标识 |
| `title` | string | 是 | — | 标题 |
| `snippet` | string | 否 | default="" | — |
| `folder_id` | string / null | 否 | — | — |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `path` | string | 是 | — | — |

<a id="schema-searchlistout"></a>
## SearchListOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[SearchHitOut](schemas.md#schema-searchhitout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |
| `query` | string | 是 | — | 查询内容 |

<a id="schema-simulationrequest"></a>
## SimulationRequest

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `baseline_run_id` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| `intervention` | [AllocateFocusMinutesIntervention](schemas.md#schema-allocatefocusminutesintervention) / [RescheduleTaskIntervention](schemas.md#schema-rescheduletaskintervention) / [AcceptPlanIntervention](schemas.md#schema-acceptplanintervention) / [ReduceDailyLoadIntervention](schemas.md#schema-reducedailyloadintervention) / [PauseDataSourceIntervention](schemas.md#schema-pausedatasourceintervention) / [AdjustGoalDeadlineIntervention](schemas.md#schema-adjustgoaldeadlineintervention) | 是 | — | — |
| `horizon_days` | integer | 否 | default=7; minimum=1.0; maximum=30.0 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-simulationresponse"></a>
## SimulationResponse

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-sourcepolicyin"></a>
## SourcePolicyIn

模型定义：[backend/app/schemas/course_research.py](../../backend/app/schemas/course_research.py)。

来源策略(硬约束)。

- course_material_priority: 课程资料优先(先检索已有课程素材)
- allow_web: 是否允许公共 Web 检索(禁用时绝不搜索 Web)
- allow_user_upload: 是否允许用户上传作为来源

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_material_priority` | boolean | 否 | default=true | — |
| `allow_web` | boolean | 否 | default=true | — |
| `allow_user_upload` | boolean | 否 | default=true | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-sourcepolicyout"></a>
## SourcePolicyOut

模型定义：[backend/app/schemas/course_research.py](../../backend/app/schemas/course_research.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_material_priority` | boolean | 否 | default=true | — |
| `allow_web` | boolean | 否 | default=true | — |
| `allow_user_upload` | boolean | 否 | default=true | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-stagecommandresultout"></a>
## StageCommandResultOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

命令应用后的 stage，附带本次实际应用了多少条命令。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `document` | object | 否 | — | — |
| `applied_commands` | integer | 否 | default=0 | — |
| `migrated` | boolean | 否 | default=false | — |

<a id="schema-stagecommandsin"></a>
## StageCommandsIn

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

编辑器提交的**命令列表**，不是整份文档。

整份 PUT 会让没看到并发修改的作者静默回退别人的改动；命令列表由服务端
作用在它刚读到的行上。上限与服务端的 `maxCommandsPerRequest` 保持一致，
这样超限在网关就得到 400，而不是变成一次昂贵的内部调用。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `commands` | array<object> | 是 | minItems=1; maxItems=50 | — |

<a id="schema-stagecreatein"></a>
## StageCreateIn

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=200 | 标题 |
| `document` | object / null | 否 | — | — |

<a id="schema-stagelistout"></a>
## StageListOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[StageSummaryOut](schemas.md#schema-stagesummaryout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |

<a id="schema-stageout"></a>
## StageOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

单个 stage，带完整 DSL 文档。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `document` | object | 否 | — | — |

<a id="schema-stageoutlineout"></a>
## StageOutlineOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `stage_id` | string | 是 | — | 舞台标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `scenes` | array<[SceneOutlineOut](schemas.md#schema-sceneoutlineout)> | 否 | — | — |

<a id="schema-stageplaybackout"></a>
## StagePlaybackOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `stage_id` | string | 是 | — | 舞台标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `start_index` | integer | 否 | default=0 | — |
| `scenes` | array<[ScenePlaybackOut](schemas.md#schema-sceneplaybackout)> | 否 | — | — |
| `degraded` | array<object> | 否 | — | — |

<a id="schema-stagereplacein"></a>
## StageReplaceIn

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `document` | object | 是 | — | — |
| `title` | string / null | 否 | string约束: minLength=1; maxLength=200 | 标题 |

<a id="schema-stagesummaryout"></a>
## StageSummaryOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

列表里的 stage。**不含 document**：列表是导航面，打开时才取全文。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

<a id="schema-studentdashboard"></a>
## StudentDashboard

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enrolled_course_count` | integer | 是 | — | — |
| `unread_announcement_count` | integer | 是 | — | — |
| `pending_assignment_count` | integer | 是 | — | — |
| `overdue_assignment_count` | integer | 是 | — | — |
| `due_soon_assignments` | array<object> | 否 | — | — |
| `recent_announcements` | array<object> | 否 | — | — |
| `pending_personal_task_count` | integer | 否 | default=0 | — |
| `overdue_personal_task_count` | integer | 否 | default=0 | — |
| `due_soon_personal_tasks` | array<object> | 否 | — | — |

<a id="schema-studentgoalcreate"></a>
## StudentGoalCreate

模型定义：[backend/app/schemas/student_goal.py](../../backend/app/schemas/student_goal.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=200 | 名称 |
| `category` | enum ["academic", "research", "competition", "certificate", "job_search", "internship", "campus_affair", "health_habit", "personal_growth"] | 是 | — | — |
| `target_date` | string / null | 否 | string约束: maxLength=32 | — |
| `idempotency_key` | string / null | 否 | string约束: maxLength=128 | — |
| `initial_progress_percent` | number | 否 | default=0.0; minimum=0.0; maximum=100.0 | — |
| `milestone_count` | integer | 否 | default=0; minimum=0.0; maximum=100.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studentgoalcreateresult"></a>
## StudentGoalCreateResult

模型定义：[backend/app/schemas/student_goal.py](../../backend/app/schemas/student_goal.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal` | [StudentGoalOut](schemas.md#schema-studentgoalout) | 是 | — | — |
| `created` | boolean | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studentgoalout"></a>
## StudentGoalOut

模型定义：[backend/app/schemas/student_goal.py](../../backend/app/schemas/student_goal.py)。

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

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studentgoalpage"></a>
## StudentGoalPage

模型定义：[backend/app/schemas/student_goal.py](../../backend/app/schemas/student_goal.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[StudentGoalOut](schemas.md#schema-studentgoalout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studentgoalprogresscreate"></a>
## StudentGoalProgressCreate

模型定义：[backend/app/schemas/student_goal.py](../../backend/app/schemas/student_goal.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `progress_percent` | number | 是 | minimum=0.0; maximum=100.0 | — |
| `milestone_reached` | string / null | 否 | string约束: maxLength=128 | — |
| `idempotency_key` | string / null | 否 | string约束: maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studentgoalprogressout"></a>
## StudentGoalProgressOut

模型定义：[backend/app/schemas/student_goal.py](../../backend/app/schemas/student_goal.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `progress_id` | string | 是 | — | — |
| `goal_id` | string | 是 | — | — |
| `progress_percent` | number | 是 | — | — |
| `milestone_reached` | string / null | 否 | — | — |
| `occurred_at` | string | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studentgoalprogressresult"></a>
## StudentGoalProgressResult

模型定义：[backend/app/schemas/student_goal.py](../../backend/app/schemas/student_goal.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal` | [StudentGoalOut](schemas.md#schema-studentgoalout) | 是 | — | — |
| `progress` | [StudentGoalProgressOut](schemas.md#schema-studentgoalprogressout) | 是 | — | 进度；对象或数值范围按字段类型 |
| `created` | boolean | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studentgoalupdate"></a>
## StudentGoalUpdate

模型定义：[backend/app/schemas/student_goal.py](../../backend/app/schemas/student_goal.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=200 | 名称 |
| `category` | enum ["academic", "research", "competition", "certificate", "job_search", "internship", "campus_affair", "health_habit", "personal_growth"] / null | 否 | — | — |
| `target_date` | string / null | 否 | string约束: maxLength=32 | — |
| `milestone_count` | integer / null | 否 | integer约束: minimum=0.0; maximum=100.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studybehaviorsummary"></a>
## StudyBehaviorSummary

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

本机行为辅助的隐私安全聚合；不接收逐帧或图像数据。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `observed_seconds` | integer | 是 | minimum=0.0; maximum=86400.0 | — |
| `study_seconds` | integer | 是 | minimum=0.0; maximum=86400.0 | — |
| `paused_seconds` | integer | 是 | minimum=0.0; maximum=86400.0 | — |
| `longest_continuous_study_seconds` | integer | 是 | minimum=0.0; maximum=86400.0 | — |
| `meaningful_switch_count` | integer | 是 | minimum=0.0; maximum=10000.0 | — |
| `phone_interaction_count` | integer | 是 | minimum=0.0; maximum=10000.0 | — |
| `possible_distraction_count` | integer | 是 | minimum=0.0; maximum=10000.0 | — |
| `absent_count` | integer | 是 | minimum=0.0; maximum=10000.0 | — |
| `reminder_count` | integer | 是 | minimum=0.0; maximum=10000.0 | — |
| `model_version` | string | 是 | minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-studybreakout"></a>
## StudyBreakOut

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `session_id` | string | 是 | — | — |
| `started_at` | string | 是 | — | — |
| `ended_at` | string / null | 否 | — | — |
| `reason` | string / null | 否 | — | 原因 |
| `created_at` | string | 是 | — | 创建时间 |

<a id="schema-studycheckincreate"></a>
## StudyCheckinCreate

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `scene` | enum ["rain", "snow", "cloud"] | 否 | default="rain" | — |
| `mood` | string / null | 否 | string约束: maxLength=100 | — |

<a id="schema-studycheckinout"></a>
## StudyCheckinOut

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `date` | string | 是 | — | — |
| `scene` | enum ["rain", "snow", "cloud"] | 是 | — | — |
| `mood` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |

<a id="schema-studycheckinresponse"></a>
## StudyCheckinResponse

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `checkin` | [StudyCheckinOut](schemas.md#schema-studycheckinout) | 是 | — | — |
| `created` | boolean | 是 | — | — |

<a id="schema-studycheckinsummary"></a>
## StudyCheckinSummary

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[StudyCheckinOut](schemas.md#schema-studycheckinout)> | 是 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `streak` | integer | 是 | — | — |
| `longest_streak` | integer | 是 | — | — |
| `week_count` | integer | 是 | — | — |
| `today_checked` | boolean | 是 | — | — |

<a id="schema-studygoalout"></a>
## StudyGoalOut

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `target_minutes` | integer | 是 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |

<a id="schema-studygoalupdate"></a>
## StudyGoalUpdate

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `target_minutes` | integer | 是 | minimum=15.0; maximum=480.0 | — |

<a id="schema-studysessioncreate"></a>
## StudySessionCreate

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | enum ["focus", "short_break", "long_break"] | 否 | default="focus" | — |
| `experience_mode` | enum ["QUIET", "AI_COMPANION", "SMART_GUARD"] | 否 | default="QUIET" | — |
| `planned_duration_seconds` | integer / null | 否 | integer约束: minimum=300.0; maximum=14400.0 | — |
| `goal` | string / null | 否 | string约束: maxLength=500 | 本次学习目标(自由文本) |
| `related_task_id` | string / null | 否 | string约束: maxLength=128 | 关联的个人待办 ID(PersonalTask ID,需属于当前用户且未软删除) |

<a id="schema-studysessionfinish"></a>
## StudySessionFinish

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

结束会话时填写的文字感受(用户主动输入,不根据表情替用户填写)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `self_report` | string / null | 否 | string约束: maxLength=2000 | — |
| `self_report_tags` | array<string> / null | 否 | array约束: maxItems=20 | — |
| `behavior_summary` | [StudyBehaviorSummary](schemas.md#schema-studybehaviorsummary) / null | 否 | — | — |

<a id="schema-studysessionout"></a>
## StudySessionOut

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

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

<a id="schema-studysessionupdate"></a>
## StudySessionUpdate

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

部分更新。goal/related_task_id 仅未结束会话可改;
self_report/self_report_tags/expression_signal 任意状态可改。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `goal` | string / null | 否 | string约束: maxLength=500 | — |
| `related_task_id` | string / null | 否 | string约束: maxLength=128 | 关联的个人待办 ID(需属于当前用户且未软删除) |
| `self_report` | string / null | 否 | string约束: maxLength=2000 | 用户主动填写的文字感受 |
| `self_report_tags` | array<string> / null | 否 | array约束: maxItems=20 | — |
| `expression_signal` | any / null | 否 | — | 预留 CNN 表情信号(本轮不实现 CNN,仅透传存储) |

<a id="schema-submissioncreate"></a>
## SubmissionCreate

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text_content` | string / null | 否 | string约束: maxLength=50000 | — |
| `submit` | boolean | 否 | default=false | — |

<a id="schema-submissionout"></a>
## SubmissionOut

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `assignment_id` | string | 是 | — | — |
| `student_id` | string | 是 | — | — |
| `student_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `text_content` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `submitted_at` | string / null | 否 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `score` | number / null | 否 | — | — |
| `teacher_comment` | string / null | 否 | — | — |
| `attachments` | array<[AttachmentOut](schemas.md#schema-attachmentout)> | 否 | — | — |

<a id="schema-submissionupdate"></a>
## SubmissionUpdate

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text_content` | string / null | 否 | string约束: maxLength=50000 | — |

<a id="schema-suggestedaction"></a>
## SuggestedAction

模型定义：[backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `label` | string | 是 | — | — |
| `type` | string | 否 | default="none" | — |
| `payload` | string / null | 否 | default=null | — |
| `data` | object / null | 否 | default=null | — |

<a id="schema-taskbreakdownrequest"></a>
## TaskBreakdownRequest

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

任务拆解输入: task_id(个人待办) 或自由文本目标,二选一(可同时提供)。

- task_id: 个人待办 PersonalTask ID(需属于当前用户)。
  解析成功时使用其 title/description/materials/submission_method/source_text 作为上下文。
  严格区分:不接受教师 Assignment ID。未来若需拆解教师作业,应增加独立 assignment_id 字段。
- goal: 自由文本目标。task_id 解析失败时以 goal 为准。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | string / null | 否 | string约束: maxLength=128 | — |
| `goal` | string / null | 否 | string约束: maxLength=500 | — |

<a id="schema-taskbreakdownresponse"></a>
## TaskBreakdownResponse

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

任务拆解响应。

`goal` 只返回 display_goal,不返回内部生成上下文(任务说明/通知原文等)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | enum ["llm", "rule_fallback"] | 是 | — | llm=模型生成成功; rule_fallback=规则降级 |
| `steps` | array<[TaskBreakdownStep](schemas.md#schema-taskbreakdownstep)> | 是 | — | — |
| `goal` | string | 是 | — | 展示用目标文本(display_goal) |
| `related_task_id` | string / null | 否 | — | — |
| `related_task_title` | string / null | 否 | — | — |
| `warnings` | array<string> | 否 | — | 警告列表；成功也需展示降级或缺失数据 |

<a id="schema-taskbreakdownstep"></a>
## TaskBreakdownStep

模型定义：[backend/app/schemas/study.py](../../backend/app/schemas/study.py)。

结构化拆解步骤。

值域由服务端规范化强制保证(见 TaskBreakdownService):
步骤数 3~8、estimated_minutes 5~120、依赖唯一且严格小于当前 step_number。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `step_number` | integer | 是 | minimum=1.0; maximum=8.0 | — |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `description` | string | 否 | default=""; maxLength=4000 | 说明 |
| `estimated_minutes` | integer | 是 | minimum=5.0; maximum=120.0 | — |
| `dependencies` | array<integer> | 否 | maxItems=7 | 依赖的 step_number 列表(必须严格小于当前 step_number) |
| `completion_criteria` | string | 是 | minLength=1; maxLength=1000 | 完成判定标准(可观测、可检验) |
| `is_policy_step` | boolean | 否 | default=false | 是否为校园政策相关步骤(依赖知识库) |
| `knowledge_source` | string / null | 否 | string约束: maxLength=256 | 政策步骤引用的知识库来源标题(展示用) |
| `knowledge_document_id` | string / null | 否 | string约束: maxLength=128 | 政策步骤引用的知识库文档 ID(服务端校验用);非政策或待确认步骤必须为空 |
| `knowledge_status` | enum ["not_applicable", "cited", "needs_confirmation"] | 否 | default="not_applicable" | not_applicable=非政策步骤; cited=引用真实检索来源; needs_confirmation=政策相关但证据不足,需人工确认 |

<a id="schema-taskimportanalyzerequest"></a>
## TaskImportAnalyzeRequest

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | minLength=1; maxLength=20000 | 正文或业务内容，嵌套结构按类型 |
| `source_name` | string / null | 否 | string约束: maxLength=256 | — |

<a id="schema-taskimportanalyzeresponse"></a>
## TaskImportAnalyzeResponse

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 是 | pattern="^(structured_text\|llm\|rules)$" | — |
| `split_reason` | string | 否 | default="" | — |
| `needs_user_confirmation` | boolean | 否 | default=false | — |
| `tasks` | array<[TaskImportDraft](schemas.md#schema-taskimportdraft)> | 否 | — | — |

<a id="schema-taskimportcommititem"></a>
## TaskImportCommitItem

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `description` | string / null | 否 | string约束: maxLength=4000 | 说明 |
| `target_students` | string / null | 否 | string约束: maxLength=512 | 通知面向对象(如 '2024级各班') |
| `deadline` | string / null | 否 | — | ISO 8601 截止时间(带时区) |
| `materials` | array<string> / null | 否 | array约束: maxItems=50 | 所需材料名称列表 |
| `submission_method` | string / null | 否 | string约束: maxLength=256 | — |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `source_name` | string / null | 否 | string约束: maxLength=256 | 通知来源(如 '教务处') |
| `source_text` | string / null | 否 | string约束: maxLength=20000 | 导入材料原文(用于确认与追溯) |
| `source_notice_id` | string / null | 否 | string约束: maxLength=128 | 关联通知 ID(可为空) |
| `priority` | string | 否 | default="medium"; pattern="^(low\|medium\|high)$" | — |
| `importance` | string / null | 否 | default="unknown"; string约束: pattern="^(urgent\|high\|important\|normal\|low\|unknown)$" | AI 评定的重要程度标签(交作业=high,填表=low) |
| `reminder_minutes` | integer / null | 否 | integer约束: minimum=0.0; maximum=43200.0 | 提前提醒分钟数(0 表示按 deadline 精确触发) |

<a id="schema-taskimportcommitrequest"></a>
## TaskImportCommitRequest

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `tasks` | array<[TaskImportCommitItem](schemas.md#schema-taskimportcommititem)> | 是 | minItems=1; maxItems=50 | — |

<a id="schema-taskimportcommitresponse"></a>
## TaskImportCommitResponse

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `created` | array<[PersonalTaskOut](schemas.md#schema-personaltaskout)> | 否 | — | — |
| `skipped_existing` | array<[TaskImportExisting](schemas.md#schema-taskimportexisting)> | 否 | — | — |

<a id="schema-taskimportdraft"></a>
## TaskImportDraft

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `description` | string / null | 否 | string约束: maxLength=4000 | 说明 |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> | 否 | maxItems=50 | — |
| `submission_method` | string / null | 否 | string约束: maxLength=256 | — |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `source_name` | string / null | 否 | string约束: maxLength=256 | — |
| `source_text` | string / null | 否 | string约束: maxLength=20000 | — |
| `priority` | string | 否 | default="medium"; pattern="^(low\|medium\|high)$" | — |
| `importance` | string | 否 | default="unknown"; pattern="^(urgent\|high\|important\|normal\|low\|unknown)$" | — |
| `confidence` | number | 否 | default=1.0; minimum=0.0; maximum=1.0 | — |
| `needs_confirmation` | boolean | 否 | default=false | — |
| `warnings` | array<string> | 否 | — | 警告列表；成功也需展示降级或缺失数据 |
| `selected` | boolean | 否 | default=true | — |
| `existing_task_id` | string / null | 否 | — | — |
| `existing_status` | string / null | 否 | — | — |

<a id="schema-taskimportexisting"></a>
## TaskImportExisting

模型定义：[backend/app/schemas/personal_task.py](../../backend/app/schemas/personal_task.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |

<a id="schema-taskworkloadvalue"></a>
## TaskWorkloadValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `known_pending` | integer | 是 | minimum=0.0 | — |
| `known_overdue` | integer | 是 | minimum=0.0 | — |
| `known_due_24h` | integer | 是 | minimum=0.0 | — |
| `known_due_7d` | integer | 是 | minimum=0.0 | — |
| `known_later` | integer | 否 | default=0; minimum=0.0 | — |
| `known_without_deadline` | integer | 是 | minimum=0.0 | — |
| `unknown_deadline` | integer | 是 | minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-todayagendaout"></a>
## TodayAgendaOut

模型定义：[backend/app/schemas/agenda.py](../../backend/app/schemas/agenda.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `date` | string | 是 | — | — |
| `timezone` | string | 否 | default="Asia/Shanghai" | — |
| `generated_at` | string | 是 | — | — |
| `last_chaoxing_synced_at` | string / null | 否 | — | — |
| `stale` | boolean | 否 | default=false | — |
| `summary` | [AgendaSummaryOut](schemas.md#schema-agendasummaryout) | 否 | — | — |
| `sources` | [AgendaSourcesOut](schemas.md#schema-agendasourcesout) | 否 | — | — |
| `items` | array<[AgendaItemOut](schemas.md#schema-agendaitemout)> | 否 | — | 列表条目 |

<a id="schema-tokenpair"></a>
## TokenPair

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `access_token` | string | 是 | — | 业务访问令牌 |
| `refresh_token` | string | 是 | — | 换发令牌；不是业务访问凭据 |
| `token_type` | string | 否 | default="Bearer" | 令牌类型 |
| `expires_in` | integer | 是 | — | access token 有效期(秒) |
| `expires_at` | string | 是 | — | access token 到期时间(ISO 8601) |
| `user` | [UserPublic](schemas.md#schema-userpublic) | 是 | — | — |

<a id="schema-tokenusage"></a>
## TokenUsage

模型定义：[backend/app/schemas/agent_observability.py](../../backend/app/schemas/agent_observability.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total_tokens` | integer | 否 | default=0; minimum=0.0 | — |
| `model_calls` | integer | 否 | default=0; minimum=0.0 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-trusteddeviceautologinrequest"></a>
## TrustedDeviceAutoLoginRequest

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `device_id` | string / null | 否 | string约束: maxLength=128 | — |

<a id="schema-trusteddevicelistitem"></a>
## TrustedDeviceListItem

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `device_id` | string | 是 | — | — |
| `device_name` | string / null | 否 | — | — |
| `browser_name` | string / null | 否 | — | — |
| `os_name` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `last_used_at` | string / null | 否 | — | — |
| `expires_at` | string | 是 | — | — |
| `is_current` | boolean | 否 | default=false | — |

<a id="schema-trusteddevicelistresponse"></a>
## TrustedDeviceListResponse

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `devices` | array<[TrustedDeviceListItem](schemas.md#schema-trusteddevicelistitem)> | 否 | — | — |

<a id="schema-trusteddevicerevokerequest"></a>
## TrustedDeviceRevokeRequest

模型定义：[backend/app/schemas/qr_auth.py](../../backend/app/schemas/qr_auth.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `device_id` | string / null | 否 | string约束: maxLength=128 | — |

<a id="schema-ttsin"></a>
## TtsIn

模型定义：[backend/app/api/routes/magicclass_tts.py](../../backend/app/api/routes/magicclass_tts.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | minLength=1; maxLength=20000 | 文本 |
| `instruction` | string / null | 否 | string约束: minLength=1; maxLength=2000 | — |
| `voice` | string / null | 否 | string约束: minLength=1; maxLength=80 | — |

<a id="schema-ttsrequest"></a>
## TtsRequest

模型定义：[backend/app/schemas/tts.py](../../backend/app/schemas/tts.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | minLength=1 | 文本 |
| `style` | string / null | 否 | string约束: maxLength=500 | — |

<a id="schema-unchangedstatesummary"></a>
## UnchangedStateSummary

模型定义：[backend/app/schemas/simulation.py](../../backend/app/schemas/simulation.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `state_type` | string | 是 | — | — |
| `scope_type` | string | 是 | — | — |
| `scope_id` | string | 是 | — | — |
| `data_quality` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-universityout"></a>
## UniversityOut

模型定义：[backend/app/schemas/university.py](../../backend/app/schemas/university.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `name` | string | 是 | — | 名称 |
| `short_name` | string / null | 否 | — | — |
| `province` | string / null | 否 | — | — |
| `city` | string / null | 否 | — | — |
| `country` | string | 是 | — | — |
| `level` | string / null | 否 | — | — |
| `logo_url` | string / null | 否 | — | — |
| `official_domain` | string / null | 否 | — | — |
| `official_website` | string / null | 否 | — | — |
| `academic_system_type` | string | 是 | — | — |
| `academic_system_url` | string / null | 否 | — | — |
| `academic_provider` | string | 是 | — | — |
| `forum_enabled` | boolean | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `is_demo` | boolean | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

<a id="schema-universitypage"></a>
## UniversityPage

模型定义：[backend/app/schemas/university.py](../../backend/app/schemas/university.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[UniversityOut](schemas.md#schema-universityout)> | 是 | — | 列表条目 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `total` | integer | 是 | — | 总数 |

<a id="schema-upcomingworkloadvalue"></a>
## UpcomingWorkloadValue

模型定义：[backend/app/schemas/forecast.py](../../backend/app/schemas/forecast.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_count` | integer | 是 | minimum=0.0 | — |
| `exam_count` | integer | 是 | minimum=0.0 | — |
| `estimated_total_minutes` | integer | 是 | minimum=0.0 | — |
| `pressure_band` | enum ["LOW", "MODERATE", "HIGH", "VERY_HIGH"] | 是 | — | — |
| `concentrated_dates` | array<string> | 否 | maxItems=16 | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-uploadimageresponse"></a>
## UploadImageResponse

模型定义：[backend/app/schemas/community.py](../../backend/app/schemas/community.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | string | 是 | — | — |
| `filename` | string | 是 | — | 文件名 |
| `size` | integer | 是 | — | — |

<a id="schema-useradminupdate"></a>
## UserAdminUpdate

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `display_name` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| `role` | string / null | 否 | string约束: pattern="^(student\|admin)$" | — |
| `college` | string / null | 否 | string约束: maxLength=64 | — |
| `major` | string / null | 否 | string约束: maxLength=64 | — |
| `grade` | string / null | 否 | string约束: maxLength=32 | — |
| `is_active` | boolean / null | 否 | — | — |

<a id="schema-usercreate"></a>
## UserCreate

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

管理员创建用户请求(仅 admin 角色可调用)。

约束:
- username: 3-64 字符,仅字母/数字/下划线
- password: 8-128 字符(由后端 PBKDF2 哈希后存储,不入日志)
- role: student / admin(CampusMate AI 只存在这两类系统角色)
- student_number: 仅 student 角色携带

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=3; maxLength=64; pattern="^[a-zA-Z0-9_]+$" | 登录用户名 |
| `password` | string | 是 | minLength=8; maxLength=128 | 登录密码，仅请求使用 |
| `role` | string | 是 | pattern="^(student\|admin)$" | — |
| `display_name` | string / null | 否 | string约束: maxLength=128 | — |
| `student_number` | string / null | 否 | string约束: maxLength=32 | — |
| `teacher_number` | string / null | 否 | string约束: maxLength=32 | 已废弃,仅为兼容旧数据保留 |
| `college` | string / null | 否 | string约束: maxLength=64 | — |
| `major` | string / null | 否 | string约束: maxLength=64 | — |
| `grade` | string / null | 否 | string约束: maxLength=32 | — |

<a id="schema-userpublic"></a>
## UserPublic

模型定义：[backend/app/schemas/multi_role.py](../../backend/app/schemas/multi_role.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `username` | string | 是 | — | 登录用户名 |
| `role` | string | 是 | — | — |
| `name` | string | 否 | default="" | 名称 |
| `display_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `teacher_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `avatar_url` | string / null | 否 | — | — |
| `university_id` | string / null | 否 | — | — |
| `university_name` | string / null | 否 | — | — |
| `is_active` | boolean | 否 | default=true | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

<a id="schema-validationerror"></a>
## ValidationError

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `loc` | array<string / integer> | 是 | — | — |
| `msg` | string | 是 | — | — |
| `type` | string | 是 | — | — |

<a id="schema-workflowactionout"></a>
## WorkflowActionOut

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `action_id` | string | 是 | minLength=1; maxLength=64 | — |
| `workflow_id` | string | 是 | minLength=1; maxLength=64 | — |
| `action_type` | string | 是 | maxLength=64 | — |
| `title` | string | 是 | maxLength=256 | 标题 |
| `risk_level` | [RiskLevel](schemas.md#schema-risklevel) | 是 | — | — |
| `status` | string | 是 | maxLength=16 | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `external_ref` | string / null | 否 | string约束: maxLength=128 | — |
| `expires_at` | string / null | 否 | string约束: maxLength=64 | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `error_message` | string / null | 否 | string约束: maxLength=256 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-workflowcreatein"></a>
## WorkflowCreateIn

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

POST /notices/{notice_id}/workflow 请求体。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-workflowout"></a>
## WorkflowOut

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `workflow_id` | string | 是 | minLength=1; maxLength=64 | — |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `notice_id` | string | 是 | minLength=1; maxLength=64 | — |
| `source_id` | string / null | 否 | string约束: maxLength=64 | — |
| `status` | string | 是 | maxLength=24 | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `title` | string / null | 否 | string约束: maxLength=256 | 标题 |
| `deadline` | string / null | 否 | string约束: maxLength=64 | 截止时间 |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `audience` | string / null | 否 | string约束: maxLength=256 | — |
| `materials` | array<string> | 否 | — | — |
| `steps` | array<[WorkflowStepOut](schemas.md#schema-workflowstepout)> | 否 | — | — |
| `source_evidence` | array<string> | 否 | — | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `uncertainty` | array<string> | 否 | — | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `error_message` | string / null | 否 | string约束: maxLength=256 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `actions` | array<[WorkflowActionOut](schemas.md#schema-workflowactionout)> | 否 | — | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-workflowreanalyzein"></a>
## WorkflowReanalyzeIn

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-workflowstepout"></a>
## WorkflowStepOut

模型定义：[backend/app/schemas/notice_workflow.py](../../backend/app/schemas/notice_workflow.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `step` | string | 是 | maxLength=512 | — |
| `done` | boolean | 否 | default=false | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-workloadpressurevalue"></a>
## WorkloadPressureValue

模型定义：[backend/app/schemas/learner_state.py](../../backend/app/schemas/learner_state.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `window_days` | integer | 是 | minimum=1.0; maximum=30.0 | — |
| `task_count` | integer | 是 | minimum=0.0 | — |
| `exam_count` | integer | 是 | minimum=0.0 | — |
| `estimated_total_minutes` | integer | 是 | minimum=0.0 | — |
| `pressure_band` | enum ["LOW", "MODERATE", "HIGH", "VERY_HIGH"] | 是 | — | — |
| `concentrated_dates` | array<string> | 否 | maxItems=16 | — |
| `data_completeness` | enum ["verified", "partial", "stale", "unavailable"] | 是 | — | — |
| `warning_codes` | array<string> | 否 | maxItems=16 | — |

对象级约束：

```json
{
  "additionalProperties": false
}
```

<a id="schema-workspacecreatein"></a>
## WorkspaceCreateIn

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=120 | 名称 |
| `description` | string | 否 | default=""; maxLength=4000 | 说明 |
| `folder_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | — |

<a id="schema-workspacelistout"></a>
## WorkspaceListOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[WorkspaceOut](schemas.md#schema-workspaceout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |

<a id="schema-workspaceout"></a>
## WorkspaceOut

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

一个学习工作台。

`revision` 是并发控制的唯一凭据：客户端读到的值必须原样回传，否则写入被拒。
`course_id` 由服务端回填，客户端**不能**在请求体里指定归属。
`folder_id` 为 `None` 表示未归档（等同于没有文件夹功能之前的行为）。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `description` | string | 否 | default="" | 说明 |
| `folder_id` | string / null | 否 | — | — |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

<a id="schema-workspaceupdatein"></a>
## WorkspaceUpdateIn

模型定义：[backend/app/schemas/magicclass_fusion.py](../../backend/app/schemas/magicclass_fusion.py)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=120 | 名称 |
| `description` | string / null | 否 | string约束: maxLength=4000 | 说明 |
| `folder_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | — |
