# CPM 校园世界模型全链路编排设计

## 1. 目标

CampusMateAI 的 CPM 校园陪伴助手应当以学生世界模型为长期状态基础，把校园知识、学生当前状态、未来风险、方案模拟和行动计划连接成一个可解释、可追溯、可由学生控制的闭环。

本阶段交付的是确定性世界模型与成熟大模型之间的安全编排。CampusMate-LM 候选模型继续运行在 Shadow 链路，不参与生产回答、预测结果、计划排序或业务写入。

完整链路为：

```text
校园事实与用户行为
  -> Learner Event
  -> CORE / ACADEMIC / WORLD Snapshot
  -> Forecast
  -> Read-only Simulation
  -> Action Plan
  -> User Decision / Execute / Undo
  -> Feedback Event
  -> State Reprojection
```

CPM 是该链路面向学生的统一交互入口，但不是世界模型本身，也不是未经约束的自主 Agent。

## 2. 非目标

本阶段不实现：

- Dreamer、RSSM 或其他神经网络环境模型；
- 真实 CampusMate-LM 权重训练、部署或生产晋级；
- 心理疾病、人格、智力、动机、退学或就业成功率推断；
- 允许大模型自由选择任意工具或自行构造写操作；
- 从聊天、表情或自报内容被动生成心理状态；
- 恢复 C 语言、编程练习、知识点掌握度或其他单学科能力；
- 重构无关页面、导航栏视觉或移动端界面。

## 3. 现状与问题

当前 CPM 已经把状态快照作为 `world_model_context` 传给 RAG 和主 LLM，并能在响应元数据中说明是否使用了状态。但现有实现存在以下缺口：

1. 状态读取依赖 Repository 默认参数，实际只读取 `CORE/__user__`，没有覆盖 `ACADEMIC` 和 `WORLD`。
2. CPM 读取 `is_current` 快照，但没有检查 `valid_until`，也没有在快照缺失或过期时按需投影。
3. `snapshot.value` 被整体序列化进提示词，缺少按状态类型定义的字段白名单。
4. CPM 只能把状态交给 LLM 组织语言，不能通过受控意图正式调用 Forecast、Simulation、Planner 和 Evidence。
5. 后端模型注册表与 ML 评测数据集的能力名称不一致。
6. CampusMate-LM 的 Shadow Runner 已装配，但正式业务中没有调用点。
7. 旧能力仍包含 `learning_summary_v1`、`read_knowledge_state` 等学习平台语义。
8. 当前定向验证仍有旧测试契约和模拟 fixture 失败，不能作为全链路完成证据。

## 4. 总体架构

新增两个边界清晰的服务：

### 4.1 `CpmWorldContextService`

职责是把数据库中的内部世界模型表示转换为适合 CPM 使用的安全、有限、带新鲜度信息的上下文。它不生成自然语言回答，不调用 LLM，不执行写操作。

输入：

- 当前认证用户 ID；
- 请求时间 `as_of`；
- 所需投影族集合；
- 状态条数和字符预算。

输出：

- CORE、ACADEMIC、WORLD 三族安全状态；
- 每族使用的 run ID、estimator version、as-of 和 valid-until 摘要；
- 被忽略、过期、不可用或截断的 warning code；
- 可安全传给主 LLM 的结构化上下文；
- 可安全传给客户端的聚合使用元数据。

### 4.2 `CpmOrchestrator`

职责是根据受控意图选择现有服务，并把结果交给 RAG/主 LLM 表达。它不复制各领域的计算公式。

允许的意图为：

- `CAMPUS_POLICY_QUERY`：校园规定、办理流程、地点、材料、截止日期；
- `CURRENT_STATE_QUERY`：当前负载、日程、目标或执行状态；
- `FORECAST_QUERY`：未来风险与趋势；
- `SCENARIO_COMPARE`：受控方案比较；
- `PLAN_REQUEST`：生成或解释行动计划；
- `GOAL_PROGRESS`：读取目标和进展；
- `GENERAL_CHAT`：普通寒暄或无需工具的通用对话。

每种意图映射到固定工具组合。未知、低置信度或参数不足时回退到 `GENERAL_CHAT` 或要求用户补充信息，不猜测工具参数。

## 5. 数据流

### 5.1 请求入口

继续保留：

- `POST /api/v1/counselor/chat`
- `POST /api/v1/assistant/counselor/chat`

兼容现有客户端请求结构。服务端从认证上下文取得用户 ID，禁止客户端在消息或工具参数中指定其他用户。

### 5.2 状态准备

CPM 请求需要个性化状态时，按以下顺序处理：

1. 分别请求 `CORE/__user__`、`ACADEMIC/__user__`、`WORLD/__user__` 当前 run。
2. 如果 run 不存在或已超过 `valid_until`，调用相应投影服务按需重算。
3. 投影失败时只降级该族，不阻断其他状态或普通问答。
4. 数据源暂停、输入截断、质量不足和状态不可用信息进入 warning codes。
5. 每族最多输出固定数量的状态，总上下文受统一字符预算限制。

禁止通过一次无界查询读取用户全部历史快照。

### 5.3 校园知识与个人状态分离

RAG 只负责回答学校规定和校园事实。检索来源必须来自当前受管理知识库，并继续返回人类可读来源。

世界模型只用于：

- 调整建议的优先级和时间安排；
- 解释为什么某个行动更适合当前状态；
- 选择是否调用 Forecast、Simulation 或 Planner；
- 提醒状态数据过期或证据不足。

世界模型不得作为学校政策、办理地点、材料、金额和截止时间的事实来源。

### 5.4 工具编排

CPM 只允许调用以下只读能力：

- `read_core_state`
- `read_academic_state`
- `read_world_state`
- `read_state_evidence`
- `read_forecasts`
- `simulate_scenario`
- `read_personal_tasks`
- `read_student_goals`
- `read_learning_plans`
- `search_campus_materials`

需要写入的行为不作为模型工具执行。CPM 只能返回受控 `SuggestedAction`：

- `OPEN_STATE`
- `OPEN_FORECAST`
- `OPEN_SIMULATION`
- `OPEN_PLAN`
- `PROPOSE_PLAN_GENERATION`
- `PROPOSE_PLAN_DECISION`
- `PROPOSE_PLAN_EXECUTION`
- `PROPOSE_PLAN_UNDO`
- `OPEN_GOAL`

客户端展示确认界面后，再调用现有正式写接口。服务端继续校验用户、资源状态、幂等键和计划有效性。

## 6. CPM 安全上下文契约

禁止直接把完整 `snapshot.value` 传给 LLM。每个状态通过固定适配器转换为 `CpmStateContextItem`：

```text
projection_kind
state_type
scope_type
state_band
confidence_bucket
data_quality
explanation_codes
warning_codes
as_of
valid_until
```

`state_band` 是受控枚举或受控数值区间，不包含自由文本。

上下文中禁止出现：

- user ID、source ID、snapshot ID、run ID、内部表名；
- 原始事件 payload；
- 通知、目标、任务、附件或聊天全文；
- Cookie、Token、密码、密钥、URL 查询凭据；
- 心理、人格或医疗标签；
- 模型 system prompt 或内部工具参数。

任务和目标标题如确有必要，只能由业务 Repository 验证归属后进入单独的“用户个人上下文”区，并受数量和长度限制，不能复制到模型日志或 shadow 数据。

## 7. Forecast 与 Simulation

Forecast 必须由现有 `ForecastService` 产生，主 LLM 只能解释结果，不能自行计算概率。允许的预测仍为：

- 截止完成风险；
- 未来工作负载；
- 日程冲突风险；
- 目标进展展望；
- 专注节律连续性。

Simulation 必须由现有 `SimulationService` 产生，允许的 intervention 继续使用 Pydantic 判别联合和服务端白名单。结果必须包含：

- baseline；
- simulated；
- delta；
- assumptions；
- limitations；
- confidence；
- data quality；
- `causal_claim=false`。

模拟调用不创建任务、不接受计划、不修改目标、不暂停真实数据源、不写入世界模型状态。

## 8. Planner 与行动闭环

CPM 请求行动建议时，调用现有 Planner，并要求 Planner 使用：

- WORLD 当前状态；
- ACADEMIC 当前状态；
- 未来七天 Forecast；
- 活跃目标；
- 任务、考试、课程和校园通知；
- 用户偏好和可用时间。

CPM 可以解释计划，但不得绕过计划状态机。正式写入顺序保持：

```text
PROPOSED -> 用户 ACCEPT -> EXECUTE -> 用户反馈或 UNDO -> 状态重投影
```

计划执行继续保持单事务、稳定 external ID、幂等和撤销冲突检测。

## 9. 显式反馈闭环

只有系统中需要用户明确操作才能进入世界模型的反馈：

- 计划有帮助或无帮助；
- 建议过早、过晚、过多或不相关；
- 用户确认的目标进度；
- 用户主动提交的状态纠正；
- 用户接受、拒绝、执行或撤销计划。

普通聊天内容、表情信号和未确认的 LLM 推测不写入世界模型。

反馈写入受控 Learner Event 后，触发相关投影族失效或重算。历史状态保留，不能就地覆盖审计历史。

## 10. CampusMate-LM Shadow 接入

CampusMate-LM 在本阶段只做旁路观察：

```text
生产输入的脱敏结构摘要
  -> ModelShadowRunner
  -> 严格 Schema 与策略验证
  -> Shadow 结果与指标
```

Shadow 输出不得：

- 改变 CPM 正式答案；
- 改变 Forecast、Simulation 或 Planner；
- 执行任何工具；
- 写入任务、目标、计划或状态；
- 被标记为生产推理。

后端能力名称与 ML 数据集统一为：

- `student_state_summary_v1`
- `campus_intent_routing_v1`
- `notice_action_classification_v1`
- `goal_support_classification_v1`
- `read_only_tool_routing_v1`

移除生产契约中的 `learning_summary_v1` 和 `read_knowledge_state`。旧 shadow 历史记录可以继续读取，但不得作为已验证的新能力来源。

只有真实权重、真实 held-out 指标、真实性能记录、来源验证、用户数据源授权、feature flag、Canary 门禁和关闭状态熔断器同时满足时，未来版本才可以讨论晋级。本阶段 `campusmate_lm_affects_production` 始终为 false。

## 11. 回答结构与透明度

CPM 回答继续区分：

1. 校园事实：带知识库来源；
2. 当前状态：说明这是系统根据近期记录形成的状态估计；
3. 趋势或模拟：展示不确定性和局限；
4. 行动建议：使用建议语气；
5. 可执行动作：必须由用户确认。

响应元数据扩展但保持兼容：

- `context_used.learner_state_used`
- `context_used.learner_state_snapshot_count`
- `context_used.projection_kinds`
- `context_used.forecast_used`
- `context_used.simulation_used`
- `context_used.plan_used`
- `context_warnings`

不向客户端暴露内部 prompt、输入摘要原文、source ID 或数据库结构。

## 12. 失败与降级策略

- 知识库无证据：校园规定问题返回无法确认，并建议咨询负责部门。
- 世界模型不可用：继续提供非个性化 RAG 或普通对话，并返回安全 warning。
- 单一投影族失败：使用其他有效投影族，不把失败族伪装为可用。
- Forecast 不可用：不输出概率，使用 `UNAVAILABLE`。
- Simulation 参数不足：返回受控补充信息要求，不由 LLM 猜参数。
- Planner 无输入：返回明确空计划原因。
- 主 LLM 不可用：沿用现有检索摘要或模板降级。
- Shadow 模型失败：记录安全失败码并使用确定性 fallback，不影响用户响应。
- 写操作冲突：保持现有 409 语义，由客户端提示刷新后重试。

所有异常日志仅记录受控操作名、用户或资源的不可逆摘要、能力名和异常类型，不记录聊天全文、世界模型上下文、检索全文或凭据。

## 13. 测试策略

### 13.1 后端契约

验证：

- CPM 显式读取 CORE、ACADEMIC、WORLD；
- 不依赖 Repository 默认 projection kind；
- 过期快照会重投影或降级；
- 数据源暂停会让对应上下文降级；
- 安全 DTO 不包含内部 ID、自由文本或敏感字段；
- 匿名请求不读取任何学生状态；
- 跨用户资源统一拒绝；
- RAG 校园事实与世界模型建议不会混淆；
- Forecast 和 Simulation 使用正式服务结果；
- Simulation 调用前后业务表不变；
- 计划写操作必须经过用户确认；
- 用户反馈触发事件与状态失效；
- Shadow 输出不影响正式返回。

### 13.2 能力与 ML 契约

验证后端注册表与 ML 数据集的五种能力名称、输入版本、输出版本和字段集合完全一致；旧能力只能作为历史迁移输入，不能进入新 run。

验证 fixture、fallback 和 synthetic 数据不会被标记为 `REAL_MODEL`，无真实权重时真实 benchmark 保持 BLOCKED。

### 13.3 Web 与 E2E

真实 Playwright 流程覆盖：

1. 学生登录并向 CPM 询问当前安排；
2. CPM 响应声明使用 CORE、ACADEMIC、WORLD；
3. 打开状态证据；
4. 请求未来七天趋势；
5. 比较两个受控方案；
6. 生成行动计划；
7. 用户接受并执行；
8. 验证任务产生；
9. 提交反馈；
10. 验证状态重新投影；
11. 撤销计划动作；
12. 确认跨用户和未确认写操作被拒绝。

桌面和移动视口使用不同测试用户。关键步骤不允许条件跳过或吞掉断言。

## 14. 验收标准

以下条件全部满足才可宣布“CPM 世界模型全链路完成”：

- CPM 真实使用 CORE、ACADEMIC、WORLD 三族状态；
- 状态上下文经过新鲜度判断、字段白名单和总量限制；
- CPM 可以通过正式服务读取 Forecast、运行只读 Simulation、生成 Planner 建议；
- 所有写操作都需要学生确认并保持幂等、事务和撤销语义；
- 显式反馈能够形成事件并触发状态更新；
- 后端与 ML 五种能力契约完全一致；
- CampusMate-LM 保持 Shadow，不影响生产；
- CPM/RAG、世界模型和校园政策事实边界有测试保障；
- 后端、Web、ML 全量测试通过；
- Web 生产构建通过；
- 真实 Playwright 桌面与移动流程通过；
- 有效业务代码、数据集和页面中不存在 C 语言专属能力；
- 工作区没有混入其他会话或本机临时文件。

对外准确表述为：

> CampusMateAI 已完成确定性、可解释、可追溯的校园陪伴世界模型，并通过 CPM 将状态、预测、方案比较和用户确认的行动闭环连接起来；CampusMate-LM 仍处于不影响生产的影子评测阶段。

