import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
export '../config/app_config.dart';
import '../../data/models/models.dart';
import '../../data/services/api/api_client.dart';
import '../../data/services/api/api_counselor_chat_service.dart';
import '../../data/services/api/api_knowledge_base_service.dart';
import '../../data/services/api/api_knowledge_management_service.dart';
import '../../data/services/api/api_notification_extraction_service.dart';
import '../../data/services/lite_rt_expression_recognition_service.dart';
import '../../data/services/local_notification_reminder_service.dart';
import '../../data/services/service_interfaces.dart';
import '../../mock/mock_data/mock_data.dart';
import '../../mock/mock_services/mock_knowledge_management_service.dart';
import '../../mock/mock_services/mock_services.dart';

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

/// 本地提醒服务 — 用于待办截止前的系统通知调度。
///
/// 当前实现:
/// - Android/iOS: [LocalNotificationReminderService] 真实调度系统通知
/// - Web: 自动降级为应用内提醒(不支持后台调度)
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

/// 任务仓库 — 当前 Mock 内存实现。
///
/// 真实后端模式下仍使用本地 Mock 仓库(任务为本地状态,本轮不接后端任务 API),
/// 以保证比赛演示模式可用,且后端不可用时不影响待办功能。
final taskRepositoryProvider = Provider<TaskRepository>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      // 任务本轮保持本地实现(后端不提供任务 CRUD 接口)
      return MockTaskRepository();
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

/// 学习会话仓库 — 当前 Mock,后续接入 FastAPI。
final studySessionRepositoryProvider = Provider<StudySessionRepository>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      throw UnimplementedError('真实学习会话仓库尚未接入,请切换到 Mock 模式');
    }
    return MockStudySessionRepository();
  },
);

/// 权限服务 — 当前 Mock。
final permissionServiceProvider = Provider<PermissionService>(
  (ref) => MockPermissionService(),
);

/// 分析服务 — 当前 Mock。
final analyticsServiceProvider = Provider<AnalyticsService>(
  (ref) => MockAnalyticsService(),
);

/// 表情识别服务 — 暴露抽象接口,UI 不依赖具体 Mock 类型。
///
/// 当前阶段:始终返回 Mock 实现。
/// 后续阶段:根据 [AppConfig.useMockExpressionRecognition] 切换为
/// [LiteRtExpressionRecognitionService](真实 CNN + LiteRT)。
final expressionRecognitionProvider =
    Provider<ExpressionRecognitionService>((ref) {
  final config = ref.watch(appConfigProvider);
  final settings = ref.watch(appSettingsProvider);

  if (!config.useMockExpressionRecognition) {
    // 真实 LiteRT 模型尚未接入,所有方法会抛 UnimplementedError。
    // 接入计划见 lite_rt_expression_recognition_service.dart 注释。
    return LiteRtExpressionRecognitionService();
  }

  final service = MockExpressionRecognitionService(
    confidenceThreshold: settings.expressionConfidenceThreshold,
    stableFrames: settings.expressionStableFrames,
    suggestionCooldownMinutes: settings.suggestionCooldownMinutes,
  );
  ref.onDispose(service.dispose);
  return service;
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

/// 当前用户。
final currentUserProvider = Provider<AppUser>((ref) => MockData.currentUser);

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
  void toggleDemoMode() => state = state.copyWith(demoMode: !state.demoMode);
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
/// 集成本地提醒(Android 精确提醒完整闭环):
/// - createTask/updateTask: 若 `reminderEnabled && reminderAt != null`,调度精确提醒
/// - toggleComplete: 完成时取消未触发的提醒(避免已完成任务仍弹通知)
/// - softDelete/hardDelete: 取消对应系统通知
/// - restore: 恢复未完成任务后,根据设置重新调度
///
/// **调度策略**(详见 `docs/reminder_guide.md`):
/// - 使用 `AndroidScheduleMode.exactAllowWhileIdle`(精确 + Doze 下也能触发)
/// - 调度前检查:通知权限 / canScheduleExactAlarms / 时间在未来 / 任务未完成
/// - 精确权限被拒时**不**静默降级,返回 `exactAlarmPermissionDenied`
/// - 通过 (taskId, offsetMinutes) 生成稳定 notificationId,支持覆盖旧提醒与重启去重
///
/// 提醒调度是"尽力而为" — 失败不阻断任务操作,但 UI 通过 [lastScheduleResult]
/// 与 [reminderStatusProvider] 准确反映状态,**不**虚报"提醒已设置"。
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

  /// 最近一次调度结果(供 UI / 测试读取,以判断是否需提示用户前往系统设置)。
  ///
  /// `null` 表示尚未调度或最近一次为取消操作。
  ReminderScheduleResult? lastScheduleResult;

  /// 最近一次调度对应的 taskId(便于 UI 定位任务)。
  String? lastScheduleTaskId;

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

  /// 计算 taskId 对应的 offsetMinutes(用于稳定 notificationId 生成)。
  ///
  /// 当 deadline 与 reminderAt 都存在时,offset = deadline - reminderAt(分钟)。
  /// 这是跨进程稳定的"提醒身份" — 同一任务同一偏移在多次调度中产生相同 ID,
  /// 支持"覆盖旧提醒"与"重启恢复去重"。
  ///
  /// 退化为 0 的场景:deadline 缺失 / reminderAt 在 deadline 之后(异常数据)。
  /// 此时仍可调度,只是无法通过 offset 区分多偏移提醒(本场景不出现多偏移)。
  int _offsetMinutesFor(Task task) {
    final deadline = task.deadline;
    final reminderAt = task.reminderAt;
    if (deadline == null || reminderAt == null) return 0;
    final diff = deadline.difference(reminderAt);
    if (diff.isNegative) return 0;
    return diff.inMinutes;
  }

  /// 根据 task 的 reminderEnabled/reminderAt 调度或取消系统通知。
  /// 调用时机: createTask / updateTask / toggleComplete / restore / setReminder。
  ///
  /// 返回调度结果,供调用方决定 UI 反馈。**不**抛异常 — 调度失败仅返回 failure。
  Future<ReminderScheduleResult?> _syncReminder(Task task) async {
    if (task.deleted || task.completed) {
      // 已删除或已完成 — 取消任何已调度的通知
      await _reminder.cancelAllForTask(task.id);
      lastScheduleResult = null;
      lastScheduleTaskId = null;
      return null;
    }
    if (!task.reminderEnabled || task.reminderAt == null) {
      // 提醒未启用 — 取消已调度的通知
      await _reminder.cancelAllForTask(task.id);
      lastScheduleResult = null;
      lastScheduleTaskId = null;
      return null;
    }
    // 提醒启用且有触发时间 — 调度(覆盖旧通知)
    final content = _reminderContent(task);
    final offset = _offsetMinutesFor(task);
    final result = await _reminder.updateReminder(
      taskId: task.id,
      offsetMinutes: offset,
      title: content.title,
      body: content.body,
      scheduledAt: task.reminderAt!,
    );
    lastScheduleResult = result;
    lastScheduleTaskId = task.id;
    return result;
  }

  Future<Task> createTask(Task task) async {
    final created = await _repo.createTask(task);
    // 调度系统通知(若启用)
    if (created.reminderEnabled && created.reminderAt != null) {
      await _syncReminder(created);
    }
    return created;
  }

  Future<void> updateTask(Task task) async {
    await _repo.updateTask(task);
    // 同步系统通知:
    // - deadline 变化 → offset 变化 → 旧 ID 与新 ID 不同(由 updateReminder 内部 cancelAll)
    // - reminderEnabled/reminderAt 变化 → 重新调度或取消
    // - 通知正文中的剩余时间随 deadline 联动刷新
    await _syncReminder(task);
  }

  Future<void> toggleComplete(Task task) async {
    final updated = task.copyWith(
      completed: !task.completed,
      completedAt: !task.completed ? DateTime.now() : null,
    );
    await _repo.updateTask(updated);
    // 完成时取消未触发的提醒;恢复未完成时若 reminderEnabled 则重新调度
    await _syncReminder(updated);
  }

  Future<void> softDelete(String id) async {
    await _repo.softDelete(id);
    // 软删除也取消系统通知(用户不再需要提醒)
    await _reminder.cancelAllForTask(id);
  }

  Future<void> restore(String id) async {
    await _repo.restore(id);
    // 恢复后,若任务有启用的提醒,重新调度
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
  /// 调用后会立即同步系统通知。
  ///
  /// 返回调度结果 — UI 据此决定反馈:
  /// - `null`:提醒已关闭(取消)
  /// - `success`:可显示"提醒已设置"
  /// - `exactAlarmPermissionDenied`:**不**显示"提醒已设置",提示前往系统设置
  /// - 其它 failure:相应提示
  Future<ReminderScheduleResult?> setReminder(
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

  /// 恢复所有未完成、未删除、已启用提醒的任务的精确提醒。
  ///
  /// 调用时机(由 [reminderRestoreProvider] 触发):
  /// - 应用启动后(设备重启 / 应用更新 / 进程重启)
  /// - 用户从系统设置授予精确提醒权限返回应用后
  ///
  /// 行为:
  /// - 跳过已完成 / 已删除 / 已过期 / 未启用提醒的任务
  /// - 由 [NotificationReminderService.restoreReminders] 通过 pendingNotificationRequests
  ///   去重,**不重复创建**同一提醒
  /// - 演示数据恢复(resetToDemo)时,先 cancelAll 再 restore,避免大量重复系统通知
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

/// 提醒能力/权限快照 — 由 [reminderStatusProvider] 提供给 UI。
///
/// 反映当前平台能力、通知权限与精确提醒权限的最新状态。UI 据此决定:
/// - 显示哪些权限引导横幅
/// - 是否允许用户启用提醒开关
/// - 是否显示"前往系统设置"操作
class ReminderStatusSnapshot {
  const ReminderStatusSnapshot({
    required this.capability,
    required this.permission,
    required this.canScheduleExactAlarms,
  });

  final ReminderCapabilityStatus capability;
  final ReminderPermissionStatus permission;
  final bool canScheduleExactAlarms;

  /// 是否可以调度精确提醒(平台支持 + 通知权限 + 精确权限 全部满足)。
  bool get canSchedule =>
      capability == ReminderCapabilityStatus.supported &&
      permission == ReminderPermissionStatus.granted &&
      canScheduleExactAlarms;

  /// 是否需要引导用户授予通知权限。
  bool get needsNotificationPermission =>
      capability == ReminderCapabilityStatus.supported &&
      (permission == ReminderPermissionStatus.notDetermined ||
          permission == ReminderPermissionStatus.denied);

  /// 是否需要引导用户授予精确提醒权限(Android 12+)。
  bool get needsExactAlarmPermission =>
      capability == ReminderCapabilityStatus.supported &&
      permission == ReminderPermissionStatus.granted &&
      !canScheduleExactAlarms;
}

/// 提醒状态 Provider — UI 通过此 Provider 读取当前能力/权限快照。
///
/// - UI 在 onResume(应用回到前台)时调用 [refreshReminderStatusProvider]
///   重新读取系统状态(用户可能从系统设置改了权限)
/// - 调度失败后可通过 [refreshReminderStatusProvider] 主动刷新
final reminderStatusProvider =
    FutureProvider<ReminderStatusSnapshot>((ref) async {
  final service = ref.watch(notificationReminderProvider);
  await service.refreshPermissionStatus();
  return ReminderStatusSnapshot(
    capability: service.capabilityStatus(),
    permission: service.permissionStatus(),
    canScheduleExactAlarms: await service.canScheduleExactAlarms(),
  );
});

/// 提醒状态刷新触发器 — 通过递增 key 让 [reminderStatusProvider] 重新计算。
///
/// 用法:
/// ```dart
/// ref.read(reminderStatusRefreshTriggerProvider.notifier).bump();
/// ```
final reminderStatusRefreshTriggerProvider = StateProvider<int>((_) => 0);

/// 监听 [reminderStatusRefreshTriggerProvider] 变化,重新读取权限状态。
final refreshedReminderStatusProvider =
    FutureProvider<ReminderStatusSnapshot>((ref) async {
  // 依赖 refresh trigger,触发时重新计算
  ref.watch(reminderStatusRefreshTriggerProvider);
  final service = ref.watch(notificationReminderProvider);
  await service.refreshPermissionStatus();
  return ReminderStatusSnapshot(
    capability: service.capabilityStatus(),
    permission: service.permissionStatus(),
    canScheduleExactAlarms: await service.canScheduleExactAlarms(),
  );
});

/// 提醒恢复 Provider — 应用启动后或权限重新授予时调度恢复。
///
/// 调用 [TaskListNotifier.restoreAllReminders],返回成功恢复的提醒数。
/// 重复调用安全(由 [NotificationReminderService.restoreReminders] 内部去重)。
final reminderRestoreProvider = FutureProvider<int>((ref) async {
  // 依赖 refresh trigger — 用户从系统设置返回后,UI 调用 bump 触发恢复
  ref.watch(reminderStatusRefreshTriggerProvider);
  final notifier = ref.watch(taskListProvider.notifier);
  return notifier.restoreAllReminders();
});

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
      final content = await service.send(
        text,
        conversationId: 'conv_main',
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
