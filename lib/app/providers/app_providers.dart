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
/// 集成本地提醒:
/// - createTask/updateTask: 若 `reminderEnabled && reminderAt != null`,调度系统通知
/// - toggleComplete: 完成时取消未触发的提醒(避免已完成任务仍弹通知)
/// - softDelete/hardDelete: 取消对应系统通知
///
/// 提醒调度是"尽力而为" — 失败(权限未授予/Web 平台/时间已过)不会阻断任务操作,
/// 只是不调度系统通知。UI 层通过 [notificationReminderProvider] 的 capabilityStatus
/// 向用户解释平台限制。
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

  /// 根据 task 的 reminderEnabled/reminderAt 调度或取消系统通知。
  /// 调用时机: createTask / updateTask 之后。
  Future<void> _syncReminder(Task task) async {
    if (task.deleted || task.completed) {
      // 已删除或已完成 — 取消任何已调度的通知
      await _reminder.cancelAllForTask(task.id);
      return;
    }
    if (!task.reminderEnabled || task.reminderAt == null) {
      // 提醒未启用 — 取消已调度的通知
      await _reminder.cancelAllForTask(task.id);
      return;
    }
    // 提醒启用且有触发时间 — 调度(覆盖旧通知)
    final content = _reminderContent(task);
    await _reminder.updateReminder(
      taskId: task.id,
      title: content.title,
      body: content.body,
      scheduledAt: task.reminderAt!,
    );
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
    final oldTask = _repo.tasks.where((t) => t.id == task.id).firstOrNull;
    await _repo.updateTask(task);
    // 同步系统通知:
    // - deadline 变化时,通知正文中的剩余时间需要更新
    // - reminderEnabled/reminderAt 变化时,需要重新调度或取消
    await _syncReminder(task);
    // 若 deadline 变化但 reminderAt 未跟随更新,通知正文仍会通过 updateReminder 刷新
    if (oldTask != null &&
        oldTask.deadline != task.deadline &&
        task.reminderEnabled &&
        task.reminderAt != null) {
      final content = _reminderContent(task);
      await _reminder.updateReminder(
        taskId: task.id,
        title: content.title,
        body: content.body,
        scheduledAt: task.reminderAt!,
      );
    }
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
  Future<void> setReminder(Task task, DateTime? reminderAt) async {
    final updated = task.copyWith(
      reminderEnabled: reminderAt != null,
      reminderAt: reminderAt ?? task.reminderAt,
    );
    await _repo.updateTask(updated);
    await _syncReminder(updated);
  }

  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }
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
