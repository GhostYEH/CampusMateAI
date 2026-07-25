import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../mock/mock_data/mock_data.dart';
import 'notification_form_styles.dart';

/// 通知输入面板 — 多行文本 + 样例芯片 + 智能整理按钮。
///
/// 提取自原 NotificationExtractPage 的 _InputSection,逻辑保持不变。
class NoticeInputPanel extends StatelessWidget {
  const NoticeInputPanel({
    super.key,
    required this.controller,
    required this.extracting,
    required this.onExtract,
  });

  final TextEditingController controller;
  final bool extracting;
  final VoidCallback onExtract;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: '粘贴通知',
            subtitle: '将校园通知原文粘贴到下方',
            icon: Icons.content_paste_rounded,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: controller,
            maxLines: 5,
            minLines: 3,
            decoration: notificationInputDecoration('在此粘贴校园通知原文...'),
          ),
          const SizedBox(height: 12),
          const Text('示例样例', style: AppTypography.label),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (int i = 0; i < MockData.noticeSamples.length; i++)
                _SampleChip(
                  label: '样例 ${i + 1}',
                  onTap: () => controller.text = MockData.noticeSamples[i],
                ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: extracting ? null : onExtract,
              icon: extracting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.onPrimary,
                      ),
                    )
                  : const Icon(Icons.auto_fix_high_rounded, size: 20),
              label: Text(extracting ? '正在提取...' : '智能整理'),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: AppColors.onPrimary,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 示例样例芯片。
class _SampleChip extends StatelessWidget {
  const _SampleChip({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.primarySubtle,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: AppColors.border, width: 0.6),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.flash_on_rounded,
              size: 14,
              color: AppColors.primary,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTypography.label.copyWith(color: AppColors.primary),
            ),
          ],
        ),
      ),
    );
  }
}
