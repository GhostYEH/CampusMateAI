import 'dart:async';

import 'package:dio/dio.dart';

import '../../../data/models/models.dart';
import '../service_interfaces.dart';
import 'api_client.dart';

/// 真实后端学习会话仓库 — 调用 FastAPI `/api/v1/study/sessions`。
///
/// 后端接口(对齐 backend/app/api/routes/study.py):
/// - POST   /api/v1/study/sessions                 创建会话
/// - GET    /api/v1/study/sessions                 列出当前用户会话
/// - GET    /api/v1/study/sessions/active          获取未结束会话(用于应用重启后恢复)
/// - GET    /api/v1/study/sessions/{id}            会话详情(含休息记录)
/// - POST   /api/v1/study/sessions/{id}/pause      暂停(开启一条休息记录)
/// - POST   /api/v1/study/sessions/{id}/resume     恢复(关闭最近休息记录)
/// - POST   /api/v1/study/sessions/{id}/finish     结束(填写文字感受,关闭所有未结束休息)
/// - PATCH  /api/v1/study/sessions/{id}            部分更新
///
/// **网络失败不伪造保存成功**:所有方法在 DioException 时抛 [ApiException]。
///
/// 状态机校验与用户隔离由后端完成,客户端只消费 JSON。
class ApiStudySessionRepository implements StudySessionRepository {
  ApiStudySessionRepository(this._client);

  final ApiClient _client;

  StudySession? _current;
  final _controller = StreamController<StudySession>.broadcast();

  @override
  StudySession? get current => _current;

  @override
  Stream<StudySession> watchCurrent() => _controller.stream;

  void _emit(StudySession session) {
    _current = session;
    _controller.add(session);
  }

  void _clearCurrent() {
    _current = null;
    // 不向流中添加 null,UI 通过 current==null 判断
  }

  @override
  Future<StudySession> start({
    String? goal,
    String? relatedTaskId,
  }) async {
    final body = <String, dynamic>{};
    if (goal != null && goal.trim().isNotEmpty) {
      body['goal'] = goal.trim();
    }
    if (relatedTaskId != null && relatedTaskId.isNotEmpty) {
      body['related_task_id'] = relatedTaskId;
    }
    final session = await _postSession(
      '/api/v1/study/sessions',
      body: body,
    );
    _emit(session);
    return session;
  }

  @override
  Future<StudySession> pause({String? reason}) async {
    final sid = _requireCurrentId();
    final path = '/api/v1/study/sessions/$sid/pause';
    final query = <String, dynamic>{};
    if (reason != null && reason.trim().isNotEmpty) {
      query['reason'] = reason.trim();
    }
    final session = await _postSession(path, query: query);
    _emit(session);
    return session;
  }

  @override
  Future<StudySession> resume() async {
    final sid = _requireCurrentId();
    final session = await _postSession('/api/v1/study/sessions/$sid/resume');
    _emit(session);
    return session;
  }

  @override
  Future<StudySession> finish({
    String? selfReport,
    List<String>? selfReportTags,
  }) async {
    final sid = _requireCurrentId();
    final body = <String, dynamic>{};
    if (selfReport != null && selfReport.trim().isNotEmpty) {
      body['self_report'] = selfReport.trim();
    }
    if (selfReportTags != null && selfReportTags.isNotEmpty) {
      body['self_report_tags'] = selfReportTags;
    }
    final session = await _postSession(
      '/api/v1/study/sessions/$sid/finish',
      body: body,
    );
    _emit(session);
    _clearCurrent();
    return session;
  }

  @override
  Future<StudySession> updateSession({
    String? goal,
    String? relatedTaskId,
    String? selfReport,
    List<String>? selfReportTags,
    Map<String, dynamic>? expressionSignal,
  }) async {
    final sid = _requireCurrentId();
    final body = <String, dynamic>{};
    if (goal != null) body['goal'] = goal.trim();
    if (relatedTaskId != null) body['related_task_id'] = relatedTaskId;
    if (selfReport != null) body['self_report'] = selfReport.trim();
    if (selfReportTags != null) body['self_report_tags'] = selfReportTags;
    if (expressionSignal != null) body['expression_signal'] = expressionSignal;
    final session = await _patchSession(
      '/api/v1/study/sessions/$sid',
      body: body,
    );
    _emit(session);
    return session;
  }

  @override
  Future<StudySession?> getActiveSession() async {
    try {
      final resp = await _client.dio.get<Map<String, dynamic>>(
        '/api/v1/study/sessions/active',
      );
      // 后端可能返回 null(无未结束会话)
      if (resp.data == null) {
        _clearCurrent();
        return null;
      }
      final session = StudySession.fromJson(resp.data!);
      _emit(session);
      return session;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<StudySession?> getSession(String sessionId) async {
    try {
      final resp = await _client.dio.get<Map<String, dynamic>>(
        '/api/v1/study/sessions/$sessionId',
      );
      if (resp.data == null) return null;
      return StudySession.fromJson(resp.data!);
    } on DioException catch (e) {
      // 404 视为未找到(跨用户访问也会返回 404)
      if (e.response?.statusCode == 404) return null;
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<List<StudySession>> history({int limit = 30}) async {
    try {
      final resp = await _client.dio.get<List<dynamic>>(
        '/api/v1/study/sessions',
        queryParameters: {
          'page': 1,
          'page_size': limit,
        },
      );
      final list = resp.data ?? const [];
      return list
          .whereType<Map<String, dynamic>>()
          .map(StudySession.fromJson)
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<Duration> todayTotal() async {
    // 后端目前未提供"今日总时长"聚合接口,基于 history 计算。
    // 仅统计 completed 状态且 startedAt 为今日的会话。
    try {
      final sessions = await history(limit: 50);
      final now = DateTime.now();
      var total = 0;
      for (final s in sessions) {
        if (s.status != StudySessionStatus.completed) continue;
        final started = s.startedAt;
        if (started.year == now.year &&
            started.month == now.month &&
            started.day == now.day) {
          total += s.durationSeconds;
        }
      }
      return Duration(seconds: total);
    } on ApiException {
      rethrow;
    } catch (_) {
      return Duration.zero;
    }
  }

  // ===== 本地缓存辅助方法(真实后端模式下大多为 no-op)=====

  @override
  List<StudySession> get historySnapshot => const [];

  @override
  Future<void> restoreHistoryFrom(List<StudySession> saved) async {
    // 真实后端模式下数据由后端权威,不需要本地恢复。
  }

  @override
  Future<void> clearHistory() async {
    // 后端目前未提供批量删除会话接口;仅清空本地当前会话缓存。
    _clearCurrent();
  }

  @override
  Future<void> resetToDemo() async {
    // 真实后端模式下不重置(数据由后端权威)。
  }

  // ===== 内部辅助 =====

  String _requireCurrentId() {
    final id = _current?.id;
    if (id == null || id.isEmpty) {
      throw const ApiException(
        code: 'NO_ACTIVE_SESSION',
        message: '当前没有进行中的学习会话',
      );
    }
    return id;
  }

  Future<StudySession> _postSession(
    String path, {
    Map<String, dynamic>? body,
    Map<String, dynamic>? query,
  }) async {
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        path,
        data: body,
        queryParameters: query,
      );
      if (resp.data == null) {
        throw const ApiException(
          code: 'EMPTY_RESPONSE',
          message: '后端返回为空',
        );
      }
      return StudySession.fromJson(resp.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<StudySession> _patchSession(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    try {
      final resp = await _client.dio.patch<Map<String, dynamic>>(
        path,
        data: body,
      );
      if (resp.data == null) {
        throw const ApiException(
          code: 'EMPTY_RESPONSE',
          message: '后端返回为空',
        );
      }
      return StudySession.fromJson(resp.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
