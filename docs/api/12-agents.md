# Agent 运行时、审批、记忆、产物

> 对照日期：2026-10-07。本模块共 20 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 并发工具调用与执行归属

相同 Run、幂等键和参数指纹的工具副作用最多由一个执行者接管；已完成调用重放结果，正在执行的并发调用返回既有 `AGENT_INVALID_STATE`（409），不能重新执行工具。审批恢复会原子抢占执行权，拒绝或过期审批仍拒绝执行。持久化 Worker 只领取已声明非空 handler_code 的运行，通知解析、复习生成和课程研究的内联运行由其原流程推进，避免被后台 Worker 当作未知处理器失败。

Worker 恢复过期租约时先原子领取执行权，并在恢复过程中续租。已续租的运行和其他 Worker 已领取的运行不会被旧扫描结果覆盖；处理器缺失、恢复抛错或明确无法恢复时，该运行进入 `FAILED`，客户端按既有终态停止轮询。恢复领取会产生 `RUN_RECOVERY_STARTED` 事件，按普通运行事件处理，不改变已有字段。

审批过期只会将仍为 `PENDING` 的记录变为 `EXPIRED`，不会覆盖并发请求已落定的 `APPROVED` / `REJECTED`。用户决定在取得数据库写锁后再次核验期限，达到 `expires_at`（含相等）时不再批准或拒绝，原子标记过期并返回 410 `AGENT_INVALID_STATE`；请求在到期前发出也不能延长期限。同方向已落定决定继续按幂等重放返回，反方向返回 409 `AGENT_APPROVAL_CONFLICT`；并发已标记过期时返回 410，开始读取时已经落定为过期的审批仍遵循既有 409 冲突分支。Web、Android、HarmonyOS 的审批调用已核对，字段无需迁移；微信小程序尚未接入该审批调用，本次未进行端侧运行验收。

<a id="run-controls"></a>
## 运行控制与重试幂等

`pause`、`resume`、`retry` 的幂等键优先级为请求体 `idempotency_key` → `Idempotency-Key` 请求头 → 固定默认值 `{action}:{run_id}`。记录按 run_id 和 key 查重，不再比较动作名；每次独立点击必须生成新键，同一次请求的网络重试才复用。省略键虽然能通过校验，但“暂停 → 恢复 → 再次暂停”会命中第一次暂停的默认键，第二次暂停不执行，仍返回当前运行状态。不同动作也不要共用同一键。上述控制返回 HTTP 200 后仍须检查响应中的 status；不满足状态前置条件返回 409 `AGENT_INVALID_STATE`。

pause 从 QUEUED/RUNNING 切换为 PAUSED，已 PAUSED 时返回原状态；resume 从 PAUSED 恢复为 RUNNING（仍有执行者租约）或 QUEUED，已 RUNNING/QUEUED 时也返回原状态。retry 仅允许 FAILED/PARTIAL/CANCELLED；新运行还需要任务具有已注册的 handler。状态前置条件针对首次执行，同键重放先查重，可能返回其他当前状态。

`retry` 首次成功创建新运行，返回新的 run_id，并将 retry_of 设置为原 run_id；后续按新 ID 追踪。**对原运行用同一键重放时，当前接口返回原运行的当前状态，不返回已创建的新运行**。客户端保留首次收到的新 ID；首次响应丢失时先用同一键重试，再读取 `GET /api/v1/agent-jobs/{job_id}/runs`（按创建时间降序）查 retry_of 为原 ID 的运行，并核对任务详情的 latest_run_id。此列表没有 source_run_id 筛选参数，公开响应也不包含控制键；多个重试运行并存时无法仅凭该列表精确对应某个键，应展示候选供确认，不要换新键盲目 retry，以免再创建运行。

`cancel` 使用独立的状态机流程：请求体的 idempotency_key 当前未被消费，也没有声明 `Idempotency-Key` 请求头。重复取消 CANCELLED 运行返回该运行；对 SUCCEEDED/FAILED 取消返回 409 `AGENT_RUN_CANCELLED`；PARTIAL 仍允许取消为 CANCELLED。不要套用 pause/resume/retry 的键查重逻辑。

这些是当前后端行为的接入说明，没有改变接口或字段。现有 Web 封装已提供控制调用；本次没有修改任何客户端，以上重复控制与响应丢失场景在 Web、Android、HarmonyOS、微信小程序均未做端侧验收。

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/agent-runtime/capabilities` | 返回 runtime 能力清单 + 契约版本 |
| GET | `/api/v1/agent-runtime/skills` | 返回可发现的 Skill/MCP 元数据；执行仍必须经过 Runtime 治理 |
| POST | `/api/v1/agent-jobs` | 创建任务 |
| GET | `/api/v1/agent-jobs` | 列出任务 |
| GET | `/api/v1/agent-jobs/{job_id}/runs` | 列出任务运行记录 |
| GET | `/api/v1/agent-jobs/{job_id}` | 读取任务 |
| GET | `/api/v1/agent-runs` | 列出运行 |
| GET | `/api/v1/agent-runs/{run_id}` | 读取运行 |
| POST | `/api/v1/agent-runs/{run_id}/cancel` | 取消运行 |
| POST | `/api/v1/agent-runs/{run_id}/pause` | 暂停运行 |
| POST | `/api/v1/agent-runs/{run_id}/resume` | 恢复运行 |
| POST | `/api/v1/agent-runs/{run_id}/retry` | 重试运行 |
| GET | `/api/v1/agent-runs/{run_id}/events` | 列出事件 |
| GET | `/api/v1/agent-runs/{run_id}/events/stream` | SSE 流。以持久化事件为真源,支持 Last-Event-ID 续传。断开不取消 run |
| POST | `/api/v1/agent-approvals/{approval_id}/decision` | 落定一次审批决定 |
| GET | `/api/v1/agent-artifacts/{artifact_id}/content` | 返回 artifact 文本内容(Markdown / JSON) |
| GET | `/api/v1/agent-artifacts/{artifact_id}` | 读取产物 |
| GET | `/api/v1/agent-memories` | 列出memories |
| POST | `/api/v1/agent-memories` | 创建记忆 |
| POST | `/api/v1/agent-memories/{memory_id}/withdraw` | 撤回记忆 |

## 接口契约

### `GET /api/v1/agent-runtime/capabilities`

用途：返回 runtime 能力清单 + 契约版本。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`get_capabilities`。

Web 封装：`getAgentCapabilities`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

返回 runtime 能力清单 + 契约版本。

清单由启动时冻结的 `CapabilityRegistry` 生成,不再在路由里硬编码;
新增能力只能追加到 `capabilities.default.json`,已发布语义由启动校验钉死。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentCapabilitiesOut](schemas.md#schema-agentcapabilitiesout) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `contract_version` | string | 否 | default="v1" | — |
| `capabilities` | array<[AgentCapabilityOut](schemas.md#schema-agentcapabilityout)> | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/agent-runtime/skills`

用途：返回可发现的 Skill/MCP 元数据；执行仍必须经过 Runtime 治理。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`get_skills`。

Web 封装：当前无封装；按本节后端契约调用。

返回可发现的 Skill/MCP 元数据；执行仍必须经过 Runtime 治理。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentSkillsOut](schemas.md#schema-agentskillsout) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `contract_version` | string | 否 | default="v1" | — |
| `skills` | array<[AgentSkillOut](schemas.md#schema-agentskillout)> | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/agent-jobs`

用途：创建任务。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`create_job`。

Web 封装：`createAgentJob`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）；`createAgentJob`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

运行时成功状态：首次创建返回 **202**，同一幂等键与相同输入重放返回 **200**；两者均为 AgentJobOut。body.idempotency_key 优先于 Idempotency-Key 头。input_ref 还必须通过对应 Handler 校验，注册能力与嵌套字段见 [Agent 创建规则](integration.md#agent-input)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[AgentJobCreateIn](schemas.md#schema-agentjobcreatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `job_kind` | string | 是 | pattern="^(learning_goal\|final_review\|course_research\|notice_workflow\|interactive_classroom)$" | — |
| `input_ref` | object | 否 | — | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "job_kind": "<job_kind>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentJobOut](schemas.md#schema-agentjobout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |
| 202 | application/json | [AgentJobOut](schemas.md#schema-agentjobout) |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | 'AGENT_RUNTIME_UNAVAILABLE' | 'Agent 运行时当前不接受新任务' |
| 422 | VALIDATION_FAILED | 'Agent Job 输入未通过 Handler Schema 校验' |
| 409 | 'AGENT_IDEMPOTENCY_CONFLICT' | '幂等键已用于不同的请求' |

### `GET /api/v1/agent-jobs`

用途：列出任务。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`list_jobs`。

Web 封装：`listAgentJobs`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[AgentJobOut](schemas.md#schema-agentjobout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/agent-jobs/{job_id}/runs`

用途：列出任务运行记录。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`list_job_runs`。

Web 封装：`listAgentJobRuns`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `job_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[AgentRunOut](schemas.md#schema-agentrunout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Job 不存在' |

### `GET /api/v1/agent-jobs/{job_id}`

用途：读取任务。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`get_job`。

Web 封装：`getAgentJob`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）；`getAgentJob`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `job_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentJobOut](schemas.md#schema-agentjobout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Job 不存在' |

### `GET /api/v1/agent-runs`

用途：列出运行。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`list_runs`。

Web 封装：当前无封装；按本节后端契约调用。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[AgentRunOut](schemas.md#schema-agentrunout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/agent-runs/{run_id}`

用途：读取运行。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`get_run`。

Web 封装：`getAgentRun`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentRunOut](schemas.md#schema-agentrunout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |

### `POST /api/v1/agent-runs/{run_id}/cancel`

用途：取消运行。

取消依赖状态机幂等，body.idempotency_key 当前不参与查重；重复取消与终态冲突见[运行控制](#run-controls)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`cancel_run`。

Web 封装：`cancelAgentRun`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |

请求体：`application/json`，必填；[AgentRunCancelIn](schemas.md#schema-agentruncancelin)。

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
| 200 | application/json | [AgentRunOut](schemas.md#schema-agentrunout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |
| 403 | 'AGENT_PERMISSION_DENIED' | '无权取消' |

### `POST /api/v1/agent-runs/{run_id}/pause`

用途：暂停运行。

每次独立暂停生成新幂等键，仅网络重试复用；省略键会使第二轮暂停被第一次的记录吞掉，见[运行控制](#run-controls)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`pause_run`。

Web 封装：`pauseAgentRun`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[AgentRunControlIn](schemas.md#schema-agentruncontrolin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{"idempotency_key":"pause_example_1"}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentRunOut](schemas.md#schema-agentrunout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |
| 403 | 'AGENT_PERMISSION_DENIED' | '无权控制此运行' |

### `POST /api/v1/agent-runs/{run_id}/resume`

用途：恢复运行。

每次独立恢复生成新幂等键，不与暂停键共用；body 优先于请求头，见[运行控制](#run-controls)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`resume_run`。

Web 封装：`resumeAgentRun`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[AgentRunControlIn](schemas.md#schema-agentruncontrolin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{"idempotency_key":"resume_example_1"}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentRunOut](schemas.md#schema-agentrunout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |
| 403 | 'AGENT_PERMISSION_DENIED' | '无权控制此运行' |

### `POST /api/v1/agent-runs/{run_id}/retry`

用途：重试运行。

首次成功返回新运行；同键重放返回原运行。首次响应丢失时按[运行控制](#run-controls)回读任务运行列表，避免换键创建重复运行。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`retry_run`。

Web 封装：`retryAgentRun`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[AgentRunControlIn](schemas.md#schema-agentruncontrolin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{"idempotency_key":"retry_example_1"}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentRunOut](schemas.md#schema-agentrunout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |
| 403 | 'AGENT_PERMISSION_DENIED' | '无权控制此运行' |

### `GET /api/v1/agent-runs/{run_id}/events`

用途：列出事件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`list_events`。

Web 封装：当前无封装；按本节后端契约调用。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |
| query | `after_sequence` | integer | 否 | default=0; minimum=0 | — |
| query | `limit` | integer | 否 | default=100; minimum=1; maximum=500 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[AgentEventOut](schemas.md#schema-agenteventout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |

### `GET /api/v1/agent-runs/{run_id}/events/stream`

用途：SSE 流。以持久化事件为真源,支持 Last-Event-ID 续传。断开不取消 run。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`stream_events`。

Web 封装：`createAgentEventStream`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）

SSE 流。以持久化事件为真源,支持 Last-Event-ID 续传。断开不取消 run。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `run_id` | string | 是 | — | — |
| header | `Last-Event-ID` | string / null | 否 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | text/event-stream | AgentEventOut 的 SSE；Last-Event-ID 续传 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
StreamingResponse(event_generator(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Run 不存在' |
| 409 | AGENT_CURSOR_INVALID | '事件游标无效或不属于该运行' |

### `POST /api/v1/agent-approvals/{approval_id}/decision`

用途：落定一次审批决定。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`resolve_approval`。

Web 封装：`resolveAgentApproval`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）；`decideAgentApproval`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

落定一次审批决定。

- 决策本身是**幂等**的：重复提交同一个决定返回同一结果（不会 409）；
- 相反的决定一律 409，绝不覆盖已生效的决定；
- `Idempotency-Key` 会被**真正记录**（`agent_run_controls`），而不是收下就丢；
- 只有**本次真正落定**的决定才会驱动 Run 状态迁移 ——
  重放不会把已经跑完的 Run 再取消/再排队一次。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `approval_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[AgentApprovalDecisionIn](schemas.md#schema-agentapprovaldecisionin)。

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
| 200 | application/json | [AgentApprovalOut](schemas.md#schema-agentapprovalout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/agent-artifacts/{artifact_id}/content`

用途：返回 artifact 文本内容(Markdown / JSON)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`get_artifact_content`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

返回 artifact 文本内容(Markdown / JSON)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `artifact_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | 产物 mime_type / text/plain | 文本产物，按内容格式读取 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
PlainTextResponse(content, media_type=meta.get('mime_type') or 'text/plain')
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Artifact 不存在' |
| 404 | AGENT_RUN_NOT_FOUND | 'Artifact 内容不可读' |

### `GET /api/v1/agent-artifacts/{artifact_id}`

用途：读取产物。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`get_artifact`。

Web 封装：`getAgentArtifact`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `artifact_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentArtifactOut](schemas.md#schema-agentartifactout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Artifact 不存在' |

### `GET /api/v1/agent-memories`

用途：列出memories。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`list_memories`。

Web 封装：当前无封装；按本节后端契约调用。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[AgentMemoryOut](schemas.md#schema-agentmemoryout)> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/agent-memories`

用途：创建记忆。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`create_memory`。

Web 封装：当前无封装；按本节后端契约调用。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[AgentMemoryCreateIn](schemas.md#schema-agentmemorycreatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | string | 是 | pattern="^(CONFIRMED_PREFERENCE\|CONFIRMED_STUDY_GOAL\|CONFIRMED_CONSTRAINT\|USER_APPROVED_SUMMARY)$" | — |
| `content_summary` | string | 是 | minLength=1; maxLength=512 | — |
| `sensitivity` | string | 否 | default="low"; pattern="^(low\|medium\|high)$" | — |
| `confirmed` | boolean | 否 | default=false | — |
| `model_may_consume` | boolean | 否 | default=false | — |
| `provenance` | string / null | 否 | string约束: maxLength=128 | — |
| `valid_until` | string / null | 否 | string约束: maxLength=64 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "kind": "<kind>",
  "content_summary": "<content_summary>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentMemoryOut](schemas.md#schema-agentmemoryout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | VALIDATION_FAILED | str(exc) |

### `POST /api/v1/agent-memories/{memory_id}/withdraw`

用途：撤回记忆。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/agent_runtime.py](../../backend/app/api/routes/agent_runtime.py)，`withdraw_memory`。

Web 封装：当前无封装；按本节后端契约调用。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `memory_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AgentMemoryOut](schemas.md#schema-agentmemoryout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

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

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | AGENT_RUN_NOT_FOUND | 'Memory 不存在' |
