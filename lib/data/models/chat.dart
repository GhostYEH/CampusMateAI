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

/// AI 导员对话上下文 — 学生从课程/通知/任务进入时携带。
///
/// 用途(AGENTS.md §7 "AI 导员融合"):
/// - UI 顶部显示 "正在询问:高等数学 · 第 3 次作业"
/// - 后端按上下文优先返回:任务原文 → 课程资料 → 学校知识库
/// - 防止学生通过 AI 读取其他班级任务 / 教师草稿 / 其他学生提交
class CounselorContext extends Equatable {
  const CounselorContext({
    this.courseId,
    this.classId,
    this.assignmentId,
    this.announcementId,
    this.contextLabel,
  });

  final String? courseId;
  final String? classId;
  final String? assignmentId;
  final String? announcementId;

  /// 用于 UI 顶部展示的简短标签(例如 "高等数学 · 第 3 次作业")。
  final String? contextLabel;

  /// 是否有任意上下文。
  bool get hasContext =>
      courseId != null ||
      classId != null ||
      assignmentId != null ||
      announcementId != null;

  /// 生成发送给后端的 conversationId(嵌入上下文,后端可解析)。
  ///
  /// 格式: `conv_main:course_xxx:class_yyy:assignment_zzz:announcement_www`
  /// 没有 context 时退化为 `conv_main`。
  String toConversationId() {
    final parts = <String>['conv_main'];
    if (courseId != null) parts.add('course:$courseId');
    if (classId != null) parts.add('class:$classId');
    if (assignmentId != null) parts.add('assignment:$assignmentId');
    if (announcementId != null) parts.add('announcement:$announcementId');
    return parts.join(':');
  }

  /// 从路由 extra(Map) 构造。
  factory CounselorContext.fromExtra(Object? extra) {
    if (extra is! Map) return const CounselorContext();
    final map = Map<String, dynamic>.from(extra);
    return CounselorContext(
      courseId: map['course_id'] as String?,
      classId: map['class_id'] as String?,
      assignmentId: map['assignment_id'] as String?,
      announcementId: map['announcement_id'] as String?,
      contextLabel: map['context_title'] as String?,
    );
  }

  @override
  List<Object?> get props =>
      [courseId, classId, assignmentId, announcementId, contextLabel];
}
