import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/staggered_enter.dart';
import '../../../../data/services/service_interfaces.dart';

/// 智能提取分步骤进度卡片。
///
/// 每个步骤按 [NotificationExtractionService.extract] 的 onProgress 回调
/// 依次出现并淡入,完成项打勾,进行中项显示 spinner。
class ExtractionProgress extends StatelessWidget {
  const ExtractionProgress({
    super.key,
    required this.steps,
    required this.extracting,
  });

  final List<ExtractionStep> steps;
  final bool extracting;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (extracting)
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                const Icon(
                  Icons.check_circle_rounded,
                  color: AppColors.success,
                  size: 18,
                ),
              const SizedBox(width: 8),
              Text(
                extracting ? '正在提取...' : '提取完成',
                style: AppTypography.subtitle,
              ),
            ],
          ),
          const SizedBox(height: 12),
          for (int i = 0; i < steps.length; i++)
            StaggeredEnter(
              child: _StepRow(
                label: steps[i].label,
                done: !extracting || i < steps.length - 1,
              ),
            ),
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({required this.label, required this.done});

  final String label;
  final bool done;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          SizedBox(
            width: 18,
            height: 18,
            child: done
                ? const Icon(
                    Icons.check_circle_rounded,
                    color: AppColors.success,
                    size: 18,
                  )
                : const CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: AppTypography.body.copyWith(
                color: done ? AppColors.textPrimary : AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
