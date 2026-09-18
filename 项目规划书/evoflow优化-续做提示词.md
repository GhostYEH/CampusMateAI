# CampusAgentRuntime v2 —— 续做交接提示词

> 用途：把 `项目规划书/evoflow优化.md` 剩余任务交给另一个 agent 继续执行。
> 直接复制「## 给下一个 agent 的提示词」整段作为开场指令即可。

---

## 当前进度快照（截至 2026-09-14 23:50）

分支：`master`（**不要新开分支**）。已完成并提交：

| 计划任务 | 状态 | 落地提交 |
| --- | --- | --- |
| Task 1 原子事务 + 持久化队列数据模型 | ✅ | `252fdfcf` |
| Task 2 JobHandlerRegistry + 迁移 learning_goal | ✅ | `39d2bbba` |
| Task 3 带租约 AgentWorker + 崩溃恢复 | ✅ | `39d2bbba` |
| Task 4A 异步 Job API + 能力准入 + 原子幂等 | ✅ | `39d2bbba` |
| Task 4B 三端异步客户端业务流 | ✅ | `39d2bbba` |
| Task 5 SSE 游标恢复 + 单一事件源 | ✅ | `5f8e80af`、`645ff5a4` |
| Task 6 统一 ToolInvocationGateway | ✅ | `619ec3b9` |
| **Task 7 期末复习高风险写操作走 Gateway** | ✅ **已完成** | 见下 |
| Task 8 能力/Skill 受控版本目录 | ✅ | `46dd34ab` |
| Task 9 管理员观测 API | ✅ | `e56262c8` |
| Task 10 Web 管理员控制面 | ✅ | `a42890db` |
| Task 11 跨端契约与 CI 门禁 | ✅ | `5299f608` |
| Task 12 灰度、故障演练与收口 | ✅ | `b69fbca8` |

**Task 1–12 全部完成。**

### Task 7 落地内容

- 新建 `backend/app/services/agent_runtime/handlers/final_review.py`：
  `final_review_plan_activate` / `final_review_adjust_apply` 两个 Handler，
  经 `ToolInvocationGateway` 执行；副作用完成后写 `checkpoint.stage=APPLIED`，
  恢复时直接返回既有结果，不重复触碰领域 Service。
- 新增工具 `final_review.plan.activate` / `final_review.adjust.apply`
  （`args_model` + `ownership_resolver` + `executor`），并在 `roles.default.json`、
  `capabilities.default.json` 中登记。
- `ToolInvocationRequest` 新增可选 `approval_id`：Gateway 复核既有审批，
  **已批准才执行，拒绝/过期一律拒绝**；`awaiting_approval` 重放同样复核审批状态，
  使"批准后进程重启"可从安全恢复点继续。
- 路由改为只创建命令：`POST /campaigns/{id}/activate` 与
  `POST /adjustment-proposals/{id}/decision` 返回 `status=PENDING` + `run_id`，
  终态由 Worker 原子写入；拒绝仍只做收口，不创建命令。
- `FinalReviewRepository.apply_proposal_version()`：创建新版本 + 激活 + 标记提案
  在**同一事务**内完成，避免崩溃重放产生第二个版本。
- `services/final_review_service.py` 退化为无副作用的兼容壳，
  移除绕过 Gateway 的直连写路径。
- Web `FinalReviewPage` 在激活命令返回 `activated=false` 时有界轮询，
  等计划真正生效再刷新。

### 已验证（2026-09-14 晚）

- 后端全量 `pytest`：**1489 passed / 6 skipped / 0 failed**（10 分钟）。
- 期末复习目标测试：`test_final_review_runtime_closure.py` 10 passed、
  `test_final_review_plans.py` + `test_final_review_adjustments.py` +
  `test_final_review_daily_agenda.py` + `test_final_review_campaigns.py` 全绿。
- 反向验证：把新测试放到改动前的 HEAD 快照上运行，
  `test_final_review_adjustments.py` 2 failed（`KeyError: 'run_id'`）、
  `test_final_review_runtime_closure.py` 收集即报错——确认旧路由的直连写路径
  无法满足新测试。
- Web：`npm test` 424 passed；`npm run build` 通过。
- Android / HarmonyOS：本次改动只涉及后端响应**追加可选字段**与 Web 页面，
  未改任何端侧 DTO 或契约 fixture，因此未重跑移动端测试。


已存在的新产物（可直接复用，不要重写）：

- `backend/app/services/agent_runtime/worker.py` —— `AgentWorker`，含 `start/stop/run_once`、租约续期、退避重试、崩溃恢复、`AWAITING_APPROVAL` 释放租约。
- `backend/app/services/agent_runtime/handlers/` —— `base.py`（Handler 契约）、`registry.py`（`register/freeze/require`）、`learning_goal.py`。
- `backend/app/services/agent_runtime/tool_gateway.py` —— 固定顺序校验 + 幂等声明 + 审批。
- `backend/app/services/agent_runtime/event_notifier.py` —— 同进程 SSE 唤醒，跨进程靠 1 秒轮询兜底。
- 仓储新方法：`create_job_with_run_and_event` / `transition_run_with_event` /
  `complete_run_with_job_output_and_event` / `claim_next_run` / `renew_run_lease` /
  `save_checkpoint` / `release_run_lease` / `get_event_sequence` / `claim_tool_call` / `get_tool_call`。
- 新错误码：`AGENT_CAPABILITY_DISABLED`(409)、`AGENT_RUNTIME_UNAVAILABLE`(503)、`AGENT_CURSOR_INVALID`(409)。
- 新事件类型：`RUN_RETRY_SCHEDULED`、`RUN_RECOVERY_STARTED`、`RUN_RECOVERED`。
- 配置项：`AGENT_RUNTIME_MODE=worker|drain|disabled`、`AGENT_WORKER_CONCURRENCY`、
  `AGENT_WORKER_LEASE_SECONDS`、`AGENT_WORKER_HEARTBEAT_SECONDS`、`AGENT_WORKER_POLL_MS`。

---

## 给下一个 agent 的提示词

```text
你负责继续实施 D:\File\demo1\项目规划书\evoflow优化.md（CampusAgentRuntime v2）的剩余任务。

## 已完成的边界（不要重做，先读代码再动手）

Task 1–6 已完成并提交在 master 上。关键既有实现：
- backend/app/services/agent_runtime/worker.py —— AgentWorker（租约、心跳、退避重试、崩溃恢复）
- backend/app/services/agent_runtime/handlers/{base,registry,learning_goal}.py —— Handler 契约与只读注册表
- backend/app/services/agent_runtime/tool_gateway.py —— ToolInvocationGateway（固定校验顺序）
- backend/app/services/agent_runtime/event_notifier.py —— 同进程 SSE 唤醒
- backend/app/repositories/agent_runtime_repository.py —— 所有原子写方法（create_job_with_run_and_event /
  transition_run_with_event / complete_run_with_job_output_and_event / claim_next_run / renew_run_lease /
  save_checkpoint / release_run_lease / get_event_sequence / claim_tool_call / get_tool_call）
- backend/app/services/container.py 已装配 agent_handler_registry / agent_worker /
  agent_event_notifier / agent_tool_gateway

## 你要做的（只剩 Task 7）

### Task 7：用 Gateway 迁移期末复习高风险写操作（P0）

新建 `backend/app/services/agent_runtime/handlers/final_review.py`，把
`final_review.plan.activate` 与 `final_review.adjust.apply` 注册为工具
（绑定 `args_model` / `ownership_resolver` / `executor`），把审批后的实际执行移入 Handler checkpoint，
路由只创建命令或解析用户审批，最终状态由 Worker 原子写入。

改动文件：

- `backend/app/services/agent_runtime/handlers/final_review.py`（新建）
- `backend/app/api/routes/final_review.py`
- `backend/app/services/final_review_service.py`
- `backend/app/services/final_review/adjustment_service.py`
- `backend/app/services/container.py`（注册 Handler 与工具）
- `backend/tests/test_final_review_runtime_closure.py`、`test_final_review_plans.py`、
  `test_final_review_adjustments.py`
- `webreact/tests/agent-final-review.test.mjs`

必须新增的测试：

1. 生成建议不产生写副作用；
2. 批准后由 Worker 经 Gateway 激活；
3. 拒绝与过期都不执行；
4. "批准后进程重启"可从 checkpoint 恢复且激活只发生一次。

最后搜索 `agent_risk_engine` / `agent_approval_gate` / 注册工具调用点，
确认迁移范围内不存在绕过 Gateway 的执行路径。

验证：
```bash
cd backend && ./.venv/Scripts/python.exe -m pytest \
  tests/test_final_review_runtime_closure.py tests/test_final_review_plans.py \
  tests/test_final_review_adjustments.py -q
cd ../webreact && node --test tests/agent-final-review.test.mjs
```

提交信息：`make approved review actions resumable and policy-bound`

> 注意：`final_review` 相关的审批链路目前散落在路由里（`container.agent_approval_gate.require(...)`、
> `container.agent_risk_engine`），迁移时不要顺手重构无关的期末复习业务逻辑，
> 只把"审批后的执行"收进 Handler + Gateway。

## 仓库硬约束（必须遵守）

1. 在 master 上直接做，不要新开分支。每次提交后用 `git branch -a --contains HEAD` 确认落点并告知用户。
2. **只提交本次任务相关的文件**：并行会话会同时改 `backend/app/services/chaoxing/*`、
   `backend/app/services/learner_state_service.py`、`webreact/src/pages/CourseDetailPage.jsx`、
   `docs/superpowers/specs/2026-09-14-task-breakdown-plan-design.md` 等。
   用 `git add <明确路径>`，禁止 `git add -A`；加完用 `git diff --cached --name-status` 逐条核对。
   提交前先跑 `git status --short` 确认没有别人的改动被带进来。
3. 后端测试：
   `cd backend && ./.venv/Scripts/python.exe -m pytest tests/<目标文件> -q`
   （Python 在 Windows 下用 `./.venv/Scripts/python.exe`，不要用裸 `python`）。
4. 前端测试：`cd webreact && node --test tests/<file>.test.mjs`；全量 `npm test`、`npm run build`。
   注意 `vite build` 清空真实 `dist/` 会触发批量删除守卫，验证编译请用
   `npx vite build --outDir <临时目录> --emptyOutDir`。
5. pytest 临时目录偶发 `PermissionError: [WinError 5]` 会造成整批假失败，先怀疑环境；
   加 `--basetemp=./.pytest_tmp` 复跑，跑完删掉。
6. Android/JVM 命令必须用仓库捆绑 JDK：
   `$env:JAVA_HOME = <repo>/android/.tools/jdk21-full/jdk-21.0.12+8`。
   HarmonyOS 本机缺 hvigor/ohpm，只能做静态核对，不要谎报"已跑测试"。
7. 不要修改数据库结构、公开 API 语义或部署流程，除非计划里明确要求。
   公共字段与枚举只能追加，不得改名或改变已发布语义。
8. 不保存 prompt、隐藏推理、完整模型响应、凭据或敏感工具参数到事件/审计/日志。
9. 不要复制 EvoFlow 源码、前端资源或技能包。

## 完成标准

每个任务：先写失败测试 → 最小实现 → 目标测试转绿 → 精确暂存 → 单独提交。
全部完成后跑一遍 `cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q`（约 8 分钟，
建议后台跑）与 `cd webreact && npm test && npm run build`，并在最终回复里说明：
做了什么、落在哪个提交、哪些验证通过、哪些未验证及原因。
```

---

## 剩余任务清单（自查用）

- [x] Task 7 期末复习写操作走 Gateway（P0）—— 已完成
- [x] Task 8 / 9 / 10 / 11 / 12 已完成
- [x] 全量回归已跑（见上方"已验证"）

**Task 1–12 全部完成，本交接文档仅作历史记录。**
