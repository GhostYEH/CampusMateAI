import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 登录页轻量偏好。
///
/// 只保存用户主动勾选后的账号，不保存密码或认证凭据。
abstract interface class LoginPreferenceService {
  Future<String?> loadRememberedUsername();
  Future<void> rememberUsername(String? username);
}

class SharedPreferencesLoginPreferenceService
    implements LoginPreferenceService {
  static const _rememberedUsernameKey = 'auth.remembered_username';

  @override
  Future<String?> loadRememberedUsername() async {
    try {
      final preferences = await SharedPreferences.getInstance();
      return preferences.getString(_rememberedUsernameKey);
    } catch (_) {
      // 偏好读取失败不应阻塞登录。
      return null;
    }
  }

  @override
  Future<void> rememberUsername(String? username) async {
    try {
      final preferences = await SharedPreferences.getInstance();
      if (username == null || username.isEmpty) {
        await preferences.remove(_rememberedUsernameKey);
      } else {
        await preferences.setString(_rememberedUsernameKey, username);
      }
    } catch (_) {
      // 偏好写入失败不应改变认证结果。
    }
  }
}

final loginPreferenceServiceProvider = Provider<LoginPreferenceService>((ref) {
  return SharedPreferencesLoginPreferenceService();
});
