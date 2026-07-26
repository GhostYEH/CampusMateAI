import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/mock/mock_data/multi_role_mock_data.dart';
import 'package:campus_companion/mock/mock_services/mock_multi_role_services.dart';

/// Mock 多角色服务单元测试 — 验证 Mock 数据链路完整,
/// 满足 AGENTS.md §10 "Mock 与演示模式" 要求:
/// - 教师 / 学生 / 管理员登录
/// - 三门课程 / 四个班级 / 三十名学生
/// - 通知和任务发布 / 已读未读 / 已交未交 / 逾期
/// - 学生提交 / 教师评分 / 教师统计
void main() {
  group('MockAuthService', () {
    late MockAuthService svc;

    setUp(() => svc = MockAuthService());

    test('student_demo 登录成功,返回学生用户', () async {
      final session = await svc.login(
        const LoginCredentials(
          username: 'student_demo',
          password: 'Demo123456',
        ),
      );
      expect(session.user.role, UserRole.student);
      expect(session.user.id, 'u_student_demo');
      expect(session.user.name, '林知夏');
      expect(session.accessToken, isNotEmpty);
      expect(session.refreshToken, isNotEmpty);
      expect(session.expiresAt.isAfter(DateTime.now()), isTrue);
    });

    test('teacher_demo 登录成功,返回教师用户', () async {
      final session = await svc.login(
        const LoginCredentials(
          username: 'teacher_demo',
          password: 'Demo123456',
        ),
      );
      expect(session.user.role, UserRole.teacher);
      expect(session.user.id, 'u_teacher_demo');
      expect(session.user.name, '张明远');
    });

    test('admin_demo 登录成功,返回管理员用户', () async {
      final session = await svc.login(
        const LoginCredentials(
          username: 'admin_demo',
          password: 'Demo123456',
        ),
      );
      expect(session.user.role, UserRole.admin);
    });

    test('错误密码抛 INVALID_CREDENTIALS', () async {
      expect(
        () => svc.login(
          const LoginCredentials(
            username: 'student_demo',
            password: 'wrong_password',
          ),
        ),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'INVALID_CREDENTIALS')
              .having((e) => e.httpStatus, 'httpStatus', 401),
        ),
      );
    });

    test('未知用户名抛 INVALID_CREDENTIALS', () async {
      expect(
        () => svc.login(
          const LoginCredentials(
            username: 'unknown_user',
            password: 'Demo123456',
          ),
        ),
        throwsA(isA<ApiException>()),
      );
    });

    test('refresh 使用已登录会话返回新 token', () async {
      final session = await svc.login(
        const LoginCredentials(
          username: 'teacher_demo',
          password: 'Demo123456',
        ),
      );
      final refreshed = await svc.refresh(session.refreshToken);
      expect(refreshed.user.id, session.user.id);
      expect(refreshed.accessToken, isNotEmpty);
      // Refresh 后 access_token 应该是新值(包含随机后缀)
      expect(refreshed.accessToken, isNot(equals(session.accessToken)));
    });

    test('未登录时 refresh 抛 INVALID_REFRESH_TOKEN', () async {
      expect(
        () => svc.refresh('non_existent_refresh_token'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'INVALID_REFRESH_TOKEN'),
        ),
      );
    });

    test('logout 后 getCurrentUser 抛 NOT_AUTHENTICATED', () async {
      await svc.login(
        const LoginCredentials(
          username: 'student_demo',
          password: 'Demo123456',
        ),
      );
      await svc.logout('any');
      expect(
        () => svc.getCurrentUser(),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'NOT_AUTHENTICATED'),
        ),
      );
    });

    test('getCurrentUser 在登录后返回当前用户', () async {
      await svc.login(
        const LoginCredentials(
          username: 'admin_demo',
          password: 'Demo123456',
        ),
      );
      final user = await svc.getCurrentUser();
      expect(user.role, UserRole.admin);
    });
  });

  group('MockCourseService', () {
    late MockCourseService svc;

    setUp(() => svc = MockCourseService());

    test('未注入 currentUser 时返回所有课程(admin 行为)', () async {
      final result = await svc.listCourses();
      expect(result.items.length, greaterThanOrEqualTo(3));
      expect(result.total, greaterThanOrEqualTo(3));
    });

    test('学生角色只返回已加入班级所属课程', () async {
      svc.setCurrentUser(MultiRoleMockData.studentDemoUser);
      final result = await svc.listCourses();
      // 学生应能见到至少一门课程
      expect(result.items, isNotEmpty);
      for (final course in result.items) {
        expect(course.classIds, isNotEmpty);
      }
    });

    test('教师角色只返回自己开设的课程', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      final result = await svc.listCourses();
      expect(result.items, isNotEmpty);
      for (final course in result.items) {
        expect(course.teacher.id, MultiRoleMockData.teacherDemoUser.id);
      }
    });

    test('搜索按课程名或代码匹配', () async {
      final result = await svc.listCourses(search: '高');
      // 至少能命中一门课程(高等数学 / 高级编程 等)
      expect(result.total, greaterThanOrEqualTo(1));
    });

    test('getCourse 命中已存在课程,否则抛 COURSE_NOT_FOUND', () async {
      final first = (await svc.listCourses()).items.first;
      final fetched = await svc.getCourse(first.id);
      expect(fetched.id, first.id);

      expect(
        () => svc.getCourse('c_does_not_exist'),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'COURSE_NOT_FOUND'),
        ),
      );
    });

    test('createCourse 创建后可被 listCourses 查到', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      final created = await svc.createCourse(
        code: 'CS_TEST_${DateTime.now().millisecondsSinceEpoch}',
        name: '测试课程',
        semesterId: MultiRoleMockData.currentSemester.id,
        description: '由测试创建',
      );
      expect(created.id, isNotEmpty);
      expect(created.name, '测试课程');

      // 教师视角应能查到这门课
      final list = await svc.listCourses();
      expect(list.items.any((c) => c.id == created.id), isTrue);
    });

    test('listClasses 返回课程下班级', () async {
      final first = (await svc.listCourses()).items.first;
      final classes = await svc.listClasses(first.id);
      expect(classes, isNotEmpty);
      expect(classes.every((c) => c.courseId == first.id), isTrue);
    });
  });

  group('MockDashboardService', () {
    late MockDashboardService svc;

    setUp(() => svc = MockDashboardService());

    test('getStudentDashboard 返回非空学生概览', () async {
      final d = await svc.getStudentDashboard();
      expect(d.totalCourses, greaterThanOrEqualTo(0));
      expect(d.todayCount, greaterThanOrEqualTo(0));
      expect(d.upcomingCount, greaterThanOrEqualTo(0));
      expect(d.overdueCount, greaterThanOrEqualTo(0));
      expect(d.unreadAnnouncementCount, greaterThanOrEqualTo(0));
    });

    test('getTeacherDashboard 在未注入 user 时仍可返回', () async {
      final d = await svc.getTeacherDashboard();
      expect(d.courseCount, greaterThanOrEqualTo(0));
      expect(d.classCount, greaterThanOrEqualTo(0));
      expect(d.studentCount, greaterThanOrEqualTo(0));
      expect(d.pendingSubmissions, greaterThanOrEqualTo(0));
    });

    test('getTeacherDashboard 注入教师后只统计该教师课程', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      final d = await svc.getTeacherDashboard();
      expect(d.courseCount, greaterThan(0));
      // 课程列表只包含当前教师的课程
      for (final c in d.courses) {
        expect(c.teacher.id, MultiRoleMockData.teacherDemoUser.id);
      }
    });

    test('hasAttention 在有待批阅时返回 true', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      final d = await svc.getTeacherDashboard();
      // Mock 数据中至少存在 1 份待批阅提交,故 hasAttention 应为 true
      expect(
        d.hasAttention,
        isTrue,
        reason: 'Mock 数据应保证教师有待批阅 / 未读 / 逾期之一',
      );
    });

    test('getAdminSystemStatus 返回健康状态', () async {
      final status = await svc.getAdminSystemStatus();
      expect(status.isHealthy, isTrue);
      expect(status.totalUsers, greaterThan(0));
      expect(status.totalCourses, greaterThan(0));
      expect(status.totalClasses, greaterThan(0));
    });
  });

  group('Mock 多角色数据完整性', () {
    test('演示账号三个齐全', () {
      expect(MultiRoleMockData.demoAccounts.length, 3);
      final roles = MultiRoleMockData.demoAccounts.map((a) => a.role).toSet();
      expect(roles.contains(UserRole.student), isTrue);
      expect(roles.contains(UserRole.teacher), isTrue);
      expect(roles.contains(UserRole.admin), isTrue);
    });

    test('演示账号密码统一为 Demo123456', () {
      for (final acc in MultiRoleMockData.demoAccounts) {
        expect(acc.password, 'Demo123456');
      }
    });

    test('课程数量 >= 3', () {
      expect(MultiRoleMockData.courses.length, greaterThanOrEqualTo(3));
    });

    test('班级数量 >= 4', () {
      expect(MultiRoleMockData.classes.length, greaterThanOrEqualTo(4));
    });

    test('学生成员总数 >= 30', () {
      final total = MultiRoleMockData.generateClassMembers().length;
      expect(total, greaterThanOrEqualTo(30));
    });

    test('每个课程至少有一个班级', () {
      for (final course in MultiRoleMockData.courses) {
        expect(
          course.classIds,
          isNotEmpty,
          reason: '课程 ${course.name} 应至少有一个班级',
        );
      }
    });

    test('每个班级都关联到存在的课程', () {
      final courseIds = MultiRoleMockData.courses.map((c) => c.id).toSet();
      for (final cls in MultiRoleMockData.classes) {
        expect(
          courseIds.contains(cls.courseId),
          isTrue,
          reason: '班级 ${cls.name} 关联的课程 ${cls.courseId} 不存在',
        );
      }
    });
  });

  // ===========================================================================
  // CourseService 扩展:createClass / resetInviteCode / joinByInviteCode /
  //                       listClassMembers / updateCourse
  // 对应 AGENTS.md §11: 创建课程和班级测试、邀请码加入班级测试
  // ===========================================================================
  group('MockCourseService - 班级与成员', () {
    late MockCourseService svc;
    late AppUser teacher;

    setUp(() {
      svc = MockCourseService();
      teacher = MultiRoleMockData.teacherDemoUser;
      svc.setCurrentUser(teacher);
    });

    test('createClass 创建班级并生成邀请码', () async {
      const courseId = 'c_hm001';
      final cls = await svc.createClass(
        courseId: courseId,
        name: '测试班级-邀请码',
        year: '2024级',
        major: '计算机科学与技术',
      );
      expect(cls.id, isNotEmpty);
      expect(cls.courseId, courseId);
      expect(cls.name, '测试班级-邀请码');
      expect(cls.inviteCode, isNotEmpty);
      expect(cls.teacherId, teacher.id);
      expect(cls.teacherName, teacher.name);

      // listClasses 应包含新建班级
      final classes = await svc.listClasses(courseId);
      expect(classes.any((c) => c.id == cls.id), isTrue);
    });

    test('resetInviteCode 生成新邀请码,旧邀请码失效', () async {
      const classId = 'cl_hm001_1';
      final beforeClasses = await svc.listClasses('c_hm001');
      final before = beforeClasses.firstWhere((c) => c.id == classId);
      final oldCode = before.inviteCode;

      final updated = await svc.resetInviteCode(classId);
      expect(updated.id, classId);
      expect(updated.inviteCode, isNot(equals(oldCode)));

      // 验证旧邀请码不能再加入
      expect(
        () => svc.joinByInviteCode(oldCode),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'INVALID_INVITE_CODE'),
        ),
      );
    });

    test('joinByInviteCode 用有效邀请码加入班级', () async {
      const inviteCode = 'HM-A1X4'; // 来自 cl_hm001_1
      final cls = await svc.joinByInviteCode(inviteCode);
      expect(cls.id, 'cl_hm001_1');
      expect(cls.inviteCode, inviteCode);
    });

    test('joinByInviteCode 用无效邀请码抛 INVALID_INVITE_CODE', () async {
      expect(
        () => svc.joinByInviteCode('INVALID-CODE-XYZ'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'INVALID_INVITE_CODE'),
        ),
      );
    });

    test('listClassMembers 按搜索/年级/专业/提交状态筛选', () async {
      const classId = 'cl_hm001_1';
      final all = await svc.listClassMembers(classId);
      expect(all.items, isNotEmpty);

      // 搜索筛选
      final searched = await svc.listClassMembers(classId, search: '林');
      expect(searched.items, isNotEmpty);
      expect(
        searched.items.every((m) => m.name.contains('林')),
        isTrue,
      );

      // 年级筛选
      final byGrade = await svc.listClassMembers(classId, grade: '2024级');
      expect(byGrade.items.every((m) => m.grade == '2024级'), isTrue);

      // 提交状态筛选 — 已提交
      final submitted = await svc.listClassMembers(
        classId,
        submissionStatus: 'submitted',
      );
      expect(
        submitted.items.every((m) => m.assignmentSubmittedCount > 0),
        isTrue,
      );

      // 提交状态筛选 — 逾期
      final overdue = await svc.listClassMembers(
        classId,
        submissionStatus: 'overdue',
      );
      expect(
        overdue.items.every((m) => m.assignmentOverdueCount > 0),
        isTrue,
      );
    });

    test('updateCourse 修改课程名/描述/学分/颜色', () async {
      const courseId = 'c_hm001';
      final updated = await svc.updateCourse(
        courseId,
        name: '更新后的课程名',
        description: '新描述',
        creditHours: 4,
        color: 0xFFAA8855,
      );
      expect(updated.name, '更新后的课程名');
      expect(updated.description, '新描述');
      expect(updated.creditHours, 4);
      expect(updated.color, 0xFFAA8855);
    });

    test('updateCourse 不存在的课程抛 COURSE_NOT_FOUND', () async {
      expect(
        () => svc.updateCourse('c_nonexistent', name: 'X'),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'COURSE_NOT_FOUND'),
        ),
      );
    });

    test('listClassMembers 不存在的班级返回空列表', () async {
      final result = await svc.listClassMembers('cl_nonexistent');
      expect(result.items, isEmpty);
    });
  });

  // ===========================================================================
  // AnnouncementService — 通知发布、已读、未读、列表筛选
  // 对应 AGENTS.md §11: 发布通知测试、已读未读状态测试
  // ===========================================================================
  group('MockAnnouncementService', () {
    late MockAnnouncementService svc;

    setUp(() => svc = MockAnnouncementService());

    test('listAnnouncements 返回指定班级的通知', () async {
      const classId = 'cl_hm001_1';
      final result = await svc.listAnnouncements(classId);
      expect(result.items, isNotEmpty);
      expect(result.items.every((a) => a.classId == classId), isTrue);
    });

    test('listAnnouncements unreadOnly=true 只返回未读', () async {
      const classId = 'cl_hm001_1';
      // 先全部标记已读
      final all = await svc.listAnnouncements(classId);
      for (final a in all.items) {
        await svc.markRead(a.id);
      }

      // unreadOnly 应返回空
      final unread = await svc.listAnnouncements(classId, unreadOnly: true);
      expect(unread.items, isEmpty);

      // 不带筛选应有全部
      final allAgain = await svc.listAnnouncements(classId);
      expect(allAgain.items.every((a) => a.read), isTrue);
    });

    test('listAnnouncements 按搜索关键词筛选', () async {
      const classId = 'cl_hm001_1';
      final searched = await svc.listAnnouncements(
        classId,
        search: '作业',
      );
      expect(
        searched.items.every(
          (a) => a.title.contains('作业') || a.content.contains('作业'),
        ),
        isTrue,
      );
    });

    test('getAnnouncement 自动标记已读(不允许伪造已读状态)', () async {
      const announcementId = 'an_hm_001';
      final before = await svc.listAnnouncements('cl_hm001_1');
      final original = before.items.firstWhere((a) => a.id == announcementId);
      expect(original.read, isFalse); // 初始未读

      // getAnnouncement 应自动调用 markRead
      final after = await svc.getAnnouncement(announcementId);
      expect(after.read, isTrue);
      expect(after.readCount, greaterThan(original.readCount));
    });

    test('markRead 多次调用幂等(不重复增加 readCount)', () async {
      // 选用初始 read=false 的通知 an_ds_001,避免初始已读状态干扰
      const announcementId = 'an_ds_001';
      final before = await svc.getAnnouncement(announcementId);
      final readCountBefore = before.readCount;

      // 重复调用 markRead 不应再增加 readCount(_readIds 已包含)
      await svc.markRead(announcementId);
      await svc.markRead(announcementId);
      final after = await svc.getAnnouncement(announcementId);
      expect(after.readCount, readCountBefore);
    });

    test('publishAnnouncement 教师发布通知后出现在列表中', () async {
      const classId = 'cl_hm001_1';
      const courseId = 'c_hm001';
      const draft = AnnouncementDraft(
        classIds: [classId],
        courseId: courseId,
        title: '测试发布的通知标题',
        content: '测试发布的通知正文内容',
        importance: NoticeImportance.urgent,
        attachments: [],
        tags: ['测试'],
        isDraft: false,
        useAiPrefill: false,
      );

      final published = await svc.publishAnnouncement(draft);
      expect(published.id, isNotEmpty);
      expect(published.title, '测试发布的通知标题');
      expect(published.classId, classId);
      expect(published.importance, NoticeImportance.urgent);

      // 列表中应能查到
      final list = await svc.listAnnouncements(classId);
      expect(list.items.any((a) => a.id == published.id), isTrue);
    });

    test('saveAnnouncementDraft 保存草稿不出现在已发布列表', () async {
      const classId = 'cl_hm001_1';
      const courseId = 'c_hm001';
      const draft = AnnouncementDraft(
        classIds: [classId],
        courseId: courseId,
        title: '草稿通知标题',
        content: '草稿内容',
        importance: NoticeImportance.normal,
        attachments: [],
        tags: [],
        isDraft: true,
        useAiPrefill: false,
      );

      final saved = await svc.saveAnnouncementDraft(draft);
      expect(saved.id, isNotEmpty);

      // 草稿不应出现在学生列表中(后端应过滤 isDraft)
      final list = await svc.listAnnouncements(classId);
      expect(list.items.any((a) => a.id == saved.id), isFalse);
    });

    test('deleteAnnouncement 删除后列表不再包含', () async {
      const classId = 'cl_hm001_1';
      final before = await svc.listAnnouncements(classId);
      expect(before.items, isNotEmpty);
      final target = before.items.first;

      await svc.deleteAnnouncement(target.id);

      final after = await svc.listAnnouncements(classId);
      expect(after.items.any((a) => a.id == target.id), isFalse);
    });

    test('getAnnouncement 不存在的 ID 抛 ANNOUNCEMENT_NOT_FOUND', () async {
      expect(
        () => svc.getAnnouncement('an_nonexistent'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'ANNOUNCEMENT_NOT_FOUND'),
        ),
      );
    });

    test('listStudentAnnouncements 聚合学生所有班级通知', () async {
      final result = await svc.listStudentAnnouncements();
      expect(result.items, isNotEmpty);
      // 学生视角应只包含其已加入班级的通知
      final studentClassIds = MultiRoleMockData.studentJoinedClassIds.toSet();
      expect(
        result.items.every((a) => studentClassIds.contains(a.classId)),
        isTrue,
      );
    });
  });

  // ===========================================================================
  // AssignmentService — 任务发布、列表、统计、学生状态
  // 对应 AGENTS.md §11: 发布任务测试、逾期状态测试
  // ===========================================================================
  group('MockAssignmentService', () {
    late MockAssignmentService svc;

    setUp(() => svc = MockAssignmentService());

    test('listAssignments 返回班级任务列表', () async {
      const classId = 'cl_hm001_1';
      final result = await svc.listAssignments(classId);
      expect(result.items, isNotEmpty);
      expect(result.items.every((a) => a.classId == classId), isTrue);
    });

    test('listAssignments 按 status 筛选逾期任务', () async {
      const classId = 'cl_hm001_1';
      final overdue = await svc.listAssignments(
        classId,
        status: 'overdue',
      );
      // 逾期任务应满足 isOverdue=true
      expect(overdue.items.every((a) => a.isOverdue), isTrue);
    });

    test('listAssignments 按 search 关键词筛选', () async {
      const classId = 'cl_hm001_1';
      final searched = await svc.listAssignments(
        classId,
        search: '极限',
      );
      expect(
        searched.items.every(
          (a) => a.title.contains('极限') || a.description.contains('极限'),
        ),
        isTrue,
      );
    });

    test('getAssignment 返回任务详情', () async {
      const assignmentId = 'as_hm_hw1';
      final a = await svc.getAssignment(assignmentId);
      expect(a.id, assignmentId);
      expect(a.title, isNotEmpty);
    });

    test('getAssignment 不存在的 ID 抛 ASSIGNMENT_NOT_FOUND', () async {
      expect(
        () => svc.getAssignment('as_nonexistent'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'ASSIGNMENT_NOT_FOUND'),
        ),
      );
    });

    test('publishAssignment 教师发布任务后出现在列表中', () async {
      const classId = 'cl_hm001_1';
      const courseId = 'c_hm001';
      final deadline = DateTime.now().add(const Duration(days: 7));
      final draft = AssignmentDraft(
        classId: classId,
        courseId: courseId,
        title: '测试发布任务标题',
        description: '测试发布任务描述',
        deadline: deadline,
        attachments: const [],
        submissionType: SubmissionType.text,
        allowResubmit: true,
        maxScore: 100,
        reminderLeadMinutes: 60,
        hasReminder: true,
        isDraft: false,
      );

      final published = await svc.publishAssignment(draft);
      expect(published.id, isNotEmpty);
      expect(published.title, '测试发布任务标题');
      expect(published.classId, classId);
      expect(published.allowResubmit, isTrue);
      expect(published.maxScore, 100);

      // 列表应能查到
      final list = await svc.listAssignments(classId);
      expect(list.items.any((a) => a.id == published.id), isTrue);
    });

    test('getAssignmentStats 返回任务统计数据', () async {
      const assignmentId = 'as_hm_hw2';
      final stats = await svc.getAssignmentStats(assignmentId);
      expect(stats.assignmentId, assignmentId);
      expect(stats.total, greaterThan(0));
      expect(stats.submitted, lessThanOrEqualTo(stats.total));
      expect(stats.graded, lessThanOrEqualTo(stats.submitted));
      // 提交率应在 0-1 之间
      expect(stats.submissionRate, inInclusiveRange(0.0, 1.0));
    });

    test('listAssignmentStudentStatuses 返回学生状态列表', () async {
      const assignmentId = 'as_hm_hw2';
      final result = await svc.listAssignmentStudentStatuses(assignmentId);
      expect(result.items, isNotEmpty);
      // 每个 status 应有 studentId 和 name
      expect(result.items.every((s) => s.studentId.isNotEmpty), isTrue);
      expect(result.items.every((s) => s.name.isNotEmpty), isTrue);
    });

    test('listAssignmentStudentStatuses 按 status 筛选已提交', () async {
      const assignmentId = 'as_hm_hw2';
      final submitted = await svc.listAssignmentStudentStatuses(
        assignmentId,
        status: 'submitted',
      );
      expect(
        submitted.items.every((s) => s.status == SubmissionStatus.submitted),
        isTrue,
      );
    });

    test('deleteAssignment 删除后列表不再包含', () async {
      const classId = 'cl_hm001_1';
      final before = await svc.listAssignments(classId);
      final target = before.items.first;
      await svc.deleteAssignment(target.id);
      final after = await svc.listAssignments(classId);
      expect(after.items.any((a) => a.id == target.id), isFalse);
    });

    test('listStudentAssignments 学生视角聚合所有课程任务', () async {
      final result = await svc.listStudentAssignments();
      expect(result.items, isNotEmpty);
    });

    test('listStudentAssignments sortBy=deadline 按 deadline 升序', () async {
      final result = await svc.listStudentAssignments(
        sortBy: 'deadline',
        sortDesc: false,
      );
      final deadlines = result.items.map((a) => a.deadline).toList();
      for (int i = 1; i < deadlines.length; i++) {
        expect(
          deadlines[i].isAfter(deadlines[i - 1]) ||
              deadlines[i].isAtSameMomentAs(deadlines[i - 1]),
          isTrue,
        );
      }
    });
  });

  // ===========================================================================
  // SubmissionService — 草稿、提交、重新提交、评分、催交
  // 对应 AGENTS.md §11: 学生保存草稿和提交测试、教师查看提交和评分测试
  // ===========================================================================
  group('MockSubmissionService', () {
    late MockSubmissionService svc;

    setUp(() {
      svc = MockSubmissionService();
      svc.setCurrentUser(MultiRoleMockData.studentDemoUser);
    });

    test('getMySubmission 未提交时返回 null', () async {
      // 用一个不存在的 assignmentId 查询
      final result = await svc.getMySubmission('as_nonexistent');
      expect(result, isNull);
    });

    test('saveDraft 保存草稿后状态为 draft', () async {
      const assignmentId = 'as_hm_hw3'; // 未过截止的任务
      final draft = await svc.saveDraft(
        assignmentId: assignmentId,
        content: '这是草稿内容',
      );
      expect(draft.status, SubmissionStatus.draft);
      expect(draft.content, '这是草稿内容');

      // getMySubmission 应能查到
      final my = await svc.getMySubmission(assignmentId);
      expect(my, isNotNull);
      expect(my!.status, SubmissionStatus.draft);
    });

    test('saveDraft 多次调用更新同一草稿(不创建新记录)', () async {
      const assignmentId = 'as_hm_hw3';
      final first = await svc.saveDraft(
        assignmentId: assignmentId,
        content: '第一版草稿',
      );
      final second = await svc.saveDraft(
        assignmentId: assignmentId,
        content: '第二版草稿',
      );
      expect(second.id, first.id);
      expect(second.content, '第二版草稿');
    });

    test('submit 正式提交后状态为 submitted', () async {
      const assignmentId = 'as_hm_hw3';
      final submission = await svc.submit(
        assignmentId: assignmentId,
        content: '正式提交内容',
      );
      expect(submission.status, SubmissionStatus.submitted);
      expect(submission.content, '正式提交内容');
      expect(submission.submittedAt, isNotNull);
    });

    test('submit 过截止时间后状态为 late', () async {
      // as_hm_hw1 的 deadline 是 now - 7 天(已逾期)
      const assignmentId = 'as_hm_hw1';
      final submission = await svc.submit(
        assignmentId: assignmentId,
        content: '逾期提交',
      );
      expect(submission.isLate, isTrue);
    });

    test('resubmit 已提交任务可重新提交(当 allowResubmit=true)', () async {
      const assignmentId = 'as_hm_hw3';
      // 先正式提交
      await svc.submit(
        assignmentId: assignmentId,
        content: '首次提交',
      );
      // 重新提交
      final resub = await svc.resubmit(
        assignmentId: assignmentId,
        content: '修改后的内容',
      );
      expect(resub.content, '修改后的内容');
      expect(resub.resubmissionCount, greaterThan(0));
    });

    test('listSubmissions 教师视角查看任务所有提交', () async {
      // 切换到教师视角
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      const assignmentId = 'as_hm_hw2';
      final result = await svc.listSubmissions(assignmentId);
      expect(result.items, isNotEmpty);
      expect(result.items.every((s) => s.assignmentId == assignmentId), isTrue);
    });

    test('listSubmissions 按状态筛选 submitted', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      const assignmentId = 'as_hm_hw2';
      final result = await svc.listSubmissions(
        assignmentId,
        status: 'submitted',
      );
      expect(
        result.items.every((s) => s.status == SubmissionStatus.submitted),
        isTrue,
      );
    });

    test('listSubmissions 按学生姓名/学号搜索', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      const assignmentId = 'as_hm_hw2';
      // 取一个已知学生姓名(从 generateHw2Submissions)
      final all = await svc.listSubmissions(assignmentId);
      expect(all.items, isNotEmpty);
      final firstName = all.items.first.studentName;
      final searched = await svc.listSubmissions(
        assignmentId,
        search: firstName,
      );
      expect(
        searched.items.every((s) => s.studentName.contains(firstName)),
        isTrue,
      );
    });

    test('gradeSubmission 教师评分后状态为 graded', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      const assignmentId = 'as_hm_hw2';
      final list = await svc.listSubmissions(assignmentId);
      final target = list.items.firstWhere(
        (s) => s.status != SubmissionStatus.graded,
        orElse: () => list.items.first,
      );

      final graded = await svc.gradeSubmission(
        submissionId: target.id,
        grade: 88.5,
        comment: '论述清晰,可进一步深化分析。',
      );
      expect(graded.status, SubmissionStatus.graded);
      expect(graded.grade, 88.5);
      expect(graded.comment, contains('论述清晰'));
      expect(graded.gradedAt, isNotNull);
      expect(graded.gradedBy, MultiRoleMockData.teacherDemoUser.id);
    });

    test('gradeSubmission 不存在的 submissionId 抛异常', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      expect(
        () => svc.gradeSubmission(
          submissionId: 'sub_nonexistent',
          grade: 80,
        ),
        throwsA(isA<ApiException>()),
      );
    });

    test('remindUnsubmitted 返回被提醒的学生数', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      const assignmentId = 'as_hm_hw2';
      final count = await svc.remindUnsubmitted(assignmentId);
      expect(count, greaterThanOrEqualTo(0));
    });

    test('getSubmission 教师查看单个提交详情', () async {
      svc.setCurrentUser(MultiRoleMockData.teacherDemoUser);
      const assignmentId = 'as_hm_hw2';
      final list = await svc.listSubmissions(assignmentId);
      final first = list.items.first;
      final detail = await svc.getSubmission(first.id);
      expect(detail.id, first.id);
      expect(detail.assignmentId, first.assignmentId);
      expect(detail.studentId, first.studentId);
    });
  });

  // ===========================================================================
  // UserManagementService — 管理员用户管理
  // ===========================================================================
  group('MockUserManagementService', () {
    late MockUserManagementService svc;

    setUp(() => svc = MockUserManagementService());

    test('listUsers 返回用户列表', () async {
      final result = await svc.listUsers();
      expect(result.items, isNotEmpty);
    });

    test('listUsers 按角色筛选教师', () async {
      final result = await svc.listUsers(role: UserRole.teacher);
      expect(result.items.every((u) => u.role == UserRole.teacher), isTrue);
    });

    test('listUsers 按角色筛选学生', () async {
      final result = await svc.listUsers(role: UserRole.student);
      expect(result.items.every((u) => u.role == UserRole.student), isTrue);
    });

    test('listUsers 按搜索关键词匹配', () async {
      final result = await svc.listUsers(search: '张');
      expect(
        result.items.every(
          (u) => u.name.contains('张') || (u.username?.contains('张') ?? false),
        ),
        isTrue,
      );
    });

    test('setUserActive 切换用户激活状态', () async {
      final users = await svc.listUsers();
      final target = users.items.first;
      final updated = await svc.setUserActive(target.id, !target.isActive);
      expect(updated.isActive, !target.isActive);
    });

    test('getUser 获取用户详情', () async {
      final users = await svc.listUsers();
      final target = users.items.first;
      final detail = await svc.getUser(target.id);
      expect(detail.id, target.id);
    });
  });

  // ===========================================================================
  // 分页与一致性
  // 对应 AGENTS.md §11: 分页测试
  // ===========================================================================
  group('分页与一致性', () {
    test('PageRequest 默认值 page=1, pageSize=20', () {
      const req = PageRequest();
      expect(req.page, 1);
      expect(req.pageSize, 20);
    });

    test('PageRequest.next() 返回下一页', () {
      const req = PageRequest();
      final next = req.next();
      expect(next.page, 2);
      expect(next.pageSize, 20);
    });

    test('PageRequest.reset() 回到第一页', () {
      const req = PageRequest(page: 5);
      final reset = req.reset();
      expect(reset.page, 1);
    });

    test('PaginatedResult.empty 返回空结果', () {
      final empty = PaginatedResult.empty<int>();
      expect(empty.items, isEmpty);
      expect(empty.total, 0);
      expect(empty.hasMore, isFalse);
    });

    test('PaginatedResult.canLoadMore 在有更多时为 true', () {
      const result = PaginatedResult<int>(
        items: [1, 2, 3],
        total: 10,
        page: 1,
        pageSize: 3,
        hasMore: true,
      );
      expect(result.canLoadMore, isTrue);
    });

    test('MockCourseService 分页正常工作', () async {
      final svc = MockCourseService();
      // admin 视角返回所有课程
      final page1 =
          await svc.listCourses(page: const PageRequest(page: 1, pageSize: 2));
      expect(page1.items.length, lessThanOrEqualTo(2));
      if (page1.hasMore) {
        final page2 = await svc.listCourses(
          page: const PageRequest(page: 2, pageSize: 2),
        );
        expect(page2.items, isNotEmpty);
        // 第 2 页的项不应与第 1 页重复
        final page1Ids = page1.items.map((c) => c.id).toSet();
        expect(page2.items.every((c) => !page1Ids.contains(c.id)), isTrue);
      }
    });
  });
}
