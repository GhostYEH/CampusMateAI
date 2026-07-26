import 'package:equatable/equatable.dart';

/// 校园通知重要程度。
enum NoticeImportance {
  urgent('紧急', 3),
  important('重要', 2),
  normal('普通', 1),
  unknown('待确认', 0);

  const NoticeImportance(this.displayName, this.weight);
  final String displayName;
  final int weight;

  static NoticeImportance fromString(String? value) {
    if (value == null) return NoticeImportance.unknown;
    final v = value.toLowerCase();
    switch (v) {
      case 'urgent':
      case '紧急':
        return NoticeImportance.urgent;
      case 'important':
      case '重要':
        return NoticeImportance.important;
      case 'normal':
      case '普通':
      case '一般':
        return NoticeImportance.normal;
      default:
        return NoticeImportance.unknown;
    }
  }
}

/// 任务所需材料项。
class TaskMaterial extends Equatable {
  const TaskMaterial({
    required this.id,
    required this.name,
    this.required = true,
    this.done = false,
    this.note,
  });

  final String id;
  final String name; // 材料名称
  final bool required; // 是否必需
  final bool done; // 是否已准备
  final String? note; // 备注

  TaskMaterial copyWith({
    String? id,
    String? name,
    bool? required,
    bool? done,
    String? note,
  }) {
    return TaskMaterial(
      id: id ?? this.id,
      name: name ?? this.name,
      required: required ?? this.required,
      done: done ?? this.done,
      note: note ?? this.note,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'required': required,
        'done': done,
        'note': note,
      };

  factory TaskMaterial.fromJson(Map<String, dynamic> json) => TaskMaterial(
        id: json['id'] as String,
        name: json['name'] as String,
        required: json['required'] as bool? ?? true,
        done: json['done'] as bool? ?? false,
        note: json['note'] as String?,
      );

  @override
  List<Object?> get props => [id, name, required, done, note];
}

/// 校园通知原文。
class CampusNotice extends Equatable {
  const CampusNotice({
    required this.id,
    required this.title,
    required this.source, // 发布单位
    required this.publishedAt,
    required this.content,
    this.importance = NoticeImportance.normal,
    this.read = false,
    this.tags = const [],
  });

  final String id;
  final String title;
  final String source;
  final DateTime publishedAt;
  final String content;
  final NoticeImportance importance;
  final bool read;
  final List<String> tags;

  CampusNotice copyWith({
    String? id,
    String? title,
    String? source,
    DateTime? publishedAt,
    String? content,
    NoticeImportance? importance,
    bool? read,
    List<String>? tags,
  }) {
    return CampusNotice(
      id: id ?? this.id,
      title: title ?? this.title,
      source: source ?? this.source,
      publishedAt: publishedAt ?? this.publishedAt,
      content: content ?? this.content,
      importance: importance ?? this.importance,
      read: read ?? this.read,
      tags: tags ?? this.tags,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'source': source,
        'publishedAt': publishedAt.toIso8601String(),
        'content': content,
        'importance': importance.name,
        'read': read,
        'tags': tags,
      };

  factory CampusNotice.fromJson(Map<String, dynamic> json) => CampusNotice(
        id: json['id'] as String,
        title: json['title'] as String,
        source: json['source'] as String,
        publishedAt: DateTime.parse(json['publishedAt'] as String),
        content: json['content'] as String,
        importance: NoticeImportance.values
            .byName(json['importance'] as String? ?? 'normal'),
        read: json['read'] as bool? ?? false,
        tags: (json['tags'] as List?)?.cast<String>() ?? const [],
      );

  @override
  List<Object?> get props =>
      [id, title, source, publishedAt, content, importance, read, tags];
}

/// 从通知中智能提取出的结构化信息。
///
/// 该结构是 [NotificationExtractionService] 的输出,
/// 字段允许为空(未提取到),用户可手动补全后再保存为待办。
///
/// [warnings] 表示"需要人工确认"的温和提示(年份缺失/对象不明等),
/// 与错误无关 — UI 应以暖色提示形式展示,而非红色错误。
/// [extractorMode] 标注提取来源: mock|llm|rules。
class ExtractedNotice extends Equatable {
  const ExtractedNotice({
    required this.taskName,
    this.targetAudience,
    this.deadline,
    this.materials = const [],
    this.submitMethod,
    this.location,
    this.sourceText,
    this.importance = NoticeImportance.unknown,
    this.confidence = 0,
    this.extractedSteps = const [],
    this.warnings = const [],
    this.extractorMode = 'mock',
  });

  final String taskName; // 任务名称
  final String? targetAudience; // 面向对象
  final DateTime? deadline; // 截止时间
  final List<TaskMaterial> materials; // 所需材料
  final String? submitMethod; // 提交方式
  final String? location; // 办理地点
  final String? sourceText; // 原文来源
  final NoticeImportance importance; // 重要程度
  final double confidence; // 提取整体置信度 0~1
  final List<String> extractedSteps; // 提取过程步骤(用于动态展示)

  // ===== 真实后端扩展字段(对齐后端 NoticeExtractResponse)=====
  final List<String> warnings; // 需要确认的温和提示(非错误)
  final String extractorMode; // mock|llm|rules

  /// 字段完成度评分(0~1),用于动态进度展示。
  double get completeness {
    int filled = 0;
    const int total = 6;
    if (taskName.trim().isNotEmpty) filled++;
    if (targetAudience != null && targetAudience!.trim().isNotEmpty) filled++;
    if (deadline != null) filled++;
    if (materials.isNotEmpty) filled++;
    if (submitMethod != null && submitMethod!.trim().isNotEmpty) filled++;
    if (location != null && location!.trim().isNotEmpty) filled++;
    return filled / total;
  }

  /// 是否需要人工确认(后端字段透传,便于 UI 决策)。
  bool get needsConfirmation => warnings.isNotEmpty;

  ExtractedNotice copyWith({
    String? taskName,
    String? targetAudience,
    DateTime? deadline,
    List<TaskMaterial>? materials,
    String? submitMethod,
    String? location,
    String? sourceText,
    NoticeImportance? importance,
    double? confidence,
    List<String>? extractedSteps,
    List<String>? warnings,
    String? extractorMode,
  }) {
    return ExtractedNotice(
      taskName: taskName ?? this.taskName,
      targetAudience: targetAudience ?? this.targetAudience,
      deadline: deadline ?? this.deadline,
      materials: materials ?? this.materials,
      submitMethod: submitMethod ?? this.submitMethod,
      location: location ?? this.location,
      sourceText: sourceText ?? this.sourceText,
      importance: importance ?? this.importance,
      confidence: confidence ?? this.confidence,
      extractedSteps: extractedSteps ?? this.extractedSteps,
      warnings: warnings ?? this.warnings,
      extractorMode: extractorMode ?? this.extractorMode,
    );
  }

  @override
  List<Object?> get props => [
        taskName,
        targetAudience,
        deadline,
        materials,
        submitMethod,
        location,
        sourceText,
        importance,
        confidence,
        extractedSteps,
        warnings,
        extractorMode,
      ];
}
