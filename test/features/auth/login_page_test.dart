import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/auth.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/multi_role_service_interfaces.dart';
import 'package:campus_companion/features/auth/presentation/login_page.dart';

/// 伪造的认证服务,用于测试登录页交互(不发起真实网络请求)。
class _FakeAuthService implements AuthService {
  _FakeAuthService({
    this.delay = const Duration(milliseconds: 50),
    this.shouldFail = false,
    // ignore: unused_element_parameter
    this.sessionUser,
  });

  final Duration delay;
  final bool shouldFail;
  final AppUser? sessionUser;

  // 在异步方法内 throw const 表达式需要先保存到 const 变量,
  // 否则编译器报错 "Not a constant expression"。
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

  @override
  Future<AuthSession> login(LoginCredentials credentials) async {
    await Future.delayed(delay);
    if (shouldFail) {
      throw _invalidCredentials;
    }
    return AuthSession(
      user: sessionUser ??
          const AppUser(
            id: 'u_test',
            name: '测试用户',
            role: UserRole.student,
            avatarSeed: 'test',
          ),
      accessToken: 'fake.access.token',
      refreshToken: 'fake.refresh.token',
      expiresAt: DateTime.now().add(const Duration(hours: 1)),
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
  /// 显式注入 Mock 模式配置(仅开发/测试场景),
  /// 避免触发 TokenStorage / AuthInterceptor 的真实初始化。
  /// 同时注入 reduceMotionProvider=true,关闭 StaggeredEnter 的动画 timer,
  /// 避免 "Timer is still pending" 错误。
  ProviderContainer makeContainer({
    required AuthService authService,
    String? initialError,
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

  /// LoginPage 内部使用了 StaggeredEnter 的延迟动画,
  /// reduceMotion=true 时直接返回 child,但 Future.delayed timer 仍会被创建。
  /// 这里使用 pumpAndSettle 让所有 timer 与动画完成,避免 "Timer pending" 错误。
  /// 设置 timeout 避免无限等待。
  Future<void> pumpLogin(WidgetTester tester) async {
    await tester.pump();
    // StaggeredEnter 最大 delay 是 360ms,加上 Future.delayed 完成 + 渲染
    // pumpAndSettle 会等待所有动画和 timer 完成
    await tester.pumpAndSettle(const Duration(milliseconds: 800));
  }

  /// 查找登录表单中的第 N 个 TextField。
  ///
  /// LoginPage 的 _TextField 结构是 Column(Text(label), SizedBox, TextField),
  /// 登录表单中按顺序:0 = 账号,1 = 密码。
  /// 直接按 index 定位最简单可靠。
  Finder textFieldByLabel(String label) {
    final index = label == '账号' ? 0 : 1;
    return find.byType(TextField).at(index);
  }

  group('LoginPage - 基础渲染', () {
    testWidgets('显示品牌头部、标题与登录表单', (tester) async {
      final container = makeContainer(
        authService: _FakeAuthService(),
      );
      await tester.pumpWidget(
        wrapWithMaterial(
          container,
          const LoginPage(),
        ),
      );
      await pumpLogin(tester);

      // 品牌头部
      expect(find.text('CampusMate AI'), findsOneWidget);
      expect(find.text('校园事务智能陪伴助手'), findsOneWidget);
      // 欢迎语
      expect(find.text('欢迎回来'), findsOneWidget);
      // 登录表单元素
      expect(find.text('账号登录'), findsOneWidget);
      expect(find.text('账号'), findsOneWidget);
      expect(find.text('密码'), findsOneWidget);
      // 登录按钮
      expect(find.text('登录'), findsOneWidget);
    });

    testWidgets('不显示任何"演示模式"或"快捷登录"入口(参赛版本约束)', (tester) async {
      final container = makeContainer(
        authService: _FakeAuthService(),
      );
      await tester.pumpWidget(
        wrapWithMaterial(
          container,
          const LoginPage(),
        ),
      );
      await pumpLogin(tester);

      // 参赛版本约束:登录页不得提供绕过认证的快捷登录入口
      expect(find.textContaining('演示'), findsNothing);
      expect(find.textContaining('Mock'), findsNothing);
      expect(find.textContaining('快捷'), findsNothing);
      expect(find.textContaining('一键'), findsNothing);
      expect(find.textContaining('teacher_demo'), findsNothing);
      expect(find.textContaining('student_demo'), findsNothing);
      expect(find.textContaining('admin_demo'), findsNothing);
    });
  });

  group('LoginPage - 交互行为', () {
    testWidgets('点击登录按钮触发 authService.login', (tester) async {
      final fakeService = _FakeAuthService();
      final container = makeContainer(authService: fakeService);
      await tester.pumpWidget(
        wrapWithMaterial(
          container,
          const LoginPage(),
        ),
      );
      await pumpLogin(tester);

      // 输入用户名和密码
      await tester.enterText(
        textFieldByLabel('账号'),
        'student_demo',
      );
      await tester.enterText(
        textFieldByLabel('密码'),
        'Demo123456',
      );
      await tester.pump();

      // 点击登录按钮
      await tester.tap(find.text('登录'));
      await tester.pump();
      // 等待异步登录完成 + 后续 _validateSession 也调用 getCurrentUser
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      // 验证状态:authenticated
      final auth = container.read(authNotifierProvider);
      expect(auth.status, AuthStatus.authenticated);
      expect(auth.session, isNotNull);
      expect(auth.session!.user.name, '测试用户');
    });

    testWidgets('登录失败时显示错误信息且不进入已认证状态', (tester) async {
      final fakeService = _FakeAuthService(shouldFail: true);
      final container = makeContainer(authService: fakeService);
      await tester.pumpWidget(
        wrapWithMaterial(
          container,
          const LoginPage(),
        ),
      );
      await pumpLogin(tester);

      await tester.enterText(
        textFieldByLabel('账号'),
        'wrong_user',
      );
      await tester.enterText(
        textFieldByLabel('密码'),
        'wrong_pass',
      );
      await tester.pump();

      await tester.tap(find.text('登录'));
      await tester.pump();
      // 等待异步登录完成 + UI 更新
      await tester.pumpAndSettle(const Duration(milliseconds: 500));

      // 状态保持 unauthenticated
      final auth = container.read(authNotifierProvider);
      expect(auth.status, AuthStatus.unauthenticated);

      // 错误信息显示在 UI 上(用户友好文案)
      expect(find.textContaining('用户名或密码错误'), findsOneWidget);
    });

    testWidgets('密码字段默认隐藏,点击切换图标可显示', (tester) async {
      final container = makeContainer(
        authService: _FakeAuthService(),
      );
      await tester.pumpWidget(
        wrapWithMaterial(
          container,
          const LoginPage(),
        ),
      );
      await pumpLogin(tester);

      // 初始状态:密码隐藏(visibility_off 图标表示"当前隐藏,点击显示")
      expect(
        find.byIcon(Icons.visibility_off_outlined),
        findsOneWidget,
      );

      // 点击切换图标
      await tester.tap(find.byIcon(Icons.visibility_off_outlined));
      await tester.pump();

      // 切换后:显示密码(visibility 图标表示"当前显示")
      expect(
        find.byIcon(Icons.visibility_outlined),
        findsOneWidget,
      );
    });

    testWidgets('initialError 在 UI 上显示为错误横幅', (tester) async {
      final container = makeContainer(
        authService: _FakeAuthService(),
      );
      await tester.pumpWidget(
        wrapWithMaterial(
          container,
          const LoginPage(initialError: '会话已过期,请重新登录'),
        ),
      );
      await pumpLogin(tester);

      // 初始错误信息显示
      expect(find.textContaining('会话已过期'), findsOneWidget);
    });
  });

  group('LoginPage - 防重复提交', () {
    testWidgets('登录中按钮禁用并显示 loading 指示器', (tester) async {
      // 长延迟确保登录过程中能观察到 loading 状态
      final fakeService = _FakeAuthService(
        delay: const Duration(milliseconds: 800),
      );
      final container = makeContainer(authService: fakeService);
      await tester.pumpWidget(
        wrapWithMaterial(
          container,
          const LoginPage(),
        ),
      );
      await pumpLogin(tester);

      await tester.enterText(
        textFieldByLabel('账号'),
        'student_demo',
      );
      await tester.enterText(
        textFieldByLabel('密码'),
        'Demo123456',
      );
      await tester.pump();

      await tester.tap(find.text('登录'));
      await tester.pump();
      // 等待状态切换为 loading
      await tester.pump(const Duration(milliseconds: 50));

      // loading 状态:按钮文本变为"登录中..."
      expect(find.text('登录中...'), findsOneWidget);

      // 通过 FilledButton 的 enabled 状态判断按钮是否禁用
      final button = tester.widget<FilledButton>(
        find.byType(FilledButton),
      );
      expect(button.enabled, isFalse);

      // 等待登录完成,避免 Timer pending
      await tester.pumpAndSettle(const Duration(milliseconds: 1500));
    });
  });
}
