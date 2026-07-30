import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/presentation/login_page.dart';
import '../../features/auth/presentation/register_page.dart';
import '../../features/home/presentation/home_page.dart';
import '../../features/knowledge/presentation/knowledge_management_page.dart';
import '../../features/counselor/presentation/counselor_page.dart';
import '../../features/study_companion/presentation/study_companion_page.dart';
import '../../features/profile/presentation/profile_page.dart';
import '../../features/notifications/presentation/notification_extract_page.dart';
import '../../features/notifications/presentation/notifications_list_page.dart';
import '../../features/tasks/presentation/task_create_page.dart';
import '../../features/student_courses/presentation/student_courses_page.dart';
import '../../features/student_courses/presentation/student_course_detail_page.dart';
import '../../features/student_assignments/presentation/student_assignments_page.dart';
import '../../features/student_assignments/presentation/student_assignment_detail_page.dart';
import '../../features/student_announcements/presentation/student_announcement_detail_page.dart';
import '../../features/teacher_workbench/presentation/teacher_workbench_page.dart';
import '../../features/teacher_courses/presentation/teacher_courses_page.dart';
import '../../features/teacher_courses/presentation/teacher_course_detail_page.dart';
import '../../features/teacher_courses/presentation/teacher_class_detail_page.dart';
import '../../features/teacher_publish/presentation/teacher_publish_center_page.dart';
import '../../features/teacher_stats/presentation/teacher_stats_page.dart';
import '../../features/teacher_stats/presentation/teacher_assignment_stats_page.dart';
import '../../features/teacher_profile/presentation/teacher_profile_page.dart';
import '../../features/admin_users/presentation/admin_users_page.dart';
import '../../features/admin_courses/presentation/admin_courses_page.dart';
import '../../features/admin_system/presentation/admin_system_page.dart';
import '../../data/models/models.dart';
import '../providers/app_providers.dart';
import 'admin_shell.dart';
import 'student_shell.dart';
import 'teacher_shell.dart';

/// 路由配置 — 多角色 + 角色保护 + 自动跳转。
///
/// 设计:
/// - /login 登录页(不受保护)
/// - 学生 ShellRoute: /home /courses /tasks /counselor /profile
///   嵌套: /tasks/create /notifications/* /study /knowledge
/// - 教师 ShellRoute: /teacher/workbench /teacher/courses /teacher/publish
///   /teacher/stats /teacher/profile
/// - 管理员 ShellRoute: /admin/users /admin/courses /admin/system
///
/// 角色保护:
/// - 未认证访问受保护路由 → /login
/// - 已认证访问 /login → 根据角色跳转默认页
/// - 角色与路由前缀不匹配 → 跳转到当前角色默认页
final routerProvider = Provider<GoRouter>((ref) {
  final refreshNotifier = _AuthRefreshListenable(ref);
  return GoRouter(
    initialLocation: '/home',
    refreshListenable: refreshNotifier,
    redirect: (context, state) {
      final auth = ref.read(authNotifierProvider);
      final status = auth.status;
      final loc = state.matchedLocation;
      final isLoggedIn = status == AuthStatus.authenticated;
      final isOnLogin = loc == '/login';
      final isOnRegister = loc == '/register';

      // 初始化中: 不做任何重定向,等待 session 恢复完成
      if (status == AuthStatus.initial) return null;

      // 未登录:
      if (!isLoggedIn) {
        // /login 与 /register 都是公开入口,未登录可访问
        if (isOnLogin || isOnRegister) return null;
        // Mock 模式下首页直接跳登录,避免空白
        return '/login';
      }

      // 已登录:
      final role = auth.session?.user.role;

      // 已登录访问 /login 或 /register → 跳转到角色默认页
      // (避免已登录用户重复注册或看到登录页)
      if (isOnLogin || isOnRegister) {
        return _defaultLocationForRole(role);
      }

      // 角色路由保护: 检查 loc 是否匹配当前角色
      if (!_roleCanAccess(role, loc)) {
        return _defaultLocationForRole(role);
      }

      return null;
    },
    routes: [
      // ===== 登录页 =====
      GoRoute(
        path: '/login',
        builder: (context, state) => LoginPage(
          initialError: state.extra is String ? state.extra as String : null,
        ),
      ),

      // ===== 注册页(公开入口,未登录可访问) =====
      GoRoute(
        path: '/register',
        builder: (context, state) {
          // 支持从登录页预填用户名(用户尝试登录不存在时,可一键带过去注册)
          final extra = state.extra;
          final prefilledUsername =
              extra is String ? extra : null;
          return RegisterPage(prefilledUsername: prefilledUsername);
        },
      ),

      // ===== 学生 Shell =====
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            StudentShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/home',
                builder: (context, state) => const HomePage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/courses',
                builder: (context, state) => const StudentCoursesPage(),
                routes: [
                  GoRoute(
                    path: ':courseId',
                    builder: (context, state) => StudentCourseDetailPage(
                      courseId: state.pathParameters['courseId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/tasks',
                builder: (context, state) => const StudentAssignmentsPage(),
                routes: [
                  GoRoute(
                    path: 'create',
                    builder: (context, state) => const TaskCreatePage(),
                  ),
                  GoRoute(
                    path: 'assignment/:assignmentId',
                    builder: (context, state) => StudentAssignmentDetailPage(
                      assignmentId: state.pathParameters['assignmentId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/counselor',
                builder: (context, state) => CounselorPage(
                  context: CounselorContext.fromExtra(state.extra),
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/profile',
                builder: (context, state) => const ProfilePage(),
              ),
            ],
          ),
        ],
      ),

      // ===== 学生专属子页面(不在 Shell 内,通过 push 进入) =====
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const NotificationsListPage(),
      ),
      GoRoute(
        path: '/notifications/extract',
        builder: (context, state) {
          final extra = state.extra;
          final prefilledText = extra is String ? extra : null;
          return NotificationExtractPage(prefilledText: prefilledText);
        },
      ),
      GoRoute(
        path: '/announcements/:announcementId',
        builder: (context, state) => StudentAnnouncementDetailPage(
          announcementId: state.pathParameters['announcementId']!,
        ),
      ),
      GoRoute(
        path: '/knowledge',
        builder: (context, state) => const KnowledgeManagementPage(),
      ),
      GoRoute(
        path: '/study',
        builder: (context, state) => const StudyCompanionPage(),
      ),

      // ===== 教师 Shell =====
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            TeacherShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/teacher/workbench',
                builder: (context, state) => const TeacherWorkbenchPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/teacher/courses',
                builder: (context, state) => const TeacherCoursesPage(),
                routes: [
                  GoRoute(
                    path: ':courseId',
                    builder: (context, state) => TeacherCourseDetailPage(
                      courseId: state.pathParameters['courseId']!,
                    ),
                    routes: [
                      GoRoute(
                        path: 'classes/:classId',
                        builder: (context, state) => TeacherClassDetailPage(
                          courseId: state.pathParameters['courseId']!,
                          classId: state.pathParameters['classId']!,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/teacher/publish',
                builder: (context, state) => const TeacherPublishCenterPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/teacher/stats',
                builder: (context, state) => const TeacherStatsPage(),
                routes: [
                  GoRoute(
                    path: ':assignmentId',
                    builder: (context, state) => TeacherAssignmentStatsPage(
                      assignmentId: state.pathParameters['assignmentId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/teacher/profile',
                builder: (context, state) => const TeacherProfilePage(),
              ),
            ],
          ),
        ],
      ),

      // ===== 管理员 Shell =====
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AdminShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/admin/users',
                builder: (context, state) => const AdminUsersPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/admin/courses',
                builder: (context, state) => const AdminCoursesPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/admin/system',
                builder: (context, state) => const AdminSystemPage(),
              ),
            ],
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) => _RouteErrorView(error: state.error),
  );
});

/// 角色默认落地页。
String _defaultLocationForRole(UserRole? role) {
  switch (role) {
    case UserRole.student:
      return '/home';
    case UserRole.teacher:
      return '/teacher/workbench';
    case UserRole.admin:
      return '/admin/users';
    case null:
      return '/login';
  }
}

/// 检查角色是否可访问指定路径。
bool _roleCanAccess(UserRole? role, String location) {
  // /login 与 /register 任何角色都可访问(已登录会跳转到默认页)
  if (location == '/login' || location == '/register') return true;

  // 学生路径前缀
  if (location.startsWith('/teacher/')) {
    return role == UserRole.teacher;
  }
  if (location.startsWith('/admin/')) {
    return role == UserRole.admin;
  }

  // 其余路径(/home /courses /tasks /counselor /profile /notifications /study
  // /knowledge /announcements)默认学生可访问。
  // 教师也允许访问 /counselor /knowledge /announcements/:id(共用 AI 导员)?
  // — 按规范,教师不使用学生 AI 导员,这里严格按角色区分。
  return role == UserRole.student;
}

/// 把 Riverpod Provider 变化转换为 GoRouter 的 ChangeNotifier 信号。
class _AuthRefreshListenable extends ChangeNotifier {
  _AuthRefreshListenable(this._ref) {
    _sub = _ref.listen(authNotifierProvider, (_, __) {
      notifyListeners();
    });
  }

  final Ref _ref;
  // ignore: unused_field
  late final ProviderSubscription _sub;

  @override
  void dispose() {
    _sub.close();
    super.dispose();
  }
}

class _RouteErrorView extends StatelessWidget {
  const _RouteErrorView({required this.error});
  final Exception? error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('页面未找到')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.map_outlined, size: 48),
              const SizedBox(height: 12),
              Text(
                '页面未找到',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text(
                error.toString(),
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
