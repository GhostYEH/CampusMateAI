import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';

/// 流式打字光标(闪烁竖线 ▍)。
///
/// 用于 AI 消息流式输出过程中,跟随内容末尾,提示"正在生成"。
class BlinkingCursor extends StatefulWidget {
  const BlinkingCursor({super.key, this.color = AppColors.textPrimary});

  final Color color;

  @override
  State<BlinkingCursor> createState() => _BlinkingCursorState();
}

class _BlinkingCursorState extends State<BlinkingCursor>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 560),
      vsync: this,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Opacity(
          opacity: (0.2 + 0.8 * _controller.value).clamp(0.0, 1.0),
          child: Padding(
            padding: const EdgeInsets.only(left: 1),
            child: Text(
              '▍',
              style: AppTypography.body.copyWith(
                color: widget.color,
                fontWeight: FontWeight.w700,
                height: 1.2,
              ),
            ),
          ),
        );
      },
    );
  }
}

/// 正在输入三点跳动 — AI 消息流式开始但内容为空时显示。
class TypingDots extends StatefulWidget {
  const TypingDots({super.key});

  @override
  State<TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<TypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Widget _dot(int index) {
    final begin = (index * 0.2).clamp(0.0, 0.8);
    final end = (begin + 0.4).clamp(0.0, 1.0);
    final tween = Tween<double>(begin: 0.35, end: 1.0)
        .chain(CurveTween(curve: Curves.easeInOut));
    final anim = tween.animate(
      CurvedAnimation(
        parent: _controller,
        curve: Interval(begin, end, curve: Curves.easeInOut),
      ),
    );
    return AnimatedBuilder(
      animation: anim,
      builder: (context, child) {
        return Opacity(opacity: anim.value, child: child);
      },
      child: Container(
        width: 6,
        height: 6,
        margin: const EdgeInsets.symmetric(horizontal: 1.5),
        decoration: const BoxDecoration(
          color: AppColors.textTertiary,
          shape: BoxShape.circle,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 16,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(3, _dot),
      ),
    );
  }
}
