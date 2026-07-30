import 'package:equatable/equatable.dart';

import 'course.dart';
import 'notice.dart';

/// 提交类型 — 任务允许的提交方式。
enum SubmissionType {
  text('文字'),
  file('附件'),
  both('文字 + 附件'),
  none('无需提交');

  const SubmissionType(this.displayName);
  final String displayName;

  static SubmissionType fromString(String? value) {
    if (value == null) return SubmissionType.text;
    final v = value.toLowerCase();
    switch (v) {
      case 'text':
      case '文字':
        return SubmissionType.text;
      case 'file':
      case '附件':
        return SubmissionType.file;
      case 'both':
      case '文字+附件':
      case '文字 + 附件':
        return SubmissionType.both;
      case 'none':
      case '无需提交':
        return SubmissionType.none;
      default:
        return SubmissionType.text;
    }
  }
}

/// 提交状态。
enum SubmissionStatus {
  draft('草稿'),
  submitted('已提交'),
  graded('已评分'),
  late('逾期提交'),
  notSubmitted('未提交');

  const SubmissionStatus(this.displayName);
  final String displayName;

  /// 用于 UI 状态色: 正常(已提交/已评分)/ 草稿中性 / 逾期暖色 / 未提交提醒色。
  bool get isPositive =>
      this == SubmissionStatus.submitted || this == SubmissionStatus.graded;
  bool get isOverdue => this == SubmissionStatus.late;

  static SubmissionStatus fromString(String? value) {
    if (value == null) return SubmissionStatus.notSubmitted;
    final v = value.toLowerCase();
    switch (v) {
      case 'draft':
      case '草稿':
        return SubmissionStatus.draft;
      case 'submitted':
      case '已提交':
        return SubmissionStatus.submitted;
      case 'graded':
      case '已评分':
        return SubmissionStatus.graded;
      case 'late':
      case '逾期':
        return SubmissionStatus.late;
      case 'not_submitted':
      case 'notsubmitted':
      case '未提交':
      default:
        return SubmissionStatus.notSubmitted;
    }
  }
}

/// 课程任务(教师发布给学生)。
class Assignment extends Equatable {
  const Assignment({
    required this.id,
    required this.classId,
    required this.courseId,
    required this.title,
    required this.description,
    required this.deadline,
    required this.createdAt,
    required this.authorId,
    required this.authorName,
    this.attachments = const [],
    this.submissionType = SubmissionType.text,
    this.allowResubmit = true,
    this.maxScore = 100,
    this.reminderLeadMinutes = 60,
    this.hasReminder = true,
    this.totalStudents = 0,
    this.submittedCount = 0,
    this.gradedCount = 0,
    this.overdueCount = 0,
    this.courseName,
    this.className,
  });

  final String id;
  final String classId;
  final String courseId;
  final String title;
  final String description;
  final DateTime deadline;
  final DateTime createdAt;
  final String authorId;
  final String authorName;
  final List<Attachment> attachments;
  final SubmissionType submissionType;
  final bool allowResubmit;
  final double maxScore;
  final int reminderLeadMinutes;
  final bool hasReminder;
  final int totalStudents;
  final int submittedCount;
  final int gradedCount;
  final int overdueCount;
  final String? courseName;
  final String? className;

  /// 提交率(0~1)。
  double get submissionRate =>
      totalStudents == 0 ? 1.0 : submittedCount / totalStudents;

  /// 是否已截止。
  bool get isOverdue => DateTime.now().isAfter(deadline);

  /// 距离截止的剩余时间(可负)。
  Duration get remaining => deadline.difference(DateTime.now());

  /// 是否在 24 小时内截止。
  bool get isDueSoon {
    final r = remaining;
    return !r.isNegative && r.inHours < 24;
  }

  Assignment copyWith({
    String? id,
    String? classId,
    String? courseId,
    String? title,
    String? description,
    DateTime? deadline,
    DateTime? createdAt,
    String? authorId,
    String? authorName,
    List<Attachment>? attachments,
    SubmissionType? submissionType,
    bool? allowResubmit,
    double? maxScore,
    int? reminderLeadMinutes,
    bool? hasReminder,
    int? totalStudents,
    int? submittedCount,
    int? gradedCount,
    int? overdueCount,
    String? courseName,
    String? className,
  }) {
    return Assignment(
      id: id ?? this.id,
      classId: classId ?? this.classId,
      courseId: courseId ?? this.courseId,
      title: title ?? this.title,
      description: description ?? this.description,
      deadline: deadline ?? this.deadline,
      createdAt: createdAt ?? this.createdAt,
      authorId: authorId ?? this.authorId,
      authorName: authorName ?? this.authorName,
      attachments: attachments ?? this.attachments,
      submissionType: submissionType ?? this.submissionType,
      allowResubmit: allowResubmit ?? this.allowResubmit,
      maxScore: maxScore ?? this.maxScore,
      reminderLeadMinutes: reminderLeadMinutes ?? this.reminderLeadMinutes,
      hasReminder: hasReminder ?? this.hasReminder,
      totalStudents: totalStudents ?? this.totalStudents,
      submittedCount: submittedCount ?? this.submittedCount,
      gradedCount: gradedCount ?? this.gradedCount,
      overdueCount: overdueCount ?? this.overdueCount,
      courseName: courseName ?? this.courseName,
      className: className ?? this.className,
    );
  }

  @override
  List<Object?> get props => [
        id,
        classId,
        courseId,
        title,
        description,
        deadline,
        createdAt,
        authorId,
        authorName,
        attachments,
        submissionType,
        allowResubmit,
        maxScore,
        reminderLeadMinutes,
        hasReminder,
        totalStudents,
        submittedCount,
        gradedCount,
        overdueCount,
        courseName,
        className,
      ];

  Map<String, dynamic> toJson() => {
        'id': id,
        'classId': classId,
        'courseId': courseId,
        'title': title,
        'description': description,
        'deadline': deadline.toIso8601String(),
        'createdAt': createdAt.toIso8601String(),
        'authorId': authorId,
        'authorName': authorName,
        'attachments': attachments.map((a) => a.toJson()).toList(),
        'submissionType': submissionType.name,
        'allowResubmit': allowResubmit,
        'maxScore': maxScore,
        'reminderLeadMinutes': reminderLeadMinutes,
        'hasReminder': hasReminder,
        'totalStudents': totalStudents,
        'submittedCount': submittedCount,
        'gradedCount': gradedCount,
        'overdueCount': overdueCount,
        if (courseName != null) 'courseName': courseName,
        if (className != null) 'className': className,
      };

  factory Assignment.fromJson(Map<String, dynamic> json) => Assignment(
        id: json['id'] as String,
        classId:
            json['classId'] as String? ?? json['class_id'] as String? ?? '',
        courseId:
            json['courseId'] as String? ?? json['course_id'] as String? ?? '',
        title: json['title'] as String,
        description: json['description'] as String? ?? '',
        deadline: DateTime.parse(
          json['deadline'] as String,
        ),
        createdAt: DateTime.parse(
          json['createdAt'] as String? ?? json['created_at'] as String,
        ),
        authorId:
            json['authorId'] as String? ?? json['author_id'] as String? ?? '',
        authorName: json['authorName'] as String? ??
            json['author_name'] as String? ??
            '',
        attachments: ((json['attachments'] ?? const []) as List)
            .whereType<Map<String, dynamic>>()
            .map(Attachment.fromJson)
            .toList(growable: false),
        submissionType: SubmissionType.fromString(
          json['submissionType'] as String? ??
              json['submission_type'] as String?,
        ),
        allowResubmit: json['allowResubmit'] as bool? ??
            json['allow_resubmit'] as bool? ??
            true,
        maxScore: (json['maxScore'] as num?)?.toDouble() ??
            (json['max_score'] as num?)?.toDouble() ??
            100,
        reminderLeadMinutes: (json['reminderLeadMinutes'] as num?)?.toInt() ??
            (json['reminder_lead_minutes'] as num?)?.toInt() ??
            60,
        hasReminder: json['hasReminder'] as bool? ??
            json['has_reminder'] as bool? ??
            true,
        totalStudents: (json['totalStudents'] as num?)?.toInt() ??
            (json['total_students'] as num?)?.toInt() ??
            0,
        submittedCount: (json['submittedCount'] as num?)?.toInt() ??
            (json['submitted_count'] as num?)?.toInt() ??
            0,
        gradedCount: (json['gradedCount'] as num?)?.toInt() ??
            (json['graded_count'] as num?)?.toInt() ??
            0,
        overdueCount: (json['overdueCount'] as num?)?.toInt() ??
            (json['overdue_count'] as num?)?.toInt() ??
            0,
        courseName:
            json['courseName'] as String? ?? json['course_name'] as String?,
        className:
            json['className'] as String? ?? json['class_name'] as String?,
      );
}

/// 学生提交记录。
class Submission extends Equatable {
  const Submission({
    required this.id,
    required this.assignmentId,
    required this.studentId,
    required this.studentName,
    required this.studentNo,
    required this.classId,
    required this.courseId,
    required this.status,
    required this.submittedAt,
    this.content = '',
    this.attachments = const [],
    this.updatedAt,
    this.grade,
    this.comment,
    this.gradedAt,
    this.gradedBy,
    this.gradedByName,
    this.resubmissionCount = 0,
    this.allowResubmit = true,
    this.isLate = false,
  });

  final String id;
  final String assignmentId;
  final String studentId;
  final String studentName;
  final String studentNo; // 学号
  final String classId;
  final String courseId;
  final SubmissionStatus status;

  final String content;
  final List<Attachment> attachments;

  final DateTime submittedAt;
  final DateTime? updatedAt;

  final double? grade;
  final String? comment;
  final DateTime? gradedAt;
  final String? gradedBy;
  final String? gradedByName;

  final int resubmissionCount;
  final bool allowResubmit;
  final bool isLate;

  /// 是否已评分。
  bool get isGraded => status == SubmissionStatus.graded || grade != null;

  /// 归一化成绩(0~1,基于 maxScore)。
  double normalizedScore(double maxScore) =>
      grade == null ? 0 : (grade! / maxScore).clamp(0.0, 1.0);

  Submission copyWith({
    String? id,
    String? assignmentId,
    String? studentId,
    String? studentName,
    String? studentNo,
    String? classId,
    String? courseId,
    SubmissionStatus? status,
    String? content,
    List<Attachment>? attachments,
    DateTime? submittedAt,
    DateTime? updatedAt,
    double? grade,
    String? comment,
    DateTime? gradedAt,
    String? gradedBy,
    String? gradedByName,
    int? resubmissionCount,
    bool? allowResubmit,
    bool? isLate,
  }) {
    return Submission(
      id: id ?? this.id,
      assignmentId: assignmentId ?? this.assignmentId,
      studentId: studentId ?? this.studentId,
      studentName: studentName ?? this.studentName,
      studentNo: studentNo ?? this.studentNo,
      classId: classId ?? this.classId,
      courseId: courseId ?? this.courseId,
      status: status ?? this.status,
      content: content ?? this.content,
      attachments: attachments ?? this.attachments,
      submittedAt: submittedAt ?? this.submittedAt,
      updatedAt: updatedAt ?? this.updatedAt,
      grade: grade ?? this.grade,
      comment: comment ?? this.comment,
      gradedAt: gradedAt ?? this.gradedAt,
      gradedBy: gradedBy ?? this.gradedBy,
      gradedByName: gradedByName ?? this.gradedByName,
      resubmissionCount: resubmissionCount ?? this.resubmissionCount,
      allowResubmit: allowResubmit ?? this.allowResubmit,
      isLate: isLate ?? this.isLate,
    );
  }

  @override
  List<Object?> get props => [
        id,
        assignmentId,
        studentId,
        studentName,
        studentNo,
        classId,
        courseId,
        status,
        content,
        attachments,
        submittedAt,
        updatedAt,
        grade,
        comment,
        gradedAt,
        gradedBy,
        gradedByName,
        resubmissionCount,
        allowResubmit,
        isLate,
      ];

  Map<String, dynamic> toJson() => {
        'id': id,
        'assignmentId': assignmentId,
        'studentId': studentId,
        'studentName': studentName,
        'studentNo': studentNo,
        'classId': classId,
        'courseId': courseId,
        'status': status.name,
        'content': content,
        'attachments': attachments.map((a) => a.toJson()).toList(),
        'submittedAt': submittedAt.toIso8601String(),
        if (updatedAt != null) 'updatedAt': updatedAt!.toIso8601String(),
        if (grade != null) 'grade': grade,
        if (comment != null) 'comment': comment,
        if (gradedAt != null) 'gradedAt': gradedAt!.toIso8601String(),
        if (gradedBy != null) 'gradedBy': gradedBy,
        if (gradedByName != null) 'gradedByName': gradedByName,
        'resubmissionCount': resubmissionCount,
        'allowResubmit': allowResubmit,
        'isLate': isLate,
      };

  factory Submission.fromJson(Map<String, dynamic> json) => Submission(
        id: json['id'] as String,
        assignmentId: json['assignmentId'] as String? ??
            json['assignment_id'] as String? ??
            '',
        studentId:
            json['studentId'] as String? ?? json['student_id'] as String? ?? '',
        studentName: json['studentName'] as String? ??
            json['student_name'] as String? ??
            '',
        studentNo: json['studentNo'] as String? ??
            json['student_no'] as String? ??
            json['student_number'] as String? ??
            '',
        classId:
            json['classId'] as String? ?? json['class_id'] as String? ?? '',
        courseId:
            json['courseId'] as String? ?? json['course_id'] as String? ?? '',
        status: SubmissionStatus.fromString(
          json['status'] as String?,
        ),
        content:
            json['content'] as String? ?? json['text_content'] as String? ?? '',
        attachments: ((json['attachments'] ?? const []) as List)
            .whereType<Map<String, dynamic>>()
            .map(Attachment.fromJson)
            .toList(growable: false),
        submittedAt: DateTime.parse(
          json['submittedAt'] as String? ??
              json['submitted_at'] as String? ??
              json['updated_at'] as String,
        ),
        updatedAt: json['updatedAt'] is String
            ? DateTime.tryParse(json['updatedAt'] as String)
            : (json['updated_at'] is String
                ? DateTime.tryParse(json['updated_at'] as String)
                : null),
        grade: (json['score'] as num?)?.toDouble() ??
            (json['grade'] is num ? (json['grade'] as num).toDouble() : null),
        comment:
            json['comment'] as String? ?? json['teacher_comment'] as String?,
        gradedAt: json['gradedAt'] is String
            ? DateTime.tryParse(json['gradedAt'] as String)
            : (json['graded_at'] is String
                ? DateTime.tryParse(json['graded_at'] as String)
                : null),
        gradedBy: json['gradedBy'] as String? ?? json['graded_by'] as String?,
        gradedByName: json['gradedByName'] as String? ??
            json['graded_by_name'] as String?,
        resubmissionCount: (json['resubmissionCount'] as num?)?.toInt() ??
            (json['resubmission_count'] as num?)?.toInt() ??
            0,
        allowResubmit: json['allowResubmit'] as bool? ??
            json['allow_resubmit'] as bool? ??
            true,
        isLate: json['isLate'] as bool? ?? json['is_late'] as bool? ?? false,
      );
}

/// 学生在某任务上的状态摘要 — 用于教师查看提交统计列表。
class StudentStatus extends Equatable {
  const StudentStatus({
    required this.studentId,
    required this.name,
    required this.studentNo,
    required this.classId,
    required this.className,
    required this.status,
    this.submittedAt,
    this.grade,
    this.hasAttachment = false,
    this.attachmentCount = 0,
    this.contentLength = 0,
  });

  final String studentId;
  final String name;
  final String studentNo;
  final String classId;
  final String className;
  final SubmissionStatus status;
  final DateTime? submittedAt;
  final double? grade;
  final bool hasAttachment;
  final int attachmentCount;
  final int contentLength;

  @override
  List<Object?> get props => [
        studentId,
        name,
        studentNo,
        classId,
        className,
        status,
        submittedAt,
        grade,
        hasAttachment,
        attachmentCount,
        contentLength,
      ];

  Map<String, dynamic> toJson() => {
        'studentId': studentId,
        'name': name,
        'studentNo': studentNo,
        'classId': classId,
        'className': className,
        'status': status.name,
        if (submittedAt != null) 'submittedAt': submittedAt!.toIso8601String(),
        if (grade != null) 'grade': grade,
        'hasAttachment': hasAttachment,
        'attachmentCount': attachmentCount,
        'contentLength': contentLength,
      };

  factory StudentStatus.fromJson(Map<String, dynamic> json) => StudentStatus(
        studentId:
            json['studentId'] as String? ?? json['student_id'] as String? ?? '',
        name: json['name'] as String,
        studentNo:
            json['studentNo'] as String? ?? json['student_no'] as String? ?? '',
        classId:
            json['classId'] as String? ?? json['class_id'] as String? ?? '',
        className:
            json['className'] as String? ?? json['class_name'] as String? ?? '',
        status: SubmissionStatus.fromString(json['status'] as String?),
        submittedAt: json['submittedAt'] is String
            ? DateTime.tryParse(json['submittedAt'] as String)
            : (json['submitted_at'] is String
                ? DateTime.tryParse(json['submitted_at'] as String)
                : null),
        grade: (json['grade'] as num?)?.toDouble(),
        hasAttachment: json['hasAttachment'] as bool? ??
            json['has_attachment'] as bool? ??
            false,
        attachmentCount: (json['attachmentCount'] as num?)?.toInt() ??
            (json['attachment_count'] as num?)?.toInt() ??
            0,
        contentLength: (json['contentLength'] as num?)?.toInt() ??
            (json['content_length'] as num?)?.toInt() ??
            0,
      );
}

/// 任务统计 — 教师查看任务统计页时返回。
class AssignmentStats extends Equatable {
  const AssignmentStats({
    required this.assignmentId,
    required this.total,
    required this.submitted,
    required this.graded,
    required this.overdue,
    required this.notSubmitted,
    required this.onTimeCount,
    this.averageScore,
    this.medianScore,
    this.maxScore = 100,
  });

  final String assignmentId;
  final int total;
  final int submitted;
  final int graded;
  final int overdue;
  final int notSubmitted;
  final int onTimeCount;

  final double? averageScore;
  final double? medianScore;
  final double maxScore;

  /// 提交率(0~1)。
  double get submissionRate => total == 0 ? 1.0 : submitted / total;

  /// 准时提交率(0~1,基于已提交)。
  double get onTimeRate => submitted == 0 ? 0 : onTimeCount / submitted;

  /// 评分完成率(0~1,基于已提交)。
  double get gradedRate => submitted == 0 ? 0 : graded / submitted;

  /// 逾期率(0~1,基于总人数)。
  double get overdueRate => total == 0 ? 0 : overdue / total;

  /// 未提交率(0~1)。
  double get notSubmittedRate => total == 0 ? 0 : notSubmitted / total;

  @override
  List<Object?> get props => [
        assignmentId,
        total,
        submitted,
        graded,
        overdue,
        notSubmitted,
        onTimeCount,
        averageScore,
        medianScore,
        maxScore,
      ];

  Map<String, dynamic> toJson() => {
        'assignmentId': assignmentId,
        'total': total,
        'submitted': submitted,
        'graded': graded,
        'overdue': overdue,
        'notSubmitted': notSubmitted,
        'onTimeCount': onTimeCount,
        if (averageScore != null) 'averageScore': averageScore,
        if (medianScore != null) 'medianScore': medianScore,
        'maxScore': maxScore,
      };

  factory AssignmentStats.fromJson(Map<String, dynamic> json) =>
      AssignmentStats(
        assignmentId: json['assignmentId'] as String? ??
            json['assignment_id'] as String? ??
            '',
        total: (json['total'] as num?)?.toInt() ?? 0,
        submitted: (json['submitted'] as num?)?.toInt() ?? 0,
        graded: (json['graded'] as num?)?.toInt() ?? 0,
        overdue: (json['overdue'] as num?)?.toInt() ?? 0,
        notSubmitted: (json['notSubmitted'] as num?)?.toInt() ??
            (json['not_submitted'] as num?)?.toInt() ??
            0,
        onTimeCount: (json['onTimeCount'] as num?)?.toInt() ??
            (json['on_time_count'] as num?)?.toInt() ??
            0,
        averageScore: (json['averageScore'] as num?)?.toDouble() ??
            (json['average_score'] as num?)?.toDouble(),
        medianScore: (json['medianScore'] as num?)?.toDouble() ??
            (json['median_score'] as num?)?.toDouble(),
        maxScore: (json['maxScore'] as num?)?.toDouble() ??
            (json['max_score'] as num?)?.toDouble() ??
            100,
      );
}

/// 教师创建任务的输入(发布时传入)。
class AssignmentDraft extends Equatable {
  const AssignmentDraft({
    this.id,
    required this.classId,
    required this.courseId,
    required this.title,
    required this.description,
    required this.deadline,
    this.attachments = const [],
    this.submissionType = SubmissionType.text,
    this.allowResubmit = true,
    this.maxScore = 100,
    this.reminderLeadMinutes = 60,
    this.hasReminder = true,
    this.isDraft = false,
  });

  final String? id;
  final String classId;
  final String courseId;
  final String title;
  final String description;
  final DateTime deadline;
  final List<Attachment> attachments;
  final SubmissionType submissionType;
  final bool allowResubmit;
  final double maxScore;
  final int reminderLeadMinutes;
  final bool hasReminder;
  final bool isDraft;

  @override
  List<Object?> get props => [
        id,
        classId,
        courseId,
        title,
        description,
        deadline,
        attachments,
        submissionType,
        allowResubmit,
        maxScore,
        reminderLeadMinutes,
        hasReminder,
        isDraft,
      ];

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'classId': classId,
        'courseId': courseId,
        'title': title,
        'description': description,
        'deadline': deadline.toIso8601String(),
        'attachments': attachments.map((a) => a.toJson()).toList(),
        'submissionType': submissionType.name,
        'allowResubmit': allowResubmit,
        'maxScore': maxScore,
        'reminderLeadMinutes': reminderLeadMinutes,
        'hasReminder': hasReminder,
        'isDraft': isDraft,
      };
}

/// 教师发布通知的输入。
class AnnouncementDraft extends Equatable {
  const AnnouncementDraft({
    this.id,
    required this.classIds,
    required this.courseId,
    required this.title,
    required this.content,
    required this.importance,
    this.attachments = const [],
    this.tags = const [],
    this.isDraft = false,
    this.useAiPrefill = false,
    this.rawNoticeText,
  });

  final String? id;
  final List<String> classIds; // 支持多班级同时发布
  final String courseId;
  final String title;
  final String content;
  final NoticeImportance importance;
  final List<Attachment> attachments;
  final List<String> tags;
  final bool isDraft;
  final bool useAiPrefill;
  final String? rawNoticeText; // AI 预填时的原始通知文本

  @override
  List<Object?> get props => [
        id,
        classIds,
        courseId,
        title,
        content,
        importance,
        attachments,
        tags,
        isDraft,
        useAiPrefill,
        rawNoticeText,
      ];

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'classIds': classIds,
        'courseId': courseId,
        'title': title,
        'content': content,
        'importance': importance.name,
        'attachments': attachments.map((a) => a.toJson()).toList(),
        'tags': tags,
        'isDraft': isDraft,
        'useAiPrefill': useAiPrefill,
        if (rawNoticeText != null) 'rawNoticeText': rawNoticeText,
      };
}

/// 通知重要程度 — 复用自 notice.dart,这里仅作为类型重导出避免循环引用。
/// 注意:不要在此文件 import notice.dart 之外的内容以避免循环。
/// 实际使用时通过 announcement.dart 间接 import 即可。
