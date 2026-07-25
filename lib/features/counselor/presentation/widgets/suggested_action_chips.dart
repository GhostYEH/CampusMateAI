import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../data/models/chat.dart';

/// 建议操作 chips — AI 回复完成后给出的快捷动作(如"查看今日任务")。
class SuggestedActionChips extends StatelessWidget {
  const SuggestedActionChips({
    super.key,
    required this.actions,
    required this.onAction,
  });

  final List<SuggestedAction> actions;
  final void Function(SuggestedAction) onAction;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      child: Wrap(
        spacing: 6,
        runSpacing: 6,
        children: [
          for (final a in actions)
            ActionChip(
              label: Text(
                a.label,
                style: AppTypography.label.copyWith(fontSize: 11.5),
              ),
              onPressed: () => onAction(a),
              backgroundColor: AppColors.primarySubtle,
              side: const BorderSide(
                color: AppColors.primarySubtle,
                width: 0.5,
              ),
              labelPadding: const EdgeInsets.symmetric(horizontal: 2),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              visualDensity: VisualDensity.compact,
            ),
        ],
      ),
    );
  }
}

/// AI 消息底部操作行(复制 / 重新生成)。
class MessageActions extends StatelessWidget {
  const MessageActions({
    super.key,
    required this.onCopy,
    required this.onRegenerate,
    required this.canRegenerate,
  });

  final VoidCallback onCopy;
  final VoidCallback onRegenerate;
  final bool canRegenerate;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 6),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _inlineButton(icon: Icons.copy_rounded, label: '复制', onTap: onCopy),
          if (canRegenerate) ...[
            const SizedBox(width: 6),
            _inlineButton(
              icon: Icons.refresh_rounded,
              label: '重新生成',
              onTap: onRegenerate,
            ),
          ],
        ],
      ),
    );
  }

  Widget _inlineButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: AppColors.textTertiary),
            const SizedBox(width: 3),
            Text(label, style: AppTypography.overline.copyWith(fontSize: 10)),
          ],
        ),
      ),
    );
  }
}

/// 流式生成中"停止生成"按钮。
class StreamingActions extends StatelessWidget {
  const StreamingActions({super.key, required this.onStop});

  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 6),
      child: InkWell(
        onTap: onStop,
        borderRadius: BorderRadius.circular(AppRadius.xs),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.stop_circle_rounded,
                size: 13,
                color: AppColors.danger,
              ),
              const SizedBox(width: 3),
              Text(
                '停止生成',
                style: AppTypography.overline.copyWith(
                  fontSize: 10,
                  color: AppColors.danger,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
