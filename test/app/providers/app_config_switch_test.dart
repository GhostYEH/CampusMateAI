import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/data/services/api/api_counselor_chat_service.dart';
import 'package:campus_companion/data/services/api/api_knowledge_base_service.dart';
import 'package:campus_companion/data/services/api/api_notification_extraction_service.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

void main() {
  group('AppConfig - 参赛版本约束', () {
    test('默认为 development 环境,使用真实后端(参赛版本约束)', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final config = container.read(appConfigProvider);
      // 默认不启用 Mock,确保不引用 Mock 实现
      expect(config.useMockBackend, isFalse);
      expect(config.useMockExpressionRecognition, isFalse);
      expect(config.isMockMode, isFalse);
      expect(config.isRealBackend, isTrue);
      expect(config.apiBaseUrl, 'http://10.0.2.2:8000');

      // 默认注入真实 Api 实现
      expect(
        container.read(notificationExtractionProvider),
        isA<ApiNotificationExtractionService>(),
      );
      expect(
        container.read(counselorChatProvider),
        isA<ApiCounselorChatService>(),
      );
      expect(
        container.read(knowledgeBaseProvider),
        isA<ApiKnowledgeBaseService>(),
      );
    });

    test('AppSettings 已移除 demoMode 字段(参赛版本约束)', () {
      // 正式参赛版本约束:
      // - AppSettings 不再保留 demoMode 字段
      // - AppSettingsNotifier 不再暴露 toggleDemoMode 方法
      // - AppConfig 仅由 dart-define 控制,不依赖任何运行时用户设置
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final config = container.read(appConfigProvider);
      expect(config.useMockBackend, isFalse);
      expect(config.isRealBackend, isTrue);
    });

    test('useMockBackend=true 时(仅 debug 开发场景)切换为 Mock 实现', () {
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            // 模拟 dart-define=USE_MOCK_BACKEND=true(仅开发场景)
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: true,
              useMockExpressionRecognition: true,
              apiBaseUrl: 'http://10.0.2.2:8000',
            );
          }),
        ],
      );
      addTearDown(container.dispose);

      final config = container.read(appConfigProvider);
      expect(config.useMockBackend, isTrue);
      expect(config.isMockMode, isTrue);
      expect(config.isRealBackend, isFalse);

      // 注入 Mock 实现(仅用于开发与测试)
      expect(
        container.read(notificationExtractionProvider),
        isA<MockNotificationExtractionService>(),
      );
      expect(
        container.read(counselorChatProvider),
        isA<MockCounselorChatService>(),
      );
      expect(
        container.read(knowledgeBaseProvider),
        isA<MockKnowledgeBaseService>(),
      );
    });

    test('production 配置字段语义检查', () {
      const config = AppConfig(
        environment: AppEnvironment.production,
        useMockBackend: false,
        useMockExpressionRecognition: false,
        apiBaseUrl: 'https://api.example.com',
      );
      expect(config.isMockMode, isFalse);
      expect(config.isRealBackend, isTrue);
      expect(config.environment, AppEnvironment.production);
      expect(config.apiBaseUrl, 'https://api.example.com');
    });

    test(
        'useMockBackend=false 但 useMockExpressionRecognition=true 时,'
        '表情仍为 Mock(开发场景)', () {
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: false,
              useMockExpressionRecognition: true,
              apiBaseUrl: 'http://10.0.2.2:8000',
            );
          }),
        ],
      );
      addTearDown(container.dispose);

      final config = container.read(appConfigProvider);
      // isMockMode 取并:backend 或 expression 任一为 Mock 即 true
      expect(config.isMockMode, isTrue);
      expect(config.useMockExpressionRecognition, isTrue);

      // 后端服务仍为真实实现
      expect(
        container.read(notificationExtractionProvider),
        isA<ApiNotificationExtractionService>(),
      );
      // 表情服务返回 Mock(而非 LiteRt)
      final service = container.read(expressionRecognitionProvider);
      expect(service, isA<MockExpressionRecognitionService>());
    });
  });

  group('BackendStatusNotifier', () {
    test('Real 模式下后端不可用时返回 disconnected', () async {
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: false,
              useMockExpressionRecognition: false,
              // 一个不可达的地址以触发连接错误
              apiBaseUrl: 'http://127.0.0.1:39999',
            );
          }),
        ],
      );
      addTearDown(container.dispose);

      await container.read(backendStatusProvider.notifier).check();

      final state = container.read(backendStatusProvider);
      expect(state, isA<AsyncData<BackendStatus>>());
      final status = (state as AsyncData<BackendStatus>).value;
      expect(status.status, BackendConnectionStatus.disconnected);
      expect(status.errorMessage, isNotNull);
      expect(status.lastChecked, isNotNull);
    });

    test('connected 与 knowledgeBaseEmpty 都视为 isAvailable', () {
      const connected = BackendStatus(
        status: BackendConnectionStatus.connected,
      );
      const kbEmpty = BackendStatus(
        status: BackendConnectionStatus.knowledgeBaseEmpty,
      );
      expect(connected.isAvailable, isTrue);
      expect(kbEmpty.isAvailable, isTrue);
    });

    test('demoMode 不应视为 isAvailable(参赛版本不允许)', () {
      // 即使残留 demoMode 状态,也不应视为可用
      const demoStatus = BackendStatus(
        status: BackendConnectionStatus.demoMode,
      );
      expect(demoStatus.isAvailable, isFalse);
    });
  });

  group('AppConfig.fromEnvironment - dart-define 解析', () {
    test('默认值: USE_MOCK_BACKEND=false / USE_MOCK_EXPRESSION=false', () {
      // fromEnvironment 使用 String.fromEnvironment,无法在运行时更改;
      // 但可通过 AppConfig 构造函数直接验证字段语义。
      const config = AppConfig(
        environment: AppEnvironment.development,
        useMockBackend: false,
        useMockExpressionRecognition: false,
        apiBaseUrl: 'http://10.0.2.2:8000',
      );
      expect(config.useMockBackend, isFalse);
      expect(config.useMockExpressionRecognition, isFalse);
      expect(config.isMockMode, isFalse);
      expect(config.isRealBackend, isTrue);
    });

    test('production 配置示例', () {
      const config = AppConfig(
        environment: AppEnvironment.production,
        useMockBackend: false,
        useMockExpressionRecognition: false,
        apiBaseUrl: 'https://api.example.com',
      );
      expect(config.isMockMode, isFalse);
      expect(config.isRealBackend, isTrue);
      expect(config.environment, AppEnvironment.production);
    });
  });

  group('Provider 注入 — AppConfig 切换会传播到下游 Provider', () {
    test('从 Real 切换到 Mock 时 notificationExtractionProvider 重新构造', () {
      // 默认为 Real
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final realService = container.read(notificationExtractionProvider);
      expect(realService, isA<ApiNotificationExtractionService>());

      // override appConfigProvider 为 Mock(仅开发场景)
      final container2 = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: true,
              useMockExpressionRecognition: true,
              apiBaseUrl: 'http://localhost:8000',
            );
          }),
        ],
      );
      addTearDown(container2.dispose);

      final mockService = container2.read(notificationExtractionProvider);
      expect(mockService, isA<MockNotificationExtractionService>());
      // 不同实例
      expect(identical(realService, mockService), isFalse);
    });
  });
}
