import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../data/models/chat.dart';

/// 参考来源区 — 模拟资料来源列表,Mock 阶段标注"模拟"。
class SourceReferencePanel extends StatelessWidget {
  const SourceReferencePanel({super.key, required this.sources});

  final List<KnowledgeSource> sources;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.bgSunken,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: AppColors.border, width: 0.6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.menu_book_rounded,
                size: 13,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                '参考来源(模拟)',
                style: AppTypography.label.copyWith(fontSize: 10.5),
              ),
            ],
          ),
          const SizedBox(height: 8),
          for (var i = 0; i < sources.length; i++) ...[
            _SourceItem(source: sources[i]),
            if (i != sources.length - 1) const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _SourceItem extends StatelessWidget {
  const _SourceItem({required this.source});

  final KnowledgeSource source;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          source.title,
          style: AppTypography.bodyStrong.copyWith(fontSize: 12.5),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 3),
        Wrap(
          spacing: 5,
          runSpacing: 2,
          children: [
            _tag(source.source),
            _tag('更新于 ${AppDateUtils.formatDate(source.updatedAt)}'),
          ],
        ),
        if (source.snippet != null && source.snippet!.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            source.snippet!,
            style: AppTypography.caption.copyWith(
              fontSize: 11.5,
              color: AppColors.textSecondary,
            ),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ],
    );
  }

  Widget _tag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AppColors.border, width: 0.5),
      ),
      child: Text(text, style: AppTypography.overline.copyWith(fontSize: 9.5)),
    );
  }
}

/// 无可靠资料提示 — 引导用户咨询辅导员或学院办公室。
///
/// 体现科学边界:不伪造学校政策。
class NoSourcesHint extends StatelessWidget {
  const NoSourcesHint({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: AppColors.warningSubtle, width: 0.6),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.info_outline_rounded,
            size: 14,
            color: AppColors.warning,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              '该问题暂无可靠资料,建议咨询辅导员或学院办公室',
              style: AppTypography.caption.copyWith(
                fontSize: 11.5,
                color: AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
