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

/// 单次学习会话记录。
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
    this.selfReportMood, // 用户主动填写的感受
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
  final String? selfReportMood; // 用户主动填写的学习感受

  int get durationMinutes => durationSeconds ~/ 60;

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
        // expressionSamples 不持久化(体积大,且表情实时性)
      };

  factory StudySession.fromJson(Map<String, dynamic> json) => StudySession(
        id: json['id'] as String,
        startedAt: DateTime.parse(json['startedAt'] as String),
        endedAt: json['endedAt'] == null
            ? null
            : DateTime.parse(json['endedAt'] as String),
        durationSeconds: json['durationSeconds'] as int,
        state: StudyState.values.byName(json['state'] as String),
        goalId: json['goalId'] as String?,
        taskId: json['taskId'] as String?,
        focusRatio: (json['focusRatio'] as num?)?.toDouble() ?? 0,
        selfReportMood: json['selfReportMood'] as String?,
      );

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
