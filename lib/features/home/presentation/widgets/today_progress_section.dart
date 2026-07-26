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
        padding: EdgeInsets.zero,
        backgroundColor: const Color(0xFF245A73),
        borderColor: const Color(0xFF245A73),
        showBorder: false,
        shadow: AppShadows.elevated,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          child: Stack(
            children: [
              const Positioned(
                right: -34,
                top: -52,
                child: _DecorativeOrb(size: 150, opacity: .07),
              ),
              const Positioned(
                right: 70,
                bottom: -58,
                child: _DecorativeOrb(size: 116, opacity: .045),
              ),
              Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '今日任务进度',
                                style: AppTypography.overline.copyWith(
                                  color: AppColors.onPrimary
                                      .withValues(alpha: 0.68),
                                  letterSpacing: 1.1,
                                ),
                              ),
                              const SizedBox(height: 7),
                              Text(
                                todayTaskCount == 0
                                    ? '今天暂无截止任务'
                                    : '今天有 $todayTaskCount 项截止',
                                style: AppTypography.title.copyWith(
                                  color: AppColors.onPrimary,
                                  fontSize: 19,
                                ),
                              ),
                            ],
                          ),
                        ),
                        AnimatedProgressRing(
                          progress: progress,
                          size: 66,
                          strokeWidth: 6,
                          color: const Color(0xFFFFC28E),
                          trackColor:
                              AppColors.onPrimary.withValues(alpha: 0.14),
                          showLabel: true,
                        ),
                      ],
                    ),
                    const SizedBox(height: 18),
                    Container(
                      height: 1,
                      color: AppColors.onPrimary.withValues(alpha: .13),
                    ),
                    const SizedBox(height: 14),
                    if (nearest != null)
                      _NearestTask(nearest: nearest!)
                    else
                      Row(
                        children: [
                          const Icon(
                            Icons.event_available_rounded,
                            size: 18,
                            color: Color(0xFFFFC28E),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '近期没有截止任务',
                            style: AppTypography.caption.copyWith(
                              color:
                                  AppColors.onPrimary.withValues(alpha: 0.82),
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DecorativeOrb extends StatelessWidget {
  const _DecorativeOrb({required this.size, required this.opacity});
  final double size;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: opacity),
        shape: BoxShape.circle,
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
