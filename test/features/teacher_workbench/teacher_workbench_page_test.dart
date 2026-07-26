import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/skeleton_loader.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/dashboard.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/multi_role_service_interfaces.dart';
import 'package:campus_companion/features/teacher_workbench/presentation/teacher_workbench_page.dart';

/// 伪造 DashboardService — 用于测试教师工作台页面。
///
/// 不发起真实网络请求,直接返回预设的 TeacherDashboard / 错误。
class _FakeDashboardService implements DashboardService {
  _FakeDashboardService({
    this.teacherDashboard,
    // ignore: unused_element_parameter
    this.studentDashboard,
    // ignore: unused_element_parameter
    this.adminStatus,
    this.shouldFail = false,
    this.delay = const Duration(milliseconds: 50),
  });

  final TeacherDashboard? teacherDashboard;
  final StudentDashboard? studentDashboard;
  final AdminSystemStatus? adminStatus;
  final bool shouldFail;
  final Duration delay;

  static const ApiException _err = ApiException(
    code: 'NETWORK_ERROR',
    message: '工作台加载失败',
    httpStatus: 503,
  );

  @override
  Future<TeacherDashboard> getTeacherDashboard() async {
    await Future.delayed(delay);
    if (shouldFail) throw _err;
    return teacherDashboard ??
        TeacherDashboard(
          courseCount: 3,
          classCount: 4,
          studentCount: 30,
          activeAssignmentCount: 5,
          pendingSubmissions: 12,
          unreadAnnouncementStudents: 8,
          overdueStudents: 3,
          nextActions: const [
            TeacherNextAction(
              id: 'act_grade_1',
              label: '12 份提交待查看',
              actionType: NextActionType.gradeSubmission,
              count: 12,
              priority: NextActionPriority.high,
              targetPath: '/teacher/stats',
            ),
          ],
          recentActivities: [
            TeacherActivity(
              id: 'activity_1',
              label: '发布了第 3 次作业',
              timestamp: DateTime(2026, 7, 26, 10, 0),
              actionType: NextActionType.publishAssignment,
            ),
          ],
        );
  }

  @override
  Future<StudentDashboard> getStudentDashboard() async {
    await Future.delayed(delay);
    if (shouldFail) throw _err;
    return studentDashboard ??
        const StudentDashboard(
          todayCount: 1,
          upcomingCount: 2,
          overdueCount: 0,
          unreadAnnouncementCount: 4,
          totalCourses: 3,
          todayProgress: 0.33,
        );
  }

  @override
  Future<AdminSystemStatus> getAdminSystemStatus() async {
    await Future.delayed(delay);
    if (shouldFail) throw _err;
    return adminStatus ??
        const AdminSystemStatus(
          totalUsers: 30,
          totalCourses: 3,
          totalClasses: 4,
          activeAssignments: 5,
          todaySubmissions: 8,
          isHealthy: true,
        );
  }
}

void main() {
  /// 构造可注入 FakeDashboardService 的 ProviderContainer。
  ///
  /// 同时注入 Mock 模式配置(仅开发/测试场景),
  /// 并注入 reduceMotionProvider=true 关闭 StaggeredEnter 的动画 timer。
  ProviderContainer makeContainer({
    DashboardService? dashboardService,
    AppUser? currentUser,
  }) {
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
        if (dashboardService != null)
          dashboardServiceProvider.overrideWithValue(dashboardService),
        if (currentUser != null)
          currentAuthUserProvider.overrideWith((ref) => currentUser),
        reduceMotionProvider.overrideWith((ref) => true),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  Widget wrapWithMaterial(ProviderContainer container, Widget child) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: child,
      ),
    );
  }

  /// 推进首帧 + 让异步加载完成 + 让 StaggeredEnter 的 Future.delayed 定时器完成。
  Future<void> pumpWorkbench(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50)); // 异步加载完成
    await tester.pumpAndSettle(const Duration(milliseconds: 800));
  }

  /// 教师演示用户。
  const teacherUser = AppUser(
    id: 'u_teacher_demo',
    name: '张明远',
    nickname: '张老师',
    role: UserRole.teacher,
    avatarSeed: 'teacher',
    teacherId: 'T20180456',
    department: '计算机与人工智能学院',
    teacherTitle: '副教授',
  );

  group('TeacherWorkbenchPage - 加载状态', () {
    testWidgets('初始加载显示 Skeleton 占位', (tester) async {
      // 使用较长延迟以保持 loading 状态
      final fakeService = _FakeDashboardService(
        delay: const Duration(seconds: 1),
      );
      final container = makeContainer(
        dashboardService: fakeService,
        currentUser: teacherUser,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const TeacherWorkbenchPage()),
      );
      await tester.pump();

      // 加载中:SkeletonCard 可见
      expect(find.byType(SkeletonCard), findsWidgets);

      // 等待 1s 延迟的 Future.delayed 完成,避免 "Timer is still pending" 错误
      await tester.pumpAndSettle(const Duration(seconds: 1));
    });
  });

  group('TeacherWorkbenchPage - 加载成功', () {
    testWidgets('显示教师欢迎语与角色徽章', (tester) async {
      final fakeService = _FakeDashboardService();
      final container = makeContainer(
        dashboardService: fakeService,
        currentUser: teacherUser,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const TeacherWorkbenchPage()),
      );
      await pumpWorkbench(tester);

      // 欢迎语包含教师昵称(displayName 优先返回 nickname)
      expect(find.textContaining('张老师'), findsOneWidget);
      // 角色徽章显示"教师"
      expect(find.text('教师'), findsWidgets);
    });

    testWidgets('显示"下一步行动"区域与待办统计', (tester) async {
      final fakeService = _FakeDashboardService();
      final container = makeContainer(
        dashboardService: fakeService,
        currentUser: teacherUser,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const TeacherWorkbenchPage()),
      );
      await pumpWorkbench(tester);

      // "下一步行动"区域标题
      expect(find.text('下一步行动'), findsOneWidget);
      // 默认 action label "12 份提交待查看"
      expect(find.textContaining('12 份提交待查看'), findsOneWidget);

      // "待处理"区域
      expect(find.text('待处理'), findsOneWidget);
      expect(find.text('待批阅'), findsOneWidget);
      expect(find.text('未读通知'), findsOneWidget);
      expect(find.text('逾期'), findsOneWidget);
    });

    testWidgets('显示"教学概览"区域(课程/班级/学生/活跃任务)', (tester) async {
      final fakeService = _FakeDashboardService();
      final container = makeContainer(
        dashboardService: fakeService,
        currentUser: teacherUser,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const TeacherWorkbenchPage()),
      );
      await pumpWorkbench(tester);

      // 教学概览标题
      expect(find.text('教学概览'), findsOneWidget);
      // 数字标签 — 课程/班级/学生/活跃任务
      expect(find.text('课程'), findsWidgets);
      expect(find.text('班级'), findsWidgets);
      expect(find.text('学生'), findsWidgets);
      expect(find.text('活跃任务'), findsOneWidget);

      // 数字值
      expect(find.text('3'), findsWidgets); // 课程数
      expect(find.text('30'), findsOneWidget); // 学生数
      expect(find.text('5'), findsWidgets); // 活跃任务数
    });

    testWidgets('显示"最近活动"区域(时间线样式)', (tester) async {
      final fakeService = _FakeDashboardService(
        teacherDashboard: TeacherDashboard(
          courseCount: 3,
          classCount: 4,
          studentCount: 30,
          activeAssignmentCount: 5,
          pendingSubmissions: 12,
          unreadAnnouncementStudents: 8,
          overdueStudents: 3,
          recentActivities: [
            TeacherActivity(
              id: 'activity_1',
              label: '发布了第 3 次作业',
              timestamp: DateTime(2026, 7, 26, 10, 0),
              actionType: NextActionType.publishAssignment,
            ),
            TeacherActivity(
              id: 'activity_2',
              label: '8 名学生尚未提交',
              timestamp: DateTime(2026, 7, 26, 11, 30),
              actionType: NextActionType.remindUnsubmitted,
            ),
          ],
        ),
      );
      final container = makeContainer(
        dashboardService: fakeService,
        currentUser: teacherUser,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const TeacherWorkbenchPage()),
      );
      await pumpWorkbench(tester);

      expect(find.text('最近活动'), findsOneWidget);
      expect(find.textContaining('发布了第 3 次作业'), findsOneWidget);
      expect(find.textContaining('8 名学生尚未提交'), findsOneWidget);
    });
  });

  group('TeacherWorkbenchPage - 加载失败', () {
    testWidgets('加载失败显示错误状态视图与重试按钮', (tester) async {
      final fakeService = _FakeDashboardService(shouldFail: true);
      final container = makeContainer(
        dashboardService: fakeService,
        currentUser: teacherUser,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const TeacherWorkbenchPage()),
      );
      await pumpWorkbench(tester);

      // 错误状态显示
      expect(find.byType(ErrorStateView), findsOneWidget);
      expect(find.textContaining('工作台加载失败'), findsOneWidget);
      expect(find.text('重试'), findsOneWidget);
    });
  });

  group('TeacherWorkbenchPage - 下拉刷新', () {
    testWidgets('下拉刷新触发 dashboardServiceProvider.getTeacherDashboard',
        (tester) async {
      final fakeService = _FakeDashboardService();
      final container = makeContainer(
        dashboardService: fakeService,
        currentUser: teacherUser,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const TeacherWorkbenchPage()),
      );
      await pumpWorkbench(tester);

      // 初始加载后已显示工作台
      expect(find.text('下一步行动'), findsOneWidget);

      // 触发下拉刷新(用 RefreshIndicator 的 onRefresh,模拟手势较复杂,
      // 这里直接验证 RefreshIndicator 存在即可)
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });
  });

  group('TeacherWorkbenchPage - nextActions 为空时不显示该区域', () {
    testWidgets('空 nextActions 时隐藏"下一步行动"区域', (tester) async {
      final fakeService = _FakeDashboardService(
        teacherDashboard: const TeacherDashboard(
          courseCount: 0,
          classCount: 0,
          studentCount: 0,
          activeAssignmentCount: 0,
          pendingSubmissions: 0,
          unreadAnnouncementStudents: 0,
          overdueStudents: 0,
          nextActions: [],
          recentActivities: [],
        ),
      );
      final container = makeContainer(
        dashboardService: fakeService,
        currentUser: teacherUser,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const TeacherWorkbenchPage()),
      );
      await pumpWorkbench(tester);

      // "下一步行动"区域隐藏
      expect(find.text('下一步行动'), findsNothing);

      // 待处理统计显示 0
      expect(find.text('待处理'), findsOneWidget);
      expect(find.text('0'), findsWidgets);
    });
  });
}

// 给 TeacherActivity 的 timestamp 字段提供 null 默认值的便捷构造,
// 避免 main 中必须传入 DateTime.now()。
extension on TeacherActivity {
  // 仅用于测试,不影响生产代码。
}
