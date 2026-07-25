import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/study.dart';

/// 学习状态英雄区 — 动态呼吸环 + 状态文字 + 计时器。
///
/// 呼吸环为缓慢循环(2.4s),开启"减少动态效果"时通过上层 [_StudyCompanionPageState]
/// 直接传入静态 state 跳过动画。
class StudyStateHero extends StatefulWidget {
  const StudyStateHero({
    super.key,
    required this.state,
    required this.durationSeconds,
    required this.isStudying,
    this.reduceMotion = false,
  });

  final StudyState state;
  final int durationSeconds;
  final bool isStudying;
  final bool reduceMotion;

  @override
  State<StudyStateHero> createState() => _StudyStateHeroState();
}

class _StudyStateHeroState extends State<StudyStateHero>
    with TickerProviderStateMixin {
  late final AnimationController _breath;

  @override
  void initState() {
    super.initState();
    _breath = AnimationController(
      duration: const Duration(milliseconds: 2400),
      vsync: this,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _breath.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final (color, icon) = _stateVisual(widget.state);
    final h = widget.durationSeconds ~/ 3600;
    final m = (widget.durationSeconds % 3600) ~/ 60;
    final s = widget.durationSeconds % 60;
    final timeStr = h > 0
        ? '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}'
        : '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';

    return AppCard(
      padding: const EdgeInsets.symmetric(vertical: 28),
      backgroundColor: AppColors.bgSurface,
      child: Column(
        children: [
          SizedBox(
            height: 180,
            child: Stack(
              alignment: Alignment.center,
              children: [
                // 呼吸环(减少动态效果时静止)
                widget.reduceMotion
                    ? _staticBreathRing(color)
                    : AnimatedBuilder(
                        animation: _breath,
                        builder: (context, _) {
                          final scale = 1 + 0.08 * _breath.value;
                          final opacity = 0.25 + 0.25 * _breath.value;
                          return Transform.scale(
                            scale: scale,
                            child: Container(
                              width: 140,
                              height: 140,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: color.withValues(alpha: opacity),
                                  width: 2,
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                AnimatedContainer(
                  duration: AppMotion.base,
                  width: 110,
                  height: 110,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: color.withValues(alpha: 0.12),
                    border: Border.all(
                      color: color.withValues(alpha: 0.4),
                      width: 1.5,
                    ),
                  ),
                  child: Icon(icon, color: color, size: 44),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          AnimatedSwitcher(
            duration: AppMotion.base,
            child: Text(
              widget.state.displayName,
              key: ValueKey(widget.state),
              style: AppTypography.subtitle.copyWith(color: color),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            timeStr,
            style: AppTypography.metric.copyWith(
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 4),
          Text(
            widget.isStudying ? '专注计时中' : '点击下方按钮开始学习',
            style: AppTypography.caption,
          ),
        ],
      ),
    );
  }

  Widget _staticBreathRing(Color color) {
    return Container(
      width: 140,
      height: 140,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: color.withValues(alpha: 0.4), width: 2),
      ),
    );
  }

  (Color, IconData) _stateVisual(StudyState s) {
    switch (s) {
      case StudyState.idle:
        return (AppColors.textTertiary, Icons.self_improvement_rounded);
      case StudyState.focusing:
        return (AppColors.primary, Icons.center_focus_strong_rounded);
      case StudyState.distracted:
        return (AppColors.warning, Icons.visibility_off_rounded);
      case StudyState.fatigued:
        return (AppColors.accent, Icons.battery_alert_rounded);
      case StudyState.paused:
        return (AppColors.textSecondary, Icons.pause_circle_rounded);
      case StudyState.resting:
        return (AppColors.success, Icons.local_cafe_rounded);
      case StudyState.completed:
        return (AppColors.success, Icons.check_circle_rounded);
    }
  }
}
