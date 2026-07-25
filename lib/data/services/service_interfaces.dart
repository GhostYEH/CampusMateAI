import '../models/models.dart';

/// 通知智能提取服务抽象。
///
/// UI 层通过依赖注入获取实现(Mock 或真实后端)。
/// 真实实现将通过 FastAPI 调用 LLM + 规则提取。
abstract interface class NotificationExtractionService {
  /// 提取通知结构化信息。
  ///
  /// [onProgress] 回调用于动态展示分步骤处理过程。
  /// 返回 [ExtractedNotice],字段允许为空(未提取到)。
  Future<ExtractedNotice> extract(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  });
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
}

/// AI 导员聊天服务抽象。
abstract interface class CounselorChatService {
  /// 流式发送消息,逐段返回内容。
  ///
  /// [onChunk] 接收增量文本,[onSources] 接收引用来源,
  /// [onActions] 接收建议操作。
  /// 返回完整消息内容。调用方可通过取消 [onChunk] 流终止。
  Future<String> send(
    String message, {
    required String conversationId,
    void Function(String chunk)? onChunk,
    void Function(List<KnowledgeSource> sources)? onSources,
    void Function(List<SuggestedAction> actions)? onActions,
    void Function()? onTyping,
  });

  /// 主动生成提醒(根据待办情况)。
  Future<String?> generateProactiveReminder(List<Task> tasks);

  /// 停止当前生成。
  void stop();
}

/// 校园知识库服务抽象(预留向量数据库接口)。
abstract interface class KnowledgeBaseService {
  Future<List<KnowledgeSource>> search(String query, {int limit = 3});
  Future<List<KnowledgeSource>> get sources;
}

/// 学习会话仓库抽象。
abstract interface class StudySessionRepository {
  StudySession? get current;
  Stream<StudySession> watchCurrent();
  Future<StudySession> start({String? goalId, String? taskId});
  Future<void> pause();
  Future<void> resume();
  Future<StudySession> end({String? selfReportMood});
  Future<List<StudySession>> history({int limit = 30});
  Future<Duration> todayTotal();
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
