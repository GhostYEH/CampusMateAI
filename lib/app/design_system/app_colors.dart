import 'package:flutter/material.dart';

/// 应用色彩系统 — "晨曦校园" 方向
///
/// 设计哲学(遵循 frontend-design skill):
/// - 低饱和青蓝色作为主色,传达冷静、专注、可靠。
/// - 暖色(琥珀/珊瑚)仅在截止时间、情绪关怀、重要提醒处点缀使用,
///   不喧宾夺主。
/// - 表面使用带冷色微调的米白,避免纯白刺眼,也避免紫色渐变白底的俗套。
/// - 阴影克制,以边框 + 微弱阴影建立层级,而非堆叠。
class AppColors {
  AppColors._();

  // ===== 主色: 青蓝 (calm cyan-blue) =====
  static const Color primary = Color(0xFF2F6486);
  static const Color primaryHover = Color(0xFF275472);
  static const Color primarySubtle = Color(0xFFDCEAF2);
  static const Color primaryContainer = Color(0xFFE8F1F7);
  static const Color onPrimary = Color(0xFFFFFFFF);
  static const Color onPrimaryContainer = Color(0xFF0E2A3D);

  // ===== 暖色强调: 琥珀 (用于截止/关怀/提醒) =====
  static const Color accent = Color(0xFFE08A4E);
  static const Color accentSubtle = Color(0xFFFBE8D6);
  static const Color accentContainer = Color(0xFFFDF1E3);
  static const Color onAccent = Color(0xFFFFFFFF);
  static const Color onAccentContainer = Color(0xFF3D2410);

  // ===== 语义色 =====
  static const Color success = Color(0xFF4E8C6A);
  static const Color successSubtle = Color(0xFFDCEDE2);
  static const Color warning = Color(0xFFD49A3D);
  static const Color warningSubtle = Color(0xFFF7ECD3);
  static const Color danger = Color(0xFFC25450);
  static const Color dangerSubtle = Color(0xFFF6DAD8);
  static const Color info = Color(0xFF4A7FA8);

  // ===== 中性 / 表面 (浅色) =====
  static const Color bgBase = Color(0xFFF6F8FA); // 冷调米白
  static const Color bgSurface = Color(0xFFFFFFFF);
  static const Color bgElevated = Color(0xFFFBFCFD);
  static const Color bgSunken = Color(0xFFEFF2F5);
  static const Color border = Color(0xFFE2E7EC);
  static const Color borderStrong = Color(0xFFCBD3DB);

  // ===== 文本 =====
  static const Color textPrimary = Color(0xFF1B2730);
  static const Color textSecondary = Color(0xFF51606C);
  static const Color textTertiary = Color(0xFF8A97A3);
  static const Color textDisabled = Color(0xFFB6BFC8);
  static const Color textOnAccent = Color(0xFFFFFFFF);

  // ===== 表情识别语义色 (用于 CNN 结果可视化) =====
  static const Color exprHappy = Color(0xFFE8B14C);
  static const Color exprNeutral = Color(0xFF6E8AA0);
  static const Color exprSad = Color(0xFF6A7FB8);
  static const Color exprAngry = Color(0xFFCB645C);
  static const Color exprFear = Color(0xFF8A6BB1);
  static const Color exprSurprise = Color(0xFF5AA9A8);
  static const Color exprDisgust = Color(0xFF7E9B5A);
  static const Color exprUnknown = Color(0xFF9AA4AE);
  static const Color exprNoFace = Color(0xFFC2C9D0);

  // ===== 深色模式 (预留) =====
  static const Color darkBgBase = Color(0xFF11171D);
  static const Color darkBgSurface = Color(0xFF1A222A);
  static const Color darkBgElevated = Color(0xFF222C36);
  static const Color darkBorder = Color(0xFF33414D);
  static const Color darkTextPrimary = Color(0xFFE8EEF2);
  static const Color darkTextSecondary = Color(0xFFA8B4BE);
  static const Color darkPrimary = Color(0xFF6FA8CE);
  static const Color darkPrimaryContainer = Color(0xFF1E3A4E);
}

/// 上下文感知色板 — 根据 [BuildContext] 的亮度自动返回浅色或深色变体。
///
/// 使用示例:
/// ```dart
/// final c = context.appColors;
/// Container(color: c.bgSurface, child: Text('hi', style: TextStyle(color: c.textPrimary)));
/// ```
///
/// 这是为支持深色模式(AGENTS.md §2.2)而提供的便利扩展。
/// 已有的 `AppColors.*` 静态颜色保留为浅色默认值;
/// 在需要适配深色模式的 widget 中,改用 `context.appColors.*` 即可。
class AppColorScheme {
  const AppColorScheme(this._isDark);

  final bool _isDark;

  /// 从 [BuildContext] 构造对应的色板。
  factory AppColorScheme.of(BuildContext context) {
    return AppColorScheme(Theme.of(context).brightness == Brightness.dark);
  }

  // ===== 主色 =====
  Color get primary => _isDark ? AppColors.darkPrimary : AppColors.primary;
  Color get onPrimary =>
      _isDark ? const Color(0xFF0E2A3D) : AppColors.onPrimary;
  Color get primarySubtle =>
      _isDark ? AppColors.darkPrimaryContainer : AppColors.primarySubtle;
  Color get primaryContainer =>
      _isDark ? AppColors.darkPrimaryContainer : AppColors.primaryContainer;

  // ===== 暖色强调 =====
  Color get accent => AppColors.accent;
  Color get accentSubtle => AppColors.accentSubtle;
  Color get accentContainer => AppColors.accentContainer;

  // ===== 语义色 =====
  Color get success => AppColors.success;
  Color get successSubtle => _isDark
      ? AppColors.success.withValues(alpha: 0.18)
      : AppColors.successSubtle;
  Color get warning => AppColors.warning;
  Color get warningSubtle => _isDark
      ? AppColors.warning.withValues(alpha: 0.18)
      : AppColors.warningSubtle;
  Color get danger => AppColors.danger;
  Color get dangerSubtle => _isDark
      ? AppColors.danger.withValues(alpha: 0.18)
      : AppColors.dangerSubtle;
  Color get info => AppColors.info;

  // ===== 表面 =====
  Color get bgBase => _isDark ? AppColors.darkBgBase : AppColors.bgBase;
  Color get bgSurface =>
      _isDark ? AppColors.darkBgSurface : AppColors.bgSurface;
  Color get bgElevated =>
      _isDark ? AppColors.darkBgElevated : AppColors.bgElevated;
  Color get bgSunken => _isDark ? AppColors.darkBgElevated : AppColors.bgSunken;
  Color get border => _isDark ? AppColors.darkBorder : AppColors.border;
  Color get borderStrong =>
      _isDark ? AppColors.darkBorder : AppColors.borderStrong;

  // ===== 文本 =====
  Color get textPrimary =>
      _isDark ? AppColors.darkTextPrimary : AppColors.textPrimary;
  Color get textSecondary =>
      _isDark ? AppColors.darkTextSecondary : AppColors.textSecondary;
  Color get textTertiary =>
      _isDark ? AppColors.darkTextSecondary : AppColors.textTertiary;
  Color get textDisabled =>
      _isDark ? AppColors.darkBorder : AppColors.textDisabled;
}

/// [BuildContext] 上的色板访问器。
extension AppColorsExtension on BuildContext {
  AppColorScheme get appColors => AppColorScheme.of(this);
}

/// 表情标签对应的展示色
Color expressionColor(String label) {
  switch (label.toLowerCase()) {
    case 'happy':
      return AppColors.exprHappy;
    case 'neutral':
      return AppColors.exprNeutral;
    case 'sad':
      return AppColors.exprSad;
    case 'angry':
      return AppColors.exprAngry;
    case 'fear':
      return AppColors.exprFear;
    case 'surprise':
      return AppColors.exprSurprise;
    case 'disgust':
      return AppColors.exprDisgust;
    case 'unknown':
      return AppColors.exprUnknown;
    case 'noface':
      return AppColors.exprNoFace;
    default:
      return AppColors.exprUnknown;
  }
}
