import 'package:dio/dio.dart';

import '../../../data/models/models.dart';
import '../service_interfaces.dart';
import 'api_client.dart';

/// 真实后端任务拆解服务 — 调用 FastAPI `/api/v1/study/task-breakdown`。
///
/// 后端负责:
/// - LLM 生成 / 规则化降级(响应中 mode 标注)
/// - 校园政策步骤必须依赖知识库
/// - 任务权限校验(task_id 不属于当前用户时改用 goal)
/// - 输出结构化步骤(step_number/title/description/estimated_minutes/
///   dependencies/completion_criteria/is_policy_step/knowledge_source)
///
/// 客户端只消费 JSON,网络失败抛 [ApiException]。
class ApiTaskBreakdownService implements TaskBreakdownService {
  ApiTaskBreakdownService(this._client);

  final ApiClient _client;

  @override
  Future<TaskBreakdownResponse> breakdown(
    TaskBreakdownRequest request,
  ) async {
    if (request.isEmpty) {
      throw const ApiException(
        code: 'VALIDATION_FAILED',
        message: 'task_id 与 goal 不能同时为空',
      );
    }
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/study/task-breakdown',
        data: request.toJson(),
      );
      if (resp.data == null) {
        throw const ApiException(
          code: 'EMPTY_RESPONSE',
          message: '后端返回为空',
        );
      }
      return TaskBreakdownResponse.fromJson(resp.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
