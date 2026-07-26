import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:campus_companion/app/app.dart';
import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/storage/data_persistence_service.dart';
import 'package:campus_companion/core/storage/local_storage.dart';
import 'package:campus_companion/core/storage/notice_storage.dart';
import 'package:campus_companion/core/storage/settings_storage.dart';
import 'package:campus_companion/core/storage/study_storage.dart';
import 'package:campus_companion/core/storage/task_storage.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

Future<ProviderContainer> _bootstrapContainer({
  AppSettings? initialSettings,
}) async {
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

  return ProviderContainer(
    overrides: [
      taskRepositoryProvider.overrideWithValue(taskRepo),
      studySessionRepositoryProvider.overrideWithValue(studyRepo),
      dataPersistenceProvider.overrideWithValue(persistenceService),
      if (initialSettings != null)
        appSettingsProvider.overrideWith((ref) {
          final notifier = AppSettingsNotifier();
          notifier.restoreFrom(initialSettings);
          return notifier;
        }),
    ],
  );
}

/// 由于 CampusCompanionApp 中可能存在持续动画(如呼吸点),
/// 不能使用 pumpAndSettle,改用 pump + 固定时长。
Future<void> pumpApp(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 800));
}

void main() {
  group('AppConfig', () {
    test('默认为 development 环境,使用真实后端(参赛版本约束)', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final config = container.read(appConfigProvider);
      expect(config.environment, AppEnvironment.development);
      // 正式参赛版本默认不启用 Mock,确保不引用 Mock 实现
      expect(config.useMockBackend, isFalse);
      expect(config.useMockExpressionRecognition, isFalse);
      expect(config.isMockMode, isFalse);
      expect(config.isRealBackend, isTrue);
    });

    test('appConfigProvider 与 AppSettings 解耦(无 demoMode 字段)', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      // AppSettings 已不再保留 demoMode 字段,
      // AppConfig 始终从 dart-define 读取 useMockBackend,
      // 默认值为 false(正式参赛版本约束)
      final config = container.read(appConfigProvider);
      expect(config.useMockBackend, isFalse);
      expect(config.isRealBackend, isTrue);
    });

    test('production 环境字段语义检查', () {
      const config = AppConfig(
        environment: AppEnvironment.production,
        useMockBackend: false,
        useMockExpressionRecognition: false,
        apiBaseUrl: 'http://test.local',
      );
      expect(config.isMockMode, isFalse);
      expect(config.environment, AppEnvironment.production);
      expect(config.apiBaseUrl, 'http://test.local');
    });
  });

  group('Provider 注入 — taskRepository 与 studySessionRepository', () {
    test('override 的 Mock 仓库被注入到 taskListProvider', () async {
      final repo = MockTaskRepository(
        initial: [
          Task(
            id: 'inject_t1',
            title: '注入任务',
            category: TaskCategory.study,
            priority: TaskPriority.high,
            createdAt: DateTime(2025, 1, 1),
            source: TaskSource.manual,
          ),
        ],
      );
      final container = ProviderContainer(
        overrides: [taskRepositoryProvider.overrideWithValue(repo)],
      );
      addTearDown(container.dispose);

      final tasks = container.read(taskListProvider);
      expect(tasks.any((t) => t.id == 'inject_t1'), isTrue);
    });

    test('override 的 studyRepository 被注入到 studyHistoryProvider', () async {
      final repo = MockStudySessionRepository();
      await repo.start(goalId: 'goal_x');
      await repo.end(selfReportMood: '良好');

      final container = ProviderContainer(
        overrides: [studySessionRepositoryProvider.overrideWithValue(repo)],
      );
      addTearDown(container.dispose);

      final history = await container.read(studyHistoryProvider.future);
      expect(history, isNotEmpty);
    });
  });

  group('AppSettingsNotifier', () {
    test('restoreFrom 后状态切换', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      const initial = AppSettings(
        darkMode: true,
        reduceMotion: true,
        reminderLeadMinutes: 30,
      );
      container.read(appSettingsProvider.notifier).restoreFrom(initial);
      final s = container.read(appSettingsProvider);
      expect(s.darkMode, isTrue);
      expect(s.reduceMotion, isTrue);
      expect(s.reminderLeadMinutes, 30);
    });

    test('resetToDefault 后状态恢复默认', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      container.read(appSettingsProvider.notifier).restoreFrom(
            const AppSettings(
              darkMode: true,
              reduceMotion: true,
            ),
          );
      expect(container.read(appSettingsProvider).darkMode, isTrue);
      container.read(appSettingsProvider.notifier).resetToDefault();
      expect(container.read(appSettingsProvider).darkMode, isFalse);
      expect(container.read(appSettingsProvider).reduceMotion, isFalse);
    });

    test('toggleReminder / setReminderLead', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      container.read(appSettingsProvider.notifier).toggleReminder();
      expect(container.read(appSettingsProvider).reminderEnabled, isFalse);
      container.read(appSettingsProvider.notifier).setReminderLead(45);
      expect(container.read(appSettingsProvider).reminderLeadMinutes, 45);
    });

    test('toggleProactiveSuggestion 切换', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(
        container.read(appSettingsProvider).counselorProactiveSuggestion,
        isTrue,
      );
      container.read(appSettingsProvider.notifier).toggleProactiveSuggestion();
      expect(
        container.read(appSettingsProvider).counselorProactiveSuggestion,
        isFalse,
      );
    });
  });

  group('CampusCompanionApp — 深色模式与浅色模式切换', () {
    testWidgets('浅色模式下使用 ThemeMode.light', (tester) async {
      final container = await _bootstrapContainer(
        initialSettings: const AppSettings(darkMode: false),
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const CampusCompanionApp(),
        ),
      );
      await pumpApp(tester);

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.themeMode, ThemeMode.light);
    });

    testWidgets('深色模式下使用 ThemeMode.dark', (tester) async {
      final container = await _bootstrapContainer(
        initialSettings: const AppSettings(darkMode: true),
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const CampusCompanionApp(),
        ),
      );
      await pumpApp(tester);

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.themeMode, ThemeMode.dark);
    });

    testWidgets('切换 darkMode 后 MaterialApp themeMode 跟随更新', (tester) async {
      final container = await _bootstrapContainer(
        initialSettings: const AppSettings(darkMode: false),
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const CampusCompanionApp(),
        ),
      );
      await pumpApp(tester);

      // 切换到深色
      container.read(appSettingsProvider.notifier).toggleDarkMode();
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.themeMode, ThemeMode.dark);
    });

    testWidgets('reduceMotion 同步到 reduceMotionProvider', (tester) async {
      final container = await _bootstrapContainer(
        initialSettings: const AppSettings(reduceMotion: true),
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const CampusCompanionApp(),
        ),
      );
      await pumpApp(tester);
      // 触发 post frame callback
      await tester.pump();

      expect(container.read(reduceMotionProvider), isTrue);
    });
  });

  group('CampusCompanionApp — 自动持久化监听', () {
    testWidgets('任务列表变化触发 saveTasks', (tester) async {
      final container = await _bootstrapContainer();
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const CampusCompanionApp(),
        ),
      );
      await pumpApp(tester);

      // 通过 Notifier 创建任务 — 应触发自动持久化
      // 使用 runAsync 让真实 async 操作完成(MockTaskRepository 内部有 Future.delayed)
      await tester.runAsync(() async {
        await container.read(taskListProvider.notifier).createTask(
              Task(
                id: 'auto_save_t1',
                title: '自动持久化任务',
                category: TaskCategory.other,
                priority: TaskPriority.low,
                createdAt: DateTime.now(),
                source: TaskSource.manual,
              ),
            );
        // 等待 stream emit + listen + saveTasks 完成
        await Future.delayed(const Duration(milliseconds: 300));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      final localStorage = SharedPreferencesLocalStorage.instance;
      final loaded = await TaskStorage(localStorage).load();
      expect(loaded.any((t) => t.id == 'auto_save_t1'), isTrue);
    });

    testWidgets('通知列表变化触发 saveNotices', (tester) async {
      final container = await _bootstrapContainer();
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const CampusCompanionApp(),
        ),
      );
      await pumpApp(tester);

      final firstNotice = container.read(campusNoticesProvider).first;
      await tester.runAsync(() async {
        container.read(campusNoticesProvider.notifier).markRead(firstNotice.id);
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      final localStorage = SharedPreferencesLocalStorage.instance;
      final loaded = await NoticeStorage(localStorage).load();
      expect(loaded.any((n) => n.id == firstNotice.id && n.read), isTrue);
    });

    testWidgets('设置变化触发 saveSettings', (tester) async {
      final container = await _bootstrapContainer();
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const CampusCompanionApp(),
        ),
      );
      await pumpApp(tester);

      await tester.runAsync(() async {
        container.read(appSettingsProvider.notifier).toggleDarkMode();
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      final localStorage = SharedPreferencesLocalStorage.instance;
      final saved = await SettingsStorage(localStorage).load();
      expect(saved, isNotNull);
      expect(saved!.darkMode, isTrue);
    });
  });
}
