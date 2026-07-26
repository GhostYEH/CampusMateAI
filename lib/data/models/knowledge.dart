import 'package:equatable/equatable.dart';

/// 知识库类型。
enum KnowledgeBaseType {
  /// 仿真校园演示资料
  demo('仿真校园知识库'),

  /// 用户导入资料
  user('用户导入知识库'),

  /// 演示 + 用户混合
  hybrid('混合知识库'),

  /// 空
  empty('空知识库');

  const KnowledgeBaseType(this.displayName);
  final String displayName;

  static KnowledgeBaseType fromString(String? value) {
    switch (value) {
      case 'demo':
        return KnowledgeBaseType.demo;
      case 'user':
        return KnowledgeBaseType.user;
      case 'hybrid':
        return KnowledgeBaseType.hybrid;
      default:
        return KnowledgeBaseType.empty;
    }
  }
}

/// 问答模式。
enum QaMode {
  /// 检索摘要(无 LLM 时使用)
  retrievalSummary('retrieval_summary', '检索摘要'),

  /// LLM RAG 生成
  llmRag('llm_rag', 'LLM RAG'),

  /// 无知识库依据
  noKnowledge('no_knowledge', '无知识库依据');

  const QaMode(this.code, this.displayName);
  final String code;
  final String displayName;

  static QaMode fromString(String? value) {
    switch (value) {
      case 'retrieval_summary':
        return QaMode.retrievalSummary;
      case 'llm_rag':
        return QaMode.llmRag;
      default:
        return QaMode.noKnowledge;
    }
  }
}

/// 索引状态。
enum IndexStatus { ready, empty, error }

/// 知识库状态信息 — 对齐后端 `KnowledgeStatus` schema。
class KnowledgeStatusInfo extends Equatable {
  const KnowledgeStatusInfo({
    required this.documentCount,
    required this.chunkCount,
    required this.indexStatus,
    required this.retrievalMethod,
    required this.isAvailable,
    required this.knowledgeBasePath,
    required this.knowledgeBaseType,
    required this.demoDocumentCount,
    required this.userDocumentCount,
    required this.llmAvailable,
    required this.qaMode,
    this.lastUpdated,
  });

  final int documentCount;
  final int chunkCount;
  final IndexStatus indexStatus;
  final String retrievalMethod;
  final bool isAvailable;
  final String knowledgeBasePath;
  final KnowledgeBaseType knowledgeBaseType;
  final int demoDocumentCount;
  final int userDocumentCount;
  final bool llmAvailable;
  final QaMode qaMode;
  final DateTime? lastUpdated;

  /// 是否包含演示资料(用于显示"仿真校园演示资料"声明)。
  bool get hasDemoDocuments => demoDocumentCount > 0;

  @override
  List<Object?> get props => [
        documentCount,
        chunkCount,
        indexStatus,
        retrievalMethod,
        isAvailable,
        knowledgeBasePath,
        knowledgeBaseType,
        demoDocumentCount,
        userDocumentCount,
        llmAvailable,
        qaMode,
        lastUpdated,
      ];
}

/// 文档摘要 — 对齐后端 `DocumentSummary` schema。
class KnowledgeDocumentSummary extends Equatable {
  const KnowledgeDocumentSummary({
    required this.documentId,
    required this.title,
    required this.contentHash,
    required this.isOfficial,
    required this.isExpired,
    required this.isDemo,
    required this.importedAt,
    this.sourceDepartment,
    this.sourceType,
    this.originalFilename,
    this.publishedAt,
    this.updatedAt,
    this.effectiveFrom,
    this.effectiveTo,
    this.version,
    this.applicableStudents,
    this.fileSize,
    this.fileExt,
  });

  final String documentId;
  final String title;
  final String contentHash;
  final bool isOfficial;
  final bool isExpired;
  final bool isDemo;
  final DateTime importedAt;
  final String? sourceDepartment;
  final String? sourceType;
  final String? originalFilename;
  final DateTime? publishedAt;
  final DateTime? updatedAt;
  final DateTime? effectiveFrom;
  final DateTime? effectiveTo;
  final String? version;
  final String? applicableStudents;
  final int? fileSize;
  final String? fileExt;

  /// 文档来源类型展示文本。
  String get sourceTypeLabel {
    switch (sourceType?.toLowerCase()) {
      case 'official':
        return '官方文件';
      case 'notice':
        return '校园通知';
      case 'guide':
        return '办事指南';
      case 'policy':
        return '制度文件';
      default:
        return sourceType ?? '未分类';
    }
  }

  /// 文档大小展示文本。
  String get fileSizeLabel {
    if (fileSize == null) return '';
    final kb = fileSize! / 1024;
    if (kb < 1024) return '${kb.toStringAsFixed(1)} KB';
    return '${(kb / 1024).toStringAsFixed(2)} MB';
  }

  @override
  List<Object?> get props => [
        documentId,
        title,
        contentHash,
        isOfficial,
        isExpired,
        isDemo,
        importedAt,
        sourceDepartment,
        sourceType,
        originalFilename,
        publishedAt,
        updatedAt,
        effectiveFrom,
        effectiveTo,
        version,
        applicableStudents,
        fileSize,
        fileExt,
      ];
}

/// 上传状态(用于 UI 状态机)。
enum UploadStatus {
  /// 等待上传
  idle,

  /// 上传中
  uploading,

  /// 正在解析
  parsing,

  /// 正在建立索引
  indexing,

  /// 上传完成
  completed,

  /// 上传失败
  failed,
}

/// 上传进度信息。
class UploadProgress extends Equatable {
  const UploadProgress({
    required this.status,
    this.message,
    this.errorCode,
    this.documentId,
  });

  final UploadStatus status;
  final String? message;
  final String? errorCode;
  final String? documentId;

  bool get isTerminal =>
      status == UploadStatus.completed || status == UploadStatus.failed;
  bool get isInProgress =>
      status == UploadStatus.uploading ||
      status == UploadStatus.parsing ||
      status == UploadStatus.indexing;

  @override
  List<Object?> get props => [status, message, errorCode, documentId];
}

/// 重建索引进度。
class RebuildProgress extends Equatable {
  const RebuildProgress({
    required this.inProgress,
    this.chunkCount,
    this.documentCount,
    this.error,
  });

  final bool inProgress;
  final int? chunkCount;
  final int? documentCount;
  final String? error;

  @override
  List<Object?> get props => [inProgress, chunkCount, documentCount, error];
}

/// 数据清理动作。
enum DataManagementAction {
  clearChatHistory('clear_chat_history', '清除聊天记录'),
  clearUserTasks('clear_user_tasks', '清除用户待办'),
  deleteUserDocuments('delete_user_documents', '删除用户导入的知识库文档'),
  restoreDemoDocuments('restore_demo_documents', '恢复仿真演示资料'),
  resetMockDemoData('reset_mock_demo_data', '重置 Mock 演示数据');

  const DataManagementAction(this.code, this.displayName);
  final String code;
  final String displayName;
}

/// 数据清理结果。
class DataManagementResult extends Equatable {
  const DataManagementResult({
    required this.action,
    required this.success,
    required this.message,
    this.affectedCount = 0,
  });

  final DataManagementAction action;
  final bool success;
  final String message;
  final int affectedCount;

  @override
  List<Object?> get props => [action, success, message, affectedCount];
}

/// 上传文档时的元数据(对应后端 Form 字段)。
///
/// 注意:此类是数据模型,放在 models 目录;[KnowledgeManagementService] 接口
/// 在 `service_interfaces.dart` 中通过 `import '../models/models.dart'` 引用。
class KnowledgeDocumentMetadata {
  const KnowledgeDocumentMetadata({
    this.title,
    this.sourceDepartment,
    this.sourceType,
    this.publishedAt,
    this.updatedAt,
    this.effectiveFrom,
    this.effectiveTo,
    this.version,
    this.applicableStudents,
    this.isOfficial = false,
  });

  final String? title;
  final String? sourceDepartment;
  final String? sourceType;
  final DateTime? publishedAt;
  final DateTime? updatedAt;
  final DateTime? effectiveFrom;
  final DateTime? effectiveTo;
  final String? version;
  final String? applicableStudents;
  final bool isOfficial;

  /// 转换为后端 Form 字段(String 化的日期)。
  Map<String, String?> toFormFields() {
    String? fmt(DateTime? d) => d?.toUtc().toIso8601String();
    return {
      'title': title,
      'source_department': sourceDepartment,
      'source_type': sourceType,
      'published_at': fmt(publishedAt),
      'updated_at': fmt(updatedAt),
      'effective_from': fmt(effectiveFrom),
      'effective_to': fmt(effectiveTo),
      'version': version,
      'applicable_students': applicableStudents,
      'is_official': isOfficial ? 'true' : 'false',
    };
  }
}
