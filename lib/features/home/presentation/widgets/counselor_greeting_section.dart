import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../mock/mock_data/mock_data.dart';

/// 首页 AI 导员问候卡片 — 点击进入 AI 导员页面。
///
/// 顶部明确标注"模拟模式",不得伪造真实政策(AGENTS.md §3)。
/// 提取自原 HomePage 的 _CounselorGreeting。
class CounselorGreetingSection extends StatelessWidget {
  const CounselorGreetingSection({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: AppCard(
        onTap: () => context.go('/counselor'),
        padding: const EdgeInsets.all(16),
        borderColor: AppColors.primarySubtle,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: const BoxDecoration(
                color: AppColors.primarySubtle,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.smart_toy_rounded,
                color: AppColors.primary,
                size: 22,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text('AI 导员', style: AppTypography.subtitle),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.bgSunken,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '模拟模式',
                          style: AppTypography.overline.copyWith(fontSize: 10),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    MockData.counselorGreeting,
                    style: AppTypography.body,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              color: AppColors.textTertiary,
            ),
          ],
        ),
      ),
    );
  }
}
