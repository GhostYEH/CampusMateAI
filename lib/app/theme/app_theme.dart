import 'package:flutter/material.dart';
import '../design_system/app_colors.dart';
import '../design_system/app_typography.dart';

/// 应用主题 — 浅色为默认,深色为补充。
///
/// 深度覆盖 Material 3 默认样式:
/// - 保留 useMaterial3 但大幅重写各组件主题
/// - 减少大圆角、胶囊按钮和明显阴影
/// - 普通圆角控制在 6–14px
/// - 普通按钮不使用默认胶囊化
/// - 纯白表面微调为冷色调
class AppTheme {
  AppTheme._();

  static ThemeData light() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: AppTypography.fontFamily,
    );
    return base.copyWith(
      scaffoldBackgroundColor: AppColors.bgBase,
      colorScheme: const ColorScheme.light(
        primary: AppColors.primary,
        onPrimary: AppColors.onPrimary,
        primaryContainer: AppColors.primaryContainer,
        onPrimaryContainer: AppColors.onPrimaryContainer,
        secondary: AppColors.accent,
        onSecondary: AppColors.onAccent,
        secondaryContainer: AppColors.accentContainer,
        onSecondaryContainer: AppColors.onAccentContainer,
        surface: AppColors.bgSurface,
        onSurface: AppColors.textPrimary,
        error: AppColors.danger,
        onError: AppColors.onAccent,
        outline: AppColors.border,
        outlineVariant: AppColors.border,
      ),
      textTheme: _buildTextTheme(base.textTheme),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.bgBase,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0.3,
        centerTitle: false,
        titleTextStyle: AppTypography.headline,
        surfaceTintColor: Colors.transparent,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.bgSurface,
        indicatorColor: AppColors.primarySubtle,
        labelTextStyle: WidgetStateProperty.all(AppTypography.label),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: AppColors.primary, size: 21);
          }
          return const IconThemeData(color: AppColors.textTertiary, size: 21);
        }),
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        height: 60,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
      cardTheme: CardThemeData(
        color: AppColors.bgSurface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.border, width: 0.6),
        ),
        clipBehavior: Clip.none,
      ),
      dividerTheme: const DividerThemeData(
        color: AppColors.border,
        thickness: 0.5,
        space: 1,
      ),
      inputDecorationTheme: _inputDecoration(
        fillColor: AppColors.bgSunken,
        hintColor: AppColors.textTertiary,
        border: AppColors.border,
        focusBorder: AppColors.primary,
        errorBorder: AppColors.danger,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: AppColors.onPrimary,
          disabledBackgroundColor: AppColors.textDisabled,
          disabledForegroundColor: AppColors.onPrimary,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: AppTypography.bodyStrong,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.primary,
          side: const BorderSide(color: AppColors.borderStrong, width: 0.8),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: AppTypography.bodyStrong,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.primary,
          textStyle: AppTypography.bodyStrong,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.bgSunken,
        selectedColor: AppColors.primarySubtle,
        labelStyle: AppTypography.label,
        secondaryLabelStyle: AppTypography.label,
        side: const BorderSide(color: Colors.transparent),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.bgSurface,
        selectedItemColor: AppColors.primary,
        unselectedItemColor: AppColors.textTertiary,
        showUnselectedLabels: true,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
        selectedLabelStyle: AppTypography.label,
        unselectedLabelStyle: AppTypography.label,
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.onPrimary;
          }
          return AppColors.bgSurface;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.primary;
          }
          return AppColors.borderStrong;
        }),
        trackOutlineColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return Colors.transparent;
          }
          return AppColors.borderStrong;
        }),
        thumbIcon: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const Icon(Icons.check, size: 14, color: AppColors.primary);
          }
          return null;
        }),
      ),
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.primary;
          }
          return Colors.transparent;
        }),
        checkColor: WidgetStateProperty.all(AppColors.onPrimary),
        side: const BorderSide(color: AppColors.borderStrong, width: 1.2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.primary,
        linearTrackColor: AppColors.bgSunken,
        circularTrackColor: AppColors.bgSunken,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.textPrimary,
        contentTextStyle:
            AppTypography.body.copyWith(color: AppColors.bgSurface),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
        actionTextColor: Colors.white,
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.bgSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: AppColors.border, width: 0.6),
        ),
        titleTextStyle: AppTypography.title,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.bgSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(14)),
        ),
      ),
      tabBarTheme: const TabBarThemeData(
        labelColor: AppColors.primary,
        unselectedLabelColor: AppColors.textSecondary,
        indicatorColor: AppColors.primary,
        indicatorSize: TabBarIndicatorSize.label,
        labelStyle: AppTypography.subtitle,
        unselectedLabelStyle: AppTypography.subtitle,
      ),
      iconTheme: const IconThemeData(
        color: AppColors.textSecondary,
        size: 22,
      ),
      listTileTheme: const ListTileThemeData(
        iconColor: AppColors.textSecondary,
        textColor: AppColors.textPrimary,
        subtitleTextStyle: AppTypography.caption,
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 0),
      ),
      drawerTheme: const DrawerThemeData(
        backgroundColor: AppColors.bgSurface,
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.onPrimary,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(14)),
        ),
      ),
      menuTheme: MenuThemeData(
        style: MenuStyle(
          backgroundColor: WidgetStateProperty.all(AppColors.bgSurface),
          surfaceTintColor: WidgetStateProperty.all(Colors.transparent),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
              side: const BorderSide(color: AppColors.border, width: 0.6),
            ),
          ),
        ),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: AppColors.bgSurface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: AppColors.border, width: 0.6),
        ),
      ),
      searchBarTheme: SearchBarThemeData(
        backgroundColor: WidgetStateProperty.all(AppColors.bgSunken),
        surfaceTintColor: WidgetStateProperty.all(Colors.transparent),
        shape: WidgetStateProperty.all(
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),
    );
  }

  static ThemeData dark() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      fontFamily: AppTypography.fontFamily,
    );
    return base.copyWith(
      scaffoldBackgroundColor: AppColors.darkBgBase,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.darkPrimary,
        onPrimary: Color(0xFF0E2A3D),
        primaryContainer: AppColors.darkPrimaryContainer,
        onPrimaryContainer: Color(0xFFD6E4EF),
        secondary: AppColors.accent,
        onSecondary: AppColors.onAccent,
        secondaryContainer: AppColors.accentContainer,
        onSecondaryContainer: AppColors.onAccentContainer,
        surface: AppColors.darkBgSurface,
        onSurface: AppColors.darkTextPrimary,
        surfaceContainerHighest: AppColors.darkBgElevated,
        error: AppColors.danger,
        onError: AppColors.onAccent,
        outline: AppColors.darkBorder,
        outlineVariant: AppColors.darkBorder,
      ),
      textTheme: _buildTextTheme(base.textTheme),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.darkBgBase,
        foregroundColor: AppColors.darkTextPrimary,
        elevation: 0,
        scrolledUnderElevation: 0.3,
        centerTitle: false,
        titleTextStyle: AppTypography.headline,
        surfaceTintColor: Colors.transparent,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.darkBgSurface,
        indicatorColor: AppColors.darkPrimaryContainer,
        labelTextStyle: WidgetStateProperty.all(AppTypography.label),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(
              color: AppColors.darkPrimary,
              size: 21,
            );
          }
          return const IconThemeData(
            color: AppColors.darkTextSecondary,
            size: 21,
          );
        }),
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        height: 60,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
      cardTheme: CardThemeData(
        color: AppColors.darkBgSurface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.darkBorder, width: 0.6),
        ),
        clipBehavior: Clip.none,
      ),
      dividerTheme: const DividerThemeData(
        color: AppColors.darkBorder,
        thickness: 0.5,
        space: 1,
      ),
      inputDecorationTheme: _inputDecoration(
        fillColor: AppColors.darkBgElevated,
        hintColor: AppColors.darkTextSecondary,
        border: AppColors.darkBorder,
        focusBorder: AppColors.darkPrimary,
        errorBorder: AppColors.danger,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.darkPrimary,
          foregroundColor: const Color(0xFF0E2A3D),
          disabledBackgroundColor: AppColors.darkBorder,
          disabledForegroundColor: AppColors.darkTextSecondary,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: AppTypography.bodyStrong,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.darkPrimary,
          side: const BorderSide(color: AppColors.darkBorder, width: 0.8),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: AppTypography.bodyStrong,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.darkPrimary,
          textStyle: AppTypography.bodyStrong,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.darkBgElevated,
        selectedColor: AppColors.darkPrimaryContainer,
        labelStyle: AppTypography.label,
        secondaryLabelStyle: AppTypography.label,
        side: const BorderSide(color: Colors.transparent),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.darkBgSurface,
        selectedItemColor: AppColors.darkPrimary,
        unselectedItemColor: AppColors.darkTextSecondary,
        showUnselectedLabels: true,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const Color(0xFF0E2A3D);
          }
          return AppColors.darkBgSurface;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.darkPrimary;
          }
          return AppColors.darkBorder;
        }),
      ),
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.darkPrimary;
          }
          return Colors.transparent;
        }),
        checkColor: WidgetStateProperty.all(const Color(0xFF0E2A3D)),
        side: const BorderSide(color: AppColors.darkBorder, width: 1.2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.darkPrimary,
        linearTrackColor: AppColors.darkBgElevated,
        circularTrackColor: AppColors.darkBgElevated,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.darkBgElevated,
        contentTextStyle:
            AppTypography.body.copyWith(color: AppColors.darkTextPrimary),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
        actionTextColor: AppColors.darkPrimary,
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.darkBgSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: AppColors.darkBorder, width: 0.6),
        ),
        titleTextStyle: AppTypography.title.copyWith(color: AppColors.darkTextPrimary),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.darkBgSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(14)),
        ),
      ),
      tabBarTheme: const TabBarThemeData(
        labelColor: AppColors.darkPrimary,
        unselectedLabelColor: AppColors.darkTextSecondary,
        indicatorColor: AppColors.darkPrimary,
        indicatorSize: TabBarIndicatorSize.label,
      ),
      iconTheme: const IconThemeData(
        color: AppColors.darkTextSecondary,
        size: 22,
      ),
      listTileTheme: const ListTileThemeData(
        iconColor: AppColors.darkTextSecondary,
        textColor: AppColors.darkTextPrimary,
        subtitleTextStyle: AppTypography.caption,
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 0),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: AppColors.darkPrimary,
        foregroundColor: Color(0xFF0E2A3D),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(14)),
        ),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: AppColors.darkBgSurface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: AppColors.darkBorder, width: 0.6),
        ),
      ),
    );
  }

  static TextTheme _buildTextTheme(TextTheme base) {
    return base.copyWith(
      displayLarge: AppTypography.display,
      displayMedium: AppTypography.display,
      headlineLarge: AppTypography.headline,
      headlineMedium: AppTypography.headline,
      titleLarge: AppTypography.headline,
      titleMedium: AppTypography.title,
      titleSmall: AppTypography.subtitle,
      bodyLarge: AppTypography.body,
      bodyMedium: AppTypography.body,
      bodySmall: AppTypography.caption,
      labelLarge: AppTypography.bodyStrong,
      labelMedium: AppTypography.label,
      labelSmall: AppTypography.overline,
    );
  }

  static InputDecorationTheme _inputDecoration({
    required Color fillColor,
    required Color hintColor,
    required Color border,
    required Color focusBorder,
    required Color errorBorder,
  }) {
    return InputDecorationTheme(
      filled: true,
      fillColor: fillColor,
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      hintStyle: AppTypography.body.copyWith(color: hintColor),
      labelStyle: AppTypography.label,
      floatingLabelStyle:
          AppTypography.label.copyWith(color: focusBorder),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: Colors.transparent),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: focusBorder, width: 1.2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: errorBorder, width: 1),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: errorBorder, width: 1.2),
      ),
      disabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: border, width: 0.6),
      ),
    );
  }
}
