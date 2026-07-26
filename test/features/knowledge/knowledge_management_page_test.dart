import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/knowledge.dart';
import 'package:campus_companion/features/knowledge/presentation/knowledge_management_page.dart';
import 'package:campus_companion/mock/mock_services/mock_knowledge_management_service.dart';

void main() {
  /// 构造测试用演示文档(包含 isDemo=true,触发演示资料声明)。
  List<KnowledgeDocumentSummary> demoDocuments() => [
        KnowledgeDocumentSummary(
          documentId: 'demo_1',
          title: '新生入学指南',
          contentHash: 'hash_demo_1',
          isOfficial: true,
          isExpired: false,
          isDemo: true,
          importedAt: DateTime(2024, 9, 1),
          sourceDepartment: '演示资料',
          sourceType: 'guide',
          originalFilename: '新生入学指南.md',
          fileSize: 12 * 1024,
          fileExt: 'md',
        ),
        KnowledgeDocumentSummary(
          documentId: 'demo_2',
          title: '综合测评实施细则',
          contentHash: 'hash_demo_2',
          isOfficial: true,
          isExpired: false,
          isDemo: true,
          importedAt: DateTime(2024, 9, 2),
          sourceDepartment: '演示资料',
          sourceType: 'policy',
          originalFilename: '综合测评实施细则.md',
          fileSize: 12 * 1024,
          fileExt: 'md',
        ),
      ];

  /// 构造可覆盖知识库服务的 ProviderContainer。
  ///
  /// 注入 [FakeKnowledgeManagementService] 与 reduceMotionProvider=true(跳过动画)。
  ProviderContainer makeContainer({
    required FakeKnowledgeManagementService service,
  }) {
    final container = ProviderContainer(
      overrides: [
        knowledgeManagementProvider.overrideWithValue(service),
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

  void setPhoneViewport(WidgetTester tester) {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  /// 推进首帧 + 让异步加载完成 + 让 StaggeredEnter 的 Future.delayed 定时器与动画完成。
  ///
  /// StaggeredEnter 在 initState 中通过 Future.delayed(delay, ...) 创建定时器,
  /// 即使 reduceMotionProvider=true(build 直接返回 child),定时器与 AnimationController
  /// 仍然会创建。需要 pump 足够时间让它们完成,否则测试结束时会有 pending timer。
  /// 知识库页面最大 delay=120ms,动画时长约 280ms,总计约 400ms,留余量到 800ms。
  Future<void> pumpLoad(WidgetTester tester) async {
    await tester.pump(); // 首帧,调度微任务
    await tester.pump(const Duration(milliseconds: 50)); // 异步加载完成,触发 setState
    await tester.pumpAndSettle(); // 让所有定时器与动画完成
  }

  group('KnowledgeManagementPage', () {
    testWidgets('页面渲染:AppBar 标题"知识库管理"', (tester) async {
      setPhoneViewport(tester);
      final service = FakeKnowledgeManagementService(
        initialDocuments: demoDocuments(),
      );
      final container = makeContainer(service: service);

      await tester.pumpWidget(
        wrapWithMaterial(container, const KnowledgeManagementPage()),
      );
      await pumpLoad(tester);

      expect(find.text('知识库管理'), findsOneWidget);
    });

    testWidgets('状态卡片:演示资料声明包含"仿真校园演示资料"', (tester) async {
      setPhoneViewport(tester);
      final service = FakeKnowledgeManagementService(
        initialDocuments: demoDocuments(),
      );
      final container = makeContainer(service: service);

      await tester.pumpWidget(
        wrapWithMaterial(container, const KnowledgeManagementPage()),
      );
      await pumpLoad(tester);

      // _DemoDataNotice 文案(包含长声明与短标签,允许匹配多widget)
      expect(find.textContaining('仿真校园演示资料'), findsWidgets);
    });

    testWidgets('状态卡片:显示文档数、分块数、问答模式', (tester) async {
      setPhoneViewport(tester);
      final service = FakeKnowledgeManagementService(
        initialDocuments: demoDocuments(),
      );
      final container = makeContainer(service: service);

      await tester.pumpWidget(
        wrapWithMaterial(container, const KnowledgeManagementPage()),
      );
      await pumpLoad(tester);

      // 指标标签
      expect(find.text('文档'), findsOneWidget);
      expect(find.text('分块'), findsOneWidget);
      // 2 份文档 → 16 段分块(每份 8 段)
      expect(find.text('2'), findsWidgets);
      expect(find.text('16'), findsWidgets);
      // 问答模式标签与值(短标签和长说明中都含"检索摘要",允许匹配多widget)
      expect(find.text('问答模式'), findsOneWidget);
      expect(find.textContaining('检索摘要'), findsWidgets);
    });

    testWidgets('文档列表:显示文档标题', (tester) async {
      setPhoneViewport(tester);
      final service = FakeKnowledgeManagementService(
        initialDocuments: demoDocuments(),
      );
      final container = makeContainer(service: service);

      await tester.pumpWidget(
        wrapWithMaterial(container, const KnowledgeManagementPage()),
      );
      await pumpLoad(tester);

      expect(find.text('新生入学指南'), findsOneWidget);
      expect(find.text('综合测评实施细则'), findsOneWidget);
    });

    testWidgets('空状态:无文档时显示引导文案', (tester) async {
      setPhoneViewport(tester);
      final service = FakeKnowledgeManagementService(
        initialDocuments: const [],
      );
      final container = makeContainer(service: service);

      await tester.pumpWidget(
        wrapWithMaterial(container, const KnowledgeManagementPage()),
      );
      await pumpLoad(tester);

      expect(find.byType(EmptyStateView), findsOneWidget);
      expect(find.text('知识库为空'), findsOneWidget);
      expect(find.textContaining('请先导入学校官方通知'), findsOneWidget);
    });

    testWidgets('错误状态:服务失败时显示重试按钮', (tester) async {
      setPhoneViewport(tester);
      final service = FakeKnowledgeManagementService(
        initialDocuments: const [],
        shouldFail: true,
        failureCode: 'NETWORK_ERROR',
        failureMessage: '连接后端失败',
      );
      final container = makeContainer(service: service);

      await tester.pumpWidget(
        wrapWithMaterial(container, const KnowledgeManagementPage()),
      );
      await pumpLoad(tester);

      expect(find.byType(ErrorStateView), findsOneWidget);
      expect(find.text('重试'), findsOneWidget);
    });

    testWidgets('上传按钮(FAB)存在', (tester) async {
      setPhoneViewport(tester);
      final service = FakeKnowledgeManagementService(
        initialDocuments: demoDocuments(),
      );
      final container = makeContainer(service: service);

      await tester.pumpWidget(
        wrapWithMaterial(container, const KnowledgeManagementPage()),
      );
      await pumpLoad(tester);

      // "上传文档" 同时出现在 FAB 与 ActionsBar 中
      expect(find.text('上传文档'), findsWidgets);
      expect(find.byType(FloatingActionButton), findsOneWidget);
    });

    testWidgets('重建索引按钮存在', (tester) async {
      setPhoneViewport(tester);
      final service = FakeKnowledgeManagementService(
        initialDocuments: demoDocuments(),
      );
      final container = makeContainer(service: service);

      await tester.pumpWidget(
        wrapWithMaterial(container, const KnowledgeManagementPage()),
      );
      await pumpLoad(tester);

      expect(find.text('重建索引'), findsOneWidget);
    });
  });
}
