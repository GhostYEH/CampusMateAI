import 'package:dio/dio.dart';

import '../models/models.dart';
import 'api/api_client.dart';

/// 多角色服务接口汇总 — UI 层只依赖抽象接口,通过 Riverpod 注入 Mock 或 Real 实现。
///
/// 接口路径严格对齐 `docs/multi_role_api_contract.md`(若后端 Agent 已生成)
/// 与用户任务说明中的固定 API 列表。
///
/// 后端使用 snake_case,Dart 模型内部使用 camelCase,
/// 各 [ApiXxxService] 实现负责字段转换。

// ===== 认证服务 =====

/// 认证服务 — 登录 / 刷新 / 退出 / 当前用户。
///
/// 凭证规范(AGENTS.md):
/// - 不在日志中打印 token
/// - 不把密码保存到 SharedPreferences
/// - 401 时尝试一次 refresh
/// - refresh 失败后退出到登录页
/// - 防止多个并发请求重复刷新 token
abstract interface class AuthService {
  /// 登录 — 返回 [AuthSession]。
  ///
  /// 失败时抛 [ApiException],UI 层根据 code 映射为 [AuthFailure] 文案。
  Future<AuthSession> login(LoginCredentials credentials);

  /// 刷新 access_token(使用 refresh_token)。
  ///
  /// 失败时抛 [ApiException] — 调用方应捕获后 logout。
  Future<AuthSession> refresh(String refreshToken);

  /// 退出登录 — 通知后端撤销 token。
  ///
  /// 即使后端不可达,本地凭证也应被清除。
  Future<void> logout(String refreshToken);

  /// 获取当前登录用户信息(用于 token 仍然有效时恢复会话)。
  Future<AppUser> getCurrentUser();
}

// ===== 课程与班级服务 =====

/// 课程服务 — 教师 / 学生 / 管理员共用,根据角色返回不同范围的数据。
abstract interface class CourseService {
  /// 列出课程(分页 + 搜索 + 学期筛选)。
  ///
  /// 学生返回已加入的课程;教师返回自己开设的课程;管理员返回全部。
  Future<PaginatedResult<Course>> listCourses({
    String? semester,
    String? search,
    PageRequest page = const PageRequest(),
  });

  /// 获取单个课程详情。
  Future<Course> getCourse(String courseId);

  /// 创建课程(教师 / 管理员)。
  Future<Course> createCourse({
    required String code,
    required String name,
    required String semesterId,
    String? description,
    int? creditHours,
    int? color,
  });

  /// 更新课程信息。
  Future<Course> updateCourse(
    String courseId, {
    String? name,
    String? description,
    int? creditHours,
    int? color,
  });

  /// 列出指定课程下的班级。
  Future<List<SchoolClass>> listClasses(String courseId);

  /// 创建班级(教师)。
  Future<SchoolClass> createClass({
    required String courseId,
    required String name,
    String? year,
    String? major,
  });

  /// 重置班级邀请码(教师)。
  Future<SchoolClass> resetInviteCode(String classId);

  /// 学生通过邀请码加入班级。
  ///
  /// 成功返回 classId;失败(无效码 / 已加入 / 已满)抛 [ApiException]。
  Future<SchoolClass> joinByInviteCode(String inviteCode);

  /// 列出班级成员(教师 / 管理员)。
  ///
  /// 严格遵循 AGENTS.md "教师数据权限":
  /// 只返回当前课程相关字段,不返回私人 AI 对话 / 私人待办 / 摄像头信息。
  Future<PaginatedResult<ClassMember>> listClassMembers(
    String classId, {
    String? search,
    String? grade,
    String? major,
    String?
        submissionStatus, // 'submitted' / 'not_submitted' / 'overdue' / null
    PageRequest page = const PageRequest(),
  });
}

// ===== 通知服务(课堂通知,区别于全局校园通知) =====

abstract interface class AnnouncementService {
  /// 列出班级通知(学生视角 — 自动带当前用户的已读状态)。
  Future<PaginatedResult<Announcement>> listAnnouncements(
    String classId, {
    String? search,
    bool? unreadOnly,
    PageRequest page = const PageRequest(),
  });

  /// 列出学生在某课程下所有班级的通知聚合(学生首页用)。
  Future<PaginatedResult<Announcement>> listStudentAnnouncements({
    String? courseId,
    String? search,
    bool? unreadOnly,
    PageRequest page = const PageRequest(),
  });

  /// 获取通知详情(自动标记当前用户已读 — 由后端确保真实回执,不允许伪造)。
  Future<Announcement> getAnnouncement(String announcementId);

  /// 标记通知为已读(发送已读回执)。
  ///
  /// Mock 模式下本地更新状态;真实模式下调用 `/api/v1/announcements/{id}/read`。
  Future<void> markRead(String announcementId);

  /// 教师发布通知(支持多班级同时发布)。
  ///
  /// AI 自动预填结果需经教师人工确认后才调用此方法发布,
  /// 不允许 AI 未经确认直接发布(AGENTS.md §6 教师发布中心规范)。
  Future<Announcement> publishAnnouncement(AnnouncementDraft draft);

  /// 教师保存通知草稿。
  Future<Announcement> saveAnnouncementDraft(AnnouncementDraft draft);

  /// 教师删除通知(软删除)。
  Future<void> deleteAnnouncement(String announcementId);
}

// ===== 任务服务(课堂任务,区别于个人待办) =====

abstract interface class AssignmentService {
  /// 列出班级任务(学生视角 — 带 status 字段表示当前学生的提交状态)。
  Future<PaginatedResult<Assignment>> listAssignments(
    String classId, {
    String? search,
    String? status, // 'all' / 'pending' / 'submitted' / 'overdue' / 'graded'
    PageRequest page = const PageRequest(),
  });

  /// 列出学生在所有课程下的任务聚合(学生任务中心用)。
  Future<PaginatedResult<Assignment>> listStudentAssignments({
    String? courseId,
    String? status,
    String? search,
    String? sortBy, // 'deadline' / 'created_at' / 'title'
    bool? sortDesc,
    PageRequest page = const PageRequest(),
  });

  /// 获取任务详情。
  Future<Assignment> getAssignment(String assignmentId);

  /// 教师发布任务。
  Future<Assignment> publishAssignment(AssignmentDraft draft);

  /// 教师保存任务草稿。
  Future<Assignment> saveAssignmentDraft(AssignmentDraft draft);

  /// 教师删除任务。
  Future<void> deleteAssignment(String assignmentId);

  /// 教师查看任务统计。
  Future<AssignmentStats> getAssignmentStats(String assignmentId);

  /// 教师查看任务的学生状态列表(分页 + 筛选)。
  Future<PaginatedResult<StudentStatus>> listAssignmentStudentStatuses(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  });
}

// ===== 提交服务 =====

abstract interface class SubmissionService {
  /// 学生获取自己在某任务下的提交(包括草稿 / 历史)。
  ///
  /// 返回 null 表示尚未提交。
  Future<Submission?> getMySubmission(String assignmentId);

  /// 学生保存草稿(不触发已提交状态)。
  Future<Submission> saveDraft({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  });

  /// 学生正式提交(二次确认由 UI 层处理,服务层只接收最终内容)。
  ///
  /// 若已过 deadline,后端返回 late 状态。
  Future<Submission> submit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  });

  /// 学生重新提交(仅当 allowResubmit=true 时允许)。
  Future<Submission> resubmit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  });

  /// 教师列出任务的所有提交(分页 + 筛选)。
  Future<PaginatedResult<Submission>> listSubmissions(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  });

  /// 教师查看单个提交详情(包括重新提交历史)。
  Future<Submission> getSubmission(String submissionId);

  /// 教师评分 + 评论。
  Future<Submission> gradeSubmission({
    required String submissionId,
    required double grade,
    String? comment,
  });

  /// 教师催交未提交学生(发送提醒)。
  ///
  /// 返回触发的提醒人数。
  Future<int> remindUnsubmitted(String assignmentId);

  /// 上传附件(返回上传后的附件信息)。
  ///
  /// [onProgress] 用于 UI 显示真实上传进度(0~1)。
  /// [cancelToken] 用于取消上传。
  Future<Attachment> uploadAttachment({
    required String assignmentId,
    required List<int> bytes,
    required String filename,
    required String mimeType,
    void Function(double progress)? onProgress,
    CancelToken? cancelToken,
  });
}

// ===== 仪表盘服务 =====

abstract interface class DashboardService {
  /// 学生首页仪表盘。
  Future<StudentDashboard> getStudentDashboard();

  /// 教师工作台仪表盘。
  Future<TeacherDashboard> getTeacherDashboard();

  /// 管理员系统状态(只读视图)。
  Future<AdminSystemStatus> getAdminSystemStatus();
}

// ===== 用户管理服务(管理员) =====

abstract interface class UserManagementService {
  /// 列出所有用户(管理员)。
  Future<PaginatedResult<UserSummary>> listUsers({
    UserRole? role,
    String? search,
    bool? activeOnly,
    PageRequest page = const PageRequest(),
  });

  /// 获取用户详情。
  Future<AppUser> getUser(String userId);

  /// 启用 / 禁用用户。
  Future<UserSummary> setUserActive(String userId, bool active);
}
