import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';

/// 截止提醒设置区(通知整理页内嵌使用)。
///
/// 提供开关 + 建议提醒时间(截止前 2 小时 / 截止前 24 小时 / 自定义)。
/// 当未设置截止时间时,提醒开关置灰并显示提示。
class ReminderSection extends StatelessWidget {
  const ReminderSection({
    super.key,
    required this.enabled,
    required this.leadMinutes,
    required this.deadline,
    required this.onToggle,
    required this.onLeadChanged,
  });

  /// 提醒是否启用。
  final bool enabled;

  /// 提前提醒分钟数(120=2h, 1440=24h, 自定义值)。
  final int leadMinutes;

  /// 截止时间(null 表示未设置)。
  final DateTime? deadline;

  /// 切换提醒开关。
  final ValueChanged<bool> onToggle;

  /// 切换提前提醒时间。
  final ValueChanged<int> onLeadChanged;

  @override
  Widget build(BuildContext context) {
    final hasDeadline = deadline != null;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.notifications_active_outlined,
                size: 18,
                color: AppColors.primary,
              ),
              const SizedBox(width: 6),
              const Expanded(
                child: Text('截止提醒', style: AppTypography.subtitle),
              ),
              Switch(
                value: enabled && hasDeadline,
                onChanged: hasDeadline ? onToggle : null,
              ),
            ],
          ),
          if (!hasDeadline) ...[
            const SizedBox(height: 6),
            Text(
              '需先设置截止时间才能开启提醒',
              style: AppTypography.caption.copyWith(
                color: AppColors.textTertiary,
              ),
            ),
          ] else if (enabled) ...[
            const SizedBox(height: 10),
            Text(
              '建议提醒时间',
              style: AppTypography.label.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _PresetChip(
                  label: '截止前 2 小时',
                  selected: leadMinutes == 120,
                  onTap: () => onLeadChanged(120),
                ),
                _PresetChip(
                  label: '截止前 24 小时',
                  selected: leadMinutes == 1440,
                  onTap: () => onLeadChanged(1440),
                ),
              ],
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<int>(
              initialValue: _dropdownValue,
              decoration: const InputDecoration(
                labelText: '自定义提前时间',
                prefixIcon: Icon(Icons.schedule_rounded, size: 20),
                isDense: true,
              ),
              items: const [
                DropdownMenuItem(value: 30, child: Text('提前 30 分钟')),
                DropdownMenuItem(value: 60, child: Text('提前 1 小时')),
                DropdownMenuItem(value: 120, child: Text('提前 2 小时')),
                DropdownMenuItem(value: 360, child: Text('提前 6 小时')),
                DropdownMenuItem(value: 1440, child: Text('提前 1 天')),
                DropdownMenuItem(value: 2880, child: Text('提前 2 天')),
              ],
              onChanged: (v) {
                if (v != null) onLeadChanged(v);
              },
            ),
            const SizedBox(height: 8),
            _ReminderPreview(leadMinutes: leadMinutes, deadline: deadline!),
          ],
        ],
      ),
    );
  }

  /// 当前 DropdownButtonFormField 应选中的值。
  /// 若 leadMinutes 不在预设列表中,回退到 120(2 小时)。
  int get _dropdownValue {
    const presets = {30, 60, 120, 360, 1440, 2880};
    return presets.contains(leadMinutes) ? leadMinutes : 120;
  }
}

class _PresetChip extends StatelessWidget {
  const _PresetChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppColors.primarySubtle : AppColors.bgSurface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.border,
            width: selected ? 1.2 : 0.8,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (selected) ...[
              const Icon(
                Icons.check_rounded,
                size: 14,
                color: AppColors.primary,
              ),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: AppTypography.label.copyWith(
                fontSize: 12,
                color: selected ? AppColors.primary : AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 提醒时间预览 — 展示预计触发的具体时刻。
class _ReminderPreview extends StatelessWidget {
  const _ReminderPreview({
    required this.leadMinutes,
    required this.deadline,
  });

  final int leadMinutes;
  final DateTime deadline;

  @override
  Widget build(BuildContext context) {
    final reminderAt = deadline.subtract(Duration(minutes: leadMinutes));
    final now = DateTime.now();
    final isPast = reminderAt.isBefore(now);

    final dateStr = _formatDateTime(reminderAt);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: isPast
            ? AppColors.warningSubtle.withValues(alpha: 0.4)
            : AppColors.primarySubtle.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        children: [
          Icon(
            isPast ? Icons.warning_amber_rounded : Icons.alarm_rounded,
            size: 14,
            color: isPast ? AppColors.warning : AppColors.primary,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              isPast ? '该提醒时间已过期($dateStr),将不会触发系统通知' : '将在 $dateStr 发送系统通知',
              style: AppTypography.caption.copyWith(
                fontSize: 11,
                color: isPast ? AppColors.warning : AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatDateTime(DateTime dt) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${dt.year}-${two(dt.month)}-${two(dt.day)} '
        '${two(dt.hour)}:${two(dt.minute)}';
  }
}
