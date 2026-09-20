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

无学生目标的普通计划会使用 `plan:{plan_id}` 作为干预记录的 scope 键。
这类计划在证据不足以归因时只产出 `WAIT_FOR_EVIDENCE`，**不会**激进替换计划。

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

- 候选模型仅接收受控结构化特征（KC 代码、分数、错误码），不接收源码、答案、课程正文
- 日志只记录 run_id、capability、model key/version、异常类型，不记录异常消息或模型原文
- API key、base URL、绝对路径不写入数据库、响应或日志
- `candidate_annotation.summary` 是**通过 schema + 策略校验后的受限投影**
  （字段集合固定、≤240 字符、禁用词正则、结论必须被输入解释码支撑），
  不是候选模型的原始补全文本；校验失败时不会出现在响应里

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

**真实模型推理状态**：当前 `real_model_inference = false`。仓库内**没有**经授权的
CampusMate-LM 服务凭据，`CAMPUSMATE_LM_ENABLED` 默认关闭，Production 与 Canary 均保持 disabled。
`CandidateModelClient`（OpenAI 兼容）已实现，影子与金丝雀两条路径都有单测覆盖，
但**真实推理未验证**：单测用受控假模型驱动，不得据此声称"已接入真实模型"。

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

1. **真实模型推理未执行**：候选模型的影子与金丝雀两条路径都已接线并有单测覆盖，
   但仓库内没有经授权的 CampusMate-LM 服务，`real_model_inference = false`。
   **不得**把单测里用假模型跑出的绿色记为"真实推理已验证"。
2. **金丝雀展示未在生产开启**：`CAMPUSMATE_LM_CANARY_ENABLED` 默认 `false`，
   且需要存在 `ELIGIBLE_FOR_CANARY` 的 promotion decision 才会展示。
   在默认配置下 `candidate_annotation.available` 恒为 `false`，响应携带稳定 reason。
3. **数据源控制部分生效**：数据源暂停状态已纳入投影 input_digest 与 warning code，
   但事件采集链路尚未完全消费该开关。
4. **Android / HarmonyOS 未做视觉大改**：两端只在既有的目标执行页里补了一块
   世界模型只读卡片，复用现有 repository / DTO / 页面与导航，没有新增独立页面。
5. **HarmonyOS 运行时单测未执行**：本机没有 DevEco Studio 与 HarmonyOS SDK，
   `hvigor test` 无法运行；已用 `harmony/test-host/learner-world-model-contract.test.mjs` 的
   host 契约测试覆盖可离线验证的部分。
6. **Android / HarmonyOS 未做真机验收**：只有编译与单元测试，没有设备上的端到端验收。
7. **反事实模拟在移动端无入口**：移动端给出的是明确的只读降级说明，不是可点击按钮。
   如需在移动端运行模拟，属于新的产品切片。
