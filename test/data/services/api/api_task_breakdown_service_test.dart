import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/api/api_task_breakdown_service.dart';

import '../../../helpers/mock_dio_adapter.dart';

/// 构造绑定 Mock 适配器的 ApiTaskBreakdownService。
(ApiTaskBreakdownService, MockDioAdapter) _setupService() {
  final adapter = MockDioAdapter();
  final dio = Dio()..interceptors.add(adapter);
  final client = ApiClient(baseUrl: 'http://test.local', dio: dio);
  return (ApiTaskBreakdownService(client), adapter);
}

/// 构造一个标准的拆解响应 JSON。
Map<String, dynamic> _breakdownResponseJson({
  String mode = 'rule_fallback',
  String goal = '复习高数',
  String? relatedTaskId,
  String? relatedTaskTitle,
  List<String> warnings = const ['未配置 LLM 或 LLM 不可用,使用规则拆解'],
  List<Map<String, dynamic>>? steps,
}) {
  return {
    'mode': mode,
    'goal': goal,
    'related_task_id': relatedTaskId,
    'related_task_title': relatedTaskTitle,
    'warnings': warnings,
    'steps': steps ??
        [
          {
            'step_number': 1,
            'title': '明确目标与范围',
            'description': '梳理本次学习要覆盖的章节与知识点',
            'estimated_minutes': 15,
            'dependencies': <int>[],
            'completion_criteria': '已列出要复习的章节列表',
            'is_policy_step': false,
            'knowledge_source': null,
          },
          {
            'step_number': 2,
            'title': '通读教材',
            'description': '快速浏览相关章节,标注疑问点',
            'estimated_minutes': 45,
            'dependencies': [1],
            'completion_criteria': '已通读并标注至少 3 个疑问点',
            'is_policy_step': false,
            'knowledge_source': null,
          },
          {
            'step_number': 3,
            'title': '做题巩固',
            'description': '完成课后习题 5 道',
            'estimated_minutes': 60,
            'dependencies': [2],
            'completion_criteria': '已完成 5 道习题并核对答案',
            'is_policy_step': false,
            'knowledge_source': null,
          },
        ],
  };
}

void main() {
  group('ApiTaskBreakdownService - 自由目标拆解', () {
    test('breakdown 发送 POST /task-breakdown,goal 注入 body', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: _breakdownResponseJson(goal: '复习数据结构链表'),
      );

      final resp = await service.breakdown(
        const TaskBreakdownRequest(goal: '复习数据结构链表'),
      );

      // 验证请求 payload
      final recorded = adapter.recordedRequests.last;
      expect(recorded.method, 'POST');
      expect(recorded.path, '/api/v1/study/task-breakdown');
      final body = recorded.data as Map<String, dynamic>;
      expect(body['goal'], '复习数据结构链表');
      expect(body.containsKey('task_id'), isFalse);

      // 验证响应解析
      expect(resp.mode, TaskBreakdownMode.ruleFallback);
      expect(resp.goal, '复习数据结构链表');
      expect(resp.steps.length, 3);
      expect(resp.steps[0].stepNumber, 1);
      expect(resp.steps[0].title, '明确目标与范围');
      expect(resp.steps[0].estimatedMinutes, 15);
      expect(resp.steps[0].dependencies, isEmpty);
      expect(resp.steps[1].dependencies, [1]);
      expect(resp.steps[2].dependencies, [2]);
      expect(resp.relatedTaskId, isNull);
      expect(resp.relatedTaskTitle, isNull);
      expect(resp.warnings, isNotEmpty);
    });

    test('breakdown 空请求抛 VALIDATION_FAILED(不发送到后端)', () async {
      final (service, _) = _setupService();
      expect(
        () => service.breakdown(const TaskBreakdownRequest()),
        throwsA(predicate(
            (e) => e is ApiException && e.code == 'VALIDATION_FAILED',),),
      );
    });
  });

  group('ApiTaskBreakdownService - 个人任务拆解', () {
    test('task_id 注入 body,响应填充 related_task_id 与 related_task_title',
        () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: _breakdownResponseJson(
          goal: '完成高数作业',
          relatedTaskId: 'ptask_001',
          relatedTaskTitle: '完成高数作业',
        ),
      );

      final resp = await service.breakdown(
        const TaskBreakdownRequest(taskId: 'ptask_001'),
      );

      // 验证请求 payload
      final body = adapter.recordedRequests.last.data as Map<String, dynamic>;
      expect(body['task_id'], 'ptask_001');

      // 验证响应解析
      expect(resp.relatedTaskId, 'ptask_001');
      expect(resp.relatedTaskTitle, '完成高数作业');
      expect(resp.goal, '完成高数作业');
    });

    test('task_id 与 goal 同时提供时,后端优先解析 task_id', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: _breakdownResponseJson(
          goal: '完成高数作业\n任务说明: 第三章习题',
          relatedTaskId: 'ptask_002',
          relatedTaskTitle: '完成高数作业',
        ),
      );

      final resp = await service.breakdown(
        const TaskBreakdownRequest(taskId: 'ptask_002', goal: '完成高数作业'),
      );

      final body = adapter.recordedRequests.last.data as Map<String, dynamic>;
      expect(body['task_id'], 'ptask_002');
      expect(body['goal'], '完成高数作业');
      expect(resp.relatedTaskId, 'ptask_002');
    });
  });

  group('ApiTaskBreakdownService - mode 标注', () {
    test('rule_fallback 模式正确解析', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: _breakdownResponseJson(mode: 'rule_fallback'),
      );

      final resp = await service.breakdown(
        const TaskBreakdownRequest(goal: '测试规则降级'),
      );
      expect(resp.mode, TaskBreakdownMode.ruleFallback);
    });

    test('llm 模式正确解析', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: _breakdownResponseJson(
          mode: 'llm',
          warnings: const [],
          steps: [
            {
              'step_number': 1,
              'title': 'LLM 生成的步骤',
              'description': '由 LLM 生成',
              'estimated_minutes': 20,
              'dependencies': <int>[],
              'completion_criteria': '已确认',
              'is_policy_step': false,
              'knowledge_source': null,
            },
          ],
        ),
      );

      final resp = await service.breakdown(
        const TaskBreakdownRequest(goal: '测试 LLM 模式'),
      );
      expect(resp.mode, TaskBreakdownMode.llm);
      expect(resp.steps.length, 1);
      expect(resp.steps[0].title, 'LLM 生成的步骤');
      expect(resp.warnings, isEmpty);
    });

    test('未知 mode 字段降级为 rule_fallback', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: _breakdownResponseJson(mode: 'unknown_mode'),
      );

      final resp = await service.breakdown(
        const TaskBreakdownRequest(goal: '测试未知 mode'),
      );
      expect(resp.mode, TaskBreakdownMode.ruleFallback);
    });
  });

  group('ApiTaskBreakdownService - 政策步骤与知识库', () {
    test('is_policy_step=true 且 knowledge_source 非空时正确解析', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: _breakdownResponseJson(
          goal: '申请奖学金,准备材料',
          steps: [
            {
              'step_number': 1,
              'title': '查询奖学金政策',
              'description': '查阅学校奖学金申请办法',
              'estimated_minutes': 15,
              'dependencies': <int>[],
              'completion_criteria': '已阅读相关政策文档',
              'is_policy_step': true,
              'knowledge_source': '《XX大学奖学金管理办法》',
            },
            {
              'step_number': 2,
              'title': '准备申请材料',
              'description': '收集成绩单、获奖证书',
              'estimated_minutes': 60,
              'dependencies': [1],
              'completion_criteria': '已准备齐全申请材料',
              'is_policy_step': true,
              'knowledge_source': '《XX大学奖学金管理办法》',
            },
            {
              'step_number': 3,
              'title': '提交申请',
              'description': '在系统内提交申请表',
              'estimated_minutes': 20,
              'dependencies': [2],
              'completion_criteria': '已成功提交申请',
              'is_policy_step': false,
              'knowledge_source': null,
            },
          ],
        ),
      );

      final resp = await service.breakdown(
        const TaskBreakdownRequest(goal: '申请奖学金,准备材料'),
      );
      expect(resp.steps.length, 3);
      expect(resp.steps[0].isPolicyStep, isTrue);
      expect(resp.steps[0].knowledgeSource, '《XX大学奖学金管理办法》');
      expect(resp.steps[1].isPolicyStep, isTrue);
      expect(resp.steps[2].isPolicyStep, isFalse);
      expect(resp.steps[2].knowledgeSource, isNull);
    });

    test('总预计分钟数计算正确', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: _breakdownResponseJson(),
      );

      final resp = await service.breakdown(
        const TaskBreakdownRequest(goal: '测试'),
      );
      // 默认 steps: 15 + 45 + 60 = 120
      expect(resp.totalEstimatedMinutes, 120);
    });
  });

  group('ApiTaskBreakdownService - 错误传播', () {
    test('后端返回 401 UNAUTHORIZED 时抛 ApiException', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: {'code': 'UNAUTHORIZED', 'message': '未认证'},
        statusCode: 401,
      );

      expect(
        () => service.breakdown(const TaskBreakdownRequest(goal: '测试')),
        throwsA(predicate(
            (e) => e is ApiException && e.code == 'UNAUTHORIZED',),),
      );
    });

    test('后端返回 422 VALIDATION_FAILED 时抛 ApiException', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: {'code': 'VALIDATION_FAILED', 'message': 'task_id 与 goal 不能同时为空'},
        statusCode: 422,
      );

      expect(
        () => service.breakdown(const TaskBreakdownRequest(goal: '测试')),
        throwsA(predicate(
            (e) => e is ApiException && e.code == 'VALIDATION_FAILED',),),
      );
    });

    test('后端返回 500 时抛 ApiException', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: {'code': 'INTERNAL_ERROR', 'message': '服务器内部错误'},
        statusCode: 500,
      );

      expect(
        () => service.breakdown(const TaskBreakdownRequest(goal: '测试')),
        throwsA(predicate(
            (e) => e is ApiException && e.code == 'INTERNAL_ERROR',),),
      );
    });

    test('网络超时抛 ApiException', () async {
      final (service, adapter) = _setupService();
      adapter.registerPostError(
        '/api/v1/study/task-breakdown',
        DioException(
          requestOptions:
              RequestOptions(path: '/api/v1/study/task-breakdown'),
          type: DioExceptionType.connectionTimeout,
        ),
      );

      expect(
        () => service.breakdown(const TaskBreakdownRequest(goal: '测试')),
        throwsA(isA<ApiException>()),
      );
    });

    test('后端返回空 body 抛 EMPTY_RESPONSE', () async {
      final (service, adapter) = _setupService();
      adapter.registerPost(
        '/api/v1/study/task-breakdown',
        data: null,
      );

      expect(
        () => service.breakdown(const TaskBreakdownRequest(goal: '测试')),
        throwsA(predicate(
            (e) => e is ApiException && e.code == 'EMPTY_RESPONSE',),),
      );
    });
  });
}
