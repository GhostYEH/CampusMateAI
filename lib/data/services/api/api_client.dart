import 'package:dio/dio.dart';

/// 后端 API 错误 — 携带结构化错误码,便于 UI 层展示与降级。
class ApiException implements Exception {
  const ApiException({
    required this.code,
    required this.message,
    this.details,
    this.httpStatus,
  });

  /// 错误码(与后端 `code` 字段对齐),例如:
  /// - NOTICE_EMPTY / NOTICE_TOO_LONG / NOTICE_UNPARSEABLE
  /// - KNOWLEDGE_BASE_EMPTY / DOCUMENT_NOT_FOUND
  /// - FILE_TYPE_NOT_ALLOWED / FILE_TOO_LARGE
  /// - NETWORK_ERROR / TIMEOUT / UNKNOWN
  final String code;

  /// 人类可读的错误消息(可直接展示给用户)。
  final String message;

  /// 后端返回的额外详情(可为 null)。
  final Map<String, dynamic>? details;

  /// HTTP 状态码(网络层错误可能为 null)。
  final int? httpStatus;

  /// 是否为网络/超时类错误(可重试)。
  bool get isRetriable =>
      code == 'NETWORK_ERROR' ||
      code == 'TIMEOUT' ||
      code == 'SERVER_ERROR' ||
      code == 'BAD_GATEWAY';

  @override
  String toString() => 'ApiException($code, $httpStatus): $message';

  /// 从 Dio 异常构造统一 ApiException。
  factory ApiException.fromDio(DioException e) {
    // 网络层错误(无法连接、DNS 失败等)
    if (e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.unknown) {
      return const ApiException(
        code: 'NETWORK_ERROR',
        message: '无法连接到后端服务,请检查网络或切换到演示模式。',
      );
    }
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout) {
      return const ApiException(
        code: 'TIMEOUT',
        message: '后端响应超时,请稍后重试。',
      );
    }
    if (e.type == DioExceptionType.cancel) {
      return const ApiException(
        code: 'CANCELLED',
        message: '请求已取消。',
      );
    }
    // HTTP 错误:尝试解析后端结构化错误
    final resp = e.response;
    if (resp != null) {
      final data = resp.data;
      String code = 'SERVER_ERROR';
      String message = '服务器返回错误 ${resp.statusCode}';
      Map<String, dynamic>? details;
      if (data is Map<String, dynamic>) {
        code = data['code'] as String? ?? code;
        message = data['message'] as String? ?? message;
        details = data['details'] as Map<String, dynamic>?;
      }
      return ApiException(
        code: code,
        message: message,
        details: details,
        httpStatus: resp.statusCode,
      );
    }
    return ApiException(
      code: 'UNKNOWN',
      message: e.message ?? '未知错误',
    );
  }
}

/// Dio 客户端封装 — 统一 BaseUrl / 超时 / 错误转换。
///
/// 所有 ApiXxxService 通过 [ApiClient] 获取 Dio 实例,便于:
/// - 集中管理 BaseUrl(支持 dart-define 注入)
/// - 统一将 DioException 转换为 ApiException
/// - 测试时通过 MockAdapter 替换网络层
class ApiClient {
  ApiClient({
    required String baseUrl,
    Duration connectTimeout = const Duration(seconds: 5),
    Duration receiveTimeout = const Duration(seconds: 30),
    Dio? dio,
  }) : _dio = dio ?? Dio() {
    if (dio == null) {
      _dio.options = BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: connectTimeout,
        receiveTimeout: receiveTimeout,
        headers: {'Accept': 'application/json'},
        responseType: ResponseType.json,
      );
    } else {
      // 测试用注入:仅设置 baseUrl
      _dio.options.baseUrl = baseUrl;
    }
  }

  final Dio _dio;

  Dio get dio => _dio;

  /// 检查后端健康状态。
  Future<Map<String, dynamic>> getHealth() async {
    try {
      final resp = await _dio.get<Map<String, dynamic>>('/api/v1/health');
      return resp.data ?? {};
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
