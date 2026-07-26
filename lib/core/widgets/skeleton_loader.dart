import 'package:flutter/material.dart';

import '../../app/design_system/app_colors.dart';
import '../../app/design_system/app_typography.dart';

/// Skeleton 加载占位 — 用于关键页面初次加载。
///
/// 设计(遵循 frontend-design skill):
/// - 低饱和度,不喧宾夺主
/// - 节奏化的脉冲动画,避免闪烁
/// - 支持 reduceMotion(自动关闭动画)
class SkeletonBox extends StatefulWidget {
  const SkeletonBox({
    super.key,
    this.width,
    this.height = 16,
    this.borderRadius,
  });

  final double? width;
  final double height;
  final double? borderRadius;

  @override
  State<SkeletonBox> createState() => _SkeletonBoxState();
}

class _SkeletonBoxState extends State<SkeletonBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat(reverse: true);
    _animation = Tween<double>(begin: 0.4, end: 1).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOutSine),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final reduceMotion = _reduceMotionOf(context);
    if (reduceMotion) {
      return Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          color: c.bgSunken,
          borderRadius: BorderRadius.circular(
            widget.borderRadius ?? AppRadius.xs,
          ),
        ),
      );
    }
    return AnimatedBuilder(
      animation: _animation,
      builder: (context, child) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            color: c.bgSunken.withValues(alpha: 0.4 + 0.4 * _animation.value),
            borderRadius: BorderRadius.circular(
              widget.borderRadius ?? AppRadius.xs,
            ),
          ),
        );
      },
    );
  }

  bool _reduceMotionOf(BuildContext context) {
    // 通过 InheritedWidget 读 ReduceMotion,避免在此引入 Riverpod
    final mq = MediaQuery.maybeOf(context);
    return mq?.disableAnimations ?? false;
  }
}

/// 列表行 Skeleton — 用于列表初次加载。
class SkeletonListItem extends StatelessWidget {
  const SkeletonListItem({
    super.key,
    this.hasLeading = true,
    this.lines = 2,
  });

  final bool hasLeading;
  final int lines;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.edge,
        vertical: AppSpacing.sm + 2,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (hasLeading) ...[
            const SkeletonBox(
              width: 44,
              height: 44,
              borderRadius: AppRadius.sm,
            ),
            const SizedBox(width: AppSpacing.md),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < lines; i++) ...[
                  SkeletonBox(
                    width: i == 0 ? double.infinity : 220,
                    height: 14,
                  ),
                  if (i < lines - 1) const SizedBox(height: 6),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 卡片 Skeleton — 用于仪表盘卡片初次加载。
class SkeletonCard extends StatelessWidget {
  const SkeletonCard({super.key, this.height = 96});

  final double height;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      margin: const EdgeInsets.symmetric(
        horizontal: AppSpacing.edge,
        vertical: AppSpacing.sm,
      ),
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.bgSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: c.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SkeletonBox(width: 80, height: 12),
          const SizedBox(height: AppSpacing.sm + 2),
          SkeletonBox(width: double.infinity, height: height - 56),
        ],
      ),
    );
  }
}

/// 整页 Skeleton — 包含顶部区域 + 列表行。
class SkeletonPage extends StatelessWidget {
  const SkeletonPage({
    super.key,
    this.headerHeight = 120,
    this.itemCount = 6,
    this.appBarTitle,
  });

  final double headerHeight;
  final int itemCount;
  final String? appBarTitle;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: appBarTitle != null ? AppBar(title: Text(appBarTitle!)) : null,
      body: ListView(
        physics: const NeverScrollableScrollPhysics(),
        children: [
          SizedBox(height: headerHeight),
          for (var i = 0; i < itemCount; i++) const SkeletonListItem(),
        ],
      ),
    );
  }
}
