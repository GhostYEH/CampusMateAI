import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/app_providers.dart';

/// 应用运行环境。
///
/// 用于决定 Provider 注入 Mock 实现还是真实实现。
/// - [demo]: 比赛演示模式,使用 Mock,完整演示数据链路。
/// - [development]: 开发模式,使用 Mock,但数据可清空。
/// - [production]: 生产模式,使用真实后端 / LiteRT(预留)。
enum AppEnvironment {
  demo,
  development,
  production,
}

/// 应用配置 — 决定服务实现注入策略。
///
/// 当前阶段(第二阶段)始终使用 Mock 实现,但保留切换为真实实现的入口:
/// - [useMockBackend]: 是否使用 Mock 后端(NotificationExtraction/Task/Counselor 等)
/// - [useMockExpressionRecognition]: 是否使用 Mock 表情识别服务
/// - [enableDemoMode]: 是否启用比赛演示模式(显示 Mock 控制台、演示数据)
class AppConfig {
  const AppConfig({
    required this.environment,
    required this.useMockBackend,
    required this.useMockExpressionRecognition,
    required this.enableDemoMode,
  });

  final AppEnvironment environment;
  final bool useMockBackend;
  final bool useMockExpressionRecognition;
  final bool enableDemoMode;

  /// 是否为 Mock 模式(便于 UI 显示"模拟模式"标识)。
  bool get isMockMode => useMockBackend || useMockExpressionRecognition;
}

/// 应用配置 Provider — 根据用户设置派生。
///
/// 当前阶段:useMockBackend 与 useMockExpressionRecognition 始终为 true,
/// 仅 [AppSettings.demoMode] 与 [AppEnvironment] 会随用户操作变化。
final appConfigProvider = Provider<AppConfig>((ref) {
  final settings = ref.watch(appSettingsProvider);
  return AppConfig(
    environment: AppEnvironment.development,
    useMockBackend: true,
    useMockExpressionRecognition: true,
    enableDemoMode: settings.demoMode,
  );
});
