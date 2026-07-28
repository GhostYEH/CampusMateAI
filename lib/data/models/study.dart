import 'package:equatable/equatable.dart';
import 'expression.dart';

/// 学习状态。
///
/// 疲劳(fatigued)状态≠FER2013表情类别,需结合学习时长、用户感受、
/// 后续闭眼/眨眼/头部姿态信号综合判断。详见 AGENTS.md §3。
enum StudyState {
  idle('未开始'),
  focusing('专注中'),
  distracted('可能分心'),
  fatigued('可能疲劳'),
  paused('已暂停'),
  resting('休息中'),
  completed('已完成');

  const StudyState(this.displayName);
  final String displayName;
}

/// 学习会话状态(对齐后端 study_sessions.status)。
///
/// 后端只承认三种状态: active | paused | completed。
/// [StudyState] 是 UI 派生状态(包含 focusing/distracted/fatigued 等表情辅助判断),
/// [StudySessionStatus] 是后端权威状态。
enum StudySessionStatus {
  active,
  paused,
  completed,
  ;

  static StudySessionStatus fromString(String? raw) {
    switch (raw) {
      case 'active':
        return StudySessionStatus.active;
      case 'paused':
        return StudySessionStatus.paused;
      case 'completed':
        return StudySessionStatus.completed;
      default:
        return StudySessionStatus.active;
    }
  }

  String get wireName {
    switch (this) {
      case StudySessionStatus.active:
        return 'active';
      case StudySessionStatus.paused:
        return 'paused';
      case StudySessionStatus.completed:
        return 'completed';
    }
  }
}

/// 学习目标。
class StudyGoal extends Equatable {
  const StudyGoal({
    required this.id,
    required this.title,
    required this.targetMinutes,
    this.completed = false,
  });

  final String id;
  final String title;
  final int targetMinutes; // 目标学习分钟数
  final bool completed;

  StudyGoal copyWith({
    String? id,
    String? title,
    int? targetMinutes,
    bool? completed,
  }) {
    return StudyGoal(
      id: id ?? this.id,
      title: title ?? this.title,
      targetMinutes: targetMinutes ?? this.targetMinutes,
      completed: completed ?? this.completed,
    );
  }

  @override
  List<Object?> get props => [id, title, targetMinutes, completed];
}

/// 学习会话中的休息记录(对齐后端 study_breaks 表)。
///
/// 一次 pause → resume 之间会产生一条休息记录。
/// 会话被 finish 时,未关闭的休息记录由后端自动关闭。
class StudyBreak extends Equatable {
  const StudyBreak({
    required this.id,
    required this.sessionId,
    required this.startedAt,
    this.endedAt,
    this.reason,
    this.createdAt,
  });

  final String id;
  final String sessionId;
  final DateTime startedAt;
  final DateTime? endedAt;
  final String? reason;
  final DateTime? createdAt;

  /// 该次休息时长(若已结束)。
  Duration? get duration {
    final end = endedAt;
    if (end == null) return null;
    return end.difference(startedAt);
  }

  /// 是否仍在进行中(未结束)。
  bool get isOpen => endedAt == null;

  StudyBreak copyWith({
    String? id,
    String? sessionId,
    DateTime? startedAt,
    DateTime? endedAt,
    String? reason,
    DateTime? createdAt,
  }) {
    return StudyBreak(
      id: id ?? this.id,
      sessionId: sessionId ?? this.sessionId,
      startedAt: startedAt ?? this.startedAt,
      endedAt: endedAt ?? this.endedAt,
      reason: reason ?? this.reason,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'session_id': sessionId,
        'started_at': startedAt.toIso8601String(),
        'ended_at': endedAt?.toIso8601String(),
        'reason': reason,
        'created_at': createdAt?.toIso8601String(),
      };

  factory StudyBreak.fromJson(Map<String, dynamic> json) => StudyBreak(
        id: json['id'] as String,
        sessionId: json['session_id'] as String,
        startedAt: DateTime.parse(json['started_at'] as String),
        endedAt: json['ended_at'] == null
            ? null
            : DateTime.parse(json['ended_at'] as String),
        reason: json['reason'] as String?,
        createdAt: json['created_at'] == null
            ? null
            : DateTime.parse(json['created_at'] as String),
      );

  @override
  List<Object?> get props =>
      [id, sessionId, startedAt, endedAt, reason, createdAt];
}

/// 单次学习会话记录。
///
/// 对齐后端 `study_sessions` 表:
/// - [status] 是后端权威状态机(active|paused|completed)。
/// - [state] 是 UI 派生状态(基于表情辅助判断)。
/// - [selfReport] / [selfReportTags] 仅由用户主动输入,不根据表情自动填写。
/// - [expressionSignal] 为 CNN 分支预留字段(本轮不实现 CNN)。
class StudySession extends Equatable {
  const StudySession({
    required this.id,
    required this.startedAt,
    required this.durationSeconds,
    required this.state,
    this.goalId,
    this.taskId,
    this.expressionSamples = const [],
    this.focusRatio = 0,
    this.endedAt,
    this.selfReportMood, // 用户主动填写的感受(向后兼容)
    this.status = StudySessionStatus.active,
    this.pausedAt,
    this.pauseSeconds = 0,
    this.selfReport,
    this.selfReportTags = const [],
    this.expressionSignal,
    this.breaks = const [],
    this.createdAt,
    this.updatedAt,
  });

  final String id;
  final DateTime startedAt;
  final DateTime? endedAt;
  final int durationSeconds; // 实际学习秒数(扣除暂停)
  final StudyState state;
  final String? goalId;
  final String? taskId; // 关联任务
  final List<ExpressionResult> expressionSamples;
  final double focusRatio; // 专注占比 0~1
  final String? selfReportMood; // 用户主动填写的学习感受(向后兼容字段)

  // ===== 后端化扩展字段 =====
  /// 后端权威状态(active|paused|completed)。
  final StudySessionStatus status;

  /// 最近一次暂停时间(后端字段 paused_at)。
  final DateTime? pausedAt;

  /// 累计暂停秒数(由后端在 resume/finish 时累加)。
  final int pauseSeconds;

  /// 用户主动填写的文字感受(对齐后端 self_report)。
  /// 与 [selfReportMood] 等价,前端展示优先使用此字段。
  final String? selfReport;

  /// 用户主动填写的感受标签(对齐后端 self_report_tags)。
  final List<String> selfReportTags;

  /// CNN 表情信号预留字段(本轮不实现 CNN,仅透传存储)。
  /// 未来 CNN 分支可在此存放多帧表情摘要,供 AI 导员参考。
  final Map<String, dynamic>? expressionSignal;

  /// 休息记录列表(对齐后端 study_breaks)。
  final List<StudyBreak> breaks;

  /// 后端记录创建时间。
  final DateTime? createdAt;

  /// 后端记录最近更新时间。
  final DateTime? updatedAt;

  int get durationMinutes => durationSeconds ~/ 60;

  int get pauseMinutes => pauseSeconds ~/ 60;

  /// 是否未结束(active 或 paused)。
  bool get isOpen =>
      status == StudySessionStatus.active ||
      status == StudySessionStatus.paused;

  StudySession copyWith({
    String? id,
    DateTime? startedAt,
    DateTime? endedAt,
    int? durationSeconds,
    StudyState? state,
    String? goalId,
    String? taskId,
    List<ExpressionResult>? expressionSamples,
    double? focusRatio,
    String? selfReportMood,
    StudySessionStatus? status,
    DateTime? pausedAt,
    int? pauseSeconds,
    String? selfReport,
    List<String>? selfReportTags,
    Map<String, dynamic>? expressionSignal,
    List<StudyBreak>? breaks,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return StudySession(
      id: id ?? this.id,
      startedAt: startedAt ?? this.startedAt,
      endedAt: endedAt ?? this.endedAt,
      durationSeconds: durationSeconds ?? this.durationSeconds,
      state: state ?? this.state,
      goalId: goalId ?? this.goalId,
      taskId: taskId ?? this.taskId,
      expressionSamples: expressionSamples ?? this.expressionSamples,
      focusRatio: focusRatio ?? this.focusRatio,
      selfReportMood: selfReportMood ?? this.selfReportMood,
      status: status ?? this.status,
      pausedAt: pausedAt ?? this.pausedAt,
      pauseSeconds: pauseSeconds ?? this.pauseSeconds,
      selfReport: selfReport ?? this.selfReport,
      selfReportTags: selfReportTags ?? this.selfReportTags,
      expressionSignal: expressionSignal ?? this.expressionSignal,
      breaks: breaks ?? this.breaks,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'startedAt': startedAt.toIso8601String(),
        'endedAt': endedAt?.toIso8601String(),
        'durationSeconds': durationSeconds,
        'state': state.name,
        'goalId': goalId,
        'taskId': taskId,
        'focusRatio': focusRatio,
        'selfReportMood': selfReportMood,
        'status': status.wireName,
        'pausedAt': pausedAt?.toIso8601String(),
        'pauseSeconds': pauseSeconds,
        'selfReport': selfReport,
        'selfReportTags': selfReportTags,
        'expressionSignal': expressionSignal,
        'breaks': breaks.map((b) => b.toJson()).toList(),
        'createdAt': createdAt?.toIso8601String(),
        'updatedAt': updatedAt?.toIso8601String(),
        // expressionSamples 不持久化(体积大,且表情实时性)
      };

  factory StudySession.fromJson(Map<String, dynamic> json) {
    final status = StudySessionStatus.fromString(
      json['status'] as String?,
    );
    // 派生 UI 状态: completed → completed; paused → paused; 否则 focusing
    final StudyState derivedState;
    switch (status) {
      case StudySessionStatus.completed:
        derivedState = StudyState.completed;
        break;
      case StudySessionStatus.paused:
        derivedState = StudyState.paused;
        break;
      case StudySessionStatus.active:
        derivedState = StudyState.focusing;
        break;
    }
    final stateRaw = json['state'] as String?;
    final state = stateRaw != null && stateRaw.isNotEmpty
        ? StudyState.values.byName(stateRaw)
        : derivedState;
    final breaksRaw = json['breaks'] as List?;
    final breaks = breaksRaw == null
        ? const <StudyBreak>[]
        : breaksRaw
            .whereType<Map<String, dynamic>>()
            .map(StudyBreak.fromJson)
            .toList(growable: false);
    final signalRaw = json['expressionSignal'] ?? json['expression_signal'];
    final Map<String, dynamic>? signal = signalRaw is Map<String, dynamic>
        ? Map<String, dynamic>.from(signalRaw)
        : null;
    return StudySession(
      id: json['id'] as String,
      startedAt: DateTime.parse(
        (json['startedAt'] ?? json['started_at']) as String,
      ),
      endedAt: _parseOptionalDate(json['endedAt'] ?? json['ended_at']),
      durationSeconds: (json['durationSeconds'] as num?)?.toInt() ??
          (json['duration_seconds'] as num?)?.toInt() ??
          0,
      state: state,
      goalId: (json['goalId'] ?? json['goal'] ?? json['goal_id']) as String?,
      taskId: (json['taskId'] ?? json['related_task_id'] ?? json['taskId'])
          as String?,
      focusRatio: (json['focusRatio'] as num?)?.toDouble() ?? 0,
      selfReportMood:
          (json['selfReportMood'] ?? json['self_report']) as String?,
      status: status,
      pausedAt: _parseOptionalDate(json['pausedAt'] ?? json['paused_at']),
      pauseSeconds: (json['pauseSeconds'] as num?)?.toInt() ??
          (json['pause_seconds'] as num?)?.toInt() ??
          0,
      selfReport: (json['selfReport'] ?? json['self_report']) as String?,
      selfReportTags:
          _parseTagsList(json['selfReportTags'] ?? json['self_report_tags']),
      expressionSignal: signal,
      breaks: breaks,
      createdAt: _parseOptionalDate(json['createdAt'] ?? json['created_at']),
      updatedAt: _parseOptionalDate(json['updatedAt'] ?? json['updated_at']),
    );
  }

  static DateTime? _parseOptionalDate(Object? raw) {
    if (raw == null) return null;
    if (raw is String && raw.isEmpty) return null;
    try {
      return DateTime.parse(raw as String);
    } catch (_) {
      return null;
    }
  }

  static List<String> _parseTagsList(Object? raw) {
    if (raw is List) {
      return raw.whereType<String>().toList(growable: false);
    }
    return const [];
  }

  @override
  List<Object?> get props => [
        id,
        startedAt,
        endedAt,
        durationSeconds,
        state,
        goalId,
        taskId,
        expressionSamples,
        focusRatio,
        selfReportMood,
        status,
        pausedAt,
        pauseSeconds,
        selfReport,
        selfReportTags,
        expressionSignal,
        breaks,
        createdAt,
        updatedAt,
      ];
}

/// AI 导员陪伴建议(基于任务 + 对话 + 表情综合生成)。
///
/// 文案必须遵循科学边界:不诊断、不判定心理状态,仅日常辅助。
class CompanionSuggestion extends Equatable {
  const CompanionSuggestion({
    required this.id,
    required this.title,
    required this.message,
    required this.kind,
    this.actionLabel,
    this.actionPayload,
    this.createdAt,
  });

  final String id;
  final String title;
  final String message; // 谨慎表达的陪伴文案
  final CompanionSuggestionKind kind;
  final String? actionLabel;
  final String? actionPayload;
  final DateTime? createdAt;

  @override
  List<Object?> get props =>
      [id, title, message, kind, actionLabel, actionPayload, createdAt];
}

enum CompanionSuggestionKind {
  rest, // 休息提醒
  refocus, // 重新专注
  taskOrganize, // 任务整理
  emotionCare, // 情绪关怀(谨慎)
  encouragement, // 鼓励
  lowConfidence, // 低置信度,不触发安慰
}

/// ===== 任务拆解 =====

/// 任务拆解模式(对齐后端 TaskBreakdownResponse.mode)。
enum TaskBreakdownMode {
  /// LLM 生成
  llm,

  /// 规则化降级(无 LLM 或 LLM 失败)
  ruleFallback;

  static TaskBreakdownMode fromString(String raw) {
    if (raw == 'llm') return TaskBreakdownMode.llm;
    return TaskBreakdownMode.ruleFallback;
  }

  String get wireName =>
      this == TaskBreakdownMode.llm ? 'llm' : 'rule_fallback';

  String get displayName => this == TaskBreakdownMode.llm ? 'AI 生成' : '规则建议';
}

/// 任务拆解请求(对齐后端 TaskBreakdownRequest)。
class TaskBreakdownRequest extends Equatable {
  const TaskBreakdownRequest({
    this.taskId,
    this.goal,
  });

  /// 关联任务 ID(后端 assignment ID 或本地待办 ID,后端会校验权限)。
  final String? taskId;

  /// 自由文本目标。
  final String? goal;

  bool get isEmpty =>
      (taskId == null || taskId!.isEmpty) &&
      (goal == null || goal!.trim().isEmpty);

  Map<String, dynamic> toJson() => {
        if (taskId != null) 'task_id': taskId,
        if (goal != null) 'goal': goal,
      };

  @override
  List<Object?> get props => [taskId, goal];
}

/// 任务拆解步骤(对齐后端 TaskBreakdownStep)。
class TaskBreakdownStep extends Equatable {
  const TaskBreakdownStep({
    required this.stepNumber,
    required this.title,
    required this.description,
    required this.estimatedMinutes,
    required this.completionCriteria,
    this.dependencies = const [],
    this.isPolicyStep = false,
    this.knowledgeSource,
  });

  /// 步骤编号(从 1 开始)。
  final int stepNumber;

  /// 步骤标题。
  final String title;

  /// 步骤描述(可观察、可执行)。
  final String description;

  /// 预计耗时(分钟)。
  final int estimatedMinutes;

  /// 依赖的步骤编号列表(必须先完成)。
  final List<int> dependencies;

  /// 完成判定标准(可观测、可检验)。
  final String completionCriteria;

  /// 是否为校园政策相关步骤(必须依赖知识库)。
  final bool isPolicyStep;

  /// 政策步骤引用的知识库来源标题(可空)。
  final String? knowledgeSource;

  TaskBreakdownStep copyWith({
    int? stepNumber,
    String? title,
    String? description,
    int? estimatedMinutes,
    List<int>? dependencies,
    String? completionCriteria,
    bool? isPolicyStep,
    String? knowledgeSource,
  }) {
    return TaskBreakdownStep(
      stepNumber: stepNumber ?? this.stepNumber,
      title: title ?? this.title,
      description: description ?? this.description,
      estimatedMinutes: estimatedMinutes ?? this.estimatedMinutes,
      dependencies: dependencies ?? this.dependencies,
      completionCriteria: completionCriteria ?? this.completionCriteria,
      isPolicyStep: isPolicyStep ?? this.isPolicyStep,
      knowledgeSource: knowledgeSource ?? this.knowledgeSource,
    );
  }

  factory TaskBreakdownStep.fromJson(Map<String, dynamic> json) =>
      TaskBreakdownStep(
        stepNumber: (json['step_number'] as num).toInt(),
        title: json['title'] as String,
        description: json['description'] as String,
        estimatedMinutes: (json['estimated_minutes'] as num?)?.toInt() ?? 30,
        dependencies: ((json['dependencies'] as List?) ?? const [])
            .map((d) => (d is num ? d.toInt() : int.parse(d.toString())))
            .toList(growable: false),
        completionCriteria:
            json['completion_criteria'] as String? ?? '完成 ${json['title']}',
        isPolicyStep: (json['is_policy_step'] as bool?) ?? false,
        knowledgeSource: json['knowledge_source'] as String?,
      );

  @override
  List<Object?> get props => [
        stepNumber,
        title,
        description,
        estimatedMinutes,
        dependencies,
        completionCriteria,
        isPolicyStep,
        knowledgeSource,
      ];
}

/// 任务拆解响应(对齐后端 TaskBreakdownResponse)。
class TaskBreakdownResponse extends Equatable {
  const TaskBreakdownResponse({
    required this.mode,
    required this.steps,
    required this.goal,
    this.relatedTaskId,
    this.relatedTaskTitle,
    this.warnings = const [],
  });

  /// 拆解模式: llm | rule_fallback。
  final TaskBreakdownMode mode;

  /// 结构化步骤列表。
  final List<TaskBreakdownStep> steps;

  /// 实际用于拆解的目标文本。
  final String goal;

  /// 关联任务 ID(若请求中提供且解析成功)。
  final String? relatedTaskId;

  /// 关联任务标题。
  final String? relatedTaskTitle;

  /// 警告信息(知识库未就绪 / LLM 失败 / 任务无权访问等)。
  final List<String> warnings;

  /// 总预计分钟数。
  int get totalEstimatedMinutes =>
      steps.fold(0, (sum, s) => sum + s.estimatedMinutes);

  factory TaskBreakdownResponse.fromJson(Map<String, dynamic> json) {
    final stepsRaw = (json['steps'] as List?) ?? const [];
    return TaskBreakdownResponse(
      mode: TaskBreakdownMode.fromString(
        json['mode'] as String? ?? 'rule_fallback',
      ),
      steps: stepsRaw
          .whereType<Map<String, dynamic>>()
          .map(TaskBreakdownStep.fromJson)
          .toList(growable: false),
      goal: json['goal'] as String? ?? '',
      relatedTaskId: json['related_task_id'] as String?,
      relatedTaskTitle: json['related_task_title'] as String?,
      warnings: ((json['warnings'] as List?) ?? const [])
          .map((w) => w.toString())
          .toList(growable: false),
    );
  }

  @override
  List<Object?> get props => [
        mode,
        steps,
        goal,
        relatedTaskId,
        relatedTaskTitle,
        warnings,
      ];
}
