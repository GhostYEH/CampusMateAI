import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../mock/mock_data/mock_data.dart';

/// 快捷问题栏 — 横向滚动的预设问题 chips。
class QuickQuestionBar extends StatelessWidget {
  const QuickQuestionBar({
    super.key,
    required this.enabled,
    required this.onPick,
  });

  final bool enabled;
  final void Function(String) onPick;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 38,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.edge,
          vertical: 2,
        ),
        itemCount: MockData.quickQuestions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final q = MockData.quickQuestions[index];
          return ActionChip(
            label: Text(q, style: AppTypography.label.copyWith(fontSize: 11.5)),
            onPressed: enabled ? () => onPick(q) : null,
            backgroundColor: AppColors.bgSurface,
            side: const BorderSide(color: AppColors.border, width: 0.6),
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            visualDensity: VisualDensity.compact,
          );
        },
      ),
    );
  }
}

/// 输入区 — TextField + 发送/停止按钮。
///
/// 流式中显示"停止",非流式中显示"发送"。
/// 防重复点击:发送按钮在 isGenerating 时切换为停止按钮。
class ChatComposer extends StatelessWidget {
  const ChatComposer({
    super.key,
    required this.controller,
    required this.isGenerating,
    required this.onSend,
    required this.onStop,
  });

  final TextEditingController controller;
  final bool isGenerating;
  final VoidCallback onSend;
  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding:
          const EdgeInsets.fromLTRB(AppSpacing.edge, 6, AppSpacing.edge, 8),
      decoration: const BoxDecoration(
        color: AppColors.bgSurface,
        border: Border(
          top: BorderSide(color: AppColors.border, width: 0.6),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => onSend(),
              style: AppTypography.body,
              decoration: InputDecoration(
                hintText: '问问 AI 导员...',
                hintStyle: AppTypography.body.copyWith(
                  color: AppColors.textTertiary,
                ),
                filled: true,
                fillColor: AppColors.bgSunken,
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 10,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                  borderSide: BorderSide.none,
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                  borderSide: const BorderSide(
                    color: AppColors.primary,
                    width: 1.2,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          if (isGenerating)
            FilledButton.icon(
              onPressed: onStop,
              icon: const Icon(Icons.stop_rounded, size: 18),
              label: const Text('停止'),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.danger,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                ),
              ),
            )
          else
            FilledButton.icon(
              onPressed: onSend,
              icon: const Icon(Icons.send_rounded, size: 18),
              label: const Text('发送'),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: AppColors.onPrimary,
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
