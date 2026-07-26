import 'package:equatable/equatable.dart';

import 'user.dart';

/// 登录请求凭据。
class LoginCredentials extends Equatable {
  const LoginCredentials({
    required this.username,
    required this.password,
  });

  final String username;
  final String password;

  @override
  List<Object?> get props => [username, password];
}

/// 认证会话 — 登录成功后由后端返回(Mock 或 Real)。
///
/// 包含 access_token / refresh_token / expires_at 与当前用户信息。
/// 严禁打印 token 到日志(AGENTS.md 凭证保存规范)。
class AuthSession extends Equatable {
  const AuthSession({
    required this.user,
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    this.tokenType = 'Bearer',
  });

  final AppUser user;
  final String accessToken;
  final String refreshToken;
  final DateTime expiresAt;
  final String tokenType;

  /// 是否已过期(预留 30 秒缓冲,避免边界面请求失败)。
  bool get isExpired {
    final now = DateTime.now();
    return now.isAfter(expiresAt.subtract(const Duration(seconds: 30)));
  }

  /// 是否需要刷新(已过期但 refresh_token 仍可能有效)。
  bool get needsRefresh => isExpired;

  /// 剩余有效时长(可负)。
  Duration get remaining => expiresAt.difference(DateTime.now());

  AuthSession copyWith({
    AppUser? user,
    String? accessToken,
    String? refreshToken,
    DateTime? expiresAt,
    String? tokenType,
  }) {
    return AuthSession(
      user: user ?? this.user,
      accessToken: accessToken ?? this.accessToken,
      refreshToken: refreshToken ?? this.refreshToken,
      expiresAt: expiresAt ?? this.expiresAt,
      tokenType: tokenType ?? this.tokenType,
    );
  }

  /// 序列化为可持久化的 JSON(只保存必要字段)。
  ///
  /// 注意: 调用方应使用 [TokenStorage] 进行轻量混淆后保存,
  /// 不应直接以明文写入 SharedPreferences。
  Map<String, dynamic> toJson() => {
        'user': user.toJson(),
        'accessToken': accessToken,
        'refreshToken': refreshToken,
        'expiresAt': expiresAt.toIso8601String(),
        'tokenType': tokenType,
      };

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    return AuthSession(
      user: AppUser.fromJson(json['user'] as Map<String, dynamic>),
      accessToken: json['accessToken'] as String,
      refreshToken: json['refreshToken'] as String,
      expiresAt: DateTime.parse(json['expiresAt'] as String),
      tokenType: json['tokenType'] as String? ?? 'Bearer',
    );
  }

  @override
  List<Object?> get props =>
      [user, accessToken, refreshToken, expiresAt, tokenType];
}

/// 登录失败原因 — 用于 UI 友好提示。
enum AuthFailure {
  invalidCredentials('用户名或密码错误'),
  networkError('网络连接失败,请检查后重试'),
  timeout('请求超时,请稍后重试'),
  accountLocked('账号已锁定,请联系管理员'),
  serverError('服务器暂时不可用'),
  unknown('登录失败,请重试');

  const AuthFailure(this.message);
  final String message;

  static AuthFailure fromCode(String? code) {
    if (code == null) return AuthFailure.unknown;
    final c = code.toLowerCase();
    switch (c) {
      case 'invalid_credentials':
        return AuthFailure.invalidCredentials;
      case 'account_locked':
        return AuthFailure.accountLocked;
      case 'network_error':
        return AuthFailure.networkError;
      case 'timeout':
        return AuthFailure.timeout;
      case 'server_error':
        return AuthFailure.serverError;
      default:
        return AuthFailure.unknown;
    }
  }
}
