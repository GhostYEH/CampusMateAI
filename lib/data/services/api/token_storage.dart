import 'dart:convert';
import 'dart:math';

import '../../../core/storage/local_storage.dart';
import '../../models/models.dart';

/// Token 持久化存储 — 使用 SharedPreferences + 轻量 XOR 混淆。
///
/// 严格遵循 AGENTS.md 凭证规范:
/// - **不**在日志中打印 token
/// - **不**把密码保存到 SharedPreferences
/// - 401 时尝试一次 refresh(由 [AuthInterceptor] 实现)
/// - refresh 失败后退出到登录页(由 [AuthNotifier] 处理)
///
/// 注意: SharedPreferences 在 Android 上是明文 XML,iOS 上是 plist。
/// 这里使用 XOR + base64 进行轻量混淆,主要防止被随手查看。
/// 真正的密钥保护应使用 flutter_secure_storage(后续阶段接入)。
///
/// 当前阶段优先保证: token 不被无意打印、不被 SharedPreferences 直读可见。
class TokenStorage {
  TokenStorage(this._storage);

  final LocalStorage _storage;

  static const _keySession = 'auth_session_v1';
  static const _keySeed = 'auth_seed_v1';

  /// 混淆种子 — 每次应用首次安装时随机生成一次,持久化保存。
  /// 之后所有 token 数据均使用此种子进行 XOR 后再 base64 存储。
  String? _cachedSeed;

  AuthSession? _cachedSession;

  /// 当前会话(只读访问器,供 [AuthInterceptor] 同步读取)。
  AuthSession? get currentSession => _cachedSession;

  /// 保存会话(包括 access_token / refresh_token / user / expiresAt)。
  Future<void> saveSession(AuthSession session) async {
    final seed = await _ensureSeed();
    final json = session.toJson();
    final raw = jsonEncode(json);
    final obfuscated = _xorString(raw, seed);
    final encoded = base64Encode(obfuscated);
    await _storage.setString(_keySession, encoded);
    _cachedSession = session;
  }

  /// 读取会话(若不存在或解析失败返回 null)。
  Future<AuthSession?> loadSession() async {
    if (_cachedSession != null) return _cachedSession;
    final encoded = await _storage.getString(_keySession);
    if (encoded == null || encoded.isEmpty) return null;
    try {
      final seed = await _ensureSeed();
      final obfuscated = base64Decode(encoded);
      final raw = _xorBytesToString(obfuscated, seed);
      final json = jsonDecode(raw) as Map<String, dynamic>;
      final session = AuthSession.fromJson(json);
      _cachedSession = session;
      return session;
    } catch (_) {
      // 解析失败说明数据损坏或种子丢失,清除避免反复失败
      await clear();
      return null;
    }
  }

  /// 清除所有会话数据。
  Future<void> clear() async {
    await _storage.remove(_keySession);
    _cachedSession = null;
  }

  /// 生成或读取混淆种子(只生成一次,持久化保存)。
  Future<String> _ensureSeed() async {
    if (_cachedSeed != null) return _cachedSeed!;
    var seed = await _storage.getString(_keySeed);
    if (seed == null || seed.isEmpty) {
      final random = Random.secure();
      final bytes = List<int>.generate(32, (_) => random.nextInt(256));
      seed = base64Encode(bytes);
      await _storage.setString(_keySeed, seed);
    }
    _cachedSeed = seed;
    return seed;
  }

  /// XOR 字符串 → 字节列表(用于编码方向)。
  List<int> _xorString(String input, String seed) {
    final inputBytes = utf8.encode(input);
    final seedBytes = utf8.encode(seed);
    final out = List<int>.filled(inputBytes.length, 0);
    for (var i = 0; i < inputBytes.length; i++) {
      out[i] = inputBytes[i] ^ seedBytes[i % seedBytes.length];
    }
    return out;
  }

  /// XOR 字节列表 → 字符串(用于解码方向)。
  String _xorBytesToString(List<int> input, String seed) {
    final seedBytes = utf8.encode(seed);
    final out = List<int>.filled(input.length, 0);
    for (var i = 0; i < input.length; i++) {
      out[i] = input[i] ^ seedBytes[i % seedBytes.length];
    }
    return utf8.decode(out);
  }
}
