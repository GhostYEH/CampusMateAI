# CampusMateAI Android -> HarmonyOS NEXT 功能对齐审计

审计时间：2026-08-13。基准为当前工作区 `android/`、`harmony/`、`backend/` 源码与本机 API 24 SDK；README 不作为完成证据。

状态只使用：`ALIGNED`、`PARTIAL`、`MISSING`、`PLATFORM_LIMITED`、`BROKEN`。

| Feature | Android implementation | Harmony implementation | Backend API | Status | Gap | Platform limitation | Action |
|---|---|---|---|---|---|---|---|
| 登录 | LoginScreen + ApiClient | LoginScreen + ApiClient | `auth/login` | ALIGNED | 无已知功能缺口 | 无 | 保持回归测试 |
| Token 生命周期 | access/refresh、401 刷新重放 | AssetStoreKit TokenStore、单航班刷新、一次重放、会话过期清理 | `auth/refresh` | ALIGNED | 尚未做真机网络联调 | 无 | 真机验证并发 401 |
| API 空响应与错误 | ApiClient 分层错误 | `requestVoid`、可选响应、403/404/409/422/429/5xx/超时/网络错误 | 共享 API | ALIGNED | 页面仍需逐步迁移到 Repository | 无 | 继续拆分 Repository |
| 首页 | DashboardScreen | DashboardPage | dashboard/聚合接口 | ALIGNED | 无已知核心缺口 | 无 | 视觉回归 |
| 课程 | CoursesScreen | CoursesPage，含课程内容入口 | courses/course-content | PARTIAL | 学习通账户态未接入 | 无 | 与 ChaoxingRepository 联动 |
| 待办列表/详情/完成/恢复 | TasksScreen/TaskDetailScreen | TasksPage | `tasks`, complete/restore | ALIGNED | 无已知核心缺口 | 无 | Repository 化 |
| 待办编辑 | TaskDetail/Edit 能力 | 未提供编辑表单 | `PATCH tasks/{id}` | MISSING | title/description/deadline/source 未编辑 | 无 | 新增编辑表单与测试 |
| 待办删除 | 删除确认 | 未提供 | `DELETE tasks/{id}` | MISSING | 缺确认弹窗与请求 | 无 | 新增删除流程 |
| 待办日历 | TaskCalendarScreen | 无 | `GET tasks` | MISSING | 缺按日期分组页面 | 无 | 新增 TaskCalendarPage |
| AI 校园助手 | CounselorScreen，流式对话 | CounselorPage，流式对话 | counselor/chat | PARTIAL | `expression_signal` 未接入 | 本地模型不可用时必须省略信号 | 接入 FocusAssistProvider 后透传 |
| 考试 | 列表、新增、编辑、删除 | ExamsPage 与 Index 请求链路 | exams/student-tools | ALIGNED | 尚未做设备交互回归 | 无 | 真机回归 |
| 空教室 | ClassroomsScreen | ClassroomsPage | classrooms | ALIGNED | 无已知核心缺口 | 无 | 保持回归 |
| 办事大厅基础类型 | 请假/报修/证明/反馈 | ServicesPage | service requests | PARTIAL | 场地、我的申请详情/完整历史未全部对齐 | 无 | 补 venue/mine |
| 失物招领基础能力 | 列表/搜索/发布/详情 | LostFoundPage | lost-found/community | PARTIAL | 分类、地点、排序、我的发布不完整 | 无 | 补筛选与 owner 视图 |
| 专注会话 | FocusScreen 完整状态机 | FocusPage + start/pause/resume/finish | study/sessions | PARTIAL | mode、goal、relatedTaskId、计时恢复仍不完整 | 无 | 引入 StudyRepository 并恢复 active session |
| 每日专注目标/统计 | 目标、今日分钟、次数、连续天数 | 未完整展示/编辑 | `study/goals/daily`, sessions | MISSING | 缺 UI 与派生统计 | 无 | 新增目标卡与统计 |
| 学习状态辅助 | CameraX + 本地 TFLite/LiteRT | CameraKit + ImageReceiver + CoreVision 人体框 + MindSpore Lite V3.4 | 无需后端推理 | PARTIAL | 构建链路已闭合，尚未完成 API24 真机时延、方向和人体框对齐验证 | CoreVision 多目标识别不支持模拟器；相机与端侧模型需真机 | 真机验证后再标记 ALIGNED，失败时继续 fail-closed |
| CNN/表情模型共建 | ExpressionContributionScreen | 无 | contributions/expression-samples | MISSING | 缺主动拍摄、同意、上传、删除 | Camera Kit 需真机验证 | 验证能力后实现 |
| 校园通知 | NotificationsScreen | NotificationsPage，后端站内通知 | notices | ALIGNED | 无已知核心缺口 | 无 | 保持回归 |
| 本机第三方通知自动采集 | NotificationListenerService | 能力探测与订阅代码保留，但普通手机构建禁用 | notices/ingest(-batch) | PLATFORM_LIMITED | 普通应用无法取得所需系统级权限 | `SUBSCRIBE_NOTIFICATION` 为 system_basic；该扩展面向特定订阅场景，不等价于 Android 监听器 | UI 明示不可用，使用后端/学习通/手动粘贴 fallback |
| 微信来源与隐私过滤 | source resolver + 独立白名单 | resolver + 独立开关/白名单 + 高置信精确匹配 | notices ingest | PARTIAL | Harmony bundleName 仍需真实设备确认 | 自动采集本身不可用 | 仅登记设备验证 alias |
| 企业微信来源与隐私过滤 | WECOM + 独立白名单 | 已新增 WECOM 与独立白名单；无猜测默认 alias | notices ingest | PARTIAL | 缺真实 bundleName | 同上 | 真机观察后登记 |
| QQ/TIM 来源与隐私过滤 | QQ + 独立白名单 | 独立开关/白名单；alias 需验证 | notices ingest | PARTIAL | TIM/Harmony alias 未验证 | 同上 | 真机观察后登记 |
| 学习通通知来源 | XUEXITONG | source resolver 与开关 | notices ingest | PARTIAL | 自动捕获不可用；应依赖账号同步 | 同上 | 复用 Chaoxing 同步 |
| 群名规范化 | GroupNameNormalizer | 全半角、空白、括号/消息数后缀规范化，最终严格相等 | 无 | ALIGNED | 无已知核心缺口 | 无 | 保持隐私边界测试 |
| 通知去重 | 指纹 + Room 唯一约束 | 指纹包含通知 identity | 无 | PARTIAL | 尚无数据库唯一约束 | 无 | 与 RDB Outbox 一并实现 |
| 通知合批 | ConversationBundler | NotificationBatch 纯逻辑与集中常量 | `notices/ingest-batch` | PARTIAL | 未接入持久队列/定时 flush | 无 | 接入 Outbox worker |
| 通知可靠 Outbox/重试 | Room + WorkManager | 仍为 Preferences 记录，缺可靠状态机 | `notices/ingest-batch` | BROKEN | 失败丢失窗口、无指数退避/重启恢复 | Background Tasks Kit 使用条件需验证 | 使用 ArkData RDB；合适前台生命周期排空 |
| 通知设置页 | 独立设置页 | NotificationsPage 内设置与真实 capability 文案 | PARTIAL | 最近记录/失败数、白名单编辑体验不完整 | 自动采集不可用 | 完善只读状态与 fallback 入口 |
| 学习通账户 | 登录、状态、同步、断开、重认证 | 无独立页面 | chaoxing/login/status/sync/disconnect | MISSING | 完整流程缺失 | 后台周期同步不得照搬 WorkManager | 先实现手动同步与状态机 |
| 校园动态 | CampusNews 列表/详情/已读/收藏 | 无 | Android 当前数据源/本地偏好 | MISSING | 页面和首页入口缺失 | 无 | 新增本地偏好与页面 |
| 文件 | PersonalHub CRUD | PersonalHubPage 主要为读取 | personal-hub/files | PARTIAL | 新增/删除/收藏操作不完整 | 无 | PersonalHubRepository + 确认弹窗 |
| 活动 | PersonalHub 活动能力 | PersonalHubPage 展示 | personal-hub/activities | PARTIAL | 与 Android 操作能力未逐项对齐 | 无 | 补操作链路 |
| 收藏 | 收藏 CRUD | 主要为读取 | personal-hub/favorites | PARTIAL | 新增/删除不完整 | 无 | 补 CRUD |
| 设置 | 多项持久开关与入口 | dark/reduce motion/backend status + 部分入口 | 多个 | PARTIAL | 截止提醒、学习辅助、学习通、模型共建、帮助入口不完整 | 未实现调度时不可显示已开启 | 补真实状态与入口 |
| 账号 | AccountScreen 完整资料 | AccountPage | auth/me | PARTIAL | student_number 字段未完整建模/展示 | 无 | 补模型字段与 UI |
| 帮助与反馈 | HelpFeedbackScreen | 无独立页面 | service_form/feedback | MISSING | FAQ、隐私、功能说明、反馈缺失 | 无 | 新增 HelpFeedbackPage |
| 深色模式/减少动态 | 全局主题 | 已有全局状态与页面传递 | 无 | PARTIAL | 新增页面需持续验收；部分动画仍存在 | 无 | 逐页视觉检查 |
| 导航/架构 | NavHost + Repository | Index 仍承担大量 API/state/route | 共享 API | PARTIAL | 缺 Auth/Task/Notification/Study/PersonalHub/Chaoxing Repository | 无 | 增量拆分，避免大重写 |

## 本轮确认的真实缺陷

1. Harmony 过去只保存 access token，401 后无法按 Android 行为刷新；现已补 access/refresh 双 token、单航班 refresh 和一次重放。
2. 空 body/204 会进入 JSON 解析；现已提供 `requestVoid`/可选响应解析。
3. 通知 UI 曾可能暗示订阅已开启，但当前 SDK 权限不支持普通应用实现 Android 等价能力；现已 fail-closed 并明确显示 `UNAVAILABLE`。
4. 通知来源缺 WECOM、三个 IM 未完全独立白名单、群名匹配与 group identity 不可靠；已补基础模型和严格过滤。
5. 通知指纹原先未包含系统通知 identity，导致不同通知误去重；已由真实执行的单测发现并修复。
6. 当前通知持久化仍不是可靠 Outbox，必须保留 `BROKEN`，不得因为存在合批纯逻辑而写成完成。

## SDK 能力结论

- 本机 SDK：HarmonyOS/OpenHarmony 6.1.1，API 24。
- `SUBSCRIBE_NOTIFICATION` 在本机 SDK 定义为 `system_basic`、`system_grant`；普通未获系统授权的 CampusMateAI 手机应用不能据此读取本机第三方应用通知。
- `NotificationSubscriberExtensionAbility` 自 API 22 可用，但当前工程 compatible SDK 为 21，构建会给出兼容性警告；更关键的是其订阅类型/权限前提不等价于 Android `NotificationListenerService`。
- 因此当前真机能力结论为 `UNAVAILABLE`（普通应用构建），不是 `SUPPORTED`。未进行具备系统签名/白名单设备的验证。

