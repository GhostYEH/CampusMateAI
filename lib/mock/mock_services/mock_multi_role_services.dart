import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';

import '../../data/models/models.dart';
import '../../data/services/api/api_client.dart';
import '../../data/services/multi_role_service_interfaces.dart';
import '../mock_data/multi_role_mock_data.dart';

/// Mock 认证服务 — 支持三个演示账号快捷登录,并支持公开注册。
///
/// 凭证:
/// - student_demo / Demo123456 → 学生 林知夏
/// - teacher_demo / Demo123456 → 教师 张明远
/// - admin_demo / Demo123456 → 管理员
///
/// 任何其他用户名/密码返回 invalidCredentials 错误(除非通过 [register] 创建)。
/// Mock 模式下 token 为固定伪造值,仅用于本地状态保持,不发送到任何后端。
class MockAuthService implements AuthService {
  MockAuthService();

  /// 已登录会话(用于 refresh / getCurrentUser 的状态保持)。
  AuthSession? _session;

  /// Mock 注册的用户表(username → AppUser),用于登录校验。
  /// 仅存在于内存中,应用重启后清空。
  final Map<String, AppUser> _registeredUsers = {};

  /// Mock 注册用户的密码表(与 [_registeredUsers] 同步维护)。
  final Map<String, String> _registeredPasswords = {};
  final _random = Random();

  @override
  Future<AuthSession> login(LoginCredentials credentials) async {
    // 模拟网络延迟
    await Future.delayed(const Duration(milliseconds: 480));

    final user = _matchUser(credentials.username, credentials.password);
    if (user == null) {
      throw const ApiException(
        code: 'INVALID_CREDENTIALS',
        message: '用户名或密码错误',
        httpStatus: 401,
      );
    }

    final session = AuthSession(
      user: user,
      // Mock token:base64 编码的简单标识符(不暴露任何敏感信息)
      accessToken: 'mock.access.${user.id}.${_random.nextInt(0xFFFFFF)}',
      refreshToken: 'mock.refresh.${user.id}.${_random.nextInt(0xFFFFFF)}',
      expiresAt: DateTime.now().add(const Duration(hours: 2)),
    );
    _session = session;
    return session;
  }

  @override
  Future<AppUser> register(RegisterCredentials credentials) async {
    await Future.delayed(const Duration(milliseconds: 520));

    // 角色限制:仅允许 student / teacher
    if (credentials.role == UserRole.admin) {
      throw const ApiException(
        code: 'VALIDATION_FAILED',
        message: '管理员账号必须由管理员创建,不可自注册',
        httpStatus: 422,
      );
    }

    // 角色一致性校验
    if (credentials.role == UserRole.student && credentials.teacherNumber != null) {
      throw const ApiException(
        code: 'VALIDATION_FAILED',
        message: '学生角色不应携带 teacher_number',
        httpStatus: 422,
      );
    }
    if (credentials.role == UserRole.teacher && credentials.studentNumber != null) {
      throw const ApiException(
        code: 'VALIDATION_FAILED',
        message: '教师角色不应携带 student_number',
        httpStatus: 422,
      );
    }

    // 唯一性校验:用户名
    final usernameKey = credentials.username.toLowerCase();
    if (_registeredUsers.containsKey(usernameKey) ||
        _isBuiltinUsername(credentials.username)) {
      throw const ApiException(
        code: 'USERNAME_EXISTS',
        message: '用户名已存在',
        httpStatus: 409,
      );
    }

    // 学号唯一性
    if (credentials.studentNumber != null) {
      final exists = _registeredUsers.values.any(
        (u) => u.studentId == credentials.studentNumber,
      );
      if (exists) {
        throw const ApiException(
          code: 'STUDENT_NUMBER_EXISTS',
          message: '学号已存在',
          httpStatus: 409,
        );
      }
    }
    // 工号唯一性
    if (credentials.teacherNumber != null) {
      final exists = _registeredUsers.values.any(
        (u) => u.teacherId == credentials.teacherNumber,
      );
      if (exists) {
        throw const ApiException(
          code: 'TEACHER_NUMBER_EXISTS',
          message: '工号已存在',
          httpStatus: 409,
        );
      }
    }

    final displayName = (credentials.displayName == null ||
            credentials.displayName!.isEmpty)
        ? credentials.username
        : credentials.displayName!;
    final newUser = AppUser(
      id: 'u_mock_${usernameKey}_${_random.nextInt(0xFFFFFF)}',
      name: displayName,
      nickname: displayName,
      role: credentials.role,
      avatarSeed: credentials.username,
      studentId: credentials.studentNumber,
      college: credentials.college,
      major: credentials.major,
      grade: credentials.grade,
      teacherId: credentials.teacherNumber,
      createdAt: DateTime.now(),
    );
    _registeredUsers[usernameKey] = newUser;
    _registeredPasswords[usernameKey] = credentials.password;
    return newUser;
  }

  /// 用户名是否与内置演示账号冲突。
  bool _isBuiltinUsername(String username) {
    final lower = username.toLowerCase();
    return lower == 'student_demo' ||
        lower == 'teacher_demo' ||
        lower == 'admin_demo';
  }

  @override
  Future<AuthSession> refresh(String refreshToken) async {
    await Future.delayed(const Duration(milliseconds: 220));
    final session = _session;
    if (session == null || session.refreshToken != refreshToken) {
      throw const ApiException(
        code: 'INVALID_REFRESH_TOKEN',
        message: '登录已过期,请重新登录',
        httpStatus: 401,
      );
    }
    final refreshed = session.copyWith(
      accessToken:
          'mock.access.${session.user.id}.${_random.nextInt(0xFFFFFF)}',
      refreshToken:
          'mock.refresh.${session.user.id}.${_random.nextInt(0xFFFFFF)}',
      expiresAt: DateTime.now().add(const Duration(hours: 2)),
    );
    _session = refreshed;
    return refreshed;
  }

  @override
  Future<void> logout(String refreshToken) async {
    await Future.delayed(const Duration(milliseconds: 120));
    _session = null;
  }

  @override
  Future<AppUser> getCurrentUser() async {
    await Future.delayed(const Duration(milliseconds: 100));
    final session = _session;
    if (session == null) {
      throw const ApiException(
        code: 'NOT_AUTHENTICATED',
        message: '尚未登录',
        httpStatus: 401,
      );
    }
    return session.user;
  }

  AppUser? _matchUser(String username, String password) {
    final usernameKey = username.toLowerCase();
    // 优先匹配 Mock 注册的用户(密码由用户自定义)
    final registered = _registeredUsers[usernameKey];
    if (registered != null) {
      if (_registeredPasswords[usernameKey] == password) {
        return registered;
      }
      return null;
    }
    // 内置演示账号统一密码 Demo123456
    if (password != 'Demo123456') return null;
    switch (usernameKey) {
      case 'student_demo':
        return MultiRoleMockData.studentDemoUser;
      case 'teacher_demo':
        return MultiRoleMockData.teacherDemoUser;
      case 'admin_demo':
        return MultiRoleMockData.adminDemoUser;
      default:
        return null;
    }
  }
}

/// Mock 课程服务 — 内存存储,启动时加载演示数据。
class MockCourseService implements CourseService {
  MockCourseService() {
    _courses = MultiRoleMockData.courses;
    _classes = MultiRoleMockData.classes;
    _members = MultiRoleMockData.generateClassMembers();
  }

  late List<Course> _courses;
  late List<SchoolClass> _classes;
  late List<ClassMember> _members;
  final _random = Random();

  /// 当前登录用户(由 Provider 在创建时注入)。
  AppUser? currentUser;

  void setCurrentUser(AppUser user) => currentUser = user;

  @override
  Future<PaginatedResult<Course>> listCourses({
    String? semester,
    String? search,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 280));

    List<Course> filtered = _courses;
    if (currentUser != null) {
      switch (currentUser!.role) {
        case UserRole.student:
          // 学生只返回已加入班级所属课程
          final joinedClassIds = _classes
              .where((c) => _isStudentInClass(currentUser!.id, c.id))
              .map((c) => c.id)
              .toSet();
          filtered = _courses
              .where((c) => c.classIds.any((id) => joinedClassIds.contains(id)))
              .toList();
          break;
        case UserRole.teacher:
          filtered =
              _courses.where((c) => c.teacher.id == currentUser!.id).toList();
          break;
        case UserRole.admin:
          break; // 全部
      }
    }

    if (semester != null && semester.isNotEmpty) {
      filtered = filtered.where((c) => c.semester.id == semester).toList();
    }
    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      filtered = filtered
          .where(
            (c) =>
                c.name.toLowerCase().contains(s) ||
                c.code.toLowerCase().contains(s),
          )
          .toList();
    }

    return _paginate(filtered, page);
  }

  @override
  Future<Course> getCourse(String courseId) async {
    await Future.delayed(const Duration(milliseconds: 200));
    final c = _courses.where((c) => c.id == courseId).firstOrNull;
    if (c == null) {
      throw const ApiException(
        code: 'COURSE_NOT_FOUND',
        message: '课程不存在',
        httpStatus: 404,
      );
    }
    return c;
  }

  @override
  Future<Course> createCourse({
    required String code,
    required String name,
    required String semesterId,
    String? description,
    int? creditHours,
    int? color,
  }) async {
    await Future.delayed(const Duration(milliseconds: 380));
    final sem = MultiRoleMockData.currentSemester;
    final course = Course(
      id: 'c_${DateTime.now().millisecondsSinceEpoch}',
      code: code,
      name: name,
      semester: sem,
      teacher: CourseTeacher(
        id: currentUser?.id ?? 'u_teacher_demo',
        name: currentUser?.name ?? '张明远',
        title: currentUser?.teacherTitle,
        department: currentUser?.department,
      ),
      description: description,
      creditHours: creditHours ?? 3,
      color: color ?? 0xFF2F6486,
      classIds: const [],
      studentCount: 0,
      classCount: 0,
    );
    _courses = [..._courses, course];
    return course;
  }

  @override
  Future<Course> updateCourse(
    String courseId, {
    String? name,
    String? description,
    int? creditHours,
    int? color,
  }) async {
    await Future.delayed(const Duration(milliseconds: 220));
    final idx = _courses.indexWhere((c) => c.id == courseId);
    if (idx < 0) {
      throw const ApiException(
        code: 'COURSE_NOT_FOUND',
        message: '课程不存在',
        httpStatus: 404,
      );
    }
    final updated = _courses[idx].copyWith(
      name: name,
      description: description,
      creditHours: creditHours,
      color: color,
    );
    _courses = [..._courses]..[idx] = updated;
    return updated;
  }

  @override
  Future<List<SchoolClass>> listClasses(String courseId) async {
    await Future.delayed(const Duration(milliseconds: 220));
    return _classes.where((c) => c.courseId == courseId).toList();
  }

  @override
  Future<SchoolClass> createClass({
    required String courseId,
    required String name,
    String? year,
    String? major,
  }) async {
    await Future.delayed(const Duration(milliseconds: 320));
    final cls = SchoolClass(
      id: 'cl_${DateTime.now().millisecondsSinceEpoch}',
      courseId: courseId,
      name: name,
      inviteCode: _generateInviteCode(),
      studentCount: 0,
      semester: MultiRoleMockData.currentSemester.id,
      teacherId: currentUser?.id,
      teacherName: currentUser?.name,
      year: year,
      major: major,
      createdAt: DateTime.now(),
    );
    _classes = [..._classes, cls];
    return cls;
  }

  @override
  Future<SchoolClass> resetInviteCode(String classId) async {
    await Future.delayed(const Duration(milliseconds: 180));
    final idx = _classes.indexWhere((c) => c.id == classId);
    if (idx < 0) {
      throw const ApiException(
        code: 'CLASS_NOT_FOUND',
        message: '班级不存在',
        httpStatus: 404,
      );
    }
    final updated = _classes[idx].copyWith(inviteCode: _generateInviteCode());
    _classes = [..._classes]..[idx] = updated;
    return updated;
  }

  @override
  Future<SchoolClass> joinByInviteCode(String inviteCode) async {
    await Future.delayed(const Duration(milliseconds: 380));
    final cls = _classes.where((c) => c.inviteCode == inviteCode).firstOrNull;
    if (cls == null) {
      throw const ApiException(
        code: 'INVALID_INVITE_CODE',
        message: '邀请码无效或已过期',
        httpStatus: 404,
      );
    }
    if (currentUser != null && _isStudentInClass(currentUser!.id, cls.id)) {
      throw const ApiException(
        code: 'ALREADY_JOINED',
        message: '你已经加入了该班级',
        httpStatus: 409,
      );
    }
    // Mock 模式下:不实际持久化成员关系,仅返回班级信息
    return cls;
  }

  @override
  Future<PaginatedResult<ClassMember>> listClassMembers(
    String classId, {
    String? search,
    String? grade,
    String? major,
    String? submissionStatus,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 280));
    List<ClassMember> filtered =
        _members.where((m) => m.classId == classId).toList();

    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      filtered = filtered
          .where(
            (m) =>
                m.name.toLowerCase().contains(s) ||
                m.studentId.toLowerCase().contains(s),
          )
          .toList();
    }
    if (grade != null && grade.isNotEmpty) {
      filtered = filtered.where((m) => m.grade == grade).toList();
    }
    if (major != null && major.isNotEmpty) {
      filtered = filtered.where((m) => m.major == major).toList();
    }
    if (submissionStatus != null) {
      switch (submissionStatus) {
        case 'submitted':
          filtered =
              filtered.where((m) => m.assignmentSubmittedCount > 0).toList();
          break;
        case 'not_submitted':
          filtered = filtered
              .where((m) => m.assignmentSubmittedCount < m.assignmentTotalCount)
              .toList();
          break;
        case 'overdue':
          filtered =
              filtered.where((m) => m.assignmentOverdueCount > 0).toList();
          break;
      }
    }

    return _paginate(filtered, page);
  }

  bool _isStudentInClass(String userId, String classId) {
    if (userId == MultiRoleMockData.studentDemoUser.id) {
      // 演示学生加入了高数1班和数据结构1班
      return classId == 'cl_hm001_1' || classId == 'cl_ds002_1';
    }
    return _members.any((m) => m.userId == userId && m.classId == classId);
  }

  String _generateInviteCode() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    final sb = StringBuffer();
    for (var i = 0; i < 6; i++) {
      sb.write(chars[_random.nextInt(chars.length)]);
    }
    return sb.toString();
  }
}

/// Mock 通知服务。
class MockAnnouncementService implements AnnouncementService {
  MockAnnouncementService() {
    _announcements = MultiRoleMockData.announcements;
    _readIds = <String>{};
  }

  late List<Announcement> _announcements;
  late Set<String> _readIds;

  AppUser? currentUser;
  void setCurrentUser(AppUser user) => currentUser = user;

  @override
  Future<PaginatedResult<Announcement>> listAnnouncements(
    String classId, {
    String? search,
    bool? unreadOnly,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 260));
    List<Announcement> filtered = _announcements
        .where((a) => a.classId == classId)
        .map((a) => a.copyWith(read: _readIds.contains(a.id)))
        .toList();

    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      filtered = filtered
          .where(
            (a) =>
                a.title.toLowerCase().contains(s) ||
                a.content.toLowerCase().contains(s),
          )
          .toList();
    }
    if (unreadOnly == true) {
      filtered = filtered.where((a) => !a.read).toList();
    }
    return _paginate(filtered, page);
  }

  @override
  Future<PaginatedResult<Announcement>> listStudentAnnouncements({
    String? courseId,
    String? search,
    bool? unreadOnly,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 320));
    // 学生视角:返回所在班级的通知
    final studentClassIds = courseId == null
        ? MultiRoleMockData.studentJoinedClassIds
        : MultiRoleMockData.classes
            .where(
              (c) =>
                  c.courseId == courseId &&
                  MultiRoleMockData.studentJoinedClassIds.contains(c.id),
            )
            .map((c) => c.id)
            .toList();

    List<Announcement> filtered = _announcements
        .where((a) => studentClassIds.contains(a.classId))
        .map((a) => a.copyWith(read: _readIds.contains(a.id)))
        .toList();

    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      filtered = filtered
          .where(
            (a) =>
                a.title.toLowerCase().contains(s) ||
                a.content.toLowerCase().contains(s),
          )
          .toList();
    }
    if (unreadOnly == true) {
      filtered = filtered.where((a) => !a.read).toList();
    }
    // 按发布时间倒序
    filtered.sort((a, b) => b.publishedAt.compareTo(a.publishedAt));
    return _paginate(filtered, page);
  }

  @override
  Future<Announcement> getAnnouncement(String announcementId) async {
    await Future.delayed(const Duration(milliseconds: 180));
    final a = _announcements.where((a) => a.id == announcementId).firstOrNull;
    if (a == null) {
      throw const ApiException(
        code: 'ANNOUNCEMENT_NOT_FOUND',
        message: '通知不存在',
        httpStatus: 404,
      );
    }
    // 自动标记已读(由后端真实记录,前端不允许伪造)
    await markRead(announcementId);
    return a.copyWith(
      read: true,
      readCount: a.readCount + (a.read ? 0 : 1),
    );
  }

  @override
  Future<void> markRead(String announcementId) async {
    await Future.delayed(const Duration(milliseconds: 80));
    if (_readIds.add(announcementId)) {
      final idx = _announcements.indexWhere((a) => a.id == announcementId);
      if (idx >= 0) {
        final a = _announcements[idx];
        _announcements = [..._announcements]..[idx] = a.copyWith(
            read: true,
            readCount: a.readCount + 1,
          );
      }
    }
  }

  @override
  Future<Announcement> publishAnnouncement(AnnouncementDraft draft) async {
    await Future.delayed(const Duration(milliseconds: 380));
    if (draft.classIds.isEmpty) {
      throw const ApiException(
        code: 'NO_TARGET_CLASS',
        message: '请至少选择一个班级',
      );
    }
    // AI 预填结果必须经教师人工确认后才能发布 — UI 层应在调用前确保确认
    final now = DateTime.now();
    final Announcement firstAnnouncement = Announcement(
      id: 'an_${now.millisecondsSinceEpoch}',
      classId: draft.classIds.first,
      courseId: draft.courseId,
      title: draft.title,
      content: draft.content,
      authorId: currentUser?.id ?? 'u_teacher_demo',
      authorName: currentUser?.name ?? '张明远',
      publishedAt: now,
      importance: draft.importance,
      attachments: draft.attachments,
      tags: draft.tags,
      read: false,
      readCount: 0,
      totalStudents: 15,
      aiSummary: draft.useAiPrefill ? 'AI 辅助预填,经教师确认后发布' : null,
      aiExtractedTasks: const [],
    );
    _announcements = [firstAnnouncement, ..._announcements];
    return firstAnnouncement;
  }

  @override
  Future<Announcement> saveAnnouncementDraft(AnnouncementDraft draft) async {
    await Future.delayed(const Duration(milliseconds: 200));
    return Announcement(
      id: draft.id ?? 'an_draft_${DateTime.now().millisecondsSinceEpoch}',
      classId: draft.classIds.first,
      courseId: draft.courseId,
      title: draft.title,
      content: draft.content,
      authorId: currentUser?.id ?? 'u_teacher_demo',
      authorName: currentUser?.name ?? '张明远',
      publishedAt: DateTime.now(),
      importance: draft.importance,
      attachments: draft.attachments,
      tags: draft.tags,
      read: false,
      readCount: 0,
      totalStudents: 0,
    );
  }

  @override
  Future<void> deleteAnnouncement(String announcementId) async {
    await Future.delayed(const Duration(milliseconds: 200));
    _announcements =
        _announcements.where((a) => a.id != announcementId).toList();
  }
}

/// Mock 任务服务。
class MockAssignmentService implements AssignmentService {
  MockAssignmentService() {
    _assignments = MultiRoleMockData.assignments;
  }

  late List<Assignment> _assignments;

  AppUser? currentUser;
  void setCurrentUser(AppUser user) => currentUser = user;

  @override
  Future<PaginatedResult<Assignment>> listAssignments(
    String classId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 260));
    List<Assignment> filtered =
        _assignments.where((a) => a.classId == classId).toList();

    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      filtered = filtered
          .where(
            (a) =>
                a.title.toLowerCase().contains(s) ||
                a.description.toLowerCase().contains(s),
          )
          .toList();
    }
    // status 过滤(基于当前学生演示账号的提交状态)
    if (status != null && status != 'all') {
      filtered = _filterByStatus(filtered, status);
    }
    // 默认按截止时间升序(最近的在前)
    filtered.sort((a, b) => b.deadline.compareTo(a.deadline));
    return _paginate(filtered, page);
  }

  List<Assignment> _filterByStatus(
    List<Assignment> source,
    String status,
  ) {
    final now = DateTime.now();
    switch (status) {
      case 'pending':
        return source.where((a) => now.isBefore(a.deadline)).toList();
      case 'submitted':
        // 简化:演示学生已提交 hw1 / hw2
        return source
            .where((a) => a.id == 'as_hm_hw1' || a.id == 'as_hm_hw2')
            .toList();
      case 'overdue':
        return source.where((a) => now.isAfter(a.deadline)).toList();
      case 'graded':
        return source.where((a) => a.id == 'as_hm_hw1').toList();
      default:
        return source;
    }
  }

  @override
  Future<PaginatedResult<Assignment>> listStudentAssignments({
    String? courseId,
    String? status,
    String? search,
    String? sortBy,
    bool? sortDesc,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 340));

    // 学生所在班级的任务
    const studentClassIds = MultiRoleMockData.studentJoinedClassIds;
    List<Assignment> filtered =
        _assignments.where((a) => studentClassIds.contains(a.classId)).toList();

    if (courseId != null && courseId.isNotEmpty) {
      filtered = filtered.where((a) => a.courseId == courseId).toList();
    }
    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      filtered = filtered
          .where(
            (a) =>
                a.title.toLowerCase().contains(s) ||
                a.description.toLowerCase().contains(s) ||
                (a.courseName?.toLowerCase().contains(s) ?? false),
          )
          .toList();
    }
    if (status != null && status != 'all') {
      filtered = _filterByStatus(filtered, status);
    }

    // 排序
    final desc = sortDesc ?? false;
    switch (sortBy) {
      case 'title':
        filtered.sort(
          (a, b) =>
              desc ? b.title.compareTo(a.title) : a.title.compareTo(b.title),
        );
        break;
      case 'created_at':
      case 'createdAt':
        filtered.sort(
          (a, b) => desc
              ? b.createdAt.compareTo(a.createdAt)
              : a.createdAt.compareTo(b.createdAt),
        );
        break;
      case 'deadline':
      default:
        filtered.sort(
          (a, b) => desc
              ? b.deadline.compareTo(a.deadline)
              : a.deadline.compareTo(b.deadline),
        );
        break;
    }

    return _paginate(filtered, page);
  }

  @override
  Future<Assignment> getAssignment(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 180));
    final a = _assignments.where((a) => a.id == assignmentId).firstOrNull;
    if (a == null) {
      throw const ApiException(
        code: 'ASSIGNMENT_NOT_FOUND',
        message: '任务不存在',
        httpStatus: 404,
      );
    }
    return a;
  }

  @override
  Future<Assignment> publishAssignment(AssignmentDraft draft) async {
    await Future.delayed(const Duration(milliseconds: 420));
    final course = MultiRoleMockData.courses
        .where((c) => c.id == draft.courseId)
        .firstOrNull;
    final cls = MultiRoleMockData.classes
        .where((c) => c.id == draft.classId)
        .firstOrNull;
    final now = DateTime.now();
    final a = Assignment(
      id: 'as_${now.millisecondsSinceEpoch}',
      classId: draft.classId,
      courseId: draft.courseId,
      title: draft.title,
      description: draft.description,
      deadline: draft.deadline,
      createdAt: now,
      authorId: currentUser?.id ?? 'u_teacher_demo',
      authorName: currentUser?.name ?? '张明远',
      attachments: draft.attachments,
      submissionType: draft.submissionType,
      allowResubmit: draft.allowResubmit,
      maxScore: draft.maxScore,
      reminderLeadMinutes: draft.reminderLeadMinutes,
      hasReminder: draft.hasReminder,
      totalStudents: 15,
      submittedCount: 0,
      gradedCount: 0,
      overdueCount: 0,
      courseName: course?.name,
      className: cls?.name,
    );
    _assignments = [a, ..._assignments];
    return a;
  }

  @override
  Future<Assignment> saveAssignmentDraft(AssignmentDraft draft) async {
    await Future.delayed(const Duration(milliseconds: 220));
    final now = DateTime.now();
    return Assignment(
      id: draft.id ?? 'as_draft_${now.millisecondsSinceEpoch}',
      classId: draft.classId,
      courseId: draft.courseId,
      title: draft.title,
      description: draft.description,
      deadline: draft.deadline,
      createdAt: now,
      authorId: currentUser?.id ?? 'u_teacher_demo',
      authorName: currentUser?.name ?? '张明远',
      attachments: draft.attachments,
      submissionType: draft.submissionType,
      allowResubmit: draft.allowResubmit,
      maxScore: draft.maxScore,
      reminderLeadMinutes: draft.reminderLeadMinutes,
      hasReminder: draft.hasReminder,
      totalStudents: 0,
      submittedCount: 0,
      gradedCount: 0,
      overdueCount: 0,
    );
  }

  @override
  Future<void> deleteAssignment(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 200));
    _assignments = _assignments.where((a) => a.id != assignmentId).toList();
  }

  @override
  Future<AssignmentStats> getAssignmentStats(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 260));
    final a = _assignments.where((a) => a.id == assignmentId).firstOrNull;
    if (a == null) {
      throw const ApiException(
        code: 'ASSIGNMENT_NOT_FOUND',
        message: '任务不存在',
        httpStatus: 404,
      );
    }
    return AssignmentStats(
      assignmentId: a.id,
      total: a.totalStudents,
      submitted: a.submittedCount,
      graded: a.gradedCount,
      overdue: a.overdueCount,
      notSubmitted: a.totalStudents - a.submittedCount,
      onTimeCount: a.submittedCount,
      averageScore: a.gradedCount > 0 ? 88.5 : null,
      maxScore: a.maxScore,
    );
  }

  @override
  Future<PaginatedResult<StudentStatus>> listAssignmentStudentStatuses(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 280));
    final a = _assignments.where((a) => a.id == assignmentId).firstOrNull;
    if (a == null) {
      throw const ApiException(
        code: 'ASSIGNMENT_NOT_FOUND',
        message: '任务不存在',
        httpStatus: 404,
      );
    }
    // 使用 hw2 的学生状态(若 assignmentId 不匹配,也返回该组数据用于演示)
    List<StudentStatus> statuses =
        MultiRoleMockData.generateHw2StudentStatuses();

    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      statuses = statuses
          .where(
            (s2) =>
                s2.name.toLowerCase().contains(s) ||
                s2.studentNo.toLowerCase().contains(s),
          )
          .toList();
    }
    if (status != null && status != 'all') {
      statuses = statuses.where((s2) => s2.status.name == status).toList();
    }
    return _paginate(statuses, page);
  }
}

/// Mock 提交服务。
class MockSubmissionService implements SubmissionService {
  MockSubmissionService() {
    _submissions = MultiRoleMockData.studentDemoSubmissions;
    _teacherSubmissions = MultiRoleMockData.generateHw2Submissions();
  }

  late List<Submission> _submissions; // 学生演示账号的提交
  late List<Submission> _teacherSubmissions; // 教师视角:所有学生的提交

  AppUser? currentUser;
  void setCurrentUser(AppUser user) => currentUser = user;

  @override
  Future<Submission?> getMySubmission(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 200));
    return _submissions
        .where(
          (s) =>
              s.assignmentId == assignmentId &&
              s.studentId ==
                  (currentUser?.id ?? MultiRoleMockData.studentDemoUser.id),
        )
        .firstOrNull;
  }

  @override
  Future<Submission> saveDraft({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    await Future.delayed(const Duration(milliseconds: 280));
    final existing = _submissions
        .where(
          (s) =>
              s.assignmentId == assignmentId &&
              s.studentId ==
                  (currentUser?.id ?? MultiRoleMockData.studentDemoUser.id),
        )
        .firstOrNull;

    final now = DateTime.now();
    if (existing != null && existing.status == SubmissionStatus.draft) {
      final updated = existing.copyWith(
        content: content,
        attachments: attachments,
        updatedAt: now,
      );
      _submissions = [..._submissions]..[_submissions.indexOf(existing)] =
          updated;
      return updated;
    }

    final draft = Submission(
      id: 'sub_draft_${now.millisecondsSinceEpoch}',
      assignmentId: assignmentId,
      studentId: currentUser?.id ?? MultiRoleMockData.studentDemoUser.id,
      studentName: currentUser?.name ?? MultiRoleMockData.studentDemoUser.name,
      studentNo: currentUser?.studentId ??
          MultiRoleMockData.studentDemoUser.studentId!,
      classId: _lookupClassId(assignmentId),
      courseId: _lookupCourseId(assignmentId),
      status: SubmissionStatus.draft,
      content: content,
      attachments: attachments,
      submittedAt: now,
      updatedAt: now,
      allowResubmit: true,
      isLate: false,
    );
    _submissions = [..._submissions, draft];
    return draft;
  }

  @override
  Future<Submission> submit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    await Future.delayed(const Duration(milliseconds: 420));
    final assignment = MultiRoleMockData.assignments
        .where((a) => a.id == assignmentId)
        .firstOrNull;
    final now = DateTime.now();
    final isLate = assignment != null && now.isAfter(assignment.deadline);

    final submission = Submission(
      id: 'sub_${now.millisecondsSinceEpoch}',
      assignmentId: assignmentId,
      studentId: currentUser?.id ?? MultiRoleMockData.studentDemoUser.id,
      studentName: currentUser?.name ?? MultiRoleMockData.studentDemoUser.name,
      studentNo: currentUser?.studentId ??
          MultiRoleMockData.studentDemoUser.studentId!,
      classId: assignment?.classId ?? _lookupClassId(assignmentId),
      courseId: assignment?.courseId ?? _lookupCourseId(assignmentId),
      status: isLate ? SubmissionStatus.late : SubmissionStatus.submitted,
      content: content,
      attachments: attachments,
      submittedAt: now,
      updatedAt: now,
      allowResubmit: assignment?.allowResubmit ?? true,
      isLate: isLate,
    );

    // 替换已有草稿/已提交
    _submissions = _submissions
        .where(
          (s) => !(s.assignmentId == assignmentId &&
              s.studentId == submission.studentId),
        )
        .toList();
    _submissions = [..._submissions, submission];
    return submission;
  }

  @override
  Future<Submission> resubmit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    await Future.delayed(const Duration(milliseconds: 380));
    final existing = _submissions
        .where(
          (s) =>
              s.assignmentId == assignmentId &&
              s.studentId ==
                  (currentUser?.id ?? MultiRoleMockData.studentDemoUser.id),
        )
        .firstOrNull;
    if (existing == null) {
      throw const ApiException(
        code: 'NO_PRIOR_SUBMISSION',
        message: '尚未提交,无法重新提交',
        httpStatus: 400,
      );
    }
    if (!existing.allowResubmit) {
      throw const ApiException(
        code: 'RESUBMIT_NOT_ALLOWED',
        message: '该任务不允许重新提交',
        httpStatus: 403,
      );
    }
    final now = DateTime.now();
    final updated = existing.copyWith(
      content: content,
      attachments: attachments,
      status: SubmissionStatus.submitted,
      submittedAt: now,
      updatedAt: now,
      resubmissionCount: existing.resubmissionCount + 1,
    );
    _submissions = [..._submissions]..[_submissions.indexOf(existing)] =
        updated;
    return updated;
  }

  @override
  Future<PaginatedResult<Submission>> listSubmissions(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 280));
    List<Submission> filtered = _teacherSubmissions
        .where((s) => s.assignmentId == assignmentId)
        .toList();

    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      filtered = filtered
          .where(
            (sub) =>
                sub.studentName.toLowerCase().contains(s) ||
                sub.studentNo.toLowerCase().contains(s),
          )
          .toList();
    }
    if (status != null && status != 'all') {
      filtered = filtered.where((s) => s.status.name == status).toList();
    }
    return _paginate(filtered, page);
  }

  @override
  Future<Submission> getSubmission(String submissionId) async {
    await Future.delayed(const Duration(milliseconds: 180));
    final s = [
      ..._submissions,
      ..._teacherSubmissions,
    ].where((s) => s.id == submissionId).firstOrNull;
    if (s == null) {
      throw const ApiException(
        code: 'SUBMISSION_NOT_FOUND',
        message: '提交不存在',
        httpStatus: 404,
      );
    }
    return s;
  }

  @override
  Future<Submission> gradeSubmission({
    required String submissionId,
    required double grade,
    String? comment,
  }) async {
    await Future.delayed(const Duration(milliseconds: 320));
    final idx = _teacherSubmissions.indexWhere((s) => s.id == submissionId);
    if (idx < 0) {
      throw const ApiException(
        code: 'SUBMISSION_NOT_FOUND',
        message: '提交不存在',
        httpStatus: 404,
      );
    }
    final now = DateTime.now();
    final updated = _teacherSubmissions[idx].copyWith(
      grade: grade,
      comment: comment,
      gradedAt: now,
      gradedBy: currentUser?.id ?? 'u_teacher_demo',
      gradedByName: currentUser?.name ?? '张明远',
      status: SubmissionStatus.graded,
      updatedAt: now,
    );
    _teacherSubmissions = [..._teacherSubmissions]..[idx] = updated;
    return updated;
  }

  @override
  Future<int> remindUnsubmitted(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 280));
    // Mock 数据中 generateHw2StudentStatuses 固定返回第 2 次作业的状态,
    // 这里直接统计未提交人数,assignmentId 参数仅用于日志/真实模式对齐。
    final statuses = MultiRoleMockData.generateHw2StudentStatuses();
    final count =
        statuses.where((s) => s.status == SubmissionStatus.notSubmitted).length;
    return count;
  }

  @override
  Future<Attachment> uploadAttachment({
    required String assignmentId,
    required List<int> bytes,
    required String filename,
    required String mimeType,
    void Function(double progress)? onProgress,
    CancelToken? cancelToken,
  }) async {
    // 模拟上传进度
    const totalSteps = 10;
    for (var i = 1; i <= totalSteps; i++) {
      await Future.delayed(const Duration(milliseconds: 60));
      if (cancelToken?.isCancelled ?? false) {
        throw DioException(
          requestOptions: RequestOptions(path: '/upload'),
          type: DioExceptionType.cancel,
        );
      }
      onProgress?.call(i / totalSteps);
    }
    return Attachment(
      id: 'att_${DateTime.now().millisecondsSinceEpoch}',
      name: filename,
      sizeBytes: bytes.length,
      mimeType: mimeType,
      url: 'mock://attachments/${DateTime.now().millisecondsSinceEpoch}',
      uploadedBy: currentUser?.id,
      uploadedAt: DateTime.now(),
    );
  }

  String _lookupClassId(String assignmentId) {
    final a = MultiRoleMockData.assignments
        .where((a) => a.id == assignmentId)
        .firstOrNull;
    return a?.classId ?? '';
  }

  String _lookupCourseId(String assignmentId) {
    final a = MultiRoleMockData.assignments
        .where((a) => a.id == assignmentId)
        .firstOrNull;
    return a?.courseId ?? '';
  }
}

/// Mock 仪表盘服务 — 派生自其他 Mock 数据。
class MockDashboardService implements DashboardService {
  MockDashboardService();

  AppUser? currentUser;
  void setCurrentUser(AppUser user) => currentUser = user;

  @override
  Future<StudentDashboard> getStudentDashboard() async {
    await Future.delayed(const Duration(milliseconds: 380));
    final assignments = MultiRoleMockData.assignments
        .where(
          (a) => MultiRoleMockData.studentJoinedClassIds.contains(a.classId),
        )
        .toList();
    final now = DateTime.now();
    final today = assignments.where((a) {
      final d = a.deadline;
      return d.year == now.year && d.month == now.month && d.day == now.day;
    }).length;
    final upcoming = assignments
        .where((a) => now.isBefore(a.deadline) && a.remaining.inHours < 72)
        .toList();
    final overdue = assignments.where((a) => now.isAfter(a.deadline)).toList();

    final announcements = MultiRoleMockData.announcements
        .where(
          (a) => MultiRoleMockData.studentJoinedClassIds.contains(a.classId),
        )
        .toList();
    final unread = announcements.where((a) => !a.read).length;

    final courses = MultiRoleMockData.courses
        .where(
          (c) => MultiRoleMockData.studentJoinedClassIds
              .any((id) => c.classIds.contains(id)),
        )
        .toList();

    return StudentDashboard(
      todayCount: today,
      upcomingCount: upcoming.length,
      overdueCount: overdue.length,
      unreadAnnouncementCount: unread,
      totalCourses: courses.length,
      todayProgress: 0.4,
      recentAnnouncements: announcements.take(3).toList(),
      upcomingAssignments: upcoming.take(5).toList(),
      courses: courses,
      todayStudyMinutes: 65,
    );
  }

  @override
  Future<TeacherDashboard> getTeacherDashboard() async {
    await Future.delayed(const Duration(milliseconds: 420));
    final courses = MultiRoleMockData.courses
        .where((c) => currentUser == null || c.teacher.id == currentUser!.id)
        .toList();
    final classes = MultiRoleMockData.classes
        .where((c) => courses.any((cc) => cc.id == c.courseId))
        .toList();
    final assignments = MultiRoleMockData.assignments
        .where((a) => courses.any((c) => c.id == a.courseId))
        .toList();

    final activeAssignments =
        assignments.where((a) => DateTime.now().isBefore(a.deadline)).length;
    final pendingSubmissions = assignments.fold<int>(
      0,
      (sum, a) => sum + (a.submittedCount - a.gradedCount),
    );
    final unreadStudents = MultiRoleMockData.announcements.fold<int>(
      0,
      (sum, a) => sum + (a.totalStudents - a.readCount),
    );
    final overdueStudents = assignments.fold<int>(
      0,
      (sum, a) => sum + a.overdueCount,
    );

    return TeacherDashboard(
      courseCount: courses.length,
      classCount: classes.length,
      studentCount: classes.fold<int>(0, (sum, c) => sum + c.studentCount),
      activeAssignmentCount: activeAssignments,
      pendingSubmissions: pendingSubmissions,
      unreadAnnouncementStudents: unreadStudents,
      overdueStudents: overdueStudents,
      recentActivities: MultiRoleMockData.teacherRecentActivities,
      nextActions: MultiRoleMockData.teacherNextActions,
      courses: courses,
    );
  }

  @override
  Future<AdminSystemStatus> getAdminSystemStatus() async {
    await Future.delayed(const Duration(milliseconds: 360));
    final courses = MultiRoleMockData.courses;
    final classes = MultiRoleMockData.classes;
    return AdminSystemStatus(
      totalUsers: 35,
      totalCourses: courses.length,
      totalClasses: classes.length,
      activeAssignments: MultiRoleMockData.assignments.length,
      todaySubmissions: 12,
      apiLatencyMs: 42,
      backendVersion: 'mock-1.0.0',
      lastCheckedAt: DateTime.now(),
      isHealthy: true,
      warnings: const [],
    );
  }
}

/// Mock 用户管理服务(管理员)。
class MockUserManagementService implements UserManagementService {
  MockUserManagementService() {
    _users = [
      MultiRoleMockData.studentDemoUser,
      MultiRoleMockData.teacherDemoUser,
      MultiRoleMockData.adminDemoUser,
      MultiRoleMockData.teacherDemoUser.copyWith(
        id: 'u_teacher_liu',
        name: '刘文静',
        nickname: '刘老师',
        teacherId: 'T20190327',
        teacherTitle: '讲师',
      ),
      ...MultiRoleMockData.generateClassMembers().map(
        (m) => AppUser(
          id: m.userId,
          name: m.name,
          role: UserRole.student,
          avatarSeed: m.userId,
          studentId: m.studentId,
          college: m.college,
          major: m.major,
          grade: m.grade,
          className: m.className,
        ),
      ),
    ];
  }

  late List<AppUser> _users;

  @override
  Future<PaginatedResult<UserSummary>> listUsers({
    UserRole? role,
    String? search,
    bool? activeOnly,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 280));
    List<UserSummary> summaries = _users
        .map(
          (u) => UserSummary(
            id: u.id,
            name: u.name,
            role: u.role,
            studentId: u.studentId,
            teacherId: u.teacherId,
            college: u.college,
            major: u.major,
            grade: u.grade,
            department: u.department,
            isActive: true,
          ),
        )
        .toList();

    if (role != null) {
      summaries = summaries.where((u) => u.role == role).toList();
    }
    if (search != null && search.isNotEmpty) {
      final s = search.toLowerCase();
      summaries = summaries
          .where(
            (u) =>
                u.name.toLowerCase().contains(s) ||
                (u.studentId?.toLowerCase().contains(s) ?? false) ||
                (u.teacherId?.toLowerCase().contains(s) ?? false),
          )
          .toList();
    }
    return _paginate(summaries, page);
  }

  @override
  Future<AppUser> getUser(String userId) async {
    await Future.delayed(const Duration(milliseconds: 180));
    final u = _users.where((u) => u.id == userId).firstOrNull;
    if (u == null) {
      throw const ApiException(
        code: 'USER_NOT_FOUND',
        message: '用户不存在',
        httpStatus: 404,
      );
    }
    return u;
  }

  @override
  Future<UserSummary> setUserActive(String userId, bool active) async {
    await Future.delayed(const Duration(milliseconds: 180));
    final u = _users.where((u) => u.id == userId).firstOrNull;
    if (u == null) {
      throw const ApiException(
        code: 'USER_NOT_FOUND',
        message: '用户不存在',
        httpStatus: 404,
      );
    }
    return UserSummary(
      id: u.id,
      name: u.name,
      role: u.role,
      studentId: u.studentId,
      teacherId: u.teacherId,
      college: u.college,
      major: u.major,
      grade: u.grade,
      department: u.department,
      isActive: active,
    );
  }
}

/// 通用分页工具 — Mock 服务使用,模拟服务端分页。
PaginatedResult<T> _paginate<T>(List<T> items, PageRequest page) {
  final total = items.length;
  final start = (page.page - 1) * page.pageSize;
  final end = (start + page.pageSize).clamp(0, total);
  final paged = start < total ? items.sublist(start, end) : <T>[];
  final hasMore = end < total;
  return PaginatedResult<T>(
    items: paged,
    total: total,
    page: page.page,
    pageSize: page.pageSize,
    hasMore: hasMore,
  );
}
