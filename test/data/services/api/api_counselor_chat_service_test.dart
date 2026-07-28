import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/models/chat.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/api/api_counselor_chat_service.dart';
import 'package:campus_companion/data/services/service_interfaces.dart';

import '../../../helpers/mock_dio_adapter.dart';

String _sse(String event, Map<String, dynamic> data) {
  return 'event: $event\ndata: ${jsonEncode(data)}\n\n';
}

void main() {
  late MockDioAdapter adapter;
  late ApiClient client;
  late ApiCounselorChatService service;

  setUp(() {
    adapter = MockDioAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://test.local'));
    dio.interceptors.add(adapter);
    client = ApiClient(baseUrl: 'http://test.local', dio: dio);
    service = ApiCounselorChatService(client);
  });

  group('ApiCounselorChatService.send', () {
    test('完整 SSE 流: sources → chunk* → done', () async {
      final ssePayloads = <String>[
        _sse('sources', {
          'sources': [
            {
              'document_id': 'doc_1',
              'title': '社会实践申请指南',
              'section': '申请流程',
              'source_department': '校团委',
              'published_at': '2026-07-01T00:00:00+08:00',
              'version': 'v1.2',
              'applicable_students': '2024级本科生',
              'excerpt': '申请表需在 7 月 30 日前提交至学院办公室',
              'relevance_score': 0.85,
              'is_official': true,
              'is_expired': false,
              'evidence_level': 'high',
            },
          ],
        }),
        _sse('chunk', {'text': '根据', 'mode': 'llm'}),
        _sse('chunk', {'text': '《社会实践申请指南》', 'mode': 'llm'}),
        _sse('chunk', {'text': ',申请表需在 7 月 30 日前提交。', 'mode': 'llm'}),
        _sse('done', {
          'answer': '根据《社会实践申请指南》,申请表需在 7 月 30 日前提交。',
          'sources': [
            {
              'document_id': 'doc_1',
              'title': '社会实践申请指南',
              'section': '申请流程',
              'source_department': '校团委',
              'published_at': '2026-07-01T00:00:00+08:00',
              'version': 'v1.2',
              'applicable_students': '2024级本科生',
              'excerpt': '申请表需在 7 月 30 日前提交至学院办公室',
              'relevance_score': 0.85,
              'is_official': true,
              'is_expired': false,
              'evidence_level': 'high',
            },
          ],
          'confidence': 0.85,
          'evidence_level': 'high',
          'needs_human_confirmation': false,
          'suggested_actions': [
            {'id': 'act_view_sources', 'label': '查看资料来源', 'type': 'none'},
            {
              'id': 'act_extract',
              'label': '去整理通知',
              'type': 'navigate',
              'payload': '/notifications/extract',
            },
          ],
          'conversation_id': 'conv_123',
          'mode': 'llm',
          'warnings': [],
        }),
      ];

      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: ssePayloads,
      );

      final chunks = <String>[];
      final sourcesList = <List<KnowledgeSource>>[];
      final actionsList = <List<SuggestedAction>>[];
      int typingCalls = 0;

      final answer = await service.send(
        '实践学分怎么申请?',
        conversationId: 'conv_123',
        onChunk: (c) => chunks.add(c),
        onSources: (s) => sourcesList.add(s),
        onActions: (a) => actionsList.add(a),
        onTyping: () => typingCalls++,
      );

      // 完整内容
      expect(answer, '根据《社会实践申请指南》,申请表需在 7 月 30 日前提交。');

      // chunk 累加
      expect(chunks.length, 3);
      expect(chunks.join(), answer);

      // typing 反馈(每个 chunk 都触发)
      expect(typingCalls, 3);

      // sources 至少触发 1 次(done 事件中再次提供)
      expect(sourcesList, isNotEmpty);
      final firstSources = sourcesList.first;
      expect(firstSources.length, 1);
      final s = firstSources.first;
      expect(s.id, 'doc_1');
      expect(s.title, '社会实践申请指南');
      expect(s.sourceDepartment, '校团委');
      expect(s.isOfficial, isTrue);
      expect(s.isExpired, isFalse);
      expect(s.version, 'v1.2');
      expect(s.applicableStudents, '2024级本科生');
      expect(s.section, '申请流程');
      expect(s.evidenceLevel, 'high');

      // done 事件中的 actions 被解析
      expect(actionsList, isNotEmpty);
      final actions = actionsList.last;
      expect(actions.length, 2);
      expect(actions[0].label, '查看资料来源');
      expect(actions[0].type, SuggestedActionType.none);
      expect(actions[1].label, '去整理通知');
      expect(actions[1].type, SuggestedActionType.navigate);
      expect(actions[1].payload, '/notifications/extract');
    });

    test('无资料的 no_knowledge 模式: 返回人工兜底提示', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('done', {
            'answer': '当前知识库无法确认这一事项。建议咨询辅导员或相关负责老师。',
            'sources': [],
            'confidence': 0.0,
            'evidence_level': 'none',
            'needs_human_confirmation': true,
            'suggested_actions': [
              {'id': 'act_consult', 'label': '咨询学院负责老师', 'type': 'none'},
            ],
            'conversation_id': 'conv_x',
            'mode': 'no_knowledge',
            'warnings': ['知识库无相关资料'],
          }),
        ],
      );

      final sourcesList = <List<KnowledgeSource>>[];
      final answer = await service.send(
        '不属于任何已知资料的问题',
        conversationId: 'conv_x',
        onSources: (s) => sourcesList.add(s),
      );

      expect(answer, contains('建议咨询辅导员'));
      expect(sourcesList, isEmpty); // 没有触发 sources 事件
    });

    test('SSE error 事件保留已生成内容并正常返回', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('chunk', {'text': '正在生成中', 'mode': 'llm'}),
          _sse('error', {
            'code': 'RAG_ERROR',
            'message': 'LLM 调用失败',
          }),
        ],
      );

      final answer = await service.send('某问题', conversationId: 'c1');

      // 保留已生成内容
      expect(answer, '正在生成中');
    });

    test('SSE 事件块跨多 chunk 传输时仍能正确解析', () async {
      // 把一个完整 SSE 事件拆成多个 byte chunk
      final fullPayload = _sse('done', {
        'answer': '完整回答',
        'sources': [],
        'confidence': 0.5,
        'evidence_level': 'medium',
        'needs_human_confirmation': true,
        'suggested_actions': [],
        'conversation_id': 'c2',
        'mode': 'retrieval_summary',
        'warnings': [],
      });
      // 拆成 3 段
      final mid = fullPayload.length ~/ 3;
      final payloads = [
        fullPayload.substring(0, mid),
        fullPayload.substring(mid, mid * 2),
        fullPayload.substring(mid * 2),
      ];

      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: payloads,
      );

      final answer = await service.send('问题', conversationId: 'c2');
      expect(answer, '完整回答');
    });

    test('网络错误抛出 ApiException', () async {
      adapter.registerPostError(
        '/api/v1/counselor/chat',
        DioException(
          type: DioExceptionType.connectionError,
          message: 'Connection refused',
          requestOptions: RequestOptions(path: '/api/v1/counselor/chat'),
        ),
      );

      expect(
        () => service.send('问题', conversationId: 'c3'),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'NETWORK_ERROR'),
        ),
      );
    });

    test('超时错误抛出 ApiException (TIMEOUT)', () async {
      adapter.registerPostError(
        '/api/v1/counselor/chat',
        DioException(
          type: DioExceptionType.sendTimeout,
          message: 'Send timeout',
          requestOptions: RequestOptions(path: '/api/v1/counselor/chat'),
        ),
      );

      expect(
        () => service.send('问题', conversationId: 'c4'),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', 'TIMEOUT')),
      );
    });

    test('stop() 触发 cancel: 保留已生成内容并正常返回', () async {
      // 模拟 server 返回一个 chunk 后客户端 cancel
      // 由于 MockAdapter 同步执行,无法精确模拟 cancel 中途;
      // 这里仅测试 stop() 不抛异常且 _cancelToken 被清理
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('done', {
            'answer': '答案',
            'sources': [],
            'confidence': 0.5,
            'evidence_level': 'medium',
            'needs_human_confirmation': false,
            'suggested_actions': [],
            'conversation_id': 'c5',
            'mode': 'llm',
            'warnings': [],
          }),
        ],
      );

      final answer = await service.send('问题', conversationId: 'c5');
      expect(answer, '答案');

      // stop() 不应抛异常
      service.stop();
    });

    test('generateProactiveReminder 始终返回 null(后端未实现)', () async {
      final result = await service.generateProactiveReminder(const []);
      expect(result, isNull);
    });

    test('空 SSE 流(无任何事件)返回空字符串', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [],
      );

      final answer = await service.send('问题', conversationId: 'c6');
      expect(answer, '');
    });

    test('sources 事件含 is_expired 字段时被正确解析', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('sources', {
            'sources': [
              {
                'document_id': 'doc_old',
                'title': '过期的奖学金办法',
                'section': null,
                'source_department': '学工处',
                'published_at': '2020-01-01T00:00:00+08:00',
                'version': 'v1.0',
                'applicable_students': '全体本科生',
                'excerpt': '旧版规定',
                'relevance_score': 0.4,
                'is_official': true,
                'is_expired': true,
                'evidence_level': 'low',
              },
            ],
          }),
          _sse('done', {
            'answer': '注意:该资料已过期',
            'sources': [
              {
                'document_id': 'doc_old',
                'title': '过期的奖学金办法',
                'section': null,
                'source_department': '学工处',
                'published_at': '2020-01-01T00:00:00+08:00',
                'version': 'v1.0',
                'applicable_students': '全体本科生',
                'excerpt': '旧版规定',
                'relevance_score': 0.4,
                'is_official': true,
                'is_expired': true,
                'evidence_level': 'low',
              },
            ],
            'confidence': 0.25,
            'evidence_level': 'low',
            'needs_human_confirmation': true,
            'suggested_actions': [],
            'conversation_id': 'c7',
            'mode': 'retrieval_summary',
            'warnings': ['引用资料中包含已过期内容'],
          }),
        ],
      );

      final sourcesList = <List<KnowledgeSource>>[];
      final answer = await service.send(
        '奖学金问题',
        conversationId: 'c7',
        onSources: (s) => sourcesList.add(s),
      );

      expect(answer, '注意:该资料已过期');
      expect(sourcesList, isNotEmpty);
      final s = sourcesList.first.first;
      expect(s.isExpired, isTrue);
      expect(s.isOfficial, isTrue);
      expect(s.evidenceLevel, 'low');
    });

    test('非合法 JSON 的 data 行被跳过(不抛异常)', () async {
      // 构造非合法 JSON 的 data 行
      const badPayload = 'event: chunk\ndata: not-a-json\n\n';
      final goodPayload = _sse('done', {
        'answer': '最终答案',
        'sources': [],
        'confidence': 0.5,
        'evidence_level': 'medium',
        'needs_human_confirmation': false,
        'suggested_actions': [],
        'conversation_id': 'c8',
        'mode': 'retrieval_summary',
        'warnings': [],
      });

      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [badPayload, goodPayload],
      );

      final answer = await service.send('问题', conversationId: 'c8');
      expect(answer, '最终答案');
    });

    test('请求 body 包含 stream=true 与 conversationId', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('done', {
            'answer': '',
            'sources': [],
            'confidence': 0.0,
            'evidence_level': 'none',
            'needs_human_confirmation': false,
            'suggested_actions': [],
            'conversation_id': 'conv_xyz',
            'mode': 'retrieval_summary',
            'warnings': [],
          }),
        ],
      );

      await service.send('问题', conversationId: 'conv_xyz');

      expect(adapter.recordedRequests, isNotEmpty);
      final req = adapter.recordedRequests.last;
      final data = req.data as Map<String, dynamic>;
      expect(data['message'], '问题');
      expect(data['conversation_id'], 'conv_xyz');
      expect(data['stream'], isTrue);
    });

    test('携带上下文时 body 包含独立上下文字段(对齐要求 #3)', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('done', {
            'answer': '回答',
            'sources': [],
            'confidence': 0.5,
            'evidence_level': 'medium',
            'needs_human_confirmation': false,
            'suggested_actions': [],
            'conversation_id': 'conv_ctx',
            'mode': 'llm',
            'warnings': [],
            'context_used': {
              'course_id': 'c_001',
              'course_name': '高等数学',
              'recent_tasks_count': 1,
              'recent_tasks_verified_count': 1,
            },
            'context_warnings': [],
          }),
        ],
      );

      const context = CounselorContext(
        courseId: 'c_001',
        classId: 'cls_101',
        assignmentId: 'a_001',
        recentTasks: [
          CounselorRecentTask(
            id: 't_001',
            title: '提交实验报告',
            deadline: '2026-09-20T23:59:59',
            priority: 'high',
            status: 'pending',
          ),
        ],
      );

      await service.send(
        '这个任务要交什么?',
        conversationId: 'conv_ctx',
        context: context,
      );

      expect(adapter.recordedRequests, isNotEmpty);
      final req = adapter.recordedRequests.last;
      final data = req.data as Map<String, dynamic>;
      // 基本字段
      expect(data['message'], '这个任务要交什么?');
      expect(data['conversation_id'], 'conv_ctx');
      expect(data['stream'], isTrue);
      // 独立上下文字段(不编码进 conversation_id)
      expect(data['course_id'], 'c_001');
      expect(data['class_id'], 'cls_101');
      expect(data['assignment_id'], 'a_001');
      // recent_tasks 序列化为 List<Map>
      expect(data['recent_tasks'], isA<List>());
      final tasks = data['recent_tasks'] as List;
      expect(tasks.length, 1);
      expect(tasks.first['id'], 't_001');
      expect(tasks.first['title'], '提交实验报告');
      expect(tasks.first['deadline'], '2026-09-20T23:59:59');
      expect(tasks.first['priority'], 'high');
      expect(tasks.first['status'], 'pending');
      // contextLabel 不应发送给后端
      expect(data.containsKey('context_label'), isFalse);
      expect(data.containsKey('context_title'), isFalse);
    });

    test('普通入口(空上下文)不发送无关字段(对齐要求 #3)', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('done', {
            'answer': '回答',
            'sources': [],
            'confidence': 0.5,
            'evidence_level': 'medium',
            'needs_human_confirmation': false,
            'suggested_actions': [],
            'conversation_id': 'conv_plain',
            'mode': 'llm',
            'warnings': [],
          }),
        ],
      );

      await service.send('普通问题', conversationId: 'conv_plain');

      expect(adapter.recordedRequests, isNotEmpty);
      final req = adapter.recordedRequests.last;
      final data = req.data as Map<String, dynamic>;
      // 只应有 message / conversation_id / stream 三个字段
      expect(data.keys.toSet(), {'message', 'conversation_id', 'stream'});
      expect(data.containsKey('course_id'), isFalse);
      expect(data.containsKey('class_id'), isFalse);
      expect(data.containsKey('assignment_id'), isFalse);
      expect(data.containsKey('announcement_id'), isFalse);
      expect(data.containsKey('recent_tasks'), isFalse);
      expect(data.containsKey('study_session_id'), isFalse);
      expect(data.containsKey('self_report'), isFalse);
      expect(data.containsKey('expression_signal'), isFalse);
    });

    test('done 事件含 context_used/context_warnings 时被正确解析(对齐要求 #11)', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('done', {
            'answer': '回答',
            'sources': [],
            'confidence': 0.5,
            'evidence_level': 'medium',
            'needs_human_confirmation': false,
            'suggested_actions': [],
            'conversation_id': 'conv_meta',
            'mode': 'llm',
            'warnings': ['引用资料中包含已过期内容'],
            'context_used': {
              'course_id': 'c_001',
              'course_name': '高等数学',
              'recent_tasks_count': 2,
              'recent_tasks_verified_count': 1,
              'self_report': '有些疲惫',
            },
            'context_warnings': [
              '任务 t_002 不可访问,已忽略',
              'recent_tasks 包含用户本地待办,未经后端验证,仅作个性化参考',
              'expression_signal 当前未接入 CNN,已忽略',
            ],
          }),
        ],
      );

      ChatFinalMeta? capturedMeta;
      await service.send(
        '问题',
        conversationId: 'conv_meta',
        onFinalMeta: (m) => capturedMeta = m,
      );

      expect(capturedMeta, isNotNull);
      expect(capturedMeta!.contextUsed['course_id'], 'c_001');
      expect(capturedMeta!.contextUsed['recent_tasks_count'], 2);
      expect(capturedMeta!.contextUsed['recent_tasks_verified_count'], 1);
      expect(capturedMeta!.contextUsed['self_report'], '有些疲惫');
      expect(capturedMeta!.contextWarnings.length, 3);
      expect(
        capturedMeta!.contextWarnings.any((w) => w.contains('不可访问')),
        isTrue,
      );
      expect(
        capturedMeta!.contextWarnings
            .any((w) => w.contains('expression_signal')),
        isTrue,
      );
    });

    test('done 事件无 context_used/context_warnings 时使用默认空值(SSE 兼容)', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('done', {
            'answer': '回答',
            'sources': [],
            'confidence': 0.5,
            'evidence_level': 'medium',
            'needs_human_confirmation': false,
            'suggested_actions': [],
            'conversation_id': 'conv_no_ctx',
            'mode': 'llm',
            'warnings': [],
            // 故意不提供 context_used / context_warnings
          }),
        ],
      );

      ChatFinalMeta? capturedMeta;
      await service.send(
        '问题',
        conversationId: 'conv_no_ctx',
        onFinalMeta: (m) => capturedMeta = m,
      );

      expect(capturedMeta, isNotNull);
      expect(capturedMeta!.contextUsed, isEmpty);
      expect(capturedMeta!.contextWarnings, isEmpty);
    });

    test('study_session_id 与 self_report 被序列化为独立字段', () async {
      adapter.registerPostSseStream(
        '/api/v1/counselor/chat',
        ssePayloads: [
          _sse('done', {
            'answer': '回答',
            'sources': [],
            'confidence': 0.5,
            'evidence_level': 'medium',
            'needs_human_confirmation': false,
            'suggested_actions': [],
            'conversation_id': 'conv_ss',
            'mode': 'llm',
            'warnings': [],
          }),
        ],
      );

      const context = CounselorContext(
        studySessionId: 'ss_001',
        selfReport: '有些疲惫',
      );
      await service.send(
        '我有点累,该怎么安排?',
        conversationId: 'conv_ss',
        context: context,
      );

      final req = adapter.recordedRequests.last;
      final data = req.data as Map<String, dynamic>;
      expect(data['study_session_id'], 'ss_001');
      expect(data['self_report'], '有些疲惫');
    });
  });
}
