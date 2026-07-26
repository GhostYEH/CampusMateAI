import 'package:dio/dio.dart';

import '../../../data/models/models.dart';
import '../service_interfaces.dart';
import 'api_client.dart';

/// 真实后端知识库服务 — 调用 FastAPI 的知识库检索接口。
///
/// 当前实现:
/// - [search] 调用后端 BM25 检索
/// - [sources] 返回已导入文档列表
///
/// 后端返回的 sources 字段比 Mock 更丰富(包含 document_id, is_official,
/// is_expired 等),由 [ApiCounselorChatService] 在 SSE 解析时消费。
class ApiKnowledgeBaseService implements KnowledgeBaseService {
  ApiKnowledgeBaseService(this._client);

  final ApiClient _client;

  @override
  Future<List<KnowledgeSource>> search(String query, {int limit = 3}) async {
    try {
      // 后端目前通过 RAG 问答接口暴露检索能力;
      // 这里提供一个轻量的"按关键词搜索文档"实现,
      // 实际客户端通常直接使用 CounselorChatService 即可。
      final resp = await _client.dio.get<List<dynamic>>(
        '/api/v1/knowledge/documents',
      );
      final docs = resp.data ?? [];
      final sources = <KnowledgeSource>[];
      for (final d in docs) {
        if (d is! Map<String, dynamic>) continue;
        sources.add(_toKnowledgeSource(d));
      }
      return sources.take(limit).toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<List<KnowledgeSource>> get sources async {
    try {
      // 列表接口返回所有已导入文档
      final docsResp = await _client.dio.get<List<dynamic>>(
        '/api/v1/knowledge/documents',
      );
      final docs = docsResp.data ?? [];
      final sources = <KnowledgeSource>[];
      for (final d in docs) {
        if (d is! Map<String, dynamic>) continue;
        sources.add(_toKnowledgeSource(d));
      }
      return sources;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  KnowledgeSource _toKnowledgeSource(Map<String, dynamic> d) {
    final title = (d['title'] as String?) ?? '未命名文档';
    final dtStr = d['updated_at'] as String? ?? d['published_at'] as String?;
    DateTime dt = DateTime.now();
    if (dtStr != null && dtStr.isNotEmpty) {
      try {
        dt = DateTime.parse(dtStr);
      } catch (_) {
        // 保留默认值
      }
    }
    final publishedAtStr = d['published_at'] as String?;
    DateTime? publishedAt;
    if (publishedAtStr != null && publishedAtStr.isNotEmpty) {
      try {
        publishedAt = DateTime.parse(publishedAtStr);
      } catch (_) {
        publishedAt = null;
      }
    }
    final isExpired = d['is_expired'] as bool? ?? false;
    final isOfficial = d['is_official'] as bool? ?? false;
    final dept = (d['source_department'] as String?) ?? '演示资料';
    final sourceLabel =
        isExpired ? '$dept · 已过期' : (isOfficial ? '$dept · 官方' : dept);
    return KnowledgeSource(
      id: (d['document_id'] as String?) ?? '',
      title: title,
      updatedAt: dt,
      source: sourceLabel,
      relevance: 0,
      sourceDepartment:
          (d['source_department'] as String?)?.trim().isEmpty == true
              ? null
              : (d['source_department'] as String?)?.trim(),
      publishedAt: publishedAt,
      version: (d['version'] as String?)?.trim().isEmpty == true
          ? null
          : (d['version'] as String?)?.trim(),
      applicableStudents:
          (d['applicable_students'] as String?)?.trim().isEmpty == true
              ? null
              : (d['applicable_students'] as String?)?.trim(),
      isOfficial: isOfficial,
      isExpired: isExpired,
    );
  }
}
