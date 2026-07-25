import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';

/// 首页今日学习概览卡片 — 呼吸圆点 + 时长 + 趋势图标。
///
/// 提取自原 HomePage 的 _StudyOverview 与 _BreathingDot。
/// 呼吸动画遵循"减少动态效果"设置(由调用方决定是否启用,当前默认开启)。
class StudySummarySection extends StatelessWidget {
  const StudySummarySection({
    super.key,
    required this.todayTotal,
    this.reduceMotion = false,
  });

  final Duration? todayTotal;
  final bool reduceMotion;

  @override
  Widget build(BuildContext context) {
    final minutes = todayTotal?.inMinutes ?? 0;
    final h = minutes ~/ 60;
    final m = minutes % 60;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: AppCard(
        onTap: () => context.go('/study'),
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            _BreathingDot(reduceMotion: reduceMotion),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('今日学习', style: AppTypography.label),
                  const SizedBox(height: 2),
                  Text(
                    h > 0 ? '$h 小时 $m 分钟' : '$m 分钟',
                    style: AppTypography.metric,
                  ),
                ],
              ),
            ),
            const Icon(Icons.trending_up_rounded, color: AppColors.success),
            const SizedBox(width: 4),
            const Text(
              '专注还不错的样子',
              style: AppTypography.caption,
            ),
          ],
        ),
      ),
    );
  }
}

class _BreathingDot extends StatefulWidget {
  const _BreathingDot({required this.reduceMotion});

  final bool reduceMotion;

  @override
  State<_BreathingDot> createState() => _BreathingDotState();
}

class _BreathingDotState extends State<_BreathingDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      duration: const Duration(milliseconds: 1600),
      vsync: this,
    );
    // 开启"减少动态效果"时停止 repeat,保持静止状态。
    if (!widget.reduceMotion) {
      _c.repeat(reverse: true);
    } else {
      _c.value = 0.5;
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.reduceMotion) {
      return _buildDot(0.5);
    }
    return AnimatedBuilder(
      animation: _c,
      builder: (context, _) => _buildDot(_c.value),
    );
  }

  Widget _buildDot(double value) {
    return Container(
      width: 14,
      height: 14,
      decoration: BoxDecoration(
        color: AppColors.success.withValues(alpha: 0.3 + 0.5 * value),
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: AppColors.success.withValues(alpha: 0.3 * value),
            blurRadius: 8 + 6 * value,
            spreadRadius: 1,
          ),
        ],
      ),
      child: Center(
        child: Container(
          width: 6,
          height: 6,
          decoration: const BoxDecoration(
            color: AppColors.success,
            shape: BoxShape.circle,
          ),
        ),
      ),
    );
  }
}
