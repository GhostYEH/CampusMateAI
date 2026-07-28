import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
export '../config/app_config.dart';
export 'auth_providers.dart';
import '../../data/models/models.dart';
import '../../data/services/api/api_client.dart';
import '../../data/services/api/api_counselor_chat_service.dart';
import '../../data/services/api/api_knowledge_base_service.dart';
import '../../data/services/api/api_knowledge_management_service.dart';
import '../../data/services/api/api_notification_extraction_service.dart';
import '../../data/services/api/api_study_session_repository.dart';
import '../../data/services/api/api_task_breakdown_service.dart';
import '../../data/services/api/api_task_repository.dart';
import '../../data/services/device_permission_service.dart';
import '../../data/services/expression_service_status.dart';
// 条件导入:Web 平台使用 stub(不依赖 dart:ffi / TFLite / ML Kit),
// 原生平台(Android/iOS/桌面)使用真实 LiteRT 实现。
import '../../data/services/lite_rt_expression_recognition_service_web.dart'
    if (dart.library.io) '../../data/services/lite_rt_expression_recognition_service.dart';
import '../../data/services/local_notification_reminder_service.dart';
import '../../data/services/service_interfaces.dart';
import '../../mock/mock_data/mock_data.dart';
import '../../mock/mock_services/mock_knowledge_management_service.dart';
import '../../mock/mock_services/mock_services.dart';
import '../../mock/mock_services/mock_task_breakdown_service.dart';

// ===== 真实后端 API 客户端(仅在 Real Backend 模式下构造)=====

/// Dio 客户端 Provider — 单例,所有 ApiXxxService 共享。
///
/// 仅当 [AppConfig.useMockBackend] 为 false 时才被使用。
final apiClientProvider = Provider<ApiClient>((ref) {
  final config = ref.watch(appConfigProvider);
  return ApiClient(baseUrl: config.apiBaseUrl);
});

// ===== 服务接口 Providers(依赖抽象接口,通过 AppConfig 切换实现)=====

/// 知识库服务 — Mock / Real 通过 AppConfig 切换。
final knowledgeBaseProvider = Provider<KnowledgeBaseService>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      return ApiKnowledgeBaseService(ref.watch(apiClientProvider));
    }
    return MockKnowledgeBaseService();
  },
);

/// 知识库管理服务 — Mock / Real 通过 AppConfig 切换。
///
/// 用于知识库管理页面(状态/列表/上传/删除/重建)。
/// Mock 模式使用 [MockKnowledgeManagementService] 内存实现;
/// 真实模式使用 [ApiKnowledgeManagementService] 调用 FastAPI 后端。
final knowledgeManagementProvider = Provider<KnowledgeManagementService>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      return ApiKnowledgeManagementService(ref.watch(apiClientProvider));
    }
    return MockKnowledgeManagementService();
  },
);

/// 本地提醒服务 — 用于待办截止前的系统精确提醒调度(Android 优先)。
///
/// 当前实现:
/// - Android/iOS: [LocalNotificationReminderService] 使用 `exactAllowWhileIdle`
/// - Web: 自动降级为应用内提醒(不支持后台精确调度)
///
/// 初始化策略:
/// - timezone 数据库与插件在 [ReminderBootstrap.initialize] 中预先初始化(main 启动时)
/// - 实现类内部对 `ensureInitialized` 是幂等的,首次调度时也会惰性初始化
/// - 因此 Provider 不在此处调用任何初始化方法,避免抽象接口暴露实现细节
///
/// 测试时可通过 ProviderScope.override 注入 [FakeNotificationReminderService]。
final notificationReminderProvider = Provider<NotificationReminderService>(
  (ref) => LocalNotificationReminderService(),
);

/// 提醒能力与权限快照 — UI 通过此 Provider 监听状态变化。
///
/// 调用 `ref.read(reminderStatusProvider.notifier).refresh()` 可主动刷新
/// (用户从系统设置返回应用后调用)。
final reminderStatusProvider =
    StateNotifierProvider<ReminderStatusNotifier, ReminderStatusSnapshot>(
  (ref) {
    final service = ref.watch(notificationReminderProvider);
    return ReminderStatusNotifier(service);
  },
);

class ReminderStatusNotifier extends StateNotifier<ReminderStatusSnapshot> {
  ReminderStatusNotifier(this._service)
      : super(
          ReminderStatusSnapshot(
            capability: _service.capabilityStatus(),
            permission: _service.permissionStatus(),
            canScheduleExactAlarms: false,
          ),
        );

  final NotificationReminderService _service;

  /// 主动刷新 — 用户从系统设置返回应用后调用。
  Future<void> refresh() async {
    await _service.refreshPermissionStatus();
    final canExact = await _service.canScheduleExactAlarms();
    if (!mounted) return;
    state = ReminderStatusSnapshot(
      capability: _service.capabilityStatus(),
      permission: _service.permissionStatus(),
      canScheduleExactAlarms: canExact,
    );
  }
}

/// 通知智能提取服务 — Mock / Real 通过 AppConfig 切换。
final notificationExtractionProvider = Provider<NotificationExtractionService>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      return ApiNotificationExtractionService(ref.watch(apiClientProvider));
    }
    return MockNotificationExtractionService();
  },
);

/// 任务仓库 — Mock / Real 通过 AppConfig 切换。
///
/// 真实后端模式(`USE_MOCK_BACKEND=false`)下使用 [ApiTaskRepository],
/// 调用 `/api/v1/tasks` 系列接口实现真实持久化(对齐后端个人待办闭环)。
/// Mock 模式下使用 [MockTaskRepository],保证离线可用与演示模式可运行。
///
/// 网络错误时 [ApiTaskRepository] 抛 [ApiException],由 UI 层展示错误,
/// 不静默伪装成功(对齐 Flutter 要求 #8)。
/// 本地通知提醒仍由 [TaskListNotifier] 通过 [notificationReminderProvider] 调度,
/// 与后端任务状态同步(对齐 Flutter 要求 #7)。
final taskRepositoryProvider = Provider<TaskRepository>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      return ApiTaskRepository(ref.watch(apiClientProvider));
    }
    return MockTaskRepository();
  },
);

/// AI 导员聊天服务 — Mock / Real 通过 AppConfig 切换。
final counselorChatProvider = Provider<CounselorChatService>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      return ApiCounselorChatService(ref.watch(apiClientProvider));
    }
    return MockCounselorChatService(
      knowledgeBase: ref.watch(knowledgeBaseProvider),
    );
  },
);

/// 学习会话仓库 — Mock / Real 通过 AppConfig 切换。
///
/// - Mock 模式: [MockStudySessionRepository] 内存状态机 + 本地持久化
/// - 真实后端: [ApiStudySessionRepository] 调用 FastAPI `/api/v1/study/sessions`,
///   状态机校验与用户隔离由后端完成,网络失败抛 [ApiException](不伪造保存成功)。
final studySessionRepositoryProvider = Provider<StudySessionRepository>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      return ApiStudySessionRepository(ref.watch(apiClientProvider));
    }
    final repo = MockStudySessionRepository();
    ref.onDispose(repo.dispose);
    return repo;
  },
);

/// 任务拆解服务 — Mock / Real 通过 AppConfig 切换。
///
/// - Mock 模式: [MockTaskBreakdownService] 本地规则化拆解,标注 mode=rule_fallback
/// - 真实后端: [ApiTaskBreakdownService] 调用 FastAPI `/api/v1/study/task-breakdown`,
///   后端负责 LLM/规则降级/知识库依赖/任务权限校验。
final taskBreakdownServiceProvider = Provider<TaskBreakdownService>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      return ApiTaskBreakdownService(ref.watch(apiClientProvider));
    }
    return MockTaskBreakdownService();
  },
);

/// 权限服务 — 真实实现基于 `permission_handler`。
///
/// 测试时可通过 ProviderScope.override 注入 [MockPermissionService]。
///
/// **不反复弹窗**(AGENTS.md §2.3):
/// UI 通过 [cameraPermissionStatus] 判断是否为永久拒绝,
/// 永久拒绝时引导用户去系统设置,而非反复调用 [requestCamera]。
final permissionServiceProvider = Provider<PermissionService>(
  (ref) => DevicePermissionService(),
);

/// 分析服务 — 当前 Mock。
final analyticsServiceProvider = Provider<AnalyticsService>(
  (ref) => MockAnalyticsService(),
);

/// 表情识别服务 — 暴露抽象接口,UI 不依赖具体 Mock 类型。
///
/// 切换策略(对齐 AGENTS.md §2.4):
/// - 真实模式(`useMockExpressionRecognition=false`):
///   返回 [LiteRtExpressionRecognitionService],真实摄像头 + ML Kit + TFLite。
///   Release 构建下强制真实模式,模型加载失败通过 [expressionStatusProvider]
///   暴露错误,不静默回退 Mock。
/// - Mock 模式(`useMockExpressionRecognition=true`,仅 Debug):
///   返回 [MockExpressionRecognitionService],带明显 Mock 标识。
///
/// **生命周期管理**:
/// Provider 销毁时调用 service.dispose,确保摄像头/Interpreter/StreamController
/// 都被正确释放。
final expressionRecognitionProvider =
    Provider<ExpressionRecognitionService>((ref) {
  final config = ref.watch(appConfigProvider);
  final settings = ref.watch(appSettingsProvider);

  if (!config.useMockExpressionRecognition) {
    // 真实 LiteRT 模式
    final service = LiteRtExpressionRecognitionService();
    ref.onDispose(service.dispose);
    return service;
  }

  // Mock 模式(仅 Debug,Release 已在 AppConfig 中强制禁用)
  final service = MockExpressionRecognitionService(
    confidenceThreshold: settings.expressionConfidenceThreshold,
    stableFrames: settings.expressionStableFrames,
    suggestionCooldownMinutes: settings.suggestionCooldownMinutes,
  );
  ref.onDispose(service.dispose);
  return service;
});

/// 表情识别服务状态流 — UI 通过此 Provider 监听模型/摄像头/性能指标。
///
/// 包含:
/// - 模型状态(加载中 / 已就绪 / 失败 / 未安装)
/// - 摄像头状态(空闲 / 启动中 / 运行中 / 已停止 / 错误 / 权限拒绝)
/// - 平台降级说明(Web / 桌面不支持 TFLite / ML Kit)
/// - 推理延迟与已处理帧数
///
/// Release 模式下模型加载失败时,通过此流暴露错误,**不静默回退 Mock**。
final expressionStatusProvider =
    StreamProvider<ExpressionServiceStatus>((ref) async* {
  final service = ref.watch(expressionRecognitionProvider);
  // 初始化时发出初始状态
  yield ExpressionServiceStatus.initial();
  await for (final s in service.status) {
    yield s;
  }
});

/// Mock 表情控制入口 — 仅在 Mock 模式下返回 Mock 实例,否则返回 null。
///
/// 用于演示模式下的"表情注入"控制台(开发/演示模式专用)。
/// UI 层不直接判断服务具体类型,而是通过此 Provider 获取可选的 Mock 控制。
final mockExpressionControlProvider =
    Provider<MockExpressionRecognitionService?>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.useMockExpressionRecognition) return null;
  final service = ref.watch(expressionRecognitionProvider);
  return service is MockExpressionRecognitionService ? service : null;
});

// ===== 应用状态 =====

/// 当前用户(向后兼容)。
///
/// 未登录时返回 Mock 演示账号(林知夏),保证旧版学生页面继续工作。
/// 登录成功后由 [AuthNotifier.login] 更新为真实登录用户。
///
/// 多角色相关页面应改用 [currentAuthUserProvider](支持 null 表示未登录)。
final currentUserProvider = StateProvider<AppUser>(
  (ref) => MockData.currentUser,
);

/// 应用设置(可持久化,启动时由 main 覆盖注入加载的初始值)。
final appSettingsProvider =
    StateNotifierProvider<AppSettingsNotifier, AppSettings>(
  (ref) => AppSettingsNotifier(),
);

class AppSettingsNotifier extends StateNotifier<AppSettings> {
  AppSettingsNotifier() : super(const AppSettings());

  /// 从持久化数据恢复(仅启动时调用)。
  void restoreFrom(AppSettings settings) {
    state = settings;
  }

  void toggleDarkMode() => state = state.copyWith(darkMode: !state.darkMode);
  void toggleReduceMotion() =>
      state = state.copyWith(reduceMotion: !state.reduceMotion);
  void toggleReminder() =>
      state = state.copyWith(reminderEnabled: !state.reminderEnabled);
  void toggleProactiveSuggestion() => state = state.copyWith(
        counselorProactiveSuggestion: !state.counselorProactiveSuggestion,
      );
  void setReminderLead(int minutes) =>
      state = state.copyWith(reminderLeadMinutes: minutes);
  void setRestInterval(int minutes) =>
      state = state.copyWith(studyRestIntervalMinutes: minutes);
  void setConfidenceThreshold(double v) =>
      state = state.copyWith(expressionConfidenceThreshold: v);
  void setStableFrames(int v) =>
      state = state.copyWith(expressionStableFrames: v);
  void setCooldown(int v) =>
      state = state.copyWith(suggestionCooldownMinutes: v);

  void grantCameraPermission() =>
      state = state.copyWith(cameraPermissionGranted: true);
  void toggleExpressionRecognition() => state = state.copyWith(
        expressionRecognitionEnabled: !state.expressionRecognitionEnabled,
      );

  /// 重置为默认设置(用于"清除本地数据")。
  void resetToDefault() {
    state = const AppSettings();
  }
}

/// 全局校园通知列表。
final campusNoticesProvider =
    StateNotifierProvider<CampusNoticesNotifier, List<CampusNotice>>(
  (ref) => CampusNoticesNotifier(),
);

class CampusNoticesNotifier extends StateNotifier<List<CampusNotice>> {
  CampusNoticesNotifier() : super(MockData.notices);

  void markRead(String id) {
    state = [
      for (final n in state) n.id == id ? n.copyWith(read: true) : n,
    ];
  }

  void markAllRead() {
    state = [for (final n in state) n.copyWith(read: true)];
  }

  int get unreadCount => state.where((n) => !n.read).length;
}

/// 未读通知数。
final unreadNoticeCountProvider = Provider<int>(
  (ref) => ref.watch(campusNoticesProvider).where((n) => !n.read).length,
);

/// 待办任务列表(从仓库派生)。
///
/// 集成本地提醒(对齐 AGENTS.md "Android 精确提醒完整闭环"):
/// - createTask: 若 `reminderEnabled && reminderAt != null`,调度精确提醒
/// - updateTask: deadline / reminderAt / reminderEnabled 变化时,取消旧提醒并按新设置调度
/// - toggleComplete: 完成时取消未触发的提醒;恢复未完成时若启用则重新调度
/// - softDelete/hardDelete: 取消所有相关提醒
/// - restore: 根据当前设置重新调度
/// - [restoreAllReminders]: 应用启动 / 权限重授后批量恢复(去重,不重复创建)
///
/// **不静默降级**: 精确权限被拒时,`scheduleReminder` 返回 `exactAlarmPermissionDenied`,
/// UI 层通过 [ReminderScheduleFeedback] 向用户解释并引导去系统设置授权。
///
/// 注意: StateNotifierProvider 会在 provider 销毁时自动调用 notifier.dispose,
/// 因此无需额外通过 ref.onDispose 注册,否则会导致 dispose 被调用两次。
final taskListProvider = StateNotifierProvider<TaskListNotifier, List<Task>>(
  (ref) {
    final repo = ref.watch(taskRepositoryProvider);
    final reminder = ref.watch(notificationReminderProvider);
    return TaskListNotifier(repo, reminder);
  },
);

class TaskListNotifier extends StateNotifier<List<Task>> {
  TaskListNotifier(this._repo, this._reminder) : super(const []) {
    _refresh();
    _sub = _repo.watchTasks().listen((list) {
      if (mounted) state = list;
    });
  }

  final TaskRepository _repo;
  final NotificationReminderService _reminder;
  late final StreamSubscription<List<Task>> _sub;

  /// 最近一次调度结果(供 UI 显示反馈)。
  ReminderScheduleFeedback? lastScheduleFeedback;

  void _refresh() {
    state = _repo.tasks;
  }

  /// 构造通知标题与正文。
  ({String title, String body}) _reminderContent(Task task) {
    final title = '待办提醒:${task.title}';
    final remaining = task.deadline?.difference(DateTime.now());
    String body;
    if (remaining != null) {
      if (remaining.isNegative) {
        body = '已逾期,请尽快处理';
      } else if (remaining.inHours < 1) {
        body = '即将截止(${remaining.inMinutes}分钟后)';
      } else if (remaining.inHours < 24) {
        body = '${remaining.inHours}小时后截止';
      } else {
        body = '${remaining.inDays}天后截止';
      }
    } else {
      body = '请查看任务详情';
    }
    return (title: title, body: body);
  }

  /// 从 task 推导 offsetMinutes(提醒相对截止的提前分钟数)。
  /// 若无 deadline 则返回 0(表示按 reminderAt 精确触发,无偏移概念)。
  int _offsetMinutesFor(Task task) {
    final deadline = task.deadline;
    final reminderAt = task.reminderAt;
    if (deadline == null || reminderAt == null) return 0;
    final diff = deadline.difference(reminderAt).inMinutes;
    return diff < 0 ? 0 : diff;
  }

  /// 根据 task 的 reminderEnabled/reminderAt 调度或取消精确提醒。
  /// 调用时机: createTask / updateTask 之后。
  ///
  /// 返回 [ReminderScheduleFeedback] 供 UI 显示反馈(成功 / 失败原因)。
  Future<ReminderScheduleFeedback> _syncReminder(Task task) async {
    if (task.deleted || task.completed) {
      await _reminder.cancelAllForTask(task.id);
      return ReminderScheduleFeedback.cancelled;
    }
    if (!task.reminderEnabled || task.reminderAt == null) {
      await _reminder.cancelAllForTask(task.id);
      return ReminderScheduleFeedback.cancelled;
    }
    final content = _reminderContent(task);
    final offset = _offsetMinutesFor(task);
    final result = await _reminder.updateReminder(
      taskId: task.id,
      offsetMinutes: offset,
      title: content.title,
      body: content.body,
      scheduledAt: task.reminderAt!,
    );
    final feedback = ReminderScheduleFeedback.fromResult(result);
    lastScheduleFeedback = feedback;
    return feedback;
  }

  Future<Task> createTask(Task task) async {
    final created = await _repo.createTask(task);
    if (created.reminderEnabled && created.reminderAt != null) {
      await _syncReminder(created);
    }
    return created;
  }

  Future<void> updateTask(Task task) async {
    final oldTask = _repo.tasks.where((t) => t.id == task.id).firstOrNull;
    await _repo.updateTask(task);

    // 若旧的提醒偏移与新偏移不同,先取消旧偏移的提醒(避免残留)
    if (oldTask != null) {
      final oldOffset = _offsetMinutesFor(oldTask);
      final newOffset = _offsetMinutesFor(task);
      if (oldOffset != newOffset && oldTask.reminderEnabled) {
        await _reminder.cancelReminder(task.id, oldOffset);
      }
    }

    // 同步系统通知(包括 deadline 变化时刷新正文)
    await _syncReminder(task);
  }

  Future<void> toggleComplete(Task task) async {
    final updated = task.copyWith(
      completed: !task.completed,
      completedAt: !task.completed ? DateTime.now() : null,
    );
    await _repo.updateTask(updated);
    await _syncReminder(updated);
  }

  Future<void> softDelete(String id) async {
    await _repo.softDelete(id);
    await _reminder.cancelAllForTask(id);
  }

  Future<void> restore(String id) async {
    await _repo.restore(id);
    final task = _repo.tasks.where((t) => t.id == id).firstOrNull;
    if (task != null) await _syncReminder(task);
  }

  Future<void> hardDelete(String id) async {
    await _repo.hardDelete(id);
    await _reminder.cancelAllForTask(id);
  }

  Future<void> toggleMaterial(Task task, String materialId) async {
    final materials = task.materials.map((m) {
      if (m.id == materialId) return m.copyWith(done: !m.done);
      return m;
    }).toList();
    await _repo.updateTask(task.copyWith(materials: materials));
  }

  /// 显式设置提醒(供 UI 调用)。
  ///
  /// [reminderAt] 为 null 表示关闭提醒。
  /// 调用后会立即同步系统通知,并返回反馈供 UI 显示。
  Future<ReminderScheduleFeedback> setReminder(
    Task task,
    DateTime? reminderAt,
  ) async {
    final updated = task.copyWith(
      reminderEnabled: reminderAt != null,
      reminderAt: reminderAt ?? task.reminderAt,
    );
    await _repo.updateTask(updated);
    return _syncReminder(updated);
  }

  /// 应用启动 / 设备重启 / 权限重授后,根据已持久化且未完成的任务恢复精确提醒。
  ///
  /// - 已完成 / 已删除 / 已过期 / 未启用提醒的任务跳过
  /// - 服务层负责去重(同一 (taskId, offsetMinutes) 不重复创建)
  /// - 返回实际恢复的提醒数量
  Future<int> restoreAllReminders() async {
    final entries = <ReminderEntry>[];
    for (final task in _repo.tasks) {
      if (task.deleted || task.completed) continue;
      if (!task.reminderEnabled || task.reminderAt == null) continue;
      final content = _reminderContent(task);
      entries.add(
        ReminderEntry(
          taskId: task.id,
          title: content.title,
          body: content.body,
          scheduledAt: task.reminderAt!,
          offsetMinutes: _offsetMinutesFor(task),
          taskCompleted: task.completed,
          taskDeleted: task.deleted,
        ),
      );
    }
    if (entries.isEmpty) return 0;
    return _reminder.restoreReminders(entries);
  }

  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }
}

/// 提醒调度反馈 — 供 UI 显示成功 / 失败提示。
enum ReminderScheduleFeedback {
  /// 调度成功
  success,

  /// 已取消(任务完成 / 删除 / 关闭提醒)
  cancelled,

  /// 平台不支持(Web)
  unsupportedPlatform,

  /// 通知权限未授予
  notificationPermissionDenied,

  /// 精确提醒权限未授予
  exactAlarmPermissionDenied,

  /// 提醒时间已过期
  pastTime,

  /// 插件调用异常(不虚报成功)
  pluginException;

  static ReminderScheduleFeedback fromResult(ReminderScheduleResult result) {
    if (result.success) return ReminderScheduleFeedback.success;
    switch (result.failure!) {
      case ReminderScheduleFailure.unsupportedPlatform:
        return ReminderScheduleFeedback.unsupportedPlatform;
      case ReminderScheduleFailure.notificationPermissionDenied:
        return ReminderScheduleFeedback.notificationPermissionDenied;
      case ReminderScheduleFailure.exactAlarmPermissionDenied:
        return ReminderScheduleFeedback.exactAlarmPermissionDenied;
      case ReminderScheduleFailure.pastTime:
        return ReminderScheduleFeedback.pastTime;
      case ReminderScheduleFailure.pluginException:
        return ReminderScheduleFeedback.pluginException;
    }
  }

  /// 用户可读的反馈文案。
  String get message {
    switch (this) {
      case ReminderScheduleFeedback.success:
        return '已设置提醒';
      case ReminderScheduleFeedback.cancelled:
        return '已取消提醒';
      case ReminderScheduleFeedback.unsupportedPlatform:
        return 'Web 端仅提供应用内提醒,精确系统提醒请使用 Android';
      case ReminderScheduleFeedback.notificationPermissionDenied:
        return '尚未获得通知权限,无法设置提醒';
      case ReminderScheduleFeedback.exactAlarmPermissionDenied:
        return '尚未获得精确提醒权限,请在系统设置中授予"闹钟和提醒"';
      case ReminderScheduleFeedback.pastTime:
        return '提醒时间已过期,未调度';
      case ReminderScheduleFeedback.pluginException:
        return '提醒调度失败,请稍后重试';
    }
  }

  /// 是否应显示"前往系统设置"入口。
  bool get shouldOfferSettings =>
      this == ReminderScheduleFeedback.notificationPermissionDenied ||
      this == ReminderScheduleFeedback.exactAlarmPermissionDenied;
}

/// 今日任务。
final todayTasksProvider = Provider<List<Task>>((ref) {
  final tasks = ref.watch(taskListProvider);
  return tasks.where((t) {
    if (t.completed || t.deleted) return false;
    final now = DateTime.now();
    if (t.deadline == null) return false;
    final d = t.deadline!;
    return d.year == now.year && d.month == now.month && d.day == now.day;
  }).toList()
    ..sort((a, b) => a.deadline!.compareTo(b.deadline!));
});

/// 即将截止任务(未完成 + 有截止,按截止排序)。
final upcomingTasksProvider = Provider<List<Task>>((ref) {
  final tasks = ref.watch(taskListProvider);
  return tasks
      .where((t) => !t.completed && !t.deleted && t.deadline != null)
      .toList()
    ..sort((a, b) => a.deadline!.compareTo(b.deadline!));
});

/// 已完成任务。
final completedTasksProvider = Provider<List<Task>>((ref) {
  final tasks = ref.watch(taskListProvider);
  return tasks.where((t) => t.completed && !t.deleted).toList()
    ..sort(
      (a, b) => (b.completedAt ?? b.createdAt)
          .compareTo(a.completedAt ?? a.createdAt),
    );
});

/// 今日任务完成进度 0~1。
final todayProgressProvider = Provider<double>((ref) {
  final all = ref.watch(taskListProvider).where((t) {
    if (t.deleted) return false;
    final now = DateTime.now();
    if (t.deadline == null) return false;
    final d = t.deadline!;
    return d.year == now.year && d.month == now.month && d.day == now.day;
  }).toList();
  if (all.isEmpty) return 0;
  final done = all.where((t) => t.completed).length;
  return done / all.length;
});

/// 最近截止任务(最紧急的一项)。
final nearestDeadlineTaskProvider = Provider<Task?>((ref) {
  final upcoming = ref.watch(upcomingTasksProvider);
  return upcoming.isEmpty ? null : upcoming.first;
});

/// 聊天消息列表。
final chatMessagesProvider =
    StateNotifierProvider<ChatMessagesNotifier, List<ChatMessage>>(
  (ref) => ChatMessagesNotifier(ref),
);

/// AI 导员对话上下文 — 由路由 extra 注入,UI 顶部展示。
///
/// 当学生从课程/通知/任务进入 AI 导员时,路由 builder 会调用
/// `ref.read(counselorContextProvider.notifier).set(...)` 设置上下文。
/// 离开 /counselor 时应清除(由 CounselorPage dispose 处理)。
final counselorContextProvider =
    StateProvider<CounselorContext>((ref) => const CounselorContext());

class ChatMessagesNotifier extends StateNotifier<List<ChatMessage>> {
  ChatMessagesNotifier(this.ref) : super([_initialGreeting()]);

  final Ref ref;
  bool _generating = false;

  static ChatMessage _initialGreeting() => ChatMessage(
        id: 'msg_init',
        sender: MessageSender.counselor,
        content: MockData.counselorGreeting,
        timestamp: DateTime.now(),
        actions: const [
          SuggestedAction(
            id: 'a_today',
            label: '查看今日任务',
            type: SuggestedActionType.navigate,
            payload: '/tasks',
          ),
        ],
      );

  bool get isGenerating => _generating;

  Future<void> send(String text) async {
    if (_generating || text.trim().isEmpty) return;
    _generating = true;

    final userMsg = ChatMessage(
      id: 'msg_${DateTime.now().millisecondsSinceEpoch}',
      sender: MessageSender.user,
      content: text.trim(),
      timestamp: DateTime.now(),
    );
    state = [...state, userMsg];

    // 占位流式消息
    final streamingId = 'msg_stream_${DateTime.now().millisecondsSinceEpoch}';
    final streamingMsg = ChatMessage(
      id: streamingId,
      sender: MessageSender.counselor,
      content: '',
      timestamp: DateTime.now(),
      isStreaming: true,
    );
    state = [...state, streamingMsg];

    try {
      final service = ref.read(counselorChatProvider);
      // 读取当前 AI 导员上下文(由路由层注入,可能包含 course_id/class_id/
      // assignment_id/announcement_id/study_session_id/self_report 等)。
      final ctx = ref.read(counselorContextProvider);
      // 注入真实最近待办(对齐要求 #4): 从当前登录用户的真实任务仓库取最近 5 项
      // 未完成且未删除的任务,只发送必要字段(id/title/deadline/priority/status)。
      // 后端会重新校验归属,这里只是为了让 AI 导员能给出个性化执行建议。
      final recentTasks = _buildRecentTasksFromRepo();
      final mergedCtx = ctx.recentTasks.isEmpty && recentTasks.isNotEmpty
          ? ctx.copyWith(recentTasks: recentTasks)
          : ctx;
      // conversation_id 仅作会话标识,不再嵌入业务上下文(对齐要求 #2)。
      // 业务上下文通过 mergedCtx.toContextJson() 作为独立 JSON 字段发送。
      final content = await service.send(
        text,
        conversationId: 'conv_main',
        context: mergedCtx,
        onChunk: (chunk) {
          if (!mounted) return;
          final idx = state.indexWhere((m) => m.id == streamingId);
          if (idx >= 0) {
            final updated = state[idx].copyWith(
              content: state[idx].content + chunk,
            );
            state = [...state]..[idx] = updated;
          }
        },
        onSources: (sources) {
          if (!mounted) return;
          final idx = state.indexWhere((m) => m.id == streamingId);
          if (idx >= 0) {
            state = [...state]..[idx] = state[idx].copyWith(sources: sources);
          }
        },
        onActions: (actions) {
          if (!mounted) return;
          final idx = state.indexWhere((m) => m.id == streamingId);
          if (idx >= 0) {
            state = [...state]..[idx] = state[idx].copyWith(
                actions: actions,
                isStreaming: false,
              );
          }
        },
        onFinalMeta: (meta) {
          if (!mounted) return;
          final idx = state.indexWhere((m) => m.id == streamingId);
          if (idx >= 0) {
            final isMock = ref.read(appConfigProvider).useMockBackend;
            final answerMode = AnswerMode.fromBackendMode(
              mode: meta.mode,
              hasUserDocs: meta.hasUserDocs,
              hasDemoDocs: meta.hasDemoDocs,
              isMock: isMock,
            );
            state = [...state]..[idx] = state[idx].copyWith(
                answerMode: answerMode,
                evidenceLevel: EvidenceLevel.fromString(meta.evidenceLevel),
                confidence: meta.confidence,
                warnings: meta.warnings,
                needsHumanConfirmation: meta.needsHumanConfirmation,
              );
          }
        },
      );
      // 确保最终状态
      final idx = state.indexWhere((m) => m.id == streamingId);
      if (idx >= 0) {
        state = [...state]..[idx] = state[idx].copyWith(
            content: content,
            isStreaming: false,
          );
      }
    } catch (e) {
      final idx = state.indexWhere((m) => m.id == streamingId);
      if (idx >= 0) {
        state = [...state]..[idx] = state[idx].copyWith(
            isStreaming: false,
            streamError: '生成失败,请重试',
          );
      }
    } finally {
      _generating = false;
    }
  }

  /// 从当前登录用户的真实任务仓库构造最近待办列表(对齐要求 #4/#5)。
  ///
  /// 仅发送必要字段: id/title/deadline/priority/status。
  /// 后端会重新校验任务归属,这里只是为了让 AI 导员能给出个性化执行建议。
  /// 最多 5 条,优先未完成且未删除的任务。
  List<CounselorRecentTask> _buildRecentTasksFromRepo() {
    final tasks = ref.read(taskListProvider);
    final upcoming = tasks.where((t) => !t.completed && !t.deleted).toList()
      ..sort((a, b) {
        // 有截止时间的排前,按截止时间升序
        final ad = a.deadline;
        final bd = b.deadline;
        if (ad != null && bd != null) return ad.compareTo(bd);
        if (ad != null) return -1;
        if (bd != null) return 1;
        return b.priority.weight.compareTo(a.priority.weight);
      });
    return upcoming.take(5).map((t) {
      final dl = t.deadline;
      return CounselorRecentTask(
        id: t.id,
        title: t.title,
        deadline: dl?.toIso8601String(),
        priority: t.priority.name,
        status: t.completed ? 'completed' : 'pending',
      );
    }).toList(growable: false);
  }

  void stop() {
    ref.read(counselorChatProvider).stop();
  }

  void copyMessage(String id) {
    // 复制到剪贴板由 UI 层处理
  }

  void regenerate(String id) {
    final idx = state.indexWhere((m) => m.id == id);
    if (idx <= 0) return;
    final userMsg = state[idx - 1];
    // 移除该 AI 回复
    state = state.where((m) => m.id != id).toList();
    send(userMsg.content);
  }

  void clear() {
    state = [_initialGreeting()];
  }
}

/// 当前学习会话。
final currentStudySessionProvider = StreamProvider<StudySession>((ref) async* {
  final repo = ref.watch(studySessionRepositoryProvider);
  await for (final s in repo.watchCurrent()) {
    yield s;
  }
});

/// 学习会话历史。
final studyHistoryProvider = FutureProvider<List<StudySession>>((ref) async {
  final repo = ref.watch(studySessionRepositoryProvider);
  return repo.history(limit: 30);
});

/// 今日学习总时长。
final todayStudyTotalProvider = FutureProvider<Duration>((ref) async {
  final repo = ref.watch(studySessionRepositoryProvider);
  return repo.todayTotal();
});

/// 表情识别结果流。
final expressionResultsProvider =
    StreamProvider<ExpressionResult>((ref) async* {
  final service = ref.watch(expressionRecognitionProvider);
  await for (final r in service.results) {
    yield r;
  }
});

// ===== 后端连接状态 =====

/// 后端连接状态。
enum BackendConnectionStatus {
  /// 已连接且知识库就绪
  connected,

  /// 已连接但知识库为空
  knowledgeBaseEmpty,

  /// 演示模式(Mock,后端未启用)
  demoMode,

  /// 网络错误,无法连接
  disconnected,

  /// 未知(尚未检查)
  unknown,
}

/// 后端状态信息。
class BackendStatus {
  const BackendStatus({
    required this.status,
    this.version = '',
    this.documentCount = 0,
    this.chunkCount = 0,
    this.llmAvailable = false,
    this.lastChecked,
    this.errorMessage,
  });

  final BackendConnectionStatus status;
  final String version;
  final int documentCount;
  final int chunkCount;
  final bool llmAvailable;
  final DateTime? lastChecked;
  final String? errorMessage;

  bool get isAvailable =>
      status == BackendConnectionStatus.connected ||
      status == BackendConnectionStatus.knowledgeBaseEmpty;
}

/// 后端状态 Notifier — 通过 [ApiClient.getHealth] 异步检查。
///
/// UI 层通过 [backendStatusProvider] 监听状态变化,显示"已连接/演示模式/未连接"。
class BackendStatusNotifier extends StateNotifier<AsyncValue<BackendStatus>> {
  BackendStatusNotifier(this._getConfig) : super(const AsyncValue.loading());

  final AppConfig Function() _getConfig;

  /// 触发健康检查。
  Future<void> check() async {
    final config = _getConfig();
    // Mock 模式直接返回 demoMode
    if (config.useMockBackend) {
      state = const AsyncValue.data(
        BackendStatus(status: BackendConnectionStatus.demoMode),
      );
      return;
    }
    state = const AsyncValue.loading();
    try {
      final client = ApiClient(baseUrl: config.apiBaseUrl);
      final health = await client.getHealth();
      final kbInit = health['knowledge_base_initialized'] as bool? ?? false;
      final status = kbInit
          ? BackendConnectionStatus.connected
          : BackendConnectionStatus.knowledgeBaseEmpty;
      state = AsyncValue.data(
        BackendStatus(
          status: status,
          version: health['version'] as String? ?? '',
          documentCount: health['document_count'] as int? ?? 0,
          chunkCount: health['chunk_count'] as int? ?? 0,
          llmAvailable: health['llm_available'] as bool? ?? false,
          lastChecked: DateTime.now(),
        ),
      );
    } on ApiException catch (e) {
      state = AsyncValue.data(
        BackendStatus(
          status: BackendConnectionStatus.disconnected,
          errorMessage: e.message,
          lastChecked: DateTime.now(),
        ),
      );
    } catch (e) {
      state = AsyncValue.data(
        BackendStatus(
          status: BackendConnectionStatus.disconnected,
          errorMessage: e.toString(),
          lastChecked: DateTime.now(),
        ),
      );
    }
  }
}

/// 后端状态 Provider — UI 通过 ref.watch 读取。
///
/// 使用 `ref.read(backendStatusProvider.notifier).check()` 触发检查。
final backendStatusProvider =
    StateNotifierProvider<BackendStatusNotifier, AsyncValue<BackendStatus>>(
  (ref) {
    // 不监听 appConfigProvider 变化(避免重建循环),通过 check() 主动拉取
    return BackendStatusNotifier(() => ref.read(appConfigProvider));
  },
);
