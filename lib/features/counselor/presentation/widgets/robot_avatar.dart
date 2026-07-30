import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';

/// AI 导员机器人头像 — 圆形主色 subtle 底 + smart_toy 图标。
class RobotAvatar extends StatelessWidget {
  const RobotAvatar({super.key, this.size = 26, this.iconSize = 15});

  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: AppColors.primarySubtle,
        shape: BoxShape.circle,
      ),
      child: Icon(
        Icons.smart_toy_rounded,
        color: AppColors.primary,
        size: iconSize,
      ),
    );
  }
}

/// 空对话占位 — 居中提示用户开始对话。
class EmptyConversation extends StatelessWidget {
  const EmptyConversation({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: c.primarySubtle,
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.smart_toy_rounded,
              size: 30,
              color: c.primary,
            ),
          ),
          const SizedBox(height: 14),
          Text('开始和 AI 导员对话吧', style: AppTypography.subtitle),
          const SizedBox(height: 6),
          Text('模拟模式 · 校园知识库', style: AppTypography.caption),
        ],
      ),
    );
  }
}
