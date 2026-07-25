import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/study.dart';
import 'local_storage.dart';

/// 学习会话历史持久化 Repository。
class StudyStorage {
  StudyStorage(this._storage);

  final LocalStorage _storage;
  static const _key = 'app_study_history';

  /// 读取本地学习历史。
  Future<List<StudySession>> loadHistory() async {
    final raw = await _storage.getString(_key);
    if (raw == null) return [];
    try {
      final list = JsonCodecHelper.decodeList(raw);
      return list.map(StudySession.fromJson).toList();
    } catch (_) {
      return [];
    }
  }

  /// 保存学习历史。
  Future<void> saveHistory(List<StudySession> history) async {
    final jsonList = history.map((s) => s.toJson()).toList();
    await _storage.setString(_key, JsonCodecHelper.encodeList(jsonList));
  }

  /// 清除学习历史。
  Future<void> clear() async {
    await _storage.remove(_key);
  }
}

final studyStorageProvider = Provider<StudyStorage>((ref) {
  throw UnimplementedError(
    'studyStorageProvider 必须在 main 中 override',
  );
});
