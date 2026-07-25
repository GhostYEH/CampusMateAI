import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';

/// 保存成功浮层 — ScaleTransition + 勾选动画卡片。
class ExtractionSuccessOverlay extends StatelessWidget {
  const ExtractionSuccessOverlay({
    super.key,
    required this.scale,
    required this.taskName,
  });

  final Animation<double> scale;
  final String taskName;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black.withValues(alpha: 0.35),
      alignment: Alignment.center,
      child: ScaleTransition(
        scale: scale,
        child: _SuccessCard(taskName: taskName),
      ),
    );
  }
}

class _SuccessCard extends StatelessWidget {
  const _SuccessCard({required this.taskName});

  final String taskName;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width * 0.72;
    return ConstrainedBox(
      constraints: BoxConstraints(maxWidth: width),
      child: AppCard(
        padding: const EdgeInsets.all(24),
        backgroundColor: AppColors.bgSurface,
        showBorder: false,
        shadow: AppShadows.elevated,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: const BoxDecoration(
                color: AppColors.successSubtle,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.check_rounded,
                color: AppColors.success,
                size: 40,
              ),
            ),
            const SizedBox(height: 16),
            const Text('已保存为待办', style: AppTypography.subtitle),
            const SizedBox(height: 6),
            Text(
              taskName.isEmpty ? '即将返回首页' : '「$taskName」已加入待办',
              style: AppTypography.caption,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
