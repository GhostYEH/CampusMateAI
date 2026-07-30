import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../data/models/task.dart';

/// 今日节奏 — 以校园日程单为原型。
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
    final c = context.appColors;
    final percent = (progress.clamp(0, 1) * 100).round();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFF183E56),
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF183E56).withValues(alpha: .18),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '今日进度',
                          style: AppTypography.overline.copyWith(
                            color: const Color(0xFF8DD7E8),
                            letterSpacing: .8,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          todayTaskCount == 0
                              ? '今天暂无截止任务'
                              : '今天有 $todayTaskCount 项截止',
                          style: AppTypography.title.copyWith(
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '$percent%',
                        style: AppTypography.metric.copyWith(
                          color: Colors.white,
                          fontSize: 24,
                        ),
                      ),
                      Text(
                        '已完成',
                        style: AppTypography.caption.copyWith(
                          color: Colors.white.withValues(alpha: .6),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: progress.clamp(0, 1)),
                duration: AppMotion.slow,
                curve: AppMotion.emphasized,
                builder: (context, value, _) => ClipRRect(
                  borderRadius: BorderRadius.circular(2),
                  child: LinearProgressIndicator(
                    value: value,
                    minHeight: 3,
                    backgroundColor: const Color(0xFF31586C),
                    valueColor: const AlwaysStoppedAnimation(Color(0xFFFFA767)),
                  ),
                ),
              ),
            ),
            InkWell(
              onTap: nearest == null ? null : () => context.go('/tasks'),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 14, 13),
                child: nearest == null
                    ? Row(
                        children: [
                          PhosphorIcon(
                            PhosphorIconsRegular.checkCircle,
                            size: 17,
                            color: c.success,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '接下来没有紧急截止事项',
                            style: AppTypography.body.copyWith(
                              color: Colors.white.withValues(alpha: .7),
                            ),
                          ),
                        ],
                      )
                    : _NearestTask(task: nearest!),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NearestTask extends StatelessWidget {
  const _NearestTask({required this.task});

  final Task task;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      children: [
        PhosphorIcon(
          PhosphorIconsRegular.flagPennant,
          size: 17,
          color: c.accent,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '最紧急',
                style: AppTypography.overline.copyWith(
                  color: Colors.white.withValues(alpha: .5),
                ),
              ),
              Text(
                task.title,
                style: AppTypography.bodyStrong.copyWith(
                  color: Colors.white,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Text(
          AppDateUtils.deadlineCountdown(task.deadline).text,
          style: AppTypography.label.copyWith(
            color: c.accent,
            fontSize: 12,
          ),
        ),
        const SizedBox(width: 2),
        PhosphorIcon(
          PhosphorIconsRegular.caretRight,
          size: 14,
          color: Colors.white.withValues(alpha: .4),
        ),
      ],
    );
  }
}
