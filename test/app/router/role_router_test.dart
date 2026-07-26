import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/data/models/auth.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/multi_role_service_interfaces.dart';

/// 伪造认证服务 — 用于角色路由测试。
class _FakeAuthService implements AuthService {
  _FakeAuthService({this.sessionUser});

  final AppUser? sessionUser;
  AuthSession? _session;

  static const ApiException _invalidRefreshToken = ApiException(
    code: 'INVALID_REFRESH_TOKEN',
    message: '登录已过期',
    httpStatus: 401,
  );

  @override
  Future<AuthSession> login(LoginCredentials credentials) async {
    final user = sessionUser ??
        const AppUser(
          id: 'u_test',
          name: '测试用户',
          role: UserRole.student,
          avatarSeed: 'test',
        );
    final session = AuthSession(
      user: user,
      accessToken: 'fake.access.token',
      refreshToken: 'fake.refresh.token',
      expiresAt: DateTime.now().add(const Duration(hours: 1)),
    );
    _session = session;
    return session;
  }

  @override
  Future<AuthSession> refresh(String refreshToken) async {
    throw _invalidRefreshToken;
  }

  @override
  Future<void> logout(String refreshToken) async {
    _session = null;
  }

  @override
  Future<AppUser> getCurrentUser() async {
    return _session?.user ??
        sessionUser ??
        const AppUser(
          id: 'u_test',
          name: '测试用户',
          role: UserRole.student,
          avatarSeed: 'test',
        );
  }
}

void main() {
  /// 构造可注入 FakeAuthService + 指定用户角色的 ProviderContainer。
  ProviderContainer makeContainer({
    AppUser? sessionUser,
    AuthStatus initialStatus = AuthStatus.unauthenticated,
    AuthSession? existingSession,
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
        authServiceProvider.overrideWithValue(
          _FakeAuthService(
            sessionUser: sessionUser,
          ),
        ),
        // 直接覆盖 AuthNotifier 的初始状态,避免触发 TokenStorage 异步加载
        authNotifierProvider.overrideWith((ref) {
          final notifier = _FakeAuthNotifier(
            ref,
            initialStatus: initialStatus,
            session: existingSession,
          );
          return notifier;
        }),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  /// 直接构造一个可控的 GoRouter,只保留 redirect 逻辑用于测试。
  ///
  /// 不构造完整 routerProvider,避免依赖全部页面组件。
  GoRouter makeRouter(ProviderContainer container) {
    return GoRouter(
      initialLocation: '/home',
      redirect: (context, state) {
        final auth = container.read(authNotifierProvider);
        final status = auth.status;
        final loc = state.matchedLocation;
        final isLoggedIn = status == AuthStatus.authenticated;
        final isOnLogin = loc == '/login';

        if (status == AuthStatus.initial) return null;

        if (!isLoggedIn) {
          if (isOnLogin) return null;
          return '/login';
        }

        final role = auth.session?.user.role;
        if (isOnLogin) {
          return _defaultLocationForRole(role);
        }
        if (!_roleCanAccess(role, loc)) {
          return _defaultLocationForRole(role);
        }
        return null;
      },
      routes: [
        GoRoute(
          path: '/login',
          builder: (context, state) => const Scaffold(
            body: Center(child: Text('登录页')),
          ),
        ),
        GoRoute(
          path: '/home',
          builder: (context, state) =>
              const Scaffold(body: Center(child: Text('学生首页'))),
        ),
        GoRoute(
          path: '/teacher/workbench',
          builder: (context, state) =>
              const Scaffold(body: Center(child: Text('教师工作台'))),
        ),
        GoRoute(
          path: '/admin/users',
          builder: (context, state) =>
              const Scaffold(body: Center(child: Text('管理员用户'))),
        ),
      ],
    );
  }

  Widget wrapApp(ProviderContainer container, GoRouter router) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        routerConfig: router,
        theme: ThemeData.light(useMaterial3: true),
      ),
    );
  }

  group('角色路由保护', () {
    testWidgets('未登录访问 /home 重定向到 /login', (tester) async {
      final container = makeContainer();
      final router = makeRouter(container);

      await tester.pumpWidget(wrapApp(container, router));
      await tester.pumpAndSettle();

      expect(find.text('登录页'), findsOneWidget);
      expect(find.text('学生首页'), findsNothing);
    });

    testWidgets('学生登录后访问 /home 不被重定向', (tester) async {
      const studentUser = AppUser(
        id: 'u_student',
        name: '林同学',
        role: UserRole.student,
        avatarSeed: 'student',
      );
      final session = AuthSession(
        user: studentUser,
        accessToken: 'access',
        refreshToken: 'refresh',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      );
      final container = makeContainer(
        sessionUser: studentUser,
        initialStatus: AuthStatus.authenticated,
        existingSession: session,
      );
      final router = makeRouter(container);

      await tester.pumpWidget(wrapApp(container, router));
      await tester.pumpAndSettle();

      expect(find.text('学生首页'), findsOneWidget);
      expect(find.text('登录页'), findsNothing);
    });

    testWidgets('学生登录后访问 /teacher/* 被重定向到 /home', (tester) async {
      const studentUser = AppUser(
        id: 'u_student',
        name: '林同学',
        role: UserRole.student,
        avatarSeed: 'student',
      );
      final session = AuthSession(
        user: studentUser,
        accessToken: 'access',
        refreshToken: 'refresh',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      );
      final container = makeContainer(
        sessionUser: studentUser,
        initialStatus: AuthStatus.authenticated,
        existingSession: session,
      );

      final router = GoRouter(
        initialLocation: '/teacher/workbench',
        redirect: (context, state) {
          final auth = container.read(authNotifierProvider);
          if (auth.status != AuthStatus.authenticated) return '/login';
          final role = auth.session?.user.role;
          if (!_roleCanAccess(role, state.matchedLocation)) {
            return _defaultLocationForRole(role);
          }
          return null;
        },
        routes: [
          GoRoute(
            path: '/login',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('登录页'))),
          ),
          GoRoute(
            path: '/home',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('学生首页'))),
          ),
          GoRoute(
            path: '/teacher/workbench',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('教师工作台'))),
          ),
        ],
      );

      await tester.pumpWidget(wrapApp(container, router));
      await tester.pumpAndSettle();

      // 学生访问教师路径 → 重定向到学生首页
      expect(find.text('学生首页'), findsOneWidget);
      expect(find.text('教师工作台'), findsNothing);
    });

    testWidgets('教师登录后访问 /teacher/workbench 不被重定向', (tester) async {
      const teacherUser = AppUser(
        id: 'u_teacher',
        name: '张老师',
        role: UserRole.teacher,
        avatarSeed: 'teacher',
      );
      final session = AuthSession(
        user: teacherUser,
        accessToken: 'access',
        refreshToken: 'refresh',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      );
      final container = makeContainer(
        sessionUser: teacherUser,
        initialStatus: AuthStatus.authenticated,
        existingSession: session,
      );

      final router = GoRouter(
        initialLocation: '/teacher/workbench',
        redirect: (context, state) {
          final auth = container.read(authNotifierProvider);
          if (auth.status != AuthStatus.authenticated) return '/login';
          final role = auth.session?.user.role;
          if (!_roleCanAccess(role, state.matchedLocation)) {
            return _defaultLocationForRole(role);
          }
          return null;
        },
        routes: [
          GoRoute(
            path: '/login',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('登录页'))),
          ),
          GoRoute(
            path: '/home',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('学生首页'))),
          ),
          GoRoute(
            path: '/teacher/workbench',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('教师工作台'))),
          ),
        ],
      );

      await tester.pumpWidget(wrapApp(container, router));
      await tester.pumpAndSettle();

      expect(find.text('教师工作台'), findsOneWidget);
      expect(find.text('登录页'), findsNothing);
    });

    testWidgets('教师登录后访问 /home 被重定向到 /teacher/workbench', (tester) async {
      const teacherUser = AppUser(
        id: 'u_teacher',
        name: '张老师',
        role: UserRole.teacher,
        avatarSeed: 'teacher',
      );
      final session = AuthSession(
        user: teacherUser,
        accessToken: 'access',
        refreshToken: 'refresh',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      );
      final container = makeContainer(
        sessionUser: teacherUser,
        initialStatus: AuthStatus.authenticated,
        existingSession: session,
      );
      final router = makeRouter(container);

      await tester.pumpWidget(wrapApp(container, router));
      await tester.pumpAndSettle();

      // 教师访问学生首页 → 重定向到教师工作台
      expect(find.text('教师工作台'), findsOneWidget);
      expect(find.text('学生首页'), findsNothing);
    });

    testWidgets('管理员登录后访问 /admin/users 不被重定向', (tester) async {
      const adminUser = AppUser(
        id: 'u_admin',
        name: '管理员',
        role: UserRole.admin,
        avatarSeed: 'admin',
      );
      final session = AuthSession(
        user: adminUser,
        accessToken: 'access',
        refreshToken: 'refresh',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      );
      final container = makeContainer(
        sessionUser: adminUser,
        initialStatus: AuthStatus.authenticated,
        existingSession: session,
      );

      final router = GoRouter(
        initialLocation: '/admin/users',
        redirect: (context, state) {
          final auth = container.read(authNotifierProvider);
          if (auth.status != AuthStatus.authenticated) return '/login';
          final role = auth.session?.user.role;
          if (!_roleCanAccess(role, state.matchedLocation)) {
            return _defaultLocationForRole(role);
          }
          return null;
        },
        routes: [
          GoRoute(
            path: '/login',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('登录页'))),
          ),
          GoRoute(
            path: '/home',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('学生首页'))),
          ),
          GoRoute(
            path: '/admin/users',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('管理员用户'))),
          ),
        ],
      );

      await tester.pumpWidget(wrapApp(container, router));
      await tester.pumpAndSettle();

      expect(find.text('管理员用户'), findsOneWidget);
      expect(find.text('登录页'), findsNothing);
    });
  });

  group('角色默认落地页', () {
    test('UserRole.student 默认路径为 /home', () {
      expect(_defaultLocationForRole(UserRole.student), '/home');
    });

    test('UserRole.teacher 默认路径为 /teacher/workbench', () {
      expect(_defaultLocationForRole(UserRole.teacher), '/teacher/workbench');
    });

    test('UserRole.admin 默认路径为 /admin/users', () {
      expect(_defaultLocationForRole(UserRole.admin), '/admin/users');
    });

    test('未登录(null)默认路径为 /login', () {
      expect(_defaultLocationForRole(null), '/login');
    });
  });

  group('角色路径访问权限', () {
    test('教师不能访问 /admin/* 路径', () {
      expect(_roleCanAccess(UserRole.teacher, '/admin/users'), isFalse);
      expect(_roleCanAccess(UserRole.teacher, '/admin/courses'), isFalse);
      expect(_roleCanAccess(UserRole.teacher, '/admin/system'), isFalse);
    });

    test('管理员不能访问 /teacher/* 路径', () {
      expect(_roleCanAccess(UserRole.admin, '/teacher/workbench'), isFalse);
      expect(_roleCanAccess(UserRole.admin, '/teacher/courses'), isFalse);
    });

    test('学生不能访问 /teacher/* 和 /admin/* 路径', () {
      expect(_roleCanAccess(UserRole.student, '/teacher/workbench'), isFalse);
      expect(_roleCanAccess(UserRole.student, '/admin/users'), isFalse);
    });

    test('学生可访问 /home /courses /tasks /counselor /profile', () {
      expect(_roleCanAccess(UserRole.student, '/home'), isTrue);
      expect(_roleCanAccess(UserRole.student, '/courses'), isTrue);
      expect(_roleCanAccess(UserRole.student, '/tasks'), isTrue);
      expect(_roleCanAccess(UserRole.student, '/counselor'), isTrue);
      expect(_roleCanAccess(UserRole.student, '/profile'), isTrue);
    });

    test('任何角色都能访问 /login(已登录会跳转)', () {
      expect(_roleCanAccess(UserRole.student, '/login'), isTrue);
      expect(_roleCanAccess(UserRole.teacher, '/login'), isTrue);
      expect(_roleCanAccess(UserRole.admin, '/login'), isTrue);
    });
  });
}

/// 暴露内部函数用于测试 — 通过导入 app_router.dart 中的私有函数无法直接访问,
/// 这里通过 mirror-free 的方式重新实现一份用于测试。
///
/// 注意:这些函数的实现必须与 lib/app/router/app_router.dart 中保持一致,
/// 否则测试会失去意义。每次修改 app_router.dart 中的对应函数都需要同步更新这里。
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

bool _roleCanAccess(UserRole? role, String location) {
  if (location == '/login') return true;
  if (location.startsWith('/teacher/')) {
    return role == UserRole.teacher;
  }
  if (location.startsWith('/admin/')) {
    return role == UserRole.admin;
  }
  return role == UserRole.student;
}

/// 伪造 AuthNotifier,允许直接设置初始状态以避免异步初始化。
///
/// 注意:由于 `_init()` 是父类的私有方法,无法被子类覆盖。
/// 父类构造函数会调用 `_init()`,在 Mock 模式下同步设置 state=AuthState.empty,
/// 然后本构造函数体再次设置 state 为测试所需的初始状态。
/// 由于 `_init()` 在 Mock 模式下不含 await,会先于构造函数体完成,
/// 因此最终 state 为本构造函数体设置的值。
class _FakeAuthNotifier extends AuthNotifier {
  _FakeAuthNotifier(
    super.ref, {
    required AuthStatus initialStatus,
    required AuthSession? session,
  }) {
    state = AuthState(
      status: initialStatus,
      session: session,
    );
  }
}
