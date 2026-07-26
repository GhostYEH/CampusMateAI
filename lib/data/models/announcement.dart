import 'package:equatable/equatable.dart';

import 'course.dart';
import 'notice.dart';

/// 课堂通知(教师发布给班级) — 区别于全局 [CampusNotice]。
class Announcement extends Equatable {
  const Announcement({
    required this.id,
    required this.classId,
    required this.courseId,
    required this.title,
    required this.content,
    required this.authorId,
    required this.authorName,
    required this.publishedAt,
    this.importance = NoticeImportance.normal,
    this.attachments = const [],
    this.tags = const [],
    this.read = false, // 当前用户是否已读
    this.readCount = 0,
    this.totalStudents = 0,
    this.aiSummary,
    this.aiExtractedTasks = const [],
    this.updatedAt,
  });

  final String id;
  final String classId;
  final String courseId;
  final String title;
  final String content;
  final String authorId;
  final String authorName;
  final DateTime publishedAt;
  final NoticeImportance importance;
  final List<Attachment> attachments;
  final List<String> tags;

  final bool read;
  final int readCount;
  final int totalStudents;

  /// AI 自动摘要(教师发布时由 AI 抽取,学生可见)。
  final String? aiSummary;

  /// AI 从通知中抽取的任务项(用于"同步为待办")。
  final List<AnnouncementExtractedTask> aiExtractedTasks;

  final DateTime? updatedAt;

  /// 已读率(0~1)。
  double get readRate => totalStudents == 0 ? 1.0 : readCount / totalStudents;

  Announcement copyWith({
    String? id,
    String? classId,
    String? courseId,
    String? title,
    String? content,
    String? authorId,
    String? authorName,
    DateTime? publishedAt,
    NoticeImportance? importance,
    List<Attachment>? attachments,
    List<String>? tags,
    bool? read,
    int? readCount,
    int? totalStudents,
    String? aiSummary,
    List<AnnouncementExtractedTask>? aiExtractedTasks,
    DateTime? updatedAt,
  }) {
    return Announcement(
      id: id ?? this.id,
      classId: classId ?? this.classId,
      courseId: courseId ?? this.courseId,
      title: title ?? this.title,
      content: content ?? this.content,
      authorId: authorId ?? this.authorId,
      authorName: authorName ?? this.authorName,
      publishedAt: publishedAt ?? this.publishedAt,
      importance: importance ?? this.importance,
      attachments: attachments ?? this.attachments,
      tags: tags ?? this.tags,
      read: read ?? this.read,
      readCount: readCount ?? this.readCount,
      totalStudents: totalStudents ?? this.totalStudents,
      aiSummary: aiSummary ?? this.aiSummary,
      aiExtractedTasks: aiExtractedTasks ?? this.aiExtractedTasks,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
        id,
        classId,
        courseId,
        title,
        content,
        authorId,
        authorName,
        publishedAt,
        importance,
        attachments,
        tags,
        read,
        readCount,
        totalStudents,
        aiSummary,
        aiExtractedTasks,
        updatedAt,
      ];

  Map<String, dynamic> toJson() => {
        'id': id,
        'classId': classId,
        'courseId': courseId,
        'title': title,
        'content': content,
        'authorId': authorId,
        'authorName': authorName,
        'publishedAt': publishedAt.toIso8601String(),
        'importance': importance.name,
        'attachments': attachments.map((a) => a.toJson()).toList(),
        'tags': tags,
        'read': read,
        'readCount': readCount,
        'totalStudents': totalStudents,
        if (aiSummary != null) 'aiSummary': aiSummary,
        'aiExtractedTasks': aiExtractedTasks.map((t) => t.toJson()).toList(),
        if (updatedAt != null) 'updatedAt': updatedAt!.toIso8601String(),
      };

  factory Announcement.fromJson(Map<String, dynamic> json) => Announcement(
        id: json['id'] as String,
        classId:
            json['classId'] as String? ?? json['class_id'] as String? ?? '',
        courseId:
            json['courseId'] as String? ?? json['course_id'] as String? ?? '',
        title: json['title'] as String,
        content: json['content'] as String,
        authorId:
            json['authorId'] as String? ?? json['author_id'] as String? ?? '',
        authorName: json['authorName'] as String? ??
            json['author_name'] as String? ??
            '',
        publishedAt: DateTime.parse(
          json['publishedAt'] as String? ?? json['published_at'] as String,
        ),
        importance: NoticeImportance.fromString(
          json['importance'] as String?,
        ),
        attachments: ((json['attachments'] ?? const []) as List)
            .whereType<Map<String, dynamic>>()
            .map(Attachment.fromJson)
            .toList(growable: false),
        tags: ((json['tags'] ?? const []) as List)
            .whereType<String>()
            .toList(growable: false),
        read: json['read'] as bool? ?? false,
        readCount: (json['readCount'] as num?)?.toInt() ??
            (json['read_count'] as num?)?.toInt() ??
            0,
        totalStudents: (json['totalStudents'] as num?)?.toInt() ??
            (json['total_students'] as num?)?.toInt() ??
            0,
        aiSummary:
            json['aiSummary'] as String? ?? json['ai_summary'] as String?,
        aiExtractedTasks: ((json['aiExtractedTasks'] ??
                json['ai_extracted_tasks'] ??
                const []) as List)
            .whereType<Map<String, dynamic>>()
            .map(AnnouncementExtractedTask.fromJson)
            .toList(growable: false),
        updatedAt: json['updatedAt'] is String
            ? DateTime.tryParse(json['updatedAt'] as String)
            : (json['updated_at'] is String
                ? DateTime.tryParse(json['updated_at'] as String)
                : null),
      );
}

/// AI 从通知中抽取的任务项 — 用于"同步为个人待办"。
class AnnouncementExtractedTask extends Equatable {
  const AnnouncementExtractedTask({
    required this.title,
    this.deadline,
    this.location,
    this.materials = const [],
    this.submissionMethod,
    this.note,
  });

  final String title;
  final DateTime? deadline;
  final String? location;
  final List<String> materials;
  final String? submissionMethod;
  final String? note;

  @override
  List<Object?> get props =>
      [title, deadline, location, materials, submissionMethod, note];

  Map<String, dynamic> toJson() => {
        'title': title,
        if (deadline != null) 'deadline': deadline!.toIso8601String(),
        if (location != null) 'location': location,
        'materials': materials,
        if (submissionMethod != null) 'submissionMethod': submissionMethod,
        if (note != null) 'note': note,
      };

  factory AnnouncementExtractedTask.fromJson(Map<String, dynamic> json) =>
      AnnouncementExtractedTask(
        title: json['title'] as String,
        deadline: json['deadline'] is String
            ? DateTime.tryParse(json['deadline'] as String)
            : null,
        location: json['location'] as String?,
        materials: ((json['materials'] ?? const []) as List)
            .whereType<String>()
            .toList(growable: false),
        submissionMethod: json['submissionMethod'] as String?,
        note: json['note'] as String?,
      );
}
