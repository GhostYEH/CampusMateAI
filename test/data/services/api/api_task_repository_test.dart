import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/api/api_task_repository.dart';

import '../../../helpers/mock_dio_adapter.dart';

/// 构造一个绑定 MockDioAdapter 的 ApiTaskRepository。
(ApiTaskRepository, MockDioAdapter) _setupRepo() {
  final adapter = MockDioAdapter();
  final dio = Dio()..interceptors.add(adapter);
  final client = ApiClient(baseUrl: 'http://test.local', dio: dio);
  return (ApiTaskRepository(client), adapter);
}

/// 构造一个待创建的 Task(模拟通知抽取后用户确认保存)。
Task _newTask({
  String id = 'task_local_1',
  String title = '提交实践申请',
  String? sourceText = '关于 2024 年暑期实践申请的通知',
  DateTime? deadline,
  int? reminderMinutes,
  bool reminderEnabled = false,
}) {
  final dl = deadline ?? DateTime(2099, 12, 31, 23, 59);
  DateTime? reminderAt;
  if (reminderEnabled && reminderMinutes != null) {
    reminderAt = dl.subtract(Duration(minutes: reminderMinutes));
  }
  return Task(
    id: id,
    title: title,
    category: TaskCategory.material,
    priority: TaskPriority.high,
    createdAt: DateTime(2025, 1, 1),
    source: TaskSource.noticeExtraction,
    deadline: dl,
    materials: const [
      TaskMaterial(id: 'm1', name: '申请表'),
      TaskMaterial(id: 'm2', name: '证明材料'),
    ],
    sourceText: sourceText,
    sourceName: '教务处',
    targetStudents: '2024级各班',
    submissionMethod: '线上提交',
    reminderEnabled: reminderEnabled,
    reminderAt: reminderAt,
    reminderMinutes: reminderMinutes,
  );
}

/// 后端返回的标准任务 JSON(对齐 PersonalTaskOut schema)。
Map<String, dynamic> _backendTaskJson({
  String id = 'ptask_abc123',
  String title = '提交实践申请',
  String status = 'pending',
  String priority = 'high',
  String? deadline = '2099-12-31T23:59:00+00:00',
  List<String> materials = const ['申请表', '证明材料'],
  String? sourceText = '关于 2024 年暑期实践申请的通知',
  String? sourceName = '教务处',
  int? reminderMinutes,
  String? completedAt,
  String? deletedAt,
}) {
  return {
    'id': id,
    'user_id': 'user_demo',
    'title': title,
    'description': null,
    'target_students': '2024级各班',
    'deadline': deadline,
    'materials': materials,
    'submission_method': '线上提交',
    'location': '教务处',
    'source_name': sourceName,
    'source_text': sourceText,
    'source_notice_id': null,
    'priority': priority,
    'status': status,
    'reminder_minutes': reminderMinutes,
    'created_at': '2025-01-01T00:00:00+00:00',
    'updated_at': '2025-01-01T00:00:00+00:00',
    'completed_at': completedAt,
    'deleted_at': deletedAt,
  };
}

void main() {
  group('ApiTaskRepository - 序列化', () {
    test('createTask 发送正确 payload 到 POST /tasks', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_new1'),
        statusCode: 201,
      );

      final task = _newTask(
        title: '提交实践申请',
        reminderMinutes: 120,
        reminderEnabled: true,
      );
      final created = await repo.createTask(task);

      // 验证请求 payload
      final recorded = adapter.recordedRequests.last;
      expect(recorded.method, 'POST');
      expect(recorded.path, '/api/v1/tasks');
      final body = recorded.data as Map<String, dynamic>;
      expect(body['title'], '提交实践申请');
      expect(body['source_text'], '关于 2024 年暑期实践申请的通知');
      expect(body['source_name'], '教务处');
      expect(body['target_students'], '2024级各班');
      expect(body['submission_method'], '线上提交');
      expect(body['priority'], 'high');
      expect(body['materials'], ['申请表', '证明材料']);
      // reminder_minutes 应从 reminderAt 与 deadline 反推
      expect(body['reminder_minutes'], 120);
      // user_id 不应出现在 payload(由 JWT 注入)
      expect(body.containsKey('user_id'), isFalse);

      // 验证返回的 Task 用后端 id 替换本地临时 id
      expect(created.id, 'ptask_new1');
      expect(created.title, '提交实践申请');
      expect(created.sourceText, '关于 2024 年暑期实践申请的通知');
    });

    test('refresh 解析后端列表响应并刷新缓存', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGet('/api/v1/tasks', data: {
        'items': [
          _backendTaskJson(id: 'ptask_1', title: '任务A'),
          _backendTaskJson(id: 'ptask_2', title: '任务B', status: 'completed'),
          _backendTaskJson(id: 'ptask_3', title: '任务C', status: 'deleted'),
        ],
        'total': 3,
        'page': 1,
        'page_size': 200,
      },);

      await repo.refresh();
      // deleted 状态的任务不在 tasks 中(被过滤)
      expect(repo.tasks.length, 2);
      expect(repo.tasks.any((t) => t.id == 'ptask_1'), isTrue);
      expect(repo.tasks.any((t) => t.id == 'ptask_2'), isTrue);
      expect(repo.tasks.any((t) => t.id == 'ptask_3'), isFalse);
      // 但 snapshot 保留全部(含已删除)
      expect(repo.snapshot.length, 3);
    });

    test('reminder_minutes 与 reminderAt 互相转换', () async {
      final (repo, adapter) = _setupRepo();
      final deadline = DateTime(2099, 12, 31, 23, 59);
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(
          id: 'ptask_reminder',
          deadline: deadline.toIso8601String(),
          reminderMinutes: 90,
        ),
        statusCode: 201,
      );

      // 创建时 reminderMinutes=90, reminderAt = deadline - 90min
      final task = _newTask(
        deadline: deadline,
        reminderMinutes: 90,
        reminderEnabled: true,
      );
      final created = await repo.createTask(task);

      // 后端返回的 reminder_minutes=90,应反推 reminderAt = deadline - 90min
      expect(created.reminderMinutes, 90);
      expect(created.reminderEnabled, isTrue);
      expect(created.reminderAt, deadline.subtract(const Duration(minutes: 90)));
    });
  });

  group('ApiTaskRepository - 通知确认后创建任务', () {
    test('source_text 必须发送到后端(原文追溯)', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(
          id: 'ptask_src',
          sourceText: '原文内容用于追溯',
        ),
        statusCode: 201,
      );

      final task = _newTask(sourceText: '原文内容用于追溯');
      await repo.createTask(task);

      final body = adapter.recordedRequests.last.data as Map<String, dynamic>;
      expect(body['source_text'], '原文内容用于追溯');
    });

    test('createTask 后任务出现在缓存与 watchTasks 流中', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_stream'),
        statusCode: 201,
      );

      final emitted = <List<Task>>[];
      final sub = repo.watchTasks().listen(emitted.add);

      expect(repo.tasks, isEmpty);
      await repo.createTask(_newTask());
      await Future.delayed(const Duration(milliseconds: 10));

      expect(repo.tasks.length, 1);
      expect(repo.tasks.first.id, 'ptask_stream');
      expect(emitted, isNotEmpty);
      expect(emitted.last.any((t) => t.id == 'ptask_stream'), isTrue);
      await sub.cancel();
    });
  });

  group('ApiTaskRepository - 修改 / 完成 / 删除 / 恢复', () {
    test('updateTask 发送 PATCH 并更新缓存', () async {
      final (repo, adapter) = _setupRepo();
      // 先创建一个任务
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_upd', title: '原标题'),
        statusCode: 201,
      );
      final created = await repo.createTask(_newTask());
      expect(created.title, '原标题');

      // 注册 PATCH 路由(支持任意 task_id)
      adapter.registerPatch(
        '/api/v1/tasks/ptask_upd',
        data: _backendTaskJson(id: 'ptask_upd', title: '新标题', priority: 'low'),
      );
      await repo.updateTask(
        created.copyWith(title: '新标题', priority: TaskPriority.low),
      );
      // 从缓存读取更新后的任务
      final updated = repo.tasks.firstWhere((t) => t.id == 'ptask_upd');
      expect(updated.title, '新标题');
      expect(updated.priority, TaskPriority.low);
    });

    test('softDelete 发送 DELETE 并标记缓存为已删除', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_del'),
        statusCode: 201,
      );
      await repo.createTask(_newTask());
      expect(repo.tasks.length, 1);

      adapter.registerDelete(
        '/api/v1/tasks/ptask_del',
        data: _backendTaskJson(id: 'ptask_del', status: 'deleted', deletedAt: '2025-01-02T00:00:00+00:00'),
      );
      await repo.softDelete('ptask_del');
      // deleted 状态不在 tasks 中
      expect(repo.tasks, isEmpty);
      // 但 snapshot 保留
      expect(repo.snapshot.length, 1);
      expect(repo.snapshot.first.deleted, isTrue);
    });

    test('restore 发送 POST /restore 并恢复缓存', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_res'),
        statusCode: 201,
      );
      await repo.createTask(_newTask());

      // 先删除
      adapter.registerDelete(
        '/api/v1/tasks/ptask_res',
        data: _backendTaskJson(id: 'ptask_res', status: 'deleted'),
      );
      await repo.softDelete('ptask_res');
      expect(repo.tasks, isEmpty);

      // 恢复 — 注意 /restore 是 POST,需要注册到不同路径
      // MockDioAdapter 按 method+path 匹配,/tasks/ptask_res/restore 与 /tasks/ptask_res 不同
      adapter.registerPost(
        '/api/v1/tasks/ptask_res/restore',
        data: _backendTaskJson(id: 'ptask_res', status: 'pending'),
      );
      await repo.restore('ptask_res');
      expect(repo.tasks.length, 1);
      expect(repo.tasks.first.deleted, isFalse);
    });

    test('complete 调用 POST /complete 并更新状态', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_done'),
        statusCode: 201,
      );
      await repo.createTask(_newTask());

      adapter.registerPost(
        '/api/v1/tasks/ptask_done/complete',
        data: _backendTaskJson(
          id: 'ptask_done',
          status: 'completed',
          completedAt: '2025-01-03T00:00:00+00:00',
        ),
      );
      final completed = await repo.complete('ptask_done');
      expect(completed.completed, isTrue);
      expect(completed.completedAt, isNotNull);
      expect(repo.tasks.first.completed, isTrue);
    });
  });

  group('ApiTaskRepository - 后端失败时显示错误(不静默伪装成功)', () {
    test('createTask 网络错误时抛 ApiException', () async {
      final (repo, adapter) = _setupRepo();
      // 注册一个 500 错误响应
      adapter.registerPost(
        '/api/v1/tasks',
        data: {'code': 'SERVER_ERROR', 'message': '后端内部错误'},
        statusCode: 500,
      );

      expect(
        () => repo.createTask(_newTask()),
        throwsA(isA<ApiException>()),
      );
      // 失败时不应更新缓存
      expect(repo.tasks, isEmpty);
    });

    test('createTask 超时时抛 ApiException(TIMEOUT)', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPostError(
        '/api/v1/tasks',
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/tasks'),
          type: DioExceptionType.connectionTimeout,
        ),
      );

      expect(
        () => repo.createTask(_newTask()),
        throwsA(predicate((e) =>
            e is ApiException && (e.code == 'TIMEOUT' || e.code == 'NETWORK_ERROR'),),),
      );
      expect(repo.tasks, isEmpty);
    });

    test('updateTask 404 时抛 ApiException 且不更新缓存', () async {
      final (repo, adapter) = _setupRepo();
      // 先创建一个任务
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_404'),
        statusCode: 201,
      );
      await repo.createTask(_newTask());
      final originalTitle = repo.tasks.first.title;

      // PATCH 返回 404
      adapter.registerPatch(
        '/api/v1/tasks/ptask_404',
        data: {'code': 'PERSONAL_TASK_NOT_FOUND', 'message': '任务不存在'},
        statusCode: 404,
      );

      expect(
        () => repo.updateTask(
          repo.tasks.first.copyWith(title: '应失败的新标题'),
        ),
        throwsA(isA<ApiException>()),
      );
      // 缓存未被修改(仍是原标题)
      expect(repo.tasks.first.title, originalTitle);
    });

    test('softDelete 失败时不修改缓存', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_del_fail'),
        statusCode: 201,
      );
      await repo.createTask(_newTask());

      adapter.registerDelete(
        '/api/v1/tasks/ptask_del_fail',
        data: {'code': 'SERVER_ERROR', 'message': '删除失败'},
        statusCode: 500,
      );

      expect(
        () => repo.softDelete('ptask_del_fail'),
        throwsA(isA<ApiException>()),
      );
      // 失败时任务仍在缓存中(未删除)
      expect(repo.tasks.length, 1);
      expect(repo.tasks.first.deleted, isFalse);
    });
  });

  group('ApiTaskRepository - 登录用户切换后不显示其他用户任务', () {
    test('clearAll 后缓存为空(模拟登出)', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerPost(
        '/api/v1/tasks',
        data: _backendTaskJson(id: 'ptask_user1'),
        statusCode: 201,
      );
      await repo.createTask(_newTask());
      expect(repo.tasks.length, 1);

      // 模拟登出:清空缓存
      await repo.clearAll();
      expect(repo.tasks, isEmpty);
      expect(repo.snapshot, isEmpty);
    });

    test('refresh 后缓存替换为新用户的数据(旧用户任务消失)', () async {
      final (repo, adapter) = _setupRepo();
      // 用户A 登录后拉取的任务
      adapter.registerGet('/api/v1/tasks', data: {
        'items': [
          _backendTaskJson(id: 'ptask_userA_1', title: '用户A的任务1'),
          _backendTaskJson(id: 'ptask_userA_2', title: '用户A的任务2'),
        ],
        'total': 2,
        'page': 1,
        'page_size': 200,
      },);
      await repo.refresh();
      expect(repo.tasks.length, 2);
      expect(repo.tasks.any((t) => t.title == '用户A的任务1'), isTrue);

      // 用户A 登出,用户B 登录后拉取的任务
      adapter.registerGet('/api/v1/tasks', data: {
        'items': [
          _backendTaskJson(id: 'ptask_userB_1', title: '用户B的任务1'),
        ],
        'total': 1,
        'page': 1,
        'page_size': 200,
      },);
      await repo.refresh();
      // 用户A 的任务应完全消失
      expect(repo.tasks.length, 1);
      expect(repo.tasks.any((t) => t.title == '用户A的任务1'), isFalse);
      expect(repo.tasks.any((t) => t.title == '用户A的任务2'), isFalse);
      expect(repo.tasks.first.title, '用户B的任务1');
    });
  });

  group('ApiTaskRepository - 派生查询', () {
    test('getUpcoming 返回未完成且有截止时间的任务', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGet('/api/v1/tasks', data: {
        'items': [
          _backendTaskJson(
            id: 'ptask_1',
            title: '未来任务',
            deadline: '2099-12-31T23:59:00+00:00',
          ),
          _backendTaskJson(
            id: 'ptask_2',
            title: '已完成',
            status: 'completed',
            deadline: '2099-12-31T23:59:00+00:00',
          ),
        ],
        'total': 2,
        'page': 1,
        'page_size': 200,
      },);
      await repo.refresh();

      final upcoming = await repo.getUpcoming(limit: 10);
      expect(upcoming.length, 1);
      expect(upcoming.first.title, '未来任务');
    });

    test('getCompleted 仅返回已完成任务', () async {
      final (repo, adapter) = _setupRepo();
      adapter.registerGet('/api/v1/tasks', data: {
        'items': [
          _backendTaskJson(id: 'ptask_1', title: '待办', status: 'pending'),
          _backendTaskJson(
              id: 'ptask_2', title: '已完成', status: 'completed',),
        ],
        'total': 2,
        'page': 1,
        'page_size': 200,
      },);
      await repo.refresh();

      final completed = await repo.getCompleted();
      expect(completed.length, 1);
      expect(completed.first.title, '已完成');
    });
  });
}
