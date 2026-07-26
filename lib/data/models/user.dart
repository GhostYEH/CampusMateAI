import 'package:equatable/equatable.dart';

/// 用户角色 — 决定登录后进入哪个 ShellRoute。
enum UserRole {
  student('学生'),
  teacher('教师'),
  admin('管理员');

  const UserRole(this.displayName);
  final String displayName;

  static UserRole fromString(String? value) {
    if (value == null) return UserRole.student;
    final v = value.toLowerCase();
    switch (v) {
      case 'student':
      case '学生':
        return UserRole.student;
      case 'teacher':
      case '教师':
        return UserRole.teacher;
      case 'admin':
      case '管理员':
        return UserRole.admin;
      default:
        return UserRole.student;
    }
  }

  /// 角色进入后的首页路径。
  String get homePath {
    switch (this) {
      case UserRole.student:
        return '/student/home';
      case UserRole.teacher:
        return '/teacher/workspace';
      case UserRole.admin:
        return '/admin/users';
    }
  }
}

/// 应用用户(支持 student/teacher/admin 三种角色)。
///
/// 不同角色使用不同的可选字段:
/// - 学生: studentId / college / major / grade / className
/// - 教师: teacherId / department / teacherTitle
/// - 管理员: adminTitle / scope
///
/// 为保持向后兼容,默认角色为 student,原有字段保留语义。
class AppUser extends Equatable {
  const AppUser({
    required this.id,
    required this.name,
    required this.role,
    required this.avatarSeed,
    this.nickname,
    // 学生字段
    this.studentId,
    this.college,
    this.major,
    this.grade,
    this.className,
    // 教师字段
    this.teacherId,
    this.department,
    this.teacherTitle,
    // 管理员字段
    this.adminTitle,
    this.scope,
    // 元数据
    this.createdAt,
  });

  final String id;
  final String name;
  final String? nickname;
  final UserRole role;
  final String avatarSeed;

  // 学生字段
  final String? studentId;
  final String? college;
  final String? major;
  final String? grade;
  final String? className;

  // 教师字段
  final String? teacherId;
  final String? department;
  final String? teacherTitle;

  // 管理员字段
  final String? adminTitle;
  final String? scope;

  final DateTime? createdAt;

  /// 显示用的昵称(若为空回退到 name)。
  String get displayName =>
      (nickname == null || nickname!.isEmpty) ? name : nickname!;

  /// 角色相关副标题(用于头像下方)。
  String get roleSubtitle {
    switch (role) {
      case UserRole.student:
        final parts = [
          if (grade != null && grade!.isNotEmpty) grade,
          if (major != null && major!.isNotEmpty) major,
        ];
        return parts.isEmpty ? role.displayName : parts.join(' · ');
      case UserRole.teacher:
        final parts = [
          if (department != null && department!.isNotEmpty) department,
          if (teacherTitle != null && teacherTitle!.isNotEmpty) teacherTitle,
        ];
        return parts.isEmpty ? role.displayName : parts.join(' · ');
      case UserRole.admin:
        return adminTitle ?? role.displayName;
    }
  }

  AppUser copyWith({
    String? id,
    String? name,
    String? nickname,
    UserRole? role,
    String? avatarSeed,
    String? studentId,
    String? college,
    String? major,
    String? grade,
    String? className,
    String? teacherId,
    String? department,
    String? teacherTitle,
    String? adminTitle,
    String? scope,
    DateTime? createdAt,
  }) {
    return AppUser(
      id: id ?? this.id,
      name: name ?? this.name,
      nickname: nickname ?? this.nickname,
      role: role ?? this.role,
      avatarSeed: avatarSeed ?? this.avatarSeed,
      studentId: studentId ?? this.studentId,
      college: college ?? this.college,
      major: major ?? this.major,
      grade: grade ?? this.grade,
      className: className ?? this.className,
      teacherId: teacherId ?? this.teacherId,
      department: department ?? this.department,
      teacherTitle: teacherTitle ?? this.teacherTitle,
      adminTitle: adminTitle ?? this.adminTitle,
      scope: scope ?? this.scope,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'nickname': nickname,
        'role': role.name,
        'avatarSeed': avatarSeed,
        if (studentId != null) 'studentId': studentId,
        if (college != null) 'college': college,
        if (major != null) 'major': major,
        if (grade != null) 'grade': grade,
        if (className != null) 'className': className,
        if (teacherId != null) 'teacherId': teacherId,
        if (department != null) 'department': department,
        if (teacherTitle != null) 'teacherTitle': teacherTitle,
        if (adminTitle != null) 'adminTitle': adminTitle,
        if (scope != null) 'scope': scope,
        if (createdAt != null) 'createdAt': createdAt!.toIso8601String(),
      };

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: json['id'] as String,
      name: json['name'] as String,
      nickname: json['nickname'] as String?,
      role: UserRole.fromString(json['role'] as String?),
      avatarSeed: (json['avatarSeed'] as String?) ?? (json['id'] as String),
      studentId: json['studentId'] as String?,
      college: json['college'] as String?,
      major: json['major'] as String?,
      grade: json['grade'] as String?,
      className: json['className'] as String?,
      teacherId: json['teacherId'] as String?,
      department: json['department'] as String?,
      teacherTitle: json['teacherTitle'] as String?,
      adminTitle: json['adminTitle'] as String?,
      scope: json['scope'] as String?,
      createdAt: json['createdAt'] is String
          ? DateTime.tryParse(json['createdAt'] as String)
          : null,
    );
  }

  @override
  List<Object?> get props => [
        id,
        name,
        nickname,
        role,
        avatarSeed,
        studentId,
        college,
        major,
        grade,
        className,
        teacherId,
        department,
        teacherTitle,
        adminTitle,
        scope,
        createdAt,
      ];
}
