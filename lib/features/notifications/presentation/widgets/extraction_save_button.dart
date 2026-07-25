import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';

/// 保存为待办按钮 — 多状态(默认 / 保存中 / 已保存),防重复点击。
class ExtractionSaveButton extends StatelessWidget {
  const ExtractionSaveButton({
    super.key,
    required this.saving,
    required this.saved,
    required this.onSave,
  });

  final bool saving;
  final bool saved;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    final disabled = saving || saved;
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: disabled ? null : onSave,
        icon: saving
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.onPrimary,
                ),
              )
            : Icon(
                saved ? Icons.check_rounded : Icons.save_rounded,
                size: 20,
              ),
        label: Text(
          saving ? '保存中...' : (saved ? '已保存' : '保存为待办'),
        ),
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.success,
          foregroundColor: AppColors.onPrimary,
          disabledBackgroundColor: AppColors.success.withValues(alpha: 0.5),
          disabledForegroundColor: AppColors.onPrimary,
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
      ),
    );
  }
}
