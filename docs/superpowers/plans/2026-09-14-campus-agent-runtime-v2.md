# CampusAgentRuntime v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不替换 CampusMateAI 现有校园业务、跨端契约和学习模型的前提下，把 Agent Runtime 升级为可持久化排队、可恢复、可审计、可扩展的轻量运行时与控制平面。

**Architecture:** 保留 FastAPI、SQLite、现有领域 Service/Repository 和 SSE；新增数据库租约队列、`JobHandlerRegistry`、统一 `ToolInvocationGateway`、原子运行状态/事件写入和管理员只读观测接口。`CampusAgentRuntime v2` 是内部架构版本，现有 `/api/v1` 公共契约继续兼容，不因内部重构强制客户端升版。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、SQLite WAL、pytest、React 18/Vite、Node test runner、微信小程序 TypeScript。

**Spec:** `docs/superpowers/specs/2026-09-12-campus-agent-runtime-v1-design.md`，以及本计划中的 v2 增量契约与验收门槛。

## Global Constraints

- 只借鉴 EvoFlow 的运行时、事件恢复、能力目录和控制面设计思想；不得复制其源码、前端资源或技能包。EvoFlow 的 PolyForm Noncommercial License 不应传导到本项目实现。
- 不引入 LangGraph、Tauri、Docker 代码沙箱、远程技能市场、任意代码执行或任意 SQL 执行。
- 第一阶段不引入 Redis、Celery 或新的基础设施；先用现有 SQLite WAL 实现带租约、至少一次投递的持久化队列。
- 模型只能提出结构化建议；业务写操作必须经过领域 Service、统一工具策略、资源归属校验和必要审批。
- 保留显式记忆、`ContextSnapshot`、上下文预算、来源摘要、过期控制、BM25 中文检索及现有跨端能力。
- 公共字段和枚举只允许追加；不得改名或改变已发布语义。未知状态、事件和错误码在客户端必须安全降级。
- 不保存 prompt、隐藏推理、完整模型响应、凭据或敏感工具参数。观测数据只保留安全摘要、哈希、计数、耗时和业务标识。
- 新 Worker 必须具备幂等、租约、心跳、有限重试和恢复语义；不能宣称 exactly-once，目标是 at-least-once + 幂等副作用。
- 每个任务先写失败测试，再做最小实现；每个任务独立提交，提交中不得混入工作区既有改动。

---

## 1. 结论评估与优先级修订

原结论方向正确：最值得借鉴的是“Agent 运行时与控制平面”，而不是 EvoFlow 的整体技术栈。CampusMateAI 已具备更适合校园场景的隐私边界、学习状态、校园领域服务和多端产品面，整体迁移会增加复杂度并削弱差异化。

需要做三项修订：

1. 在“持久化任务队列”之前增加一个独立 P0：**运行状态与事件原子提交**。当前状态更新和事件追加分属不同提交，进程崩溃可能造成状态与事件不一致。
2. 将“扩展 CI”从 P2 提升到 P1：运行时契约横跨 Web、Android、HarmonyOS 和微信端，没有契约门禁就无法安全追加恢复事件和错误码。
3. 将 Skill 热加载和远程安装降到 P2/不做：近期只实现版本、启停、角色绑定和启动校验；动态加载会扩大供应链与权限面，收益不足。

| 项目 | 业务收益 | 实现成本 | 主要风险 | 修订优先级 | 决策 |
| --- | --- | --- | --- | --- | --- |
| 原子状态 + 事件存储 | 极高 | 中 | 迁移兼容、事务边界 | P0 | 最先实施 |
| SQLite 持久化队列 + Worker | 极高 | 中高 | 重复执行、租约丢失 | P0 | 实施，不先上 Redis |
| SSE 游标恢复与单一事件归并 | 高 | 中 | 重连重复、跨进程通知 | P0 | 保留 SSE，不上 WebSocket |
| Tool Invocation Gateway | 极高 | 高 | 审批恢复、策略绕过 | P0 | 先迁移高风险写操作 |
| JobHandlerRegistry | 高 | 中低 | 路由迁移回归 | P1，但作为 Worker 前置一起做 |
| 管理员观测控制面 | 高 | 中 | 隐私泄漏、指标误导 | P1 | 只读、聚合优先 |
| 跨端契约 CI | 高 | 中 | Android CI 的 JDK 供应 | P1 | Web/微信先落地，Android设准入门 |
| Skill 版本/启停/角色绑定 | 中 | 中 | 配置漂移 | P1 | 启动时加载，不热加载 |
| Notification Channel/Outbox | 中高 | 高 | 重复通知、平台授权 | P2 | 单独立项 |
| LangGraph/Tauri/沙箱/技能市场 | 低 | 极高 | 运维、许可、攻击面 | 不做 | 仅在需求发生根本变化时复评 |

粗略工作量为 28–42 人日，误差约 ±30%。一名熟悉后端和跨端契约的工程师约需 6–9 周；两名工程师按“运行时内核/控制面与客户端”拆分约需 4–6 周。第一批可独立交付的 P0 内核预计 12–18 人日。

## 2. 目标架构与不变量

```text
POST /api/v1/agent-jobs
          |
          v
Atomic Job + Run + RUN_QUEUED event
          |
          v
Lease-based AgentWorker --> JobHandlerRegistry --> WorkflowHandler
                                      |                    |
                                      v                    v
                           ToolInvocationGateway --> Campus Domain Services
                              | Policy / Risk / Approval / Ownership
                              v
                    Atomic Run State + Event Store
                              |
                 +------------+-------------+
                 |                          |
                 v                          v
           REST/SSE resume            Admin observability

Later: Notification Outbox --> App / Android / WeChat / Webhook
```

必须长期成立的不变量：

- `agent_runs.status/phase` 的每次变化与对应 `agent_events` 在同一事务提交。
- 同一 `run_id` 的事件 `sequence` 严格递增且唯一；SSE 只以持久化事件为真源。
- Worker 获取任务必须通过有期限租约；只有租约持有者可续租、写 checkpoint 或完成运行。
- 处理器可能重复执行；任何领域副作用都必须由 `idempotency_key + request_hash` 防重。
- `AWAITING_APPROVAL` 不占 Worker；审批完成后将运行重新排入 `QUEUED`，从安全 checkpoint 恢复。
- 客户端断线不取消运行；重连先按 `Last-Event-ID` 恢复，再继续接收新事件。
- 管理员观测接口不能返回原始 prompt、完整模型内容、凭据、记忆正文或工具敏感参数。

## 3. v2 增量接口契约

### 3.1 Handler 接口

新建 `backend/app/services/agent_runtime/handlers/base.py`：

```python
@dataclass(frozen=True)
class HandlerContext:
    run_id: str
    job_id: str
    user_id: str
    job_kind: str
    input_ref: dict[str, Any]
    checkpoint: dict[str, Any] | None
    attempt_no: int

@dataclass(frozen=True)
class HandlerResult:
    status: Literal["SUCCEEDED", "PARTIAL", "AWAITING_APPROVAL"]
    artifact_ids: tuple[str, ...] = ()
    checkpoint: dict[str, Any] | None = None
    summary: str | None = None

class JobHandler(Protocol):
    code: str
    version: str
    job_kind: str
    input_model: type[BaseModel]
    max_attempts: int

    async def execute(self, context: HandlerContext) -> HandlerResult: ...
    async def recover(self, context: HandlerContext) -> RecoveryDecision: ...
```

注册表必须在启动时拒绝重复 `job_kind`、空版本、未声明输入模型和未知工具能力。路由不得再包含 `if job_kind == ...` 的执行分支。

### 3.2 Job 创建与幂等

- 继续使用 `POST /api/v1/agent-jobs` 和现有响应体。
- 新任务成功入队返回 `202 Accepted`；相同幂等键和相同请求哈希重放返回原 Job，可返回 `200 OK`。
- 请求哈希由规范化后的 `job_kind + input_ref` 生成，不包含 Header 顺序或 JSON 键顺序。
- 相同 `(user_id, operation, idempotency_key)` 携带不同请求哈希时返回 `409` 和 `AGENT_IDEMPOTENCY_CONFLICT`。
- Job、首个 Run、幂等声明和 `RUN_QUEUED` 事件必须在同一事务中创建。

### 3.3 Worker 租约与重试

- 默认单进程并发数 `1`，租约 `30s`，心跳 `10s`，空队列轮询 `500ms`。
- 领取条件：`status='QUEUED'`、`next_attempt_at <= now`、无有效租约。
- 默认最多 3 次尝试，退避为 1s、5s、15s；处理器可降低但不能无限重试。
- 不可重试错误直接 `FAILED`；可重试错误回到 `QUEUED` 并追加 `RUN_RETRY_SCHEDULED`。
- Worker 崩溃后，另一 Worker 在租约过期后调用 Handler 的 `recover()`；不得无条件把所有运行标记失败。

### 3.4 SSE 恢复

- `Last-Event-ID` 必须通过 `(run_id, event_id)` 索引直接定位，不再扫描 10,000 条事件。
- 找不到或不属于该 Run 的游标返回 `409 AGENT_CURSOR_INVALID`，客户端随后调用 REST 事件列表做一次安全全量归并。
- SSE 发送 15 秒注释心跳；同进程事件由内存通知器唤醒，跨进程仍以数据库短轮询兜底。
- 追加事件类型只能附加在枚举末尾：`RUN_RETRY_SCHEDULED`、`RUN_RECOVERY_STARTED`、`RUN_RECOVERED`。
- Web、Android、HarmonyOS、微信端 reducer 必须按 `(run_id, sequence)` 去重，并对未知事件执行“记录游标、不提升权限、不崩溃”的安全降级。

### 3.5 Tool Invocation Gateway

```python
class ToolInvocationRequest(BaseModel):
    run_id: str
    role_code: str
    tool_name: str
    arguments: dict[str, Any]
    idempotency_key: str

class ToolInvocationGateway:
    async def invoke(self, request: ToolInvocationRequest) -> ToolInvocationResult: ...
```

校验顺序固定为：运行/用户有效性 → Handler capability → Role permission → Pydantic JSON Schema → 资源归属 → Hard Deny → RiskEngine → ApprovalGate → 幂等原子声明 → 领域 Service 执行 → 安全事件/审计。任何工作流不得绕过此入口直接执行注册工具。

## 4. 实施任务

### Task 1: 建立原子事务与持久化队列数据模型

**Files:**

- Modify: `backend/app/database/sqlite_db.py`
- Modify: `backend/app/repositories/agent_runtime_repository.py`
- Modify: `backend/tests/test_agent_runtime_migrations.py`
- Modify: `backend/tests/test_agent_runtime_repository.py`
- Create: `backend/tests/test_agent_runtime_atomicity.py`

- [ ] 在迁移测试中构造 v1 旧库，断言升级后 `agent_runs` 拥有 `handler_code`、`handler_version`、`attempt_no`、`next_attempt_at`、`lease_owner`、`lease_expires_at`、`heartbeat_at`、`checkpoint_json` 字段。
- [ ] 新增失败测试：故意在事件插入前抛错，断言 Run 状态和 Job 状态都不改变。
- [ ] 新增失败测试：并发创建相同幂等键时只产生一个 Job/Run；相同键不同请求哈希返回冲突。
- [ ] 新增失败测试：两个 Worker 同时领取队列，只能有一个获得同一 `run_id`。
- [ ] 运行 `cd backend && python -m pytest tests/test_agent_runtime_migrations.py tests/test_agent_runtime_repository.py tests/test_agent_runtime_atomicity.py -q`，确认新增测试因缺少事务 API 失败。
- [ ] 增加 `agent_idempotency_claims` 表，以 `(scope, user_id, idempotency_key)` 为主键保存 `request_hash` 和 `resource_id`；不要直接对可能含历史重复数据的旧列强加唯一索引。
- [ ] 为 `agent_events` 增加或确认 `(run_id, sequence)` 唯一约束及 `(run_id, event_id)` 查询索引。
- [ ] 在 Repository 实现 `create_job_with_run_and_event()`、`transition_run_with_event()`、`claim_next_run()`、`renew_run_lease()`、`save_checkpoint()`、`release_run_lease()`、`get_event_sequence()`；所有复合写操作使用 `Database.transaction()`。
- [ ] 对状态更新使用期望状态和租约所有者条件，更新行数不为 1 时抛 `AgentInvalidState`，避免后到 Worker 覆盖新状态。
- [ ] 重新运行上述测试，预期全部通过。
- [ ] 运行 `python -m pytest tests/test_agent_runtime_lifecycle.py tests/test_agent_runtime_cancellation.py -q`，确认生命周期回归通过。
- [ ] 提交：`git commit -m "ensure agent state and events commit atomically"`。

### Task 2: 引入 JobHandlerRegistry 并迁移 learning_goal

**Files:**

- Create: `backend/app/services/agent_runtime/handlers/__init__.py`
- Create: `backend/app/services/agent_runtime/handlers/base.py`
- Create: `backend/app/services/agent_runtime/handlers/registry.py`
- Create: `backend/app/services/agent_runtime/handlers/learning_goal.py`
- Modify: `backend/app/services/container.py`
- Modify: `backend/app/api/routes/agent_runtime.py`
- Create: `backend/tests/test_agent_handler_registry.py`
- Modify: `backend/tests/test_agent_runtime_api.py`

- [ ] 为重复 `job_kind`、未知类型、输入 Schema 校验失败和 Handler 版本冻结编写失败测试。
- [ ] 为 `learning_goal` 编写 Handler 测试，固定输入模型为 `goal_id: str` 与 `available_minutes: int[1..1440]`，并验证产物和事件与现状等价。
- [ ] 运行 `python -m pytest tests/test_agent_handler_registry.py tests/test_agent_runtime_api.py -q`，确认测试失败。
- [ ] 实现 `JobHandler`、`HandlerContext`、`HandlerResult`、`RecoveryDecision` 和只读注册表。
- [ ] 把 `_execute_learning_goal_run` 从路由迁入 `LearningGoalHandler`；路由只负责认证、幂等声明、入队和响应映射。
- [ ] `build_container()` 显式注册 Handler；禁止自动扫描 Python 模块，避免不可审计的代码加载。
- [ ] 保留公共 `job_kind` 字符串和值域；未知类型返回稳定业务错误，不返回 Python 类型或栈信息。
- [ ] 重新运行目标测试，预期全部通过。
- [ ] 提交：`git commit -m "separate agent workflows from HTTP routing"`。

### Task 3: 实现带租约 AgentWorker 与崩溃恢复

**Files:**

- Create: `backend/app/services/agent_runtime/worker.py`
- Modify: `backend/app/services/agent_runtime/run_manager.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/app/services/container.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_agent_runtime_recovery.py`
- Create: `backend/tests/test_agent_worker.py`

- [ ] 用可控时钟编写失败测试：Worker 领取、续租、完成、可重试失败退避、达到最大次数失败、取消后不再执行。
- [ ] 编写崩溃测试：Worker A 在 checkpoint 后停止续租，租约过期后 Worker B 恢复；领域副作用只发生一次。
- [ ] 编写审批测试：`AWAITING_APPROVAL` 不被领取，审批后回到 `QUEUED` 并从 checkpoint 继续。
- [ ] 运行 `python -m pytest tests/test_agent_worker.py tests/test_agent_runtime_recovery.py -q`，确认测试失败。
- [ ] 实现 `AgentWorker.start()`、`stop()`、`run_once()` 和心跳协程；为每个实例生成随机、不可复用的 `worker_id`。
- [ ] 增加 `AGENT_WORKER_ENABLED`、`AGENT_WORKER_CONCURRENCY`、`AGENT_WORKER_LEASE_SECONDS`、`AGENT_WORKER_HEARTBEAT_SECONDS`、`AGENT_WORKER_POLL_MS` 配置并校验合理范围。
- [ ] 在 FastAPI lifespan 中启动 Worker，在 shutdown 先停止领取、等待当前 checkpoint，再释放资源；删除“启动时一律标记失败”的旧恢复策略。
- [ ] Worker 被关闭或禁用时，新建任务返回明确 `503`，不得悄悄回退为 HTTP 请求内执行。
- [ ] 重新运行目标测试，预期全部通过。
- [ ] 提交：`git commit -m "make agent runs durable across process restarts"`。

### Task 4: 固化异步 Job API 与原子幂等语义

**Files:**

- Modify: `backend/app/api/routes/agent_runtime.py`
- Modify: `backend/app/schemas/agent_runtime.py`
- Modify: `backend/app/schemas/agent_contract_enums.py`
- Modify: `backend/tests/test_agent_runtime_api.py`
- Modify: `backend/tests/test_agent_runtime_contracts.py`
- Modify: `webreact/tests/agent-runtime-api.test.mjs`
- Modify: `android/app/src/test/java/com/example/campusai/AgentRuntimeApiContractTest.kt`
- Modify: `harmony/entry/src/test/ets/agent/AgentRuntimeModels.test.ets`
- Modify: `wx/miniprogram/services/agent-runtime.test.ts`

- [ ] 增加 API 测试：新建返回 `202` 且 Run 为 `QUEUED`；请求耗时不受 Handler 执行时间影响。
- [ ] 增加幂等重放和冲突测试；冲突必须为 `409 AGENT_IDEMPOTENCY_CONFLICT`。
- [ ] 更新四端契约测试，确认所有客户端接受任意 2xx 成功状态，并保留未知枚举安全降级。
- [ ] 运行后端和各端最小契约测试，确认修改前失败。
- [ ] 路由改用 `create_job_with_run_and_event()`，通过 `Response.status_code` 区分新入队与幂等重放，响应 JSON 字段保持不变。
- [ ] `AGENT_CONTRACT_VERSION` 暂时保留 `v1`；只有未来发生不可兼容 wire format 变更时才新开版本。
- [ ] 运行 `cd backend && python -m pytest tests/test_agent_runtime_api.py tests/test_agent_runtime_contracts.py -q`。
- [ ] 运行 `cd webreact && npm test -- --test-name-pattern="agent runtime"`；若 Node 版本不支持该过滤参数，则运行 `npm test`。
- [ ] 运行 `cd wx && npm run typecheck`。
- [ ] Android 本地测试必须先按仓库说明设置捆绑 JDK 21，再运行 `cd android && .\gradlew.bat testDebugUnitTest --tests "*AgentRuntimeApiContractTest"`。
- [ ] 提交：`git commit -m "define asynchronous and idempotent agent job creation"`。

### Task 5: 优化事件恢复与客户端单一状态源

**Files:**

- Create: `backend/app/services/agent_runtime/event_notifier.py`
- Modify: `backend/app/services/agent_runtime/event_store.py`
- Modify: `backend/app/repositories/agent_runtime_repository.py`
- Modify: `backend/app/api/routes/agent_runtime.py`
- Modify: `backend/app/schemas/agent_contract_enums.py`
- Modify: `backend/app/core/exceptions.py`
- Modify: `backend/tests/test_agent_runtime_sse.py`
- Create: `backend/tests/test_agent_event_recovery.py`
- Modify: `webreact/src/data/agentSseStream.js`
- Modify: `webreact/src/hooks/useAgentRun.js`
- Modify: `webreact/tests/agent-sse-stream.test.mjs`
- Modify: `android/app/src/main/java/com/example/campusai/data/remote/agent/SseEventParser.kt`
- Modify: `harmony/entry/src/main/ets/service/AgentEventReducer.ets`
- Modify: `wx/miniprogram/services/agent-runtime.ts`

- [ ] 编写 SQL 查询计数测试，证明 `Last-Event-ID` 恢复不会加载历史事件列表。
- [ ] 编写 SSE 测试：合法续传、错误 Run 游标、未知游标、心跳、终态关闭、断开不取消。
- [ ] 编写四端 reducer 测试：重复事件、乱序事件、未知事件和 REST 快照后 SSE 续接。
- [ ] 运行目标测试，确认缺少直接游标定位和未知游标错误时失败。
- [ ] 实现 `(run_id, event_id) -> sequence` 直接查询，移除 10,000 条扫描和吞异常逻辑。
- [ ] `AgentEventStore.append()` 提交后通知本进程 `EventNotifier`；SSE 无事件时等待通知，最长 1 秒后查询数据库，兼容多进程写入。
- [ ] 每 15 秒发送 SSE 注释心跳；心跳不写入数据库，不推进客户端业务状态。
- [ ] 客户端将持久化 REST/SSE 事件统一交给同一个 reducer，以 `sequence` 为唯一推进依据。
- [ ] 重新运行后端和跨端目标测试，预期全部通过。
- [ ] 提交：`git commit -m "resume agent event streams from durable cursors"`。

### Task 6: 建立统一 ToolInvocationGateway

**Files:**

- Create: `backend/app/services/agent_runtime/tool_gateway.py`
- Modify: `backend/app/services/agent_runtime/tool_registry.py`
- Modify: `backend/app/services/agent_runtime/risk_engine.py`
- Modify: `backend/app/services/agent_runtime/approval_gate.py`
- Modify: `backend/app/repositories/agent_runtime_repository.py`
- Modify: `backend/app/services/container.py`
- Create: `backend/tests/test_agent_tool_gateway.py`
- Modify: `backend/tests/test_agent_tool_permissions.py`
- Modify: `backend/tests/test_agent_risk_and_approval.py`

- [ ] 为完整校验顺序编写参数化失败测试：未知 Run、非所有者、Handler 未声明、Role 未授权、Schema 错误、跨用户资源、Hard Deny、需要审批、幂等冲突。
- [ ] 编写并发测试：相同工具幂等键和请求哈希最多执行一次领域副作用，重放返回首次结果引用。
- [ ] 编写日志测试，断言原始参数和凭据不出现在事件、审计日志与异常中。
- [ ] 运行 `python -m pytest tests/test_agent_tool_gateway.py tests/test_agent_tool_permissions.py tests/test_agent_risk_and_approval.py -q`，确认测试失败。
- [ ] 将 `ToolSpec` 扩展为 `args_model`、`risk_level`、`ownership_policy`、`executor` 和安全摘要生成器；取消仅按字节大小校验参数的做法。
- [ ] 实现固定顺序的 `invoke()`，所有拒绝路径使用稳定错误码；审批仅保存动作摘要、请求哈希和安全业务引用。
- [ ] 在 `agent_tool_calls` 上实现原子幂等声明和结果引用；租约丢失时不得提交工具完成事件。
- [ ] 对 `AUTO_SAFE` 也执行资源归属和 Hard Deny；`MANUAL_ONLY` 永不由 Agent 自动执行。
- [ ] 重新运行目标测试，预期全部通过。
- [ ] 提交：`git commit -m "centralize agent tool policy and idempotency"`。

### Task 7: 用 Gateway 迁移期末复习高风险写操作

**Files:**

- Create: `backend/app/services/agent_runtime/handlers/final_review.py`
- Modify: `backend/app/api/routes/final_review.py`
- Modify: `backend/app/services/final_review_service.py`
- Modify: `backend/app/services/final_review/adjustment_service.py`
- Modify: `backend/tests/test_final_review_runtime_closure.py`
- Modify: `backend/tests/test_final_review_plans.py`
- Modify: `backend/tests/test_final_review_adjustments.py`
- Modify: `webreact/tests/agent-final-review.test.mjs`

- [ ] 增加端到端失败测试：生成建议不产生写副作用；批准后由 Worker 通过 Gateway 激活；拒绝和过期均不执行。
- [ ] 增加“批准后进程重启”测试，确认 checkpoint 可恢复且激活只发生一次。
- [ ] 运行期末复习测试，确认旧路由直连 `RiskEngine/ApprovalGate` 的路径不能满足新测试。
- [ ] 注册 `final_review.plan.activate` 与 `final_review.adjust.apply` 工具，将审批后的执行移入 Handler checkpoint。
- [ ] 路由只创建命令或解析用户审批，不直接完成 Agent Run；最终状态由 Worker 原子写入。
- [ ] 搜索 `agent_risk_engine`、`agent_approval_gate` 和注册工具调用点，确认迁移范围内不存在绕过 Gateway 的执行路径。
- [ ] 运行 `python -m pytest tests/test_final_review_runtime_closure.py tests/test_final_review_plans.py tests/test_final_review_adjustments.py -q`。
- [ ] 运行 `cd webreact && node --test tests/agent-final-review.test.mjs`。
- [ ] 提交：`git commit -m "make approved review actions resumable and policy-bound"`。

### Task 8: 将能力与 Skill 清单升级为受控版本目录

**Files:**

- Create: `backend/app/services/agent_runtime/capability_registry.py`
- Modify: `backend/app/services/agent_runtime/skill_registry.py`
- Modify: `backend/app/services/agent_runtime/skills.default.json`
- Modify: `backend/app/services/agent_runtime/roles.default.json`
- Modify: `backend/app/services/agent_runtime/agent_registry.py`
- Modify: `backend/app/api/routes/agent_runtime.py`
- Modify: `backend/app/schemas/agent_runtime.py`
- Modify: `backend/tests/test_agent_skills.py`
- Create: `backend/tests/test_agent_capability_registry.py`

- [ ] 为清单 Schema、语义版本、启用状态、角色绑定、Handler 绑定、Tool 引用完整性编写失败测试。
- [ ] 增加生产环境测试：清单损坏必须阻止 runtime 启动；不得静默回退到默认宽权限。
- [ ] 运行目标测试，确认当前静态清单与硬编码 `/capabilities` 无法通过。
- [ ] 实现只读 `CapabilityRegistry`，启动时一次性加载并交叉校验 Agent、Role、Skill、Handler、Tool。
- [ ] `/capabilities` 从注册表生成，不再在路由硬编码；新增字段必须为可选或放入新管理员接口，避免破坏现有客户端。
- [ ] 支持配置级启停和角色绑定，但不支持运行时热加载、远程 URL、压缩包安装或 Python 插件加载。
- [ ] 重新运行目标测试，预期全部通过。
- [ ] 提交：`git commit -m "make agent capabilities versioned and auditable"`。

### Task 9: 增加隐私安全的管理员观测 API

**Files:**

- Create: `backend/app/api/routes/agent_observability.py`
- Create: `backend/app/schemas/agent_observability.py`
- Create: `backend/app/services/agent_runtime/observability.py`
- Modify: `backend/app/repositories/agent_runtime_repository.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_agent_observability.py`

- [ ] 编写鉴权测试：未登录、学生和教师均不可访问；管理员可访问。
- [ ] 编写聚合测试：队列深度、状态分布、成功率、P50/P95 总耗时/模型耗时、Token 总量、工具失败、重试、审批等待和陈旧租约。
- [ ] 编写隐私测试：响应中不存在 prompt、model_response、credential、memory_content、raw_arguments 等字段。
- [ ] 运行 `python -m pytest tests/test_agent_observability.py -q`，确认测试失败。
- [ ] 新增 `GET /api/v1/admin/agent-runtime/overview?since_hours=24` 和 `GET /api/v1/admin/agent-runtime/runs/{run_id}/trace`。
- [ ] 所有查询使用时间范围和最大行数限制；Run trace 只返回安全摘要、状态、阶段、角色、模型名、Token、耗时、错误码、重试和审批时长。
- [ ] 为慢查询增加必要索引，并用测试数据库验证查询计划不做无界全表扫描。
- [ ] 重新运行目标测试，预期全部通过。
- [ ] 提交：`git commit -m "expose privacy-safe agent runtime health to admins"`。

### Task 10: 增加 Web 管理员控制面

**Files:**

- Create: `webreact/src/data/agentObservabilityApi.js`
- Create: `webreact/src/pages/AgentRuntimeOpsPage.jsx`
- Create: `webreact/src/components/agentOps/RuntimeOverview.jsx`
- Create: `webreact/src/components/agentOps/RunTrace.jsx`
- Modify: `webreact/src/App.jsx`
- Modify: `webreact/src/app/routePreload.js`
- Create: `webreact/tests/agent-runtime-ops.test.mjs`

- [ ] 编写页面测试：管理员可进入 `/admin/agent-runtime`，非管理员无入口且路由安全返回首页或 403 状态页。
- [ ] 编写渲染测试：空队列、部分失败、审批积压、陈旧租约、未知事件类型均可读且不崩溃。
- [ ] 运行 `cd webreact && node --test tests/agent-runtime-ops.test.mjs`，确认测试失败。
- [ ] 实现按需加载页面，展示聚合卡片、状态分布和单 Run 时间线；默认不自动高频刷新，手动刷新与 30 秒刷新可选。
- [ ] 不提供任意重放、改状态、执行工具或查看原始模型内容的按钮；第一版严格只读。
- [ ] 运行 `npm test` 和 `npm run build`，预期通过。
- [ ] 提交：`git commit -m "give admins a read-only agent operations view"`。

### Task 11: 建立跨端契约与 CI 门禁

**Files:**

- Modify: `backend/tests/fixtures/agent_runtime/v1/runtime.json`
- Modify: `backend/tests/test_agent_runtime_contracts.py`
- Modify: `webreact/tests/agent-contracts.test.mjs`
- Modify: `android/app/src/test/java/com/example/campusai/data/remote/agent/AgentRuntimeDtoFixtureTest.kt`
- Modify: `harmony/entry/src/test/ets/agent/AgentRuntimeModels.test.ets`
- Modify: `wx/miniprogram/services/agent-runtime.test.ts`
- Create: `.github/workflows/client_contract_ci.yml`

- [ ] 扩充共享 fixture，覆盖新恢复事件、未知未来事件、`202` 创建、幂等冲突和管理员观测脱敏响应。
- [ ] 先让四端契约测试消费同一 fixture 语义，避免各端手写互相漂移的样例。
- [ ] CI 增加 Web `npm test && npm run build` 和微信 `npm run typecheck && npm run check:contracts`。
- [ ] 保留现有后端全量 pytest，并额外把 runtime 原子性、Worker 恢复和跨端 fixture 测试列为显式门禁，便于失败定位。
- [ ] Android CI 暂不使用 `actions/setup-java` 绕过仓库 JDK 规则。当前捆绑 JDK 未纳入 Git，先确定受控 CI 工件或缓存供应方案；方案落地后在 `windows-latest` 从仓库解析路径并运行 Agent 最小单测。
- [ ] HarmonyOS CI 在官方 hvigor/SDK 可重复供应前只执行可独立运行的契约静态校验；不得伪造“已构建”状态。
- [ ] 在本地运行 `cd backend && python -m pytest -q`、`cd webreact && npm test && npm run build`、`cd wx && npm run typecheck && npm run check:contracts`。
- [ ] 提交：`git commit -m "prevent agent contract drift across clients"`。

### Task 12: 灰度、故障演练与收口

**Files:**

- Modify: `backend/README.md`
- Modify: `docs/superpowers/specs/2026-09-12-campus-agent-runtime-v1-design.md`
- Create: `backend/tests/test_agent_runtime_failure_drills.py`

- [ ] 增加故障演练：Handler 异常、模型超时、工具超时、审批期间重启、租约中断、重复请求、SSE 断线重连、数据库短时锁竞争。
- [ ] 验证 SLO：入队 API P95 < 200ms；单实例空闲时调度 P95 < 2s；恢复时间不超过租约期 + 2 次轮询；重复领域副作用为 0；合法游标恢复无事件缺失。
- [ ] 首先只启用 `learning_goal`，观察至少一个完整验收周期；再启用 `final_review`，最后迁移 `course_research` 和 `notice_workflow`。
- [ ] 回滚只关闭 Worker/新建 Job，不删除新表、不降级数据库；已排队任务保留，恢复后继续处理。
- [ ] 更新 README 的运行、配置、恢复、观测和故障处理说明；把 v2 增量决策回写设计文档，不复制 EvoFlow 文档内容。
- [ ] 运行全量后端、Web、微信及可用移动端验证；检查 `git diff`、`git diff --cached`、`git status` 和敏感信息扫描。
- [ ] 提交：`git commit -m "document and validate the durable agent runtime rollout"`。

## 5. 后续独立计划：Notification Channel

通知自动化与 Agent Worker 有依赖，但它是独立的跨平台产品与授权问题，不应塞进首批 v2 内核。只有 P0/P1 达标后再编写独立设计，至少包含：

- `NotificationEnvelope`、渠道偏好、免打扰、时区、截止时间和撤销语义。
- 独立 `notification_outbox`，以 `(channel, recipient, template, business_key)` 幂等投递。
- App 内通知、Android 本地通知、微信订阅消息和未来 Webhook 的适配器。
- 平台授权、失败重试、退订、频控、重复提醒和隐私审计。
- 只消费已提交 Agent 事件，不允许通知失败反向回滚 Agent 业务事务。

## 6. 升级基础设施的触发门槛

满足任一条件时，再为 PostgreSQL/Redis 队列编写独立迁移计划，而不是提前引入：

- 持续需要 2 个以上后端副本并且 SQLite 写锁等待 P95 超过 100ms。
- 活跃 Run 持续超过 20 个，或队列深度超过 100 且持续 15 分钟。
- 单机 Worker 调度延迟 P95 连续 3 天超过 2 秒。
- 需要跨区域执行、优先级队列、定时任务或超过数据库轮询能力的事件广播。

WebSocket 也不作为默认升级项。只有出现客户端双向实时控制、SSE 被目标网络环境稳定阻断，或事件频率明显超出 SSE 适用范围时再评估。

## 7. 完成定义

- HTTP 请求不再直接执行 Agent Workflow。
- 进程在任意安全 checkpoint 重启后，运行可恢复或以稳定错误明确失败，不会长期伪装为 RUNNING。
- 状态、事件、幂等声明和必要业务引用具备明确事务边界。
- 所有注册工具都通过 ToolInvocationGateway；权限、Schema、归属、风险、审批和幂等测试齐全。
- SSE 可按持久化游标准确恢复，四端 reducer 对重复、乱序和未知事件安全。
- 管理员能看到队列、耗时、Token、工具、错误、重试和审批等待，但看不到敏感内容。
- Web/微信契约 CI 生效；Android/HarmonyOS 的未自动化部分有明确、可验证的环境前置条件，不能被标记为已覆盖。
- 全量相关测试通过，工作区只提交本计划对应任务的文件，无密钥、本机路径、缓存或构建产物。
