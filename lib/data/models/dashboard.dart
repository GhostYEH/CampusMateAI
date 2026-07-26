import 'package:equatable/equatable.dart';

import 'announcement.dart';
import 'assignment.dart';
import 'course.dart';

/// 学生首页仪表盘数据。
class StudentDashboard extends Equatable {
  const StudentDashboard({
    required this.todayCount,
    required this.upcomingCount,
    required this.overdueCount,
    required this.unreadAnnouncementCount,
    required this.totalCourses,
    required this.todayProgress,
    this.recentAnnouncements = const [],
    this.upcomingAssignments = const [],
    this.courses = const [],
    this.lastStudiedAt,
    this.todayStudyMinutes = 0,
  });

  final int todayCount;
  final int upcomingCount;
  final int overdueCount;
  final int unreadAnnouncementCount;
  final int totalCourses;
  final double todayProgress; // 0~1,今日任务完成进度

  final List<Announcement> recentAnnouncements;
  final List<Assignment> upcomingAssignments;
  final List<Course> courses;

  final DateTime? lastStudiedAt;
  final int todayStudyMinutes;

  /// 是否有任何"需要注意"的事项(逾期/截止/未读)。
  bool get hasAttention =>
      overdueCount > 0 || todayCount > 0 || unreadAnnouncementCount > 0;

  @override
  List<Object?> get props => [
        todayCount,
        upcomingCount,
        overdueCount,
        unreadAnnouncementCount,
        totalCourses,
        todayProgress,
        recentAnnouncements,
        upcomingAssignments,
        courses,
        lastStudiedAt,
        todayStudyMinutes,
      ];

  Map<String, dynamic> toJson() => {
        'todayCount': todayCount,
        'upcomingCount': upcomingCount,
        'overdueCount': overdueCount,
        'unreadAnnouncementCount': unreadAnnouncementCount,
        'totalCourses': totalCourses,
        'todayProgress': todayProgress,
        'recentAnnouncements':
            recentAnnouncements.map((a) => a.toJson()).toList(),
        'upcomingAssignments':
            upcomingAssignments.map((a) => a.toJson()).toList(),
        'courses': courses.map((c) => c.toJson()).toList(),
        if (lastStudiedAt != null)
          'lastStudiedAt': lastStudiedAt!.toIso8601String(),
        'todayStudyMinutes': todayStudyMinutes,
      };

  factory StudentDashboard.fromJson(Map<String, dynamic> json) =>
      StudentDashboard(
        todayCount: (json['todayCount'] as num?)?.toInt() ??
            (json['today_count'] as num?)?.toInt() ??
            0,
        upcomingCount: (json['upcomingCount'] as num?)?.toInt() ??
            (json['upcoming_count'] as num?)?.toInt() ??
            0,
        overdueCount: (json['overdueCount'] as num?)?.toInt() ??
            (json['overdue_count'] as num?)?.toInt() ??
            0,
        unreadAnnouncementCount:
            (json['unreadAnnouncementCount'] as num?)?.toInt() ??
                (json['unread_announcement_count'] as num?)?.toInt() ??
                0,
        totalCourses: (json['totalCourses'] as num?)?.toInt() ??
            (json['total_courses'] as num?)?.toInt() ??
            0,
        todayProgress: (json['todayProgress'] as num?)?.toDouble() ??
            (json['today_progress'] as num?)?.toDouble() ??
            0,
        recentAnnouncements: ((json['recentAnnouncements'] ??
                json['recent_announcements'] ??
                const []) as List)
            .whereType<Map<String, dynamic>>()
            .map(Announcement.fromJson)
            .toList(growable: false),
        upcomingAssignments: ((json['upcomingAssignments'] ??
                json['upcoming_assignments'] ??
                const []) as List)
            .whereType<Map<String, dynamic>>()
            .map(Assignment.fromJson)
            .toList(growable: false),
        courses: ((json['courses'] ?? const []) as List)
            .whereType<Map<String, dynamic>>()
            .map(Course.fromJson)
            .toList(growable: false),
        lastStudiedAt: json['lastStudiedAt'] is String
            ? DateTime.tryParse(json['lastStudiedAt'] as String)
            : (json['last_studied_at'] is String
                ? DateTime.tryParse(json['last_studied_at'] as String)
                : null),
        todayStudyMinutes: (json['todayStudyMinutes'] as num?)?.toInt() ??
            (json['today_study_minutes'] as num?)?.toInt() ??
            0,
      );
}

/// 教师工作台"下一步行动"项 — 工作台视觉重点不是数字,而是 next-action。
class TeacherNextAction extends Equatable {
  const TeacherNextAction({
    required this.id,
    required this.label,
    required this.actionType,
    required this.count,
    this.targetPath,
    this.payload,
    this.priority = NextActionPriority.normal,
  });

  final String id;
  final String label; // 例如 "12 份提交待查看"
  final NextActionType actionType;
  final int count;
  final String? targetPath;
  final Map<String, dynamic>? payload;
  final NextActionPriority priority;

  @override
  List<Object?> get props =>
      [id, label, actionType, count, targetPath, payload, priority];
}

/// 下一步行动类型。
enum NextActionType {
  gradeSubmission('待批阅提交'),
  publishAnnouncement('发布通知'),
  publishAssignment('发布任务'),
  remindUnread('未读通知提醒'),
  remindUnsubmitted('未提交催交'),
  viewOverdue('查看逾期'),
  viewStats('查看统计'),
  other('其他');

  const NextActionType(this.displayName);
  final String displayName;
}

/// 下一步行动优先级 — 影响 UI 强调色。
enum NextActionPriority {
  high,
  normal,
  low,
}

/// 最近活动项(教师工作台)。
class TeacherActivity extends Equatable {
  const TeacherActivity({
    required this.id,
    required this.label,
    required this.timestamp,
    this.actionType,
    this.targetPath,
  });

  final String id;
  final String label;
  final DateTime timestamp;
  final NextActionType? actionType;
  final String? targetPath;

  @override
  List<Object?> get props => [id, label, timestamp, actionType, targetPath];
}

/// 教师工作台仪表盘数据。
class TeacherDashboard extends Equatable {
  const TeacherDashboard({
    required this.courseCount,
    required this.classCount,
    required this.studentCount,
    required this.activeAssignmentCount,
    required this.pendingSubmissions,
    required this.unreadAnnouncementStudents,
    required this.overdueStudents,
    this.recentActivities = const [],
    this.nextActions = const [],
    this.courses = const [],
  });

  final int courseCount;
  final int classCount;
  final int studentCount;
  final int activeAssignmentCount;
  final int pendingSubmissions;
  final int unreadAnnouncementStudents;
  final int overdueStudents;

  final List<TeacherActivity> recentActivities;
  final List<TeacherNextAction> nextActions;
  final List<Course> courses;

  /// 是否有任何"需要注意"的事项(待批阅 / 未读 / 逾期)。
  bool get hasAttention =>
      pendingSubmissions > 0 ||
      unreadAnnouncementStudents > 0 ||
      overdueStudents > 0;

  @override
  List<Object?> get props => [
        courseCount,
        classCount,
        studentCount,
        activeAssignmentCount,
        pendingSubmissions,
        unreadAnnouncementStudents,
        overdueStudents,
        recentActivities,
        nextActions,
        courses,
      ];

  Map<String, dynamic> toJson() => {
        'courseCount': courseCount,
        'classCount': classCount,
        'studentCount': studentCount,
        'activeAssignmentCount': activeAssignmentCount,
        'pendingSubmissions': pendingSubmissions,
        'unreadAnnouncementStudents': unreadAnnouncementStudents,
        'overdueStudents': overdueStudents,
        'recentActivities': recentActivities.map((a) => a.toString()).toList(),
        'nextActions': nextActions.map((a) => a.toString()).toList(),
        'courses': courses.map((c) => c.toJson()).toList(),
      };
}

/// 管理员系统状态摘要。
class AdminSystemStatus extends Equatable {
  const AdminSystemStatus({
    required this.totalUsers,
    required this.totalCourses,
    required this.totalClasses,
    required this.activeAssignments,
    required this.todaySubmissions,
    this.apiLatencyMs,
    this.backendVersion,
    this.lastCheckedAt,
    this.isHealthy = true,
    this.warnings = const [],
  });

  final int totalUsers;
  final int totalCourses;
  final int totalClasses;
  final int activeAssignments;
  final int todaySubmissions;
  final int? apiLatencyMs;
  final String? backendVersion;
  final DateTime? lastCheckedAt;
  final bool isHealthy;
  final List<String> warnings;

  @override
  List<Object?> get props => [
        totalUsers,
        totalCourses,
        totalClasses,
        activeAssignments,
        todaySubmissions,
        apiLatencyMs,
        backendVersion,
        lastCheckedAt,
        isHealthy,
        warnings,
      ];
}
