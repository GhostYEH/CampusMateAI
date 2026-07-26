import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/knowledge.dart';

/// 单份文档卡片 — 展示元数据 + 折叠的详情。
///
/// 设计原则:
/// - 仿真资料用 warning 暖色徽章,用户导入用 primary 冷色徽章
/// - 官方/过期徽章清晰区分
/// - 默认折叠,点击展开查看完整元数据
class KnowledgeDocumentTile extends StatefulWidget {
  const KnowledgeDocumentTile({
    super.key,
    required this.document,
    this.onDelete,
    this.isDeleting = false,
  });

  final KnowledgeDocumentSummary document;
  final VoidCallback? onDelete;
  final bool isDeleting;

  @override
  State<KnowledgeDocumentTile> createState() => _KnowledgeDocumentTileState();
}

class _KnowledgeDocumentTileState extends State<KnowledgeDocumentTile> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final doc = widget.document;
    return AppCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(AppRadius.lg),
              topRight: const Radius.circular(AppRadius.lg),
              bottomLeft:
                  _expanded ? Radius.zero : const Radius.circular(AppRadius.lg),
              bottomRight:
                  _expanded ? Radius.zero : const Radius.circular(AppRadius.lg),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _DocTypeIcon(fileExt: doc.fileExt ?? 'md'),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          doc.title,
                          style: AppTypography.bodyStrong.copyWith(
                            fontSize: 13,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        Wrap(
                          spacing: 5,
                          runSpacing: 3,
                          children: [
                            _Badge(
                              label: doc.isDemo ? '仿真资料' : '用户导入',
                              color: doc.isDemo
                                  ? AppColors.warning
                                  : AppColors.primary,
                            ),
                            if (doc.isOfficial)
                              const _Badge(
                                label: '官方',
                                color: AppColors.success,
                              ),
                            if (doc.isExpired)
                              const _Badge(
                                label: '已过期',
                                color: AppColors.danger,
                              ),
                            _Badge(
                              label: doc.sourceTypeLabel,
                              color: AppColors.textTertiary,
                              filled: false,
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _metaLine(doc),
                          style: AppTypography.overline.copyWith(
                            fontSize: 10,
                            color: AppColors.textTertiary,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 4),
                  Icon(
                    _expanded
                        ? Icons.keyboard_arrow_up_rounded
                        : Icons.keyboard_arrow_down_rounded,
                    size: 18,
                    color: AppColors.textTertiary,
                  ),
                ],
              ),
            ),
          ),
          if (_expanded) ...[
            const Divider(height: 1, color: AppColors.border),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
              child: _DocumentMetadata(doc: doc),
            ),
            if (widget.onDelete != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
                child: Row(
                  children: [
                    OutlinedButton.icon(
                      onPressed: widget.isDeleting ? null : widget.onDelete,
                      icon: widget.isDeleting
                          ? const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.delete_outline_rounded, size: 16),
                      label: Text(
                        widget.isDeleting ? '删除中...' : '删除文档',
                        style: AppTypography.label.copyWith(fontSize: 11),
                      ),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.danger,
                        side: const BorderSide(color: AppColors.dangerSubtle),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        minimumSize: const Size(0, 32),
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }

  String _metaLine(KnowledgeDocumentSummary doc) {
    final parts = <String>[];
    if (doc.sourceDepartment != null && doc.sourceDepartment!.isNotEmpty) {
      parts.add(doc.sourceDepartment!);
    }
    parts.add('导入于 ${AppDateUtils.formatDate(doc.importedAt)}');
    if (doc.fileSizeLabel.isNotEmpty) parts.add(doc.fileSizeLabel);
    return parts.join(' · ');
  }
}

class _DocTypeIcon extends StatelessWidget {
  const _DocTypeIcon({required this.fileExt});
  final String fileExt;

  @override
  Widget build(BuildContext context) {
    final (icon, color) = switch (fileExt.toLowerCase()) {
      'md' || 'txt' => (Icons.description_rounded, AppColors.primary),
      'pdf' => (Icons.picture_as_pdf_rounded, AppColors.danger),
      'doc' || 'docx' => (Icons.article_rounded, AppColors.info),
      _ => (Icons.insert_drive_file_rounded, AppColors.textTertiary),
    };
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadius.xs),
      ),
      child: Icon(icon, size: 16, color: color),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({
    required this.label,
    required this.color,
    this.filled = true,
  });

  final String label;
  final Color color;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
      decoration: BoxDecoration(
        color: filled ? color.withValues(alpha: 0.12) : Colors.transparent,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color, width: 0.5),
      ),
      child: Text(
        label,
        style: AppTypography.overline.copyWith(fontSize: 9.5, color: color),
      ),
    );
  }
}

class _DocumentMetadata extends StatelessWidget {
  const _DocumentMetadata({required this.doc});
  final KnowledgeDocumentSummary doc;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('文档元数据', style: AppTypography.label.copyWith(fontSize: 10.5)),
        const SizedBox(height: 8),
        _Row(label: '标题', value: doc.title),
        if (doc.originalFilename != null)
          _Row(label: '原始文件名', value: doc.originalFilename!),
        if (doc.sourceDepartment != null)
          _Row(label: '来源部门', value: doc.sourceDepartment!),
        _Row(label: '来源类型', value: doc.sourceTypeLabel),
        if (doc.publishedAt != null)
          _Row(
            label: '发布日期',
            value: AppDateUtils.formatDateFull(doc.publishedAt!),
          ),
        if (doc.version != null) _Row(label: '版本号', value: doc.version!),
        if (doc.applicableStudents != null)
          _Row(label: '适用对象', value: doc.applicableStudents!),
        _Row(
          label: '官方状态',
          value: doc.isOfficial ? '官方资料' : '非官方资料',
        ),
        _Row(
          label: '有效性',
          value: doc.isExpired ? '已过期(仅作历史参考)' : '当前有效',
        ),
        _Row(
          label: '资料类型',
          value: doc.isDemo ? '仿真校园演示资料' : '用户导入资料',
        ),
        if (doc.fileSize != null) _Row(label: '文件大小', value: doc.fileSizeLabel),
        _Row(
          label: '内容哈希',
          value: doc.contentHash.length > 16
              ? '${doc.contentHash.substring(0, 16)}...'
              : doc.contentHash,
        ),
      ],
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 76,
            child: Text(
              label,
              style: AppTypography.overline.copyWith(fontSize: 10.5),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTypography.caption.copyWith(
                fontSize: 11.5,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
