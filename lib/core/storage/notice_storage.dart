import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/notice.dart';
import 'local_storage.dart';

/// 校园通知持久化 Repository — 保存已读状态等。
class NoticeStorage {
  NoticeStorage(this._storage);

  final LocalStorage _storage;
  static const _key = 'app_notices';

  /// 读取本地通知列表(已读状态会保留)。
  Future<List<CampusNotice>> load() async {
    final raw = await _storage.getString(_key);
    if (raw == null) return [];
    try {
      final list = JsonCodecHelper.decodeList(raw);
      return list.map(CampusNotice.fromJson).toList();
    } catch (_) {
      return [];
    }
  }

  /// 保存通知列表。
  Future<void> saveAll(List<CampusNotice> notices) async {
    final jsonList = notices.map((n) => n.toJson()).toList();
    await _storage.setString(_key, JsonCodecHelper.encodeList(jsonList));
  }

  /// 清除通知列表。
  Future<void> clear() async {
    await _storage.remove(_key);
  }
}

final noticeStorageProvider = Provider<NoticeStorage>((ref) {
  throw UnimplementedError(
    'noticeStorageProvider 必须在 main 中 override',
  );
});
