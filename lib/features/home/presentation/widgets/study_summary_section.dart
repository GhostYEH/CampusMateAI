import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';

/// 首页今日学习概览卡片 — 静息圆点 + 时长 + 提示语。
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
    final c = context.appColors;
    final minutes = todayTotal?.inMinutes ?? 0;
    final h = minutes ~/ 60;
    final m = minutes % 60;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: AppCard(
        onTap: () => context.go('/study'),
        padding: const EdgeInsets.all(14),
        borderRadius: 12,
        child: Row(
          children: [
            _StudyDot(reduceMotion: reduceMotion),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('今日学习', style: AppTypography.label),
                  const SizedBox(height: 2),
                  Text(
                    h > 0 ? '$h 小时 $m 分钟' : '$m 分钟',
                    style: AppTypography.metric,
                  ),
                ],
              ),
            ),
            Icon(Icons.trending_up_rounded, color: c.success, size: 20),
            const SizedBox(width: 4),
            Text(
              hoursToLabel(h),
              style: AppTypography.caption,
            ),
          ],
        ),
      ),
    );
  }

  String hoursToLabel(int hours) {
    if (hours <= 0) return '还没开始呢';
    if (hours < 2) return '刚开始状态不错';
    if (hours < 4) return '专注状态很好';
    return '今日学习状态很棒';
  }
}

class _StudyDot extends StatefulWidget {
  const _StudyDot({required this.reduceMotion});

  final bool reduceMotion;

  @override
  State<_StudyDot> createState() => _StudyDotState();
}

class _StudyDotState extends State<_StudyDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      duration: const Duration(milliseconds: 1400),
      vsync: this,
    );
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
      width: 12,
      height: 12,
      decoration: BoxDecoration(
        color: AppColors.success.withValues(alpha: 0.3 + 0.5 * value),
        shape: BoxShape.circle,
      ),
      child: Center(
        child: Container(
          width: 5,
          height: 5,
          decoration: const BoxDecoration(
            color: AppColors.success,
            shape: BoxShape.circle,
          ),
        ),
      ),
    );
  }
}
