import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../app/design_system/app_typography.dart';
import 'state_views.dart';

/// 分层进入动画 — 子项依次淡入 + 上移。
///
/// 遵循"减少动态效果"设置:开启时直接显示,不播放动画。
class StaggeredEnter extends ConsumerStatefulWidget {
  const StaggeredEnter({
    super.key,
    required this.child,
    this.delay = Duration.zero,
    this.duration = AppMotion.base,
    this.offset = 18,
  });

  final Widget child;
  final Duration delay;
  final Duration duration;
  final double offset;

  @override
  ConsumerState<StaggeredEnter> createState() => _StaggeredEnterState();
}

class _StaggeredEnterState extends ConsumerState<StaggeredEnter>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _opacity;
  late final Animation<Offset> _offset;
  Timer? _startTimer;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: widget.duration,
      vsync: this,
    );
    _opacity =
        CurvedAnimation(parent: _controller, curve: AppMotion.emphasized);
    _offset = Tween<Offset>(
      begin: Offset(0, widget.offset / 40),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(parent: _controller, curve: AppMotion.decelerate),
    );
    // reduceMotion 模式下不创建 timer,直接保持初始状态(build 中也跳过动画)
    if (!ref.read(reduceMotionProvider)) {
      _startTimer = Timer(widget.delay, () {
        if (mounted) _controller.forward();
      });
    }
  }

  @override
  void dispose() {
    _startTimer?.cancel();
    _controller.dispose();
    super.dispose();
  }

  /// 监听 reduceMotion 变化:切换为 true 时立即停止动画与待触发的 Timer。
  void _onReduceMotionChanged(bool? previous, bool reduceMotion) {
    if (reduceMotion) {
      _startTimer?.cancel();
      _startTimer = null;
      _controller.stop();
      _controller.reset();
    }
  }

  @override
  Widget build(BuildContext context) {
    // 监听 reduceMotion 变化:切换为 true 时立即停止动画。
    ref.listen(reduceMotionProvider, _onReduceMotionChanged);
    if (ref.watch(reduceMotionProvider)) {
      return widget.child;
    }
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Opacity(
          opacity: _opacity.value.clamp(0.0, 1.0),
          child: FractionalTranslation(
            translation: _offset.value,
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}

/// 列表项依次进入。
class StaggeredListView extends ConsumerWidget {
  const StaggeredListView({
    super.key,
    required this.itemCount,
    required this.itemBuilder,
    this.separator,
    this.padding,
    this.shrinkWrap = false,
    this.stepDelay = const Duration(milliseconds: 60),
  });

  final int itemCount;
  final Widget Function(BuildContext, int) itemBuilder;
  final Widget? separator;
  final EdgeInsets? padding;
  final bool shrinkWrap;
  final Duration stepDelay;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListView.separated(
      padding: padding,
      shrinkWrap: shrinkWrap,
      physics: shrinkWrap ? const NeverScrollableScrollPhysics() : null,
      itemCount: itemCount,
      separatorBuilder: (_, __) => separator ?? const SizedBox(height: 12),
      itemBuilder: (context, index) {
        return StaggeredEnter(
          delay: stepDelay * index,
          child: itemBuilder(context, index),
        );
      },
    );
  }
}
