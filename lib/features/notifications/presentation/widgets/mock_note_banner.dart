import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';

/// 顶部提取说明横幅(科学边界标注,见 AGENTS.md §3)。
///
/// - Mock 模式: 提示"模拟提取,结果可手动修正"
/// - Real Backend 模式: 提示"由后端 LLM/规则抽取,请按原文核对"
///
/// 不论模式均保留人工修正入口,不伪造真实政策文件。
class MockNoteBanner extends StatelessWidget {
  const MockNoteBanner({super.key, this.isRealBackend = false});

  /// 是否为真实后端模式。
  final bool isRealBackend;

  @override
  Widget build(BuildContext context) {
    final text = isRealBackend ? '由后端智能抽取,结果可手动修正。请按通知原文核对字段。' : '模拟提取,结果可手动修正';
    final color =
        isRealBackend ? AppColors.primarySubtle : AppColors.warningSubtle;
    final borderColor = isRealBackend
        ? AppColors.primary.withValues(alpha: 0.35)
        : AppColors.warning.withValues(alpha: 0.35);
    final iconColor = isRealBackend ? AppColors.primary : AppColors.warning;
    final icon =
        isRealBackend ? Icons.cloud_done_outlined : Icons.info_outline_rounded;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: borderColor, width: 0.8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: iconColor),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: AppTypography.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
