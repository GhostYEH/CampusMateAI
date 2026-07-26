import '../../data/models/models.dart';
import '../../data/services/api/api_client.dart';
import '../../data/services/service_interfaces.dart';
import '../mock_data/mock_data.dart';

/// 简易哈希(仅供 Mock 模式去重使用,非密码学安全)。
String _simpleHash(List<int> bytes) {
  var h1 = 0x811C9DC5;
  var h2 = 0x1000193;
  for (final b in bytes) {
    h1 = (h1 ^ b) * 0x01000193 & 0xFFFFFFFF;
    h2 = (h2 + b * 31) & 0xFFFFFFFF;
  }
  return '${h1.toRadixString(16).padLeft(8, '0')}${h2.toRadixString(16).padLeft(8, '0')}';
}

String _simpleHashString(String input) {
  return _simpleHash(input.codeUnits);
}

/// Mock 知识库管理服务 — 演示模式下的内存实现。
///
/// 不进行真实持久化,数据保存在内存中。仅供 Mock 模式下知识库管理页面演示用。
/// 真实模式下使用 [ApiKnowledgeManagementService]。
class MockKnowledgeManagementService implements KnowledgeManagementService {
  MockKnowledgeManagementService() {
    _seedDemoDocuments();
  }

  final List<KnowledgeDocumentSummary> _documents = [];

  void _seedDemoDocuments() {
    // 从 MockData.knowledgeSources 派生演示文档(简化元数据)
    for (final src in MockData.knowledgeSources) {
      _documents.add(
        KnowledgeDocumentSummary(
          documentId: src.id.isEmpty ? 'demo_${_documents.length}' : src.id,
          title: src.title,
          contentHash: _simpleHashString(src.title),
          isOfficial: src.isOfficial,
          isExpired: src.isExpired,
          isDemo: true,
          importedAt: src.updatedAt,
          sourceDepartment: src.sourceDepartment ?? '演示资料',
          sourceType: 'guide',
          originalFilename: '${src.title}.md',
          publishedAt: src.publishedAt,
          updatedAt: src.updatedAt,
          version: src.version,
          applicableStudents: src.applicableStudents,
          fileSize: 12 * 1024,
          fileExt: 'md',
        ),
      );
    }
  }

  @override
  Future<KnowledgeStatusInfo> getStatus() async {
    await Future.delayed(const Duration(milliseconds: 120));
    final demoCount = _documents.where((d) => d.isDemo).length;
    final userCount = _documents.where((d) => !d.isDemo).length;
    final kbType = demoCount == 0 && userCount == 0
        ? KnowledgeBaseType.empty
        : demoCount > 0 && userCount == 0
            ? KnowledgeBaseType.demo
            : demoCount == 0 && userCount > 0
                ? KnowledgeBaseType.user
                : KnowledgeBaseType.hybrid;
    return KnowledgeStatusInfo(
      documentCount: _documents.length,
      chunkCount: _documents.length * 8,
      indexStatus: _documents.isEmpty ? IndexStatus.empty : IndexStatus.ready,
      retrievalMethod: 'bm25',
      isAvailable: _documents.isNotEmpty,
      knowledgeBasePath: '(mock) 内存演示资料',
      knowledgeBaseType: kbType,
      demoDocumentCount: demoCount,
      userDocumentCount: userCount,
      llmAvailable: false,
      qaMode: _documents.isEmpty ? QaMode.noKnowledge : QaMode.retrievalSummary,
      lastUpdated: _documents.isEmpty
          ? null
          : _documents
              .map((d) => d.importedAt)
              .reduce((a, b) => a.isAfter(b) ? a : b),
    );
  }

  @override
  Future<List<KnowledgeDocumentSummary>> listDocuments() async {
    await Future.delayed(const Duration(milliseconds: 120));
    return List.of(_documents);
  }

  @override
  Future<KnowledgeDocumentSummary> uploadDocument({
    required List<int> bytes,
    required String originalFilename,
    required KnowledgeDocumentMetadata metadata,
    void Function(UploadProgress progress)? onProgress,
  }) async {
    onProgress?.call(
      const UploadProgress(
        status: UploadStatus.uploading,
        message: '正在上传文件...',
      ),
    );
    await Future.delayed(const Duration(milliseconds: 300));
    onProgress?.call(
      const UploadProgress(
        status: UploadStatus.parsing,
        message: '正在解析文档内容...',
      ),
    );
    await Future.delayed(const Duration(milliseconds: 300));
    onProgress?.call(
      const UploadProgress(
        status: UploadStatus.indexing,
        message: '正在建立检索索引...',
      ),
    );
    await Future.delayed(const Duration(milliseconds: 300));

    final hash = _simpleHash(bytes);
    // 重复检测
    final existing = _documents.where((d) => d.contentHash == hash);
    if (existing.isNotEmpty) {
      onProgress?.call(
        const UploadProgress(
          status: UploadStatus.failed,
          message: '文档已存在(哈希重复)',
          errorCode: 'DOCUMENT_ALREADY_EXISTS',
        ),
      );
      throw const ApiException(
        code: 'DOCUMENT_ALREADY_EXISTS',
        message: '文档已存在(哈希重复)',
        httpStatus: 409,
      );
    }

    final ext = originalFilename.contains('.')
        ? originalFilename.split('.').last.toLowerCase()
        : '';
    final doc = KnowledgeDocumentSummary(
      documentId: 'user_${DateTime.now().millisecondsSinceEpoch}',
      title: metadata.title?.isNotEmpty == true
          ? metadata.title!
          : originalFilename,
      contentHash: hash,
      isOfficial: metadata.isOfficial,
      isExpired: false,
      isDemo: false,
      importedAt: DateTime.now(),
      sourceDepartment: metadata.sourceDepartment,
      sourceType: metadata.sourceType,
      originalFilename: originalFilename,
      publishedAt: metadata.publishedAt,
      updatedAt: metadata.updatedAt,
      effectiveFrom: metadata.effectiveFrom,
      effectiveTo: metadata.effectiveTo,
      version: metadata.version,
      applicableStudents: metadata.applicableStudents,
      fileSize: bytes.length,
      fileExt: ext,
    );
    _documents.add(doc);
    onProgress?.call(
      UploadProgress(
        status: UploadStatus.completed,
        message: '上传完成',
        documentId: doc.documentId,
      ),
    );
    return doc;
  }

  @override
  Future<bool> deleteDocument(String documentId) async {
    await Future.delayed(const Duration(milliseconds: 150));
    final initialLen = _documents.length;
    _documents.removeWhere((d) => d.documentId == documentId);
    return _documents.length < initialLen;
  }

  @override
  Future<int> rebuildIndex({
    void Function(RebuildProgress progress)? onProgress,
  }) async {
    onProgress?.call(const RebuildProgress(inProgress: true));
    await Future.delayed(const Duration(milliseconds: 600));
    final chunks = _documents.length * 8;
    onProgress?.call(
      RebuildProgress(
        inProgress: false,
        chunkCount: chunks,
        documentCount: _documents.length,
      ),
    );
    return chunks;
  }

  @override
  Future<int> restoreDemoDocuments() async {
    await Future.delayed(const Duration(milliseconds: 200));
    var added = 0;
    for (final src in MockData.knowledgeSources) {
      final hash = _simpleHashString(src.title);
      if (_documents.any((d) => d.contentHash == hash)) continue;
      _documents.add(
        KnowledgeDocumentSummary(
          documentId:
              'demo_restored_${DateTime.now().millisecondsSinceEpoch}_$added',
          title: src.title,
          contentHash: hash,
          isOfficial: src.isOfficial,
          isExpired: src.isExpired,
          isDemo: true,
          importedAt: DateTime.now(),
          sourceDepartment: src.sourceDepartment ?? '演示资料',
          sourceType: 'guide',
          originalFilename: '${src.title}.md',
          publishedAt: src.publishedAt,
          updatedAt: src.updatedAt,
          version: src.version,
          applicableStudents: src.applicableStudents,
          fileSize: 12 * 1024,
          fileExt: 'md',
        ),
      );
      added++;
    }
    return added;
  }

  @override
  Future<DataManagementResult> manageData(DataManagementAction action) async {
    await Future.delayed(const Duration(milliseconds: 200));
    switch (action) {
      case DataManagementAction.deleteUserDocuments:
        final n = _documents.where((d) => !d.isDemo).length;
        _documents.removeWhere((d) => !d.isDemo);
        return DataManagementResult(
          action: action,
          success: true,
          message: n > 0 ? '已删除 $n 份用户导入文档' : '没有用户导入文档可删除',
          affectedCount: n,
        );
      case DataManagementAction.restoreDemoDocuments:
        final added = await restoreDemoDocuments();
        return DataManagementResult(
          action: action,
          success: true,
          message: '恢复完成,新增 $added 份演示资料',
          affectedCount: added,
        );
      case DataManagementAction.clearChatHistory:
      case DataManagementAction.clearUserTasks:
      case DataManagementAction.resetMockDemoData:
        // 这些动作在 Mock 模式下由本地仓库处理,这里返回 no-op
        return DataManagementResult(
          action: action,
          success: true,
          message: 'Mock 模式下此操作由本地仓库处理',
        );
    }
  }
}

/// Fake 知识库管理服务 — 测试用,记录所有调用并可控返回。
class FakeKnowledgeManagementService implements KnowledgeManagementService {
  FakeKnowledgeManagementService({
    List<KnowledgeDocumentSummary>? initialDocuments,
    this.statusOverride,
    this.shouldFail = false,
    this.failureCode = 'NETWORK_ERROR',
    this.failureMessage = 'Mock 失败',
  }) : _documents = initialDocuments ?? const [] {
    if (statusOverride == null) {
      _recomputeStatus();
    }
  }

  final List<KnowledgeDocumentSummary> _documents;
  KnowledgeStatusInfo? statusOverride;
  bool shouldFail;
  String failureCode;
  String failureMessage;

  final List<String> calls = [];
  final List<Map<String, dynamic>> uploadCalls = [];
  final List<String> deleteCalls = [];

  void _recomputeStatus() {
    final demoCount = _documents.where((d) => d.isDemo).length;
    final userCount = _documents.where((d) => !d.isDemo).length;
    final kbType = demoCount == 0 && userCount == 0
        ? KnowledgeBaseType.empty
        : demoCount > 0 && userCount == 0
            ? KnowledgeBaseType.demo
            : demoCount == 0 && userCount > 0
                ? KnowledgeBaseType.user
                : KnowledgeBaseType.hybrid;
    statusOverride = KnowledgeStatusInfo(
      documentCount: _documents.length,
      chunkCount: _documents.length * 8,
      indexStatus: _documents.isEmpty ? IndexStatus.empty : IndexStatus.ready,
      retrievalMethod: 'bm25',
      isAvailable: _documents.isNotEmpty,
      knowledgeBasePath: '(fake)',
      knowledgeBaseType: kbType,
      demoDocumentCount: demoCount,
      userDocumentCount: userCount,
      llmAvailable: false,
      qaMode: _documents.isEmpty ? QaMode.noKnowledge : QaMode.retrievalSummary,
      lastUpdated: null,
    );
  }

  Exception _makeFailure() =>
      ApiException(code: failureCode, message: failureMessage);

  @override
  Future<KnowledgeStatusInfo> getStatus() async {
    calls.add('getStatus');
    if (shouldFail) throw _makeFailure();
    return statusOverride ?? _recomputeStatusAndReturn();
  }

  KnowledgeStatusInfo _recomputeStatusAndReturn() {
    _recomputeStatus();
    return statusOverride!;
  }

  @override
  Future<List<KnowledgeDocumentSummary>> listDocuments() async {
    calls.add('listDocuments');
    if (shouldFail) throw _makeFailure();
    return List.of(_documents);
  }

  @override
  Future<KnowledgeDocumentSummary> uploadDocument({
    required List<int> bytes,
    required String originalFilename,
    required KnowledgeDocumentMetadata metadata,
    void Function(UploadProgress progress)? onProgress,
  }) async {
    calls.add('uploadDocument');
    uploadCalls.add({
      'bytes': bytes,
      'filename': originalFilename,
      'metadata': metadata,
    });
    if (shouldFail) {
      onProgress?.call(
        UploadProgress(
          status: UploadStatus.failed,
          message: failureMessage,
          errorCode: failureCode,
        ),
      );
      throw _makeFailure();
    }
    onProgress?.call(
      const UploadProgress(status: UploadStatus.uploading, message: '上传中'),
    );
    onProgress?.call(
      const UploadProgress(status: UploadStatus.parsing, message: '解析中'),
    );
    onProgress?.call(
      const UploadProgress(status: UploadStatus.indexing, message: '索引中'),
    );
    final doc = KnowledgeDocumentSummary(
      documentId: 'fake_${DateTime.now().millisecondsSinceEpoch}',
      title: metadata.title?.isNotEmpty == true
          ? metadata.title!
          : originalFilename,
      contentHash: 'fake_hash_${uploadCalls.length}',
      isOfficial: metadata.isOfficial,
      isExpired: false,
      isDemo: false,
      importedAt: DateTime.now(),
      sourceDepartment: metadata.sourceDepartment,
      sourceType: metadata.sourceType,
      originalFilename: originalFilename,
      publishedAt: metadata.publishedAt,
      version: metadata.version,
      applicableStudents: metadata.applicableStudents,
      fileSize: bytes.length,
      fileExt: originalFilename.split('.').lastOrNull,
    );
    _documents.add(doc);
    _recomputeStatus();
    onProgress?.call(
      UploadProgress(
        status: UploadStatus.completed,
        message: '完成',
        documentId: doc.documentId,
      ),
    );
    return doc;
  }

  @override
  Future<bool> deleteDocument(String documentId) async {
    calls.add('deleteDocument:$documentId');
    deleteCalls.add(documentId);
    if (shouldFail) throw _makeFailure();
    final initialLen = _documents.length;
    _documents.removeWhere((d) => d.documentId == documentId);
    _recomputeStatus();
    return _documents.length < initialLen;
  }

  @override
  Future<int> rebuildIndex({
    void Function(RebuildProgress progress)? onProgress,
  }) async {
    calls.add('rebuildIndex');
    if (shouldFail) {
      onProgress?.call(
        RebuildProgress(inProgress: false, error: failureMessage),
      );
      throw _makeFailure();
    }
    onProgress?.call(const RebuildProgress(inProgress: true));
    await Future.delayed(const Duration(milliseconds: 10));
    final chunks = _documents.length * 8;
    onProgress?.call(
      RebuildProgress(
        inProgress: false,
        chunkCount: chunks,
        documentCount: _documents.length,
      ),
    );
    return chunks;
  }

  @override
  Future<int> restoreDemoDocuments() async {
    calls.add('restoreDemoDocuments');
    if (shouldFail) throw _makeFailure();
    return 0;
  }

  @override
  Future<DataManagementResult> manageData(DataManagementAction action) async {
    calls.add('manageData:${action.code}');
    if (shouldFail) throw _makeFailure();
    if (action == DataManagementAction.deleteUserDocuments) {
      final n = _documents.where((d) => !d.isDemo).length;
      _documents.removeWhere((d) => !d.isDemo);
      _recomputeStatus();
      return DataManagementResult(
        action: action,
        success: true,
        message: '已删除 $n 份用户文档',
        affectedCount: n,
      );
    }
    return DataManagementResult(
      action: action,
      success: true,
      message: 'OK',
    );
  }
}
