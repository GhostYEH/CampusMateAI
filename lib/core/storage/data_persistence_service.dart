import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/notice.dart';
import '../../data/models/settings.dart';
import '../../data/services/service_interfaces.dart';
import 'notice_storage.dart';
import 'settings_storage.dart';
import 'study_storage.dart';
import 'task_storage.dart';

/// 数据持久化服务 — 统一管理应用启动时的加载与运行时的保存。
///
/// 流程(AGENTS.md §4):
/// 1. 应用启动时调用 [loadAll] 从 SharedPreferences 读取数据。
/// 2. 内存仓库在启动时从持久化数据恢复。
/// 3. UI 修改后通过 [saveTasks]/[saveSettings] 等写回。
/// 4. "清除本地数据"通过 [clearAllData] 清空并弹出确认。
///
/// 正式参赛版本约束(AGENTS.md §2):
/// - [restoreDemoData] 仅供开发与测试使用,不在普通用户界面暴露。
/// - Release 构建不引用任何 Mock 实现,所有数据来自真实后端。
class DataPersistenceService {
  DataPersistenceService({
    required this.settingsStorage,
    required this.taskStorage,
    required this.studyStorage,
    required this.noticeStorage,
    required this.taskRepository,
    required this.studyRepository,
  });

  final SettingsStorage settingsStorage;
  final TaskStorage taskStorage;
  final StudyStorage studyStorage;
  final NoticeStorage noticeStorage;
  final TaskRepository taskRepository;
  final StudySessionRepository studyRepository;

  /// 启动时加载所有持久化数据,返回 [AppSettings]。
  ///
  /// - 若无设置,返回默认值(并触发演示数据写入流程)。
  /// - 若有任务/学习/通知数据,则恢复到对应仓库。
  ///
  /// 优化:三组加载(settings / tasks+restore / study+restore)互相独立,
  /// 使用 [Future.wait] 并行执行,避免串行 await 拉长启动白屏时间。
  Future<AppSettings> loadAll() async {
    final results = await Future.wait([
      settingsStorage.load(),
      _loadAndRestoreTasks(),
      _loadAndRestoreStudy(),
    ]);
    return results[0] as AppSettings? ?? const AppSettings();
  }

  Future<void> _loadAndRestoreTasks() async {
    final savedTasks = await taskStorage.load();
    if (savedTasks.isNotEmpty) {
      await taskRepository.restoreFrom(savedTasks);
    }
  }

  Future<void> _loadAndRestoreStudy() async {
    final savedStudy = await studyStorage.loadHistory();
    if (savedStudy.isNotEmpty) {
      await studyRepository.restoreHistoryFrom(savedStudy);
    }
  }

  /// 保存当前设置。
  Future<void> saveSettings(AppSettings settings) =>
      settingsStorage.save(settings);

  /// 保存当前任务列表(包括已删除项)。
  Future<void> saveTasks() => taskStorage.saveAll(taskRepository.snapshot);

  /// 保存学习历史。
  Future<void> saveStudyHistory() =>
      studyStorage.saveHistory(studyRepository.historySnapshot);

  /// 保存通知列表(用于持久化已读状态)。
  Future<void> saveNotices(List<CampusNotice> notices) =>
      noticeStorage.saveAll(notices);

  /// 清除所有本地数据 — 任务、学习、设置回默认、通知已读状态。
  ///
  /// 内存仓库也会被清空。UI 应弹出确认对话框后再调用。
  Future<void> clearAllData() async {
    await Future.wait([
      taskStorage.clear(),
      studyStorage.clear(),
      noticeStorage.clear(),
      settingsStorage.clear(),
    ]);
    await taskRepository.clearAll();
    await studyRepository.clearHistory();
  }

  /// 恢复演示数据 — 重置为 MockData 默认数据(仅供开发与测试使用)。
  ///
  /// 正式参赛版本约束:此方法不通过 UI 暴露,仅用于:
  /// - 单元测试 / 集成测试中的演示数据准备
  /// - 开发模式下通过测试依赖注入调用
  Future<void> restoreDemoData() async {
    await taskRepository.resetToDemo();
    await studyRepository.resetToDemo();
    await saveTasks();
    await saveStudyHistory();
  }
}

/// Provider — 在 main 中 override 注入已初始化实例。
final dataPersistenceProvider = Provider<DataPersistenceService>((ref) {
  throw UnimplementedError(
    'dataPersistenceProvider 必须在 main 中 override',
  );
});
