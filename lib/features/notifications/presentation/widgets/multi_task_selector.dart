import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/notice.dart';
import '../../../../data/services/service_interfaces.dart';

/// 多任务抽取结果选择器。
///
/// 当 [MultiExtractResult.tasks] 长度 >= 2 时显示,让用户在多个独立任务间切换。
/// 每个任务以编号 + 任务名 + 截止时间呈现,选中态高亮。
/// 同时展示拆分说明(splitReason)与"需要人工确认"提示。
class MultiTaskSelector extends StatelessWidget {
  const MultiTaskSelector({
    super.key,
    required this.result,
    required this.selectedIndex,
    required this.onSelect,
  });

  final MultiExtractResult result;
  final int selectedIndex;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final tasks = result.tasks;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.call_split_rounded,
                size: 18,
                color: AppColors.accent,
              ),
              const SizedBox(width: 6),
              const Expanded(
                child: Text('已拆分为多个任务', style: AppTypography.subtitle),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.accentSubtle,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${tasks.length} 个任务',
                  style: AppTypography.label.copyWith(
                    fontSize: 11,
                    color: AppColors.accent,
                  ),
                ),
              ),
            ],
          ),
          if (result.splitReason.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              result.splitReason,
              style: AppTypography.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
          if (result.needsUserConfirmation) ...[
            const SizedBox(height: 8),
            _ConfirmationHint(),
          ],
          const SizedBox(height: 12),
          SizedBox(
            height: 72,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: tasks.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, index) {
                final task = tasks[index];
                final selected = index == selectedIndex;
                return _TaskChip(
                  task: task,
                  index: index,
                  selected: selected,
                  onTap: () => onSelect(index),
                );
              },
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '当前编辑第 ${selectedIndex + 1} 个任务,保存后将单独生成一条待办',
            style: AppTypography.caption.copyWith(
              color: AppColors.textTertiary,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}

class _ConfirmationHint extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.warningSubtle, width: 0.6),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.help_outline_rounded,
            size: 14,
            color: AppColors.warning,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              '拆分结果仅供参考,请人工确认各任务字段后再保存',
              style: AppTypography.caption.copyWith(
                fontSize: 11,
                color: AppColors.warning,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TaskChip extends StatelessWidget {
  const _TaskChip({
    required this.task,
    required this.index,
    required this.selected,
    required this.onTap,
  });

  final ExtractedNotice task;
  final int index;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final deadline = task.deadline;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        width: 160,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppColors.primarySubtle : AppColors.bgSurface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.border,
            width: selected ? 1.4 : 0.8,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Row(
              children: [
                Container(
                  width: 18,
                  height: 18,
                  decoration: BoxDecoration(
                    color:
                        selected ? AppColors.primary : AppColors.textTertiary,
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      '${index + 1}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.onPrimary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    task.taskName.isEmpty ? '未命名任务' : task.taskName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.label.copyWith(
                      fontSize: 12,
                      color:
                          selected ? AppColors.primary : AppColors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              deadline != null ? _formatDeadline(deadline) : '未设置截止时间',
              style: AppTypography.caption.copyWith(
                fontSize: 10.5,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatDeadline(DateTime dt) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '截止 ${dt.year}-${two(dt.month)}-${two(dt.day)}';
  }
}
