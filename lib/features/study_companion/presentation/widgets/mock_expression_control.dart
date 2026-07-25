import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../data/models/expression.dart';

/// Mock 表情注入控制台 — 演示/开发模式注入表情标签。
///
/// 仅在开发或比赛演示模式下显示(由调用方控制可见性)。
class MockExpressionControl extends StatelessWidget {
  const MockExpressionControl({super.key, required this.onInject});

  final void Function(ExpressionLabel?) onInject;

  static const List<ExpressionLabel> _labels = [
    ExpressionLabel.happy,
    ExpressionLabel.neutral,
    ExpressionLabel.sad,
    ExpressionLabel.angry,
    ExpressionLabel.fear,
    ExpressionLabel.surprise,
    ExpressionLabel.disgust,
    ExpressionLabel.noFace,
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.bgSunken,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border, width: 0.6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.tune_rounded,
                size: 14,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                'Mock 控制台(演示用)',
                style: AppTypography.overline.copyWith(fontSize: 10),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final l in _labels)
                ActionChip(
                  label: Text(
                    l.displayName,
                    style: const TextStyle(fontSize: 11),
                  ),
                  onPressed: () => onInject(l),
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ActionChip(
                label: const Text('随机漂移', style: TextStyle(fontSize: 11)),
                onPressed: () => onInject(null),
                visualDensity: VisualDensity.compact,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
