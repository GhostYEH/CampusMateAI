import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// 测试用 Dio Mock 适配器 — 拦截请求并返回预设响应。
///
/// 不依赖任何外部库,通过自定义 [Interceptor] 实现。
/// 用法:
/// ```dart
/// final adapter = MockDioAdapter();
/// final dio = Dio()..interceptors.add(adapter);
/// adapter.registerGet('/api/v1/health', {'status': 'ok'});
/// final client = ApiClient(baseUrl: 'http://test.local', dio: dio);
/// ```
class MockDioAdapter extends Interceptor {
  MockDioAdapter();

  /// 按方法 + 路径匹配的响应注册表。
  final List<_MockRoute> _routes = [];

  /// 默认 fallback 响应(未匹配时返回)。
  _MockResponse? _defaultResponse;

  /// 注册一个 GET 路由。
  /// [data] 可以是 Map<String, dynamic> 或 List<dynamic>(用于返回数组响应)。
  ///
  /// 同 method+path 的路由会被替换(后注册覆盖先注册),
  /// 便于"重试成功"测试场景。
  void registerGet(
    String path, {
    dynamic data,
    int statusCode = 200,
    Map<String, List<String>>? headers,
  }) {
    _upsertRoute(
      'GET',
      path,
      _MockResponse(data, statusCode, headers),
    );
  }

  /// 注册一个 POST 路由。
  void registerPost(
    String path, {
    dynamic data,
    int statusCode = 200,
    Map<String, List<String>>? headers,
  }) {
    _upsertRoute(
      'POST',
      path,
      _MockResponse(data, statusCode, headers),
    );
  }

  /// 注册一个 DELETE 路由。
  void registerDelete(
    String path, {
    dynamic data,
    int statusCode = 200,
    Map<String, List<String>>? headers,
  }) {
    _upsertRoute(
      'DELETE',
      path,
      _MockResponse(data, statusCode, headers),
    );
  }

  /// 注册流式 SSE 响应(用于 Counselor Chat)。
  void registerPostSseStream(
    String path, {
    required List<String> ssePayloads,
    int statusCode = 200,
  }) {
    _upsertRoute(
      'POST',
      path,
      _MockResponse(null, statusCode, null, sseStream: ssePayloads),
    );
  }

  /// 注册一个 DioException 响应(用于测试网络错误)。
  void registerGetError(String path, DioException error) {
    _upsertRoute('GET', path, _MockResponse(null, 0, null, error: error));
  }

  void registerPostError(String path, DioException error) {
    _upsertRoute('POST', path, _MockResponse(null, 0, null, error: error));
  }

  /// 替换同 method+path 的路由,避免旧路由遮蔽新路由。
  void _upsertRoute(String method, String path, _MockResponse response) {
    _routes.removeWhere(
      (r) =>
          r.method.toUpperCase() == method.toUpperCase() &&
          r.pathPattern == path,
    );
    _routes.add(_MockRoute(method, path, response));
  }

  /// 设置默认响应(未匹配路由时返回)。
  void setDefault({dynamic data, int statusCode = 404}) {
    _defaultResponse = _MockResponse(data, statusCode, null);
  }

  /// 已收到的请求记录(便于断言 body / headers)。
  final List<RecordedRequest> recordedRequests = [];

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    recordedRequests.add(
      RecordedRequest(
        method: options.method,
        path: options.path,
        data: options.data,
        headers: Map<String, dynamic>.from(options.headers),
      ),
    );

    // 匹配路由
    for (final route in _routes) {
      if (route.matches(options.method, options.path)) {
        final response = route.response;
        if (response.error != null) {
          handler.reject(response.error!);
          return;
        }
        // SSE 流式响应
        if (response.sseStream != null) {
          final stream = _buildSseStream(response.sseStream!);
          handler.resolve(
            Response<ResponseBody>(
              requestOptions: options,
              data: ResponseBody(
                stream,
                200,
                headers: {
                  Headers.contentTypeHeader: ['text/event-stream'],
                },
              ),
              statusCode: 200,
            ),
          );
          return;
        }
        // HTTP 4xx/5xx:走 Dio badResponse 路径,让 ApiException.fromDio 能解析结构化错误
        if (response.statusCode >= 400) {
          handler.reject(
            DioException(
              requestOptions: options,
              response: Response<dynamic>(
                requestOptions: options,
                data: response.data,
                statusCode: response.statusCode,
                headers: Headers.fromMap(
                  response.headers ??
                      {
                        'content-type': ['application/json'],
                      },
                ),
              ),
              type: DioExceptionType.badResponse,
            ),
          );
          return;
        }
        // 普通 JSON 响应
        handler.resolve(
          Response<dynamic>(
            requestOptions: options,
            data: response.data,
            statusCode: response.statusCode,
            headers: Headers.fromMap(
              response.headers ??
                  {
                    'content-type': ['application/json'],
                  },
            ),
          ),
        );
        return;
      }
    }

    // 默认 fallback
    if (_defaultResponse != null) {
      handler.resolve(
        Response<dynamic>(
          requestOptions: options,
          data: _defaultResponse!.data,
          statusCode: _defaultResponse!.statusCode,
        ),
      );
      return;
    }

    // 没有匹配:返回 404
    handler.resolve(
      Response<dynamic>(
        requestOptions: options,
        data: {
          'code': 'ROUTE_NOT_FOUND',
          'message': 'Mock 未注册路由: ${options.method} ${options.path}',
        },
        statusCode: 404,
      ),
    );
  }

  /// 把 SSE payload 列表转为字节流。
  Stream<Uint8List> _buildSseStream(List<String> payloads) async* {
    for (final p in payloads) {
      yield Uint8List.fromList(utf8.encode(p));
    }
  }
}

class _MockRoute {
  const _MockRoute(this.method, this.pathPattern, this.response);
  final String method;
  final String pathPattern;
  final _MockResponse response;

  bool matches(String m, String p) {
    if (m.toUpperCase() != method.toUpperCase()) return false;
    // 支持精确匹配或前缀匹配(以 * 结尾)
    if (pathPattern.endsWith('*')) {
      return p.startsWith(pathPattern.substring(0, pathPattern.length - 1));
    }
    return p == pathPattern || p.endsWith(pathPattern);
  }
}

class _MockResponse {
  const _MockResponse(
    this.data,
    this.statusCode,
    this.headers, {
    this.sseStream,
    this.error,
  });
  final dynamic data;
  final int statusCode;
  final Map<String, List<String>>? headers;
  final List<String>? sseStream;
  final DioException? error;
}

class RecordedRequest {
  const RecordedRequest({
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
