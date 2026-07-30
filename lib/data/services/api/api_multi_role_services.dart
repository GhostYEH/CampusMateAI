import 'package:dio/dio.dart';

import '../../../core/utils/id_generator.dart';
import '../../models/models.dart';
import '../multi_role_service_interfaces.dart';
import 'api_client.dart';
import 'snake_case_adapter.dart';

/// 真实后端认证服务 — 调用 `/api/v1/auth/*` 系列接口。
///
/// 严格遵循 AGENTS.md 凭证规范:
/// - 不在日志中打印 token(代码中只在内存与 [TokenStorage] 之间传递)
/// - 不把密码保存到 SharedPreferences(密码仅作为请求参数使用)
/// - 401 时由 [AuthInterceptor] 处理一次 refresh
/// - refresh 失败后由 [AuthNotifier] 处理退出到登录页
///
/// 与 Mock 实现共享同一接口,通过 AppConfig 切换。
class ApiAuthService implements AuthService {
  ApiAuthService(this._client);

  final ApiClient _client;

  @override
  Future<AuthSession> login(LoginCredentials credentials) async {
    final data = await _client.post(
      '/api/v1/auth/login',
      data: {
        'username': credentials.username,
        'password': credentials.password,
      },
    );
    return _parseSession(data);
  }

  @override
  Future<AppUser> register(RegisterCredentials credentials) async {
    final data = await _client.post(
      '/api/v1/auth/register',
      data: credentials.toJson(),
    );
    return _parseUserPublic(data);
  }

  /// 将后端 [UserPublic] JSON 转换为前端 [AppUser]。
  ///
  /// 字段映射差异:
  /// - 后端 `display_name` → 前端 `name` / `nickname`
  /// - 后端 `student_number` → 前端 `studentId`
  /// - 后端 `teacher_number` → 前端 `teacherId`
  /// - 后端 `created_at` → 前端 `createdAt`(ISO 字符串)
  AppUser _parseUserPublic(Map<String, dynamic> data) {
    final displayName = data['display_name'] as String? ??
        data['displayName'] as String? ??
        data['username'] as String? ??
        '';
    final createdAtStr =
        data['created_at'] as String? ?? data['createdAt'] as String?;
    return AppUser(
      id: data['id'] as String,
      name: displayName,
      nickname: displayName,
      role: UserRole.fromString(data['role'] as String?),
      avatarSeed: (data['avatar_url'] as String?) ??
          (data['avatarUrl'] as String?) ??
          (data['id'] as String),
      studentId:
          data['student_number'] as String? ?? data['studentId'] as String?,
      college: data['college'] as String?,
      major: data['major'] as String?,
      grade: data['grade'] as String?,
      teacherId:
          data['teacher_number'] as String? ?? data['teacherId'] as String?,
      createdAt: createdAtStr == null || createdAtStr.isEmpty
          ? null
          : DateTime.tryParse(createdAtStr),
    );
  }

  @override
  Future<AuthSession> refresh(String refreshToken) async {
    final data = await _client.post(
      '/api/v1/auth/refresh',
      data: {'refresh_token': refreshToken},
    );
    return _parseSession(data);
  }

  @override
  Future<void> logout(String refreshToken) async {
    // 即使后端不可达也算成功(本地凭证由 TokenStorage.clear 清除)
    try {
      await _client.post(
        '/api/v1/auth/logout',
        data: {'refresh_token': refreshToken},
      );
    } on ApiException {
      // 忽略后端错误,本地仍要清理
    }
  }

  @override
  Future<AppUser> getCurrentUser() async {
    final data = await _client.get('/api/v1/auth/me');
    final userJson = data['user'] as Map<String, dynamic>? ?? data;
    return _parseUserPublic(userJson);
  }

  AuthSession _parseSession(Map<String, dynamic> data) {
    // 后端返回 snake_case,直接解析
    final userJson = data['user'] as Map<String, dynamic>? ?? const {};
    final accessToken =
        data['access_token'] as String? ?? data['accessToken'] as String? ?? '';
    final refreshToken = data['refresh_token'] as String? ??
        data['refreshToken'] as String? ??
        '';
    final expiresAtStr =
        data['expires_at'] as String? ?? data['expiresAt'] as String?;
    final tokenType = data['token_type'] as String? ?? 'Bearer';

    if (accessToken.isEmpty || expiresAtStr == null) {
      throw const ApiException(
        code: 'INVALID_SESSION_RESPONSE',
        message: '后端返回的会话数据不完整',
      );
    }

    return AuthSession(
      user: _parseUserPublic(userJson),
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt: DateTime.parse(expiresAtStr),
      tokenType: tokenType,
    );
  }
}

/// 真实后端课程服务 — 调用 `/api/v1/courses` 和 `/api/v1/classes`。
class ApiCourseService implements CourseService {
  ApiCourseService(this._client);

  final ApiClient _client;

  @override
  Future<PaginatedResult<Course>> listCourses({
    String? semester,
    String? search,
    PageRequest page = const PageRequest(),
  }) async {
    final data = await _client.get(
      '/api/v1/courses',
      queryParameters: {
        if (semester != null) 'semester': semester,
        if (search != null && search.isNotEmpty) 'search': search,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => Course.fromJson(json),
    );
  }

  @override
  Future<Course> getCourse(String courseId) async {
    final data = await _client.get('/api/v1/courses/$courseId');
    return Course.fromJson(data);
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
    final data = await _client.post(
      '/api/v1/courses',
      data: SnakeCaseAdapter.toSnakeKeys({
        'code': code,
        'name': name,
        'semesterId': semesterId,
        if (description != null) 'description': description,
        if (creditHours != null) 'creditHours': creditHours,
        if (color != null) 'color': color,
      }),
    );
    return Course.fromJson(data);
  }

  @override
  Future<Course> updateCourse(
    String courseId, {
    String? name,
    String? description,
    int? creditHours,
    int? color,
  }) async {
    final body = <String, dynamic>{};
    if (name != null) body['name'] = name;
    if (description != null) body['description'] = description;
    if (creditHours != null) body['creditHours'] = creditHours;
    if (color != null) body['color'] = color;

    final data = await _client.patch(
      '/api/v1/courses/$courseId',
      data: SnakeCaseAdapter.toSnakeKeys(body),
    );
    return Course.fromJson(data);
  }

  @override
  Future<List<SchoolClass>> listClasses(String courseId) async {
    final data = await _client.get('/api/v1/courses/$courseId/classes');
    final items = data['items'] as List? ?? const [];
    return items
        .whereType<Map<String, dynamic>>()
        .map(SchoolClass.fromJson)
        .toList(growable: false);
  }

  @override
  Future<SchoolClass> createClass({
    required String courseId,
    required String name,
    String? year,
    String? major,
  }) async {
    final data = await _client.post(
      '/api/v1/courses/$courseId/classes',
      data: SnakeCaseAdapter.toSnakeKeys({
        'name': name,
        if (year != null) 'year': year,
        if (major != null) 'major': major,
      }),
    );
    return SchoolClass.fromJson(data);
  }

  @override
  Future<SchoolClass> resetInviteCode(String classId) async {
    final data = await _client.post('/api/v1/classes/$classId/reset-invite');
    return SchoolClass.fromJson(data);
  }

  @override
  Future<SchoolClass> joinByInviteCode(String inviteCode) async {
    final data = await _client.post(
      '/api/v1/classes/join',
      data: {'invite_code': inviteCode},
    );
    return SchoolClass.fromJson(data);
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
    final data = await _client.get(
      '/api/v1/classes/$classId/members',
      queryParameters: {
        if (search != null && search.isNotEmpty) 'search': search,
        if (grade != null && grade.isNotEmpty) 'grade': grade,
        if (major != null && major.isNotEmpty) 'major': major,
        if (submissionStatus != null && submissionStatus != 'all')
          'submission_status': submissionStatus,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => ClassMember.fromJson(json),
    );
  }
}

/// 真实后端通知服务。
class ApiAnnouncementService implements AnnouncementService {
  ApiAnnouncementService(this._client);

  final ApiClient _client;

  @override
  Future<PaginatedResult<Announcement>> listAnnouncements(
    String classId, {
    String? search,
    bool? unreadOnly,
    PageRequest page = const PageRequest(),
  }) async {
    final data = await _client.get(
      '/api/v1/classes/$classId/announcements',
      queryParameters: {
        if (search != null && search.isNotEmpty) 'search': search,
        if (unreadOnly == true) 'unreadOnly': true,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => Announcement.fromJson(json),
    );
  }

  @override
  Future<PaginatedResult<Announcement>> listStudentAnnouncements({
    String? courseId,
    String? search,
    bool? unreadOnly,
    PageRequest page = const PageRequest(),
  }) async {
    final data = await _client.get(
      '/api/v1/student/announcements',
      queryParameters: {
        if (courseId != null) 'course_id': courseId,
        if (search != null && search.isNotEmpty) 'search': search,
        if (unreadOnly == true) 'unread_only': true,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => Announcement.fromJson(json),
    );
  }

  @override
  Future<Announcement> getAnnouncement(String announcementId) async {
    final data = await _client.get('/api/v1/announcements/$announcementId');
    return Announcement.fromJson(data);
  }

  @override
  Future<void> markRead(String announcementId) async {
    await _client.post('/api/v1/announcements/$announcementId/read');
  }

  @override
  Future<Announcement> publishAnnouncement(AnnouncementDraft draft) async {
    final data = await _client.post(
      '/api/v1/announcements',
      data: SnakeCaseAdapter.toSnakeKeys(draft.toJson()),
    );
    return Announcement.fromJson(data);
  }

  @override
  Future<Announcement> saveAnnouncementDraft(AnnouncementDraft draft) async {
    final data = await _client.post(
      '/api/v1/announcements/draft',
      data: SnakeCaseAdapter.toSnakeKeys(draft.toJson()),
    );
    return Announcement.fromJson(data);
  }

  @override
  Future<void> deleteAnnouncement(String announcementId) async {
    await _client.delete('/api/v1/announcements/$announcementId');
  }
}

/// 真实后端任务服务。
class ApiAssignmentService implements AssignmentService {
  ApiAssignmentService(this._client);

  final ApiClient _client;

  @override
  Future<PaginatedResult<Assignment>> listAssignments(
    String classId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    final data = await _client.get(
      '/api/v1/classes/$classId/assignments',
      queryParameters: {
        if (search != null && search.isNotEmpty) 'search': search,
        if (status != null && status != 'all') 'status': status,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => Assignment.fromJson(json),
    );
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
    final data = await _client.get(
      '/api/v1/student/assignments',
      queryParameters: {
        if (courseId != null) 'course_id': courseId,
        if (status != null && status != 'all') 'status': status,
        if (search != null && search.isNotEmpty) 'search': search,
        if (sortBy != null) 'sort_by': sortBy,
        if (sortDesc != null) 'sort_desc': sortDesc,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => Assignment.fromJson(json),
    );
  }

  @override
  Future<Assignment> getAssignment(String assignmentId) async {
    final data = await _client.get('/api/v1/assignments/$assignmentId');
    return Assignment.fromJson(data);
  }

  @override
  Future<Assignment> publishAssignment(AssignmentDraft draft) async {
    final data = await _client.post(
      '/api/v1/assignments',
      data: SnakeCaseAdapter.toSnakeKeys(draft.toJson()),
    );
    return Assignment.fromJson(data);
  }

  @override
  Future<Assignment> saveAssignmentDraft(AssignmentDraft draft) async {
    final data = await _client.post(
      '/api/v1/assignments/draft',
      data: SnakeCaseAdapter.toSnakeKeys(draft.toJson()),
    );
    return Assignment.fromJson(data);
  }

  @override
  Future<void> deleteAssignment(String assignmentId) async {
    await _client.delete('/api/v1/assignments/$assignmentId');
  }

  @override
  Future<AssignmentStats> getAssignmentStats(String assignmentId) async {
    final data = await _client.get('/api/v1/assignments/$assignmentId/stats');
    return AssignmentStats.fromJson(data);
  }

  @override
  Future<PaginatedResult<StudentStatus>> listAssignmentStudentStatuses(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    final data = await _client.get(
      '/api/v1/assignments/$assignmentId/student-status',
      queryParameters: {
        if (search != null && search.isNotEmpty) 'search': search,
        if (status != null && status != 'all') 'status': status,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => StudentStatus.fromJson(json),
    );
  }
}

/// 真实后端提交服务。
class ApiSubmissionService implements SubmissionService {
  ApiSubmissionService(this._client);

  final ApiClient _client;

  @override
  Future<Submission?> getMySubmission(String assignmentId) async {
    try {
      final data = await _client.get(
        '/api/v1/assignments/$assignmentId/my-submission',
      );
      return Submission.fromJson(data);
    } on ApiException catch (e) {
      if (e.isNotFound) return null;
      rethrow;
    }
  }

  @override
  Future<Submission> saveDraft({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    final data = await _client.post(
      '/api/v1/assignments/$assignmentId/submissions',
      data: {
        'text_content': content,
        'submit': false,
      },
    );
    return Submission.fromJson(data);
  }

  @override
  Future<Submission> submit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    final data = await _client.post(
      '/api/v1/assignments/$assignmentId/submissions',
      data: {
        'text_content': content,
        'submit': true,
      },
    );
    return Submission.fromJson(data);
  }

  @override
  Future<Submission> resubmit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    final existing = await getMySubmission(assignmentId);
    if (existing == null) {
      return submit(
        assignmentId: assignmentId,
        content: content,
        attachments: attachments,
      );
    }
    await _client.patch(
      '/api/v1/submissions/${existing.id}',
      data: {'text_content': content},
    );
    final data = await _client.post(
      '/api/v1/submissions/${existing.id}/submit',
    );
    return Submission.fromJson(data);
  }

  @override
  Future<PaginatedResult<Submission>> listSubmissions(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    final data = await _client.get(
      '/api/v1/assignments/$assignmentId/submissions',
      queryParameters: {
        if (search != null && search.isNotEmpty) 'search': search,
        if (status != null && status != 'all') 'status': status,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => Submission.fromJson(json),
    );
  }

  @override
  Future<Submission> getSubmission(String submissionId) async {
    final data = await _client.get('/api/v1/submissions/$submissionId');
    return Submission.fromJson(data);
  }

  @override
  Future<Submission> gradeSubmission({
    required String submissionId,
    required double grade,
    String? comment,
  }) async {
    final data = await _client.post(
      '/api/v1/submissions/$submissionId/grade',
      data: {
        'grade': grade,
        if (comment != null) 'comment': comment,
      },
    );
    return Submission.fromJson(data);
  }

  @override
  Future<int> remindUnsubmitted(String assignmentId) async {
    final data = await _client.post(
      '/api/v1/assignments/$assignmentId/remind',
    );
    return (data['reminded_count'] as num?)?.toInt() ??
        (data['remindedCount'] as num?)?.toInt() ??
        0;
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
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        bytes,
        filename: filename,
        contentType: DioMediaType.parse(mimeType),
      ),
    });
    final data = await _client.upload(
      '/api/v1/assignments/$assignmentId/attachments',
      formData: formData,
      cancelToken: cancelToken,
      onSendProgress: (sent, total) {
        if (total > 0 && onProgress != null) {
          onProgress(sent / total);
        }
      },
    );
    final att = Attachment.fromJson(data);
    return att.copyWith(
      uploadedBy: att.uploadedBy,
      uploadedAt: att.uploadedAt,
    );
  }
}

/// 真实后端仪表盘服务。
class ApiDashboardService implements DashboardService {
  ApiDashboardService(this._client);

  final ApiClient _client;

  @override
  Future<StudentDashboard> getStudentDashboard() async {
    final data = await _client.get('/api/v1/student/dashboard');
    return StudentDashboard.fromJson(data);
  }

  @override
  Future<TeacherDashboard> getTeacherDashboard() async {
    final data = await _client.get('/api/v1/teacher/dashboard');
    // 后端返回的 recentActivities / nextActions 是结构化对象,这里做兼容解析
    // 如果后端返回字符串列表,则按字符串解析为 label
    return _parseTeacherDashboard(data);
  }

  TeacherDashboard _parseTeacherDashboard(Map<String, dynamic> data) {
    final courseCount = (data['course_count'] as num?)?.toInt() ??
        (data['courseCount'] as num?)?.toInt() ??
        0;
    final classCount = (data['class_count'] as num?)?.toInt() ??
        (data['classCount'] as num?)?.toInt() ??
        0;
    final studentCount = (data['student_count'] as num?)?.toInt() ??
        (data['studentCount'] as num?)?.toInt() ??
        0;
    final activeCount = (data['active_assignment_count'] as num?)?.toInt() ??
        (data['activeAssignmentCount'] as num?)?.toInt() ??
        0;
    final pending = (data['pending_submissions'] as num?)?.toInt() ??
        (data['pendingSubmissions'] as num?)?.toInt() ??
        0;
    final unreadStudents =
        (data['unread_announcement_students'] as num?)?.toInt() ??
            (data['unreadAnnouncementStudents'] as num?)?.toInt() ??
            0;
    final overdue = (data['overdue_students'] as num?)?.toInt() ??
        (data['overdueStudents'] as num?)?.toInt() ??
        0;

    final recentActivitiesRaw =
        data['recent_activities'] ?? data['recentActivities'] ?? const [];
    final nextActionsRaw =
        data['next_actions'] ?? data['nextActions'] ?? const [];
    final coursesRaw = data['courses'] ?? const [];

    final recentActivities = (recentActivitiesRaw as List)
        .whereType<Map<String, dynamic>>()
        .map(_parseTeacherActivity)
        .toList(growable: false);
    final nextActions = (nextActionsRaw as List)
        .whereType<Map<String, dynamic>>()
        .map(_parseNextAction)
        .toList(growable: false);
    final courses = (coursesRaw as List)
        .whereType<Map<String, dynamic>>()
        .map(Course.fromJson)
        .toList(growable: false);

    return TeacherDashboard(
      courseCount: courseCount,
      classCount: classCount,
      studentCount: studentCount,
      activeAssignmentCount: activeCount,
      pendingSubmissions: pending,
      unreadAnnouncementStudents: unreadStudents,
      overdueStudents: overdue,
      recentActivities: recentActivities,
      nextActions: nextActions,
      courses: courses,
    );
  }

  TeacherActivity _parseTeacherActivity(Map<String, dynamic> json) {
    return TeacherActivity(
      id: json['id'] as String? ?? IdGenerator.newId('activity'),
      label: json['label'] as String? ?? json['text'] as String? ?? '',
      timestamp: json['timestamp'] is String
          ? DateTime.tryParse(json['timestamp'] as String) ?? DateTime.now()
          : DateTime.now(),
      actionType: _parseActionType(json['action_type'] ?? json['actionType']),
      targetPath:
          json['target_path'] as String? ?? json['targetPath'] as String?,
    );
  }

  TeacherNextAction _parseNextAction(Map<String, dynamic> json) {
    return TeacherNextAction(
      id: json['id'] as String? ?? IdGenerator.newId('action'),
      label: json['label'] as String? ?? json['text'] as String? ?? '',
      actionType: _parseActionType(json['action_type'] ?? json['actionType']),
      count: (json['count'] as num?)?.toInt() ?? 0,
      targetPath:
          json['target_path'] as String? ?? json['targetPath'] as String?,
      payload: (json['payload'] as Map<String, dynamic>?) ?? const {},
      priority: _parsePriority(json['priority']),
    );
  }

  NextActionType _parseActionType(String? value) {
    if (value == null) return NextActionType.other;
    switch (value.toLowerCase()) {
      case 'grade_submission':
      case 'gradesubmission':
        return NextActionType.gradeSubmission;
      case 'publish_announcement':
      case 'publishannouncement':
        return NextActionType.publishAnnouncement;
      case 'publish_assignment':
      case 'publishassignment':
        return NextActionType.publishAssignment;
      case 'remind_unread':
      case 'remindunread':
        return NextActionType.remindUnread;
      case 'remind_unsubmitted':
      case 'remindunsubmitted':
        return NextActionType.remindUnsubmitted;
      case 'view_overdue':
      case 'viewoverdue':
        return NextActionType.viewOverdue;
      case 'view_stats':
      case 'viewstats':
        return NextActionType.viewStats;
      default:
        return NextActionType.other;
    }
  }

  NextActionPriority _parsePriority(String? value) {
    switch (value?.toLowerCase()) {
      case 'high':
        return NextActionPriority.high;
      case 'low':
        return NextActionPriority.low;
      default:
        return NextActionPriority.normal;
    }
  }

  @override
  Future<AdminSystemStatus> getAdminSystemStatus() async {
    final data = await _client.get('/api/v1/admin/system-status');
    return AdminSystemStatus(
      totalUsers: (data['total_users'] as num?)?.toInt() ??
          (data['totalUsers'] as num?)?.toInt() ??
          0,
      totalCourses: (data['total_courses'] as num?)?.toInt() ??
          (data['totalCourses'] as num?)?.toInt() ??
          0,
      totalClasses: (data['total_classes'] as num?)?.toInt() ??
          (data['totalClasses'] as num?)?.toInt() ??
          0,
      activeAssignments: (data['active_assignments'] as num?)?.toInt() ??
          (data['activeAssignments'] as num?)?.toInt() ??
          0,
      todaySubmissions: (data['today_submissions'] as num?)?.toInt() ??
          (data['todaySubmissions'] as num?)?.toInt() ??
          0,
      apiLatencyMs: (data['api_latency_ms'] as num?)?.toInt() ??
          (data['apiLatencyMs'] as num?)?.toInt(),
      backendVersion: data['backend_version'] as String? ??
          data['backendVersion'] as String?,
      lastCheckedAt: DateTime.now(),
      isHealthy:
          data['is_healthy'] as bool? ?? data['isHealthy'] as bool? ?? true,
      warnings: ((data['warnings'] ?? const []) as List)
          .whereType<String>()
          .toList(growable: false),
    );
  }
}

/// 真实后端用户管理服务(管理员)。
class ApiUserManagementService implements UserManagementService {
  ApiUserManagementService(this._client);

  final ApiClient _client;

  @override
  Future<PaginatedResult<UserSummary>> listUsers({
    UserRole? role,
    String? search,
    bool? activeOnly,
    PageRequest page = const PageRequest(),
  }) async {
    final data = await _client.get(
      '/api/v1/admin/users',
      queryParameters: {
        if (role != null) 'role': role.name,
        if (search != null && search.isNotEmpty) 'search': search,
        if (activeOnly == true) 'active_only': true,
        'page': page.page,
        'page_size': page.pageSize,
      },
    );
    return PaginatedResult.fromJson(
      data,
      (json) => UserSummary.fromJson(json),
    );
  }

  @override
  Future<AppUser> getUser(String userId) async {
    final data = await _client.get('/api/v1/admin/users/$userId');
    return AppUser.fromJson(data);
  }

  @override
  Future<UserSummary> setUserActive(String userId, bool active) async {
    final data = await _client.patch(
      '/api/v1/admin/users/$userId/active',
      data: {'active': active},
    );
    return UserSummary.fromJson(data);
  }
}
