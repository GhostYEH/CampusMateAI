import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../app/design_system/app_colors.dart';
import '../../app/design_system/app_typography.dart';
import 'state_views.dart';

/// 动画进度环 — 首次出现有动画,数值变化平滑过渡。
class AnimatedProgressRing extends ConsumerStatefulWidget {
  const AnimatedProgressRing({
    super.key,
    required this.progress,
    this.size = 88,
    this.strokeWidth = 8,
    this.color = AppColors.primary,
    this.trackColor = AppColors.bgSunken,
    this.child,
    this.showLabel = false,
  });

  final double progress; // 0.0 ~ 1.0
  final double size;
  final double strokeWidth;
  final Color color;
  final Color trackColor;
  final Widget? child;
  final bool showLabel;

  @override
  ConsumerState<AnimatedProgressRing> createState() =>
      _AnimatedProgressRingState();
}

class _AnimatedProgressRingState extends ConsumerState<AnimatedProgressRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late Animation<double> _animation;
  double _oldProgress = 0;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: AppMotion.slow,
      vsync: this,
    );
    _animateTo(widget.progress);
  }

  @override
  void didUpdateWidget(covariant AnimatedProgressRing oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.progress != widget.progress) {
      _oldProgress = oldWidget.progress;
      _animateTo(widget.progress);
    }
  }

  void _animateTo(double target) {
    _animation = Tween<double>(begin: _oldProgress, end: target).animate(
      CurvedAnimation(parent: _controller, curve: AppMotion.emphasized),
    );
    _controller.forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = ref.watch(reduceMotionProvider);
    final value = reduceMotion ? widget.progress : _animation.value;
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
            size: Size(widget.size, widget.size),
            painter: _RingPainter(
              progress: value.clamp(0.0, 1.0),
              color: widget.color,
              trackColor: widget.trackColor,
              strokeWidth: widget.strokeWidth,
            ),
          ),
          if (widget.child != null)
            widget.child!
          else if (widget.showLabel)
            Text(
              '${(value.clamp(0.0, 1.0) * 100).round()}%',
              style: AppTypography.subtitle,
            ),
        ],
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter({
    required this.progress,
    required this.color,
    required this.trackColor,
    required this.strokeWidth,
  });
  final double progress;
  final Color color;
  final Color trackColor;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - strokeWidth) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);

    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..color = trackColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth,
    );

    canvas.drawArc(
      rect,
      -math.pi / 2,
      2 * math.pi * progress,
      false,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(_RingPainter oldDelegate) =>
      oldDelegate.progress != progress ||
      oldDelegate.color != color ||
      oldDelegate.trackColor != trackColor;
}

/// 动画线性进度条。
class AnimatedLinearProgress extends ConsumerStatefulWidget {
  const AnimatedLinearProgress({
    super.key,
    required this.progress,
    this.height = 6,
    this.color = AppColors.primary,
    this.trackColor = AppColors.bgSunken,
    this.radius = 999,
  });

  final double progress;
  final double height;
  final Color color;
  final Color trackColor;
  final double radius;

  @override
  ConsumerState<AnimatedLinearProgress> createState() =>
      _AnimatedLinearProgressState();
}

class _AnimatedLinearProgressState
    extends ConsumerState<AnimatedLinearProgress> {
  double _current = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) setState(() => _current = widget.progress);
    });
  }

  @override
  void didUpdateWidget(covariant AnimatedLinearProgress oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.progress != widget.progress) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => _current = widget.progress);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = ref.watch(reduceMotionProvider);
    return ClipRRect(
      borderRadius: BorderRadius.circular(widget.radius),
      child: LinearProgressIndicator(
        value: reduceMotion ? widget.progress : _current,
        minHeight: widget.height,
        backgroundColor: widget.trackColor,
        color: widget.color,
      ),
    );
  }
}
