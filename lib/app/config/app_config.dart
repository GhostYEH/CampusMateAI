import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/app_providers.dart';

/// 应用运行环境。
///
/// 用于决定 Provider 注入 Mock 实现还是真实实现。
/// - [demo]: 比赛演示模式,使用 Mock,完整演示数据链路。
/// - [development]: 开发模式,可通过 dart-define 切换 Mock/Real。
/// - [production]: 生产模式,使用真实后端 / LiteRT(预留)。
enum AppEnvironment {
  demo,
  development,
  production,
}

/// 应用配置 — 决定服务实现注入策略。
///
/// 通过 dart-define 注入:
/// - `USE_MOCK_BACKEND` (true|false): 是否使用 Mock 后端
/// - `API_BASE_URL`: 真实后端地址(如 http://10.0.2.2:8000)
/// - `USE_MOCK_EXPRESSION` (true|false): 是否使用 Mock 表情识别
///
/// 默认(Mock 模式)保证现有功能继续可用;
/// 比赛演示模式与"恢复演示数据"不受后端可用性影响。
class AppConfig {
  const AppConfig({
    required this.environment,
    required this.useMockBackend,
    required this.useMockExpressionRecognition,
    required this.enableDemoMode,
    required this.apiBaseUrl,
  });

  final AppEnvironment environment;
  final bool useMockBackend;
  final bool useMockExpressionRecognition;
  final bool enableDemoMode;

  /// 后端 API 基础 URL。
  /// - Mock 模式:可为空
  /// - Real 模式:必填,Android 模拟器默认 http://10.0.2.2:8000
  final String apiBaseUrl;

  /// 是否为 Mock 模式(便于 UI 显示"模拟模式"标识)。
  bool get isMockMode => useMockBackend || useMockExpressionRecognition;

  /// 是否为真实后端模式。
  bool get isRealBackend => !useMockBackend;

  /// 解析 dart-define 的基础配置(不依赖 AppSettings,可在 Provider 中读取)。
  ///
  /// dart-define 注入键:
  /// - `USE_MOCK_BACKEND` (true|false): 默认 true
  /// - `USE_MOCK_EXPRESSION` (true|false): 默认 true
  /// - `API_BASE_URL`: 默认 http://10.0.2.2:8000(Android 模拟器)
  static AppConfig fromEnvironment({required bool demoMode}) {
    final useMockStr = const String.fromEnvironment(
      'USE_MOCK_BACKEND',
      defaultValue: 'true',
    ).toLowerCase();
    final useMock = !(useMockStr == 'false' || useMockStr == '0');

    final useMockExprStr = const String.fromEnvironment(
      'USE_MOCK_EXPRESSION',
      defaultValue: 'true',
    ).toLowerCase();
    final useMockExpr = !(useMockExprStr == 'false' || useMockExprStr == '0');

    const apiBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    );
    return AppConfig(
      environment: AppEnvironment.development,
      useMockBackend: useMock,
      useMockExpressionRecognition: useMockExpr,
      enableDemoMode: demoMode,
      apiBaseUrl: apiBaseUrl,
    );
  }
}

/// 应用配置 Provider — 根据用户设置 + dart-define 派生。
///
/// 行为:
/// - `USE_MOCK_BACKEND=false` 时切换到真实后端实现(由 Provider 注入)。
/// - `USE_MOCK_BACKEND` 未定义或为 true 时,使用 Mock 实现(保证现有功能可用)。
/// - 比赛演示模式([AppSettings.demoMode])始终可启用,与后端模式独立。
final appConfigProvider = Provider<AppConfig>((ref) {
  final settings = ref.watch(appSettingsProvider);
  return AppConfig.fromEnvironment(demoMode: settings.demoMode);
});
