import 'package:equatable/equatable.dart';

import 'user.dart';

/// 学期信息。
class Semester extends Equatable {
  const Semester({
    required this.id,
    required this.name,
    required this.startDate,
    required this.endDate,
    this.isActive = false,
  });

  final String id;
  final String name; // 例如 "2024-2025-2"
  final DateTime startDate;
  final DateTime endDate;
  final bool isActive;

  /// 用于 UI 显示的简称(如 "24-25-2")。
  String get shortName =>
      name.replaceAll(RegExp(r'20(\d{2})-20(\d{2})-'), r'$1-$2-');

  @override
  List<Object?> get props => [id, name, startDate, endDate, isActive];

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'start_date': startDate.toIso8601String(),
        'end_date': endDate.toIso8601String(),
        'is_active': isActive,
      };

  factory Semester.fromJson(Map<String, dynamic> json) => Semester(
        id: json['id'] as String,
        name: json['name'] as String,
        startDate: DateTime.parse(json['start_date'] as String),
        endDate: DateTime.parse(json['end_date'] as String),
        isActive: json['is_active'] as bool? ?? false,
      );
}

/// 课程教师简要信息(嵌入在 Course 中)。
class CourseTeacher extends Equatable {
  const CourseTeacher({
    required this.id,
    required this.name,
    this.title,
    this.department,
  });

  final String id;
  final String name;
  final String? title;
  final String? department;

  /// 显示用 "姓名 · 职称"。
  String get displayName {
    final parts = [
      name,
      if (title != null && title!.isNotEmpty) title,
    ];
    return parts.join(' · ');
  }

  @override
  List<Object?> get props => [id, name, title, department];

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        if (title != null) 'title': title,
        if (department != null) 'department': department,
      };

  factory CourseTeacher.fromJson(Map<String, dynamic> json) => CourseTeacher(
        id: json['id'] as String,
        name: json['name'] as String,
        title: json['title'] as String?,
        department: json['department'] as String?,
      );
}

/// 课程。
class Course extends Equatable {
  const Course({
    required this.id,
    required this.code,
    required this.name,
    required this.semester,
    required this.teacher,
    this.description,
    this.creditHours = 3,
    this.startDate,
    this.endDate,
    this.classIds = const [],
    this.color = 0xFF2F6486,
    this.studentCount = 0,
    this.classCount = 0,
  });

  final String id;
  final String code; // 课程代码,如 "CS101"
  final String name;
  final Semester semester;
  final CourseTeacher teacher;
  final String? description;
  final int creditHours;
  final DateTime? startDate;
  final DateTime? endDate;
  final List<String> classIds;
  final int color; // 课程主题色(用于卡片/进度条等)
  final int studentCount;
  final int classCount;

  Course copyWith({
    String? id,
    String? code,
    String? name,
    Semester? semester,
    CourseTeacher? teacher,
    String? description,
    int? creditHours,
    DateTime? startDate,
    DateTime? endDate,
    List<String>? classIds,
    int? color,
    int? studentCount,
    int? classCount,
  }) {
    return Course(
      id: id ?? this.id,
      code: code ?? this.code,
      name: name ?? this.name,
      semester: semester ?? this.semester,
      teacher: teacher ?? this.teacher,
      description: description ?? this.description,
      creditHours: creditHours ?? this.creditHours,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      classIds: classIds ?? this.classIds,
      color: color ?? this.color,
      studentCount: studentCount ?? this.studentCount,
      classCount: classCount ?? this.classCount,
    );
  }

  @override
  List<Object?> get props => [
        id,
        code,
        name,
        semester,
        teacher,
        description,
        creditHours,
        startDate,
        endDate,
        classIds,
        color,
        studentCount,
        classCount,
      ];

  Map<String, dynamic> toJson() => {
        'id': id,
        'code': code,
        'name': name,
        'semester': semester.toJson(),
        'teacher': teacher.toJson(),
        if (description != null) 'description': description,
        'creditHours': creditHours,
        if (startDate != null) 'startDate': startDate!.toIso8601String(),
        if (endDate != null) 'endDate': endDate!.toIso8601String(),
        'classIds': classIds,
        'color': color,
        'studentCount': studentCount,
        'classCount': classCount,
      };

  factory Course.fromJson(Map<String, dynamic> json) => Course(
        id: json['id'] as String,
        code: json['code'] as String? ?? '',
        name: json['name'] as String,
        semester: Semester.fromJson(
          json['semester'] as Map<String, dynamic>? ?? {},
        ),
        teacher: CourseTeacher.fromJson(
          json['teacher'] as Map<String, dynamic>? ?? {},
        ),
        description: json['description'] as String?,
        creditHours: (json['creditHours'] as num?)?.toInt() ??
            (json['credit_hours'] as num?)?.toInt() ??
            3,
        startDate: json['startDate'] is String
            ? DateTime.tryParse(json['startDate'] as String)
            : null,
        endDate: json['endDate'] is String
            ? DateTime.tryParse(json['endDate'] as String)
            : null,
        classIds: ((json['classIds'] ?? json['class_ids']) as List?)
                ?.whereType<String>()
                .toList(growable: false) ??
            const [],
        color: (json['color'] as num?)?.toInt() ?? 0xFF2F6486,
        studentCount: (json['studentCount'] as num?)?.toInt() ??
            (json['student_count'] as num?)?.toInt() ??
            0,
        classCount: (json['classCount'] as num?)?.toInt() ??
            (json['class_count'] as num?)?.toInt() ??
            0,
      );
}

/// 教学班级 — 一门课程下的一组学生。
class SchoolClass extends Equatable {
  const SchoolClass({
    required this.id,
    required this.courseId,
    required this.name,
    required this.inviteCode,
    required this.studentCount,
    required this.semester,
    this.teacherId,
    this.teacherName,
    this.year,
    this.major,
    this.createdAt,
  });

  final String id;
  final String courseId;
  final String name; // 例如 "计科2024-1班"
  final String inviteCode; // 学生加入用的邀请码
  final int studentCount;
  final String semester; // 例如 "2024-2025-2"
  final String? teacherId;
  final String? teacherName;
  final String? year; // 年级,例如 "2024级"
  final String? major; // 专业,例如 "计算机科学与技术"
  final DateTime? createdAt;

  SchoolClass copyWith({
    String? id,
    String? courseId,
    String? name,
    String? inviteCode,
    int? studentCount,
    String? semester,
    String? teacherId,
    String? teacherName,
    String? year,
    String? major,
    DateTime? createdAt,
  }) {
    return SchoolClass(
      id: id ?? this.id,
      courseId: courseId ?? this.courseId,
      name: name ?? this.name,
      inviteCode: inviteCode ?? this.inviteCode,
      studentCount: studentCount ?? this.studentCount,
      semester: semester ?? this.semester,
      teacherId: teacherId ?? this.teacherId,
      teacherName: teacherName ?? this.teacherName,
      year: year ?? this.year,
      major: major ?? this.major,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  List<Object?> get props => [
        id,
        courseId,
        name,
        inviteCode,
        studentCount,
        semester,
        teacherId,
        teacherName,
        year,
        major,
        createdAt,
      ];

  Map<String, dynamic> toJson() => {
        'id': id,
        'courseId': courseId,
        'name': name,
        'inviteCode': inviteCode,
        'studentCount': studentCount,
        'semester': semester,
        if (teacherId != null) 'teacherId': teacherId,
        if (teacherName != null) 'teacherName': teacherName,
        if (year != null) 'year': year,
        if (major != null) 'major': major,
        if (createdAt != null) 'createdAt': createdAt!.toIso8601String(),
      };

  factory SchoolClass.fromJson(Map<String, dynamic> json) => SchoolClass(
        id: json['id'] as String,
        courseId:
            json['courseId'] as String? ?? json['course_id'] as String? ?? '',
        name: json['name'] as String,
        inviteCode: json['inviteCode'] as String? ??
            json['invite_code'] as String? ??
            '',
        studentCount: (json['studentCount'] as num?)?.toInt() ??
            (json['student_count'] as num?)?.toInt() ??
            0,
        semester: json['semester'] as String? ?? '',
        teacherId:
            json['teacherId'] as String? ?? json['teacher_id'] as String?,
        teacherName:
            json['teacherName'] as String? ?? json['teacher_name'] as String?,
        year: json['year'] as String?,
        major: json['major'] as String?,
        createdAt: json['createdAt'] is String
            ? DateTime.tryParse(json['createdAt'] as String)
            : null,
      );
}

/// 附件信息(用于通知 / 任务 / 提交)。
class Attachment extends Equatable {
  const Attachment({
    required this.id,
    required this.name,
    required this.sizeBytes,
    required this.mimeType,
    this.url,
    this.uploadedBy,
    this.uploadedAt,
    this.localPath, // 仅本地选择文件时使用,上传后清空
  });

  final String id;
  final String name;
  final int sizeBytes;
  final String mimeType;
  final String? url;
  final String? uploadedBy;
  final DateTime? uploadedAt;
  final String? localPath;

  /// 人类可读的文件大小(如 "2.3 MB")。
  String get sizeLabel {
    const units = ['B', 'KB', 'MB', 'GB'];
    var size = sizeBytes.toDouble();
    var u = 0;
    while (size >= 1024 && u < units.length - 1) {
      size /= 1024;
      u++;
    }
    return '${size.toStringAsFixed(u == 0 ? 0 : 1)} ${units[u]}';
  }

  /// 简单图标判断(用于 UI 显示)。
  String get iconKind {
    final m = mimeType.toLowerCase();
    if (m.startsWith('image/')) return 'image';
    if (m == 'application/pdf') return 'pdf';
    if (m.contains('word') || m.contains('msword')) return 'doc';
    if (m.contains('excel') || m.contains('spreadsheet')) return 'sheet';
    if (m.contains('zip') || m.contains('compressed')) return 'archive';
    if (m.startsWith('video/')) return 'video';
    if (m.startsWith('audio/')) return 'audio';
    return 'file';
  }

  Attachment copyWith({
    String? id,
    String? name,
    int? sizeBytes,
    String? mimeType,
    String? url,
    String? uploadedBy,
    DateTime? uploadedAt,
    String? localPath,
  }) {
    return Attachment(
      id: id ?? this.id,
      name: name ?? this.name,
      sizeBytes: sizeBytes ?? this.sizeBytes,
      mimeType: mimeType ?? this.mimeType,
      url: url ?? this.url,
      uploadedBy: uploadedBy ?? this.uploadedBy,
      uploadedAt: uploadedAt ?? this.uploadedAt,
      localPath: localPath ?? this.localPath,
    );
  }

  @override
  List<Object?> get props =>
      [id, name, sizeBytes, mimeType, url, uploadedBy, uploadedAt, localPath];

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'sizeBytes': sizeBytes,
        'mimeType': mimeType,
        if (url != null) 'url': url,
        if (uploadedBy != null) 'uploadedBy': uploadedBy,
        if (uploadedAt != null) 'uploadedAt': uploadedAt!.toIso8601String(),
      };

  factory Attachment.fromJson(Map<String, dynamic> json) => Attachment(
        id: json['id'] as String,
        name: json['name'] as String,
        sizeBytes: (json['sizeBytes'] as num?)?.toInt() ??
            (json['size_bytes'] as num?)?.toInt() ??
            0,
        mimeType: json['mimeType'] as String? ??
            json['mime_type'] as String? ??
            'application/octet-stream',
        url: json['url'] as String?,
        uploadedBy:
            json['uploadedBy'] as String? ?? json['uploaded_by'] as String?,
        uploadedAt: json['uploadedAt'] is String
            ? DateTime.tryParse(json['uploadedAt'] as String)
            : null,
        localPath: json['localPath'] as String?,
      );
}

/// 班级成员(学生视角) — 教师查看班级成员时返回。
///
/// 严格遵循 AGENTS.md "教师数据权限":
/// 只展示与当前课程相关的字段(姓名、学号、学院、专业、年级、
/// 当前课程的通知已读、任务完成、逾期、成绩),
/// 禁止包含私人 AI 对话、私人待办、学习陪伴、摄像头/表情信息。
class ClassMember extends Equatable {
  const ClassMember({
    required this.userId,
    required this.studentId,
    required this.name,
    required this.classId,
    this.college,
    this.major,
    this.grade,
    this.className,
    this.noticeReadCount = 0,
    this.noticeTotalCount = 0,
    this.assignmentSubmittedCount = 0,
    this.assignmentTotalCount = 0,
    this.assignmentOverdueCount = 0,
    this.assignmentGradedCount = 0,
    this.lastSubmissionAt,
    this.lastReadAt,
    this.latestGrade,
    this.averageScore,
  });

  final String userId;
  final String studentId;
  final String name;
  final String classId;
  final String? college;
  final String? major;
  final String? grade;
  final String? className;

  // 当前课程范围内的统计(不是用户全局隐私数据)
  final int noticeReadCount;
  final int noticeTotalCount;
  final int assignmentSubmittedCount;
  final int assignmentTotalCount;
  final int assignmentOverdueCount;
  final int assignmentGradedCount;
  final DateTime? lastSubmissionAt;
  final DateTime? lastReadAt;
  final double? latestGrade;
  final double? averageScore;

  /// 通知已读率(0~1)。
  double get noticeReadRate =>
      noticeTotalCount == 0 ? 1.0 : noticeReadCount / noticeTotalCount;

  /// 任务提交率(0~1)。
  double get submissionRate => assignmentTotalCount == 0
      ? 1.0
      : assignmentSubmittedCount / assignmentTotalCount;

  /// 是否有逾期任务。
  bool get hasOverdue => assignmentOverdueCount > 0;

  @override
  List<Object?> get props => [
        userId,
        studentId,
        name,
        classId,
        college,
        major,
        grade,
        className,
        noticeReadCount,
        noticeTotalCount,
        assignmentSubmittedCount,
        assignmentTotalCount,
        assignmentOverdueCount,
        assignmentGradedCount,
        lastSubmissionAt,
        lastReadAt,
        latestGrade,
        averageScore,
      ];

  Map<String, dynamic> toJson() => {
        'userId': userId,
        'studentId': studentId,
        'name': name,
        'classId': classId,
        if (college != null) 'college': college,
        if (major != null) 'major': major,
        if (grade != null) 'grade': grade,
        if (className != null) 'className': className,
        'noticeReadCount': noticeReadCount,
        'noticeTotalCount': noticeTotalCount,
        'assignmentSubmittedCount': assignmentSubmittedCount,
        'assignmentTotalCount': assignmentTotalCount,
        'assignmentOverdueCount': assignmentOverdueCount,
        'assignmentGradedCount': assignmentGradedCount,
        if (lastSubmissionAt != null)
          'lastSubmissionAt': lastSubmissionAt!.toIso8601String(),
        if (lastReadAt != null) 'lastReadAt': lastReadAt!.toIso8601String(),
        if (latestGrade != null) 'latestGrade': latestGrade,
        if (averageScore != null) 'averageScore': averageScore,
      };

  factory ClassMember.fromJson(Map<String, dynamic> json) => ClassMember(
        userId: json['userId'] as String? ?? json['user_id'] as String? ?? '',
        studentId:
            json['studentId'] as String? ?? json['student_id'] as String? ?? '',
        name: json['name'] as String,
        classId:
            json['classId'] as String? ?? json['class_id'] as String? ?? '',
        college: json['college'] as String?,
        major: json['major'] as String?,
        grade: json['grade'] as String?,
        className:
            json['className'] as String? ?? json['class_name'] as String?,
        noticeReadCount: (json['noticeReadCount'] as num?)?.toInt() ??
            (json['notice_read_count'] as num?)?.toInt() ??
            0,
        noticeTotalCount: (json['noticeTotalCount'] as num?)?.toInt() ??
            (json['notice_total_count'] as num?)?.toInt() ??
            0,
        assignmentSubmittedCount:
            (json['assignmentSubmittedCount'] as num?)?.toInt() ??
                (json['assignment_submitted_count'] as num?)?.toInt() ??
                0,
        assignmentTotalCount: (json['assignmentTotalCount'] as num?)?.toInt() ??
            (json['assignment_total_count'] as num?)?.toInt() ??
            0,
        assignmentOverdueCount:
            (json['assignmentOverdueCount'] as num?)?.toInt() ??
                (json['assignment_overdue_count'] as num?)?.toInt() ??
                0,
        assignmentGradedCount:
            (json['assignmentGradedCount'] as num?)?.toInt() ??
                (json['assignment_graded_count'] as num?)?.toInt() ??
                0,
        lastSubmissionAt: json['lastSubmissionAt'] is String
            ? DateTime.tryParse(json['lastSubmissionAt'] as String)
            : (json['last_submission_at'] is String
                ? DateTime.tryParse(json['last_submission_at'] as String)
                : null),
        lastReadAt: json['lastReadAt'] is String
            ? DateTime.tryParse(json['lastReadAt'] as String)
            : (json['last_read_at'] is String
                ? DateTime.tryParse(json['last_read_at'] as String)
                : null),
        latestGrade: (json['latestGrade'] as num?)?.toDouble() ??
            (json['latest_grade'] as num?)?.toDouble(),
        averageScore: (json['averageScore'] as num?)?.toDouble() ??
            (json['average_score'] as num?)?.toDouble(),
      );
}

/// 用户简要信息(用于管理员查看用户列表 / 搜索)。
class UserSummary extends Equatable {
  const UserSummary({
    required this.id,
    required this.name,
    required this.role,
    this.username,
    this.email,
    this.studentId,
    this.teacherId,
    this.college,
    this.major,
    this.grade,
    this.department,
    this.createdAt,
    this.isActive = true,
  });

  final String id;
  final String name;
  final UserRole role;
  final String? username;
  final String? email;
  final String? studentId;
  final String? teacherId;
  final String? college;
  final String? major;
  final String? grade;
  final String? department;
  final DateTime? createdAt;
  final bool isActive;

  @override
  List<Object?> get props => [
        id,
        name,
        role,
        username,
        email,
        studentId,
        teacherId,
        college,
        major,
        grade,
        department,
        createdAt,
        isActive,
      ];

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'role': role.name,
        if (username != null) 'username': username,
        if (email != null) 'email': email,
        if (studentId != null) 'studentId': studentId,
        if (teacherId != null) 'teacherId': teacherId,
        if (college != null) 'college': college,
        if (major != null) 'major': major,
        if (grade != null) 'grade': grade,
        if (department != null) 'department': department,
        if (createdAt != null) 'createdAt': createdAt!.toIso8601String(),
        'isActive': isActive,
      };

  factory UserSummary.fromJson(Map<String, dynamic> json) => UserSummary(
        id: json['id'] as String,
        name: json['name'] as String,
        role: UserRole.fromString(json['role'] as String?),
        username: json['username'] as String?,
        email: json['email'] as String?,
        studentId:
            json['studentId'] as String? ?? json['student_id'] as String?,
        teacherId:
            json['teacherId'] as String? ?? json['teacher_id'] as String?,
        college: json['college'] as String?,
        major: json['major'] as String?,
        grade: json['grade'] as String?,
        department: json['department'] as String?,
        createdAt: json['createdAt'] is String
            ? DateTime.tryParse(json['createdAt'] as String)
            : null,
        isActive:
            json['isActive'] as bool? ?? json['is_active'] as bool? ?? true,
      );
}
