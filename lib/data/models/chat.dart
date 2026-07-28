import 'package:equatable/equatable.dart';

/// 消息发送方。
enum MessageSender { user, counselor, system }

/// AI 导员回答的"建议操作"按钮。
class SuggestedAction extends Equatable {
  const SuggestedAction({
    required this.id,
    required this.label,
    this.type = SuggestedActionType.navigate,
    this.payload,
  });

  final String id;
  final String label;
  final SuggestedActionType type;
  final String? payload; // 路由路径或预填问题

  @override
  List<Object?> get props => [id, label, type, payload];
}

enum SuggestedActionType { navigate, prefillQuestion, createTask, none }

/// 知识库引用来源。
///
/// Mock 阶段标注 "模拟资料来源",不得伪造真实学校政策文件。
///
/// 真实后端模式下,以下字段由 RAG 检索结果填充(对齐后端 ChatSource):
/// - [sourceDepartment]: 来源部门
/// - [publishedAt]: 文档发布时间
/// - [version]: 文档版本
/// - [applicableStudents]: 适用对象
/// - [isOfficial]: 是否官方资料(影响优先级)
/// - [isExpired]: 是否过期资料(影响优先级,过期降权)
/// - [isDemo]: 是否属于仿真演示资料(用于"明确演示资料声明")
/// - [section]: 文档小节
/// - [evidenceLevel]: high|medium|low|none|conflict
class KnowledgeSource extends Equatable {
  const KnowledgeSource({
    required this.id,
    required this.title,
    required this.updatedAt,
    this.source = '模拟资料来源',
    this.url,
    this.snippet,
    this.relevance = 0,
    this.sourceDepartment,
    this.publishedAt,
    this.version,
    this.applicableStudents,
    this.section,
    this.isOfficial = false,
    this.isExpired = false,
    this.isDemo = false,
    this.evidenceLevel = 'medium',
  });

  final String id;
  final String title; // 文件名称
  final DateTime updatedAt; // 更新时间
  final String source; // 来源标注(简短展示用)
  final String? url;
  final String? snippet; // 引用片段
  final double relevance; // 相关度 0~1

  // ===== RAG 扩展字段(后端返回,Mock 模式可不填)=====
  final String? sourceDepartment; // 来源部门
  final DateTime? publishedAt; // 文档发布时间
  final String? version; // 文档版本
  final String? applicableStudents; // 适用对象(如"2024级本科生")
  final String? section; // 文档小节
  final bool isOfficial; // 是否官方资料
  final bool isExpired; // 是否过期资料
  final bool isDemo; // 是否属于仿真演示资料
  final String evidenceLevel; // high|medium|low|none|conflict

  KnowledgeSource copyWith({
    String? id,
    String? title,
    DateTime? updatedAt,
    String? source,
    String? url,
    String? snippet,
    double? relevance,
    String? sourceDepartment,
    DateTime? publishedAt,
    String? version,
    String? applicableStudents,
    String? section,
    bool? isOfficial,
    bool? isExpired,
    bool? isDemo,
    String? evidenceLevel,
  }) {
    return KnowledgeSource(
      id: id ?? this.id,
      title: title ?? this.title,
      updatedAt: updatedAt ?? this.updatedAt,
      source: source ?? this.source,
      url: url ?? this.url,
      snippet: snippet ?? this.snippet,
      relevance: relevance ?? this.relevance,
      sourceDepartment: sourceDepartment ?? this.sourceDepartment,
      publishedAt: publishedAt ?? this.publishedAt,
      version: version ?? this.version,
      applicableStudents: applicableStudents ?? this.applicableStudents,
      section: section ?? this.section,
      isOfficial: isOfficial ?? this.isOfficial,
      isExpired: isExpired ?? this.isExpired,
      isDemo: isDemo ?? this.isDemo,
      evidenceLevel: evidenceLevel ?? this.evidenceLevel,
    );
  }

  @override
  List<Object?> get props => [
        id,
        title,
        updatedAt,
        source,
        url,
        snippet,
        relevance,
        sourceDepartment,
        publishedAt,
        version,
        applicableStudents,
        section,
        isOfficial,
        isExpired,
        isDemo,
        evidenceLevel,
      ];
}

/// 聊天消息。
class ChatMessage extends Equatable {
  const ChatMessage({
    required this.id,
    required this.sender,
    required this.content,
    required this.timestamp,
    this.sources = const [],
    this.actions = const [],
    this.isStreaming = false,
    this.streamError,
    this.answerMode = AnswerMode.unknown,
    this.evidenceLevel = EvidenceLevel.none,
    this.confidence = 0,
    this.warnings = const [],
    this.needsHumanConfirmation = false,
  });

  final String id;
  final MessageSender sender;
  final String content;
  final DateTime timestamp;
  final List<KnowledgeSource> sources; // 引用来源
  final List<SuggestedAction> actions; // 建议操作
  final bool isStreaming; // 是否正在流式输出
  final String? streamError; // 生成错误

  // ===== RAG 元数据(对齐后端 ChatFinalMeta)=====
  /// 回答模式 — 用于在气泡上展示"依据来源"徽章。
  final AnswerMode answerMode;

  /// 证据等级 — 转换为用户可理解文案。
  final EvidenceLevel evidenceLevel;

  /// 整体置信度 0~1(后端 confidence 字段)。
  final double confidence;

  /// 后端返回的提示(如"已过期资料仅作历史参考")。
  final List<String> warnings;

  /// 是否需要人工确认(冲突资料 / 低置信度)。
  final bool needsHumanConfirmation;

  ChatMessage copyWith({
    String? id,
    MessageSender? sender,
    String? content,
    DateTime? timestamp,
    List<KnowledgeSource>? sources,
    List<SuggestedAction>? actions,
    bool? isStreaming,
    String? streamError,
    AnswerMode? answerMode,
    EvidenceLevel? evidenceLevel,
    double? confidence,
    List<String>? warnings,
    bool? needsHumanConfirmation,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      sender: sender ?? this.sender,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      sources: sources ?? this.sources,
      actions: actions ?? this.actions,
      isStreaming: isStreaming ?? this.isStreaming,
      streamError: streamError ?? this.streamError,
      answerMode: answerMode ?? this.answerMode,
      evidenceLevel: evidenceLevel ?? this.evidenceLevel,
      confidence: confidence ?? this.confidence,
      warnings: warnings ?? this.warnings,
      needsHumanConfirmation:
          needsHumanConfirmation ?? this.needsHumanConfirmation,
    );
  }

  @override
  List<Object?> get props => [
        id,
        sender,
        content,
        timestamp,
        sources,
        actions,
        isStreaming,
        streamError,
        answerMode,
        evidenceLevel,
        confidence,
        warnings,
        needsHumanConfirmation,
      ];
}

/// AI 导员回答模式 — 严格区分,避免将检索摘要描述为"大模型生成"。
enum AnswerMode {
  /// 仿真知识库 · 检索摘要(后端 mode=retrieval_summary + demo docs)
  demoRetrievalSummary,

  /// 用户知识库 · 检索摘要(后端 mode=retrieval_summary + user docs)
  userRetrievalSummary,

  /// 用户知识库 · LLM RAG(后端 mode=llm + user docs)
  userLlmRag,

  /// 混合知识库 · LLM RAG(后端 mode=llm + demo + user docs)
  hybridLlmRag,

  /// 无知识库依据(后端 mode=no_knowledge)
  noKnowledge,

  /// Mock 演示模式(AppConfig.useMockBackend)
  mockDemo,

  /// 未知(尚未收到 done 事件)
  unknown;

  /// 从后端 mode 字符串构造(结合是否 demo / 是否有 user docs)。
  static AnswerMode fromBackendMode({
    required String mode,
    required bool hasUserDocs,
    required bool hasDemoDocs,
    required bool isMock,
  }) {
    if (isMock) return AnswerMode.mockDemo;
    switch (mode) {
      case 'llm':
        return hasUserDocs && hasDemoDocs
            ? AnswerMode.hybridLlmRag
            : AnswerMode.userLlmRag;
      case 'retrieval_summary':
        return hasDemoDocs && !hasUserDocs
            ? AnswerMode.demoRetrievalSummary
            : AnswerMode.userRetrievalSummary;
      case 'no_knowledge':
        return AnswerMode.noKnowledge;
      default:
        return AnswerMode.unknown;
    }
  }

  /// 用户可读的简短徽章文案。
  String get badgeLabel {
    switch (this) {
      case AnswerMode.demoRetrievalSummary:
        return '仿真知识库 · 检索摘要';
      case AnswerMode.userRetrievalSummary:
        return '用户知识库 · 检索摘要';
      case AnswerMode.userLlmRag:
        return '用户知识库 · LLM RAG';
      case AnswerMode.hybridLlmRag:
        return '混合知识库 · LLM RAG';
      case AnswerMode.noKnowledge:
        return '无知识库依据';
      case AnswerMode.mockDemo:
        return 'Mock 演示模式';
      case AnswerMode.unknown:
        return '';
    }
  }
}

/// 证据等级 — 转换为用户可理解文案(满足"不能只显示小数分数"要求)。
enum EvidenceLevel {
  high,
  medium,
  conflict,
  none,
  unknown;

  static EvidenceLevel fromString(String? value) {
    switch (value) {
      case 'high':
        return EvidenceLevel.high;
      case 'medium':
        return EvidenceLevel.medium;
      case 'conflict':
        return EvidenceLevel.conflict;
      case 'none':
        return EvidenceLevel.none;
      default:
        return EvidenceLevel.unknown;
    }
  }

  /// 用户可理解文案(用于气泡下方显示)。
  String get userFacingLabel {
    switch (this) {
      case EvidenceLevel.high:
        return '依据较充分';
      case EvidenceLevel.medium:
        return '依据有限,建议核对原文';
      case EvidenceLevel.conflict:
        return '资料存在冲突,需要人工确认';
      case EvidenceLevel.none:
        return '当前知识库无法确认';
      case EvidenceLevel.unknown:
        return '';
    }
  }
}

/// AI 导员上下文中的"最近待办"条目(仅必要字段,对齐后端 CounselorRecentTask)。
///
/// 重要(对齐用户新要求):
/// - recent_tasks 现在只表示 PersonalTask(用户个人待办),不表示 Assignment。
/// - 教师作业只能通过 [CounselorContext.assignmentId] 传递,不得放入 recent_tasks。
/// - 后端会通过 PersonalTaskRepository 重新查询,客户端传入的
///   title/deadline/priority/status 一律视为 hint,不得作为事实使用。
/// - 未登录用户: recent_tasks 全部忽略 + warning。
/// - 已登录用户: 后端按 user_id 查询;不存在 / 越权 / 已软删除的任务
///   不得进入上下文,会被忽略并生成 warning。
/// - 前端发送的任务必须来自真实 ApiTaskRepository 缓存,
///   不得从 MockTaskRepository 取任务(USE_MOCK_BACKEND=false 时)。
class CounselorRecentTask extends Equatable {
  const CounselorRecentTask({
    required this.id,
    this.title,
    this.deadline,
    this.priority,
    this.status,
  });

  /// PersonalTask ID(必填,后端据此查询数据库)。
  final String id;

  /// 客户端 hint(后端不信任,仅作 debug 用途)。
  /// 后端会使用数据库权威 title 覆盖此字段。
  final String? title;

  /// 客户端 hint(后端不信任)。
  /// ISO8601 字符串或可读文案,后端会使用数据库权威 deadline 覆盖。
  final String? deadline;

  /// 客户端 hint(后端不信任)。
  /// 后端会使用数据库权威 priority 覆盖。
  final String? priority;

  /// 客户端 hint(后端不信任)。
  /// 后端会使用数据库权威 status 覆盖。
  final String? status;

  Map<String, dynamic> toJson() => {
        'id': id,
        if (title != null) 'title': title,
        if (deadline != null) 'deadline': deadline,
        if (priority != null) 'priority': priority,
        if (status != null) 'status': status,
      };

  @override
  List<Object?> get props => [id, title, deadline, priority, status];
}

/// AI 导员对话上下文 — 学生从课程/通知/任务进入时携带。
///
/// 用途(AGENTS.md §7 "AI 导员融合"):
/// - UI 顶部显示 "正在询问:高等数学 · 第 3 次作业"
/// - 后端按上下文优先返回:任务原文 → 课程资料 → 学校知识库
/// - 防止学生通过 AI 读取其他班级任务 / 教师草稿 / 其他学生提交
///
/// 重要(对齐要求 #2): 前端不得再仅把上下文编码进 conversation_id,
/// 必须通过 [toContextJson] 生成独立上下文字段放入 JSON Body 发送。
class CounselorContext extends Equatable {
  const CounselorContext({
    this.courseId,
    this.classId,
    this.assignmentId,
    this.announcementId,
    this.contextLabel,
    this.studySessionId,
    this.selfReport,
    this.expressionSignal,
    this.recentTasks = const [],
  });

  final String? courseId;
  final String? classId;
  final String? assignmentId;
  final String? announcementId;

  /// 用于 UI 顶部展示的简短标签(例如 "高等数学 · 第 3 次作业")。
  final String? contextLabel;

  /// 当前学习会话 ID(可选,用于学习陪伴场景)。
  final String? studySessionId;

  /// 用户自报状态(如"有些疲惫"),仅作个性化参考。
  final String? selfReport;

  /// 表情信号(预留,当前为空,留给 CNN 分支接入)。
  /// 后端当前实现会忽略此字段并生成 warning。
  final Map<String, dynamic>? expressionSignal;

  /// 最近待办条目(仅必要字段)。
  /// 后端会重新校验归属,越权条目会被忽略并生成 warning。
  final List<CounselorRecentTask> recentTasks;

  /// 是否有任意上下文(用于 UI 判断是否显示上下文条幅)。
  bool get hasContext =>
      courseId != null ||
      classId != null ||
      assignmentId != null ||
      announcementId != null ||
      studySessionId != null ||
      selfReport != null ||
      expressionSignal != null ||
      recentTasks.isNotEmpty;

  /// 生成发送给后端的 conversationId(仅作会话标识,不再嵌入业务上下文)。
  ///
  /// 旧实现把 course/class/assignment/announcement 编码进 conversation_id,
  /// 已弃用。新代码必须使用 [toContextJson] 把上下文作为独立字段发送。
  @Deprecated('使用 toContextJson() 把上下文作为独立 JSON 字段发送,'
      '不要编码进 conversation_id')
  String toConversationId() {
    final parts = <String>['conv_main'];
    if (courseId != null) parts.add('course:$courseId');
    if (classId != null) parts.add('class:$classId');
    if (assignmentId != null) parts.add('assignment:$assignmentId');
    if (announcementId != null) parts.add('announcement:$announcementId');
    return parts.join(':');
  }

  /// 生成发送给后端的独立上下文 JSON 字段(对齐后端 ChatRequest)。
  ///
  /// 调用方应把返回的 Map 合并到请求 Body 中,与 message/conversation_id/stream
  /// 并列发送。后端会校验当前用户是否有权访问这些资源,越权/不存在/已删除的
  /// 对象会被忽略并生成 warning。
  ///
  /// 注意(对齐要求 #5): recent_tasks 只发送必要字段
  /// (id/title/deadline/priority/status),不发送描述/附件/创建时间等。
  Map<String, dynamic> toContextJson() {
    final json = <String, dynamic>{};
    if (courseId != null) json['course_id'] = courseId;
    if (classId != null) json['class_id'] = classId;
    if (assignmentId != null) json['assignment_id'] = assignmentId;
    if (announcementId != null) json['announcement_id'] = announcementId;
    if (studySessionId != null) json['study_session_id'] = studySessionId;
    if (selfReport != null) json['self_report'] = selfReport;
    if (expressionSignal != null) json['expression_signal'] = expressionSignal;
    if (recentTasks.isNotEmpty) {
      json['recent_tasks'] = recentTasks.map((t) => t.toJson()).toList();
    }
    return json;
  }

  /// 从路由 extra(Map) 构造。
  factory CounselorContext.fromExtra(Object? extra) {
    if (extra is! Map) return const CounselorContext();
    final map = Map<String, dynamic>.from(extra);
    final recentTasksRaw = map['recent_tasks'];
    List<CounselorRecentTask> recentTasks = const [];
    if (recentTasksRaw is List) {
      recentTasks = recentTasksRaw
          .whereType<Map>()
          .map(
            (m) => CounselorRecentTask(
              id: m['id']?.toString() ?? '',
              title: m['title']?.toString() ?? '',
              deadline: m['deadline']?.toString(),
              priority: m['priority']?.toString(),
              status: m['status']?.toString(),
            ),
          )
          .where((t) => t.id.isNotEmpty)
          .toList(growable: false);
    }
    return CounselorContext(
      courseId: map['course_id'] as String?,
      classId: map['class_id'] as String?,
      assignmentId: map['assignment_id'] as String?,
      announcementId: map['announcement_id'] as String?,
      contextLabel: map['context_title'] as String?,
      studySessionId: map['study_session_id'] as String?,
      selfReport: map['self_report'] as String?,
      expressionSignal: map['expression_signal'] is Map
          ? Map<String, dynamic>.from(map['expression_signal'] as Map)
          : null,
      recentTasks: recentTasks,
    );
  }

  CounselorContext copyWith({
    String? courseId,
    String? classId,
    String? assignmentId,
    String? announcementId,
    String? contextLabel,
    String? studySessionId,
    String? selfReport,
    Map<String, dynamic>? expressionSignal,
    List<CounselorRecentTask>? recentTasks,
  }) {
    return CounselorContext(
      courseId: courseId ?? this.courseId,
      classId: classId ?? this.classId,
      assignmentId: assignmentId ?? this.assignmentId,
      announcementId: announcementId ?? this.announcementId,
      contextLabel: contextLabel ?? this.contextLabel,
      studySessionId: studySessionId ?? this.studySessionId,
      selfReport: selfReport ?? this.selfReport,
      expressionSignal: expressionSignal ?? this.expressionSignal,
      recentTasks: recentTasks ?? this.recentTasks,
    );
  }

  @override
  List<Object?> get props => [
        courseId,
        classId,
        assignmentId,
        announcementId,
        contextLabel,
        studySessionId,
        selfReport,
        expressionSignal,
        recentTasks,
      ];
}
