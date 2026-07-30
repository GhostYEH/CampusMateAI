import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/auth.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/multi_role_service_interfaces.dart';

/// 可配置返回角色的 Fake AuthService,用于测试学生专用 APK 拦截逻辑。
class _FakeAuthService implements AuthService {
  _FakeAuthService({this.returnedRole = UserRole.student});

  final UserRole returnedRole;

  /// 记录 logout 是否被调用(用于验证拦截后是否撤销了服务端 token)。
  bool logoutCalled = false;
  String? lastLogoutRefreshToken;

  @override
  Future<AuthSession> login(LoginCredentials credentials) async {
    // 模拟轻微延迟,让 loading 状态可观察
    await Future.delayed(const Duration(milliseconds: 20));
    return AuthSession(
      user: AppUser(
        id: 'u_test_${returnedRole.name}',
        name: '测试${returnedRole.displayName}',
        role: returnedRole,
        avatarSeed: 'test',
      ),
      accessToken: 'fake.access.token',
      refreshToken: 'fake.refresh.token',
      expiresAt: DateTime.now().add(const Duration(hours: 1)),
    );
  }

  @override
  Future<AppUser> register(RegisterCredentials credentials) async {
    throw const ApiException(
      code: 'NOT_USED',
      message: 'register not used in this test',
      httpStatus: 400,
    );
  }

  @override
  Future<AuthSession> refresh(String refreshToken) async {
    throw const ApiException(
      code: 'INVALID_REFRESH_TOKEN',
      message: 'not used',
      httpStatus: 401,
    );
  }

  @override
  Future<void> logout(String refreshToken) async {
    logoutCalled = true;
    lastLogoutRefreshToken = refreshToken;
  }

  @override
  Future<AppUser> getCurrentUser() async {
    return AppUser(
      id: 'u_test_${returnedRole.name}',
      name: '测试${returnedRole.displayName}',
      role: returnedRole,
      avatarSeed: 'test',
    );
  }
}

void main() {
  /// 构造可注入 AppConfig + FakeAuthService 的 ProviderContainer。
  ///
  /// 关键点:
  /// - 通过 appConfigProvider.overrideWith 注入 restrictToStudent 字段
  /// - effectiveRestrictToStudent 在测试环境下(kIsWeb=true)默认为 false,
  ///   所以我们直接通过 override AppConfig 的方式测试 login 内部判断逻辑,
  ///   让 config.effectiveRestrictToStudent 返回 true 来模拟原生 APK。
  ///   这需要使用一个 wrapper AppConfig 子类。
  ProviderContainer makeContainer({
    required AuthService authService,
    required bool restrictToStudent,
  }) {
    final container = ProviderContainer(
      overrides: [
        appConfigProvider.overrideWith((ref) {
          // 构造一个 AppConfig,手动覆盖 effectiveRestrictToStudent 的行为
          // 通过 useMockBackend=true 跳过 TokenStorage 真实初始化
          return _TestAppConfig(
            restrictToStudent: restrictToStudent,
          );
        }),
        authServiceProvider.overrideWithValue(authService),
        // 关闭动画,避免 Timer pending
        reduceMotionProvider.overrideWith((ref) => true),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  test(
      'RESTRICT_TO_STUDENT=true 时学生角色登录正常通过',
      () async {
    final fake = _FakeAuthService(returnedRole: UserRole.student);
    final container = makeContainer(
      authService: fake,
      restrictToStudent: true,
    );

    final notifier = container.read(authNotifierProvider.notifier);
    // 等待 _init() 完成(Mock 模式直接 unauthenticated)
    // 因为 useMockBackend=true,_init 不会读取 TokenStorage
    await Future.delayed(const Duration(milliseconds: 50));

    final session = await notifier.login(
      const LoginCredentials(username: 'student_demo', password: 'Demo123456'),
    );

    final auth = container.read(authNotifierProvider);
    expect(session, isNotNull);
    expect(session!.user.role, UserRole.student);
    expect(auth.status, AuthStatus.authenticated);
    expect(auth.errorMessage, isNull);
    // 学生登录不应触发 logout
    expect(fake.logoutCalled, isFalse);
  });

  test(
      'RESTRICT_TO_STUDENT=true 时教师角色登录被拦截',
      () async {
    final fake = _FakeAuthService(returnedRole: UserRole.teacher);
    final container = makeContainer(
      authService: fake,
      restrictToStudent: true,
    );

    final notifier = container.read(authNotifierProvider.notifier);
    await Future.delayed(const Duration(milliseconds: 50));

    final session = await notifier.login(
      const LoginCredentials(username: 'teacher_demo', password: 'Demo123456'),
    );

    final auth = container.read(authNotifierProvider);
    // 拦截:返回 null,状态保持 unauthenticated
    expect(session, isNull);
    expect(auth.status, AuthStatus.unauthenticated);
    // 错误文案包含角色名和引导文案
    expect(auth.errorMessage, isNotNull);
    expect(auth.errorMessage, contains('教师'));
    expect(auth.errorMessage, contains('Web 端'));
    // 已签发的 token 应被主动撤销(避免悬挂会话)
    expect(fake.logoutCalled, isTrue);
    expect(fake.lastLogoutRefreshToken, 'fake.refresh.token');
  });

  test(
      'RESTRICT_TO_STUDENT=true 时管理员角色登录被拦截',
      () async {
    final fake = _FakeAuthService(returnedRole: UserRole.admin);
    final container = makeContainer(
      authService: fake,
      restrictToStudent: true,
    );

    final notifier = container.read(authNotifierProvider.notifier);
    await Future.delayed(const Duration(milliseconds: 50));

    final session = await notifier.login(
      const LoginCredentials(username: 'admin_demo', password: 'Demo123456'),
    );

    final auth = container.read(authNotifierProvider);
    expect(session, isNull);
    expect(auth.status, AuthStatus.unauthenticated);
    expect(auth.errorMessage, contains('管理员'));
    expect(fake.logoutCalled, isTrue);
  });

  test(
      'RESTRICT_TO_STUDENT=false 时教师角色登录正常通过(模拟 Web 端)',
      () async {
    final fake = _FakeAuthService(returnedRole: UserRole.teacher);
    final container = makeContainer(
      authService: fake,
      restrictToStudent: false, // 模拟 Web 端或非限制 APK
    );

    final notifier = container.read(authNotifierProvider.notifier);
    await Future.delayed(const Duration(milliseconds: 50));

    final session = await notifier.login(
      const LoginCredentials(username: 'teacher_demo', password: 'Demo123456'),
    );

    final auth = container.read(authNotifierProvider);
    // 不拦截:正常登录
    expect(session, isNotNull);
    expect(session!.user.role, UserRole.teacher);
    expect(auth.status, AuthStatus.authenticated);
    expect(auth.errorMessage, isNull);
    expect(fake.logoutCalled, isFalse);
  });

  test('错误文案不暴露具体账号是否存在(避免用户名枚举)', () async {
    final fake = _FakeAuthService(returnedRole: UserRole.teacher);
    final container = makeContainer(
      authService: fake,
      restrictToStudent: true,
    );

    final notifier = container.read(authNotifierProvider.notifier);
    await Future.delayed(const Duration(milliseconds: 50));

    await notifier.login(
      const LoginCredentials(username: 'any_username', password: 'any_pwd'),
    );

    final auth = container.read(authNotifierProvider);
    // 文案应包含角色 + 引导,不直接暴露服务端返回的具体账号信息
    expect(auth.errorMessage, contains('请使用 Web 端登录'));
  });
}

/// 测试专用 AppConfig 子类。
///
/// 通过 override [effectiveRestrictToStudent] 让其在 Web 测试环境下
/// 也能返回 true(模拟原生 APK 行为),从而测试拦截逻辑。
class _TestAppConfig extends AppConfig {
  _TestAppConfig({required super.restrictToStudent})
      : super(
          environment: AppEnvironment.development,
          useMockBackend: true, // 避免 TokenStorage 真实初始化
          useMockExpressionRecognition: true,
          apiBaseUrl: 'http://10.0.2.2:8000',
        );

  /// 永远返回 [restrictToStudent] 的值,忽略 kIsWeb(用于测试)。
  /// 在生产代码中,Web 平台会返回 false(由 [AppConfig.effectiveRestrictToStudent] 兜底)。
  @override
  bool get effectiveRestrictToStudent => restrictToStudent;
}
