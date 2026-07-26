import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:campus_companion/core/storage/local_storage.dart';
import 'package:campus_companion/core/storage/notice_storage.dart';
import 'package:campus_companion/core/storage/settings_storage.dart';
import 'package:campus_companion/core/storage/study_storage.dart';
import 'package:campus_companion/core/storage/task_storage.dart';
import 'package:campus_companion/data/models/models.dart';

void main() {
  late SharedPreferencesLocalStorage localStorage;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    // 重置单例以便重新初始化
    SharedPreferencesLocalStorage.setTestInstance(null);
    localStorage = await SharedPreferencesLocalStorage.initialize();
  });

  group('SettingsStorage', () {
    test('load 无数据返回 null', () async {
      final storage = SettingsStorage(localStorage);
      expect(await storage.load(), isNull);
    });

    test('save / load 往返一致', () async {
      final storage = SettingsStorage(localStorage);
      const settings = AppSettings(
        darkMode: true,
        reduceMotion: true,
        reminderLeadMinutes: 30,
      );
      await storage.save(settings);

      final loaded = await storage.load();
      expect(loaded, isNotNull);
      expect(loaded!.darkMode, isTrue);
      expect(loaded.reduceMotion, isTrue);
      expect(loaded.reminderLeadMinutes, 30);
    });

    test('clear 清空数据', () async {
      final storage = SettingsStorage(localStorage);
      await storage.save(const AppSettings(darkMode: true));
      expect(await storage.load(), isNotNull);

      await storage.clear();
      expect(await storage.load(), isNull);
    });

    test('load 损坏 JSON 返回 null', () async {
      await localStorage.setString('app_settings', '{invalid json');
      final storage = SettingsStorage(localStorage);
      expect(await storage.load(), isNull);
    });
  });

  group('TaskStorage', () {
    test('load 空数据返回空列表', () async {
      final storage = TaskStorage(localStorage);
      expect(await storage.load(), isEmpty);
    });

    test('saveAll / load 往返一致', () async {
      final storage = TaskStorage(localStorage);
      final tasks = [
        Task(
          id: 't1',
          title: '任务1',
          category: TaskCategory.study,
          priority: TaskPriority.high,
          createdAt: DateTime(2025, 10, 1),
          source: TaskSource.manual,
          deadline: DateTime(2025, 10, 10),
          completed: true,
          completedAt: DateTime(2025, 10, 2),
          materials: const [
            TaskMaterial(id: 'm1', name: '材料1', done: true),
          ],
        ),
        Task(
          id: 't2',
          title: '任务2',
          category: TaskCategory.activity,
          priority: TaskPriority.medium,
          createdAt: DateTime(2025, 10, 3),
          source: TaskSource.noticeExtraction,
          deleted: true,
        ),
      ];
      await storage.saveAll(tasks);
      final loaded = await storage.load();

      expect(loaded.length, 2);
      expect(loaded[0].id, 't1');
      expect(loaded[0].title, '任务1');
      expect(loaded[0].completed, isTrue);
      expect(loaded[0].materials.first.name, '材料1');
      expect(loaded[1].id, 't2');
      expect(loaded[1].deleted, isTrue);
      expect(loaded[1].source, TaskSource.noticeExtraction);
    });

    test('clear 清空数据', () async {
      final storage = TaskStorage(localStorage);
      await storage.saveAll([
        Task(
          id: 't1',
          title: '任务1',
          category: TaskCategory.other,
          priority: TaskPriority.low,
          createdAt: DateTime.now(),
          source: TaskSource.manual,
        ),
      ]);
      expect((await storage.load()).length, 1);

      await storage.clear();
      expect(await storage.load(), isEmpty);
    });

    test('load 损坏 JSON 返回空列表', () async {
      await localStorage.setString('app_tasks', '[invalid json');
      final storage = TaskStorage(localStorage);
      expect(await storage.load(), isEmpty);
    });
  });

  group('StudyStorage', () {
    test('loadHistory 空数据返回空列表', () async {
      final storage = StudyStorage(localStorage);
      expect(await storage.loadHistory(), isEmpty);
    });

    test('saveHistory / loadHistory 往返一致', () async {
      final storage = StudyStorage(localStorage);
      final history = [
        StudySession(
          id: 's1',
          startedAt: DateTime(2025, 10, 1, 9, 0),
          endedAt: DateTime(2025, 10, 1, 10, 0),
          durationSeconds: 3600,
          state: StudyState.completed,
          focusRatio: 0.85,
          selfReportMood: '专注',
        ),
        StudySession(
          id: 's2',
          startedAt: DateTime(2025, 10, 2, 14, 0),
          durationSeconds: 1800,
          state: StudyState.paused,
          goalId: 'goal_a',
          taskId: 't1',
        ),
      ];
      await storage.saveHistory(history);
      final loaded = await storage.loadHistory();

      expect(loaded.length, 2);
      expect(loaded[0].id, 's1');
      expect(loaded[0].durationSeconds, 3600);
      expect(loaded[0].state, StudyState.completed);
      expect(loaded[0].focusRatio, 0.85);
      expect(loaded[0].selfReportMood, '专注');
      expect(loaded[1].id, 's2');
      expect(loaded[1].goalId, 'goal_a');
      expect(loaded[1].taskId, 't1');
    });

    test('clear 清空数据', () async {
      final storage = StudyStorage(localStorage);
      await storage.saveHistory([
        StudySession(
          id: 's1',
          startedAt: DateTime.now(),
          durationSeconds: 60,
          state: StudyState.completed,
        ),
      ]);
      expect((await storage.loadHistory()).length, 1);

      await storage.clear();
      expect(await storage.loadHistory(), isEmpty);
    });

    test('loadHistory 损坏 JSON 返回空列表', () async {
      await localStorage.setString('app_study_history', '{invalid');
      final storage = StudyStorage(localStorage);
      expect(await storage.loadHistory(), isEmpty);
    });
  });

  group('NoticeStorage', () {
    test('load 空数据返回空列表', () async {
      final storage = NoticeStorage(localStorage);
      expect(await storage.load(), isEmpty);
    });

    test('saveAll / load 往返一致', () async {
      final storage = NoticeStorage(localStorage);
      final notices = [
        CampusNotice(
          id: 'n1',
          title: '通知1',
          source: '教务处',
          publishedAt: DateTime(2025, 10, 1),
          content: '正文',
          importance: NoticeImportance.urgent,
          read: true,
          tags: const ['实践', '2024级'],
        ),
        CampusNotice(
          id: 'n2',
          title: '通知2',
          source: '学生处',
          publishedAt: DateTime(2025, 10, 2),
          content: '内容',
          importance: NoticeImportance.normal,
        ),
      ];
      await storage.saveAll(notices);
      final loaded = await storage.load();

      expect(loaded.length, 2);
      expect(loaded[0].id, 'n1');
      expect(loaded[0].importance, NoticeImportance.urgent);
      expect(loaded[0].read, isTrue);
      expect(loaded[0].tags, ['实践', '2024级']);
      expect(loaded[1].id, 'n2');
      expect(loaded[1].read, isFalse);
    });

    test('clear 清空数据', () async {
      final storage = NoticeStorage(localStorage);
      await storage.saveAll([
        CampusNotice(
          id: 'n1',
          title: '通知1',
          source: '教务处',
          publishedAt: DateTime.now(),
          content: '',
        ),
      ]);
      expect((await storage.load()).length, 1);

      await storage.clear();
      expect(await storage.load(), isEmpty);
    });

    test('load 损坏 JSON 返回空列表', () async {
      await localStorage.setString('app_notices', '{invalid');
      final storage = NoticeStorage(localStorage);
      expect(await storage.load(), isEmpty);
    });
  });
}
