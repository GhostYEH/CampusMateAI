import 'dart:async';

import 'package:dio/dio.dart';

import '../../../data/models/models.dart';
import '../service_interfaces.dart';
import 'api_client.dart';

/// 真实后端个人待办仓库 — 调用 FastAPI `/api/v1/tasks` 系列接口。
///
/// **设计目标**(对齐 backend 个人待办真实闭环要求):
/// - 当 `USE_MOCK_BACKEND=false` 时,通过 [ApiClient] 调用真实后端
/// - 所有写操作必须等待后端成功才更新本地状态(不静默伪装成功)
/// - 网络错误时抛 [ApiException],由 UI 层展示错误
/// - 任务按 JWT 用户隔离,后端强制 user_id 校验,客户端不需要传 user_id
/// - 软删除走 `DELETE /tasks/{id}`,本地状态镜像后端 status
///
/// **本地缓存策略**:
/// - 内存缓存仅用于 UI 即时渲染,不作为服务端保存成功的证据
/// - 启动后通过 [refresh] 拉取最新数据,后续写操作以后端返回为准
/// - 离线时缓存仍可读,但写操作必须报错(不静默降级)
///
/// **字段映射**(前端 Task ↔ 后端 PersonalTaskOut):
/// - 前端 `completed`/`deleted` ↔ 后端 `status` (pending/completed/deleted)
/// - 前端 `reminderEnabled`/`reminderAt` ↔ 后端 `reminder_minutes`(从 deadline 偏移)
/// - 前端 `sourceText` ↔ 后端 `source_text`(原文追溯,必须保留)
/// - 前端 `materials`(List<TaskMaterial>) ↔ 后端 `materials`(List<String>,仅名称)
///
/// **离线兼容**:
/// - 此仓库不负责离线持久化(由调用方决定是否缓存到 SharedPreferences)
/// - `snapshot`/`restoreFrom`/`clearAll`/`resetToDemo` 仅操作内存缓存,
///   不调用后端 — 用于"清除本地数据"等场景
class ApiTaskRepository implements TaskRepository {
  ApiTaskRepository(this._client);

  final ApiClient _client;

  /// 内存缓存(只读镜像,写操作以后端返回为准)。
  final List<Task> _cache = [];
  final _controller = StreamController<List<Task>>.broadcast();

  @override
  List<Task> get tasks => List.unmodifiable(
        _cache.where((t) => !t.deleted).toList()..sort(_byDeadlineThenPriority),
      );

  @override
  List<Task> get snapshot => List.unmodifiable(_cache);

  @override
  Stream<List<Task>> watchTasks() =>
      _controller.stream.map((list) => List.unmodifiable(list));

  void _emit() {
    _controller.add(tasks);
  }

  /// 从后端拉取最新任务列表并刷新缓存。
  ///
  /// 应在登录后 / 应用启动时调用一次,后续写操作会自动维护缓存。
  /// 网络错误时抛 [ApiException],不静默清空缓存。
  Future<void> refresh() async {
    try {
      final resp = await _client.dio.get<Map<String, dynamic>>(
        '/api/v1/tasks',
        queryParameters: {'include_deleted': true, 'page_size': 200},
      );
      final data = resp.data ?? {};
      final items = (data['items'] as List?) ?? [];
      _cache
        ..clear()
        ..addAll(
          items
              .map((e) => e is Map<String, dynamic> ? _parseTask(e) : null)
              .whereType<Task>(),
        );
      _emit();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<Task> createTask(Task task) async {
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/tasks',
        data: _toCreatePayload(task),
      );
      final created = _parseTask(resp.data ?? {});
      if (created == null) {
        throw const ApiException(
          code: 'PARSE_ERROR',
          message: '后端返回数据格式异常,创建任务失败。',
        );
      }
      _cache.add(created);
      _emit();
      return created;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<void> updateTask(Task task) async {
    try {
      final resp = await _client.dio.patch<Map<String, dynamic>>(
        '/api/v1/tasks/${task.id}',
        data: _toUpdatePayload(task),
      );
      final updated = _parseTask(resp.data ?? {});
      if (updated == null) {
        throw const ApiException(
          code: 'PARSE_ERROR',
          message: '后端返回数据格式异常,更新任务失败。',
        );
      }
      final i = _cache.indexWhere((t) => t.id == updated.id);
      if (i >= 0) {
        _cache[i] = updated;
      } else {
        _cache.add(updated);
      }
      _emit();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<void> softDelete(String taskId) async {
    try {
      final resp = await _client.dio.delete<Map<String, dynamic>>(
        '/api/v1/tasks/$taskId',
      );
      final updated = _parseTask(resp.data ?? {});
      if (updated != null) {
        final i = _cache.indexWhere((t) => t.id == updated.id);
        if (i >= 0) _cache[i] = updated;
      } else {
        // 后端返回 200 但解析失败,本地标记为删除以保持一致
        final i = _cache.indexWhere((t) => t.id == taskId);
        if (i >= 0) {
          _cache[i] = _cache[i].copyWith(deleted: true);
        }
      }
      _emit();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<void> restore(String taskId) async {
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/tasks/$taskId/restore',
      );
      final updated = _parseTask(resp.data ?? {});
      if (updated == null) {
        throw const ApiException(
          code: 'PARSE_ERROR',
          message: '后端返回数据格式异常,恢复任务失败。',
        );
      }
      final i = _cache.indexWhere((t) => t.id == updated.id);
      if (i >= 0) {
        _cache[i] = updated;
      } else {
        _cache.add(updated);
      }
      _emit();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<void> hardDelete(String taskId) async {
    // 后端本轮不提供物理删除接口,softDelete 后不再列出即可。
    // 这里调用 softDelete 以保持语义一致,本地从缓存中移除。
    try {
      await _client.dio.delete<Map<String, dynamic>>(
        '/api/v1/tasks/$taskId',
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
    _cache.removeWhere((t) => t.id == taskId);
    _emit();
  }

  /// 标记任务完成(对齐后端 `POST /tasks/{id}/complete`)。
  ///
  /// 此方法不在 [TaskRepository] 抽象接口中,因为 [TaskListNotifier.toggleComplete]
  /// 通过 [updateTask] 走通用更新流程。但保留此方法以便未来直接调用后端完成接口,
  /// 避免 PATCH 接口不允许修改 status 的限制。
  Future<Task> complete(String taskId) async {
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/tasks/$taskId/complete',
      );
      final updated = _parseTask(resp.data ?? {});
      if (updated == null) {
        throw const ApiException(
          code: 'PARSE_ERROR',
          message: '后端返回数据格式异常,完成任务失败。',
        );
      }
      final i = _cache.indexWhere((t) => t.id == updated.id);
      if (i >= 0) _cache[i] = updated;
      _emit();
      return updated;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // ===== 派生查询(从缓存计算,不调用后端)=====

  @override
  Future<List<Task>> getByCategory(TaskCategory category) async =>
      tasks.where((t) => t.category == category).toList();

  @override
  Future<List<Task>> getUpcoming({int limit = 5}) async {
    final list = tasks.where((t) => !t.completed && t.deadline != null).toList()
      ..sort((a, b) => a.deadline!.compareTo(b.deadline!));
    return list.take(limit).toList();
  }

  @override
  Future<List<Task>> getCompleted() async =>
      tasks.where((t) => t.completed).toList();

  @override
  Future<List<Task>> getToday() async {
    final now = DateTime.now();
    return tasks.where((t) {
      if (t.completed) return false;
      if (t.deadline == null) return false;
      final d = t.deadline!;
      return d.year == now.year && d.month == now.month && d.day == now.day;
    }).toList();
  }

  // ===== 本地缓存管理(不调用后端)=====

  @override
  Future<void> restoreFrom(List<Task> saved) async {
    _cache
      ..clear()
      ..addAll(saved);
    _emit();
  }

  @override
  Future<void> clearAll() async {
    _cache.clear();
    _emit();
  }

  @override
  Future<void> resetToDemo() async {
    // 真实后端模式不支持"恢复演示数据" — 清空缓存,等待下次 refresh
    _cache.clear();
    _emit();
  }

  // ===== 序列化辅助 =====

  /// 构造创建任务请求体(对齐后端 PersonalTaskCreate schema)。
  ///
  /// 注意:
  /// - `user_id` 由后端 JWT 注入,客户端不传
  /// - `source_text` 必须保留(原文追溯)
  /// - `reminder_minutes` 从 `reminderAt` 与 `deadline` 反推
  Map<String, dynamic> _toCreatePayload(Task task) {
    return {
      'title': task.title,
      'description': task.description,
      'target_students': task.targetStudents,
      'deadline': task.deadline?.toIso8601String(),
      'materials': [for (final m in task.materials) m.name],
      'submission_method': task.submissionMethod,
      'location': task.location,
      'source_name': task.sourceName,
      'source_text': task.sourceText,
      'source_notice_id': task.sourceNoticeId,
      'priority': task.priority.name,
      'reminder_minutes': _computeReminderMinutes(task),
    };
  }

  /// 构造更新任务请求体(对齐后端 PersonalTaskUpdate schema)。
  ///
  /// 后端不允许通过 PATCH 修改 status/completed_at/deleted_at,
  /// 这些状态由 /complete /restore /DELETE 接口管理。
  Map<String, dynamic> _toUpdatePayload(Task task) {
    return {
      'title': task.title,
      'description': task.description,
      'target_students': task.targetStudents,
      'deadline': task.deadline?.toIso8601String(),
      'materials': [for (final m in task.materials) m.name],
      'submission_method': task.submissionMethod,
      'location': task.location,
      'source_name': task.sourceName,
      'source_text': task.sourceText,
      'source_notice_id': task.sourceNoticeId,
      'priority': task.priority.name,
      'reminder_minutes': _computeReminderMinutes(task),
    };
  }

  /// 从 reminderAt 与 deadline 反推 reminder_minutes。
  /// 若无 deadline 或 reminderAt,返回 null。
  int? _computeReminderMinutes(Task task) {
    final deadline = task.deadline;
    final reminderAt = task.reminderAt;
    if (deadline == null || reminderAt == null) return null;
    final diff = deadline.difference(reminderAt).inMinutes;
    return diff < 0 ? 0 : diff;
  }

  /// 解析后端返回的任务对象。失败返回 null。
  Task? _parseTask(Map<String, dynamic> json) {
    final id = json['id'] as String?;
    if (id == null) return null;
    final status = (json['status'] as String?) ?? 'pending';
    final deadlineStr = json['deadline'] as String?;
    final deadline =
        deadlineStr == null ? null : DateTime.tryParse(deadlineStr);
    final reminderMinutes = (json['reminder_minutes'] as num?)?.toInt();

    // 从 reminder_minutes 与 deadline 反推 reminderAt(用于本地提醒调度)
    DateTime? reminderAt;
    bool reminderEnabled = false;
    if (reminderMinutes != null && deadline != null) {
      reminderAt = deadline.subtract(Duration(minutes: reminderMinutes));
      reminderEnabled = true;
    }

    // 解析 completed_at
    final completedAtStr = json['completed_at'] as String?;
    final completedAt =
        completedAtStr == null ? null : DateTime.tryParse(completedAtStr);

    // 解析 created_at(失败时回退到当前时间)
    final createdAtStr = json['created_at'] as String? ?? '';
    final createdAt = createdAtStr.isEmpty
        ? DateTime.now()
        : (DateTime.tryParse(createdAtStr) ?? DateTime.now());

    // 解析 materials(后端为 List<String>,前端包装为 TaskMaterial)
    final materialsList = (json['materials'] as List?) ?? [];
    final materials = <TaskMaterial>[];
    for (final m in materialsList) {
      if (m is String) {
        materials.add(TaskMaterial(id: 'm_${materials.length}_$m', name: m));
      }
    }

    return Task(
      id: id,
      title: (json['title'] as String?) ?? '',
      category: TaskCategory.material, // 后端不区分 category,前端默认 material
      priority: TaskPriority.fromString(json['priority'] as String?),
      createdAt: createdAt,
      source: TaskSource.noticeExtraction, // 后端任务来源于通知抽取
      description: json['description'] as String?,
      deadline: deadline,
      materials: materials,
      location: json['location'] as String?,
      completed: status == 'completed',
      completedAt: completedAt,
      deleted: status == 'deleted',
      reminderEnabled: reminderEnabled,
      reminderAt: reminderAt,
      sourceNoticeId: json['source_notice_id'] as String?,
      sourceText: json['source_text'] as String?,
      sourceName: json['source_name'] as String?,
      targetStudents: json['target_students'] as String?,
      submissionMethod: json['submission_method'] as String?,
      reminderMinutes: reminderMinutes,
    );
  }

  int _byDeadlineThenPriority(Task a, Task b) {
    if (a.completed != b.completed) return a.completed ? 1 : -1;
    final ad = a.deadline;
    final bd = b.deadline;
    if (ad != null && bd != null) return ad.compareTo(bd);
    if (ad != null) return -1;
    if (bd != null) return 1;
    return b.priority.weight.compareTo(a.priority.weight);
  }

  void dispose() => _controller.close();
}
