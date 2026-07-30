import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/auth.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/multi_role_service_interfaces.dart';
import 'package:campus_companion/features/auth/presentation/register_page.dart';

/// 伪造的认证服务,用于测试注册页交互(不发起真实网络请求)。
class _FakeAuthService implements AuthService {
  _FakeAuthService({
    this.delay = const Duration(milliseconds: 50),
    this.shouldFail = false,
    this.failCode = 'USERNAME_EXISTS',
    // ignore: unused_element_parameter
    this.sessionUser,
  });

  final Duration delay;
  final bool shouldFail;
  final String failCode;
  final AppUser? sessionUser;

  static const ApiException _invalidCredentials = ApiException(
    code: 'INVALID_CREDENTIALS',
    message: '用户名或密码错误',
    httpStatus: 401,
  );
  static const ApiException _invalidRefreshToken = ApiException(
    code: 'INVALID_REFRESH_TOKEN',
    message: '登录已过期',
    httpStatus: 401,
  );

  /// 最近一次 register 调用的凭据(测试用,验证表单 → service 的数据传递)。
  RegisterCredentials? lastRegisterCall;

  @override
  Future<AuthSession> login(LoginCredentials credentials) async {
    await Future.delayed(delay);
    throw _invalidCredentials;
  }

  @override
  Future<AppUser> register(RegisterCredentials credentials) async {
    await Future.delayed(delay);
    lastRegisterCall = credentials;
    if (shouldFail) {
      throw ApiException(
        code: failCode,
        message: '测试错误: $failCode',
        httpStatus: 409,
      );
    }
    return AppUser(
      id: 'u_new_${credentials.username}',
      name: credentials.displayName ?? credentials.username,
      role: credentials.role,
      avatarSeed: credentials.username,
      studentId: credentials.studentNumber,
      teacherId: credentials.teacherNumber,
      college: credentials.college,
      major: credentials.major,
      grade: credentials.grade,
      createdAt: DateTime.now(),
    );
  }

  @override
  Future<AuthSession> refresh(String refreshToken) async {
    await Future.delayed(delay);
    throw _invalidRefreshToken;
  }

  @override
  Future<void> logout(String refreshToken) async {
    await Future.delayed(delay);
  }

  @override
  Future<AppUser> getCurrentUser() async {
    await Future.delayed(delay);
    return sessionUser ??
        const AppUser(
          id: 'u_test',
          name: '测试用户',
          role: UserRole.student,
          avatarSeed: 'test',
        );
  }
}

void main() {
  /// 构造可注入 FakeAuthService 的 ProviderContainer。
  ///
  /// 显式注入 Mock 模式配置 + reduceMotionProvider=true,
  /// 关闭 StaggeredEnter 的动画 timer,避免 "Timer is still pending" 错误。
  ProviderContainer makeContainer({
    required AuthService authService,
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
        authServiceProvider.overrideWithValue(authService),
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

  /// 等待 StaggeredEnter 动画 + Future.delayed 完成。
  ///
  /// 注册表单字段较多(用户名/昵称/密码/确认密码/学号/学院/专业/年级),
  /// 默认 800x600 测试视口放不下,需要更大的高度才能完整渲染 + 点击按钮。
  /// 设置 surface size 后,所有字段与按钮都在可视区域内。
  Future<void> pumpRegister(WidgetTester tester) async {
    tester.view.physicalSize = const Size(800, 1800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pump();
    await tester.pumpAndSettle(const Duration(milliseconds: 800));
  }

  group('RegisterPage - 基础渲染', () {
    testWidgets('显示注册表单与必要字段', (tester) async {
      final container = makeContainer(authService: _FakeAuthService());
      await tester.pumpWidget(
        wrapWithMaterial(container, const RegisterPage()),
      );
      await pumpRegister(tester);

      expect(find.text('创建账号'), findsOneWidget);
      expect(find.text('填写信息'), findsOneWidget);
      expect(find.text('用户名'), findsOneWidget);
      expect(find.text('密码'), findsOneWidget);
      expect(find.text('确认密码'), findsOneWidget);
      expect(find.text('注册'), findsOneWidget);
      expect(find.text('返回登录'), findsOneWidget);
    });

    testWidgets('默认角色为学生,显示学号/学院/专业/年级字段', (tester) async {
      final container = makeContainer(authService: _FakeAuthService());
      await tester.pumpWidget(
        wrapWithMaterial(container, const RegisterPage()),
      );
      await pumpRegister(tester);

      expect(find.text('学号(选填)'), findsOneWidget);
      expect(find.text('学院(选填)'), findsOneWidget);
      expect(find.text('专业(选填)'), findsOneWidget);
      expect(find.text('年级(选填)'), findsOneWidget);
      // 学生模式下不应显示工号字段
      expect(find.text('工号(选填)'), findsNothing);
    });

    testWidgets('切换到教师角色后显示工号字段,隐藏学号/专业/年级', (tester) async {
      final container = makeContainer(authService: _FakeAuthService());
      await tester.pumpWidget(
        wrapWithMaterial(container, const RegisterPage()),
      );
      await pumpRegister(tester);

      // 点击「教师」角色 Chip
      await tester.tap(find.text('教师'));
      await tester.pumpAndSettle();

      expect(find.text('工号(选填)'), findsOneWidget);
      expect(find.text('院系(选填)'), findsOneWidget);
      // 教师模式不应显示学号/专业/年级
      expect(find.text('学号(选填)'), findsNothing);
      expect(find.text('专业(选填)'), findsNothing);
      expect(find.text('年级(选填)'), findsNothing);
    });
  });

  group('RegisterPage - 表单校验', () {
    testWidgets('密码不一致时显示错误且不调用 register', (tester) async {
      final fake = _FakeAuthService();
      final container = makeContainer(authService: fake);
      await tester.pumpWidget(
        wrapWithMaterial(container, const RegisterPage()),
      );
      await pumpRegister(tester);

      // TextField 顺序: 0=用户名, 1=昵称, 2=密码, 3=确认密码
      await tester.enterText(find.byType(TextField).at(0), 'newuser');
      await tester.enterText(find.byType(TextField).at(2), 'Password123');
      await tester.enterText(find.byType(TextField).at(3), 'Password456');
      await tester.pump();

      await tester.tap(find.text('注册'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      // 应显示密码不一致错误
      expect(find.textContaining('两次输入的密码不一致'), findsOneWidget);
      // service 不应被调用
      expect(fake.lastRegisterCall, isNull);
    });

    testWidgets('密码过短时显示错误', (tester) async {
      final fake = _FakeAuthService();
      final container = makeContainer(authService: fake);
      await tester.pumpWidget(
        wrapWithMaterial(container, const RegisterPage()),
      );
      await pumpRegister(tester);

      await tester.enterText(find.byType(TextField).at(0), 'newuser');
      await tester.enterText(find.byType(TextField).at(2), 'Short1');
      await tester.enterText(find.byType(TextField).at(3), 'Short1');
      await tester.pump();

      await tester.tap(find.text('注册'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      expect(find.textContaining('密码至少 8 个字符'), findsOneWidget);
      expect(fake.lastRegisterCall, isNull);
    });

    testWidgets('用户名包含非法字符时显示错误', (tester) async {
      final fake = _FakeAuthService();
      final container = makeContainer(authService: fake);
      await tester.pumpWidget(
        wrapWithMaterial(container, const RegisterPage()),
      );
      await pumpRegister(tester);

      // 用户名带空格(非法)
      await tester.enterText(find.byType(TextField).at(0), 'bad user');
      await tester.enterText(find.byType(TextField).at(2), 'Password123');
      await tester.enterText(find.byType(TextField).at(3), 'Password123');
      await tester.pump();

      await tester.tap(find.text('注册'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      expect(find.textContaining('用户名仅允许字母'), findsOneWidget);
      expect(fake.lastRegisterCall, isNull);
    });
  });

  group('RegisterPage - 注册流程', () {
    testWidgets('合法表单提交成功后跳转到登录页', (tester) async {
      final fake = _FakeAuthService();
      final container = makeContainer(authService: fake);

      // 用 GoRouter 验证成功后跳转到 /login
      final router = GoRouter(
        initialLocation: '/register',
        routes: [
          GoRoute(
            path: '/register',
            builder: (context, state) => const RegisterPage(),
          ),
          GoRoute(
            path: '/login',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('登录页占位'))),
          ),
        ],
      );
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await pumpRegister(tester);

      // TextField 顺序: 0=用户名, 1=昵称, 2=密码, 3=确认密码
      await tester.enterText(find.byType(TextField).at(0), 'newstudent');
      await tester.enterText(find.byType(TextField).at(2), 'Password123');
      await tester.enterText(find.byType(TextField).at(3), 'Password123');
      await tester.pump();

      await tester.tap(find.text('注册'));
      await tester.pumpAndSettle(const Duration(milliseconds: 1500));

      // service 被调用,且字段正确传递
      expect(fake.lastRegisterCall, isNotNull);
      expect(fake.lastRegisterCall!.username, 'newstudent');
      expect(fake.lastRegisterCall!.password, 'Password123');
      expect(fake.lastRegisterCall!.role, UserRole.student);

      // 成功跳转到登录页
      expect(find.text('登录页占位'), findsOneWidget);
    });

    testWidgets('注册失败(用户名已存在)显示友好错误且不跳转', (tester) async {
      final fake = _FakeAuthService(
        shouldFail: true,
        failCode: 'USERNAME_EXISTS',
      );
      final container = makeContainer(authService: fake);
      await tester.pumpWidget(
        wrapWithMaterial(container, const RegisterPage()),
      );
      await pumpRegister(tester);

      await tester.enterText(find.byType(TextField).at(0), 'duplicate_user');
      await tester.enterText(find.byType(TextField).at(2), 'Password123');
      await tester.enterText(find.byType(TextField).at(3), 'Password123');
      await tester.pump();

      await tester.tap(find.text('注册'));
      await tester.pumpAndSettle(const Duration(milliseconds: 800));

      // 显示映射后的友好文案
      expect(find.textContaining('该用户名已被注册'), findsOneWidget);
    });

    testWidgets('注册中按钮禁用并显示 loading', (tester) async {
      final fake = _FakeAuthService(delay: const Duration(milliseconds: 800));
      final container = makeContainer(authService: fake);
      await tester.pumpWidget(
        wrapWithMaterial(container, const RegisterPage()),
      );
      await pumpRegister(tester);

      await tester.enterText(find.byType(TextField).at(0), 'loading_user');
      await tester.enterText(find.byType(TextField).at(2), 'Password123');
      await tester.enterText(find.byType(TextField).at(3), 'Password123');
      await tester.pump();

      await tester.tap(find.text('注册'));
      // 等待状态切换为 loading
      await tester.pump(const Duration(milliseconds: 50));

      // loading 状态:按钮文本变为"注册中..."
      expect(find.text('注册中...'), findsOneWidget);
      // 按钮禁用
      final button = tester.widget<FilledButton>(
        find.byType(FilledButton),
      );
      expect(button.enabled, isFalse);

      // 等待完成避免 Timer pending
      await tester.pumpAndSettle(const Duration(milliseconds: 1500));
    });
  });

  group('RegisterPage - 导航', () {
    testWidgets('点击「返回登录」跳转到 /login', (tester) async {
      final container = makeContainer(authService: _FakeAuthService());
      final router = GoRouter(
        initialLocation: '/register',
        routes: [
          GoRoute(
            path: '/register',
            builder: (context, state) => const RegisterPage(),
          ),
          GoRoute(
            path: '/login',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('登录页占位'))),
          ),
        ],
      );
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await pumpRegister(tester);

      await tester.tap(find.text('返回登录'));
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      expect(find.text('登录页占位'), findsOneWidget);
    });

    testWidgets('prefilledUsername 预填到用户名输入框', (tester) async {
      final container = makeContainer(authService: _FakeAuthService());
      await tester.pumpWidget(
        wrapWithMaterial(
          container,
          const RegisterPage(prefilledUsername: 'carried_over_user'),
        ),
      );
      await pumpRegister(tester);

      // 用户名输入框(index 1,因为 0 是角色选择器中的某个 TextField)
      // 实际查找时,直接验证输入框中包含预填的文本
      expect(find.text('carried_over_user'), findsOneWidget);
    });
  });
}
