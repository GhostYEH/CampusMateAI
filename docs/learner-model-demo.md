# 学习模型演示与体系结构

## 体系结构

CampusMateAI 学生世界模型由确定性生产链路和可选影子评测组成：

```
学习事件 → 事件采集 → 状态投影 → 学习计划 → 计划执行 → 效果评估
                ↑                         ↑              ↓
          数据源控制                 状态纠正      持久化决策（落库，页面只读）
                                                             ↓
                              CONTINUE / WAIT_FOR_EVIDENCE / SUSPEND / REPLAN
                                                             ↓
                              REPLAN → 唯一后继 → 计划血缘与干预血缘原子替换
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

### 确定性生产链路

生产链路完全确定性，不依赖任何外部模型服务：

1. **事件采集**：学习会话、练习作答、任务完成等事件写入 `learner_events` 表
2. **状态投影**：`LearnerStateProjectionService` 从事件计算 CORE/KNOWLEDGE 快照
   - 估算器版本：`deterministic-observed-v1`
   - 输入摘要：SHA-256(canonical JSON of events + sessions + tasks + corrections)
   - 缓存：相同 estimator_version + input_digest + as_of 复用已有 run
3. **学习计划**：`LearningPlannerService` 基于状态投影生成确定性计划
   - 规划器版本：`deterministic-learning-plan-v1`
4. **效果评估**：`LearningPlanEvaluationService` 对比基线和当前指标

### CampusMate-LM shadow/canary 边界

影子评测和金丝雀展示严格与生产写链路隔离：

- **影子模式**：候选模型输出只写入 `model_shadow_runs/results` 表，不影响学习状态、计划或任务
- **金丝雀展示**：仅当门禁全部通过时，候选输出作为只读展示附加在生产响应中
- **回退保证**：候选模型超时、非法输出或门禁失败时，生产响应不受影响

### 数据最小化

- 候选模型仅接收受控结构化特征（KC 代码、分数、错误码），不接收源码、答案、课程正文
- 日志只记录 run_id、capability、model key/version、异常类型，不记录异常消息或模型原文
- API key、base URL、绝对路径不写入数据库、响应或日志

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
| 知识掌握度 | 确定性计算 | 基于练习正确率和衰减桶 |
| 计划分配 | 确定性计算 | 基于优先级和可用时间 |
| 影子评测指标 | fixture 预测文件 | 当前未接入真实模型推理 |
| 延迟/吞吐 | fixture 固定值 | latency_ms=2, throughput=unavailable |

**真实模型推理状态**：当前 `real_model_inference = false`，所有影子指标来自 deterministic fixture。
CandidateModelClient 已实现 OpenAI 兼容客户端，但需配置 `CAMPUSMATE_LM_SHADOW_ENABLED=true` 和本地模型服务才能启用。

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

## 当前风险与未完成项

1. **真实模型推理未执行**：CandidateModelClient 已实现适配器和模拟服务测试，但未连接真实 CampusMate-LM 服务
2. **金丝雀展示未启用**：门禁逻辑已实现，但只读 canary 链路尚未接入生产 API 响应
3. **数据源控制部分生效**：数据源暂停状态已纳入投影 input_digest，但事件采集链路尚未完全消费
4. **前端决策展示已完成，闭环 E2E 未跑**：页面按后端落库的 `decision_status` 分档展示（只有 `APPLIED` 才显示"已调整学习计划"），并有投影层单测覆盖；但驱动真实后端 + 浏览器的闭环 E2E 在当前环境无法执行
5. **Playwright E2E 需要环境**：当前环境无法获取 chromium（npm registry 502、本机无 `ms-playwright` 缓存），浏览器验收**未执行**；脚本保留，但不得记为通过