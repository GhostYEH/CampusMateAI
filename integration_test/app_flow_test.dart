// =============================================================================
// app_flow_test.dart — 端到端集成测试(Mock 模式)
//
// This integration test runs in Mock mode. It does NOT rely on dart-define;
// instead it injects Mock services explicitly via ProviderScope overrides.
//
// To run against a real backend:
//   1) Start FastAPI server (e.g. uvicorn main:app --host 127.0.0.1 --port 8000)
//   2) Run:
//      flutter test integration_test/app_flow_test.dart \
//        --dart-define=USE_MOCK_BACKEND=false \
//        --dart-define=API_BASE_URL=http://127.0.0.1:8000
//
// 注意: 本测试使用 Mock 服务实现,模拟 ~2s 提取延迟与流式回复延迟。
// 因 CampusCompanionApp 内部存在持续动画(呼吸点等),不使用 pumpAndSettle,
// 改用 pump(Duration) 推进时间。同时开启"减少动态效果"以避免动画期间
// 按钮被 IgnorePointer 替换而无法点击。
// =============================================================================

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:campus_companion/app/app.dart';
import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/app/router/app_router.dart';
import 'package:campus_companion/core/storage/data_persistence_service.dart';
import 'package:campus_companion/core/storage/local_storage.dart';
import 'package:campus_companion/core/storage/notice_storage.dart';
import 'package:campus_companion/core/storage/settings_storage.dart';
import 'package:campus_companion/core/storage/study_storage.dart';
import 'package:campus_companion/core/storage/task_storage.dart';
import 'package:campus_companion/data/models/settings.dart';
import 'package:campus_companion/features/counselor/presentation/counselor_page.dart';
import 'package:campus_companion/features/home/presentation/home_page.dart';
import 'package:campus_companion/features/knowledge/presentation/widgets/knowledge_status_card.dart';
import 'package:campus_companion/features/notifications/presentation/notification_extract_page.dart';
import 'package:campus_companion/mock/mock_services/fake_notification_reminder_service.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  /// 共享的 ProviderContainer — 每个 testWidgets 重建。
  late ProviderContainer container;

  /// 构造 Mock 模式的应用容器并启动。
  ///
  /// 显式注入 Mock 服务实现,不依赖 dart-define:
  /// - [MockTaskRepository] / [MockStudySessionRepository]: 内存数据
  /// - [FakeNotificationReminderService]: 避免 flutter_local_notifications
  ///   插件在测试环境中初始化失败
  /// - reduceMotion=true: 关闭 StaggeredEnter 入场动画,确保按钮可点击
  Future<void> bootstrapApp(WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    SharedPreferencesLocalStorage.setTestInstance(null);
    final localStorage = await SharedPreferencesLocalStorage.initialize();

    final taskRepo = MockTaskRepository(initial: const []);
    final studyRepo = MockStudySessionRepository();

    final persistenceService = DataPersistenceService(
      settingsStorage: SettingsStorage(localStorage),
      taskStorage: TaskStorage(localStorage),
      studyStorage: StudyStorage(localStorage),
      noticeStorage: NoticeStorage(localStorage),
      taskRepository: taskRepo,
      studyRepository: studyRepo,
    );

    container = ProviderContainer(
      overrides: [
        taskRepositoryProvider.overrideWithValue(taskRepo),
        studySessionRepositoryProvider.overrideWithValue(studyRepo),
        dataPersistenceProvider.overrideWithValue(persistenceService),
        notificationReminderProvider.overrideWithValue(
          FakeNotificationReminderService(),
        ),
        // 开启减少动态效果,关闭入场动画,确保按钮在动画期间也可点击
        appSettingsProvider.overrideWith((ref) {
          final notifier = AppSettingsNotifier();
          notifier.restoreFrom(const AppSettings(reduceMotion: true));
          return notifier;
        }),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const CampusCompanionApp(),
      ),
    );
    // 推进足够时间让首帧 + 入场渲染完成
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 800));
  }

  /// 尽力截图 — 在 Android 模拟器上需先调用 convertFlutterSurfaceToImage,
  /// 但该调用在某些环境下会卡住,因此用 try/catch 包裹,失败时不影响测试结果。
  Future<void> safeScreenshot(String name) async {
    try {
      await IntegrationTestWidgetsFlutterBinding.instance.takeScreenshot(name);
    } catch (_) {
      // 截图失败不影响测试断言
    }
  }

  /// 设置手机视口,避免默认 800x600 下部分组件超出可视区域。
  void setPhoneViewport(WidgetTester tester) {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  /// 通过 router 导航到指定路由,并等待页面渲染。
  Future<void> navigateTo(WidgetTester tester, String location) async {
    container.read(routerProvider).go(location);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
  }

  testWidgets(
    'App starts and shows home page',
    (tester) async {
      setPhoneViewport(tester);
      await bootstrapApp(tester);

      // 首页 widget 已渲染
      expect(find.byType(HomePage), findsOneWidget);

      // 底部导航栏存在且选中"首页"
      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.text('首页'), findsWidgets);

      // 首页快捷入口标题
      expect(find.text('现在想做什么？'), findsOneWidget);
      // 快捷入口包含"整理通知"与"问AI导员"
      expect(find.text('整理通知'), findsOneWidget);
      expect(find.text('问AI导员'), findsOneWidget);

      // 记录截图供集成测试报告使用
      await safeScreenshot('home_page');
    },
  );

  testWidgets(
    'Knowledge management page shows status',
    (tester) async {
      setPhoneViewport(tester);
      await bootstrapApp(tester);

      await navigateTo(tester, '/knowledge');

      // 等待 Mock 知识库管理服务加载完成(getStatus ~120ms + listDocuments)
      await tester.pump(const Duration(milliseconds: 600));

      // 知识库管理页 AppBar 标题
      expect(find.text('知识库管理'), findsOneWidget);

      // 状态卡片渲染
      expect(find.byType(KnowledgeStatusCard), findsOneWidget);
      // 知识库类型名称由后端返回的 status.knowledgeBaseType.displayName 决定
      // (参赛版本约束:不再有"演示模式知识库"字样)
      expect(find.text('演示模式知识库'), findsNothing);

      // 文档列表区域标题(演示资料已内置)
      expect(find.textContaining('已导入文档'), findsOneWidget);

      await safeScreenshot('knowledge_management');
    },
  );

  testWidgets(
    'Notification extraction flow works',
    (tester) async {
      setPhoneViewport(tester);
      await bootstrapApp(tester);

      await navigateTo(tester, '/notifications/extract');

      // 整理页 AppBar 标题
      expect(find.text('智能整理通知'), findsOneWidget);
      expect(find.byType(NotificationExtractPage), findsOneWidget);

      // 输入通知原文(主输入框为页面第一个 TextFormField)
      final mainInput = find.byType(TextFormField).first;
      expect(mainInput, findsOneWidget);
      await tester.enterText(
        mainInput,
        '请2024级学生于10月20日前填写实践申请表,'
        '并将申请表和证明材料提交至学院办公室。',
      );
      await tester.pump();

      // 点击"智能整理"按钮(提取前页面仅 1 个 FilledButton)
      final extractButton = find.byType(FilledButton);
      expect(extractButton, findsOneWidget);
      await tester.tap(extractButton);
      await tester.pump();

      // 等待 Mock 多任务提取完成(extractMulti: 5 步 * 300ms ≈ 1.5s)
      // 加上分步动画与单任务 ruleExtract,推进 ~2.5s
      await tester.pump(const Duration(milliseconds: 1000));
      await tester.pump(const Duration(milliseconds: 1000));
      await tester.pump(const Duration(milliseconds: 500));

      // 结果表单出现:任务信息 / 办理方式 / 所需材料 / 原文来源 卡片标题
      expect(find.text('任务信息'), findsOneWidget);
      expect(find.text('办理方式'), findsOneWidget);
      expect(find.text('所需材料'), findsOneWidget);
      expect(find.text('原文来源'), findsOneWidget);

      // 任务名称已被自动填入(通知含"实践申请",taskName = "提交实践申请")
      expect(find.textContaining('提交实践申请'), findsWidgets);

      // 保存按钮出现
      expect(find.text('保存为待办'), findsOneWidget);

      await safeScreenshot('notification_extraction');
    },
  );

  testWidgets(
    'AI counselor responds to questions',
    (tester) async {
      setPhoneViewport(tester);
      await bootstrapApp(tester);

      await navigateTo(tester, '/counselor');

      // AI 导员页 AppBar 标题
      expect(find.byType(CounselorPage), findsOneWidget);
      expect(find.text('AI 导员'), findsWidgets);

      // 初始问候消息已存在(ChatMessagesNotifier._initialGreeting)
      expect(find.textContaining('模拟模式'), findsWidgets);

      // 通过 hint 定位聊天输入框
      final inputFinder = find.ancestor(
        of: find.text('问问 AI 导员...'),
        matching: find.byType(TextField),
      );
      expect(inputFinder, findsOneWidget);

      await tester.enterText(inputFinder, '综合测评怎么准备?');
      await tester.pump();

      // 点击"发送"按钮
      final sendButton = find.ancestor(
        of: find.text('发送'),
        matching: find.byType(FilledButton),
      );
      expect(sendButton, findsOneWidget);
      await tester.tap(sendButton);
      await tester.pump();

      // 等待 Mock 导员回复:
      //   420ms(onTyping) + 180ms(kb search) + 220ms + 流式输出(~22ms/字,约 120 字 ≈ 2.6s)
      // 总计约 3.5s,推进 5s 确保完成
      await tester.pump(const Duration(milliseconds: 2000));
      await tester.pump(const Duration(milliseconds: 2000));
      await tester.pump(const Duration(milliseconds: 1000));

      // 用户消息出现
      expect(find.text('综合测评怎么准备?'), findsOneWidget);

      // AI 回复出现:综合测评回复包含"综合测评由学业成绩、思想品德"
      // 注意:回复正文与引用卡片摘要中均可能出现该文本,故使用 findsWidgets。
      expect(find.textContaining('综合测评由学业成绩'), findsWidgets);

      // 回复包含模拟资料来源说明
      expect(find.textContaining('模拟资料来源'), findsWidgets);

      await safeScreenshot('counselor_response');
    },
  );
}
