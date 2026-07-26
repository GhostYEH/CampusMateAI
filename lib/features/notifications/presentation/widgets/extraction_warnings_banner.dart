import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';

/// 通知抽取结果"需要确认"温和提示横幅。
///
/// 设计原则(遵循 frontend-design skill 的"晨曦校园"方向):
/// - 使用 warning 暖色,而非 danger 红色 — 表示"提示确认",非"系统错误"
/// - 圆角、低对比、克制 — 不喧宾夺主,信息层级低于主表单
/// - 每条 warning 配 info 图标,清晰列出待确认项
/// - 当 extractorMode 为 rules(降级模式)时,展示"本地规则提取"徽章
class ExtractionWarningsBanner extends StatelessWidget {
  const ExtractionWarningsBanner({
    super.key,
    required this.warnings,
    this.extractorMode = 'mock',
    this.confidence,
  });

  final List<String> warnings;

  /// 提取模式: mock | llm | rules
  /// - llm: 不显示模式徽章
  /// - rules: 显示"本地规则提取(降级模式)"徽章
  /// - mock: 不显示
  final String extractorMode;

  /// 置信度 0~1,可选展示
  final double? confidence;

  bool get _showRulesBadge => extractorMode == 'rules' && warnings.isNotEmpty;

  @override
  Widget build(BuildContext context) {
    if (warnings.isEmpty && !_showRulesBadge) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.only(top: 4, bottom: 4),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: AppColors.warningSubtle, width: 0.8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.help_outline_rounded,
                size: 14,
                color: AppColors.warning,
              ),
              const SizedBox(width: 5),
              Text(
                '需要确认',
                style: AppTypography.label.copyWith(
                  fontSize: 11.5,
                  color: AppColors.warning,
                ),
              ),
              const Spacer(),
              if (_showRulesBadge)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.bgSurface,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: AppColors.border, width: 0.5),
                  ),
                  child: Text(
                    '本地规则提取',
                    style: AppTypography.overline.copyWith(fontSize: 9),
                  ),
                ),
            ],
          ),
          if (warnings.isNotEmpty) ...[
            const SizedBox(height: 6),
            for (final w in warnings)
              Padding(
                padding: const EdgeInsets.only(top: 3, left: 19),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      margin: const EdgeInsets.only(top: 5),
                      width: 3,
                      height: 3,
                      decoration: const BoxDecoration(
                        color: AppColors.warning,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        w,
                        style: AppTypography.caption.copyWith(
                          fontSize: 11.5,
                          color: AppColors.textSecondary,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
          if (confidence != null) ...[
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.only(left: 19),
              child: Text(
                '提取置信度 ${(confidence! * 100).round()}% — 仅供辅助参考,请按通知原文核对',
                style: AppTypography.overline.copyWith(
                  fontSize: 9.5,
                  color: AppColors.textTertiary,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
