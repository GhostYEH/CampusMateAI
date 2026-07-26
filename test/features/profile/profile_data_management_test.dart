import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/storage/data_persistence_service.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/core/storage/local_storage.dart';
import 'package:campus_companion/core/storage/notice_storage.dart';
import 'package:campus_companion/core/storage/settings_storage.dart';
import 'package:campus_companion/core/storage/study_storage.dart';
import 'package:campus_companion/core/storage/task_storage.dart';
import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/features/profile/presentation/profile_page.dart';
import 'package:campus_companion/mock/mock_services/mock_knowledge_management_service.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

void main() {
  late SharedPreferencesLocalStorage localStorage;
  late MockTaskRepository taskRepo;
  late MockStudySessionRepository studyRepo;
  late DataPersistenceService dataPersistence;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    SharedPreferencesLocalStorage.setTestInstance(null);
    localStorage = await SharedPreferencesLocalStorage.initialize();
    taskRepo = MockTaskRepository(initial: const []);
    studyRepo = MockStudySessionRepository();
    dataPersistence = DataPersistenceService(
      settingsStorage: SettingsStorage(localStorage),
      taskStorage: TaskStorage(localStorage),
      studyStorage: StudyStorage(localStorage),
      noticeStorage: NoticeStorage(localStorage),
      taskRepository: taskRepo,
      studyRepository: studyRepo,
    );
  });

  /// 构造可覆盖多个 Provider 的 ProviderContainer。
  ProviderContainer makeContainer({
    MockTaskRepository? customTaskRepo,
    DataPersistenceService? customDataPersistence,
  }) {
    final repo = customTaskRepo ?? taskRepo;
    final dp = customDataPersistence ?? dataPersistence;
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
        taskRepositoryProvider.overrideWithValue(repo),
        studySessionRepositoryProvider.overrideWithValue(studyRepo),
        knowledgeManagementProvider.overrideWithValue(
          FakeKnowledgeManagementService(initialDocuments: const []),
        ),
        dataPersistenceProvider.overrideWithValue(dp),
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
  Future<void> pumpIdle(WidgetTester tester) async {
    await tester.pump(); // 首帧,调度微任务
    await tester.pump(const Duration(milliseconds: 50)); // 异步加载完成,触发 setState
    await tester.pumpAndSettle(); // 让所有定时器与动画完成
  }

  group('ProfilePage - 数据管理分区', () {
    testWidgets('渲染"本地数据管理"分区标题', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();

      await tester.pumpWidget(
        wrapWithMaterial(container, const ProfilePage()),
      );
      await pumpIdle(tester);

      // 参赛版本约束:分区标题从"数据管理"改为"本地数据管理",
      // 强调仅影响本地数据,不影响后端
      expect(find.text('本地数据管理'), findsOneWidget);
      expect(find.text('数据管理'), findsNothing);
    });

    testWidgets('显示数据管理操作项(无演示数据入口)', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();

      await tester.pumpWidget(
        wrapWithMaterial(container, const ProfilePage()),
      );
      await pumpIdle(tester);

      // 参赛版本约束:不暴露"恢复仿真演示资料"、"重置 Mock 演示数据"等入口
      expect(find.text('清除聊天记录'), findsOneWidget);
      expect(find.text('清除本地待办'), findsOneWidget);
      expect(find.text('删除用户导入的知识库文档'), findsOneWidget);
      expect(find.text('清除所有本地数据'), findsOneWidget);

      // 禁止出现的演示模式入口
      expect(find.text('恢复仿真演示资料'), findsNothing);
      expect(find.text('重置 Mock 演示数据'), findsNothing);
      expect(find.textContaining('演示'), findsNothing);
      expect(find.textContaining('Mock'), findsNothing);
    });

    testWidgets('点击"清除本地待办"显示确认对话框', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();

      await tester.pumpWidget(
        wrapWithMaterial(container, const ProfilePage()),
      );
      await pumpIdle(tester);

      // 滚动到"清除本地待办"确保可见
      await tester.ensureVisible(find.text('清除本地待办'));
      await tester.pumpAndSettle();

      // 点击
      await tester.tap(find.text('清除本地待办'));
      await tester.pumpAndSettle();

      // 对话框标题(列表项 + 对话框标题 = 2)
      expect(find.text('清除本地待办'), findsNWidgets(2));
      expect(find.textContaining('将删除本地所有待办任务'), findsOneWidget);
      expect(find.text('取消'), findsOneWidget);
      expect(find.text('清除'), findsOneWidget);
    });

    testWidgets('确认对话框后调用 taskRepository.clearAll()', (tester) async {
      setPhoneViewport(tester);

      // 使用带初始任务的仓库,验证 clearAll 生效
      final repoWithTasks = MockTaskRepository(
        initial: [
          Task(
            id: 'test_task_1',
            title: '测试任务',
            category: TaskCategory.study,
            priority: TaskPriority.high,
            createdAt: DateTime.now(),
            source: TaskSource.manual,
          ),
        ],
      );
      // 前置断言:仓库非空
      expect(repoWithTasks.tasks, isNotEmpty);

      final dp = DataPersistenceService(
        settingsStorage: SettingsStorage(localStorage),
        taskStorage: TaskStorage(localStorage),
        studyStorage: StudyStorage(localStorage),
        noticeStorage: NoticeStorage(localStorage),
        taskRepository: repoWithTasks,
        studyRepository: studyRepo,
      );

      final container = makeContainer(
        customTaskRepo: repoWithTasks,
        customDataPersistence: dp,
      );

      await tester.pumpWidget(
        wrapWithMaterial(container, const ProfilePage()),
      );
      await pumpIdle(tester);

      // 滚动并点击"清除本地待办"
      await tester.ensureVisible(find.text('清除本地待办'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('清除本地待办'));
      await tester.pumpAndSettle();

      // 点击对话框中的"清除"按钮
      await tester.tap(find.widgetWithText(FilledButton, '清除'));
      await tester.pumpAndSettle();

      // 验证 clearAll() 已调用 — 仓库任务已清空
      expect(repoWithTasks.tasks, isEmpty);
    });

    testWidgets('点击"清除聊天记录"显示确认对话框', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();

      await tester.pumpWidget(
        wrapWithMaterial(container, const ProfilePage()),
      );
      await pumpIdle(tester);

      // 滚动到"清除聊天记录"确保可见
      await tester.ensureVisible(find.text('清除聊天记录'));
      await tester.pumpAndSettle();

      // 点击
      await tester.tap(find.text('清除聊天记录'));
      await tester.pumpAndSettle();

      // 对话框标题(列表项 + 对话框标题 = 2)
      expect(find.text('清除聊天记录'), findsNWidgets(2));
      expect(find.textContaining('将删除 AI 导员的所有历史对话'), findsOneWidget);
      expect(find.text('取消'), findsOneWidget);
      expect(find.text('清除'), findsOneWidget);
    });
  });
}
