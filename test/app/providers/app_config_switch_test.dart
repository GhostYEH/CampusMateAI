import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/data/services/api/api_counselor_chat_service.dart';
import 'package:campus_companion/data/services/api/api_knowledge_base_service.dart';
import 'package:campus_companion/data/services/api/api_notification_extraction_service.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

void main() {
  group('AppConfig - Mock / Real Backend 切换', () {
    test('默认为 Mock 模式,所有服务返回 Mock 实现', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final config = container.read(appConfigProvider);
      expect(config.useMockBackend, isTrue);
      expect(config.isMockMode, isTrue);
      expect(config.isRealBackend, isFalse);
      expect(config.apiBaseUrl, 'http://10.0.2.2:8000');

      // 注入 Mock 实现
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

    test('useMockBackend=false 时切换为真实 Api 实现', () {
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            // 模拟 dart-define=USE_MOCK_BACKEND=false
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: false,
              useMockExpressionRecognition: true,
              enableDemoMode: false,
              apiBaseUrl: 'http://10.0.2.2:8000',
            );
          }),
        ],
      );
      addTearDown(container.dispose);

      final config = container.read(appConfigProvider);
      expect(config.useMockBackend, isFalse);
      expect(config.isRealBackend, isTrue);

      // 注入真实 Api 实现
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

    test('useMockBackend=false 但 useMockExpressionRecognition=true 时,表情仍为 Mock',
        () {
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: false,
              useMockExpressionRecognition: true,
              enableDemoMode: false,
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

      // 表情服务返回 Mock(而非 LiteRt)
      final service = container.read(expressionRecognitionProvider);
      expect(service, isA<MockExpressionRecognitionService>());
    });

    test('useMockBackend 与 useMockExpressionRecognition 同时关闭时为 production', () {
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.production,
              useMockBackend: false,
              useMockExpressionRecognition: false,
              enableDemoMode: false,
              apiBaseUrl: 'http://prod.local',
            );
          }),
        ],
      );
      addTearDown(container.dispose);

      final config = container.read(appConfigProvider);
      expect(config.isMockMode, isFalse);
      expect(config.isRealBackend, isTrue);
      expect(config.apiBaseUrl, 'http://prod.local');

      // 真实后端服务被注入
      expect(
        container.read(notificationExtractionProvider),
        isA<ApiNotificationExtractionService>(),
      );
    });

    test('demoMode 与 useMockBackend 独立切换', () {
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: false,
              useMockExpressionRecognition: true,
              enableDemoMode: true,
              apiBaseUrl: 'http://10.0.2.2:8000',
            );
          }),
        ],
      );
      addTearDown(container.dispose);

      final config = container.read(appConfigProvider);
      // 演示模式可独立于后端模式启用
      expect(config.enableDemoMode, isTrue);
      expect(config.useMockBackend, isFalse);
      // 演示模式 + 真实后端:RAG 仍调用真实后端
      expect(
        container.read(counselorChatProvider),
        isA<ApiCounselorChatService>(),
      );
    });
  });

  group('BackendStatusNotifier', () {
    test('Mock 模式下 check() 直接返回 demoMode', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // 默认为 Mock 模式
      await container.read(backendStatusProvider.notifier).check();

      final state = container.read(backendStatusProvider);
      expect(state, isA<AsyncData<BackendStatus>>());
      final status = (state as AsyncData<BackendStatus>).value;
      expect(status.status, BackendConnectionStatus.demoMode);
      expect(status.version, isEmpty);
      expect(status.documentCount, 0);
    });

    test('Real 模式下后端不可用时返回 disconnected', () async {
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: false,
              useMockExpressionRecognition: true,
              enableDemoMode: false,
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

    test('Mock 模式下 isAvailable 返回 false(demoMode 不等于 connected)', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      const status = BackendStatus(
        status: BackendConnectionStatus.demoMode,
      );
      expect(status.isAvailable, isFalse);
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
  });

  group('AppConfig.fromEnvironment - dart-define 解析', () {
    test('默认值: USE_MOCK_BACKEND=true / USE_MOCK_EXPRESSION=true', () {
      // fromEnvironment 使用 String.fromEnvironment,无法在运行时更改;
      // 但可通过 AppConfig 构造函数直接验证字段语义。
      const config = AppConfig(
        environment: AppEnvironment.development,
        useMockBackend: true,
        useMockExpressionRecognition: true,
        enableDemoMode: false,
        apiBaseUrl: 'http://10.0.2.2:8000',
      );
      expect(config.useMockBackend, isTrue);
      expect(config.useMockExpressionRecognition, isTrue);
      expect(config.isMockMode, isTrue);
    });

    test('production 配置示例', () {
      const config = AppConfig(
        environment: AppEnvironment.production,
        useMockBackend: false,
        useMockExpressionRecognition: false,
        enableDemoMode: false,
        apiBaseUrl: 'https://api.example.com',
      );
      expect(config.isMockMode, isFalse);
      expect(config.isRealBackend, isTrue);
      expect(config.environment, AppEnvironment.production);
    });
  });

  group('Provider 注入 — AppConfig 切换会传播到下游 Provider', () {
    test('从 Mock 切换到 Real 时 notificationExtractionProvider 重新构造', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // 初始 Mock
      final mockService = container.read(notificationExtractionProvider);
      expect(mockService, isA<MockNotificationExtractionService>());

      // override appConfigProvider 为 Real
      // (实际场景中由 dart-define 决定,这里通过 override 模拟)
      // 注意:override 后,新读取的 Provider 会重建
      final container2 = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWith((ref) {
            return const AppConfig(
              environment: AppEnvironment.development,
              useMockBackend: false,
              useMockExpressionRecognition: true,
              enableDemoMode: false,
              apiBaseUrl: 'http://localhost:8000',
            );
          }),
        ],
      );
      addTearDown(container2.dispose);

      final realService = container2.read(notificationExtractionProvider);
      expect(realService, isA<ApiNotificationExtractionService>());
      // 不同实例
      expect(identical(mockService, realService), isFalse);
    });
  });
}
