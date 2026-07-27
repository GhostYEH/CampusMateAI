import 'package:equatable/equatable.dart';
import 'notice.dart';

/// 任务类别。
enum TaskCategory {
  study('学习'),
  courseSelection('选课'),
  scholarship('奖学金'),
  comprehensiveEval('综合测评'),
  practice('实践学分'),
  activity('活动报名'),
  material('材料提交'),
  daily('日常'),
  other('其他');

  const TaskCategory(this.displayName);
  final String displayName;

  static TaskCategory fromString(String? value) {
    if (value == null) return TaskCategory.other;
    final v = value.toLowerCase();
    for (final c in TaskCategory.values) {
      if (c.name == v) return c;
    }
    return TaskCategory.other;
  }
}

/// 任务优先级。
enum TaskPriority {
  high('高', 3),
  medium('中', 2),
  low('低', 1);

  const TaskPriority(this.displayName, this.weight);
  final String displayName;
  final int weight;

  static TaskPriority fromString(String? value) {
    if (value == null) return TaskPriority.medium;
    final v = value.toLowerCase();
    switch (v) {
      case 'high':
      case '高':
        return TaskPriority.high;
      case 'low':
      case '低':
        return TaskPriority.low;
      default:
        return TaskPriority.medium;
    }
  }
}

/// 任务来源类型。
enum TaskSource {
  manual('手动创建'),
  noticeExtraction('通知整理'),
  counselor('AI导员'),
  import('导入');

  const TaskSource(this.displayName);
  final String displayName;
}

/// 个人待办任务。
///
/// 字段对齐后端 `personal_tasks` 表(见 backend/app/database/sqlite_db.py):
/// - [sourceText] 保留原通知文本,确保后端可追溯(对齐后端要求 #4)
/// - [sourceName] 通知来源(如 "教务处")
/// - [targetStudents] 通知面向对象(如 "2024级各班")
/// - [submissionMethod] 提交方式
/// - [reminderMinutes] 提前提醒分钟数(对齐后端 `reminder_minutes`)
///
/// 本地提醒调度仍使用 [reminderEnabled] + [reminderAt](绝对时间),
/// 由 [ApiTaskRepository] 在读写后端时与 [reminderMinutes] 互相转换。
class Task extends Equatable {
  const Task({
    required this.id,
    required this.title,
    required this.category,
    required this.priority,
    required this.createdAt,
    required this.source,
    this.description,
    this.deadline,
    this.materials = const [],
    this.location,
    this.completed = false,
    this.completedAt,
    this.deleted = false,
    this.reminderEnabled = false,
    this.reminderAt,
    this.sourceNoticeId,
    this.sourceText,
    this.sourceName,
    this.targetStudents,
    this.submissionMethod,
    this.reminderMinutes,
  });

  final String id;
  final String title;
  final TaskCategory category;
  final TaskPriority priority;
  final DateTime createdAt;
  final TaskSource source;
  final String? description;
  final DateTime? deadline;
  final List<TaskMaterial> materials;
  final String? location;
  final bool completed;
  final DateTime? completedAt;
  final bool deleted; // 软删除(支持撤销)
  final bool reminderEnabled;
  final DateTime? reminderAt;
  final String? sourceNoticeId; // 关联通知ID
  // ===== 后端 personal_tasks 表对齐字段(用于原文追溯与同步)=====
  final String? sourceText; // 原通知全文(确保后端可追溯)
  final String? sourceName; // 通知来源(如 "教务处")
  final String? targetStudents; // 通知面向对象(如 "2024级各班")
  final String? submissionMethod; // 提交方式
  final int? reminderMinutes; // 提前提醒分钟数(对齐后端)

  /// 是否今日截止或逾期(用于"即将截止"判断)。
  bool get isOverdue =>
      !completed && deadline != null && deadline!.isBefore(DateTime.now());

  /// 距离截止的剩余时长(负值表示已逾期)。
  Duration? get remaining => deadline?.difference(DateTime.now());

  /// 材料准备进度 0~1。
  double get materialProgress {
    if (materials.isEmpty) return 1;
    final required = materials.where((m) => m.required).toList();
    if (required.isEmpty) return 1;
    final done = required.where((m) => m.done).length;
    return done / required.length;
  }

  Task copyWith({
    String? id,
    String? title,
    TaskCategory? category,
    TaskPriority? priority,
    DateTime? createdAt,
    TaskSource? source,
    String? description,
    DateTime? deadline,
    List<TaskMaterial>? materials,
    String? location,
    bool? completed,
    DateTime? completedAt,
    bool? deleted,
    bool? reminderEnabled,
    DateTime? reminderAt,
    String? sourceNoticeId,
    String? sourceText,
    String? sourceName,
    String? targetStudents,
    String? submissionMethod,
    int? reminderMinutes,
  }) {
    return Task(
      id: id ?? this.id,
      title: title ?? this.title,
      category: category ?? this.category,
      priority: priority ?? this.priority,
      createdAt: createdAt ?? this.createdAt,
      source: source ?? this.source,
      description: description ?? this.description,
      deadline: deadline ?? this.deadline,
      materials: materials ?? this.materials,
      location: location ?? this.location,
      completed: completed ?? this.completed,
      completedAt: completedAt ?? this.completedAt,
      deleted: deleted ?? this.deleted,
      reminderEnabled: reminderEnabled ?? this.reminderEnabled,
      reminderAt: reminderAt ?? this.reminderAt,
      sourceNoticeId: sourceNoticeId ?? this.sourceNoticeId,
      sourceText: sourceText ?? this.sourceText,
      sourceName: sourceName ?? this.sourceName,
      targetStudents: targetStudents ?? this.targetStudents,
      submissionMethod: submissionMethod ?? this.submissionMethod,
      reminderMinutes: reminderMinutes ?? this.reminderMinutes,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'category': category.name,
        'priority': priority.name,
        'createdAt': createdAt.toIso8601String(),
        'source': source.name,
        'description': description,
        'deadline': deadline?.toIso8601String(),
        'materials': [for (final m in materials) m.toJson()],
        'location': location,
        'completed': completed,
        'completedAt': completedAt?.toIso8601String(),
        'deleted': deleted,
        'reminderEnabled': reminderEnabled,
        'reminderAt': reminderAt?.toIso8601String(),
        'sourceNoticeId': sourceNoticeId,
        'sourceText': sourceText,
        'sourceName': sourceName,
        'targetStudents': targetStudents,
        'submissionMethod': submissionMethod,
        'reminderMinutes': reminderMinutes,
      };

  factory Task.fromJson(Map<String, dynamic> json) => Task(
        id: json['id'] as String,
        title: json['title'] as String,
        category: TaskCategory.fromString(json['category'] as String?),
        priority: TaskPriority.fromString(json['priority'] as String?),
        createdAt: DateTime.tryParse(json['createdAt'] as String? ?? '') ??
            DateTime.now(),
        source: TaskSource.values.firstWhere(
          (s) => s.name == (json['source'] as String? ?? 'manual'),
          orElse: () => TaskSource.manual,
        ),
        description: json['description'] as String?,
        deadline: (json['deadline'] as String?)?.let(DateTime.tryParse),
        materials: ((json['materials'] as List?) ?? [])
            .map((e) => TaskMaterial.fromJson(e as Map<String, dynamic>))
            .toList(),
        location: json['location'] as String?,
        completed: json['completed'] as bool? ?? false,
        completedAt: (json['completedAt'] as String?)?.let(DateTime.tryParse),
        deleted: json['deleted'] as bool? ?? false,
        reminderEnabled: json['reminderEnabled'] as bool? ?? false,
        reminderAt: (json['reminderAt'] as String?)?.let(DateTime.tryParse),
        sourceNoticeId: json['sourceNoticeId'] as String?,
        sourceText: json['sourceText'] as String?,
        sourceName: json['sourceName'] as String?,
        targetStudents: json['targetStudents'] as String?,
        submissionMethod: json['submissionMethod'] as String?,
        reminderMinutes: (json['reminderMinutes'] as num?)?.toInt(),
      );

  @override
  List<Object?> get props => [
        id,
        title,
        category,
        priority,
        createdAt,
        source,
        description,
        deadline,
        materials,
        location,
        completed,
        completedAt,
        deleted,
        reminderEnabled,
        reminderAt,
        sourceNoticeId,
        sourceText,
        sourceName,
        targetStudents,
        submissionMethod,
        reminderMinutes,
      ];
}

/// 任务提醒。
class Reminder extends Equatable {
  const Reminder({
    required this.id,
    required this.taskId,
    required this.scheduledAt,
    this.title,
    this.body,
    this.fired = false,
  });

  final String id;
  final String taskId;
  final DateTime scheduledAt;
  final String? title;
  final String? body;
  final bool fired;

  Reminder copyWith({
    String? id,
    String? taskId,
    DateTime? scheduledAt,
    String? title,
    String? body,
    bool? fired,
  }) {
    return Reminder(
      id: id ?? this.id,
      taskId: taskId ?? this.taskId,
      scheduledAt: scheduledAt ?? this.scheduledAt,
      title: title ?? this.title,
      body: body ?? this.body,
      fired: fired ?? this.fired,
    );
  }

  @override
  List<Object?> get props => [id, taskId, scheduledAt, title, body, fired];
}

/// Nullable String -> T 扩展(简化 JSON 解析)
extension _StringLet on String? {
  T? let<T>(T? Function(String) f) => this == null ? null : f(this!);
}
