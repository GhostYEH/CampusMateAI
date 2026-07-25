import 'package:flutter/material.dart';
import '../../app/design_system/app_colors.dart';
import '../../app/design_system/app_typography.dart';
import '../../core/utils/date_utils.dart';
import '../../data/models/task.dart';

/// 截止倒计时标签 — 根据紧急程度变色。
class DeadlineChip extends StatelessWidget {
  const DeadlineChip({super.key, required this.deadline, this.compact = false});

  final DateTime? deadline;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final countdown = AppDateUtils.deadlineCountdown(deadline);
    final (color, bg) = _colors(countdown.urgency);
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : 8,
        vertical: compact ? 2 : 3,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(compact ? 6 : 8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_icon(countdown.urgency), size: compact ? 11 : 13, color: color),
          const SizedBox(width: 3),
          Text(
            countdown.text,
            style: AppTypography.label.copyWith(
              color: color,
              fontSize: compact ? 10.5 : 12,
            ),
          ),
        ],
      ),
    );
  }

  (Color, Color) _colors(DeadlineUrgency u) {
    switch (u) {
      case DeadlineUrgency.overdue:
        return (AppColors.danger, AppColors.dangerSubtle);
      case DeadlineUrgency.urgent:
        return (AppColors.accent, AppColors.accentSubtle);
      case DeadlineUrgency.soon:
        return (AppColors.warning, AppColors.warningSubtle);
      case DeadlineUrgency.normal:
        return (AppColors.textSecondary, AppColors.bgSunken);
      case DeadlineUrgency.none:
        return (AppColors.textTertiary, AppColors.bgSunken);
    }
  }

  IconData _icon(DeadlineUrgency u) {
    switch (u) {
      case DeadlineUrgency.overdue:
        return Icons.error_outline_rounded;
      case DeadlineUrgency.urgent:
        return Icons.schedule_rounded;
      case DeadlineUrgency.soon:
        return Icons.schedule_rounded;
      default:
        return Icons.event_available_rounded;
    }
  }
}

/// 优先级标签。
class PriorityDot extends StatelessWidget {
  const PriorityDot({super.key, required this.priority});
  final TaskPriority priority;

  @override
  Widget build(BuildContext context) {
    final color = switch (priority) {
      TaskPriority.high => AppColors.danger,
      TaskPriority.medium => AppColors.warning,
      TaskPriority.low => AppColors.success,
    };
    return Container(
      width: 6,
      height: 6,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

/// 类别图标。
class CategoryIcon extends StatelessWidget {
  const CategoryIcon({super.key, required this.category, this.size = 18});
  final TaskCategory category;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Icon(_icon(category), size: size, color: AppColors.primary);
  }

  IconData _icon(TaskCategory c) {
    switch (c) {
      case TaskCategory.study:
        return Icons.menu_book_rounded;
      case TaskCategory.courseSelection:
        return Icons.app_registration_rounded;
      case TaskCategory.scholarship:
        return Icons.emoji_events_rounded;
      case TaskCategory.comprehensiveEval:
        return Icons.fact_check_rounded;
      case TaskCategory.practice:
        return Icons.groups_rounded;
      case TaskCategory.activity:
        return Icons.event_rounded;
      case TaskCategory.material:
        return Icons.description_rounded;
      case TaskCategory.daily:
        return Icons.today_rounded;
      case TaskCategory.other:
        return Icons.tag_rounded;
    }
  }
}
