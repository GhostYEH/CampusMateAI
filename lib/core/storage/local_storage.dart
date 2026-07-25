import 'dart:convert';

import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:shared_preferences/shared_preferences.dart';

/// 轻量本地存储抽象 — 用于 SharedPreferences 持久化与 JSON 序列化。
///
/// 设计目标(AGENTS.md §4):
/// - UI 通过 Repository 接口访问,与存储实现解耦
/// - 应用重启后可恢复任务、设置、学习记录、通知
/// - 支持清除本地数据(演示模式下可恢复)
///
/// 当前实现:SharedPreferences + JSON 字符串。
/// 后续可迁移至 Drift/SQLite。
abstract class LocalStorage {
  Future<String?> getString(String key);
  Future<bool> setString(String key, String value);
  Future<bool> remove(String key);
  Future<bool> clear();
  Future<bool> containsKey(String key);
  Future<Set<String>> getKeys();
}

/// SharedPreferences 实现的 [LocalStorage]。
class SharedPreferencesLocalStorage implements LocalStorage {
  SharedPreferencesLocalStorage._(this._prefs);

  static SharedPreferencesLocalStorage? _instance;
  final SharedPreferences _prefs;

  /// 初始化(异步),应在应用启动前调用一次。
  static Future<SharedPreferencesLocalStorage> initialize() async {
    if (_instance != null) return _instance!;
    final prefs = await SharedPreferences.getInstance();
    _instance = SharedPreferencesLocalStorage._(prefs);
    return _instance!;
  }

  /// 测试用注入构造函数。
  @visibleForTesting
  static void setTestInstance(SharedPreferencesLocalStorage? instance) {
    _instance = instance;
  }

  static SharedPreferencesLocalStorage get instance {
    if (_instance == null) {
      throw StateError(
        'SharedPreferencesLocalStorage 未初始化,请先调用 initialize()',
      );
    }
    return _instance!;
  }

  @override
  Future<String?> getString(String key) async => _prefs.getString(key);

  @override
  Future<bool> setString(String key, String value) =>
      _prefs.setString(key, value);

  @override
  Future<bool> remove(String key) => _prefs.remove(key);

  @override
  Future<bool> clear() => _prefs.clear();

  @override
  Future<bool> containsKey(String key) async => _prefs.containsKey(key);

  @override
  Future<Set<String>> getKeys() async => _prefs.getKeys().toSet();
}

/// JSON 序列化辅助 — 将对象编码为字符串、从字符串解码。
class JsonCodecHelper {
  static const _codec = JsonCodec();

  static String encode(Map<String, dynamic> json) => _codec.encode(json);

  static Map<String, dynamic> decode(String raw) {
    final decoded = _codec.decode(raw);
    if (decoded is Map<String, dynamic>) return decoded;
    throw const FormatException('JSON 不是 Map<String, dynamic>');
  }

  static String encodeList(List<Map<String, dynamic>> list) =>
      _codec.encode(list);

  static List<Map<String, dynamic>> decodeList(String raw) {
    final decoded = _codec.decode(raw);
    if (decoded is List) {
      return decoded
          .map(
            (e) => e is Map<String, dynamic>
                ? e
                : Map<String, dynamic>.from(e as Map),
          )
          .toList();
    }
    throw const FormatException('JSON 不是 List');
  }
}
