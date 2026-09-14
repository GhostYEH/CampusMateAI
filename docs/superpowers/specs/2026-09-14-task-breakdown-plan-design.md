# AI 任务拆解闭环设计

## 状态

设计方向已于 2026-09-14 批准。本书面版本纳入评审提出的六项修订，等待最终复核后再生成逐文件实施计划。

## 1. 目标

把现有 AI 任务拆解从“可生成但上下文和结果各丢一半”的预览能力，升级为可追溯、可编辑、可持久化并能进入专注统计的学习执行闭环：

```text
个人待办或自由目标
  -> 安全生成上下文
  -> LLM / 规则降级
  -> 服务端规范化
  -> 用户预览和编辑
  -> 原子提交拆解计划与个人待办
  -> 选择具体步骤开始专注
  -> StudySession 归因到步骤待办
  -> 计划进度与实际专注时长聚合
```

最终结果必须同时满足：

- 个人待办的任务上下文能够真实进入生成和校园政策检索；
- 无论模型输出质量如何，对外步骤始终满足统一结构约束；
- `estimated_minutes`、依赖、完成标准和政策来源在确认保存后不丢失；
- 每个已物化步骤都能作为 `StudySessionCreate.related_task_id` 开始专注；
- 子待办完成、删除和恢复后，拆解计划具有确定、可逆的进度语义；
- 老客户端和自由文本拆解路径保持兼容。

## 2. 非目标

本设计不包含：

- 修改教师 `Assignment` 实体或允许 `task_id` 接受 Assignment ID；
- 把拆解步骤塞入 `personal_tasks.description` 或在 `personal_tasks` 上增加依赖 JSON；
- 复用或改造 `learning_plan_*` 每日规划生命周期；
- 自动把一次专注结束等同于步骤完成；
- 自动完成、删除或替换原始父任务；
- 第一期提供依赖拖拽、任意图编辑或跨计划依赖；
- 在本轮打通 Android、HarmonyOS 或微信小程序的任务级入口；
- 迁移旧版已经保存为普通待办、但结构化字段已经丢失的“AI 拆解步骤”。

## 3. 现状与边界

当前 `POST /api/v1/study/task-breakdown` 已支持 `task_id` 或 `goal`，服务层能读取个人待办的 title、description、deadline、materials、submission_method 和 source_text，并在政策意图下检索知识库。Web 两个调用点都只发送 goal，因此任务上下文路径在 Web 不可达。

模型提示要求输出 3～8 步，但服务端目前没有完整执行该约束；空标题、重复编号和超量步骤可以进入响应。Web 随后只保留 title、description 和 estimated_minutes，并通过并发创建多个个人待办保存，导致依赖、完成标准和政策来源丢失，也存在部分成功的问题。

`StudySessionCreate.related_task_id`、服务端归属校验、会话 `duration_seconds` 和 Web `relatedTaskId` 状态都已经存在。缺口是 Web 从未给 `relatedTaskId` 赋予真实任务 ID，也没有从拆解步骤进入专注的操作。

仓库现有 `learning_plan_items` 确实包含 `estimated_minutes` 和 `task_id`，`learning_plan_execution_actions` 也包含 `target_task_id`。不复用它的决定基于生命周期而非字段缺失：

- `learning_plan_runs.valid_until` 表达短期有效窗口；
- `supersedes_plan_id`、`stale_reason` 和 `replan_key` 表达每日重规划与替换；
- AI 任务拆解是用户对一个目标的一次性确认结果，不应因每日规划过期或被重规划而失效；
- 两者未来可以通过 `personal_tasks.id` 协作，但不共享聚合根和状态机。

## 4. 总体架构决策

### 4.1 独立拆解聚合

建立 `TaskBreakdownPlan` 和 `TaskBreakdownPlanStep` 两个持久化实体。计划负责来源、幂等和生成元数据；步骤负责执行顺序、结构化字段及物化后的个人待办关联。

第一版不建立 `task_breakdown_dependencies` 表。每个计划最多 8 步，依赖仅允许指向同一计划中更早的位置，也没有跨计划反查需求。数据库使用 `task_breakdown_steps.prerequisite_positions_json` 保存整数数组，API 仍使用 `prerequisite_positions: list[int]`。若未来确实需要高频查询“哪些步骤已解锁”或跨计划依赖，再通过独立设计迁移为关系表。

### 4.2 预览与提交分离

生成接口保持无业务写入，只返回规范化预览。用户编辑后调用新的提交接口，服务端再次校验并在一个事务中创建计划、步骤和个人待办。

预览不分配可长期引用的 plan ID；只有成功提交的聚合才进入数据库。这样不会为用户关闭弹窗或反复生成留下草稿垃圾。

### 4.3 展示目标与内部上下文分离

服务内部分为：

- `display_goal`：用户输入的目标；仅提供 task_id 时使用个人待办标题；返回客户端并用于人类可读展示；
- `generation_context`：任务说明、材料、提交方式、截止时间和截断后的通知原文；只用于检索与模型生成；
- `related_task_id` / `related_task_title`：明确表示个人待办关联。

响应的 `goal` 只返回 `display_goal`。不得再把拼接了通知原文的内部文本作为 goal 返回或保存到新待办的 `source_text`。

## 5. 第一期：生成契约与安全边界

第一期不修改数据库。

### 5.1 固定规范化顺序

LLM 原始数组必须按以下顺序处理，顺序本身属于契约：

1. 逐项解析并过滤非对象、缺字段、空白 title、非法 step_number 等无效项；
2. 按旧 `step_number` 升序稳定排序，相同编号保持模型数组中的原顺序；
3. 截取前 8 个有效步骤，超量时增加受控 warning；
4. 建立旧编号到新编号的映射；重复旧编号由第一次出现的步骤取得映射，后续同号步骤仍可保留但不能覆盖映射；
5. 依次重编号为 1～n，并把依赖映射到新编号；
6. 删除不存在、指向自身、指向后续步骤或重复的依赖；
7. 执行最终不变量检查；有效步骤少于 3 个时判定整次 LLM 结果无效并进入规则降级。

最终不变量为：

- 步骤数为 3～8；
- title 去除首尾空白后非空；
- estimated_minutes 为 5～120；
- dependency 是唯一正整数，且严格小于当前 step_number；
- completion_criteria 非空；
- 依赖图不存在环；
- 对外 mode 只能为 `llm` 或 `rule_fallback`。

### 5.2 响应 Schema

`TaskBreakdownResponse.mode` 改为 `Literal["llm", "rule_fallback"]`。`TaskBreakdownStep` 统一约束：

- title：1～256 字符；
- description：0～4000 字符；
- estimated_minutes：5～120；
- dependencies：最多 7 个正整数；
- completion_criteria：1～1000 字符；
- knowledge_source：最多 256 字符。

政策引用另带可空的 `knowledge_document_id`。title 用于展示，document ID 用于服务端验证和后续追溯；非政策步骤及待人工确认步骤的 ID 必须为空。

新增 `knowledge_status`：

- `not_applicable`：非政策步骤；
- `cited`：引用了本次检索结果中的真实来源；
- `needs_confirmation`：政策相关但证据不足，需要人工确认。

如果存在政策知识，模型返回的来源必须能映射到服务端提供的来源编号，服务端据此写入真实 document ID 和标题；不能仅凭自由文本接受任意标题。`is_policy_step` 不能用普通字符串的 truthiness 解析，必须按布尔类型校验；服务端还要结合 display_goal、步骤 title 和 description 重新判断政策意图，模型不能通过返回 false 绕过引用约束。如果没有足够知识，服务端强制使用 `needs_confirmation`，说明中提示咨询辅导员或负责部门，完成标准要求确认具体口径。

`knowledge_status` 是向后兼容的新增字段。Android 和 HarmonyOS 现有解析器应允许未知字段；实施前仍需用各端现有序列化测试验证这一点。

### 5.3 不可信输入隔离

goal、个人待办字段和通知原文都视为不可信数据：

- system message 声明数据块中的内容不得改变指令、输出格式和政策约束；
- goal、任务上下文和知识库使用彼此独立、带明确边界的结构化数据块；
- 通知原文继续限制长度，不能进入日志；
- 日志只记录 mode、步骤数、过滤数、fallback code、耗时、模型标识和不可逆 input digest；
- warning 只返回稳定中文文案或受控码，不泄露异常消息和内部类名。

### 5.4 第一期验收

- 20 步模型输出稳定得到按编号排序后的前 8 步；
- 截断后依赖只指向保留的更早步骤，不存在悬空依赖；
- 重复旧编号不会让后项覆盖前项的依赖映射；
- 空标题被过滤，剩余少于 3 步时使用完整规则降级；
- 政策步骤只能为真实引用或明确待确认；
- route docstring 正确声明 task_id 是 PersonalTask ID，而不是 Assignment ID。

## 6. 第二期：Web 上下文和完整预览

### 6.1 2a：任务级入口

计划页的每条未删除个人待办增加“AI 拆解”操作。点击后打开现有拆解台并发送：

```json
{"task_id": "personal-task-id"}
```

如果用户在任务上下文上补充目标，可同时发送 task_id 和 goal。自由文本入口继续只发送 goal。UI 显示当前关联任务标题并允许退出任务上下文回到自由目标。

2a 不依赖 `knowledge_status` 的展示，可以在第一期后单独上线。验收以真实网络请求包含 task_id、响应 related_task_id 匹配、服务端读取任务上下文及政策检索被触发为准。

### 6.2 2b：完整预览

Web 提取一个纯转换函数，把响应转为可编辑草稿并完整保留：

- step_number；
- title；
- description；
- estimated_minutes；
- dependencies；
- completion_criteria；
- is_policy_step；
- knowledge_source；
- knowledge_document_id；
- knowledge_status。

完成标准允许编辑。依赖第一版只显示“需先完成第 N 步”，不提供复杂图编辑。用户删除步骤后，客户端不自行猜测最终编号；提交时由服务端使用当前数组顺序重新编号并清理无效依赖。

### 6.3 跨端范围声明

第二期只覆盖 Web 主入口。Android `ApiService` 的两个 overload 和 HarmonyOS `StudyRepository` 继续保持现有 goal-only 调用，因此这两端本期仍不能获得 PersonalTask 上下文增强。服务端收紧后的响应值域与当前实际输出一致，不主动破坏移动端，但必须运行现有 DTO/序列化测试。

移动端任务级入口、完整预览和提交能力是独立后续工作，不得在第二期验收中表述为“跨端已打通”。微信小程序当前没有该调用路径，本期不新增。

## 7. 第三期：持久化、原子提交与专注闭环

### 7.1 数据模型

`task_breakdown_plans`：

- `breakdown_id`：主键；
- `user_id`：所有者；
- `related_task_id`：可空的原始 PersonalTask ID；
- `display_goal`：纯展示目标；
- `idempotency_key`：客户端提交幂等键；
- `request_digest`：规范化提交内容摘要，用于发现同键异参；
- `created_at`。

预览不落库，因此数据库不保存由客户端回传的 generation mode 或 warnings。它们继续服务于当前预览，但不得被当作持久化审计事实。

约束：`UNIQUE(user_id, idempotency_key)`。相关任务必须属于同一用户；不存在、跨用户或已软删除时提交失败。

`task_breakdown_steps`：

- `step_id`：主键；
- `breakdown_id`：所属计划；
- `position`：1～8；
- `title`、`description`；
- `estimated_minutes`；
- `completion_criteria`；
- `prerequisite_positions_json`：更早位置组成的整数数组；
- `is_policy_step`；
- `knowledge_source`；
- `knowledge_document_id`；
- `knowledge_status`；
- `materialized_task_id`：原子提交时创建的 PersonalTask ID；
- `created_at`。

约束：`UNIQUE(breakdown_id, position)`。Repository 读写时必须验证 JSON 是去重、升序、仅包含 `1 <= prerequisite < position` 的整数数组。

新增表使用 `CREATE TABLE IF NOT EXISTS` 和索引的幂等建表方式接入 `sqlite_db.py`，不重建或重命名既有表。迁移中禁止使用 `ALTER TABLE ... RENAME`，避免 SQLite 静默改写子表外键。由于本设计只新增表，不需要改动 `personal_tasks` 结构。

### 7.2 提交接口

新增：

```http
POST /api/v1/study/task-breakdowns/commit
GET  /api/v1/study/task-breakdowns
GET  /api/v1/study/task-breakdowns/{breakdown_id}
```

提交请求包含：

- idempotency_key；
- related_task_id，可空；
- goal；
- 用户编辑后的完整 steps。

服务端忽略客户端声称的用户 ID。提交前按数组顺序重新编号，重新校验 3～8 步、时长、依赖和政策字段，并生成 request_digest。服务端重新识别每一步的政策意图，不能信任客户端把 is_policy_step 改为 false。`cited` 步骤必须用 knowledge_document_id 重新查询当前知识库并核对标题；引用不存在、不可见或标题不匹配时，服务端将其降级为 `needs_confirmation`、清空文档 ID，并返回受控 warning。

幂等语义对齐 `AgentRuntimeRepository.find_job_by_idempotency` 的现有模式：按 `user_id + idempotency_key` 查询。首次请求执行事务；相同键且 request_digest 相同则返回既有计划；相同键但摘要不同返回 409，不能静默复用或覆盖。

单个数据库事务必须完成：

1. 创建 task_breakdown_plans；
2. 按 position 创建 task_breakdown_steps；
3. 为每个步骤创建 PersonalTask；
4. 回填每步的 materialized_task_id；
5. 提交事务并返回完整计划。

任意一步失败全部回滚。Web 用一次 commit 请求替换当前多个 `Promise.all(createTask)` 调用。

物化 PersonalTask 的字段规则：

- title、description 来自编辑后的步骤；
- source_name 固定为“AI 拆解步骤”；
- source_text 保存纯 display_goal，不保存 generation_context；
- 有 related_task_id 时可继承原任务的 deadline、priority 和 course_id；
- 不继承 source_notice_id、external_id 或其他带唯一约束的外部来源字段。

### 7.3 步骤删除、恢复与孤儿语义

`materialized_task_id` 在软删除时不置空。查询计划时根据关联 PersonalTask 的真实状态计算步骤执行状态：

- PersonalTask 为 pending：`PENDING`；
- PersonalTask 为 completed：`COMPLETED`；
- PersonalTask 为 deleted：`ABANDONED`；
- materialized_task_id 为空或物理行异常缺失：按 `ABANDONED` 返回，并增加 `materialized_task_missing` warning。

恢复软删除 PersonalTask 后，步骤自动回到 `PENDING`，不创建第二个待办。这样保留可逆性和审计关系。

`ABANDONED` 不满足后续步骤的前置条件，也不计入“全部完成”。计划状态由查询结果派生，不额外维护容易漂移的冗余列：

- 所有步骤均为 COMPLETED：`COMPLETED`；
- 仍有 PENDING：`ACTIVE`；
- 没有 PENDING，但至少一个 ABANDONED：`INCOMPLETE`。

对于 PENDING 步骤，如果任一前置步骤不是 COMPLETED，额外返回 `is_unlocked=false`。第一版只用于 UI 提示，不禁止用户直接完成待办；是否强制执行依赖需要独立产品决策。

### 7.4 接入专注计时

计划页和拆解计划详情中的每个非删除步骤提供“开始专注”。点击后导航到现有 StudyPage，并传递：

- `relatedTaskId = materialized_task_id`；
- `goal = step.title`；
- 可选建议时长 `estimated_minutes`，只作为计时器预填值，由用户确认后开始。

StudyPage 读取该上下文并首次给现有 `relatedTaskId` 状态赋真实值。开始按钮继续调用现有 `startStudySession`，由 `studySessionPayload` 转换为 `related_task_id`。服务端沿用现有“属于当前用户且未软删除”的校验，因此 ABANDONED 步骤必须先恢复才能开始专注。

计划查询按 `study_sessions.related_task_id = materialized_task_id` 聚合 status=completed 的 `duration_seconds`，返回每步 `actual_focus_seconds` 和计划 `total_focus_seconds`。预计时长与实际时长均为事实展示，不据此自动完成 PersonalTask；任务完成仍由用户显式操作。

## 8. 第四期：成本控制与降级质量

第四期在前三期行为稳定并获得调用指标后实施。

### 8.1 缓存与限流

生成缓存键至少包含：

- user_id；
- display_goal；
- 相关 PersonalTask 内容摘要；
- prompt_version 和模型标识；
- 本次知识库结果摘要。

默认 TTL 为 5 分钟；相关任务内容、prompt 版本、模型或知识结果变化都会产生新键。缓存不能跨用户共享。

后端增加可配置的每用户生成限流和单用户并发保护。初始默认值为每 60 秒最多 5 次、同一用户最多 1 个进行中的生成请求；触发时返回 429 和 Retry-After。阈值必须配置化，并根据真实 p95 延迟、失败率和调用成本调整。

### 8.2 规则降级分类

规则降级至少区分：

- 复习与刷题；
- 阅读、写作与报告；
- 编程与项目；
- 比赛与活动准备；
- 校园事务与政策事项；
- 无法分类的通用目标。

删除“看”“写”等单字学习关键词。政策识别使用强政策词，或“办理动作 + 校园实体”的组合；“整理宿舍”不能因“宿舍”单词命中政策，“申请宿舍”应命中。

## 9. 服务与文件边界

实施时保持以下职责分离：

- `task_breakdown_service.py`：生成上下文、LLM/规则生成、规范化和政策约束；
- 新 `task_breakdown_plan_service.py`：提交校验、幂等协调、物化任务和查询聚合；
- 新 `task_breakdown_plan_repository.py`：两张新表的事务读写，不包含生成逻辑；
- `personal_task_repository.py`：复用现有 `create_task(..., conn=conn)` 事务入口物化步骤待办，禁止在新 Repository 复制 PersonalTask INSERT；
- `schemas/study.py`：生成、提交和计划查询的 API DTO；
- `routes/study.py`：认证入口与错误映射，不承载事务细节；
- Web 纯 helper：响应转草稿、提交 payload 和路由上下文转换；
- StudyPage：只负责接收步骤任务上下文并启动现有学习会话；
- StudySubpages：任务级拆解入口、预览编辑、计划分组和步骤专注入口。

不为本功能重构无关的 PersonalTask、LearningPlan 或 StudySession 代码。

## 10. 错误与降级语义

- task_id 不存在、跨用户或已软删除，且没有 goal：保持 4xx，不调用模型；
- task_id 解析失败但有 goal：使用 goal 拆解并返回受控 warning；
- LLM 超时、SSL、截断、解析失败或违反最终不变量：完整规则降级；
- 政策知识不足：返回 needs_confirmation，不把普通 LLM 常识当校园事实；
- commit 时政策来源失效或不匹配：降级为 needs_confirmation，不持久化客户端声称的引用；
- commit 同键同参：返回既有结果；同键异参：409；
- commit 任一任务创建失败：整个事务回滚；
- 步骤待办软删除：步骤 ABANDONED，计划不能显示为全部完成；
- 步骤待办恢复：恢复原关联并回到 PENDING；
- 专注页面收到已删除任务：服务端拒绝创建会话，Web 提示先恢复步骤；
- 计划查询无法找到异常物化行：返回受控 warning，不抛出导致整个计划不可读的 500。

## 11. 测试策略

### 11.1 后端生成单元测试

覆盖：

- 20 步按编号排序后截断为 8；
- 截断前后依赖映射不悬空；
- 空 title、缺字段和非法编号过滤；
- 有效步骤少于 3 时规则降级；
- 重复旧编号采用第一次映射；
- 自依赖、未来依赖、不存在依赖和重复依赖被移除；
- Schema 时长、字符串长度和 mode 枚举；
- 政策有真实来源与无来源待确认；
- commit 对有效、失效及伪造 knowledge_document_id 的重新核验；
- source_text 中的提示注入文本不能改变输出约束；
- task_id 只接受当前用户 PersonalTask，并实际使用任务上下文。

### 11.2 Repository 与提交集成测试

覆盖：

- 新库建表与旧库幂等初始化；
- 没有使用表重命名，既有外键定义不被改写；
- 两张表完整往返 prerequisite_positions JSON；
- 用户隔离；
- 同键同参幂等返回；
- 同键异参 409；
- 第 N 个 PersonalTask 创建失败时计划、步骤和此前任务全部回滚；
- 软删除映射 ABANDONED、恢复映射 PENDING；
- 全部完成、活跃和不完整三种计划状态；
- 前置步骤未完成时 is_unlocked=false；
- StudySession 实际时长只聚合当前用户、当前物化任务且 status=completed 的会话。

### 11.3 Web 测试

把数据转换和 payload 构造抽为可由现有 Node test runner 执行的纯函数，覆盖：

- 任务入口发送 task_id，自由入口发送 goal；
- 响应到草稿不丢任何结构化字段；
- 删除步骤后的提交 payload 保持当前数组顺序；
- 保存只调用一次 commit；
- 从步骤开始专注时传递 materialized_task_id；
- StudyPage 生成的 StudySession payload 包含 related_task_id；
- ABANDONED、锁定和完成状态正确展示。

现有 study E2E 增加一条真实闭环：创建个人待办 -> 从任务行拆解 -> 编辑完成标准 -> 原子保存 -> 选择第二步开始专注 -> 结束会话 -> 查询计划看到 actual_focus_seconds -> 完成或删除步骤 -> 验证计划状态。

### 11.4 跨端兼容测试

- Android 两个 breakdown overload 能解析收紧值域和新增可选字段；
- HarmonyOS TaskBreakdownResponse 能忽略或接收新增字段；
- 旧客户端只发 goal 时生成接口行为不变；
- 第三期新增接口不要求移动端同步调用。

## 12. 分期交付与发布顺序

1. 第一期：生成规范化、Schema、内部上下文隔离、安全提示和后端测试；
2. 2a：Web 任务级入口与 task_id 上下文；
3. 2b：Web 完整字段预览和编辑；
4. 第三期后端：新表、Repository、原子 commit、查询与状态聚合；
5. 第三期 Web：单次提交、计划分组、孤儿状态和步骤专注入口；
6. 第四期：缓存、限流、规则模板和关键词质量；
7. 独立后续：Android/HarmonyOS 任务级入口、完整预览和提交。

每一期必须是可独立测试和回滚的提交。数据库变更仅为新增表；回滚应用版本时旧代码会忽略新表，不删除用户已经生成的计划数据。

## 13. 完成标准

以下条件全部满足才能宣称“AI 任务拆解闭环完成”：

- Web 任务行拆解真实发送 PersonalTask ID 并使用任务上下文；
- 任意成功生成响应均满足 3～8 步、非空标题、5～120 分钟和合法有向无环依赖；
- display_goal 与内部 generation_context 不混用、不泄露；
- 政策步骤只引用真实知识来源或明确要求人工确认；
- Web 预览、提交和重新加载均保留时长、依赖、完成标准与政策字段；
- commit 是幂等、单事务、全成或全败；
- 软删除步骤显示 ABANDONED，恢复后回到 PENDING，计划不会错误显示全部完成；
- 已物化步骤可以把真实 PersonalTask ID 接入 StudySession；
- 完成的专注会话时长能聚合回具体步骤和拆解计划；
- 专注结束不会自动完成步骤；
- Android 和 HarmonyOS 现有 goal-only 调用继续工作，且文档不宣称移动端上下文已打通；
- 相关后端、Web、跨端契约测试及 Web 构建通过；
- 本次提交不混入当前工作树中其他会话的源码、数据文件或本机产物。
