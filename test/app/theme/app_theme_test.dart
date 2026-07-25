import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/app/design_system/app_colors.dart';
import 'package:campus_companion/app/theme/app_theme.dart';

void main() {
  group('AppTheme', () {
    test('light 返回浅色 ThemeData', () {
      final theme = AppTheme.light();
      expect(theme.brightness, Brightness.light);
      expect(theme.scaffoldBackgroundColor, AppColors.bgBase);
      expect(theme.colorScheme.primary, AppColors.primary);
      expect(theme.colorScheme.onPrimary, AppColors.onPrimary);
      expect(theme.colorScheme.surface, AppColors.bgSurface);
      expect(theme.colorScheme.onSurface, AppColors.textPrimary);
    });

    test('dark 返回深色 ThemeData', () {
      final theme = AppTheme.dark();
      expect(theme.brightness, Brightness.dark);
      expect(theme.scaffoldBackgroundColor, AppColors.darkBgBase);
      expect(theme.colorScheme.primary, AppColors.darkPrimary);
      expect(theme.colorScheme.surface, AppColors.darkBgSurface);
      expect(theme.colorScheme.onSurface, AppColors.darkTextPrimary);
    });

    test('light 与 dark 主色不同(深色模式有独立主色)', () {
      final light = AppTheme.light();
      final dark = AppTheme.dark();
      expect(
        light.colorScheme.primary,
        isNot(equals(dark.colorScheme.primary)),
      );
      expect(
        light.scaffoldBackgroundColor,
        isNot(equals(dark.scaffoldBackgroundColor)),
      );
    });

    test('cardTheme 浅色使用浅边框,深色使用深边框', () {
      final lightCard = AppTheme.light().cardTheme;
      final darkCard = AppTheme.dark().cardTheme;
      final lightBorder =
          (lightCard.shape as RoundedRectangleBorder).side.color;
      final darkBorder = (darkCard.shape as RoundedRectangleBorder).side.color;
      expect(lightBorder, AppColors.border);
      expect(darkBorder, AppColors.darkBorder);
      expect(lightBorder, isNot(equals(darkBorder)));
    });

    test('appBarTheme 浅色与深色背景不同', () {
      final lightAppBar = AppTheme.light().appBarTheme;
      final darkAppBar = AppTheme.dark().appBarTheme;
      expect(lightAppBar.backgroundColor, AppColors.bgBase);
      expect(darkAppBar.backgroundColor, AppColors.darkBgBase);
      expect(lightAppBar.foregroundColor, AppColors.textPrimary);
      expect(darkAppBar.foregroundColor, AppColors.darkTextPrimary);
    });

    test('filledButtonTheme 浅色与深色主色一致语义但值不同', () {
      final lightBtn = AppTheme.light().filledButtonTheme.style!;
      final darkBtn = AppTheme.dark().filledButtonTheme.style!;
      final lightBg = lightBtn.backgroundColor?.resolve({})!;
      final darkBg = darkBtn.backgroundColor?.resolve({})!;
      expect(lightBg, AppColors.primary);
      expect(darkBg, AppColors.darkPrimary);
    });
  });

  group('AppColorScheme', () {
    test('浅色模式返回浅色调色板', () {
      const scheme = AppColorScheme(false);
      expect(scheme.primary, AppColors.primary);
      expect(scheme.bgSurface, AppColors.bgSurface);
      expect(scheme.textPrimary, AppColors.textPrimary);
      expect(scheme.border, AppColors.border);
    });

    test('深色模式返回深色调色板', () {
      const scheme = AppColorScheme(true);
      expect(scheme.primary, AppColors.darkPrimary);
      expect(scheme.bgSurface, AppColors.darkBgSurface);
      expect(scheme.textPrimary, AppColors.darkTextPrimary);
      expect(scheme.border, AppColors.darkBorder);
    });

    test('accent 与语义色在深浅模式下保持一致', () {
      const light = AppColorScheme(false);
      const dark = AppColorScheme(true);
      expect(light.accent, dark.accent);
      expect(light.danger, dark.danger);
      expect(light.success, dark.success);
      expect(light.warning, dark.warning);
      expect(light.info, dark.info);
    });

    test('bgSunken 深色使用 darkBgElevated', () {
      const light = AppColorScheme(false);
      const dark = AppColorScheme(true);
      expect(light.bgSunken, AppColors.bgSunken);
      expect(dark.bgSunken, AppColors.darkBgElevated);
    });
  });

  group('AppColors 静态色板', () {
    test('主色为青蓝色调(蓝绿分量高于红)', () {
      // 青蓝色: 蓝 > 红,且带绿分量
      const c = AppColors.primary;
      expect((c.b * 255).round(), greaterThan((c.r * 255).round()));
      expect((c.g * 255).round(), greaterThan((c.r * 255).round()));
    });

    test('深色与浅色背景有显著差异', () {
      expect(AppColors.bgBase, isNot(equals(AppColors.darkBgBase)));
      expect(AppColors.bgSurface, isNot(equals(AppColors.darkBgSurface)));
    });

    test('语义色明显区分', () {
      expect(AppColors.success, isNot(equals(AppColors.danger)));
      expect(AppColors.warning, isNot(equals(AppColors.danger)));
      expect(AppColors.info, isNot(equals(AppColors.danger)));
    });

    test('expressionColor 映射所有标签', () {
      expect(expressionColor('happy'), AppColors.exprHappy);
      expect(expressionColor('neutral'), AppColors.exprNeutral);
      expect(expressionColor('sad'), AppColors.exprSad);
      expect(expressionColor('angry'), AppColors.exprAngry);
      expect(expressionColor('fear'), AppColors.exprFear);
      expect(expressionColor('surprise'), AppColors.exprSurprise);
      expect(expressionColor('disgust'), AppColors.exprDisgust);
      expect(expressionColor('unknown'), AppColors.exprUnknown);
      expect(expressionColor('noface'), AppColors.exprNoFace);
    });

    test('expressionColor 大小写不敏感', () {
      expect(expressionColor('HAPPY'), AppColors.exprHappy);
      expect(expressionColor('Sad'), AppColors.exprSad);
    });

    test('expressionColor 未知标签返回 exprUnknown', () {
      expect(expressionColor('something'), AppColors.exprUnknown);
      expect(expressionColor(''), AppColors.exprUnknown);
    });
  });
}
