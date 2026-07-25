import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/design_system/app_colors.dart';
import '../../app/design_system/app_typography.dart';
import '../../core/utils/date_utils.dart';
import '../../core/widgets/app_card.dart';
import '../../core/widgets/deadline_chip.dart';
import '../../core/widgets/state_views.dart';
import '../../data/models/task.dart';

/// 任务卡片 — 用于首页与待办列表。
class TaskCard extends ConsumerStatefulWidget {
  const TaskCard({
    super.key,
    required this.task,
    this.onToggle,
    this.onTap,
    this.compact = false,
    this.showSource = true,
    this.trailing,
  });

  final Task task;
  final VoidCallback? onToggle;
  final VoidCallback? onTap;
  final bool compact;
  final bool showSource;
  final Widget? trailing;

  @override
  ConsumerState<TaskCard> createState() => _TaskCardState();
}

class _TaskCardState extends ConsumerState<TaskCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _checkController;

  @override
  void initState() {
    super.initState();
    _checkController = AnimationController(
      duration: AppMotion.base,
      vsync: this,
      value: widget.task.completed ? 1 : 0,
    );
  }

  @override
  void didUpdateWidget(covariant TaskCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.task.completed != widget.task.completed) {
      if (widget.task.completed) {
        _checkController.forward();
      } else {
        _checkController.reverse();
      }
    }
  }

  @override
  void dispose() {
    _checkController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final task = widget.task;
    final reduceMotion = ref.watch(reduceMotionProvider);
    return AppCard(
      onTap: widget.onTap,
      padding: EdgeInsets.all(widget.compact ? 12 : 14),
      borderColor: task.completed ? AppColors.border : AppColors.border,
      backgroundColor:
          task.completed ? AppColors.bgSunken : AppColors.bgSurface,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 勾选按钮
          GestureDetector(
            onTap: widget.onToggle,
            behavior: HitTestBehavior.opaque,
            child: Padding(
              padding: const EdgeInsets.only(top: 2, right: 12),
              child: AnimatedScale(
                scale: 1,
                duration: AppMotion.fast,
                child: _checkbox(reduceMotion),
              ),
            ),
          ),
          // 内容
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const PriorityDot(priority: TaskPriority.medium),
                    const SizedBox(width: 6),
                    PriorityDot(priority: task.priority),
                    const SizedBox(width: 8),
                    CategoryIcon(category: task.category, size: 16),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        task.title,
                        style: AppTypography.subtitle.copyWith(
                          decoration: task.completed
                              ? TextDecoration.lineThrough
                              : null,
                          color: task.completed
                              ? AppColors.textTertiary
                              : AppColors.textPrimary,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                if (!widget.compact) ...[
                  if (task.description != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      task.description!,
                      style: AppTypography.caption,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      DeadlineChip(deadline: task.deadline),
                      if (task.location != null)
                        _metaChip(
                          Icons.place_outlined,
                          task.location!,
                          AppColors.textTertiary,
                        ),
                      if (widget.showSource)
                        _metaChip(
                          Icons.link_rounded,
                          task.source.displayName,
                          AppColors.textTertiary,
                        ),
                    ],
                  ),
                  if (task.materials.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    _materialsBar(task),
                  ],
                ] else if (task.deadline != null) ...[
                  const SizedBox(height: 6),
                  DeadlineChip(deadline: task.deadline, compact: true),
                ],
              ],
            ),
          ),
          if (widget.trailing != null) widget.trailing!,
        ],
      ),
    );
  }

  Widget _checkbox(bool reduceMotion) {
    const size = 22.0;
    if (reduceMotion) {
      return Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: widget.task.completed ? AppColors.primary : Colors.transparent,
          shape: BoxShape.circle,
          border: Border.all(
            color: widget.task.completed
                ? AppColors.primary
                : AppColors.borderStrong,
            width: 1.6,
          ),
        ),
        child: widget.task.completed
            ? const Icon(Icons.check, size: 14, color: AppColors.onPrimary)
            : null,
      );
    }
    return AnimatedBuilder(
      animation: _checkController,
      builder: (context, _) {
        return Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            color: Color.lerp(
              Colors.transparent,
              AppColors.primary,
              _checkController.value,
            ),
            shape: BoxShape.circle,
            border: Border.all(
              color: Color.lerp(
                AppColors.borderStrong,
                AppColors.primary,
                _checkController.value,
              )!,
              width: 1.6,
            ),
          ),
          child: FadeTransition(
            opacity: _checkController,
            child:
                const Icon(Icons.check, size: 14, color: AppColors.onPrimary),
          ),
        );
      },
    );
  }

  Widget _metaChip(IconData icon, String text, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 12, color: color),
        const SizedBox(width: 2),
        Text(
          text,
          style: AppTypography.label.copyWith(
            color: color,
            fontWeight: FontWeight.w400,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }

  Widget _materialsBar(Task task) {
    final required = task.materials.where((m) => m.required).toList();
    if (required.isEmpty) return const SizedBox.shrink();
    final done = required.where((m) => m.done).length;
    final progress = done / required.length;
    return Row(
      children: [
        const Icon(
          Icons.inventory_2_outlined,
          size: 13,
          color: AppColors.textTertiary,
        ),
        const SizedBox(width: 4),
        Text(
          '材料 $done/${required.length}',
          style: AppTypography.label.copyWith(
            color: AppColors.textTertiary,
            fontWeight: FontWeight.w400,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 4,
              backgroundColor: AppColors.bgSunken,
              color: progress == 1 ? AppColors.success : AppColors.primary,
            ),
          ),
        ),
      ],
    );
  }
}

/// 通知卡片。
class NoticeCard extends StatelessWidget {
  const NoticeCard({
    super.key,
    required this.notice,
    this.onTap,
    this.compact = false,
  });

  final dynamic notice; // CampusNotice
  final VoidCallback? onTap;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final n = notice;
    final importanceColor = _importanceColor(n.importance);
    return AppCard(
      onTap: onTap,
      padding: EdgeInsets.all(compact ? 12 : 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!n.read)
            Container(
              margin: const EdgeInsets.only(top: 6),
              width: 7,
              height: 7,
              decoration: const BoxDecoration(
                color: AppColors.accent,
                shape: BoxShape.circle,
              ),
            )
          else
            const SizedBox(width: 7),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: importanceColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        n.importance.displayName,
                        style: AppTypography.label.copyWith(
                          color: importanceColor,
                          fontSize: 10.5,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      n.source,
                      style: AppTypography.label.copyWith(
                        color: AppColors.textTertiary,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      AppDateUtils.relativeTime(n.publishedAt),
                      style: AppTypography.label.copyWith(
                        color: AppColors.textTertiary,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  n.title,
                  style: AppTypography.subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (!compact) ...[
                  const SizedBox(height: 4),
                  Text(
                    n.content,
                    style: AppTypography.caption,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Color _importanceColor(dynamic importance) {
    switch (importance.toString().split('.').last) {
      case 'urgent':
        return AppColors.danger;
      case 'important':
        return AppColors.accent;
      default:
        return AppColors.info;
    }
  }
}

/// 快捷入口按钮。
class QuickActionTile extends StatelessWidget {
  const QuickActionTile({
    super.key,
    required this.icon,
    required this.label,
    required this.route,
    this.color = AppColors.primary,
  });

  final IconData icon;
  final String label;
  final String route;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => context.push(route),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 6),
            Text(
              label,
              style: AppTypography.label.copyWith(
                color: AppColors.textPrimary,
                fontWeight: FontWeight.w600,
              ),
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
