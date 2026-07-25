import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:campus_companion/core/storage/data_persistence_service.dart';
import 'package:campus_companion/core/storage/local_storage.dart';
import 'package:campus_companion/core/storage/notice_storage.dart';
import 'package:campus_companion/core/storage/settings_storage.dart';
import 'package:campus_companion/core/storage/study_storage.dart';
import 'package:campus_companion/core/storage/task_storage.dart';
import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

void main() {
  late SharedPreferencesLocalStorage localStorage;
  late MockTaskRepository taskRepo;
  late MockStudySessionRepository studyRepo;
  late DataPersistenceService service;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    SharedPreferencesLocalStorage.setTestInstance(null);
    localStorage = await SharedPreferencesLocalStorage.initialize();
    taskRepo = MockTaskRepository(initial: const []);
    studyRepo = MockStudySessionRepository();
    service = DataPersistenceService(
      settingsStorage: SettingsStorage(localStorage),
      taskStorage: TaskStorage(localStorage),
      studyStorage: StudyStorage(localStorage),
      noticeStorage: NoticeStorage(localStorage),
      taskRepository: taskRepo,
      studyRepository: studyRepo,
    );
  });

  group('DataPersistenceService.loadAll', () {
    test('无数据时返回默认设置', () async {
      final settings = await service.loadAll();
      expect(settings, const AppSettings());
      expect(taskRepo.snapshot, isEmpty);
      expect(studyRepo.historySnapshot, isNotEmpty); // MockData 默认历史
    });

    test('有持久化任务时恢复到仓库', () async {
      final tasks = [
        Task(
          id: 'p_t1',
          title: '持久化任务',
          category: TaskCategory.study,
          priority: TaskPriority.high,
          createdAt: DateTime(2025, 10, 1),
          source: TaskSource.manual,
        ),
      ];
      await TaskStorage(localStorage).saveAll(tasks);

      await service.loadAll();
      expect(taskRepo.snapshot.any((t) => t.id == 'p_t1'), isTrue);
    });

    test('有持久化设置时返回已保存设置', () async {
      const saved = AppSettings(
        darkMode: true,
        reduceMotion: true,
        demoMode: true,
        reminderLeadMinutes: 45,
      );
      await SettingsStorage(localStorage).save(saved);

      final loaded = await service.loadAll();
      expect(loaded.darkMode, isTrue);
      expect(loaded.reduceMotion, isTrue);
      expect(loaded.demoMode, isTrue);
      expect(loaded.reminderLeadMinutes, 45);
    });

    test('有持久化学习历史时恢复', () async {
      final history = [
        StudySession(
          id: 'p_s1',
          startedAt: DateTime(2025, 10, 1, 9, 0),
          endedAt: DateTime(2025, 10, 1, 10, 0),
          durationSeconds: 3600,
          state: StudyState.completed,
          focusRatio: 0.9,
        ),
      ];
      await StudyStorage(localStorage).saveHistory(history);

      await service.loadAll();
      expect(studyRepo.historySnapshot.any((s) => s.id == 'p_s1'), isTrue);
    });
  });

  group('DataPersistenceService.saveTasks', () {
    test('保存后写入 TaskStorage', () async {
      await taskRepo.createTask(
        Task(
          id: 'save_t1',
          title: '保存任务',
          category: TaskCategory.other,
          priority: TaskPriority.low,
          createdAt: DateTime.now(),
          source: TaskSource.manual,
        ),
      );

      await service.saveTasks();
      final loaded = await TaskStorage(localStorage).load();
      expect(loaded.any((t) => t.id == 'save_t1'), isTrue);
    });
  });

  group('DataPersistenceService.saveSettings', () {
    test('保存设置后可被 SettingsStorage 读回', () async {
      const settings = AppSettings(
        darkMode: true,
        reduceMotion: true,
        reminderLeadMinutes: 60,
      );
      await service.saveSettings(settings);

      final loaded = await SettingsStorage(localStorage).load();
      expect(loaded, isNotNull);
      expect(loaded!.darkMode, isTrue);
      expect(loaded.reminderLeadMinutes, 60);
    });
  });

  group('DataPersistenceService.saveStudyHistory', () {
    test('保存学习历史后可被 StudyStorage 读回', () async {
      await studyRepo.start(goalId: 'goal_a');
      await studyRepo.end(selfReportMood: '专注');

      await service.saveStudyHistory();
      final loaded = await StudyStorage(localStorage).loadHistory();
      expect(loaded, isNotEmpty);
    });
  });

  group('DataPersistenceService.saveNotices', () {
    test('保存通知列表后可被 NoticeStorage 读回', () async {
      final notices = [
        CampusNotice(
          id: 'pn1',
          title: '持久化通知',
          source: '教务处',
          publishedAt: DateTime(2025, 10, 1),
          content: '正文',
          read: true,
        ),
      ];
      await service.saveNotices(notices);

      final loaded = await NoticeStorage(localStorage).load();
      expect(loaded.any((n) => n.id == 'pn1'), isTrue);
      expect(loaded.first.read, isTrue);
    });
  });

  group('DataPersistenceService.clearAllData', () {
    test('清除所有存储与仓库数据', () async {
      // 先写入数据
      await taskRepo.createTask(
        Task(
          id: 'clear_t1',
          title: '待清除任务',
          category: TaskCategory.other,
          priority: TaskPriority.low,
          createdAt: DateTime.now(),
          source: TaskSource.manual,
        ),
      );
      await service.saveTasks();
      await service.saveSettings(
        const AppSettings(darkMode: true, reminderLeadMinutes: 99),
      );

      // 清除
      await service.clearAllData();

      expect(await TaskStorage(localStorage).load(), isEmpty);
      expect(await StudyStorage(localStorage).loadHistory(), isEmpty);
      expect(await NoticeStorage(localStorage).load(), isEmpty);
      expect(await SettingsStorage(localStorage).load(), isNull);
      expect(taskRepo.snapshot, isEmpty);
      expect(studyRepo.historySnapshot, isEmpty);
    });
  });

  group('DataPersistenceService.restoreDemoData', () {
    test('重置为 MockData 演示数据并写入持久化层', () async {
      // 先清空
      await service.clearAllData();
      expect(taskRepo.snapshot, isEmpty);

      // 恢复演示
      await service.restoreDemoData();

      // 内存恢复
      expect(taskRepo.snapshot, isNotEmpty);
      expect(studyRepo.historySnapshot, isNotEmpty);

      // 持久化层也写入
      final tasksOnDisk = await TaskStorage(localStorage).load();
      final historyOnDisk = await StudyStorage(localStorage).loadHistory();
      expect(tasksOnDisk, isNotEmpty);
      expect(historyOnDisk, isNotEmpty);
    });
  });

  group('DataPersistenceService — 与 Mock 仓库协同', () {
    test('保存 → 清除 → 恢复演示 完整流程', () async {
      // 1. 创建用户任务
      await taskRepo.createTask(
        Task(
          id: 'flow_t1',
          title: '用户任务',
          category: TaskCategory.other,
          priority: TaskPriority.low,
          createdAt: DateTime.now(),
          source: TaskSource.manual,
        ),
      );
      await service.saveTasks();
      expect((await TaskStorage(localStorage).load()).length, greaterThan(0));

      // 2. 清除
      await service.clearAllData();
      expect((await TaskStorage(localStorage).load()), isEmpty);

      // 3. 恢复演示
      await service.restoreDemoData();
      final tasks = await TaskStorage(localStorage).load();
      expect(tasks, isNotEmpty);
      // 演示数据中不应包含已清除的用户任务
      expect(tasks.any((t) => t.id == 'flow_t1'), isFalse);
    });
  });
}
