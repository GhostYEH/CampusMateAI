import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/expression.dart';
import '../../../../data/models/study.dart';

/// AI 导员陪伴建议 — 遵循科学边界,不进行心理诊断。
///
/// 低置信度/无人脸时:  仅提示"识别结果仅供辅助参考",不进行情绪安慰。
/// 状态稳定时:  根据学习状态给出温和建议(不夸大、不诊断)。
class CompanionSuggestionPanel extends StatelessWidget {
  const CompanionSuggestionPanel({
    super.key,
    required this.state,
    required this.expression,
    required this.recentStable,
  });

  final StudyState state;
  final ExpressionResult? expression;
  final List<ExpressionResult> recentStable;

  @override
  Widget build(BuildContext context) {
    final suggestion = _build();
    return AppCard(
      padding: const EdgeInsets.all(16),
      borderColor: AppColors.primarySubtle,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CircleAvatar(
            radius: 16,
            backgroundColor: AppColors.primarySubtle,
            child: Icon(
              Icons.smart_toy_rounded,
              size: 18,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('AI 导员陪伴', style: AppTypography.subtitle),
                const SizedBox(height: 6),
                Text(suggestion, style: AppTypography.body),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _build() {
    // 低置信度不触发情绪安慰
    if (expression != null &&
        (expression!.isLowConfidence || !expression!.hasFace)) {
      return '识别结果仅供辅助参考。继续专注吧,需要休息时随时告诉我。';
    }
    switch (state) {
      case StudyState.idle:
        return '准备好了就开始吧,定个小目标会更专注。';
      case StudyState.focusing:
        if (expression?.label == ExpressionLabel.happy) {
          return '状态看起来不错,保持节奏,记得适时休息。';
        }
        return '专注中,继续加油。每过一段时间可以抬头看看远处。';
      case StudyState.distracted:
        return '你好像有些走神,要不要把当前任务拆小一点?我们可以一起整理。';
      case StudyState.fatigued:
        return '你好像有些疲惫,需要休息一下吗?起来走走、喝口水都好。';
      case StudyState.paused:
        return '已暂停,休息好了再继续。';
      case StudyState.resting:
        return '休息中,放松一下眼睛和肩膀吧。';
      case StudyState.completed:
        return '本次学习完成,辛苦了!记得给自己一点正向反馈。';
    }
  }
}
