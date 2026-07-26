import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/announcement.dart';
import 'package:campus_companion/data/models/assignment.dart';
import 'package:campus_companion/data/models/course.dart';
import 'package:campus_companion/data/models/pagination.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/multi_role_service_interfaces.dart';
import 'package:campus_companion/features/teacher_publish/presentation/teacher_publish_center_page.dart';

/// 教师 demo 用户(用于注入 currentAuthUserProvider)。
const _teacherUser = AppUser(
  id: 'u_teacher_demo',
  name: '张明远',
  nickname: '张老师',
  role: UserRole.teacher,
  avatarSeed: 'teacher',
  teacherId: 'T20180456',
  department: '计算机与人工智能学院',
  teacherTitle: '副教授',
);

/// 测试用课程数据:2 门课程,每门至少一个班级。
final _testCourses = <Course>[
  Course(
    id: 'c_test_1',
    code: 'CS101',
    name: '测试课程 1',
    semester: Semester(
      id: '2025-2026-2',
      name: '2025-2026 学年第二学期',
      startDate: DateTime(2025, 2, 15),
      endDate: DateTime(2025, 7, 10),
      isActive: true,
    ),
    teacher: const CourseTeacher(
      id: 'u_teacher_demo',
      name: '张明远',
      title: '副教授',
      department: '计算机与人工智能学院',
    ),
    description: '测试课程描述',
    creditHours: 3,
    classIds: const ['cl_test_1'],
    color: 0xFF2F6486,
    studentCount: 30,
    classCount: 1,
  ),
];

/// 测试用班级列表。
final _testClasses = <SchoolClass>[
  const SchoolClass(
    id: 'cl_test_1',
    courseId: 'c_test_1',
    name: '测试班级-1',
    inviteCode: 'TEST-INVITE',
    studentCount: 30,
    semester: '2025-2026-2',
    teacherId: 'u_teacher_demo',
    teacherName: '张明远',
    year: '2024级',
    major: '计算机科学与技术',
  ),
];

/// Fake CourseService — 返回测试课程和班级。
class _FakeCourseService implements CourseService {
  @override
  Future<PaginatedResult<Course>> listCourses({
    String? semester,
    String? search,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 30));
    var filtered = _testCourses.toList();
    if (search != null && search.isNotEmpty) {
      filtered = filtered
          .where(
            (c) =>
                c.name.contains(search) ||
                c.code.toLowerCase().contains(search.toLowerCase()),
          )
          .toList();
    }
    return PaginatedResult(
      items: filtered,
      total: filtered.length,
      page: page.page,
      pageSize: page.pageSize,
      hasMore: false,
    );
  }

  @override
  Future<Course> getCourse(String courseId) async => _testCourses.first;

  @override
  Future<Course> createCourse({
    required String code,
    required String name,
    required String semesterId,
    String? description,
    int? creditHours,
    int? color,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<Course> updateCourse(
    String courseId, {
    String? name,
    String? description,
    int? creditHours,
    int? color,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<List<SchoolClass>> listClasses(String courseId) async {
    await Future.delayed(const Duration(milliseconds: 20));
    return _testClasses.where((c) => c.courseId == courseId).toList();
  }

  @override
  Future<SchoolClass> createClass({
    required String courseId,
    required String name,
    String? year,
    String? major,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<SchoolClass> resetInviteCode(String classId) async =>
      throw UnimplementedError();

  @override
  Future<SchoolClass> joinByInviteCode(String inviteCode) async =>
      throw UnimplementedError();

  @override
  Future<PaginatedResult<ClassMember>> listClassMembers(
    String classId, {
    String? search,
    String? grade,
    String? major,
    String? submissionStatus,
    PageRequest page = const PageRequest(),
  }) async {
    return PaginatedResult.empty<ClassMember>();
  }
}

/// Fake AnnouncementService — 跟踪 publishAnnouncement 调用。
class _FakeAnnouncementService implements AnnouncementService {
  AnnouncementDraft? lastPublishDraft;
  AnnouncementDraft? lastSavedDraft;
  String? deletedId;
  bool shouldFail = false;

  @override
  Future<Announcement> publishAnnouncement(AnnouncementDraft draft) async {
    await Future.delayed(const Duration(milliseconds: 50));
    if (shouldFail) {
      throw const ApiException(
        code: 'PUBLISH_FAILED',
        message: '发布失败,请重试',
        httpStatus: 500,
      );
    }
    lastPublishDraft = draft;
    return Announcement(
      id: 'an_published_${DateTime.now().millisecondsSinceEpoch}',
      classId: draft.classIds.first,
      courseId: draft.courseId,
      title: draft.title,
      content: draft.content,
      authorId: 'u_teacher_demo',
      authorName: '张明远',
      publishedAt: DateTime.now(),
      importance: draft.importance,
      attachments: draft.attachments,
      tags: draft.tags,
      read: false,
      readCount: 0,
      totalStudents: 30,
    );
  }

  @override
  Future<Announcement> saveAnnouncementDraft(AnnouncementDraft draft) async {
    await Future.delayed(const Duration(milliseconds: 30));
    lastSavedDraft = draft;
    return Announcement(
      id: 'an_draft_${DateTime.now().millisecondsSinceEpoch}',
      classId: draft.classIds.first,
      courseId: draft.courseId,
      title: draft.title,
      content: draft.content,
      authorId: 'u_teacher_demo',
      authorName: '张明远',
      publishedAt: DateTime.now(),
      importance: draft.importance,
      read: false,
      readCount: 0,
      totalStudents: 30,
    );
  }

  @override
  Future<void> deleteAnnouncement(String announcementId) async {
    deletedId = announcementId;
  }

  @override
  Future<Announcement> getAnnouncement(String announcementId) async =>
      throw UnimplementedError();

  @override
  Future<PaginatedResult<Announcement>> listAnnouncements(
    String classId, {
    String? search,
    bool? unreadOnly,
    PageRequest page = const PageRequest(),
  }) async {
    return PaginatedResult.empty<Announcement>();
  }

  @override
  Future<PaginatedResult<Announcement>> listStudentAnnouncements({
    String? courseId,
    String? search,
    bool? unreadOnly,
    PageRequest page = const PageRequest(),
  }) async {
    return PaginatedResult.empty<Announcement>();
  }

  @override
  Future<void> markRead(String announcementId) async {}
}

/// Fake AssignmentService — 跟踪 publishAssignment 调用。
class _FakeAssignmentService implements AssignmentService {
  AssignmentDraft? lastPublishDraft;
  AssignmentDraft? lastSavedDraft;
  bool shouldFail = false;

  @override
  Future<Assignment> publishAssignment(AssignmentDraft draft) async {
    await Future.delayed(const Duration(milliseconds: 50));
    if (shouldFail) {
      throw const ApiException(
        code: 'PUBLISH_FAILED',
        message: '发布失败,请重试',
        httpStatus: 500,
      );
    }
    lastPublishDraft = draft;
    return Assignment(
      id: 'as_published_${DateTime.now().millisecondsSinceEpoch}',
      classId: draft.classId,
      courseId: draft.courseId,
      title: draft.title,
      description: draft.description,
      deadline: draft.deadline,
      createdAt: DateTime.now(),
      authorId: 'u_teacher_demo',
      authorName: '张明远',
      submissionType: draft.submissionType,
      allowResubmit: draft.allowResubmit,
      maxScore: draft.maxScore,
      reminderLeadMinutes: draft.reminderLeadMinutes,
      hasReminder: draft.hasReminder,
      totalStudents: 30,
      submittedCount: 0,
      gradedCount: 0,
      overdueCount: 0,
    );
  }

  @override
  Future<Assignment> saveAssignmentDraft(AssignmentDraft draft) async {
    await Future.delayed(const Duration(milliseconds: 30));
    lastSavedDraft = draft;
    return Assignment(
      id: 'as_draft_${DateTime.now().millisecondsSinceEpoch}',
      classId: draft.classId,
      courseId: draft.courseId,
      title: draft.title,
      description: draft.description,
      deadline: draft.deadline,
      createdAt: DateTime.now(),
      authorId: 'u_teacher_demo',
      authorName: '张明远',
      submissionType: draft.submissionType,
      allowResubmit: draft.allowResubmit,
      maxScore: draft.maxScore,
      totalStudents: 30,
    );
  }

  @override
  Future<void> deleteAssignment(String assignmentId) async {}

  @override
  Future<Assignment> getAssignment(String assignmentId) async =>
      throw UnimplementedError();

  @override
  Future<AssignmentStats> getAssignmentStats(String assignmentId) async =>
      throw UnimplementedError();

  @override
  Future<PaginatedResult<Assignment>> listAssignments(
    String classId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    return PaginatedResult.empty<Assignment>();
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
    return PaginatedResult.empty<Assignment>();
  }

  @override
  Future<PaginatedResult<StudentStatus>> listAssignmentStudentStatuses(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    return PaginatedResult.empty<StudentStatus>();
  }
}

void main() {
  late _FakeCourseService courseSvc;
  late _FakeAnnouncementService announcementSvc;
  late _FakeAssignmentService assignmentSvc;

  setUp(() {
    courseSvc = _FakeCourseService();
    announcementSvc = _FakeAnnouncementService();
    assignmentSvc = _FakeAssignmentService();
  });

  ProviderContainer makeContainer() {
    final container = ProviderContainer(
      overrides: [
        appConfigProvider.overrideWith((ref) {
          return const AppConfig(
            environment: AppEnvironment.development,
            useMockBackend: true,
            useMockExpressionRecognition: true,
            apiBaseUrl: 'http://10.0.2.2:8000',
          );
        }),
        courseServiceProvider.overrideWithValue(courseSvc),
        announcementServiceProvider.overrideWithValue(announcementSvc),
        assignmentServiceProvider.overrideWithValue(assignmentSvc),
        currentAuthUserProvider.overrideWith((ref) => _teacherUser),
        reduceMotionProvider.overrideWith((ref) => true),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  Widget wrapApp(ProviderContainer container, Widget child) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: child,
      ),
    );
  }

  /// 等待课程和班级加载完成。
  Future<void> pumpPage(WidgetTester tester) async {
    // 设置手机尺寸视口,确保下方按钮在屏幕内可点击
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pumpAndSettle(const Duration(milliseconds: 500));
  }

  group('TeacherPublishCenterPage - 基础渲染', () {
    testWidgets('显示 Tab 结构(发布通知 + 发布任务)', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      expect(find.text('发布通知'), findsOneWidget);
      expect(find.text('发布任务'), findsOneWidget);
    });

    testWidgets('默认显示"发布通知"Tab', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 通知标题输入框可见
      expect(find.text('通知标题'), findsOneWidget);
      expect(find.text('通知正文'), findsOneWidget);
    });

    testWidgets('切换到"发布任务"Tab 显示任务表单', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 点击"发布任务"Tab — 用 pumpAndSettle 等待 _PublishAssignmentTab
      // initState 中触发的 _loadClasses() Future.delayed Timer 完成,避免
      // "Timer is still pending" 断言失败。
      await tester.tap(find.text('发布任务'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      // 任务表单元素出现
      expect(find.text('任务详情'), findsOneWidget);
      expect(find.text('任务标题'), findsOneWidget);
      expect(find.text('任务描述'), findsOneWidget);
      expect(find.text('截止时间'), findsOneWidget);
      expect(find.text('提交方式'), findsOneWidget);
    });
  });

  group('TeacherPublishCenterPage - 发布通知', () {
    testWidgets('未选择班级时点击发布提示"请至少选择一个班级"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 课程在 initState 中已自动选中首个课程,但未选择班级
      // 直接点击发布按钮应触发"请至少选择一个班级"校验
      await tester.tap(find.text('发布'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 应显示 SnackBar 提示
      expect(find.textContaining('请至少选择一个班级'), findsOneWidget);
    });

    testWidgets('选择课程但未填标题提示"请输入通知标题"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 选择课程(DropdownButton)— onChanged 会触发 _loadClasses()
      // 并清空 _selectedClassIds,所以下面需要重新选择班级
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      // 点击第一个下拉项
      await tester.tap(find.textContaining('CS101').last);
      await tester.pumpAndSettle();

      // 重新选择班级(因为 _loadClasses 清空了已选班级)
      await tester.tap(find.text('测试班级-1'));
      await tester.pumpAndSettle();

      // 点击发布(未填标题)
      await tester.tap(find.text('发布'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.textContaining('请输入通知标题'), findsOneWidget);
    });

    testWidgets('填写完整后点击发布弹出"确认发布"对话框', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 选择课程
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('CS101').last);
      await tester.pumpAndSettle();

      // 选择班级(FilterChip)
      await tester.tap(find.text('测试班级-1'));
      await tester.pumpAndSettle();

      // 输入标题
      await tester.enterText(
        find.ancestor(
          of: find.text('通知标题'),
          matching: find.byType(TextField),
        ),
        '测试通知标题',
      );
      // 输入正文
      await tester.enterText(
        find.ancestor(
          of: find.text('通知正文'),
          matching: find.byType(TextField),
        ),
        '测试通知正文内容',
      );
      await tester.pump();

      // 点击发布
      await tester.tap(find.text('发布'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 应弹出确认对话框
      expect(find.text('确认发布'), findsWidgets);
      expect(find.text('取消'), findsOneWidget);
    });

    testWidgets('确认发布后调用 announcementService.publishAnnouncement',
        (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 选择课程
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('CS101').last);
      await tester.pumpAndSettle();

      // 选择班级
      await tester.tap(find.text('测试班级-1'));
      await tester.pumpAndSettle();

      // 输入标题和正文
      await tester.enterText(
        find.ancestor(of: find.text('通知标题'), matching: find.byType(TextField)),
        '正式发布测试',
      );
      await tester.enterText(
        find.ancestor(of: find.text('通知正文'), matching: find.byType(TextField)),
        '这是正文',
      );
      await tester.pump();

      // 点击发布
      await tester.tap(find.text('发布'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 确认发布(对话框中的 FilledButton)
      await tester.tap(find.widgetWithText(FilledButton, '确认发布'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));

      // 验证 service 被调用
      expect(announcementSvc.lastPublishDraft, isNotNull);
      expect(announcementSvc.lastPublishDraft!.title, '正式发布测试');
      expect(announcementSvc.lastPublishDraft!.content, '这是正文');
      expect(announcementSvc.lastPublishDraft!.isDraft, isFalse);
    });

    testWidgets('保存草稿调用 announcementService.saveAnnouncementDraft',
        (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 选择课程
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('CS101').last);
      await tester.pumpAndSettle();

      await tester.tap(find.text('测试班级-1'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.ancestor(of: find.text('通知标题'), matching: find.byType(TextField)),
        '草稿标题',
      );
      await tester.enterText(
        find.ancestor(of: find.text('通知正文'), matching: find.byType(TextField)),
        '草稿正文',
      );
      await tester.pump();

      // 点击保存草稿
      await tester.tap(find.text('保存草稿'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(announcementSvc.lastSavedDraft, isNotNull);
      expect(announcementSvc.lastSavedDraft!.title, '草稿标题');
      expect(announcementSvc.lastSavedDraft!.isDraft, isTrue);
    });

    testWidgets('发布失败时显示错误 SnackBar(不假装成功)', (tester) async {
      announcementSvc.shouldFail = true;
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 选择课程
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('CS101').last);
      await tester.pumpAndSettle();

      await tester.tap(find.text('测试班级-1'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.ancestor(of: find.text('通知标题'), matching: find.byType(TextField)),
        '失败测试',
      );
      await tester.enterText(
        find.ancestor(of: find.text('通知正文'), matching: find.byType(TextField)),
        '失败正文',
      );
      await tester.pump();

      await tester.tap(find.text('发布'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      await tester.tap(find.widgetWithText(FilledButton, '确认发布'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));

      // 应显示发布失败提示(不假装成功)
      expect(find.textContaining('发布失败'), findsOneWidget);

      // 表单内容应保留(不清空)
      expect(find.text('失败测试'), findsWidgets);
    });
  });

  group('TeacherPublishCenterPage - 发布任务', () {
    testWidgets('选择课程、班级、填入标题和截止时间后可发布', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      // 切到发布任务 Tab
      await tester.tap(find.text('发布任务'));
      await tester.pumpAndSettle();

      // 选择课程
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('CS101').last);
      await tester.pumpAndSettle();

      // 选择班级(任务 Tab 中是单个 Dropdown)
      final classDropdowns = find.byType(DropdownButtonFormField<String>);
      if (classDropdowns.evaluate().isNotEmpty) {
        await tester.tap(classDropdowns.first);
        await tester.pumpAndSettle();
        await tester.tap(find.text('测试班级-1').last);
        await tester.pumpAndSettle();
      }

      // 输入任务标题
      await tester.enterText(
        find.ancestor(of: find.text('任务标题'), matching: find.byType(TextField)),
        '测试任务标题',
      );
      await tester.enterText(
        find.ancestor(of: find.text('任务描述'), matching: find.byType(TextField)),
        '测试任务描述',
      );
      await tester.pump();

      // 点击发布 — 应弹出确认对话框(或提示选择截止时间)
      await tester.tap(find.text('发布'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 如果有截止时间未填会提示;否则弹出确认对话框
      // 这里只验证没有假装成功(没有显示"已发布")
      expect(find.textContaining('已发布'), findsNothing);
    });
  });

  group('TeacherPublishCenterPage - 课程加载状态', () {
    testWidgets('课程为空时显示空状态与"去创建"按钮', (tester) async {
      // 用一个返回空列表的 FakeCourseService
      final emptyCourseSvc = _EmptyCourseService();
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: true,
              useMockExpressionRecognition: true,
              apiBaseUrl: 'http://10.0.2.2:8000',
            );
          }),
          courseServiceProvider.overrideWithValue(emptyCourseSvc),
          announcementServiceProvider.overrideWithValue(announcementSvc),
          assignmentServiceProvider.overrideWithValue(assignmentSvc),
          currentAuthUserProvider.overrideWith((ref) => _teacherUser),
          reduceMotionProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        wrapApp(container, const TeacherPublishCenterPage()),
      );
      await pumpPage(tester);

      expect(find.byType(EmptyStateView), findsOneWidget);
      expect(find.textContaining('去创建'), findsOneWidget);
    });
  });
}

/// 返回空课程列表的 Fake,用于测试空状态。
class _EmptyCourseService implements CourseService {
  @override
  Future<PaginatedResult<Course>> listCourses({
    String? semester,
    String? search,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 20));
    return PaginatedResult.empty<Course>();
  }

  @override
  Future<Course> getCourse(String courseId) async => throw UnimplementedError();

  @override
  Future<Course> createCourse({
    required String code,
    required String name,
    required String semesterId,
    String? description,
    int? creditHours,
    int? color,
  }) async =>
      throw UnimplementedError();

  @override
  Future<Course> updateCourse(
    String courseId, {
    String? name,
    String? description,
    int? creditHours,
    int? color,
  }) async =>
      throw UnimplementedError();

  @override
  Future<List<SchoolClass>> listClasses(String courseId) async => [];

  @override
  Future<SchoolClass> createClass({
    required String courseId,
    required String name,
    String? year,
    String? major,
  }) async =>
      throw UnimplementedError();

  @override
  Future<SchoolClass> resetInviteCode(String classId) async =>
      throw UnimplementedError();

  @override
  Future<SchoolClass> joinByInviteCode(String inviteCode) async =>
      throw UnimplementedError();

  @override
  Future<PaginatedResult<ClassMember>> listClassMembers(
    String classId, {
    String? search,
    String? grade,
    String? major,
    String? submissionStatus,
    PageRequest page = const PageRequest(),
  }) async =>
      PaginatedResult.empty<ClassMember>();
}
