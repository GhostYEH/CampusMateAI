import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/knowledge.dart';
import '../../../data/services/api/api_client.dart';
import 'widgets/knowledge_document_tile.dart';
import 'widgets/knowledge_status_card.dart';

/// 知识库管理页面 — 状态、文档列表、上传、删除、重建索引。
///
/// 设计原则(遵循 frontend-design skill 的"晨曦校园"方向):
/// - 状态卡片置顶,演示资料声明始终可见(只要包含演示资料)
/// - 操作按钮分组:上传 / 重建索引 / 恢复演示资料
/// - 错误状态温和,提供重试,不清空已选文件或已填元数据
/// - 上传过程状态机驱动:等待 → 上传中 → 解析中 → 索引中 → 完成/失败
/// - 失败显示后端返回的具体可理解原因
class KnowledgeManagementPage extends ConsumerStatefulWidget {
  const KnowledgeManagementPage({super.key});

  @override
  ConsumerState<KnowledgeManagementPage> createState() =>
      _KnowledgeManagementPageState();
}

class _KnowledgeManagementPageState
    extends ConsumerState<KnowledgeManagementPage> {
  KnowledgeStatusInfo? _status;
  List<KnowledgeDocumentSummary> _documents = [];
  bool _loading = true;
  String? _loadError;

  // 上传状态
  UploadProgress? _uploadProgress;
  Uint8List? _pendingBytes;
  String? _pendingFilename;

  // 重建索引状态
  RebuildProgress? _rebuildProgress;

  // 删除中的文档 ID
  String? _deletingId;

  // 上传对话框元数据控制器
  final _titleCtrl = TextEditingController();
  final _deptCtrl = TextEditingController();
  final _versionCtrl = TextEditingController();
  final _audienceCtrl = TextEditingController();
  String? _sourceType = 'guide';
  bool _isOfficial = false;
  DateTime? _publishedAt;

  @override
  void initState() {
    super.initState();
    _loadAll();
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _deptCtrl.dispose();
    _versionCtrl.dispose();
    _audienceCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final service = ref.read(knowledgeManagementProvider);
      final status = await service.getStatus();
      final docs = await service.listDocuments();
      if (!mounted) return;
      setState(() {
        _status = status;
        _documents = docs;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _loadError = e.message;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadError = '加载失败:$e';
        _loading = false;
      });
    }
  }

  Future<void> _refreshStatusOnly() async {
    try {
      final service = ref.read(knowledgeManagementProvider);
      final status = await service.getStatus();
      if (!mounted) return;
      setState(() => _status = status);
    } catch (_) {
      // 静默失败 — 状态刷新不应阻断主流程
    }
  }

  // ============ 上传流程 ============

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['md', 'txt', 'docx', 'pdf'],
        withData: true,
      );
      if (result == null || result.files.isEmpty) return;
      final file = result.files.single;
      final bytes = file.bytes;
      if (bytes == null) {
        _showSnack('无法读取文件内容,请重试');
        return;
      }
      setState(() {
        _pendingBytes = bytes;
        _pendingFilename = file.name;
        _titleCtrl.text = _defaultTitleFromFilename(file.name);
      });
      _showUploadDialog();
    } catch (e) {
      _showSnack('选择文件失败:$e');
    }
  }

  String _defaultTitleFromFilename(String name) {
    final dot = name.lastIndexOf('.');
    if (dot <= 0) return name;
    return name.substring(0, dot);
  }

  void _showUploadDialog() {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => _UploadMetadataDialog(
        filename: _pendingFilename ?? '',
        titleCtrl: _titleCtrl,
        deptCtrl: _deptCtrl,
        versionCtrl: _versionCtrl,
        audienceCtrl: _audienceCtrl,
        sourceType: _sourceType ?? 'guide',
        isOfficial: _isOfficial,
        publishedAt: _publishedAt,
        onSourceTypeChanged: (v) => _sourceType = v,
        onOfficialChanged: (v) => _isOfficial = v,
        onPickPublishedAt: _pickPublishedAt,
        onCancel: () {
          Navigator.pop(context);
          _resetPendingUpload();
        },
        onConfirm: () {
          Navigator.pop(context);
          _performUpload();
        },
      ),
    );
  }

  Future<void> _pickPublishedAt() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _publishedAt ?? now,
      firstDate: DateTime(now.year - 10),
      lastDate: DateTime(now.year + 1),
      locale: const Locale('zh'),
    );
    if (picked != null) {
      setState(() => _publishedAt = picked);
    }
  }

  void _resetPendingUpload() {
    setState(() {
      _pendingBytes = null;
      _pendingFilename = null;
      _uploadProgress = null;
      _titleCtrl.clear();
      _deptCtrl.clear();
      _versionCtrl.clear();
      _audienceCtrl.clear();
      _sourceType = 'guide';
      _isOfficial = false;
      _publishedAt = null;
    });
  }

  Future<void> _performUpload() async {
    final bytes = _pendingBytes;
    final filename = _pendingFilename;
    if (bytes == null || filename == null) return;

    final metadata = KnowledgeDocumentMetadata(
      title: _titleCtrl.text.trim().isEmpty ? null : _titleCtrl.text.trim(),
      sourceDepartment:
          _deptCtrl.text.trim().isEmpty ? null : _deptCtrl.text.trim(),
      sourceType: _sourceType,
      publishedAt: _publishedAt,
      version:
          _versionCtrl.text.trim().isEmpty ? null : _versionCtrl.text.trim(),
      applicableStudents:
          _audienceCtrl.text.trim().isEmpty ? null : _audienceCtrl.text.trim(),
      isOfficial: _isOfficial,
    );

    setState(() {
      _uploadProgress = const UploadProgress(
        status: UploadStatus.uploading,
        message: '准备上传...',
      );
    });

    try {
      final service = ref.read(knowledgeManagementProvider);
      final doc = await service.uploadDocument(
        bytes: bytes,
        originalFilename: filename,
        metadata: metadata,
        onProgress: (p) {
          if (!mounted) return;
          setState(() => _uploadProgress = p);
        },
      );
      if (!mounted) return;
      // 上传成功 — 刷新列表
      await _loadAll();
      if (!mounted) return;
      setState(() => _uploadProgress = null);
      _resetPendingUpload();
      _showSnack('文档已上传:${doc.title}');
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _uploadProgress = UploadProgress(
          status: UploadStatus.failed,
          message: e.message,
          errorCode: e.code,
        );
      });
      _showUploadFailureSheet(e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _uploadProgress = UploadProgress(
          status: UploadStatus.failed,
          message: '上传失败:$e',
        );
      });
      _showUploadFailureSheet('上传失败:$e');
    }
  }

  void _showUploadFailureSheet(String message) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.lg)),
      ),
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(
                    Icons.error_outline_rounded,
                    color: AppColors.danger,
                    size: 20,
                  ),
                  SizedBox(width: 8),
                  Text('上传失败', style: AppTypography.subtitle),
                ],
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.dangerSubtle.withValues(alpha: 0.4),
                  borderRadius: BorderRadius.circular(AppRadius.xs),
                ),
                child: Text(
                  message,
                  style: AppTypography.caption.copyWith(
                    fontSize: 11.5,
                    color: AppColors.textSecondary,
                    height: 1.5,
                  ),
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                '当前仅支持包含文本层的 PDF,纯扫描 PDF 暂不支持文字识别。',
                style: AppTypography.caption,
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () {
                      Navigator.pop(context);
                      _resetPendingUpload();
                    },
                    child: const Text('取消'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: () {
                      Navigator.pop(context);
                      _performUpload();
                    },
                    child: const Text('重试'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ============ 删除流程 ============

  Future<void> _confirmDelete(KnowledgeDocumentSummary doc) async {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除文档'),
        content: Text(
          '将删除文档:"${doc.title}"\n'
          '此操作不可恢复,删除后该文档将不再参与检索。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () {
              Navigator.pop(context);
              _performDelete(doc);
            },
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  Future<void> _performDelete(KnowledgeDocumentSummary doc) async {
    setState(() => _deletingId = doc.documentId);
    try {
      final service = ref.read(knowledgeManagementProvider);
      final ok = await service.deleteDocument(doc.documentId);
      if (!mounted) return;
      if (ok) {
        // 立即从本地列表移除,避免与后端状态不一致
        setState(() {
          _documents =
              _documents.where((d) => d.documentId != doc.documentId).toList();
          _deletingId = null;
        });
        await _refreshStatusOnly();
        if (!mounted) return;
        _showSnack('已删除:${doc.title}');
      } else {
        setState(() => _deletingId = null);
        _showSnack('删除失败:后端返回未成功');
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _deletingId = null);
      _showSnack('删除失败:${e.message}');
    } catch (e) {
      if (!mounted) return;
      setState(() => _deletingId = null);
      _showSnack('删除失败:$e');
    }
  }

  // ============ 重建索引 ============

  Future<void> _confirmRebuild() async {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('重建索引'),
        content: const Text(
          '重建索引不会删除原始知识库文档,但会重新生成用于检索的内容分块。\n\n'
          '此操作期间检索功能可能短暂不可用。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(context);
              _performRebuild();
            },
            child: const Text('重建'),
          ),
        ],
      ),
    );
  }

  Future<void> _performRebuild() async {
    if (_rebuildProgress?.inProgress == true) return;
    setState(() {
      _rebuildProgress = const RebuildProgress(inProgress: true);
    });
    try {
      final service = ref.read(knowledgeManagementProvider);
      final chunks = await service.rebuildIndex(
        onProgress: (p) {
          if (!mounted) return;
          setState(() => _rebuildProgress = p);
        },
      );
      if (!mounted) return;
      await _refreshStatusOnly();
      if (!mounted) return;
      setState(() => _rebuildProgress = null);
      _showSnack('索引已重建,共 $chunks 段分块');
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _rebuildProgress = RebuildProgress(inProgress: false, error: e.message);
      });
      _showSnack('重建失败:${e.message}');
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _rebuildProgress = RebuildProgress(inProgress: false, error: '重建失败:$e');
      });
      _showSnack('重建失败:$e');
    }
  }

  // ============ 恢复演示资料 ============

  Future<void> _confirmRestoreDemo() async {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('恢复仿真演示资料'),
        content: const Text(
          '将恢复内置的仿真校园演示资料。\n\n'
          '基于内容哈希去重,不会覆盖你已导入的资料。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(context);
              _performRestoreDemo();
            },
            child: const Text('恢复'),
          ),
        ],
      ),
    );
  }

  Future<void> _performRestoreDemo() async {
    try {
      final service = ref.read(knowledgeManagementProvider);
      final added = await service.restoreDemoDocuments();
      if (!mounted) return;
      await _loadAll();
      if (!mounted) return;
      _showSnack(added > 0 ? '已恢复 $added 份演示资料' : '演示资料已存在,无新增');
    } on ApiException catch (e) {
      if (!mounted) return;
      _showSnack('恢复失败:${e.message}');
    } catch (e) {
      if (!mounted) return;
      _showSnack('恢复失败:$e');
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), duration: const Duration(seconds: 2)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final config = ref.watch(appConfigProvider);
    final isMockMode = config.useMockBackend;

    return Scaffold(
      backgroundColor: AppColors.bgBase,
      appBar: AppBar(
        title: const Text('知识库管理'),
        backgroundColor: AppColors.bgSurface,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        actions: [
          IconButton(
            tooltip: '刷新',
            onPressed: _loading ? null : _loadAll,
            icon: const Icon(Icons.refresh_rounded, size: 22),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: SafeArea(
        child: _buildBody(isMockMode),
      ),
      floatingActionButton: _buildFab(),
    );
  }

  Widget _buildBody(bool isMockMode) {
    if (_loading) {
      return const LoadingView(label: '加载知识库状态...');
    }
    if (_loadError != null) {
      return ErrorStateView(
        message: _loadError!,
        onRetry: _loadAll,
      );
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        12,
        AppSpacing.edge,
        96,
      ),
      children: [
        if (_status != null)
          StaggeredEnter(
            child: KnowledgeStatusCard(
              status: _status!,
              isMockMode: isMockMode,
            ),
          ),
        const SizedBox(height: 12),
        StaggeredEnter(
          delay: const Duration(milliseconds: 60),
          child: _ActionsBar(
            onUpload: _pickFile,
            onRebuild:
                _rebuildProgress?.inProgress == true ? null : _confirmRebuild,
            onRestoreDemo: _confirmRestoreDemo,
            rebuildInProgress: _rebuildProgress?.inProgress == true,
          ),
        ),
        if (_uploadProgress != null && _uploadProgress!.isInProgress) ...[
          const SizedBox(height: 12),
          StaggeredEnter(
            child: _UploadProgressCard(progress: _uploadProgress!),
          ),
        ],
        if (_rebuildProgress?.inProgress == true ||
            _rebuildProgress?.error != null) ...[
          const SizedBox(height: 12),
          StaggeredEnter(
            child: _RebuildProgressCard(progress: _rebuildProgress!),
          ),
        ],
        const SizedBox(height: 16),
        StaggeredEnter(
          delay: const Duration(milliseconds: 120),
          child: _DocumentsSection(
            documents: _documents,
            deletingId: _deletingId,
            onDelete: _confirmDelete,
          ),
        ),
      ],
    );
  }

  Widget? _buildFab() {
    if (_loading || _loadError != null) return null;
    return FloatingActionButton.extended(
      onPressed: _pickFile,
      icon: const Icon(Icons.upload_file_rounded),
      label: const Text('上传文档'),
      backgroundColor: AppColors.primary,
      foregroundColor: AppColors.onPrimary,
    );
  }
}

// ============================================================
// 子组件
// ============================================================

class _ActionsBar extends StatelessWidget {
  const _ActionsBar({
    required this.onUpload,
    required this.onRebuild,
    required this.onRestoreDemo,
    required this.rebuildInProgress,
  });

  final VoidCallback onUpload;
  final VoidCallback? onRebuild;
  final VoidCallback onRestoreDemo;
  final bool rebuildInProgress;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          Expanded(
            child: _ActionChip(
              icon: Icons.upload_file_rounded,
              label: '上传文档',
              hint: '支持 MD / TXT / DOCX / 文本型 PDF',
              onTap: onUpload,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _ActionChip(
              icon: rebuildInProgress
                  ? Icons.hourglass_top_rounded
                  : Icons.refresh_rounded,
              label: rebuildInProgress ? '重建中' : '重建索引',
              hint: '重新生成分块,不删除原文',
              onTap: onRebuild,
              color: AppColors.accent,
              disabled: rebuildInProgress,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _ActionChip(
              icon: Icons.restore_rounded,
              label: '恢复演示',
              hint: '恢复仿真校园资料',
              onTap: onRestoreDemo,
              color: AppColors.success,
            ),
          ),
        ],
      ),
    );
  }
}

class _ActionChip extends StatelessWidget {
  const _ActionChip({
    required this.icon,
    required this.label,
    required this.hint,
    required this.onTap,
    required this.color,
    this.disabled = false,
  });

  final IconData icon;
  final String label;
  final String hint;
  final VoidCallback? onTap;
  final Color color;
  final bool disabled;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final effectiveColor = disabled ? c.textDisabled : color;
    return InkWell(
      onTap: disabled ? null : onTap,
      borderRadius: BorderRadius.circular(AppRadius.sm),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
        decoration: BoxDecoration(
          color: effectiveColor.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(AppRadius.sm),
          border: Border.all(
            color: effectiveColor.withValues(alpha: 0.3),
            width: 0.6,
          ),
        ),
        child: Column(
          children: [
            Icon(icon, size: 18, color: effectiveColor),
            const SizedBox(height: 4),
            Text(
              label,
              style: AppTypography.label.copyWith(
                fontSize: 11,
                color: effectiveColor,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 2),
            Text(
              hint,
              style: AppTypography.overline.copyWith(fontSize: 9),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

class _UploadProgressCard extends StatelessWidget {
  const _UploadProgressCard({required this.progress});
  final UploadProgress progress;

  @override
  Widget build(BuildContext context) {
    final (label, icon, color) = switch (progress.status) {
      UploadStatus.idle => (
          '等待上传',
          Icons.hourglass_empty_rounded,
          AppColors.textTertiary
        ),
      UploadStatus.uploading => (
          '上传中',
          Icons.cloud_upload_rounded,
          AppColors.primary
        ),
      UploadStatus.parsing => (
          '正在解析',
          Icons.find_in_page_rounded,
          AppColors.accent
        ),
      UploadStatus.indexing => (
          '建立索引',
          Icons.auto_fix_high_rounded,
          AppColors.info
        ),
      UploadStatus.completed => (
          '上传完成',
          Icons.check_circle_rounded,
          AppColors.success
        ),
      UploadStatus.failed => (
          '上传失败',
          Icons.error_outline_rounded,
          AppColors.danger
        ),
    };
    return AppCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          if (progress.status != UploadStatus.completed &&
              progress.status != UploadStatus.failed)
            SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: color,
              ),
            )
          else
            Icon(icon, size: 18, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: AppTypography.bodyStrong),
                if (progress.message != null)
                  Text(
                    progress.message!,
                    style: AppTypography.caption.copyWith(fontSize: 11),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RebuildProgressCard extends StatelessWidget {
  const _RebuildProgressCard({required this.progress});
  final RebuildProgress progress;

  @override
  Widget build(BuildContext context) {
    final hasError = progress.error != null;
    return AppCard(
      padding: const EdgeInsets.all(14),
      backgroundColor: hasError
          ? AppColors.dangerSubtle.withValues(alpha: 0.3)
          : AppColors.accentSubtle.withValues(alpha: 0.3),
      child: Row(
        children: [
          if (progress.inProgress)
            const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppColors.accent,
              ),
            )
          else
            Icon(
              hasError
                  ? Icons.error_outline_rounded
                  : Icons.check_circle_rounded,
              size: 18,
              color: hasError ? AppColors.danger : AppColors.success,
            ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  hasError
                      ? '索引重建失败'
                      : progress.inProgress
                          ? '正在重建索引...'
                          : '索引已重建',
                  style: AppTypography.bodyStrong,
                ),
                if (progress.error != null)
                  Text(
                    progress.error!,
                    style: AppTypography.caption.copyWith(
                      fontSize: 11,
                      color: AppColors.danger,
                    ),
                  )
                else if (progress.chunkCount != null)
                  Text(
                    '共 ${progress.documentCount ?? 0} 份文档,${progress.chunkCount} 段分块',
                    style: AppTypography.caption.copyWith(fontSize: 11),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DocumentsSection extends StatelessWidget {
  const _DocumentsSection({
    required this.documents,
    required this.deletingId,
    required this.onDelete,
  });

  final List<KnowledgeDocumentSummary> documents;
  final String? deletingId;
  final void Function(KnowledgeDocumentSummary) onDelete;

  @override
  Widget build(BuildContext context) {
    if (documents.isEmpty) {
      return const EmptyStateView(
        icon: Icons.menu_book_rounded,
        title: '知识库为空',
        message: '请先导入学校官方通知、制度文件或办事指南。'
            'AI 导员只能依据已导入资料回答校园事务问题。',
      );
    }

    // 分组:演示资料在前,用户导入在后
    final demoDocs = documents.where((d) => d.isDemo).toList();
    final userDocs = documents.where((d) => !d.isDemo).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            '已导入文档(${documents.length})',
            style: AppTypography.label,
          ),
        ),
        if (demoDocs.isNotEmpty) ...[
          _GroupLabel(label: '仿真校园演示资料(${demoDocs.length})'),
          const SizedBox(height: 6),
          for (final doc in demoDocs)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: KnowledgeDocumentTile(
                document: doc,
                onDelete: () => onDelete(doc),
                isDeleting: deletingId == doc.documentId,
              ),
            ),
        ],
        if (userDocs.isNotEmpty) ...[
          if (demoDocs.isNotEmpty) const SizedBox(height: 8),
          _GroupLabel(label: '用户导入资料(${userDocs.length})'),
          const SizedBox(height: 6),
          for (final doc in userDocs)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: KnowledgeDocumentTile(
                document: doc,
                onDelete: () => onDelete(doc),
                isDeleting: deletingId == doc.documentId,
              ),
            ),
        ],
      ],
    );
  }
}

class _GroupLabel extends StatelessWidget {
  const _GroupLabel({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Text(
        label,
        style: AppTypography.overline.copyWith(fontSize: 10),
      ),
    );
  }
}

// ============================================================
// 上传元数据对话框
// ============================================================

class _UploadMetadataDialog extends StatelessWidget {
  const _UploadMetadataDialog({
    required this.filename,
    required this.titleCtrl,
    required this.deptCtrl,
    required this.versionCtrl,
    required this.audienceCtrl,
    required this.sourceType,
    required this.isOfficial,
    required this.publishedAt,
    required this.onSourceTypeChanged,
    required this.onOfficialChanged,
    required this.onPickPublishedAt,
    required this.onCancel,
    required this.onConfirm,
  });

  final String filename;
  final TextEditingController titleCtrl;
  final TextEditingController deptCtrl;
  final TextEditingController versionCtrl;
  final TextEditingController audienceCtrl;
  final String sourceType;
  final bool isOfficial;
  final DateTime? publishedAt;
  final ValueChanged<String> onSourceTypeChanged;
  final ValueChanged<bool> onOfficialChanged;
  final VoidCallback onPickPublishedAt;
  final VoidCallback onCancel;
  final VoidCallback onConfirm;

  static const _sourceTypes = <String, String>{
    'guide': '办事指南',
    'notice': '校园通知',
    'policy': '制度文件',
    'official': '官方文件',
  };

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('上传文档'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _FilenameChip(filename: filename),
            const SizedBox(height: 12),
            const _FieldLabel(label: '标题'),
            TextField(
              controller: titleCtrl,
              decoration: const InputDecoration(
                hintText: '文档标题(留空则使用文件名)',
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),
            const _FieldLabel(label: '来源部门'),
            TextField(
              controller: deptCtrl,
              decoration: const InputDecoration(
                hintText: '如:教务处 / 学生处',
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),
            const _FieldLabel(label: '来源类型'),
            DropdownButton<String>(
              value: sourceType,
              isExpanded: true,
              items: [
                for (final entry in _sourceTypes.entries)
                  DropdownMenuItem(
                    value: entry.key,
                    child: Text(entry.value),
                  ),
              ],
              onChanged: (v) {
                if (v != null) onSourceTypeChanged(v);
              },
            ),
            const SizedBox(height: 10),
            const _FieldLabel(label: '发布日期'),
            InkWell(
              onTap: onPickPublishedAt,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  border: Border.all(color: AppColors.border),
                  borderRadius: BorderRadius.circular(AppRadius.xs),
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.event_outlined,
                      size: 16,
                      color: AppColors.textSecondary,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        publishedAt == null
                            ? '选择发布日期(可选)'
                            : '${publishedAt!.year}-${publishedAt!.month.toString().padLeft(2, '0')}-${publishedAt!.day.toString().padLeft(2, '0')}',
                        style: AppTypography.body.copyWith(
                          fontSize: 13,
                          color: publishedAt == null
                              ? AppColors.textTertiary
                              : AppColors.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            const _FieldLabel(label: '版本号'),
            TextField(
              controller: versionCtrl,
              decoration: const InputDecoration(
                hintText: '如:v1.0 / 2024 修订版',
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),
            const _FieldLabel(label: '适用对象'),
            TextField(
              controller: audienceCtrl,
              decoration: const InputDecoration(
                hintText: '如:2024 级本科生 / 全体在校生',
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: const Text('官方资料', style: AppTypography.body),
              value: isOfficial,
              onChanged: onOfficialChanged,
            ),
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.warningSubtle.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(AppRadius.xs),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.info_outline_rounded,
                    size: 13,
                    color: AppColors.warning,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      '当前仅支持包含文本层的 PDF,纯扫描 PDF 暂不支持文字识别。',
                      style: AppTypography.caption.copyWith(fontSize: 11),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: onCancel, child: const Text('取消')),
        FilledButton(onPressed: onConfirm, child: const Text('上传')),
      ],
    );
  }
}

class _FilenameChip extends StatelessWidget {
  const _FilenameChip({required this.filename});
  final String filename;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.primarySubtle,
        borderRadius: BorderRadius.circular(AppRadius.xs),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.insert_drive_file_rounded,
            size: 14,
            color: AppColors.primary,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              filename,
              style: AppTypography.caption.copyWith(
                fontSize: 11.5,
                color: AppColors.primary,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}

class _FieldLabel extends StatelessWidget {
  const _FieldLabel({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text(label, style: AppTypography.label.copyWith(fontSize: 11)),
    );
  }
}
