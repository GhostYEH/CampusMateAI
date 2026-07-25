import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/progress_ring.dart';
import '../../../../data/models/task.dart';

/// 首页今日概览英雄卡片 — 动画进度环 + 最紧急任务倒计时。
///
/// 提取自原 HomePage 的 _TodayOverview 与 _NearestTask。
class TodayProgressSection extends StatelessWidget {
  const TodayProgressSection({
    super.key,
    required this.progress,
    required this.nearest,
    required this.todayTaskCount,
  });

  final double progress;
  final Task? nearest;
  final int todayTaskCount;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: AppCard(
        padding: const EdgeInsets.all(18),
        backgroundColor: AppColors.primary,
        borderColor: AppColors.primary,
        showBorder: false,
        shadow: AppShadows.elevated,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                AnimatedProgressRing(
                  progress: progress,
                  size: 64,
                  strokeWidth: 6,
                  color: AppColors.onPrimary,
                  trackColor: AppColors.onPrimary.withValues(alpha: 0.2),
                  showLabel: true,
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '今日任务进度',
                        style: AppTypography.label.copyWith(
                          color: AppColors.onPrimary.withValues(alpha: 0.8),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        todayTaskCount == 0
                            ? '今天暂无截止任务'
                            : '今天有 $todayTaskCount 项截止',
                        style: AppTypography.subtitle.copyWith(
                          color: AppColors.onPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Divider(color: Color(0x33FFFFFF), height: 1),
            const SizedBox(height: 14),
            if (nearest != null)
              _NearestTask(nearest: nearest!)
            else
              Text(
                '没有临近截止的任务,可以安排一些自主学习',
                style: AppTypography.caption.copyWith(
                  color: AppColors.onPrimary.withValues(alpha: 0.85),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _NearestTask extends StatelessWidget {
  const _NearestTask({required this.nearest});
  final Task nearest;

  @override
  Widget build(BuildContext context) {
    final countdown = AppDateUtils.deadlineCountdown(nearest.deadline);
    return GestureDetector(
      onTap: () => context.go('/tasks'),
      child: Row(
        children: [
          const Icon(Icons.flag_rounded, color: AppColors.onPrimary, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '最紧急',
                  style: AppTypography.label.copyWith(
                    color: AppColors.onPrimary.withValues(alpha: 0.7),
                    fontSize: 11,
                  ),
                ),
                Text(
                  nearest.title,
                  style: AppTypography.bodyStrong.copyWith(
                    color: AppColors.onPrimary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: AppColors.onPrimary.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              countdown.text,
              style: AppTypography.label.copyWith(
                color: AppColors.onPrimary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
