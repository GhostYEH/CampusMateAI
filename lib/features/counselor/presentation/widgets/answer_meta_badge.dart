import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../data/models/chat.dart';

/// AI 回答元数据徽章 — 同时展示"回答模式"和"证据等级"两行。
///
/// 设计原则:
/// - 模式徽章用低饱和青蓝色,避免误导用户认为是"AI 生成"
/// - 证据等级文案直接使用后端 evidence_level 转译后的中文短句
/// - conflict / none 状态使用暖色提示,引导用户人工核实
/// - 仅在 AI 回复且非流式输出时显示
class AnswerMetaBadge extends StatelessWidget {
  const AnswerMetaBadge({
    super.key,
    required this.message,
    this.onAddToTasks,
  });

  final ChatMessage message;

  /// "根据回答创建待办"回调 — 进入人工确认页面。
  /// 若为 null,则不显示该按钮。
  final VoidCallback? onAddToTasks;

  @override
  Widget build(BuildContext context) {
    if (message.answerMode == AnswerMode.unknown) {
      return const SizedBox.shrink();
    }

    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.bgSunken,
        borderRadius: BorderRadius.circular(AppRadius.xs),
        border: Border.all(color: AppColors.border, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _modeRow(),
          if (message.evidenceLevel != EvidenceLevel.unknown) ...[
            const SizedBox(height: 4),
            _evidenceRow(),
          ],
          if (message.warnings.isNotEmpty) ...[
            const SizedBox(height: 4),
            _warningsRow(),
          ],
          if (onAddToTasks != null &&
              message.content.trim().isNotEmpty &&
              message.answerMode != AnswerMode.noKnowledge) ...[
            const SizedBox(height: 6),
            _addToTasksButton(),
          ],
        ],
      ),
    );
  }

  Widget _modeRow() {
    final badgeColor = _modeColor(message.answerMode);
    return Row(
      children: [
        Icon(_modeIcon(message.answerMode), size: 11, color: badgeColor),
        const SizedBox(width: 4),
        Text(
          message.answerMode.badgeLabel,
          style: AppTypography.overline.copyWith(
            fontSize: 9.5,
            color: badgeColor,
            letterSpacing: 0.3,
          ),
        ),
      ],
    );
  }

  Widget _evidenceRow() {
    final level = message.evidenceLevel;
    final color = _evidenceColor(level);
    final label = level.userFacingLabel;
    if (label.isEmpty) return const SizedBox.shrink();
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(_evidenceIcon(level), size: 11, color: color),
        const SizedBox(width: 4),
        Expanded(
          child: Text(
            label,
            style: AppTypography.overline.copyWith(
              fontSize: 9.5,
              color: color,
              height: 1.3,
            ),
          ),
        ),
      ],
    );
  }

  Widget _warningsRow() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final w in message.warnings) ...[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.warning_amber_rounded,
                size: 11,
                color: AppColors.warning,
              ),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  w,
                  style: AppTypography.overline.copyWith(
                    fontSize: 9.5,
                    color: AppColors.warning,
                    height: 1.3,
                  ),
                ),
              ),
            ],
          ),
          if (w != message.warnings.last) const SizedBox(height: 2),
        ],
      ],
    );
  }

  Widget _addToTasksButton() {
    return InkWell(
      onTap: onAddToTasks,
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: AppColors.primarySubtle,
          borderRadius: BorderRadius.circular(AppRadius.xs),
          border: Border.all(color: AppColors.primary, width: 0.6),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.add_task_rounded,
              size: 11,
              color: AppColors.primary,
            ),
            const SizedBox(width: 4),
            Text(
              '根据回答创建待办',
              style: AppTypography.label.copyWith(
                fontSize: 10.5,
                color: AppColors.primary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _modeColor(AnswerMode mode) {
    switch (mode) {
      case AnswerMode.demoRetrievalSummary:
        return AppColors.accent;
      case AnswerMode.userRetrievalSummary:
        return AppColors.primary;
      case AnswerMode.userLlmRag:
      case AnswerMode.hybridLlmRag:
        return AppColors.primary;
      case AnswerMode.noKnowledge:
        return AppColors.warning;
      case AnswerMode.mockDemo:
        return AppColors.accent;
      case AnswerMode.unknown:
        return AppColors.textTertiary;
    }
  }

  IconData _modeIcon(AnswerMode mode) {
    switch (mode) {
      case AnswerMode.demoRetrievalSummary:
      case AnswerMode.userRetrievalSummary:
        return Icons.summarize_outlined;
      case AnswerMode.userLlmRag:
      case AnswerMode.hybridLlmRag:
        return Icons.auto_awesome_outlined;
      case AnswerMode.noKnowledge:
        return Icons.help_outline_rounded;
      case AnswerMode.mockDemo:
        return Icons.science_outlined;
      case AnswerMode.unknown:
        return Icons.circle_outlined;
    }
  }

  Color _evidenceColor(EvidenceLevel level) {
    switch (level) {
      case EvidenceLevel.high:
        return AppColors.success;
      case EvidenceLevel.medium:
        return AppColors.accent;
      case EvidenceLevel.conflict:
        return AppColors.warning;
      case EvidenceLevel.none:
        return AppColors.warning;
      case EvidenceLevel.unknown:
        return AppColors.textTertiary;
    }
  }

  IconData _evidenceIcon(EvidenceLevel level) {
    switch (level) {
      case EvidenceLevel.high:
        return Icons.verified_outlined;
      case EvidenceLevel.medium:
        return Icons.info_outline_rounded;
      case EvidenceLevel.conflict:
        return Icons.warning_amber_rounded;
      case EvidenceLevel.none:
        return Icons.help_outline_rounded;
      case EvidenceLevel.unknown:
        return Icons.circle_outlined;
    }
  }
}
