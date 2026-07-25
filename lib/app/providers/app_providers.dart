import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../../data/models/models.dart';
import '../../data/services/lite_rt_expression_recognition_service.dart';
import '../../data/services/service_interfaces.dart';
import '../../mock/mock_data/mock_data.dart';
import '../../mock/mock_services/mock_services.dart';

// ===== 服务接口 Providers(依赖抽象接口,通过 AppConfig 切换实现)=====

/// 知识库服务 — 当前 Mock,后续接入 RAG 向量数据库。
final knowledgeBaseProvider = Provider<KnowledgeBaseService>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      // TODO(后续阶段): 接入真实 RAG 后端
      throw UnimplementedError('真实 RAG 知识库尚未接入,请切换到 Mock 模式');
    }
    return MockKnowledgeBaseService();
  },
);

/// 通知智能提取服务 — 当前 Mock,后续接入 FastAPI LLM。
final notificationExtractionProvider = Provider<NotificationExtractionService>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      throw UnimplementedError('真实通知提取后端尚未接入,请切换到 Mock 模式');
    }
    return MockNotificationExtractionService();
  },
);

/// 任务仓库 — 当前 Mock 内存实现,后续接入 FastAPI + PostgreSQL。
final taskRepositoryProvider = Provider<TaskRepository>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      throw UnimplementedError('真实任务仓库尚未接入,请切换到 Mock 模式');
    }
    return MockTaskRepository();
  },
);

/// AI 导员聊天服务 — 当前 Mock,后续接入 FastAPI + RAG。
final counselorChatProvider = Provider<CounselorChatService>(
  (ref) {
    final config = ref.watch(appConfigProvider);
    if (!config.useMockBackend) {
      throw UnimplementedError('真实 AI 导员后端尚未接入,请切换到 Mock 模式');
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
/// 注意: StateNotifierProvider 会在 provider 销毁时自动调用 notifier.dispose,
/// 因此无需额外通过 ref.onDispose 注册,否则会导致 dispose 被调用两次。
final taskListProvider = StateNotifierProvider<TaskListNotifier, List<Task>>(
  (ref) {
    final repo = ref.watch(taskRepositoryProvider);
    return TaskListNotifier(repo);
  },
);

class TaskListNotifier extends StateNotifier<List<Task>> {
  TaskListNotifier(this._repo) : super(const []) {
    _refresh();
    _sub = _repo.watchTasks().listen((list) {
      if (mounted) state = list;
    });
  }

  final TaskRepository _repo;
  late final StreamSubscription<List<Task>> _sub;

  void _refresh() {
    state = _repo.tasks;
  }

  Future<Task> createTask(Task task) async {
    final created = await _repo.createTask(task);
    return created;
  }

  Future<void> updateTask(Task task) async => _repo.updateTask(task);

  Future<void> toggleComplete(Task task) async {
    await _repo.updateTask(
      task.copyWith(
        completed: !task.completed,
        completedAt: !task.completed ? DateTime.now() : null,
      ),
    );
  }

  Future<void> softDelete(String id) async => _repo.softDelete(id);

  Future<void> restore(String id) async => _repo.restore(id);

  Future<void> hardDelete(String id) async => _repo.hardDelete(id);

  Future<void> toggleMaterial(Task task, String materialId) async {
    final materials = task.materials.map((m) {
      if (m.id == materialId) return m.copyWith(done: !m.done);
      return m;
    }).toList();
    await _repo.updateTask(task.copyWith(materials: materials));
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
