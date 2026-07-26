import 'package:dio/dio.dart';

import '../../../data/models/models.dart';
import '../service_interfaces.dart';
import 'api_client.dart';

/// 真实后端通知抽取服务 — 调用 FastAPI `/api/v1/notices/extract`。
///
/// 兼容 Mock 模式下的分步骤进度反馈:
/// - 调用前发送"准备调用后端"步骤
/// - 调用后发送"已收到结构化结果"步骤
///
/// 后端 LLM 模式或规则模式由后端决定,客户端只消费 JSON。
class ApiNotificationExtractionService
    implements NotificationExtractionService {
  ApiNotificationExtractionService(this._client);

  final ApiClient _client;

  @override
  Future<ExtractedNotice> extract(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  }) async {
    // 步骤 0:通知后端准备抽取
    onProgress?.call(
      const ExtractionStep(
        label: '正在连接后端服务',
        order: 0,
        detail: '发送通知原文到 FastAPI',
      ),
    );

    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/notices/extract',
        data: {
          'content': rawNotice,
        },
      );

      // 步骤 1~5:模拟分步处理(以可视化方式展示后端已返回)
      for (var i = 1; i <= 5; i++) {
        onProgress?.call(
          ExtractionStep(
            label: _stepLabel(i),
            order: i,
          ),
        );
        // 短暂动画,仅为视觉一致性,不阻塞业务
        await Future<void>.delayed(const Duration(milliseconds: 80));
      }

      final data = resp.data ?? {};
      return _parseExtractedNotice(data, rawNotice);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<MultiExtractResult> extractMulti(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  }) async {
    onProgress?.call(
      const ExtractionStep(
        label: '正在连接后端服务',
        order: 0,
        detail: '请求多任务抽取',
      ),
    );

    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/notices/extract-multi',
        data: {
          'content': rawNotice,
          'allow_multi_task': true,
        },
      );

      for (var i = 1; i <= 5; i++) {
        onProgress?.call(
          ExtractionStep(
            label: _stepLabel(i),
            order: i,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 80));
      }

      final data = resp.data ?? {};
      final tasksRaw = (data['tasks'] as List?) ?? [];
      final tasks = <ExtractedNotice>[];
      for (final t in tasksRaw) {
        if (t is Map<String, dynamic>) {
          tasks.add(_parseExtractedNotice(t, rawNotice));
        }
      }
      if (tasks.isEmpty) {
        // 后端返回空列表时,降级为单任务抽取
        final single = await extract(rawNotice, onProgress: onProgress);
        return MultiExtractResult(
          tasks: [single],
          splitReason: '后端返回空列表,降级为单任务',
          needsUserConfirmation: false,
        );
      }
      return MultiExtractResult(
        tasks: tasks,
        splitReason: (data['split_reason'] as String?) ?? '',
        needsUserConfirmation:
            (data['needs_user_confirmation'] as bool?) ?? false,
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<DuplicateCheckResult> checkDuplicate({
    required String content,
    String? sourceName,
    String? taskName,
    DateTime? deadline,
    required List<RecentNoticeItem> recentNotices,
  }) async {
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/notices/check-duplicate',
        data: {
          'content': content,
          'source_name': sourceName,
          'task_name': taskName,
          'deadline': deadline?.toUtc().toIso8601String(),
          'recent_notices': [
            for (final n in recentNotices)
              {
                'notice_id': n.noticeId,
                'title': n.title,
                'task': n.task,
                'source_name': n.sourceName,
                'source_text': n.sourceText,
                'deadline': n.deadline?.toUtc().toIso8601String(),
              },
          ],
        },
      );
      final data = resp.data ?? {};
      final matchesRaw = (data['matches'] as List?) ?? [];
      return DuplicateCheckResult(
        isDuplicate: (data['is_duplicate'] as bool?) ?? false,
        matches: [
          for (final m in matchesRaw)
            if (m is Map<String, dynamic>)
              DuplicateMatch(
                noticeId: (m['notice_id'] as String?) ?? '',
                title: (m['title'] as String?) ?? '',
                sourceName: m['source_name'] as String?,
                deadline: _parseDate(m['deadline']),
                similarity: ((m['similarity'] as num?) ?? 0).toDouble(),
                reasons: ((m['reasons'] as List?) ?? [])
                    .map((e) => e.toString())
                    .toList(growable: false),
              ),
        ],
        contentHash: (data['content_hash'] as String?) ?? '',
        note: (data['note'] as String?) ?? '仅提示可能重复,不会自动覆盖原待办。',
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  DateTime? _parseDate(dynamic raw) {
    if (raw is! String || raw.isEmpty) return null;
    return DateTime.tryParse(raw);
  }

  String _stepLabel(int i) {
    switch (i) {
      case 1:
        return '识别通知类型';
      case 2:
        return '提取任务名称与面向对象';
      case 3:
        return '解析截止时间';
      case 4:
        return '识别所需材料';
      case 5:
        return '判断提交方式与地点';
      default:
        return '处理中';
    }
  }

  ExtractedNotice _parseExtractedNotice(
    Map<String, dynamic> data,
    String rawNotice,
  ) {
    final task = (data['task'] as String?)?.trim() ?? '';
    final title = (data['title'] as String?)?.trim() ?? task;
    final deadlineRaw = data['deadline'];
    DateTime? deadline;
    if (deadlineRaw is String && deadlineRaw.isNotEmpty) {
      try {
        deadline = DateTime.parse(deadlineRaw);
      } catch (_) {
        deadline = null;
      }
    }

    final materialsRaw = (data['materials'] as List?) ?? [];
    final materials = <TaskMaterial>[];
    for (final m in materialsRaw) {
      if (m is Map<String, dynamic>) {
        final name = (m['name'] as String?)?.trim() ?? '';
        if (name.isEmpty) continue;
        materials.add(
          TaskMaterial(
            id: (m['id'] as String?) ?? 'm_${materials.length + 1}',
            name: name,
            required: m['required'] as bool? ?? true,
          ),
        );
      }
    }

    final importance = NoticeImportance.fromString(
      data['importance'] as String?,
    );

    final confidence = (data['confidence'] as num?)?.toDouble() ?? 0.0;
    final warnings = ((data['warnings'] as List?) ?? [])
        .map((w) => w.toString())
        .where((w) => w.isNotEmpty)
        .toList();

    // extractor_mode: llm | rules(后端字段),客户端透传
    final extractorMode =
        (data['extractor_mode'] as String?)?.trim().isEmpty == true
            ? 'rules'
            : (data['extractor_mode'] as String?)!.trim();

    // 将 warnings 作为提取步骤可视化(便于 UI 显示)
    final steps = <String>['已收到后端响应'];
    if (warnings.isNotEmpty) {
      steps.addAll(warnings);
    }

    return ExtractedNotice(
      taskName: task.isEmpty ? title : task,
      targetAudience:
          (data['target_students'] as String?)?.trim().isEmpty == true
              ? null
              : (data['target_students'] as String?)?.trim(),
      deadline: deadline,
      materials: materials,
      submitMethod:
          (data['submission_method'] as String?)?.trim().isEmpty == true
              ? null
              : (data['submission_method'] as String?)?.trim(),
      location: (data['location'] as String?)?.trim().isEmpty == true
          ? null
          : (data['location'] as String?)?.trim(),
      sourceText: rawNotice,
      importance: importance,
      confidence: confidence,
      extractedSteps: steps,
      warnings: warnings,
      extractorMode: extractorMode,
    );
  }
}
