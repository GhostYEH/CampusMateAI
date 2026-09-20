# 学习模型演示与体系结构

> 本文档与当前 `master` 上的真实代码和验证状态保持一致。
> 最后核对：2026-09-20。凡是"未执行"的验证，这里都明确写成未执行，不记为通过。

## 体系结构

CampusMateAI 学生世界模型由确定性生产链路和受控的候选模型接线组成：

```
业务事实/事件 → 事件采集 → 状态投影(CORE/ACADEMIC/WORLD) → 预测 → 计划生成
                                   ↑                              ↓
                             数据源控制                    用户确认/执行
                                                                  ↓
                                                          干预记录(adaptive_interventions)
                                                                  ↓
                                       观测窗结束后后台 Worker 评估 → 持久化决策
                                                                  ↓
                             CONTINUE / WAIT_FOR_EVIDENCE / SUSPEND / REPLAN
                                                                  ↓
                          REPLAN → 唯一后继 → 计划血缘与干预血缘原子替换
```

候选模型（CampusMate-LM）**不在**这条链路的任何一个写入位置上：

```
GET /learning-plans/{id}/summary
        ├─ 门禁全过 → 候选结果作为只读字段 candidate_annotation 附加在响应上
        └─ 其余情形 → 降级为 available=false + 稳定 reason，改走影子观测
                                            └→ 只写 model_shadow_runs / model_shadow_results
```

### 自动重规划闭环

效果评估之后不是终点：后台 Worker 会在观测窗到期后比较干预前后的状态，
把决定**落库**，并在需要时自动替换学习计划。整条链路不依赖页面访问。

1. **决策**：`ReplanDecisionPolicy` 是确定性纯函数，不调用任何模型。
   取值只有 `CONTINUE` / `WAIT_FOR_EVIDENCE` / `SUSPEND` / `REPLAN`。
2. **防抖先于落库**：冷却（12h）、单日上限（2 次）、链深（3 层）在**持久化 REPLAN 之前**判定；
   命中时降级为带稳定 reason code 的 `SUSPEND`（保守等待），**不是 FAILED**。
3. **CAS 抢占**：`adaptive_replan_decisions` 的 `APPLYING` 由带 owner + 到期时间的租约持有。
   只有 `PENDING` / 可重试 `FAILED` / **租约已过期** 的 `APPLYING` 能被接手；
   租约未过期时其他 Worker 必须原样退出，**不无条件抢占**。
4. **原子血缘**：计划血缘（旧计划 → 新计划）与干预血缘（旧干预 → 新干预）
   在同一个事务里成对写入。任一步失败整体回滚，旧计划仍是正式版本，
   后继保持暂存态供重试复用，**不会产生两份"当前计划"**。
5. **崩溃可恢复**：决策刚进入 `APPLYING`、后继已暂存但血缘未绑定、
   血缘已绑定但未写 `APPLIED` —— 三种残留都能被重启后的 Worker 幂等完成。

**前端只读**：页面展示的是后端**落库**的决策与 `decision_status`，
不按 delta 或观测结果自行推测；只有 `decision_status = APPLIED` 才显示"已调整学习计划"。

### 两条进入闭环的用户路径

| 路径 | 何时创建干预 | 说明 |
| --- | --- | --- |
| Agent `learning_goal` | 工作流运行到"记录干预"阶段时 | Handler 调 `AdaptiveInterventionService.plan_for_goal`，按策略生成差异化计划 |
| 普通 `POST /learning-plans/generate` | **学生确认（ACCEPT）或执行（EXECUTE）之后** | 走 `AdaptiveInterventionService.adopt_plan`：**不生成新计划、不动计划血缘**，只补一条绑定既有计划的干预记录 |

关键约束：`/generate` 只产出**草案**。未被采纳的计划永远不会创建干预，
也就永远不会被后台自动重规划。确认/执行时若该计划已绑定干预（Agent 路径），
按 `plan_id` 复用，不会产生第二条记录。

采纳链路的幂等键是 `plan-adoption:{plan_id}`，观测窗到期时间由
`ObservationWindowPolicy` 依据计划窗口算出。采纳失败只记警告日志，
**不影响计划确认本身**——闭环是增强项，不是确认的前置条件。

### 无目标普通计划的产品语义

普通 `/learning-plans/generate` 可以不绑定学生目标。这类计划**同样**进入完整的
观测 → 评估 → 重规划闭环，区别只在**归因范围**：

- scope 键是 `plan:{plan_id}`（干预表 `goal_id` 非空，这里用计划自身占位）；
- 归因范围对三端显式出网：`scope_type = "PLAN"`（绑定目标的干预是 `"GOAL"`）；
- 策略有可归因维度时（如 `PACE_RECOVERY`、`WORKLOAD_REDUCTION`），下降会被判为
  `DECLINED` 并**安全替换计划** —— 后继计划由规划器按"无目标计划"生成
  （`goal_id=None`），双向血缘与干预血缘在同一事务写入；
- 策略不可归因时（`BALANCED_PROGRESS`，证据不足）比较器给出
  `INSUFFICIENT_EVIDENCE`，决策收敛到 `WAIT_FOR_EVIDENCE`，**计划保持不变**。

实现要点：`plan:{plan_id}` 只是干预 scope 键，**不是**学生目标。
它必须经 `planner_goal_id()` 翻译成 `None` 才能交给规划器 ——
直接透传会被拒绝（`ValueError: goal 不存在、已归档或无权访问`），
自动重规划就会以 `FAILED` 收场、计划永远换不掉。

三端都必须写明归因范围，避免学生把"没有绑定目标"误读成"系统不会跟进"。

### 确定性生产链路

生产链路完全确定性，不依赖任何外部模型服务：

1. **事件采集**：学习会话、练习作答、任务完成等事件写入 `learner_events` 表
2. **状态投影**：`LearnerStateProjectionService` 从事件计算 CORE/ACADEMIC/WORLD 快照
   - 估算器版本：`deterministic-observed-v1`
   - 输入摘要：SHA-256(canonical JSON of events + sessions + tasks + corrections)
   - 缓存：相同 estimator_version + input_digest + as_of 复用已有 run
3. **学习计划**：`LearningPlannerService` 基于状态投影生成确定性计划
   - 规划器版本：`deterministic-learning-plan-v1`
4. **效果评估**：`LearningPlanEvaluationService` 对比基线和当前指标

## CampusMate-LM shadow / canary 边界

`backend/app/services/model_assist_service.py` 是候选模型**唯一**的业务接线点。
它复用同一个 `ModelCapabilityRegistry` 与同一个 `ModelShadowRunner` 实例
（同一套熔断器、并发闸门、采样器），因此不存在"第二套模型系统"。

### 影子模式（shadow）

- 调用点：`GET /api/v1/learning-plans/{plan_id}/summary`（FastAPI `BackgroundTasks`，
  响应发出之后才执行）。这是已注册只读能力 `learning_summary_v1` 的真实业务入口。
- 输入只包含受控结构化特征：计划 id、warning codes、解释码枚举、条目类型、
  时长、数据质量、证据计数、截止时间桶、阶段、置信度分桶。
  **不含**源码、答案、课程正文、任务标题、用户自由文本、内部 id 或凭据。
- 输出只写入 `model_shadow_runs` / `model_shadow_results`，调用方拿到的是 `None`。
- `request_id` 由 `(plan_id, 输入摘要)` 派生，因此重复查看同一份计划只会有一条影子记录。

### 金丝雀展示（canary）

- 同一个调用点。只有 7 项门禁全过才调用候选模型，并把结果作为
  `LearningPlanSummaryOut.candidate_annotation` 附加在生产响应上。
- 注解字段是**只读**的：`read_only=true`、`affects_production=false`，
  且不参与任何状态、计划、任务或决策的写入。
- 可识别：`capability_name` / `model_key` / `prompt_version` / `inference_source`。
- 可降级：`available=false` + 稳定 `reason`。覆盖 `canary_feature_flag_disabled`、
  `candidate_model_not_configured`、`model_shadow_paused_for_user`、
  `no_promotion_decision`、`quality_gates_failed`、`circuit_breaker_open`、
  `MODEL_RATE_LIMITED`、`MODEL_TIMEOUT`、`MODEL_SCHEMA_INVALID`、
  `MODEL_POLICY_VIOLATION`、`MODEL_DISABLED`、`MODEL_UNAVAILABLE` 等。
- 可追溯：`shadow_run_id` + `input_digest` 指向影子表里的那一次观测。
- 采样：`CAMPUSMATE_LM_CANARY_SAMPLE_RATE`（默认 `1.0`）与影子采样
  `CAMPUSMATE_LM_SHADOW_SAMPLE_RATE` 解耦——前者控制"展示多少"，后者控制"记录多少"。

### 数据最小化

- 候选模型只接收受控结构化特征：条目类型、时长、数据质量、证据计数、解释码枚举、
  截止时间桶、置信度分桶。**不发送** `plan_id` / `user_id` / `task_id` / `goal_id` /
  `run_id` 等任何稳定内部标识，也不发送源码、答案、课程正文、任务标题或用户自由文本。
- 本地影子记录与生产响应之间的关联由 `request_id`（形如
  `plan-summary:{plan_id}:{input_digest前16位}`）与 `input_digest` 完成 ——
  两者都在请求信封与落库侧，**不进入发给模型的 messages**。
- 日志只记录 run_id、capability、model key/version、异常类型，不记录异常消息或模型原文
- API key、base URL、绝对路径不写入数据库、响应或日志
- `candidate_annotation.summary` 是**通过 schema + 策略校验后的受限投影**
  （字段集合固定、≤240 字符、禁用词正则、结论必须被输入解释码支撑），
  不是候选模型的原始补全文本；校验失败时不会出现在响应里

### 熔断与探测权

`ModelShadowRunner` 的 half-open 探测权（`probe_in_flight`）**只能由 `run()` 占用**：

- `canary_gate` 用只读的 `canary_allowed()`，`circuit_status()` 也只读；
- 网关或状态查询一旦占用探测权，真正调用候选模型的 `run()` 就会拿不到探测权、
  被判 `MODEL_CIRCUIT_OPEN`，熔断永远停在 HALF_OPEN、再也关不上；
- `run()` 在申请探测权之前先把请求体构造完，并用 `finally` 兜底释放，
  即使调用被取消（`CancelledError` 是 `BaseException`）也不会把探测权留在手里。

### 并发语义：熔断代次（generation）

熔断状态机不只是"计数 + 时间戳"。每次熔断**状态迁移**（打开 / 关闭）都会推进一个
代次（`generation`），一次调用在放行时记下当时的代次，返回时只有代次仍然一致，
才允许改动熔断状态：

| 情形 | 行为 |
| --- | --- |
| 旧请求在熔断打开**之前**发起、half-open **之后**才返回（成功） | **不关闭熔断**：用旧观察去关断会把全部流量立刻重新打向仍在故障的下游 |
| 旧请求同上但返回失败 | 不计入失败计数，也不释放当前探测者的探测权 |
| 并发打进来多个 half-open 请求 | 只有一个拿到探测权，其余判 `MODEL_CIRCUIT_OPEN` |
| 探测成功 / 失败 / 取消 | 三种结束路径都归还探测权；取消不写失败计数 |

`_circuit_allows()` 返回 `(allowed, generation)`，`run()` 把代次原样回传给
`_record_success` / `_record_failure` / `_release_probe`。放行与取代次必须在同一段
**没有 `await`** 的同步代码里完成，否则两者可能来自不同的熔断状态。

### 线程模型：熔断状态只在事件循环上被修改

这一点决定了"不需要加锁"，已用测试钉住：

- **唯一的写入方**是 `run()`，它只被 `async def summarize_learning_plan`
  与其 `BackgroundTasks` 异步回调 await —— 都在事件循环上；
- `GET /learner-state/canary-gate/{capability}` 是**同步**路由（`def`），
  FastAPI 会把它放进 **threadpool** 执行。它现在只用只读的 `canary_allowed()`，
  多线程并发调用后熔断状态逐字段不变（有单测）；
- 后台 Worker 通过 `asyncio.to_thread` 在 **worker 线程**里跑 `tick`，
  但 `adaptive_agent` 包**零引用**熔断器（有源码级断言守着这条不变量）。

> 顺带发现：在 `4c30001b` 之前，门禁调用的是会写入 `probe_in_flight` 的
> `_circuit_allows`，而它所在的路由是同步路由 —— 也就是说那次写入**来自 worker 线程**，
> 与事件循环上真实进行的 half-open 探测并发。修复门禁的同时也消除了这个跨线程写入。

### 部署形态与跨进程一致性（重要）

**当前部署是单服务进程，因此进程内熔断状态是一致且正确的。**

证据：

- 仓库内所有启动入口都是 `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
  （`start_backend.bat`、`README.md` ×3、`backend/README.md`、`docs/DEVICE_TEST_CHECKLIST.md`），
  **没有 `--workers`**；
- 仓库内没有 gunicorn / Dockerfile / docker-compose / K8s manifest；
- 应用自身的后台能力（`AgentWorker`、`AdaptiveReplanningWorker`）就是**进程内 asyncio 任务**
  + 数据库租约协调，设计上已经假设单服务进程。

**触发条件**：一旦改成 `--workers N`、gunicorn 多 worker 或 K8s 多副本，
`ModelShadowRunner._circuits` 就变成**每进程一份**，会出现：

1. 失败阈值不聚合 → 熔断打开延迟最多 N 倍；
2. `canary_gate` 的 `circuit_breaker_open` 只反映当前进程 → 同一用户在实例 A 放行、实例 B 拒绝；
3. 探测权每进程独立 → 冷却结束后 N 个实例同时探测（探测风暴）。

**这属于设计变更，不属于本次修复范围**：实现跨进程一致的熔断需要共享存储
（Redis 或新的数据库表），本任务明确不允许擅自引入。最小可行方案与迁移影响见
`## 当前风险与未完成项` 中的 P1 条目。

### CPM 使用边界

候选模型输出与状态投影都只能作为**受控个性化上下文**（例如"该生本周截止压力偏高"），
**不得**当作校园政策事实（考试时间、报名截止、培养方案要求等）使用。
校园政策事实的唯一来源是教务/通知/课程等权威数据源；CPM 若引用世界模型，
必须保留"这是推测/这是学生自述/这是权威事实"的来源标注。

## 三个演示场景

> 说明：这里只列**当前代码真正支持**的场景。C 语言练习系统（`practice_attempts`、
> 误区假设等）已在 `ad6fa731` 整体移除，原先的 `pointer-recovery` 场景随之删除；
> 若在文档或脚本里再看到它，说明那份材料已经过时。

### 1. deadline-pressure（截止任务与时间预算）

- 创建 3 个截止任务（12h/36h pending + -6h 已逾期）
- 记入 1 个 30 分钟学习会话事件
- 生成 CORE snapshot 展示任务负载
- 生成可解释计划展示时间预算

### 2. stale-source-replan（数据源失效）

- CHAOXING 数据源设为 PAUSED
- 计入 48h 前的 stale 同步事件
- 状态显示 PARTIAL/STALE
- replan 不依赖已暂停来源

### 3. shadow-model-blocked（模型影子评测）

- 候选模型产生 quality_gate_micro_f1 门禁失败
- promotion decision 为 BLOCKED
- 生产确定性结果不受影响
- 模型透明度显示阻断原因

## 指标来源说明

| 指标类别 | 来源 | 说明 |
|---------|------|------|
| 状态投影质量 | 确定性计算 | 基于事件覆盖率和新鲜度 |
| 知识掌握度 | 确定性计算 | 基于练习正确率和达衰减桶 |
| 计划分配 | 确定性计算 | 基于优先级和可用时间 |
| 影子评测指标 | fixture 预测文件 | 当前未接入真实模型推理 |
| 延迟/吞吐 | fixture 固定值 | latency_ms=2, throughput=unavailable |

**真实模型推理状态**：**未验证**。当前 `real_model_inference = false`。

- 仓库内**没有**经授权的 CampusMate-LM 服务凭据：`backend/.env` 与 `backend/.env.example`
  里都**不存在**任何 `CAMPUSMATE_LM_*` 键（已用键名清单核对，未读取任何值）；
- `CAMPUSMATE_LM_ENABLED` 默认 `false`，Production 与 Canary 均保持 disabled；
- 候选适配器就是既有的 OpenAI 兼容客户端（`OpenAICompatibleClient`），无独立重试策略，
  超时由 `CAMPUSMATE_LM_TIMEOUT_MS` 与 `asyncio.wait_for` 双重约束；
- 影子与金丝雀两条路径都有单测覆盖，但**全部由受控假模型驱动**，
  不得据此声称"已接入真实模型"。

**上线时用户需要提供的配置**（缺任意一项都不会产生真实调用）：

| 配置项 | 说明 |
| --- | --- |
| `CAMPUSMATE_LM_ENABLED=true` | 总开关，默认关闭 |
| `CAMPUSMATE_LM_BASE_URL` | 候选服务 origin，必须是安全的 HTTP(S)，不接受 URL 内嵌凭据/query/fragment |
| `CAMPUSMATE_LM_API_KEY` | 候选服务凭据，只写入未追踪的 `backend/.env` |
| `CAMPUSMATE_LM_MODEL_NAME` | 候选模型名 |
| `CAMPUSMATE_LM_CANARY_ENABLED=true` | 只读金丝雀展示开关（另需 promotion decision = `ELIGIBLE_FOR_CANARY`） |

外加一项**非配置**前置条件：候选能力的 `model_promotion_decisions` 记录必须为
`ELIGIBLE_FOR_CANARY` 且无失败门控，金丝雀才会展示。

## 跨端覆盖

| 能力 | Web | Android | HarmonyOS | 微信小程序 |
| --- | --- | --- | --- | --- |
| 状态投影摘要 + 数据质量/警告 | ✅ | ✅（`GoalExecutionScreen` 世界模型卡片） | ✅（`GoalExecutionPage` WorldModelCard） | 不在范围内 |
| 预测摘要 | ✅ | ✅ | ✅ | 不在范围内 |
| 计划状态 + 自动重规划结果 | ✅ | ✅（只认后端 `decision_status`） | ✅（只认后端 `decision_status`） | 不在范围内 |
| 反事实模拟 | ✅ 可运行 | 明确只读降级说明（本端无入口） | 明确只读降级说明（本端无入口） | 不在范围内 |
| 数据源控制 | ✅ 可切换 | ✅ 可切换 ENABLED/PAUSED | ✅ 可切换 ENABLED/PAUSED | 不在范围内 |
| 模型透明度 | ✅ | ✅ | ✅ | 不在范围内 |

微信小程序当前**不在世界模型的产品范围内**（`wx/miniprogram/app.json` 无相关页面，
全局检索无 learner-state / forecast / learning-plans 调用），本次不做开发。

## 演示脚本

```powershell
# 运行所有场景的完整流程（seed → verify → clear）
.\scripts\run-learner-model-demo.ps1 -Action all

# 仅注入数据
.\scripts\run-learner-model-demo.ps1 -Action seed

# 仅清理
.\scripts\run-learner-model-demo.ps1 -Action clear

# 指定场景
.\scripts\run-learner-model-demo.ps1 -Action all -Scenario stale-source-replan
```

脚本从自身位置解析仓库根目录，使用独立演示数据库，不修改开发者现有数据库。

## 可复现的验证命令

Web 的 E2E 入口不再直接调用裸 `python`（Windows 开发机上通常不存在），
而是统一走 `webreact/scripts/run-python.mjs`：按 `PYTHON` / `PYTHON_BIN` 环境变量 →
仓库内 `backend/.venv` → PATH 上的 `python3` / `python` → Windows `py -3` 的顺序解析，
并把最终选中的解释器打印出来。没有硬编码任何机器绝对路径。

```bash
# 后端：世界模型 / 闭环 / 候选接线相关子集
cd backend && PYTHONPATH=. ./.venv/Scripts/python.exe -m pytest tests/ -q \
  -k "adaptive or learner_state or learning_plan or model_shadow or canary or forecast or simulation or world"

# ML：learner_state_evaluation
cd ml && ../backend/.venv/Scripts/python.exe -m pytest tests/test_learner_state_evaluation.py -q

# Web：单测 + 生产构建
cd webreact && npm test && npm run build

# Web：learner-state 浏览器闭环 E2E（桌面 1440x900 + 移动 390x844）
cd webreact && npm run test:e2e:learner-state

# Android：单元测试 + Debug 构建（必须使用仓库捆绑 JDK 21）
cd android && JAVA_HOME="$PWD/.tools/jdk21-full/jdk-21.0.12+8" \
  PATH="$JAVA_HOME/bin:$PATH" ./gradlew --offline :app:testDebugUnitTest :app:assembleDebug

# HarmonyOS：host 契约测试（纯 Node，不需要 DevEco）
node --test harmony/test-host/*.test.mjs

# HarmonyOS：运行时单测（需要 DevEco Studio + HarmonyOS SDK 6.1.1）
#   $hvigor = Join-Path $env:DEVECO_HOME 'tools\hvigor\bin\hvigorw.bat'
#   & $hvigor test --no-daemon
```

## 当前风险与未完成项

### 已实现并验证（本轮）

- **熔断并发语义**：新增熔断代次（generation）门控，旧请求晚返回既不释放他人
  half-open 探测权、也不关闭熔断；并发 half-open 只产生一次真实探测。
  回归测试见 `backend/tests/test_model_shadow_runner.py` 的「并发 / 熔断状态机回归」一节。
- **候选模型配置入口可发现**：`backend/.env.example` 补齐 16 个 `CAMPUSMATE_LM_*` 键，
  并有双向契约测试保证「模板 ↔ Settings 字段」完全一致、凭据键保持留空。
- **默认关闭**：默认配置下不构造候选客户端、不发起任何真实调用（有测试钉住）。
- **候选 TLS 与通用 LLM 解耦**：新增 `CAMPUSMATE_LM_TLS_MAX_VERSION`。留空时**沿用**
  `LLM_TLS_MAX_VERSION`（与历史行为逐位一致，升级不改变线上表现）；显式设置时只作用于
  候选服务；非法值启动即失败。

### 阻塞项（需要外部条件，未验证）

1. **真实模型推理未验证**：缺经授权的候选服务凭据（`CAMPUSMATE_LM_BASE_URL` /
   `CAMPUSMATE_LM_API_KEY` / `CAMPUSMATE_LM_MODEL_NAME`）与 `ELIGIBLE_FOR_CANARY`
   的 promotion decision。在拿到之前**不调用任何外部服务**，也不得声称真实推理已验证。
2. **Android 运行时验证未执行**：本机没有 Android SDK platform-tools / `adb` / 模拟器
   （`adb devices` 不可用），无法验证世界模型页面的加载、失败降级、`scope_type` 与
   重规划结果在真实设备上的呈现。已执行的部分：538 个单测（0 失败）+ Debug APK 构建，
   以及新增的 `LearnerWorldModelSectionContractTest` 源码级契约测试。
3. **HarmonyOS 运行时单测与 HAP 构建未执行**：本机没有 DevEco Studio
   （`DEVECO_HOME` 为空、`local.properties` 指向的 SDK 路径不存在）。
   已执行的部分：`node --test harmony/test-host/*.test.mjs`（26 例）。
   按要求**未安装或修改本机环境**。

### 设计决策（需要授权才能推进）

4. **跨进程熔断一致性（P1）**：当前单进程部署下无风险（证据见上文「部署形态与跨进程一致性」）。
   一旦水平扩展就需要共享状态。**最小可行方案**（未实施，需授权）：

   - 数据模型：一张 `model_circuit_state` 表，主键 `(capability_name)`，列
     `failures INTEGER`、`opened_at REAL`、`probe_owner TEXT`、`probe_expires_at REAL`、
     `generation INTEGER`、`updated_at TEXT`；
   - 原子占用：用条件 UPDATE 实现 CAS，例如
     `UPDATE model_circuit_state SET probe_owner=?, probe_expires_at=? WHERE capability_name=?
      AND (opened_at IS NULL OR :now - opened_at >= :cooldown) AND (probe_owner IS NULL OR probe_expires_at < :now)`，
      `rowcount=1` 才算拿到探测权；探测权带过期时间，避免实例崩溃后永久卡死；
   - 迁移影响：新增一张表 + 一次 schema 初始化，不改任何既有表；
     每次放行/记账多一次数据库往返（SQLite 本地约 0.1–1ms），需要在
     `CAMPUSMATE_LM_*` 超时预算内重新评估；
   - 需要授权：新增数据库结构、引入跨进程协调语义（以及可能的外部存储选型）。
   - 替代方案（成本更低但语义更弱）：把阈值按 worker 数下调 `T/N`，
     或对候选调用做 sticky 路由；两者都不解决 `canary_gate` 的跨实例决策不一致，
     只作为过渡手段。

### 其余已知风险

5. **金丝雀展示未在生产开启**：默认 `false` 且需要 promotion decision；
   默认配置下 `candidate_annotation.available` 恒为 `false`，响应携带稳定 reason。
6. **数据源控制：`CORE_STUDY` / `PERSONAL_TASK` 的暂停语义未实现（需产品决策）**。
   实测（`learner_event_service.py`）：
   - `record_chaoxing_*` / `record_edu_*` / `record_campus_*` / `record_self_report_*` 等
     入口都会调用 `_is_source_skipped`，暂停后确实不再创建派生 learner event；
   - 但 `record_study_session_finished`（`source="study"`）与
     `record_personal_task_completed`（`source="personal_task"`）**没有**该检查；
   - 且 `should_skip_learner_event` 的映射表键写的是 `"core_study"`，与实际写入的
     `"study"` **不匹配** —— 即使补上调用也命不中；
   - 投影侧 `paused_sources` 只对 `EDU` / `CHAOXING` 做降级，`CORE_STUDY` / `PERSONAL_TASK`
     只体现在 input digest 与通用 warning 上。

   后果：界面对这两个来源同样提供「暂停」按钮，但暂停几乎不产生实际效果。

   **两处契约声明互相矛盾**，因此这是产品决策而非可直接修的缺陷：
   - `learner_model_source_policy` 模块文档写「被暂停后，不再为该来源创建新的 learner event」；
   - `should_skip_learner_event` 的 docstring 写「核心业务事件（study session finish,
     task complete）不受数据源控制影响，始终保存」；
   - 界面只提供通用开关，没有任何解释性文案，不能作为判据。

   两种意图各自的最小改动：
   - 若要**生效**：把映射键 `"core_study"` 改为 `"study"`，并在
     `record_study_session_finished` / `record_personal_task_completed` 里补
     `_is_source_skipped` 检查（约 6 行）。
   - 若要**保持"核心记录始终保存"**：把映射表里的 `"core_study"` / `"personal_task"`
     两个死键删掉，并在界面与文档里写明这两个来源的暂停只影响投影权重、不停止记录。

   在拿到产品决策前**不做改动**（属于用户可见的同意语义，不宜擅自变更）。
7. **移动端反事实模拟无入口**：给出的是明确的只读降级说明，不是可点击按钮。
   如需在移动端运行模拟，属于新的产品切片。
8. **测试会读取开发机的 `backend/.env`**：`Settings` 的 `env_file=".env"` 使默认值依赖本机配置
   （例如本机 `LLM_TLS_MAX_VERSION=1.2`）。因此断言默认值时必须写**不变量**而不是绝对值，
   否则测试会随开发机漂移。已在候选 TLS 测试里按此写法处理。
