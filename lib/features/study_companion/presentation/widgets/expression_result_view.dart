import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../data/models/expression.dart';

/// 表情识别结果区 — 当前表情 + 置信度 + 概率分布 + 最近稳定帧。
///
/// 低置信度/无人脸: 显示"暂时无法稳定判断当前表情"且不触发情绪安慰。
class ExpressionResultView extends StatelessWidget {
  const ExpressionResultView({
    super.key,
    required this.result,
    required this.recentStable,
  });

  final ExpressionResult result;
  final List<ExpressionResult> recentStable;

  @override
  Widget build(BuildContext context) {
    final r = result;
    final color = expressionColor(r.label.name);

    if (r.isLowConfidence || !r.hasFace) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.bgSunken,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            const Icon(
              Icons.help_outline_rounded,
              color: AppColors.textTertiary,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                r.label == ExpressionLabel.noFace
                    ? '未检测到人脸,请调整姿势。'
                    : '暂时无法稳定判断当前表情。',
                style: AppTypography.body.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            AnimatedContainer(
              duration: AppMotion.base,
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: Icon(_labelIcon(r.label), color: color, size: 20),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(r.label.displayName, style: AppTypography.subtitle),
                  Text(
                    '置信度 ${(r.confidence * 100).round()}% · ${r.isStable ? "已稳定" : "采集中"}',
                    style: AppTypography.caption,
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        // 概率分布条
        ...r.sortedProbabilities.take(4).map((e) {
          final isTop = e.key == r.label;
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              children: [
                SizedBox(
                  width: 48,
                  child: Text(
                    e.key.displayName,
                    style: AppTypography.label.copyWith(
                      fontSize: 11,
                      color: isTop
                          ? AppColors.textPrimary
                          : AppColors.textTertiary,
                      fontWeight: isTop ? FontWeight.w600 : FontWeight.w400,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(999),
                    child: LinearProgressIndicator(
                      value: e.value,
                      minHeight: 5,
                      backgroundColor: AppColors.bgSunken,
                      color: expressionColor(e.key.name),
                    ),
                  ),
                ),
                SizedBox(
                  width: 36,
                  child: Text(
                    '${(e.value * 100).round()}%',
                    style: AppTypography.label.copyWith(
                      fontSize: 10.5,
                      color: AppColors.textTertiary,
                    ),
                    textAlign: TextAlign.right,
                  ),
                ),
              ],
            ),
          );
        }),
        if (recentStable.length >= 2) ...[
          const SizedBox(height: 8),
          Text(
            '最近 ${recentStable.length} 帧稳定结果',
            style: AppTypography.overline,
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            children: recentStable.map((e) {
              final c = expressionColor(e.label.name);
              return Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(color: c, shape: BoxShape.circle),
              );
            }).toList(),
          ),
        ],
      ],
    );
  }

  IconData _labelIcon(ExpressionLabel l) {
    switch (l) {
      case ExpressionLabel.happy:
        return Icons.sentiment_satisfied_rounded;
      case ExpressionLabel.neutral:
        return Icons.sentiment_neutral_rounded;
      case ExpressionLabel.sad:
        return Icons.sentiment_dissatisfied_rounded;
      case ExpressionLabel.angry:
        return Icons.sentiment_very_dissatisfied_rounded;
      case ExpressionLabel.fear:
        return Icons.warning_amber_rounded;
      case ExpressionLabel.surprise:
        return Icons.sentiment_satisfied_alt_rounded;
      case ExpressionLabel.disgust:
        return Icons.sick_rounded;
      default:
        return Icons.help_outline_rounded;
    }
  }
}

/// 表情识别禁用提示。
class ExpressionDisabledHint extends StatelessWidget {
  const ExpressionDisabledHint({super.key});

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 16),
      child: Column(
        children: [
          Icon(
            Icons.lock_outline_rounded,
            size: 30,
            color: AppColors.textTertiary,
          ),
          SizedBox(height: 8),
          Text(
            '请在"我的"中开启摄像头权限与表情识别',
            style: AppTypography.caption,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
