import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';

/// 通知整理表单统一的 InputDecoration 样式。
///
/// 抽出到独立函数以避免多个 widget 重复定义。
InputDecoration notificationInputDecoration(String hint) => InputDecoration(
      hintText: hint,
      hintStyle: AppTypography.body.copyWith(color: AppColors.textTertiary),
      filled: true,
      fillColor: AppColors.bgSunken,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 12,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: const BorderSide(color: AppColors.primary, width: 1.2),
      ),
    );
