import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/features/profile/presentation/widgets/backend_status_card.dart';

/// 用于在测试中注入固定 BackendStatus 的假 Notifier。
///
/// [BackendStatusNotifier] 默认会异步调用真实 ApiClient,
/// 在 Widget 测试中我们希望直接控制 state 而不触发网络请求,
/// 因此用一个子类在构造后立即覆盖 state,并让 check() 成为 no-op。
class _FakeBackendStatusNotifier extends BackendStatusNotifier {
  _FakeBackendStatusNotifier(AsyncValue<BackendStatus> initial)
      : super(() => throw UnimplementedError()) {
    state = initial;
  }

  /// 测试 stub:点击"重试"时不触发真实网络请求,保持当前 state 不变。
  @override
  Future<void> check() async {}
}

void main() {
  Widget wrapApp(ProviderContainer container) {
    return UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: Scaffold(body: BackendStatusCard()),
      ),
    );
  }

  ProviderContainer mockContainer() {
    final container = ProviderContainer(
      overrides: [
        // 显式注入 Mock 模式配置(仅开发/测试场景)
        appConfigProvider.overrideWith((ref) {
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
    return container;
  }

  /// 注入 Real Backend 配置 + 指定初始 BackendStatus 的容器。
  ProviderContainer realBackendContainer({
    required BackendStatus initialStatus,
    String apiBaseUrl = 'http://10.0.2.2:8000',
  }) {
    final container = ProviderContainer(
      overrides: [
        appConfigProvider.overrideWith((ref) {
          return AppConfig(
            environment: AppEnvironment.development,
            useMockBackend: false,
            useMockExpressionRecognition: true,
            apiBaseUrl: apiBaseUrl,
          );
        }),
        backendStatusProvider.overrideWith(
          (ref) => _FakeBackendStatusNotifier(
            AsyncValue<BackendStatus>.data(initialStatus),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  /// 注入 Real Backend 配置 + loading 状态的容器。
  ProviderContainer realBackendLoadingContainer({
    String apiBaseUrl = 'http://test.local',
  }) {
    final container = ProviderContainer(
      overrides: [
        appConfigProvider.overrideWith((ref) {
          return AppConfig(
            environment: AppEnvironment.development,
            useMockBackend: false,
            useMockExpressionRecognition: true,
            apiBaseUrl: apiBaseUrl,
          );
        }),
        backendStatusProvider.overrideWith(
          (ref) => _FakeBackendStatusNotifier(
            const AsyncValue<BackendStatus>.loading(),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  group('BackendStatusCard - Mock 模式(开发场景)', () {
    testWidgets('渲染"服务暂时不可用"标题(不暴露 Mock 字样)', (tester) async {
      final container = mockContainer();
      await tester.pumpWidget(wrapApp(container));
      await tester.pump();

      // 参赛版本约束:不向用户暴露"演示模式"字样,
      // 统一显示为"服务暂时不可用"
      expect(find.text('服务暂时不可用'), findsOneWidget);
      expect(find.text('演示模式'), findsNothing);
      expect(find.textContaining('Mock'), findsNothing);
      expect(find.text('API 地址'), findsOneWidget);
    });

    testWidgets('Mock 模式提供"重试"按钮以重试连接后端', (tester) async {
      final container = mockContainer();
      await tester.pumpWidget(wrapApp(container));
      await tester.pump();

      // Mock 模式视为 disconnected,提供重试入口
      expect(find.text('重试'), findsOneWidget);
    });
  });

  group('BackendStatusCard - Real Backend 已连接', () {
    testWidgets('connected 状态显示"已连接 · 知识库就绪"', (tester) async {
      final container = realBackendContainer(
        initialStatus: const BackendStatus(
          status: BackendConnectionStatus.connected,
          version: '0.2.0',
          documentCount: 5,
          chunkCount: 42,
          llmAvailable: true,
        ),
      );
      await tester.pumpWidget(wrapApp(container));
      await tester.pump();

      expect(find.text('已连接 · 知识库就绪'), findsOneWidget);
      expect(find.textContaining('FastAPI 后端已连接'), findsOneWidget);
      expect(find.text('后端版本'), findsOneWidget);
      expect(find.text('0.2.0'), findsOneWidget);
      expect(find.text('已索引文档'), findsOneWidget);
      expect(find.text('5 份'), findsOneWidget);
      expect(find.text('索引分块'), findsOneWidget);
      expect(find.text('42 段'), findsOneWidget);
      expect(find.text('LLM Provider'), findsOneWidget);
      expect(find.text('已启用'), findsOneWidget);
    });

    testWidgets('knowledgeBaseEmpty 状态显示"已连接 · 知识库未初始化"', (tester) async {
      final container = realBackendContainer(
        initialStatus: const BackendStatus(
          status: BackendConnectionStatus.knowledgeBaseEmpty,
          version: '0.2.0',
          documentCount: 0,
          chunkCount: 0,
          llmAvailable: false,
        ),
      );
      await tester.pumpWidget(wrapApp(container));
      await tester.pump();

      expect(find.text('已连接 · 知识库未初始化'), findsOneWidget);
      expect(find.textContaining('知识库尚未导入文档'), findsOneWidget);
      // LLM 未配置时显示检索摘要模式提示
      expect(find.text('未配置(检索摘要模式)'), findsOneWidget);
    });
  });

  group('BackendStatusCard - 未连接状态', () {
    testWidgets('disconnected 状态显示"服务暂时不可用"与重试按钮', (tester) async {
      final container = realBackendContainer(
        initialStatus: const BackendStatus(
          status: BackendConnectionStatus.disconnected,
          errorMessage: 'Connection refused',
        ),
      );
      await tester.pumpWidget(wrapApp(container));
      await tester.pump();

      // 参赛版本约束:不暴露"未连接"等内部状态字样,统一显示为"服务暂时不可用"
      expect(find.text('服务暂时不可用'), findsOneWidget);
      expect(find.textContaining('无法连接到后端服务'), findsOneWidget);
      // 重试按钮可见
      expect(find.text('重试'), findsOneWidget);
      // 错误信息以温和方式展示
      expect(find.text('Connection refused'), findsOneWidget);
    });

    testWidgets('点击重试按钮不抛异常(Notifier 已被假实现替换)', (tester) async {
      final container = realBackendContainer(
        initialStatus: const BackendStatus(
          status: BackendConnectionStatus.disconnected,
          errorMessage: 'old error',
        ),
        apiBaseUrl: 'http://test.local',
      );

      await tester.pumpWidget(wrapApp(container));
      await tester.pump();

      // 初始 disconnected
      expect(find.text('服务暂时不可用'), findsOneWidget);

      // 点击重试(假 Notifier 的 check 不会被调用,但 UI 不应崩溃)
      await tester.tap(find.text('重试'));
      await tester.pump();
      // 仍处于 disconnected
      expect(find.text('服务暂时不可用'), findsOneWidget);
    });
  });

  group('BackendStatusCard - 检查中状态', () {
    testWidgets('checking 状态显示"检查中"与加载指示器', (tester) async {
      final container = realBackendLoadingContainer();
      await tester.pumpWidget(wrapApp(container));
      await tester.pump();

      expect(find.text('检查中'), findsOneWidget);
      expect(find.textContaining('正在连接后端'), findsOneWidget);
      // CircularProgressIndicator 可见
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });

  group('BackendStatusCard - API 地址展示', () {
    testWidgets('正确显示 apiBaseUrl', (tester) async {
      final container = realBackendContainer(
        initialStatus: const BackendStatus(
          status: BackendConnectionStatus.connected,
          version: '0.2.0',
          documentCount: 1,
          chunkCount: 1,
          llmAvailable: false,
        ),
        apiBaseUrl: 'http://10.0.2.2:8000',
      );

      await tester.pumpWidget(wrapApp(container));
      await tester.pump();

      expect(find.text('http://10.0.2.2:8000'), findsOneWidget);
    });
  });
}
