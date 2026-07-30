import 'package:flutter/material.dart';
import 'app_colors.dart';

/// 应用间距系统 — 8 倍数基准,辅以 4 倍数微调。
class AppSpacing {
  AppSpacing._();

  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double base = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 48;
  static const double edge = 16;
}

/// 圆角系统 — 统一柔和不锐利。
class AppRadius {
  AppRadius._();

  static const double xs = 6;
  static const double sm = 10;
  static const double md = 14;
  static const double lg = 18;
  static const double xl = 24;
  static const double pill = 999;
}

/// 动画时长与曲线 — 有节制,服务于反馈。
class AppMotion {
  AppMotion._();

  static const Duration instant = Duration(milliseconds: 80);
  static const Duration fast = Duration(milliseconds: 180);
  static const Duration base = Duration(milliseconds: 280);
  static const Duration slow = Duration(milliseconds: 420);
  static const Duration pageEnter = Duration(milliseconds: 480);
  static const Duration staggerStep = Duration(milliseconds: 60);

  static const Curve emphasized = Curves.easeOutCubic;
  static const Curve standard = Curves.easeOut;
  static const Curve decelerate = Curves.decelerate;
  static const Curve gentleSpring = Curves.easeOutBack;
}

/// 阴影系统 — 克制,以边框为主、阴影为辅。
class AppShadows {
  AppShadows._();

  static const List<BoxShadow> none = [];

  static const List<BoxShadow> subtle = [
    BoxShadow(
      color: Color(0x081B2730),
      blurRadius: 6,
      offset: Offset(0, 2),
    ),
  ];

  static const List<BoxShadow> card = [
    BoxShadow(
      color: Color(0x0A1B2730),
      blurRadius: 10,
      offset: Offset(0, 3),
    ),
  ];

  static const List<BoxShadow> elevated = [
    BoxShadow(
      color: Color(0x0F1B2730),
      blurRadius: 18,
      offset: Offset(0, 6),
    ),
  ];
}

/// 排版系统 — 中文优先,字重与字号建立清晰层级。
class AppTypography {
  AppTypography._();

  static const String fontFamily = 'NotoSansSC';

  static const TextStyle display = TextStyle(
    fontFamily: fontFamily,
    fontSize: 28,
    fontWeight: FontWeight.w700,
    height: 1.2,
    color: AppColors.textPrimary,
    fontFamilyFallback: ['PingFang SC', 'Microsoft YaHei'],
  );

  static const TextStyle headline = TextStyle(
    fontFamily: fontFamily,
    fontSize: 20,
    fontWeight: FontWeight.w700,
    height: 1.25,
    color: AppColors.textPrimary,
    letterSpacing: -0.2,
  );

  static const TextStyle title = TextStyle(
    fontFamily: fontFamily,
    fontSize: 16,
    fontWeight: FontWeight.w600,
    height: 1.35,
    color: AppColors.textPrimary,
  );

  static const TextStyle subtitle = TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    height: 1.4,
    color: AppColors.textPrimary,
  );

  static const TextStyle body = TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.55,
    color: AppColors.textPrimary,
  );

  static const TextStyle bodyStrong = TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    height: 1.5,
    color: AppColors.textPrimary,
  );

  static const TextStyle caption = TextStyle(
    fontFamily: fontFamily,
    fontSize: 12.5,
    fontWeight: FontWeight.w400,
    height: 1.45,
    color: AppColors.textSecondary,
  );

  static const TextStyle label = TextStyle(
    fontFamily: fontFamily,
    fontSize: 11.5,
    fontWeight: FontWeight.w600,
    height: 1.3,
    color: AppColors.textSecondary,
    letterSpacing: 0.2,
  );

  static const TextStyle overline = TextStyle(
    fontFamily: fontFamily,
    fontSize: 10.5,
    fontWeight: FontWeight.w600,
    height: 1.2,
    color: AppColors.textTertiary,
    letterSpacing: 0.5,
  );

  static const TextStyle metric = TextStyle(
    fontFamily: fontFamily,
    fontSize: 26,
    fontWeight: FontWeight.w700,
    height: 1.1,
    color: AppColors.textPrimary,
    letterSpacing: -0.5,
  );
}
