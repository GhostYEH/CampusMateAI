import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/app.dart';
import 'app/providers/app_providers.dart';
import 'core/storage/data_persistence_service.dart';
import 'core/storage/local_storage.dart';
import 'core/storage/notice_storage.dart';
import 'core/storage/settings_storage.dart';
import 'core/storage/study_storage.dart';
import 'core/storage/task_storage.dart';
import 'data/models/settings.dart';
import 'mock/mock_services/mock_services.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 初始化本地存储 (SharedPreferences)
  await SharedPreferencesLocalStorage.initialize();
  final localStorage = SharedPreferencesLocalStorage.instance;

  // 构造仓储实例 (Mock,单例,供 Provider 与 PersistenceService 共享)
  final taskRepository = MockTaskRepository();
  final studyRepository = MockStudySessionRepository();

  // 构造持久化服务
  final persistenceService = DataPersistenceService(
    settingsStorage: SettingsStorage(localStorage),
    taskStorage: TaskStorage(localStorage),
    studyStorage: StudyStorage(localStorage),
    noticeStorage: NoticeStorage(localStorage),
    taskRepository: taskRepository,
    studyRepository: studyRepository,
  );

  // 启动时加载持久化数据 — 失败时不阻断启动,使用默认设置
  AppSettings loadedSettings;
  try {
    loadedSettings = await persistenceService.loadAll();
  } catch (_) {
    loadedSettings = const AppSettings();
  }

  runApp(
    ProviderScope(
      overrides: [
        taskRepositoryProvider.overrideWithValue(taskRepository),
        studySessionRepositoryProvider.overrideWithValue(studyRepository),
        dataPersistenceProvider.overrideWithValue(persistenceService),
        // 用加载的设置覆盖默认值,触发 AppSettingsNotifier 同步
        appSettingsProvider.overrideWith((ref) {
          final notifier = AppSettingsNotifier();
          notifier.restoreFrom(loadedSettings);
          return notifier;
        }),
      ],
      child: const CampusCompanionApp(),
    ),
  );
}
