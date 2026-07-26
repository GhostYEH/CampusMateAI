import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/services/service_interfaces.dart';

/// 重复通知检测结果展示。
///
/// 当 [DuplicateCheckResult.isDuplicate] 为 true 时显示,列出命中的已存在通知。
/// 不阻止用户保存 — 仅提示"可能重复",由用户人工决定。
class DuplicateWarningBanner extends StatelessWidget {
  const DuplicateWarningBanner({
    super.key,
    required this.result,
    required this.onDismiss,
  });

  final DuplicateCheckResult result;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    if (!result.isDuplicate) return const SizedBox.shrink();

    return AppCard(
      borderColor: AppColors.warningSubtle,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.content_copy_rounded,
                size: 18,
                color: AppColors.warning,
              ),
              const SizedBox(width: 6),
              const Expanded(
                child: Text('可能存在重复通知', style: AppTypography.subtitle),
              ),
              IconButton(
                icon: const Icon(Icons.close_rounded, size: 16),
                onPressed: onDismiss,
                visualDensity: VisualDensity.compact,
                tooltip: '忽略提示',
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            result.note.isNotEmpty
                ? result.note
                : '检测到与已保存的待办可能重复,仅作提示,不会自动覆盖。',
            style: AppTypography.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 10),
          for (final match in result.matches.take(3))
            _DuplicateMatchTile(match: match),
          if (result.matches.length > 3)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                '还有 ${result.matches.length - 3} 条可能重复...',
                style: AppTypography.caption.copyWith(
                  color: AppColors.textTertiary,
                  fontSize: 11,
                ),
              ),
            ),
          const SizedBox(height: 8),
          Row(
            children: [
              _PillButton(
                label: '仍要保存',
                icon: Icons.check_rounded,
                isPrimary: true,
                onTap: onDismiss,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _DuplicateMatchTile extends StatelessWidget {
  const _DuplicateMatchTile({required this.match});

  final DuplicateMatch match;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.warningSubtle, width: 0.6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  match.title.isEmpty ? '未命名待办' : match.title,
                  style: AppTypography.label.copyWith(fontSize: 12),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (match.sourceName != null)
                Flexible(
                  child: Padding(
                    padding: const EdgeInsets.only(left: 6),
                    child: Text(
                      match.sourceName!,
                      style: AppTypography.caption.copyWith(
                        fontSize: 10,
                        color: AppColors.textTertiary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              if (match.deadline != null)
                _ReasonChip(
                  icon: Icons.event_rounded,
                  text: _formatDate(match.deadline!),
                ),
              for (final reason in match.reasons)
                _ReasonChip(
                  icon: Icons.link_rounded,
                  text: _reasonLabel(reason),
                ),
              _ReasonChip(
                icon: Icons.percent_rounded,
                text: '相似度 ${(match.similarity * 100).round()}%',
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _reasonLabel(String reason) {
    switch (reason) {
      case 'content_similarity':
        return '内容相似';
      case 'content_hash':
        return '原文一致';
      case 'source_name':
        return '来源相同';
      case 'deadline':
        return '截止时间接近';
      case 'task':
        return '任务名相同';
      default:
        return reason;
    }
  }

  String _formatDate(DateTime dt) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${dt.year}-${two(dt.month)}-${two(dt.day)}';
  }
}

class _ReasonChip extends StatelessWidget {
  const _ReasonChip({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 10, color: AppColors.textTertiary),
          const SizedBox(width: 3),
          Text(
            text,
            style: AppTypography.caption.copyWith(
              fontSize: 10,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }
}

class _PillButton extends StatelessWidget {
  const _PillButton({
    required this.label,
    required this.icon,
    required this.isPrimary,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool isPrimary;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = isPrimary ? AppColors.primary : AppColors.textSecondary;
    final bg = isPrimary ? AppColors.primarySubtle : AppColors.bgSurface;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(AppRadius.xs),
          border: Border.all(color: color, width: 0.6),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 12, color: color),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTypography.label.copyWith(fontSize: 10.5, color: color),
            ),
          ],
        ),
      ),
    );
  }
}
