import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/task.dart';
import 'local_storage.dart';

/// 任务持久化 Repository — 通过 [LocalStorage] 保存任务列表。
///
/// 与 [TaskRepository] 解耦:本类仅负责存储读写,
/// [MockTaskRepository] 在初始化时从此处恢复数据。
class TaskStorage {
  TaskStorage(this._storage);

  final LocalStorage _storage;
  static const _key = 'app_tasks';

  /// 读取本地任务列表。若不存在则返回空列表。
  Future<List<Task>> load() async {
    final raw = await _storage.getString(_key);
    if (raw == null) return [];
    try {
      final list = JsonCodecHelper.decodeList(raw);
      return list.map(Task.fromJson).toList();
    } catch (_) {
      return [];
    }
  }

  /// 保存任务列表到本地存储。
  Future<void> saveAll(List<Task> tasks) async {
    final jsonList = tasks.map((t) => t.toJson()).toList();
    await _storage.setString(_key, JsonCodecHelper.encodeList(jsonList));
  }

  /// 清除任务列表。
  Future<void> clear() async {
    await _storage.remove(_key);
  }
}

/// 任务持久化 Provider。
final taskStorageProvider = Provider<TaskStorage>((ref) {
  throw UnimplementedError(
    'taskStorageProvider 必须在 main 中 override',
  );
});
