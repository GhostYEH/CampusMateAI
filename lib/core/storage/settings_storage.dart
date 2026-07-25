import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/settings.dart';
import 'local_storage.dart';

/// 设置持久化 Repository — 通过 [LocalStorage] 保存 [AppSettings]。
///
/// 应用启动时调用 [load] 读取,UI 修改时调用 [save]。
class SettingsStorage {
  SettingsStorage(this._storage);

  final LocalStorage _storage;
  static const _key = 'app_settings';

  /// 读取本地设置。若不存在则返回 null(由调用方决定默认值)。
  Future<AppSettings?> load() async {
    final raw = await _storage.getString(_key);
    if (raw == null) return null;
    try {
      return AppSettings.fromJson(JsonCodecHelper.decode(raw));
    } catch (_) {
      return null;
    }
  }

  /// 保存设置到本地存储。
  Future<void> save(AppSettings settings) async {
    await _storage.setString(_key, JsonCodecHelper.encode(settings.toJson()));
  }

  /// 清除设置(回到默认值)。
  Future<void> clear() async {
    await _storage.remove(_key);
  }
}

/// 设置持久化 Provider。
///
/// 测试中可 override 为内存实现。
final settingsStorageProvider = Provider<SettingsStorage>((ref) {
  throw UnimplementedError(
    'settingsStorageProvider 必须在 main 中 override 为基于已初始化 LocalStorage 的实现',
  );
});
