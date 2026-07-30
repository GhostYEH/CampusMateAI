import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 应用运行环境。
///
/// 用于决定 Provider 注入 Mock 实现还是真实实现。
/// - [development]: 开发模式,可通过 dart-define 切换 Mock/Real(仅 debug)。
/// - [production]: 生产模式,强制使用真实后端 / LiteRT(预留)。
enum AppEnvironment {
  development,
  production,
}

/// 应用配置 — 决定服务实现注入策略。
///
/// 通过 dart-define 注入:
/// - `USE_MOCK_BACKEND` (true|false): 是否使用 Mock 后端(默认 false,
///   仅在 debug 模式下生效,release 强制为 false)
/// - `API_BASE_URL`: 真实后端地址(如 http://10.0.2.2:8000)
/// - `USE_MOCK_EXPRESSION` (true|false): 是否使用 Mock 表情识别
/// - `RESTRICT_TO_STUDENT` (true|false): 是否将非学生角色拦截在登录页
///   (默认 false。打包学生专用 APK 时传 true,Web 端不传保持 false)
///
/// 正式参赛版本约束(遵循 AGENTS.md §2.4 接口优先, Mock 可替换):
/// - Release 构建强制 `useMockBackend=false`,确保不引用 Mock 实现。
/// - 登录必须调用真实认证接口,不提供绕过认证的快捷入口。
/// - Mock 实现仅供开发与测试使用,通过测试依赖注入控制。
class AppConfig {
  const AppConfig({
    required this.environment,
    required this.useMockBackend,
    required this.useMockExpressionRecognition,
    required this.apiBaseUrl,
    this.restrictToStudent = false,
  });

  final AppEnvironment environment;

  /// 是否使用 Mock 后端。
  ///
  /// 仅在 debug 模式下可由 dart-define `USE_MOCK_BACKEND=true` 启用,
  /// release 模式下始终为 false。
  final bool useMockBackend;

  /// 是否使用 Mock 表情识别。
  final bool useMockExpressionRecognition;

  /// 后端 API 基础 URL。
  /// - Mock 模式:可为空
  /// - Real 模式:必填,Android 模拟器默认 http://10.0.2.2:8000
  final String apiBaseUrl;

  /// 是否仅允许学生角色登录(用于学生专用 APK 打包)。
  ///
  /// 为 true 时,登录成功后若用户角色不是 student,会拒绝进入应用并提示
  /// 「请使用 Web 端登录教师/管理员账号」,session 不会被持久化。
  ///
  /// 仅在非 Web 平台生效(Web 端师生均可,通过 [effectiveRestrictToStudent] 计算)。
  /// 默认 false,Web 端与教师 APK 不传此 define 时保持开放。
  final bool restrictToStudent;

  /// 实际生效的「仅学生」开关。
  ///
  /// Web 平台永远返回 false(师生均可使用 Web);
  /// 原生平台(Android/iOS/桌面)返回 [restrictToStudent] 的值。
  bool get effectiveRestrictToStudent {
    if (kIsWeb) return false;
    return restrictToStudent;
  }

  /// 是否为 Mock 模式(便于在 debug 下显示"模拟模式"标识)。
  bool get isMockMode => useMockBackend || useMockExpressionRecognition;

  /// 是否为真实后端模式。
  bool get isRealBackend => !useMockBackend;

  /// 解析 dart-define 的基础配置。
  ///
  /// dart-define 注入键:
  /// - `USE_MOCK_BACKEND` (true|false): 默认 false;release 模式下强制 false
  /// - `USE_MOCK_EXPRESSION` (true|false): 默认 false;release 模式下强制 false
  /// - `API_BASE_URL`: 默认 http://10.0.2.2:8000(Android 模拟器)
  /// - `RESTRICT_TO_STUDENT` (true|false): 默认 false;Web 端永远为 false
  static AppConfig fromEnvironment() {
    // RESTRICT_TO_STUDENT 在所有模式下都生效(包括 release),由 dart-define 控制。
    // Web 平台永远为 false(由 [effectiveRestrictToStudent] 兜底,这里仍读取原值)。
    final restrictStr = const String.fromEnvironment(
      'RESTRICT_TO_STUDENT',
      defaultValue: 'false',
    ).toLowerCase();
    final restrictToStudent = restrictStr == 'true' || restrictStr == '1';

    // Release 模式下强制禁用所有 Mock,保证正式参赛版本不引用 Mock 实现
    if (kReleaseMode) {
      const apiBaseUrl = String.fromEnvironment(
        'API_BASE_URL',
        defaultValue: 'http://10.0.2.2:8000',
      );
      return AppConfig(
        environment: AppEnvironment.production,
        useMockBackend: false,
        useMockExpressionRecognition: false,
        apiBaseUrl: apiBaseUrl,
        restrictToStudent: restrictToStudent,
      );
    }

    // Debug / Profile 模式下允许通过 dart-define 切换 Mock
    final useMockStr = const String.fromEnvironment(
      'USE_MOCK_BACKEND',
      defaultValue: 'false',
    ).toLowerCase();
    final useMock = useMockStr == 'true' || useMockStr == '1';

    final useMockExprStr = const String.fromEnvironment(
      'USE_MOCK_EXPRESSION',
      defaultValue: 'false',
    ).toLowerCase();
    final useMockExpr = useMockExprStr == 'true' || useMockExprStr == '1';

    const apiBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    );
    return AppConfig(
      environment: AppEnvironment.development,
      useMockBackend: useMock,
      useMockExpressionRecognition: useMockExpr,
      apiBaseUrl: apiBaseUrl,
      restrictToStudent: restrictToStudent,
    );
  }
}

/// 应用配置 Provider — 仅依赖 dart-define,与 AppSettings 解耦。
///
/// 行为:
/// - Release 模式:强制真实后端,不读取任何运行时开关。
/// - Debug / Profile 模式:可通过 `USE_MOCK_BACKEND=true` 启用 Mock 实现,
///   仅供开发与测试使用,不在普通用户界面暴露。
final appConfigProvider = Provider<AppConfig>((ref) {
  return AppConfig.fromEnvironment();
});
