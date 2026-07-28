import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/api/api_study_session_repository.dart';

import '../../../helpers/mock_dio_adapter.dart';

/// 构造一个绑定 MockDioAdapter 的 ApiStudySessionRepository。
(ApiStudySessionRepository, MockDioAdapter) _setupRepo() {
  final adapter = MockDioAdapter();
  final dio = Dio()..interceptors.add(adapter);
  final client = ApiClient(baseUrl: 'http://test.local', dio: dio);
  return (ApiStudySessionRepository(client), adapter);
}

/// 后端返回的标准会话 JSON(对齐 StudySessionOut schema)。
Map<String, dynamic> _sessionJson({
  String id = 'sess_001',
  String status = 'active',
  String goal = '复习高数',
  String? relatedTaskId,
  int durationSeconds = 0,
  int pauseSeconds = 0,
  String? startedAt,
  String? endedAt,
  String? pausedAt,
  String? selfReport,
  List<String> selfReportTags = const [],
  List<Map<String, dynamic>> breaks = const [],
  Map<String, dynamic>? expressionSignal,
}) {
  return {
    'id': id,
    'user_id': 'user_demo',
    'goal': goal,
    'related_task_id': relatedTaskId,
    'started_at': startedAt ?? '2025-01-01T09:00:00+00:00',
    'ended_at': endedAt,
    'paused_at': pausedAt,
    'duration_seconds': durationSeconds,
    'pause_seconds': pauseSeconds,
    'status': status,
    'self_report': selfReport,
    'self_report_tags': selfReportTags,
    'breaks': breaks,
    if (expressionSignal != null) 'expression_signal': expressionSignal,
    'created_at': '2025-01-01T09:00:00+00:00',
    'updated_at': '2025-01-01T09:00:00+00:00',
  };
}

/// 后端返回的休息记录 JSON。
Map<String, dynamic> _breakJson({
  String id = 'brk_001',
  String sessionId = 'sess_001',
  String startedAt = '2025-01-01T09:30:00+00:00',
  String? endedAt,
  String? reason,
}) {
  return {
    'id': id,
    'session_id': sessionId,
    'started_at': startedAt,
    'ended_at': endedAt,
    'reason': reason,
    'created_at': startedAt,
  };
}

void main() {
  group('ApiStudySessionRepository - 创建会话', () {
    test('start 发送 POST /sessions,goal 与 related_task_id 注入 body', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(
          id: 'sess_new',
          goal: '复习数据结构',
          relatedTaskId: 'ptask_001',
        ),
        statusCode: 201,
      );

      final session = await repo.start(
        goal: '复习数据结构',
        relatedTaskId: 'ptask_001',
      );

      // 验证请求 payload
      final recorded = adapter.recordedRequests.last;
      expect(recorded.method, 'POST');
      expect(recorded.path, '/api/v1/study/sessions');
      final body = recorded.data as Map<String, dynamic>;
      expect(body['goal'], '复习数据结构');
      expect(body['related_task_id'], 'ptask_001');
      // user_id 不应出现在 payload(由 JWT 注入)
      expect(body.containsKey('user_id'), isFalse);

      // 验证返回的会话
      expect(session.id, 'sess_new');
      expect(session.status, StudySessionStatus.active);
      expect(session.goalId, '复习数据结构');
      expect(session.taskId, 'ptask_001');
      expect(session.durationSeconds, 0);
      expect(session.pauseSeconds, 0);
    });

    test('start 后会话出现在 current 与 watchCurrent 流中', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_stream'),
        statusCode: 201,
      );

      final emitted = <StudySession>[];
      final sub = repo.watchCurrent().listen(emitted.add);

      expect(repo.current, isNull);
      await repo.start(goal: '测试');
      await Future.delayed(const Duration(milliseconds: 10));

      expect(repo.current, isNotNull);
      expect(repo.current!.id, 'sess_stream');
      expect(emitted, isNotEmpty);
      expect(emitted.last.id, 'sess_stream');
      await sub.cancel();
    });

    test('start 时空白 goal 不发送到 body', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(goal: '', relatedTaskId: null),
        statusCode: 201,
      );

      await repo.start(goal: '   ', relatedTaskId: null);

      final body = adapter.recordedRequests.last.data as Map<String, dynamic>;
      // 空白应被过滤
      expect(body.containsKey('goal'), isFalse);
      expect(body.containsKey('related_task_id'), isFalse);
    });
  });

  group('ApiStudySessionRepository - 状态机', () {
    test('pause 发送 POST /sessions/{id}/pause', () async {
      final (repo, adapter) = _setupRepo();
      // 先创建
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_p1'),
        statusCode: 201,
      );
      await repo.start(goal: '测试');
      // 暂停
      adapter.registerPost(
        '/api/v1/study/sessions/sess_p1/pause',
        data: _sessionJson(
          id: 'sess_p1',
          status: 'paused',
          pausedAt: '2025-01-01T09:30:00+00:00',
          breaks: [
            _breakJson(endedAt: null, reason: null),
          ],
        ),
      );

      final paused = await repo.pause();
      expect(paused.status, StudySessionStatus.paused);
      expect(paused.pausedAt, isNotNull);
      expect(paused.breaks.length, 1);
      expect(paused.breaks.first.isOpen, isTrue);
    });

    test('pause 带 reason 时附加到 query 参数', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_p2'),
        statusCode: 201,
      );
      await repo.start(goal: '测试');
      adapter.registerPost(
        '/api/v1/study/sessions/sess_p2/pause',
        data: _sessionJson(
          id: 'sess_p2',
          status: 'paused',
          breaks: [
            _breakJson(reason: '喝水'),
          ],
        ),
      );

      await repo.pause(reason: '喝水');
      final recorded = adapter.recordedRequests.last;
      expect(recorded.path, '/api/v1/study/sessions/sess_p2/pause');
      // reason 应通过 queryParameters 传递
      expect(recorded.queryParameters['reason'], '喝水');
    });

    test('resume 发送 POST /sessions/{id}/resume 并关闭休息记录', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_r1'),
        statusCode: 201,
      );
      await repo.start(goal: '测试');
      // 暂停后恢复
      adapter.registerPost(
        '/api/v1/study/sessions/sess_r1/resume',
        data: _sessionJson(
          id: 'sess_r1',
          status: 'active',
          pausedAt: null,
          pauseSeconds: 120,
          breaks: [
            _breakJson(endedAt: '2025-01-01T09:32:00+00:00', reason: '喝水'),
          ],
        ),
      );

      final resumed = await repo.resume();
      expect(resumed.status, StudySessionStatus.active);
      expect(resumed.pauseSeconds, 120);
      expect(resumed.breaks.first.isOpen, isFalse);
    });

    test('finish 发送 POST /sessions/{id}/finish 含 self_report', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_f1'),
        statusCode: 201,
      );
      await repo.start(goal: '测试');
      adapter.registerPost(
        '/api/v1/study/sessions/sess_f1/finish',
        data: _sessionJson(
          id: 'sess_f1',
          status: 'completed',
          durationSeconds: 1800,
          endedAt: '2025-01-01T09:30:00+00:00',
          selfReport: '今天很专注',
          selfReportTags: ['专注', '有收获'],
        ),
      );

      final finished = await repo.finish(
        selfReport: '今天很专注',
        selfReportTags: ['专注', '有收获'],
      );
      expect(finished.status, StudySessionStatus.completed);
      expect(finished.endedAt, isNotNull);
      expect(finished.durationSeconds, 1800);
      expect(finished.selfReport, '今天很专注');
      expect(finished.selfReportTags, ['专注', '有收获']);

      // 验证请求 body
      final body = adapter.recordedRequests.last.data as Map<String, dynamic>;
      expect(body['self_report'], '今天很专注');
      expect(body['self_report_tags'], ['专注', '有收获']);

      // 结束后 current 被清空
      expect(repo.current, isNull);
    });

    test('无 active 会话时 pause/resume/finish 抛 NO_ACTIVE_SESSION', () async {
      final (repo, _) = _setupRepo();
      expect(
        () => repo.pause(),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == 'NO_ACTIVE_SESSION',
          ),
        ),
      );
      expect(
        () => repo.resume(),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == 'NO_ACTIVE_SESSION',
          ),
        ),
      );
      expect(
        () => repo.finish(),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == 'NO_ACTIVE_SESSION',
          ),
        ),
      );
    });
  });

  group('ApiStudySessionRepository - 更新会话', () {
    test('updateSession 发送 PATCH /sessions/{id}', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_u1'),
        statusCode: 201,
      );
      await repo.start(goal: '原目标');

      adapter.registerPatch(
        '/api/v1/study/sessions/sess_u1',
        data: _sessionJson(
          id: 'sess_u1',
          goal: '新目标',
          selfReport: '中途记录',
          selfReportTags: ['专注'],
        ),
      );

      final updated = await repo.updateSession(
        goal: '新目标',
        selfReport: '中途记录',
        selfReportTags: ['专注'],
      );
      expect(updated.goalId, '新目标');
      expect(updated.selfReport, '中途记录');
      expect(updated.selfReportTags, ['专注']);

      final body = adapter.recordedRequests.last.data as Map<String, dynamic>;
      expect(body['goal'], '新目标');
      expect(body['self_report'], '中途记录');
      expect(body['self_report_tags'], ['专注']);
    });

    test('updateSession 可透传 expression_signal(CNN 预留字段)', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_e1'),
        statusCode: 201,
      );
      await repo.start(goal: '测试');

      final signal = {
        'label': 'neutral',
        'confidence': 0.82,
        'frames': 30,
      };
      adapter.registerPatch(
        '/api/v1/study/sessions/sess_e1',
        data: _sessionJson(
          id: 'sess_e1',
          expressionSignal: signal,
        ),
      );

      final updated = await repo.updateSession(expressionSignal: signal);
      expect(updated.expressionSignal, isNotNull);
      expect(updated.expressionSignal!['label'], 'neutral');
      expect(updated.expressionSignal!['confidence'], 0.82);

      final body = adapter.recordedRequests.last.data as Map<String, dynamic>;
      expect(body['expression_signal'], signal);
    });
  });

  group('ApiStudySessionRepository - 会话恢复', () {
    test('getActiveSession 返回当前未结束会话', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGet(
        '/api/v1/study/sessions/active',
        data: _sessionJson(
          id: 'sess_active',
          status: 'active',
          goal: '恢复的会话',
        ),
      );

      final active = await repo.getActiveSession();
      expect(active, isNotNull);
      expect(active!.id, 'sess_active');
      expect(active.status, StudySessionStatus.active);
      expect(active.goalId, '恢复的会话');
      // 应填充到 current
      expect(repo.current?.id, 'sess_active');
    });

    test('getActiveSession 后端返回 null 时返回 null(无未结束会话)', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGet(
        '/api/v1/study/sessions/active',
        data: null,
      );

      final active = await repo.getActiveSession();
      expect(active, isNull);
      expect(repo.current, isNull);
    });

    test('getActiveSession 网络失败时抛 ApiException(不伪造恢复成功)', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGetError(
        '/api/v1/study/sessions/active',
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/study/sessions/active'),
          type: DioExceptionType.connectionTimeout,
        ),
      );

      expect(
        () => repo.getActiveSession(),
        throwsA(isA<ApiException>()),
      );
      // 失败时 current 不应被填充
      expect(repo.current, isNull);
    });
  });

  group('ApiStudySessionRepository - 详情与历史', () {
    test('getSession 返回会话详情含休息记录', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGet(
        '/api/v1/study/sessions/sess_detail',
        data: _sessionJson(
          id: 'sess_detail',
          status: 'paused',
          breaks: [
            _breakJson(id: 'brk_1', reason: '喝水'),
            _breakJson(id: 'brk_2', reason: '上厕所'),
          ],
        ),
      );

      final session = await repo.getSession('sess_detail');
      expect(session, isNotNull);
      expect(session!.breaks.length, 2);
      expect(session.breaks[0].reason, '喝水');
      expect(session.breaks[1].reason, '上厕所');
    });

    test('getSession 404 返回 null(跨用户访问也返回 404)', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGet(
        '/api/v1/study/sessions/sess_other_user',
        data: {'code': 'STUDY_SESSION_NOT_FOUND', 'message': '会话不存在'},
        statusCode: 404,
      );

      final session = await repo.getSession('sess_other_user');
      expect(session, isNull);
    });

    test('history 解析列表响应', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGet(
        '/api/v1/study/sessions',
        data: [
          _sessionJson(id: 'sess_h1', status: 'completed'),
          _sessionJson(id: 'sess_h2', status: 'completed'),
        ],
      );

      final list = await repo.history(limit: 30);
      expect(list.length, 2);
      expect(list[0].id, 'sess_h1');
      expect(list[1].id, 'sess_h2');
    });

    test('history 网络失败时抛 ApiException', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGetError(
        '/api/v1/study/sessions',
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/study/sessions'),
          type: DioExceptionType.connectionError,
        ),
      );

      expect(
        () => repo.history(),
        throwsA(isA<ApiException>()),
      );
    });
  });

  group('ApiStudySessionRepository - todayTotal 派生计算', () {
    test('仅累计今日已结束会话的 duration_seconds', () async {
      final (repo, adapter) = _setupRepo();
      final now = DateTime.now();
      final todayIso =
          DateTime(now.year, now.month, now.day, 9, 0).toIso8601String();
      final yesterdayIso =
          DateTime(now.year, now.month, now.day - 1, 9, 0).toIso8601String();

      adapter.registerGet(
        '/api/v1/study/sessions',
        data: [
          _sessionJson(
            id: 'today_1',
            status: 'completed',
            startedAt: todayIso,
            durationSeconds: 1800,
          ),
          _sessionJson(
            id: 'today_2',
            status: 'completed',
            startedAt: todayIso,
            durationSeconds: 900,
          ),
          // 昨日不应计入
          _sessionJson(
            id: 'yesterday',
            status: 'completed',
            startedAt: yesterdayIso,
            durationSeconds: 3600,
          ),
          // active 不应计入
          _sessionJson(
            id: 'active',
            status: 'active',
            startedAt: todayIso,
            durationSeconds: 600,
          ),
        ],
      );

      final total = await repo.todayTotal();
      expect(total.inSeconds, 2700); // 1800 + 900
    });

    test('history 失败时 todayTotal 抛 ApiException', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGetError(
        '/api/v1/study/sessions',
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/study/sessions'),
          type: DioExceptionType.connectionError,
        ),
      );

      expect(
        () => repo.todayTotal(),
        throwsA(isA<ApiException>()),
      );
    });
  });

  group('ApiStudySessionRepository - 网络失败不伪造成功', () {
    test('start 网络错误时抛 ApiException 且不更新 current', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPostError(
        '/api/v1/study/sessions',
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/study/sessions'),
          type: DioExceptionType.connectionTimeout,
        ),
      );

      expect(
        () => repo.start(goal: '测试'),
        throwsA(isA<ApiException>()),
      );
      // 失败时 current 不应被更新
      expect(repo.current, isNull);
    });

    test('start 后端返回 500 时抛 ApiException', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: {'code': 'SERVER_ERROR', 'message': '后端内部错误'},
        statusCode: 500,
      );

      expect(
        () => repo.start(goal: '测试'),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == 'SERVER_ERROR',
          ),
        ),
      );
      expect(repo.current, isNull);
    });

    test('pause 后端返回 409 INVALID_TRANSITION 时抛 ApiException', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_409'),
        statusCode: 201,
      );
      await repo.start(goal: '测试');
      // 已结束会话再次 pause → 409
      adapter.registerPost(
        '/api/v1/study/sessions/sess_409/pause',
        data: {
          'code': 'INVALID_TRANSITION',
          'message': '已结束会话不能暂停',
        },
        statusCode: 409,
      );

      expect(
        () => repo.pause(),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == 'INVALID_TRANSITION',
          ),
        ),
      );
    });

    test('finish 后端返回 422 VALIDATION_FAILED 时抛 ApiException', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_422'),
        statusCode: 201,
      );
      await repo.start(goal: '测试');
      adapter.registerPost(
        '/api/v1/study/sessions/sess_422/finish',
        data: {
          'code': 'VALIDATION_FAILED',
          'message': 'self_report 不能为空白',
        },
        statusCode: 422,
      );

      expect(
        () => repo.finish(selfReport: '   '),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == 'VALIDATION_FAILED',
          ),
        ),
      );
      // 失败时 current 仍保留(会话未结束)
      expect(repo.current, isNotNull);
    });
  });

  group('ApiStudySessionRepository - 本地缓存 no-op 行为', () {
    test('historySnapshot 真实后端模式返回空列表', () async {
      final (repo, _) = _setupRepo();
      expect(repo.historySnapshot, isEmpty);
    });

    test('restoreHistoryFrom 真实后端模式为 no-op', () async {
      final (repo, _) = _setupRepo();
      // 不应抛异常
      await repo.restoreHistoryFrom(const []);
    });

    test('clearHistory 仅清空本地 current 缓存', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/study/sessions',
        data: _sessionJson(id: 'sess_clear'),
        statusCode: 201,
      );
      await repo.start(goal: '测试');
      expect(repo.current, isNotNull);

      await repo.clearHistory();
      expect(repo.current, isNull);
    });

    test('resetToDemo 真实后端模式为 no-op', () async {
      final (repo, _) = _setupRepo();
      await repo.resetToDemo();
    });
  });

  group('ApiStudySessionRepository - JSON 解析', () {
    test('StudySession.fromJson 兼容 snake_case 字段', () {
      final json = _sessionJson(
        id: 'sess_parse',
        status: 'paused',
        relatedTaskId: 'ptask_001',
        pausedAt: '2025-01-01T09:30:00+00:00',
        pauseSeconds: 120,
        selfReport: '测试感受',
        selfReportTags: ['专注'],
      );
      final session = StudySession.fromJson(json);
      expect(session.id, 'sess_parse');
      expect(session.status, StudySessionStatus.paused);
      expect(session.taskId, 'ptask_001');
      expect(session.pausedAt, isNotNull);
      expect(session.pauseSeconds, 120);
      expect(session.selfReport, '测试感受');
      expect(session.selfReportTags, ['专注']);
    });

    test('StudySession.fromJson 解析休息记录', () {
      final json = _sessionJson(
        breaks: [
          _breakJson(
            id: 'b1',
            reason: '喝水',
            endedAt: '2025-01-01T09:32:00+00:00',
          ),
          _breakJson(id: 'b2', reason: null, endedAt: null),
        ],
      );
      final session = StudySession.fromJson(json);
      expect(session.breaks.length, 2);
      expect(session.breaks[0].isOpen, isFalse);
      expect(session.breaks[0].reason, '喝水');
      expect(session.breaks[1].isOpen, isTrue);
      expect(session.breaks[1].reason, isNull);
    });

    test('StudySession.fromJson 解析 expression_signal(预留 CNN 字段)', () {
      final signal = {'label': 'neutral', 'confidence': 0.85, 'frames': 30};
      final json = _sessionJson(expressionSignal: signal);
      final session = StudySession.fromJson(json);
      expect(session.expressionSignal, isNotNull);
      expect(session.expressionSignal!['label'], 'neutral');
      expect(session.expressionSignal!['confidence'], 0.85);
    });
  });
}
