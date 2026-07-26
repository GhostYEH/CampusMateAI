import 'package:dio/dio.dart';

import '../../../data/models/models.dart';
import '../service_interfaces.dart';
import 'api_client.dart';

/// 真实后端知识库管理服务 — 调用 FastAPI 的知识库管理接口。
///
/// 后端接口(对齐 docs/api_contract.md):
/// - GET    /api/v1/knowledge/status
/// - GET    /api/v1/knowledge/documents
/// - POST   /api/v1/knowledge/documents          (multipart/form-data)
/// - DELETE /api/v1/knowledge/documents/{document_id}
/// - POST   /api/v1/knowledge/rebuild
/// - POST   /api/v1/knowledge/restore-demo
/// - POST   /api/v1/knowledge/manage/{action}
class ApiKnowledgeManagementService implements KnowledgeManagementService {
  ApiKnowledgeManagementService(this._client);

  final ApiClient _client;

  @override
  Future<KnowledgeStatusInfo> getStatus() async {
    try {
      final resp = await _client.dio.get<Map<String, dynamic>>(
        '/api/v1/knowledge/status',
      );
      final data = resp.data ?? {};
      return _parseStatus(data);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<List<KnowledgeDocumentSummary>> listDocuments() async {
    try {
      final resp = await _client.dio.get<List<dynamic>>(
        '/api/v1/knowledge/documents',
      );
      final docs = resp.data ?? [];
      final result = <KnowledgeDocumentSummary>[];
      for (final d in docs) {
        if (d is! Map<String, dynamic>) continue;
        result.add(_parseDocument(d));
      }
      return result;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<KnowledgeDocumentSummary> uploadDocument({
    required List<int> bytes,
    required String originalFilename,
    required KnowledgeDocumentMetadata metadata,
    void Function(UploadProgress progress)? onProgress,
  }) async {
    final formFields = metadata.toFormFields();
    try {
      // 阶段 1: 上传中
      onProgress?.call(
        const UploadProgress(
          status: UploadStatus.uploading,
          message: '正在上传文件...',
        ),
      );

      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: originalFilename),
        for (final entry in formFields.entries)
          if (entry.value != null) entry.key: entry.value,
      });

      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/knowledge/documents',
        data: formData,
        options: Options(
          headers: {'Content-Type': 'multipart/form-data'},
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 60),
        ),
        onSendProgress: (sent, total) {
          if (total > 0) {
            final pct = (sent / total * 100).toStringAsFixed(0);
            onProgress?.call(
              UploadProgress(
                status: UploadStatus.uploading,
                message: '正在上传文件... $pct%',
              ),
            );
          }
        },
      );

      // 阶段 2: 解析中(后端已返回,但前端模拟解析状态)
      onProgress?.call(
        const UploadProgress(
          status: UploadStatus.parsing,
          message: '正在解析文档内容...',
        ),
      );
      await Future.delayed(const Duration(milliseconds: 200));

      // 阶段 3: 索引中
      onProgress?.call(
        const UploadProgress(
          status: UploadStatus.indexing,
          message: '正在建立检索索引...',
        ),
      );
      await Future.delayed(const Duration(milliseconds: 200));

      final doc = _parseDocument(resp.data ?? {});
      // 阶段 4: 完成
      onProgress?.call(
        UploadProgress(
          status: UploadStatus.completed,
          message: '上传完成',
          documentId: doc.documentId,
        ),
      );
      return doc;
    } on DioException catch (e) {
      final apiEx = ApiException.fromDio(e);
      onProgress?.call(
        UploadProgress(
          status: UploadStatus.failed,
          message: apiEx.message,
          errorCode: apiEx.code,
        ),
      );
      throw apiEx;
    }
  }

  @override
  Future<bool> deleteDocument(String documentId) async {
    try {
      await _client.dio.delete<Map<String, dynamic>>(
        '/api/v1/knowledge/documents/$documentId',
      );
      return true;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<int> rebuildIndex({
    void Function(RebuildProgress progress)? onProgress,
  }) async {
    onProgress?.call(const RebuildProgress(inProgress: true));
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/knowledge/rebuild',
      );
      final data = resp.data ?? {};
      final chunks = (data['chunk_count'] as num?)?.toInt() ?? 0;
      final docs = (data['document_count'] as num?)?.toInt() ?? 0;
      onProgress?.call(
        RebuildProgress(
          inProgress: false,
          chunkCount: chunks,
          documentCount: docs,
        ),
      );
      return chunks;
    } on DioException catch (e) {
      final apiEx = ApiException.fromDio(e);
      onProgress?.call(
        RebuildProgress(inProgress: false, error: apiEx.message),
      );
      throw apiEx;
    }
  }

  @override
  Future<int> restoreDemoDocuments() async {
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/knowledge/restore-demo',
      );
      final data = resp.data ?? {};
      return (data['restored_count'] as num?)?.toInt() ?? 0;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  @override
  Future<DataManagementResult> manageData(DataManagementAction action) async {
    try {
      final resp = await _client.dio.post<Map<String, dynamic>>(
        '/api/v1/knowledge/manage/${action.code}',
      );
      final data = resp.data ?? {};
      return DataManagementResult(
        action: action,
        success: (data['success'] as bool?) ?? false,
        message: (data['message'] as String?) ?? '操作完成',
        affectedCount: (data['affected_count'] as num?)?.toInt() ?? 0,
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  KnowledgeStatusInfo _parseStatus(Map<String, dynamic> data) {
    return KnowledgeStatusInfo(
      documentCount: (data['document_count'] as num?)?.toInt() ?? 0,
      chunkCount: (data['chunk_count'] as num?)?.toInt() ?? 0,
      indexStatus: _parseIndexStatus(data['index_status'] as String?),
      retrievalMethod: (data['retrieval_method'] as String?) ?? 'bm25',
      isAvailable: (data['is_available'] as bool?) ?? false,
      knowledgeBasePath: (data['knowledge_base_path'] as String?) ?? '',
      knowledgeBaseType: KnowledgeBaseType.fromString(
        data['knowledge_base_type'] as String?,
      ),
      demoDocumentCount: (data['demo_document_count'] as num?)?.toInt() ?? 0,
      userDocumentCount: (data['user_document_count'] as num?)?.toInt() ?? 0,
      llmAvailable: (data['llm_available'] as bool?) ?? false,
      qaMode: QaMode.fromString(data['qa_mode'] as String?),
      lastUpdated: _tryParseDate(data['last_updated'] as String?),
    );
  }

  IndexStatus _parseIndexStatus(String? value) {
    switch (value) {
      case 'ready':
        return IndexStatus.ready;
      case 'error':
        return IndexStatus.error;
      default:
        return IndexStatus.empty;
    }
  }

  KnowledgeDocumentSummary _parseDocument(Map<String, dynamic> d) {
    return KnowledgeDocumentSummary(
      documentId: (d['document_id'] as String?) ?? '',
      title: (d['title'] as String?) ?? '未命名文档',
      contentHash: (d['content_hash'] as String?) ?? '',
      isOfficial: (d['is_official'] as bool?) ?? false,
      isExpired: (d['is_expired'] as bool?) ?? false,
      isDemo: (d['is_demo'] as bool?) ?? false,
      importedAt: _tryParseDate(d['imported_at'] as String?) ?? DateTime.now(),
      sourceDepartment: _asString(d['source_department']),
      sourceType: _asString(d['source_type']),
      originalFilename: _asString(d['original_filename']),
      publishedAt: _tryParseDate(d['published_at'] as String?),
      updatedAt: _tryParseDate(d['updated_at'] as String?),
      effectiveFrom: _tryParseDate(d['effective_from'] as String?),
      effectiveTo: _tryParseDate(d['effective_to'] as String?),
      version: _asString(d['version']),
      applicableStudents: _asString(d['applicable_students']),
      fileSize: (d['file_size'] as num?)?.toInt(),
      fileExt: _asString(d['file_ext']),
    );
  }

  String? _asString(dynamic v) {
    if (v == null) return null;
    final s = v.toString().trim();
    return s.isEmpty ? null : s;
  }

  DateTime? _tryParseDate(String? s) {
    if (s == null || s.isEmpty) return null;
    return DateTime.tryParse(s);
  }
}
