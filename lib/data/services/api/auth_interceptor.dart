import 'dart:async';
import 'dart:collection';

import 'package:dio/dio.dart';

import '../../models/models.dart';
import 'token_storage.dart';

/// 认证拦截器 — 自动注入 Authorization 头,处理 401 refresh + 单次重试。
///
/// 严格遵循 AGENTS.md 凭证规范:
/// - 防止多个并发请求重复刷新 token(使用 [Completer] 互斥)
/// - 401 时尝试一次 refresh;refresh 失败则触发 [onSessionExpired] 回调
/// - 不在日志中打印 token
///
/// 工作流程:
/// 1. onRequest: 若有 access_token → 注入 Authorization 头(Mock token 不发送)
/// 2. onError: 若 401 且不是 refresh 请求 → 触发 refresh(互斥)
/// 3. refresh 成功 → 用新 token 重试原请求(仅一次)
/// 4. refresh 失败 → 调用 [onSessionExpired],向上抛出原 401
class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required this.tokenStorage,
    required this.dio,
    required this.refreshPath,
    this.onSessionExpired,
  });

  final TokenStorage tokenStorage;

  /// 所属 Dio 实例 — 用于发起 refresh 请求(通过 [_skipAuth] 标记避免递归)。
  final Dio dio;

  /// refresh 接口路径(相对 baseUrl),例如 `/api/v1/auth/refresh`。
  final String refreshPath;

  /// 会话过期回调 — 由 [AuthNotifier] 注册,触发退出到登录页。
  final void Function()? onSessionExpired;

  /// 互斥锁 — 并发 401 时只触发一次 refresh。
  Completer<AuthSession?>? _refreshCompleter;

  /// 防止重试请求再次进入 401 处理(避免无限循环)。
  final Set<String> _retriedRequestIds = HashSet<String>();

  /// 标记请求跳过认证拦截(用于 refresh 请求本身)。
  static const _skipAuth = 'skip_auth_interceptor';

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    if (options.extra[_skipAuth] == true) {
      handler.next(options);
      return;
    }
    final session = tokenStorage.currentSession;
    if (session != null &&
        !session.accessToken.startsWith('mock.') &&
        session.accessToken.isNotEmpty) {
      options.headers['Authorization'] =
          '${session.tokenType} ${session.accessToken}';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final response = err.response;
    final path = err.requestOptions.path;
    final isRefreshCall = path == refreshPath || path.endsWith(refreshPath);
    final requestId = _requestId(err.requestOptions);

    if (response?.statusCode != 401 ||
        isRefreshCall ||
        _retriedRequestIds.contains(requestId)) {
      handler.next(err);
      return;
    }

    _refreshAndRetry(err.requestOptions, handler);
  }

  Future<void> _refreshAndRetry(
    RequestOptions original,
    ErrorInterceptorHandler handler,
  ) async {
    final requestId = _requestId(original);
    _retriedRequestIds.add(requestId);

    try {
      final newSession = await _refreshOnce();
      if (newSession == null) {
        onSessionExpired?.call();
        handler.next(
          DioException(
            requestOptions: original,
            type: DioExceptionType.unknown,
            error: 'SESSION_EXPIRED',
            message: '会话已过期,请重新登录',
          ),
        );
        return;
      }
      // 用新 token 重试原请求
      final cloned = original
        ..headers['Authorization'] =
            '${newSession.tokenType} ${newSession.accessToken}';
      final retryResp = await dio.fetch<dynamic>(
        RequestOptions(
          path: cloned.path,
          data: cloned.data,
          queryParameters: cloned.queryParameters,
          method: cloned.method,
          headers: cloned.headers,
          extra: {_skipAuth: true},
          responseType: cloned.responseType,
          contentType: cloned.contentType,
        ),
      );
      handler.resolve(retryResp);
    } on DioException catch (e) {
      onSessionExpired?.call();
      handler.next(e);
    } catch (e) {
      onSessionExpired?.call();
      handler.next(
        DioException(
          requestOptions: original,
          type: DioExceptionType.unknown,
          error: e,
          message: '会话刷新失败',
        ),
      );
    } finally {
      _retriedRequestIds.remove(requestId);
    }
  }

  /// 触发一次 refresh,并发时仅执行一次真实请求,其余等待结果。
  Future<AuthSession?> _refreshOnce() async {
    if (_refreshCompleter != null) {
      return _refreshCompleter!.future;
    }
    final completer = Completer<AuthSession?>();
    _refreshCompleter = completer;

    try {
      final current = tokenStorage.currentSession;
      if (current == null) {
        completer.complete(null);
        return null;
      }
      final resp = await dio.post<Map<String, dynamic>>(
        refreshPath,
        data: {'refresh_token': current.refreshToken},
        options: Options(
          extra: {_skipAuth: true},
          headers: {'Accept': 'application/json'},
        ),
      );
      final data = resp.data ?? {};
      final newSession = AuthSession(
        user: current.user,
        accessToken: data['access_token'] as String? ?? current.accessToken,
        refreshToken: data['refresh_token'] as String? ?? current.refreshToken,
        expiresAt: data['expires_at'] is String
            ? DateTime.parse(data['expires_at'] as String)
            : DateTime.now().add(const Duration(hours: 2)),
        tokenType: data['token_type'] as String? ?? current.tokenType,
      );
      await tokenStorage.saveSession(newSession);
      completer.complete(newSession);
      return newSession;
    } catch (e) {
      completer.complete(null);
      return null;
    } finally {
      _refreshCompleter = null;
    }
  }

  String _requestId(RequestOptions options) {
    // 用 path + method + 一段随机串(由 extra 中的 _id 提供)作为唯一标识
    final extra = options.extra['_req_id'] ?? '';
    return '${options.method}:${options.path}:$extra';
  }

  /// 给请求注入唯一 ID,便于重试去重(由 [ApiClient] 在每次请求时调用)。
  static String stampRequestId() {
    return DateTime.now().microsecondsSinceEpoch.toString();
  }
}
