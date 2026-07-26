import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/assignment.dart';
import 'package:campus_companion/data/models/course.dart';
import 'package:campus_companion/data/models/pagination.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/multi_role_service_interfaces.dart';
import 'package:campus_companion/features/student_assignments/presentation/student_assignment_detail_page.dart';

/// 学生演示用户(用于注入 currentAuthUserProvider)。
const _studentUser = AppUser(
  id: 'u_student_demo',
  name: '林知夏',
  nickname: '知夏',
  role: UserRole.student,
  avatarSeed: 'zhixia',
  studentId: '2024010132',
  college: '计算机与人工智能学院',
  major: '计算机科学与技术',
  grade: '2024级',
  className: '计科2024-1班',
);

/// 测试任务 — 截止时间在未来(可提交),允许重交。
Assignment _makeAssignment({
  String id = 'as_test_1',
  bool allowResubmit = true,
  DateTime? deadline,
  SubmissionType submissionType = SubmissionType.text,
}) {
  final now = DateTime.now();
  return Assignment(
    id: id,
    classId: 'cl_test_1',
    courseId: 'c_test_1',
    title: '测试任务标题',
    description: '测试任务说明,完成教材习题。',
    deadline: deadline ?? now.add(const Duration(days: 3)),
    createdAt: now.subtract(const Duration(days: 2)),
    authorId: 'u_teacher_demo',
    authorName: '张明远',
    submissionType: submissionType,
    allowResubmit: allowResubmit,
    maxScore: 100,
    reminderLeadMinutes: 60,
    hasReminder: true,
    totalStudents: 30,
    submittedCount: 10,
    gradedCount: 5,
    overdueCount: 0,
    courseName: '高等数学',
    className: '计科2024-1班',
  );
}

/// Fake AssignmentService — 仅实现 getAssignment,其他方法返回空/抛 UnimplementedError。
class _FakeAssignmentService implements AssignmentService {
  _FakeAssignmentService({
    Assignment? assignment,
    Object? error,
  })  : _assignment = assignment,
        _error = error;

  final Assignment? _assignment;
  final Object? _error;

  @override
  Future<Assignment> getAssignment(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 30));
    if (_error != null) throw _error;
    return _assignment ?? _makeAssignment(id: assignmentId);
  }

  @override
  Future<Assignment> publishAssignment(AssignmentDraft draft) async =>
      throw UnimplementedError();

  @override
  Future<Assignment> saveAssignmentDraft(AssignmentDraft draft) async =>
      throw UnimplementedError();

  @override
  Future<void> deleteAssignment(String assignmentId) async =>
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
  }) async =>
      PaginatedResult.empty<Assignment>();

  @override
  Future<PaginatedResult<Assignment>> listStudentAssignments({
    String? courseId,
    String? status,
    String? search,
    String? sortBy,
    bool? sortDesc,
    PageRequest page = const PageRequest(),
  }) async =>
      PaginatedResult.empty<Assignment>();

  @override
  Future<PaginatedResult<StudentStatus>> listAssignmentStudentStatuses(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async =>
      PaginatedResult.empty<StudentStatus>();
}

/// Fake SubmissionService — 跟踪 saveDraft / submit / resubmit 调用。
class _FakeSubmissionService implements SubmissionService {
  _FakeSubmissionService({
    Submission? initialSubmission,
    bool shouldFail = false,
  })  : _mySubmission = initialSubmission,
        _shouldFail = shouldFail;

  Submission? _mySubmission;
  final bool _shouldFail;

  /// 上次调用记录(用于断言)。
  String? lastCall; // 'saveDraft' / 'submit' / 'resubmit'
  String? lastContent;
  String? lastAssignmentId;

  static const _apiError = ApiException(
    code: 'SUBMIT_FAILED',
    message: '提交失败,请重试',
    httpStatus: 500,
  );

  @override
  Future<Submission?> getMySubmission(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 30));
    return _mySubmission;
  }

  @override
  Future<Submission> saveDraft({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    await Future.delayed(const Duration(milliseconds: 50));
    if (_shouldFail) throw _apiError;
    lastCall = 'saveDraft';
    lastContent = content;
    lastAssignmentId = assignmentId;
    final now = DateTime.now();
    final sub = Submission(
      id: 'sub_draft_${now.millisecondsSinceEpoch}',
      assignmentId: assignmentId,
      studentId: 'u_student_demo',
      studentName: '林知夏',
      studentNo: '2024010132',
      classId: 'cl_test_1',
      courseId: 'c_test_1',
      status: SubmissionStatus.draft,
      content: content,
      submittedAt: now,
      attachments: attachments,
    );
    _mySubmission = sub;
    return sub;
  }

  @override
  Future<Submission> submit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    await Future.delayed(const Duration(milliseconds: 50));
    if (_shouldFail) throw _apiError;
    lastCall = 'submit';
    lastContent = content;
    lastAssignmentId = assignmentId;
    final now = DateTime.now();
    final sub = Submission(
      id: 'sub_submitted_${now.millisecondsSinceEpoch}',
      assignmentId: assignmentId,
      studentId: 'u_student_demo',
      studentName: '林知夏',
      studentNo: '2024010132',
      classId: 'cl_test_1',
      courseId: 'c_test_1',
      status: SubmissionStatus.submitted,
      content: content,
      submittedAt: now,
      attachments: attachments,
    );
    _mySubmission = sub;
    return sub;
  }

  @override
  Future<Submission> resubmit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    await Future.delayed(const Duration(milliseconds: 50));
    if (_shouldFail) throw _apiError;
    lastCall = 'resubmit';
    lastContent = content;
    lastAssignmentId = assignmentId;
    final now = DateTime.now();
    final sub = Submission(
      id: 'sub_resubmitted_${now.millisecondsSinceEpoch}',
      assignmentId: assignmentId,
      studentId: 'u_student_demo',
      studentName: '林知夏',
      studentNo: '2024010132',
      classId: 'cl_test_1',
      courseId: 'c_test_1',
      status: SubmissionStatus.submitted,
      content: content,
      submittedAt: now,
      attachments: attachments,
      resubmissionCount: (_mySubmission?.resubmissionCount ?? 0) + 1,
    );
    _mySubmission = sub;
    return sub;
  }

  @override
  Future<PaginatedResult<Submission>> listSubmissions(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async =>
      PaginatedResult.empty<Submission>();

  @override
  Future<Submission> getSubmission(String submissionId) async =>
      throw UnimplementedError();

  @override
  Future<Submission> gradeSubmission({
    required String submissionId,
    required double grade,
    String? comment,
  }) async =>
      throw UnimplementedError();

  @override
  Future<int> remindUnsubmitted(String assignmentId) async => 0;

  @override
  Future<Attachment> uploadAttachment({
    required String assignmentId,
    required List<int> bytes,
    required String filename,
    required String mimeType,
    void Function(double progress)? onProgress,
    CancelToken? cancelToken,
  }) async =>
      throw UnimplementedError();
}

void main() {
  late _FakeAssignmentService assignmentSvc;
  late _FakeSubmissionService submissionSvc;

  setUp(() {
    assignmentSvc = _FakeAssignmentService();
    submissionSvc = _FakeSubmissionService();
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
        assignmentServiceProvider.overrideWithValue(assignmentSvc),
        submissionServiceProvider.overrideWithValue(submissionSvc),
        currentAuthUserProvider.overrideWith((ref) => _studentUser),
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

  /// 加载任务详情(等待 getAssignment + getMySubmission 完成)。
  Future<void> pumpPage(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pumpAndSettle(const Duration(milliseconds: 500));
  }

  group('StudentAssignmentDetailPage - 加载与渲染', () {
    testWidgets('加载完成后显示任务标题、教师姓名、课程名与班级名', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      expect(find.text('测试任务标题'), findsOneWidget);
      expect(find.text('张明远'), findsWidgets);
      expect(find.text('高等数学'), findsWidgets);
      expect(find.text('计科2024-1班'), findsWidgets);
    });

    testWidgets('无提交记录时状态 chip 显示"待提交"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      expect(find.text('待提交'), findsOneWidget);
      // 底部按钮显示"提交任务"(无草稿状态)
      expect(find.text('提交任务'), findsOneWidget);
      expect(find.text('保存草稿'), findsOneWidget);
    });

    testWidgets('加载失败时显示 ErrorStateView 与重试按钮', (tester) async {
      assignmentSvc = _FakeAssignmentService(
        error: const ApiException(
          code: 'NOT_FOUND',
          message: '任务不存在',
          httpStatus: 404,
        ),
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_missing'),
        ),
      );
      await pumpPage(tester);

      expect(find.byType(ErrorStateView), findsOneWidget);
      expect(find.textContaining('加载任务失败'), findsOneWidget);
      expect(find.text('重试'), findsOneWidget);
    });
  });

  group('StudentAssignmentDetailPage - 保存草稿', () {
    testWidgets('内容为空时点击保存草稿提示"草稿内容不能为空"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 不输入任何内容,直接点击保存草稿
      await tester.tap(find.text('保存草稿'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.textContaining('草稿内容不能为空'), findsOneWidget);
      // service 不应被调用
      expect(submissionSvc.lastCall, isNull);
    });

    testWidgets('输入内容后保存草稿成功,显示"草稿已保存"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 在 TextField 中输入内容
      await tester.enterText(
        find.byType(TextField),
        '这是我的草稿内容',
      );
      await tester.pump();

      // 点击保存草稿
      await tester.tap(find.text('保存草稿'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 验证 service 被调用
      expect(submissionSvc.lastCall, 'saveDraft');
      expect(submissionSvc.lastContent, '这是我的草稿内容');
      expect(submissionSvc.lastAssignmentId, 'as_test_1');

      // 应显示成功提示
      expect(find.textContaining('草稿已保存'), findsOneWidget);

      // 状态 chip 应变为"草稿"
      expect(find.text('草稿'), findsOneWidget);
      // 底部按钮变为"正式提交"(因为已有草稿)
      expect(find.text('正式提交'), findsOneWidget);
    });

    testWidgets('保存草稿失败时显示"保存失败"(不假装成功)', (tester) async {
      submissionSvc = _FakeSubmissionService(shouldFail: true);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.enterText(
        find.byType(TextField),
        '会失败的草稿',
      );
      await tester.pump();

      await tester.tap(find.text('保存草稿'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 应显示失败提示(不假装成功)
      expect(find.textContaining('保存失败'), findsOneWidget);
      // 不应显示"草稿已保存"
      expect(find.textContaining('草稿已保存'), findsNothing);
    });
  });

  group('StudentAssignmentDetailPage - 提交任务', () {
    testWidgets('点击提交后弹出"确认提交"对话框', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.enterText(
        find.byType(TextField),
        '我的提交内容',
      );
      await tester.pump();

      // 点击提交按钮
      await tester.tap(find.text('提交任务'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 应弹出确认对话框
      expect(find.text('确认提交'), findsWidgets);
      expect(find.text('取消'), findsOneWidget);
      expect(find.widgetWithText(FilledButton, '确认提交'), findsOneWidget);
    });

    testWidgets('点击取消不调用 submit', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.enterText(
        find.byType(TextField),
        '我的提交内容',
      );
      await tester.pump();

      await tester.tap(find.text('提交任务'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 点击取消
      await tester.tap(find.text('取消'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // service 不应被调用
      expect(submissionSvc.lastCall, isNull);
    });

    testWidgets('确认提交后调用 submit,显示"提交成功"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.enterText(
        find.byType(TextField),
        '正式提交内容',
      );
      await tester.pump();

      await tester.tap(find.text('提交任务'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 确认提交
      await tester.tap(find.widgetWithText(FilledButton, '确认提交'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 验证 submit 被调用
      expect(submissionSvc.lastCall, 'submit');
      expect(submissionSvc.lastContent, '正式提交内容');
      expect(submissionSvc.lastAssignmentId, 'as_test_1');

      // 应显示成功提示
      expect(find.textContaining('提交成功'), findsOneWidget);

      // 状态 chip 应变为"已提交"
      expect(find.text('已提交'), findsOneWidget);
      // 底部按钮变为"重新提交"(因为已提交且允许重交)
      expect(find.text('重新提交'), findsOneWidget);
    });

    testWidgets('内容为空时确认提交提示"内容不能为空"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 不输入内容,直接点击提交
      await tester.tap(find.text('提交任务'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 确认提交
      await tester.tap(find.widgetWithText(FilledButton, '确认提交'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 应显示内容不能为空提示
      expect(find.textContaining('内容不能为空'), findsOneWidget);
      expect(submissionSvc.lastCall, isNull);
    });

    testWidgets('提交失败时显示"提交失败"(不假装成功)', (tester) async {
      submissionSvc = _FakeSubmissionService(shouldFail: true);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.enterText(
        find.byType(TextField),
        '会失败的提交',
      );
      await tester.pump();

      await tester.tap(find.text('提交任务'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      await tester.tap(find.widgetWithText(FilledButton, '确认提交'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 应显示失败提示
      expect(find.textContaining('提交失败'), findsOneWidget);
      expect(find.textContaining('提交成功'), findsNothing);
    });
  });

  group('StudentAssignmentDetailPage - 重新提交', () {
    testWidgets('已提交且 allowResubmit=true 时显示"重新提交"按钮', (tester) async {
      // 初始状态:已提交
      submissionSvc = _FakeSubmissionService(
        initialSubmission: Submission(
          id: 'sub_initial',
          assignmentId: 'as_test_1',
          studentId: 'u_student_demo',
          studentName: '林知夏',
          studentNo: '2024010132',
          classId: 'cl_test_1',
          courseId: 'c_test_1',
          status: SubmissionStatus.submitted,
          content: '之前提交的内容',
          submittedAt: DateTime.now().subtract(const Duration(hours: 2)),
          allowResubmit: true,
        ),
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 状态 chip 显示"已提交"
      expect(find.text('已提交'), findsOneWidget);
      // 底部按钮显示"重新提交"
      expect(find.text('重新提交'), findsOneWidget);
      // 上次提交时间应显示
      expect(find.textContaining('上次提交'), findsOneWidget);
    });

    testWidgets('重新提交时调用 resubmit(不是 submit)', (tester) async {
      submissionSvc = _FakeSubmissionService(
        initialSubmission: Submission(
          id: 'sub_initial',
          assignmentId: 'as_test_1',
          studentId: 'u_student_demo',
          studentName: '林知夏',
          studentNo: '2024010132',
          classId: 'cl_test_1',
          courseId: 'c_test_1',
          status: SubmissionStatus.submitted,
          content: '之前的内容',
          submittedAt: DateTime.now().subtract(const Duration(hours: 2)),
          allowResubmit: true,
        ),
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 清空原内容并输入新内容
      await tester.enterText(
        find.byType(TextField),
        '重新提交的新内容',
      );
      await tester.pump();

      // 点击重新提交
      await tester.tap(find.text('重新提交'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 确认提交
      await tester.tap(find.widgetWithText(FilledButton, '确认提交'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 应调用 resubmit 而不是 submit
      expect(submissionSvc.lastCall, 'resubmit');
      expect(submissionSvc.lastContent, '重新提交的新内容');

      // 应显示"重新提交成功"
      expect(find.textContaining('重新提交成功'), findsOneWidget);
    });

    testWidgets('已提交且 allowResubmit=false 时提交按钮被禁用', (tester) async {
      // 使用不允许重交的任务
      assignmentSvc = _FakeAssignmentService(
        assignment: _makeAssignment(allowResubmit: false),
      );
      submissionSvc = _FakeSubmissionService(
        initialSubmission: Submission(
          id: 'sub_initial',
          assignmentId: 'as_test_1',
          studentId: 'u_student_demo',
          studentName: '林知夏',
          studentNo: '2024010132',
          classId: 'cl_test_1',
          courseId: 'c_test_1',
          status: SubmissionStatus.submitted,
          content: '之前的内容',
          submittedAt: DateTime.now().subtract(const Duration(hours: 2)),
          allowResubmit: false,
        ),
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 底部按钮显示"已提交"且按钮禁用(onPressed 为 null)
      expect(find.text('已提交'), findsWidgets);
      // FilledButton 的 onPressed 应为 null
      final filledBtn = tester.widget<FilledButton>(
        find
            .ancestor(
              of: find.text('已提交'),
              matching: find.byType(FilledButton),
            )
            .first,
      );
      expect(filledBtn.onPressed, isNull);
    });
  });

  group('StudentAssignmentDetailPage - 评分结果展示', () {
    testWidgets('已评分提交显示评分卡片、分数与教师评语', (tester) async {
      submissionSvc = _FakeSubmissionService(
        initialSubmission: Submission(
          id: 'sub_graded',
          assignmentId: 'as_test_1',
          studentId: 'u_student_demo',
          studentName: '林知夏',
          studentNo: '2024010132',
          classId: 'cl_test_1',
          courseId: 'c_test_1',
          status: SubmissionStatus.graded,
          content: '已评分的提交',
          submittedAt: DateTime.now().subtract(const Duration(days: 1)),
          grade: 88.5,
          comment: '论述清晰,可进一步深化分析。',
          gradedAt: DateTime.now().subtract(const Duration(hours: 3)),
          gradedBy: 'u_teacher_demo',
          gradedByName: '张明远',
        ),
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 状态 chip 显示"已评分"
      expect(find.text('已评分'), findsOneWidget);

      // GradeCard 在 ListView 末尾,需要滚动到可见区域
      // (ListView 默认懒加载,未渲染的项目 find 不到)
      // 滚动到列表底部以渲染 GradeCard
      await tester.scrollUntilVisible(
        find.text('评分结果'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle(const Duration(milliseconds: 300));

      // 评分卡片
      expect(find.text('评分结果'), findsOneWidget);
      // 分数显示(88.5 / 100)
      expect(find.textContaining('88.5'), findsOneWidget);
      expect(find.textContaining('/ 100'), findsOneWidget);
      // 教师评语
      expect(find.text('教师评语'), findsOneWidget);
      expect(find.textContaining('论述清晰'), findsOneWidget);
      // 评分人
      expect(find.textContaining('张明远'), findsWidgets);
    });
  });

  group('StudentAssignmentDetailPage - 防重复点击', () {
    testWidgets('保存中按钮禁用,不能重复点击', (tester) async {
      // 使用较长延迟确保保存中状态可见
      final slowSvc = _SlowSubmissionService();
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
          assignmentServiceProvider.overrideWithValue(assignmentSvc),
          submissionServiceProvider.overrideWithValue(slowSvc),
          currentAuthUserProvider.overrideWith((ref) => _studentUser),
          reduceMotionProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        wrapApp(
          container,
          const StudentAssignmentDetailPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.enterText(
        find.byType(TextField),
        '防重复点击测试',
      );
      await tester.pump();

      // 点击保存草稿
      await tester.tap(find.text('保存草稿'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      // 保存中:OutlinedButton 应被禁用(onPressed 为 null)
      final outlineBtn = tester.widget<OutlinedButton>(
        find.ancestor(
          of: find.text('保存草稿'),
          matching: find.byType(OutlinedButton),
        ),
      );
      expect(outlineBtn.onPressed, isNull);

      // 等待保存完成
      await tester.pumpAndSettle(const Duration(seconds: 1));

      // 完成后应能再次点击(onPressed 不为 null)
      final outlineBtnAfter = tester.widget<OutlinedButton>(
        find.ancestor(
          of: find.text('保存草稿'),
          matching: find.byType(OutlinedButton),
        ),
      );
      expect(outlineBtnAfter.onPressed, isNotNull);
      expect(slowSvc.saveCallCount, 1);
    });
  });
}

/// 慢速 SubmissionService — 用于测试防重复点击。
class _SlowSubmissionService implements SubmissionService {
  int saveCallCount = 0;

  @override
  Future<Submission> saveDraft({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async {
    saveCallCount++;
    await Future.delayed(const Duration(milliseconds: 500));
    return Submission(
      id: 'sub_slow_$saveCallCount',
      assignmentId: assignmentId,
      studentId: 'u_student_demo',
      studentName: '林知夏',
      studentNo: '2024010132',
      classId: 'cl_test_1',
      courseId: 'c_test_1',
      status: SubmissionStatus.draft,
      content: content,
      submittedAt: DateTime.now(),
    );
  }

  @override
  Future<Submission?> getMySubmission(String assignmentId) async => null;

  @override
  Future<Submission> submit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async =>
      throw UnimplementedError();

  @override
  Future<Submission> resubmit({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async =>
      throw UnimplementedError();

  @override
  Future<PaginatedResult<Submission>> listSubmissions(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async =>
      PaginatedResult.empty<Submission>();

  @override
  Future<Submission> getSubmission(String submissionId) async =>
      throw UnimplementedError();

  @override
  Future<Submission> gradeSubmission({
    required String submissionId,
    required double grade,
    String? comment,
  }) async =>
      throw UnimplementedError();

  @override
  Future<int> remindUnsubmitted(String assignmentId) async => 0;

  @override
  Future<Attachment> uploadAttachment({
    required String assignmentId,
    required List<int> bytes,
    required String filename,
    required String mimeType,
    void Function(double progress)? onProgress,
    CancelToken? cancelToken,
  }) async =>
      throw UnimplementedError();
}
