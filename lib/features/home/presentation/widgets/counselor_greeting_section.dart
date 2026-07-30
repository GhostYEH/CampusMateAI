import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../mock/mock_data/mock_data.dart';

/// 首页 AI 导员问候卡片 — 点击进入 AI 导员页面。
class CounselorGreetingSection extends StatelessWidget {
  const CounselorGreetingSection({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: AppCard(
        onTap: () => context.go('/counselor'),
        padding: const EdgeInsets.all(14),
        borderRadius: 12,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: c.primarySubtle,
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.smart_toy_rounded,
                color: c.primary,
                size: 20,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text('AI 导员', style: AppTypography.subtitle),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 5,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          color: c.bgSunken,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '模拟模式',
                          style: AppTypography.overline.copyWith(fontSize: 10),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 5),
                  Text(
                    MockData.counselorGreeting,
                    style: AppTypography.body,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              color: c.textTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }
}
