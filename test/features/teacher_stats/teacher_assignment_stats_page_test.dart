import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/skeleton_loader.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/assignment.dart';
import 'package:campus_companion/data/models/course.dart';
import 'package:campus_companion/data/models/pagination.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/multi_role_service_interfaces.dart';
import 'package:campus_companion/features/teacher_stats/presentation/teacher_assignment_stats_page.dart';

/// 教师演示用户。
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

/// 测试任务 — 截止时间在未来(未逾期),允许催交。
Assignment _makeAssignment({String id = 'as_test_1'}) {
  final now = DateTime.now();
  return Assignment(
    id: id,
    classId: 'cl_test_1',
    courseId: 'c_test_1',
    title: '测试任务标题',
    description: '测试任务说明',
    deadline: now.add(const Duration(days: 3)),
    createdAt: now.subtract(const Duration(days: 2)),
    authorId: 'u_teacher_demo',
    authorName: '张明远',
    submissionType: SubmissionType.text,
    allowResubmit: true,
    maxScore: 100,
    reminderLeadMinutes: 60,
    hasReminder: true,
    totalStudents: 15,
    submittedCount: 10,
    gradedCount: 5,
    overdueCount: 0,
    courseName: '高等数学',
    className: '计科2024-1班',
  );
}

/// 测试统计数据。
AssignmentStats _makeStats({String assignmentId = 'as_test_1'}) {
  return AssignmentStats(
    assignmentId: assignmentId,
    total: 15,
    submitted: 10,
    graded: 5,
    overdue: 0,
    notSubmitted: 5,
    onTimeCount: 9,
    averageScore: 82.5,
    medianScore: 85,
    maxScore: 100,
  );
}

/// 测试学生状态列表。
List<StudentStatus> _makeStudentStatuses() {
  return [
    StudentStatus(
      studentId: 'u_student_01',
      name: '林知夏',
      studentNo: '2024010132',
      classId: 'cl_test_1',
      className: '计科2024-1班',
      status: SubmissionStatus.submitted,
      submittedAt: DateTime.now().subtract(const Duration(hours: 2)),
      hasAttachment: false,
      attachmentCount: 0,
      contentLength: 200,
    ),
    StudentStatus(
      studentId: 'u_student_02',
      name: '李思齐',
      studentNo: '2024010102',
      classId: 'cl_test_1',
      className: '计科2024-1班',
      status: SubmissionStatus.graded,
      submittedAt: DateTime.now().subtract(const Duration(days: 1)),
      grade: 88.5,
      hasAttachment: false,
      attachmentCount: 0,
      contentLength: 180,
    ),
    const StudentStatus(
      studentId: 'u_student_03',
      name: '王宇航',
      studentNo: '2024010103',
      classId: 'cl_test_1',
      className: '计科2024-1班',
      status: SubmissionStatus.notSubmitted,
    ),
  ];
}

/// 测试提交记录。
Submission _makeSubmission({
  String id = 'sub_1',
  String studentNo = '2024010132',
}) {
  return Submission(
    id: id,
    assignmentId: 'as_test_1',
    studentId: 'u_student_01',
    studentName: '林知夏',
    studentNo: studentNo,
    classId: 'cl_test_1',
    courseId: 'c_test_1',
    status: SubmissionStatus.submitted,
    content: '这是提交的内容,论述了微积分的应用场景。',
    submittedAt: DateTime.now().subtract(const Duration(hours: 2)),
  );
}

/// Fake AssignmentService — 用于教师统计页测试。
class _FakeAssignmentService implements AssignmentService {
  _FakeAssignmentService({
    Assignment? assignment,
    AssignmentStats? stats,
    List<StudentStatus>? studentStatuses,
    Object? assignmentError,
  })  : _assignment = assignment,
        _stats = stats,
        _studentStatuses = studentStatuses,
        _assignmentError = assignmentError;

  final Assignment? _assignment;
  final AssignmentStats? _stats;
  final List<StudentStatus>? _studentStatuses;
  final Object? _assignmentError;

  @override
  Future<Assignment> getAssignment(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 30));
    if (_assignmentError != null) throw _assignmentError;
    return _assignment ?? _makeAssignment(id: assignmentId);
  }

  @override
  Future<AssignmentStats> getAssignmentStats(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 30));
    return _stats ?? _makeStats(assignmentId: assignmentId);
  }

  @override
  Future<PaginatedResult<StudentStatus>> listAssignmentStudentStatuses(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 40));
    var items = _studentStatuses ?? _makeStudentStatuses();
    if (search != null && search.isNotEmpty) {
      items = items
          .where((s) => s.name.contains(search) || s.studentNo.contains(search))
          .toList();
    }
    if (status != null && status.isNotEmpty) {
      items = items.where((s) => s.status.name == status).toList();
    }
    return PaginatedResult(
      items: items,
      total: items.length,
      page: page.page,
      pageSize: page.pageSize,
      hasMore: false,
    );
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
}

/// Fake SubmissionService — 用于教师评分测试。
class _FakeSubmissionService implements SubmissionService {
  _FakeSubmissionService({
    Submission? submission,
    int remindCount = 5,
    bool shouldFailGrade = false,
    bool shouldFailRemind = false,
  })  : _submission = submission,
        _remindCount = remindCount,
        _shouldFailGrade = shouldFailGrade,
        _shouldFailRemind = shouldFailRemind;

  Submission? _submission;
  final int _remindCount;
  final bool _shouldFailGrade;
  final bool _shouldFailRemind;

  /// 上次调用记录。
  String? lastGradeSubmissionId;
  double? lastGrade;
  String? lastComment;

  @override
  Future<PaginatedResult<Submission>> listSubmissions(
    String assignmentId, {
    String? search,
    String? status,
    PageRequest page = const PageRequest(),
  }) async {
    await Future.delayed(const Duration(milliseconds: 40));
    if (_submission == null) {
      return PaginatedResult.empty<Submission>();
    }
    // 模拟按 studentNo / name 搜索
    var items = [_submission!];
    if (search != null && search.isNotEmpty) {
      items = items
          .where(
            (s) =>
                s.studentNo.contains(search) || s.studentName.contains(search),
          )
          .toList();
    }
    return PaginatedResult(
      items: items,
      total: items.length,
      page: page.page,
      pageSize: page.pageSize,
      hasMore: false,
    );
  }

  @override
  Future<Submission> getSubmission(String submissionId) async =>
      throw UnimplementedError();

  @override
  Future<Submission> gradeSubmission({
    required String submissionId,
    required double grade,
    String? comment,
  }) async {
    await Future.delayed(const Duration(milliseconds: 60));
    if (_shouldFailGrade) {
      throw const ApiException(
        code: 'GRADE_FAILED',
        message: '评分失败,请重试',
        httpStatus: 500,
      );
    }
    lastGradeSubmissionId = submissionId;
    lastGrade = grade;
    lastComment = comment;
    final sub = _submission;
    if (sub == null) throw StateError('No submission to grade');
    final updated = sub.copyWith(
      status: SubmissionStatus.graded,
      grade: grade,
      comment: comment,
      gradedAt: DateTime.now(),
      gradedBy: 'u_teacher_demo',
      gradedByName: '张明远',
    );
    _submission = updated;
    return updated;
  }

  @override
  Future<int> remindUnsubmitted(String assignmentId) async {
    await Future.delayed(const Duration(milliseconds: 60));
    if (_shouldFailRemind) {
      throw const ApiException(
        code: 'REMIND_FAILED',
        message: '催交失败',
        httpStatus: 500,
      );
    }
    return _remindCount;
  }

  @override
  Future<Submission?> getMySubmission(String assignmentId) async => _submission;

  @override
  Future<Submission> saveDraft({
    required String assignmentId,
    required String content,
    List<Attachment> attachments = const [],
  }) async =>
      throw UnimplementedError();

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
    submissionSvc = _FakeSubmissionService(submission: _makeSubmission());
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

  /// 加载统计页(等待 getAssignment + getAssignmentStats + listStudentStatuses)。
  /// 注意:不使用 pumpAndSettle,因为 CustomScrollView + SliverFillRemaining
  /// + AlwaysScrollableScrollPhysics 会导致 pumpAndSettle 永不 settle。
  Future<void> pumpPage(WidgetTester tester) async {
    await tester.pump();
    // 等待 getAssignment(30ms) + getAssignmentStats(30ms) 完成
    await tester.pump(const Duration(milliseconds: 100));
    // 等待 PagedListView._loadFirst() 的 listStudentStatuses(40ms) 完成
    await tester.pump(const Duration(milliseconds: 100));
    // 等待 setState 和渲染完成
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));
  }

  group('TeacherAssignmentStatsPage - 加载与渲染', () {
    testWidgets('初始加载显示 Skeleton 占位', (tester) async {
      // 使用较长延迟以保持 loading 状态
      final slowSvc = _FakeAssignmentService();
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
          assignmentServiceProvider.overrideWithValue(slowSvc),
          submissionServiceProvider.overrideWithValue(submissionSvc),
          currentAuthUserProvider.overrideWith((ref) => _teacherUser),
          reduceMotionProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await tester.pump();

      // Skeleton 占位可见
      expect(find.byType(SkeletonPage), findsOneWidget);

      // 清理:_load() 中的 Future.delayed(30ms) Timer 仍处于 pending 状态,
      // 需推进时钟让其触发并完成 setState,避免 "Timer is still pending" 断言。
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
    });

    testWidgets('加载完成后显示任务标题、统计概览', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // AppBar 显示任务标题
      expect(find.text('测试任务标题'), findsWidgets);
      // 统计概览:提交率 / 准时率 / 评分率
      expect(find.text('提交率'), findsOneWidget);
      expect(find.text('准时率'), findsOneWidget);
      expect(find.text('评分率'), findsOneWidget);
      // 平均分
      expect(find.textContaining('82.5'), findsOneWidget);
    });

    testWidgets('加载失败显示 ErrorStateView 与重试', (tester) async {
      assignmentSvc = _FakeAssignmentService(
        assignmentError: const ApiException(
          code: 'NOT_FOUND',
          message: '任务不存在',
          httpStatus: 404,
        ),
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_missing'),
        ),
      );
      await pumpPage(tester);

      expect(find.byType(ErrorStateView), findsOneWidget);
      expect(find.textContaining('加载统计失败'), findsOneWidget);
      expect(find.text('重试'), findsOneWidget);
    });
  });

  group('TeacherAssignmentStatsPage - 学生提交列表', () {
    testWidgets('显示学生姓名、学号、班级与状态标签', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 学生姓名(列表中)
      expect(find.text('林知夏'), findsWidgets);
      expect(find.text('李思齐'), findsWidgets);
      expect(find.text('王宇航'), findsWidgets);

      // 学号与班级
      expect(find.textContaining('2024010132'), findsWidgets);
      expect(find.textContaining('2024010102'), findsWidgets);
      expect(find.textContaining('2024010103'), findsWidgets);

      // 状态标签 — 同样的文案会出现在统计概览、状态筛选条和学生列表中,
      // 因此使用 findsWidgets 而非 findsOneWidget。
      expect(find.text('已提交'), findsWidgets);
      expect(find.text('已评分'), findsWidgets);
      expect(find.text('未提交'), findsWidgets);
    });

    testWidgets('搜索框输入后过滤学生列表', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 三个学生都在
      expect(find.text('林知夏'), findsWidgets);
      expect(find.text('王宇航'), findsWidgets);

      // 输入搜索关键词
      await tester.enterText(find.byType(TextField).first, '林知夏');
      await tester.pump();
      // 等待防抖(默认 DebouncedSearchField 通常 250-300ms)
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      // 只剩林知夏
      expect(find.text('林知夏'), findsWidgets);
      expect(find.text('王宇航'), findsNothing);
    });

    testWidgets('列表为空时显示空状态', (tester) async {
      assignmentSvc = _FakeAssignmentService(studentStatuses: const []);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      expect(find.textContaining('没有匹配的学生'), findsOneWidget);
    });
  });

  group('TeacherAssignmentStatsPage - 评分', () {
    testWidgets('点击学生打开提交详情底部表单,显示提交内容', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 点击第一个学生(林知夏)
      await tester.tap(find.text('林知夏').first);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 100));

      // 底部表单显示学生信息
      expect(find.text('提交内容'), findsOneWidget);
      // 提交内容显示
      expect(find.textContaining('论述了微积分'), findsOneWidget);
      // 评分表单
      expect(find.text('成绩'), findsWidgets);
      expect(find.text('评论(可选)'), findsOneWidget);
      expect(find.text('保存评分'), findsOneWidget);
    });

    testWidgets('未输入成绩时点击保存提示"请输入成绩"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 点击学生打开评分表单
      await tester.tap(find.text('林知夏').first);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 100));

      // 不输入成绩,直接点击保存
      await tester.tap(find.text('保存评分'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.textContaining('请输入成绩'), findsOneWidget);
      // gradeSubmission 不应被调用
      expect(submissionSvc.lastGrade, isNull);
    });

    testWidgets('输入非数字成绩时提示"成绩必须为非负数字"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.tap(find.text('林知夏').first);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 100));

      // 找到成绩输入框(label 为"成绩")
      final gradeField = find
          .ancestor(
            of: find.text('成绩'),
            matching: find.byType(TextField),
          )
          .first;
      await tester.enterText(gradeField, 'abc');
      await tester.pump();

      await tester.tap(find.text('保存评分'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.textContaining('成绩必须为非负数字'), findsOneWidget);
      expect(submissionSvc.lastGrade, isNull);
    });

    testWidgets('输入合法成绩后保存调用 gradeSubmission,显示"评分已保存"', (tester) async {
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.tap(find.text('林知夏').first);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 100));

      // 输入成绩
      final gradeField = find
          .ancestor(
            of: find.text('成绩'),
            matching: find.byType(TextField),
          )
          .first;
      await tester.enterText(gradeField, '88.5');
      await tester.pump();

      // 输入评论
      final commentField = find
          .ancestor(
            of: find.text('评论(可选)'),
            matching: find.byType(TextField),
          )
          .first;
      await tester.enterText(commentField, '论述清晰,可进一步深化分析。');
      await tester.pump();

      // 点击保存
      await tester.tap(find.text('保存评分'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      // 验证 gradeSubmission 被调用
      expect(submissionSvc.lastGrade, 88.5);
      expect(submissionSvc.lastComment, '论述清晰,可进一步深化分析。');
      expect(submissionSvc.lastGradeSubmissionId, 'sub_1');

      // 应显示成功提示
      expect(find.textContaining('评分已保存'), findsOneWidget);
    });

    testWidgets('评分失败显示"评分失败"(不假装成功)', (tester) async {
      submissionSvc = _FakeSubmissionService(
        submission: _makeSubmission(),
        shouldFailGrade: true,
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.tap(find.text('林知夏').first);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 100));

      final gradeField = find
          .ancestor(
            of: find.text('成绩'),
            matching: find.byType(TextField),
          )
          .first;
      await tester.enterText(gradeField, '90');
      await tester.pump();

      await tester.tap(find.text('保存评分'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示失败提示
      expect(find.textContaining('评分失败'), findsOneWidget);
      expect(find.textContaining('评分已保存'), findsNothing);
    });

    testWidgets('学生未提交时显示提示信息(无法评分)', (tester) async {
      // 设置 submissionSvc 返回空(该学生未提交)
      submissionSvc = _FakeSubmissionService(submission: null);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 点击未提交学生(王宇航)
      await tester.tap(find.text('王宇航').first);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示未提交提示
      expect(find.textContaining('尚未提交'), findsOneWidget);
      expect(find.textContaining('无法评分'), findsOneWidget);
      // 不应显示"保存评分"按钮
      expect(find.text('保存评分'), findsNothing);
    });
  });

  group('TeacherAssignmentStatsPage - 催交', () {
    testWidgets('点击催交按钮调用 remindUnsubmitted,显示提醒人数', (tester) async {
      submissionSvc = _FakeSubmissionService(
        submission: _makeSubmission(),
        remindCount: 5,
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      // 点击催交按钮(AppBar 中的 IconButton)
      final remindBtn = find.byTooltip('催交未提交学生');
      expect(remindBtn, findsOneWidget);
      await tester.tap(remindBtn);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示提醒人数
      expect(find.textContaining('已提醒 5 名'), findsOneWidget);
    });

    testWidgets('催交失败显示"催交失败"', (tester) async {
      submissionSvc = _FakeSubmissionService(
        submission: _makeSubmission(),
        shouldFailRemind: true,
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.tap(find.byTooltip('催交未提交学生'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.textContaining('催交失败'), findsOneWidget);
    });

    testWidgets('无未提交学生时显示"没有未提交学生需要提醒"', (tester) async {
      submissionSvc = _FakeSubmissionService(
        submission: _makeSubmission(),
        remindCount: 0,
      );
      final container = makeContainer();
      await tester.pumpWidget(
        wrapApp(
          container,
          const TeacherAssignmentStatsPage(assignmentId: 'as_test_1'),
        ),
      );
      await pumpPage(tester);

      await tester.tap(find.byTooltip('催交未提交学生'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.textContaining('没有未提交学生'), findsOneWidget);
    });
  });
}
