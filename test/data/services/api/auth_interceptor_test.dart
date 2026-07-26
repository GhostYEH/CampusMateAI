import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/models/auth.dart';
import 'package:campus_companion/data/models/user.dart';
import 'package:campus_companion/data/services/api/auth_interceptor.dart';
import 'package:campus_companion/data/services/api/token_storage.dart';

/// 测试用 TokenStorage — 不依赖 SharedPreferences,只内存。
class _FakeTokenStorage implements TokenStorage {
  _FakeTokenStorage({AuthSession? initial}) : _session = initial;

  AuthSession? _session;

  @override
  AuthSession? get currentSession => _session;

  @override
  Future<void> saveSession(AuthSession session) async {
    _session = session;
  }

  @override
  Future<AuthSession?> loadSession() async => _session;

  @override
  Future<void> clear() async {
    _session = null;
  }
}

AuthSession _session({
  String accessToken = 'access-token-aaa',
  String refreshToken = 'refresh-token-rrr',
}) {
  return AuthSession(
    user: const AppUser(
      id: 'u_test_1',
      name: '测试用户',
      role: UserRole.student,
      avatarSeed: 'testuser',
    ),
    accessToken: accessToken,
    refreshToken: refreshToken,
    expiresAt: DateTime.now().add(const Duration(hours: 1)),
    tokenType: 'Bearer',
  );
}

/// 给每个请求注入唯一 _req_id(模拟 ApiClient 应有的行为,便于并发去重)。
class _RequestStamper extends Interceptor {
  int _counter = 0;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    options.extra['_req_id'] = 'req_${_counter++}';
    handler.next(options);
  }
}

/// 状态化路由拦截器 — 用于按调用次数返回不同响应(模拟"首次 401,重试 200")。
///
/// 工作方式:
/// - 对注册的路径,第 N 次调用按预设序列返回响应。
/// - 序列耗尽后保持最后一个。
class _StatefulRouteInterceptor extends Interceptor {
  _StatefulRouteInterceptor();

  final Map<String, List<_StubResponse>> _responsesByPath = {};

  /// 记录每个路径的调用次数。
  final Map<String, int> _callCount = {};

  /// refresh 接口被调用的次数。
  int refreshCallCount = 0;

  /// 所有已收到的请求(便于断言 headers / body)。
  final List<RecordedStub> recorded = [];

  void registerPath(
    String path, {
    required List<_StubResponse> responses,
  }) {
    _responsesByPath[path] = responses;
    _callCount[path] = 0;
  }

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final path = options.path;
    recorded.add(
      RecordedStub(
        method: options.method,
        path: path,
        data: options.data,
        headers: Map<String, dynamic>.from(options.headers),
      ),
    );

    if (path == '/api/v1/auth/refresh') {
      refreshCallCount++;
    }

    final responses = _responsesByPath[path];
    if (responses == null || responses.isEmpty) {
      handler.next(options);
      return;
    }

    final count = (_callCount[path] ?? 0) + 1;
    _callCount[path] = count;

    final index = (count - 1).clamp(0, responses.length - 1);
    final resp = responses[index];

    if (resp.isError) {
      // 第二个参数 true 表示调用前面拦截器的 onError(逆序)
      // 这样 auth_interceptor(在 routeInterceptor 之前)的 onError 才能捕获 401
      handler.reject(
        DioException(
          requestOptions: options,
          type: DioExceptionType.badResponse,
          response: Response<dynamic>(
            requestOptions: options,
            data: resp.data,
            statusCode: resp.statusCode,
          ),
        ),
        true,
      );
      return;
    }
    handler.resolve(
      Response<dynamic>(
        requestOptions: options,
        data: resp.data,
        statusCode: resp.statusCode,
      ),
    );
  }
}

class _StubResponse {
  const _StubResponse({
    this.data,
    required this.statusCode,
    this.isError = false,
  });
  final dynamic data;
  final int statusCode;
  final bool isError;

  factory _StubResponse.ok(dynamic data, {int statusCode = 200}) =>
      _StubResponse(data: data, statusCode: statusCode);

  factory _StubResponse.error(dynamic data, int statusCode) =>
      _StubResponse(data: data, statusCode: statusCode, isError: true);
}

class RecordedStub {
  const RecordedStub({
    required this.method,
    required this.path,
    required this.data,
    required this.headers,
  });
  final String method;
  final String path;
  final dynamic data;
  final Map<String, dynamic> headers;
}

void main() {
  late _StatefulRouteInterceptor routeInterceptor;
  late Dio dio;
  late _FakeTokenStorage tokenStorage;
  late AuthInterceptor authInterceptor;
  late List<String> sessionExpiredCalls;

  void setupDio({AuthSession? initialSession, bool useDefaultSession = true}) {
    routeInterceptor = _StatefulRouteInterceptor();
    dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    tokenStorage = _FakeTokenStorage(
      initial: useDefaultSession ? (initialSession ?? _session()) : null,
    );
    sessionExpiredCalls = [];
    authInterceptor = AuthInterceptor(
      tokenStorage: tokenStorage,
      dio: dio,
      refreshPath: '/api/v1/auth/refresh',
      onSessionExpired: () => sessionExpiredCalls.add('expired'),
    );
    // 顺序:stamper → auth_interceptor → route_interceptor
    // stamper 先于 auth_interceptor 注入唯一 _req_id(模拟 ApiClient 应有的行为)
    // onRequest: stamper → auth_interceptor → route_interceptor
    // onError: route_interceptor → auth_interceptor (捕获 401)
    dio.interceptors.add(_RequestStamper());
    dio.interceptors.add(authInterceptor);
    dio.interceptors.add(routeInterceptor);
  }

  /// 注册 refresh 接口成功响应。
  void registerRefreshSuccess({
    String accessToken = 'new-token-xyz',
    String refreshToken = 'new-refresh',
  }) {
    routeInterceptor.registerPath(
      '/api/v1/auth/refresh',
      responses: [
        _StubResponse.ok({
          'access_token': accessToken,
          'refresh_token': refreshToken,
          'expires_at':
              DateTime.now().add(const Duration(hours: 1)).toIso8601String(),
          'token_type': 'Bearer',
        }),
      ],
    );
  }

  group('AuthInterceptor - onRequest', () {
    test('存在有效 access_token 时注入 Authorization 头', () async {
      setupDio(initialSession: _session(accessToken: 'access-token-aaa'));
      routeInterceptor.registerPath(
        '/api/v1/me',
        responses: [
          _StubResponse.ok({'id': 'u_test_1'}),
        ],
      );

      await dio.get<dynamic>('/api/v1/me');

      final recorded = routeInterceptor.recorded.last;
      expect(recorded.headers['Authorization'], 'Bearer access-token-aaa');
    });

    test('mock token(以 mock. 前缀)不发送 Authorization 头', () async {
      setupDio(initialSession: _session(accessToken: 'mock.student.demo'));
      routeInterceptor.registerPath(
        '/api/v1/me',
        responses: [
          _StubResponse.ok({'id': 'u_test_1'}),
        ],
      );

      await dio.get<dynamic>('/api/v1/me');

      final recorded = routeInterceptor.recorded.last;
      expect(recorded.headers.containsKey('Authorization'), isFalse);
    });

    test('无会话时不发送 Authorization 头', () async {
      setupDio(useDefaultSession: false);
      routeInterceptor.registerPath(
        '/api/v1/me',
        responses: [
          _StubResponse.ok({'id': 'u_test_1'}),
        ],
      );

      await dio.get<dynamic>('/api/v1/me');

      final recorded = routeInterceptor.recorded.last;
      expect(recorded.headers.containsKey('Authorization'), isFalse);
    });
  });

  group('AuthInterceptor - 401 refresh + 重试', () {
    test('401 时触发 refresh,用新 token 重试原请求并返回 200', () async {
      setupDio(initialSession: _session(accessToken: 'expired-token'));
      // /api/v1/me:首次 401,重试 200
      routeInterceptor.registerPath(
        '/api/v1/me',
        responses: [
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
          _StubResponse.ok({'id': 'u_test_1', 'name': '测试用户'}),
        ],
      );
      registerRefreshSuccess();

      final response = await dio.get<dynamic>('/api/v1/me');

      expect(response.statusCode, 200);
      expect(response.data['id'], 'u_test_1');
      // refresh 接口被调用一次
      expect(routeInterceptor.refreshCallCount, 1);
      // TokenStorage 已更新为新 access_token
      expect(tokenStorage.currentSession?.accessToken, 'new-token-xyz');
      expect(tokenStorage.currentSession?.refreshToken, 'new-refresh');
      // 会话过期回调未被调用
      expect(sessionExpiredCalls, isEmpty);
    });

    test('refresh 接口返回 401 时不无限重试 — 触发 onSessionExpired', () async {
      setupDio(initialSession: _session(accessToken: 'expired-token'));
      routeInterceptor.registerPath(
        '/api/v1/me',
        responses: [
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
          _StubResponse.ok({'id': 'should-not-reach'}),
        ],
      );
      // refresh 接口返回 401
      routeInterceptor.registerPath(
        '/api/v1/auth/refresh',
        responses: [
          _StubResponse.error({'code': 'INVALID_REFRESH_TOKEN'}, 401),
        ],
      );

      await expectLater(
        dio.get<dynamic>('/api/v1/me'),
        throwsA(isA<DioException>()),
      );

      // onSessionExpired 被调用
      expect(sessionExpiredCalls.length, 1);
      // refresh 接口只被调用一次
      expect(routeInterceptor.refreshCallCount, 1);
    });

    test('refresh 接口网络异常时触发 onSessionExpired 并抛出', () async {
      setupDio(initialSession: _session(accessToken: 'expired-token'));
      routeInterceptor.registerPath(
        '/api/v1/me',
        responses: [
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
        ],
      );
      // refresh 接口"网络错误"(返回 0 状态码 + error 标记,模拟连接失败)
      // 用 dio 直接 reject 网络错误需要自定义,这里用 500 模拟 refresh 失败
      routeInterceptor.registerPath(
        '/api/v1/auth/refresh',
        responses: [
          _StubResponse.error({'code': 'INTERNAL_ERROR'}, 500),
        ],
      );

      await expectLater(
        dio.get<dynamic>('/api/v1/me'),
        throwsA(isA<DioException>()),
      );

      expect(sessionExpiredCalls.length, 1);
    });
  });

  group('AuthInterceptor - 并发请求去重', () {
    test('多个 401 并发请求只触发一次 refresh,且都使用新 token 重试成功', () async {
      setupDio(initialSession: _session(accessToken: 'expired-token'));
      // /api/v1/concurrent:前 3 次都 401,接下来都 200(对应重试)
      routeInterceptor.registerPath(
        '/api/v1/concurrent',
        responses: [
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
          _StubResponse.ok({'ok': true}),
          _StubResponse.ok({'ok': true}),
          _StubResponse.ok({'ok': true}),
        ],
      );
      registerRefreshSuccess(
        accessToken: 'new-token-shared',
        refreshToken: 'new-refresh-shared',
      );

      // 同时发起三个并发请求
      final results = await Future.wait([
        dio.get<dynamic>('/api/v1/concurrent'),
        dio.get<dynamic>('/api/v1/concurrent'),
        dio.get<dynamic>('/api/v1/concurrent'),
      ]);

      // 三个请求都成功
      expect(results.every((r) => r.statusCode == 200), isTrue);
      // refresh 接口只调用一次(去重)
      expect(routeInterceptor.refreshCallCount, 1);
      // token 已更新
      expect(tokenStorage.currentSession?.accessToken, 'new-token-shared');
      // onSessionExpired 不应被调用
      expect(sessionExpiredCalls, isEmpty);
    });

    test('refresh 失败时所有并发请求都抛出', () async {
      setupDio(initialSession: _session(accessToken: 'expired-token'));
      // /api/v1/concurrent:前 2 次 401
      routeInterceptor.registerPath(
        '/api/v1/concurrent',
        responses: [
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
        ],
      );
      // refresh 失败
      routeInterceptor.registerPath(
        '/api/v1/auth/refresh',
        responses: [
          _StubResponse.error({'code': 'INVALID_REFRESH_TOKEN'}, 401),
        ],
      );

      // 用 try/catch 包装,避免 catchError 类型不匹配
      Future<Object?> tryGet() async {
        try {
          final r = await dio.get<dynamic>('/api/v1/concurrent');
          return r;
        } catch (e) {
          return e;
        }
      }

      final results = await Future.wait([tryGet(), tryGet()]);

      // 都抛出 DioException
      expect(results.every((r) => r is DioException), isTrue);
      // refresh 接口只调用一次(去重)
      expect(routeInterceptor.refreshCallCount, 1);
      // onSessionExpired 应被调用
      expect(sessionExpiredCalls.isNotEmpty, isTrue);
    });
  });

  group('AuthInterceptor - 边界场景', () {
    test('401 但是 refresh 请求本身 — 不再触发刷新,直接抛出', () async {
      setupDio(initialSession: _session(accessToken: 'expired-token'));
      // refresh 接口返回 401
      routeInterceptor.registerPath(
        '/api/v1/auth/refresh',
        responses: [
          _StubResponse.error({'code': 'INVALID_REFRESH_TOKEN'}, 401),
        ],
      );

      // 直接调用 refresh 接口(应得到 401,不触发二次刷新)
      await expectLater(
        dio.post<dynamic>(
          '/api/v1/auth/refresh',
          data: {
            'refresh_token': 'refresh-token-rrr',
          },
        ),
        throwsA(isA<DioException>()),
      );

      // refresh 接口只被调用一次(原始那次)
      expect(routeInterceptor.refreshCallCount, 1);
      // onSessionExpired 不应被调用(因为是 refresh 请求本身的 401,
      // 走 isRefreshCall 分支,不会触发 _refreshAndRetry)
      expect(sessionExpiredCalls, isEmpty);
    });

    test('非 401 错误(如 500)不触发 refresh', () async {
      setupDio(initialSession: _session(accessToken: 'valid-token'));
      routeInterceptor.registerPath(
        '/api/v1/server-error',
        responses: [
          _StubResponse.error({'code': 'INTERNAL_ERROR'}, 500),
        ],
      );
      registerRefreshSuccess();

      await expectLater(
        dio.get<dynamic>('/api/v1/server-error'),
        throwsA(isA<DioException>()),
      );

      // refresh 接口未被调用
      expect(routeInterceptor.refreshCallCount, 0);
      expect(sessionExpiredCalls, isEmpty);
    });

    test('原请求重试时已注入新 Authorization 头', () async {
      setupDio(initialSession: _session(accessToken: 'old-token'));
      routeInterceptor.registerPath(
        '/api/v1/headers-check',
        responses: [
          _StubResponse.error({'code': 'UNAUTHORIZED'}, 401),
          _StubResponse.ok({'ok': true}),
        ],
      );
      registerRefreshSuccess(accessToken: 'new-token-injected');

      await dio.get<dynamic>('/api/v1/headers-check');

      // 找到第二次对 /api/v1/headers-check 的请求记录
      final headerCheckRequests = routeInterceptor.recorded
          .where((r) => r.path == '/api/v1/headers-check')
          .toList();
      expect(headerCheckRequests.length, 2);
      // 第二次(重试)的 Authorization 头应为新 token
      expect(
        headerCheckRequests[1].headers['Authorization'],
        'Bearer new-token-injected',
      );
    });
  });
}
