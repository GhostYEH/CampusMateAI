import '../models/models.dart';

/// 通知智能提取服务抽象。
///
/// UI 层通过依赖注入获取实现(Mock 或真实后端)。
/// 真实实现将通过 FastAPI 调用 LLM + 规则提取。
abstract interface class NotificationExtractionService {
  /// 提取通知结构化信息(单任务)。
  ///
  /// [onProgress] 回调用于动态展示分步骤处理过程。
  /// 返回 [ExtractedNotice],字段允许为空(未提取到)。
  Future<ExtractedNotice> extract(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  });

  /// 多任务抽取 — 自动识别通知中是否包含多个独立任务。
  ///
  /// 后端 `/api/v1/notices/extract-multi` 实现:
  /// - 当识别到 >=2 个独立截止/动作时返回多个任务
  /// - 无法可靠拆分时返回单任务,并标注 splitReason
  /// - needsUserConfirmation=true 时建议用户人工确认拆分结果
  ///
  /// Mock 实现:通过简单规则检测"并于/以及/然后/同时"等连接词,
  /// 检测到多个截止时间时拆分为多任务。
  Future<MultiExtractResult> extractMulti(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  });

  /// 重复通知检测(基于本地已保存任务列表)。
  ///
  /// 服务端无状态,客户端需传入本地最近已保存的通知列表。
  /// 返回 [DuplicateCheckResult],发现重复时只提示,不自动覆盖。
  Future<DuplicateCheckResult> checkDuplicate({
    required String content,
    String? sourceName,
    String? taskName,
    DateTime? deadline,
    required List<RecentNoticeItem> recentNotices,
  });
}

/// 多任务抽取结果。
class MultiExtractResult {
  const MultiExtractResult({
    required this.tasks,
    required this.splitReason,
    required this.needsUserConfirmation,
  });

  /// 抽取的任务列表(1 个或多个)。
  final List<ExtractedNotice> tasks;

  /// 拆分说明(如"识别到 2 个独立截止时间"或"合并为单任务")。
  final String splitReason;

  /// 是否建议用户人工确认拆分结果。
  final bool needsUserConfirmation;
}

/// 重复通知检测中的"已存在通知项"(客户端传入)。
class RecentNoticeItem {
  const RecentNoticeItem({
    required this.noticeId,
    this.title,
    this.task,
    this.sourceName,
    this.sourceText,
    this.deadline,
  });

  final String noticeId;
  final String? title;
  final String? task;
  final String? sourceName;
  final String? sourceText;
  final DateTime? deadline;
}

/// 重复通知检测结果。
class DuplicateCheckResult {
  const DuplicateCheckResult({
    required this.isDuplicate,
    required this.matches,
    required this.contentHash,
    required this.note,
  });

  /// 是否可能重复。
  final bool isDuplicate;

  /// 命中的已存在通知列表。
  final List<DuplicateMatch> matches;

  /// 当前通知的内容哈希。
  final String contentHash;

  /// 说明文案。
  final String note;
}

/// 重复检测命中项。
class DuplicateMatch {
  const DuplicateMatch({
    required this.noticeId,
    required this.title,
    this.sourceName,
    this.deadline,
    required this.similarity,
    required this.reasons,
  });

  final String noticeId;
  final String title;
  final String? sourceName;
  final DateTime? deadline;
  final double similarity;
  final List<String> reasons;
}

/// 提取步骤(用于动态展示处理过程)。
class ExtractionStep {
  const ExtractionStep({
    required this.label,
    required this.order,
    this.detail,
  });
  final String label;
  final int order;
  final String? detail;
}

/// 待办任务仓库抽象。
///
/// 持久化相关方法([snapshot]/[restoreFrom]/[clearAll]/[resetToDemo])用于
/// 本地缓存管理;真实后端实现可作为 no-op 或维护本地缓存。
abstract interface class TaskRepository {
  List<Task> get tasks;
  Stream<List<Task>> watchTasks();
  Future<Task> createTask(Task task);
  Future<void> updateTask(Task task);
  Future<void> softDelete(String taskId);
  Future<void> restore(String taskId);
  Future<void> hardDelete(String taskId);
  Future<List<Task>> getByCategory(TaskCategory category);
  Future<List<Task>> getUpcoming({int limit = 5});
  Future<List<Task>> getCompleted();
  Future<List<Task>> getToday();

  /// 当前内存中所有任务的可持久化快照(包含已删除项)。
  List<Task> get snapshot;

  /// 从持久化数据恢复(替换内存数据)。
  Future<void> restoreFrom(List<Task> saved);

  /// 清空所有任务(用于"清除本地数据")。
  Future<void> clearAll();

  /// 重置为演示数据(用于"恢复演示数据")。
  Future<void> resetToDemo();
}

/// AI 导员聊天服务抽象。
abstract interface class CounselorChatService {
  /// 流式发送消息,逐段返回内容。
  ///
  /// [onChunk] 接收增量文本,[onSources] 接收引用来源,
  /// [onActions] 接收建议操作,[onFinalMeta] 接收最终元数据(模式/证据等级/置信度/警告)。
  /// 返回完整消息内容。调用方可通过取消 [onChunk] 流终止。
  Future<String> send(
    String message, {
    required String conversationId,
    void Function(String chunk)? onChunk,
    void Function(List<KnowledgeSource> sources)? onSources,
    void Function(List<SuggestedAction> actions)? onActions,
    void Function(ChatFinalMeta meta)? onFinalMeta,
    void Function()? onTyping,
  });

  /// 主动生成提醒(根据待办情况)。
  Future<String?> generateProactiveReminder(List<Task> tasks);

  /// 停止当前生成。
  void stop();
}

/// SSE `done` 事件的最终元数据(对齐后端 ChatFinalMeta)。
///
/// 用于让 UI 准确区分回答模式与证据等级,避免将 retrieval_summary 描述为"大模型生成"。
class ChatFinalMeta {
  const ChatFinalMeta({
    required this.mode,
    required this.evidenceLevel,
    required this.confidence,
    required this.warnings,
    required this.needsHumanConfirmation,
    required this.hasUserDocs,
    required this.hasDemoDocs,
  });

  /// 后端返回的模式: llm | retrieval_summary | no_knowledge
  final String mode;

  /// 后端返回的证据等级: high | medium | conflict | none | low
  final String evidenceLevel;

  /// 整体置信度 0~1
  final double confidence;

  /// 后端返回的提示(冲突/过期/低置信度等)
  final List<String> warnings;

  /// 是否需要人工确认
  final bool needsHumanConfirmation;

  /// 是否包含用户导入文档(用于推导 [AnswerMode])
  final bool hasUserDocs;

  /// 是否包含仿真演示文档(用于推导 [AnswerMode])
  final bool hasDemoDocs;
}

/// 校园知识库服务抽象(预留向量数据库接口)。
abstract interface class KnowledgeBaseService {
  Future<List<KnowledgeSource>> search(String query, {int limit = 3});
  Future<List<KnowledgeSource>> get sources;
}

/// 知识库管理服务抽象 — 用于知识库管理页面。
///
/// 与 [KnowledgeBaseService] 的区别:
/// - [KnowledgeBaseService] 面向 AI 导员,只提供检索能力
/// - [KnowledgeManagementService] 面向知识库管理页面,提供完整的状态/列表/上传/删除/重建能力
///
/// 实现类:
/// - [ApiKnowledgeManagementService]: 调用 FastAPI 真实后端
/// - [MockKnowledgeManagementService]: 演示模式下的内存实现(无真实持久化)
abstract interface class KnowledgeManagementService {
  /// 获取知识库状态(类型/文档数/分块数/问答模式/索引状态)。
  Future<KnowledgeStatusInfo> getStatus();

  /// 列出所有已导入文档(包含元数据)。
  Future<List<KnowledgeDocumentSummary>> listDocuments();

  /// 上传文档。
  ///
  /// [bytes] 文件二进制内容
  /// [originalFilename] 原始文件名(用于推断类型)
  /// [metadata] 元数据(标题、来源部门、发布日期等)
  /// [onProgress] 上传进度回调(状态机驱动 UI)
  ///
  /// 返回上传后的文档摘要。失败时抛 [ApiException]。
  Future<KnowledgeDocumentSummary> uploadDocument({
    required List<int> bytes,
    required String originalFilename,
    required KnowledgeDocumentMetadata metadata,
    void Function(UploadProgress progress)? onProgress,
  });

  /// 删除指定文档。
  ///
  /// 返回是否删除成功。失败时抛 [ApiException]。
  Future<bool> deleteDocument(String documentId);

  /// 重建索引(不删除原始文档)。
  ///
  /// [onProgress] 进度回调。
  /// 返回新的分块数量。失败时抛 [ApiException]。
  Future<int> rebuildIndex({
    void Function(RebuildProgress progress)? onProgress,
  });

  /// 恢复仿真演示资料。
  ///
  /// 不会覆盖用户已导入资料(基于 content_hash 去重)。
  /// 返回新增的演示资料数量。
  Future<int> restoreDemoDocuments();

  /// 执行数据管理动作(删除用户文档/删除全部文档等)。
  Future<DataManagementResult> manageData(DataManagementAction action);
}

/// 上传文档时的元数据(对应后端 Form 字段)。
///
/// 定义已移至 `models/knowledge.dart`(`KnowledgeDocumentMetadata` 是数据模型,
/// 应与其它知识库模型放在一起)。此处通过 `import '../models/models.dart'` 引用。

/// 学习会话仓库抽象。
///
/// 持久化相关方法([historySnapshot]/[restoreHistoryFrom]/[clearHistory]/
/// [resetToDemo])用于本地缓存管理;真实后端实现可作为 no-op。
abstract interface class StudySessionRepository {
  StudySession? get current;
  Stream<StudySession> watchCurrent();
  Future<StudySession> start({String? goalId, String? taskId});
  Future<void> pause();
  Future<void> resume();
  Future<StudySession> end({String? selfReportMood});
  Future<List<StudySession>> history({int limit = 30});
  Future<Duration> todayTotal();

  /// 当前内存历史记录的可持久化快照。
  List<StudySession> get historySnapshot;

  /// 从持久化数据恢复历史记录(替换内存数据)。
  Future<void> restoreHistoryFrom(List<StudySession> saved);

  /// 清空历史记录(用于"清除本地数据")。
  Future<void> clearHistory();

  /// 重置为演示历史(用于"恢复演示数据")。
  Future<void> resetToDemo();
}

/// 表情识别服务抽象(强制接口,见 AGENTS.md §6)。
abstract interface class ExpressionRecognitionService {
  Stream<ExpressionResult> get results;
  bool get isRunning;
  Future<void> initialize();
  Future<void> start();
  Future<void> pause();
  Future<void> stop();
  Future<void> dispose();
}

/// 权限服务抽象。
abstract interface class PermissionService {
  Future<bool> requestCamera();
  Future<bool> requestNotifications();
  Future<bool> get hasCamera;
  Future<bool> get hasNotifications;
}

/// 分析服务抽象(埋点,当前 Mock)。
abstract interface class AnalyticsService {
  Future<void> logEvent(String name, {Map<String, dynamic>? params});
  Future<void> setUserId(String? userId);
}

/// 本地提醒服务抽象 — 调度系统级定时通知。
///
/// 抽象目的:
/// - 让 UI / Notifier 不直接依赖 `flutter_local_notifications` 插件
/// - 单元测试时可注入 [FakeNotificationReminderService]
/// - Web 平台降级为应用内提醒(不调度系统通知)
///
/// 实现类:
/// - [LocalNotificationReminderService]: Android/iOS 真实调度
/// - [FakeNotificationReminderService]: 测试用,记录所有调用
/// - Web 端降级实现: 仅维护状态,不调度系统通知
///
/// **Android 精确提醒要求**(详见 `docs/reminder_guide.md`):
/// - 调度使用 `AndroidScheduleMode.exactAllowWhileIdle`
/// - 仅声明 `SCHEDULE_EXACT_ALARM`(不声明 `USE_EXACT_ALARM`)
/// - Android 13+ 分别处理 POST_NOTIFICATIONS 与 SCHEDULE_EXACT_ALARM
/// - 调度前必须检查:通知权限 / canScheduleExactAlarms / 时间在未来
/// - 精确权限被拒绝时**不得**静默降级为 inexact,返回明确的 failure
abstract interface class NotificationReminderService {
  /// 请求通知显示权限(Android 13+ POST_NOTIFICATIONS / iOS alert+badge+sound)。
  ///
  /// **不**请求 SCHEDULE_EXACT_ALARM — 该权限需用户在系统"闹钟和提醒"
  /// 设置页中授予,通过 [openExactAlarmSettings] 跳转。
  ///
  /// 已授权时不应重复弹出系统弹窗(由实现负责)。
  Future<bool> requestPermission();

  /// 当前权限状态(不触发系统弹窗)。
  ///
  /// - [ReminderPermissionStatus.granted]: 通知显示权限已授权
  /// - [ReminderPermissionStatus.denied]: 已拒绝
  /// - [ReminderPermissionStatus.notDetermined]: 未询问
  /// - [ReminderPermissionStatus.unsupported]: 平台不支持(Web)
  ReminderPermissionStatus permissionStatus();

  /// 重新从系统读取权限状态。
  ///
  /// 用户从系统设置返回应用后调用,使 [permissionStatus] / [canScheduleExactAlarms]
  /// 反映最新状态。capabilityStatus 也会随权限变化(权限撤销后不再 supported)。
  Future<void> refreshPermissionStatus();

  /// 是否可调度精确闹钟。
  ///
  /// - Android 12+: 返回 `SCHEDULE_EXACT_ALARM` 是否已授予
  /// - Android <12 / iOS: 返回 `true`(系统不要求该权限)
  /// - Web: 返回 `false`(平台不支持后台调度)
  Future<bool> canScheduleExactAlarms();

  /// 打开系统"闹钟和提醒"设置页(Android 12+)。
  ///
  /// 其它平台为 no-op(不会抛异常,以便 UI 无差别调用)。
  Future<void> openExactAlarmSettings();

  /// 打开应用通知设置页。
  Future<void> openNotificationSettings();

  /// 调度一条任务提醒。
  ///
  /// [taskId] 任务 ID(用于 cancelAllForTask 分组)
  /// [offsetMinutes] 提前提醒分钟数 — 与 taskId 组合生成**稳定**的 notificationId,
  ///   同一 taskId+offset 在多次调度中产生相同 ID,从而支持"覆盖旧提醒"。
  /// [title] 通知标题
  /// [body] 通知正文
  /// [scheduledAt] 触发时间(本地时区)
  ///
  /// 返回 [ReminderScheduleResult] — UI 据此决定如何反馈给用户:
  /// - `notificationPermissionDenied`: 提示去开启通知权限
  /// - `exactAlarmPermissionDenied`: 提示去开启"闹钟和提醒",**不**显示"提醒已设置"
  /// - `pastTime`: 时间已过,提示用户重新选择
  /// - `unsupportedPlatform`: Web 平台,展示降级文案
  /// - `pluginException`: 插件异常,不虚报成功
  Future<ReminderScheduleResult> scheduleReminder({
    required String taskId,
    required int offsetMinutes,
    required String title,
    required String body,
    required DateTime scheduledAt,
  });

  /// 取消指定任务+偏移的提醒。
  Future<void> cancelReminder(String taskId, int offsetMinutes);

  /// 取消指定任务的所有提醒(支持单任务多偏移时一次清空)。
  Future<void> cancelAllForTask(String taskId);

  /// 更新指定任务的提醒(等同于 cancelAllForTask + schedule)。
  ///
  /// 当 offset 变化时,旧 ID 与新 ID 不同 — 内部会先取消该任务下所有已知偏移的提醒。
  Future<ReminderScheduleResult> updateReminder({
    required String taskId,
    required int offsetMinutes,
    required String title,
    required String body,
    required DateTime scheduledAt,
  });

  /// 恢复持久化的提醒列表。
  ///
  /// 调用时机:
  /// - 应用启动后(设备重启 / 应用更新后,系统接收器已重建 alarms,
  ///   但若用户曾撤销 SCHEDULE_EXACT_ALARM 又重新授予,需重新调度)
  /// - 用户从系统设置授予精确提醒权限返回应用后
  ///
  /// 实现要求:
  /// - 跳过 `taskCompleted` / `taskDeleted` 的条目
  /// - 跳过 `scheduledAt` 已过去的条目
  /// - 跳过权限/能力不足时无法调度的条目(返回结果计入失败,但不抛异常)
  /// - **不重复创建**已存在的提醒(通过 `pendingNotificationRequests` 去重或内存跟踪)
  ///
  /// 返回成功恢复的提醒数。
  Future<int> restoreReminders(List<ReminderEntry> entries);

  /// 当前平台能力状态。
  ///
  /// - [ReminderCapabilityStatus.supported]: 平台支持系统级定时通知(Android/iOS)
  /// - [ReminderCapabilityStatus.degraded]: 平台不支持后台调度(Web),仅应用内提醒
  /// - [ReminderCapabilityStatus.unknown]: 尚未检测
  ///
  /// **权限撤销会改变能力状态**:Android 上 SCHEDULE_EXACT_ALARM 被撤销后
  /// 返回 `degraded`(只能 inexact,且本实现拒绝 inexact 降级 → 实际无法调度)。
  ReminderCapabilityStatus capabilityStatus();
}

/// 提醒能力状态。
enum ReminderCapabilityStatus {
  /// 平台支持系统级定时通知(Android/iOS)
  supported,

  /// 平台不支持后台调度(Web),仅应用内提醒
  degraded,

  /// 尚未检测
  unknown,
}

/// 提醒权限状态。
enum ReminderPermissionStatus {
  /// 已授权
  granted,

  /// 已拒绝
  denied,

  /// 未询问
  notDetermined,

  /// 平台不支持
  unsupported,
}

/// 提醒调度结果 — 描述一次调度的具体结果。
///
/// UI 据此决定如何反馈给用户(是否提示 / 跳转哪里)。
class ReminderScheduleResult {
  const ReminderScheduleResult.success(this.notificationId)
      : success = true,
        failure = null;

  const ReminderScheduleResult.failed(this.failure)
      : success = false,
        notificationId = null;

  /// 是否成功调度。
  final bool success;

  /// 失败原因(`success == false` 时非空)。
  final ReminderScheduleFailure? failure;

  /// 实际分配的通知 ID(`success == true` 时非空)。
  final int? notificationId;

  @override
  String toString() => success
      ? 'ReminderScheduleResult.success($notificationId)'
      : 'ReminderScheduleResult.failed($failure)';
}

/// 提醒调度失败原因。
enum ReminderScheduleFailure {
  /// 通知显示权限未授予(Android 13+ POST_NOTIFICATIONS 被拒绝)。
  notificationPermissionDenied,

  /// 精确提醒权限未授予(Android 12+ SCHEDULE_EXACT_ALARM 未授予)。
  ///
  /// UI 应:不显示"提醒已设置",提示"尚未获得精确提醒权限",
  /// 提供"前往系统设置"操作,返回后重新检查权限。
  exactAlarmPermissionDenied,

  /// 提醒时间已过去。
  pastTime,

  /// 当前平台不支持系统调度(Web)。
  unsupportedPlatform,

  /// 插件调用异常 — 不虚报成功。
  pluginException,
}

/// 用于恢复调度的提醒条目 — 由调用方从持久化任务列表构造。
///
/// `offsetMinutes` 用于生成稳定 notificationId(taskId + offset 组合哈希)。
/// 当 deadline 与 reminderAt 都已持久化时,offset = deadline - reminderAt。
class ReminderEntry {
  const ReminderEntry({
    required this.taskId,
    required this.title,
    required this.body,
    required this.scheduledAt,
    required this.offsetMinutes,
    required this.taskCompleted,
    required this.taskDeleted,
  });

  final String taskId;
  final String title;
  final String body;
  final DateTime scheduledAt;
  final int offsetMinutes;
  final bool taskCompleted;
  final bool taskDeleted;
}
