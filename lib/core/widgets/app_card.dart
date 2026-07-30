import 'package:flutter/material.dart';
import '../../app/design_system/app_colors.dart';
import '../../app/design_system/app_typography.dart';

/// 统一卡片样式 — 以边框为主、微弱阴影为辅,避免堆叠。
///
/// 默认圆角 12(符合设计规范 6–14px 范围),
/// 默认使用 [AppColorScheme] 自适应浅色/深色模式。
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.margin,
    this.onTap,
    this.borderRadius = 12,
    this.borderColor,
    this.backgroundColor,
    this.shadow = AppShadows.subtle,
    this.showBorder = true,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final VoidCallback? onTap;
  final double borderRadius;
  final Color? borderColor;
  final Color? backgroundColor;
  final List<BoxShadow> shadow;
  final bool showBorder;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final bg = backgroundColor ?? c.bgSurface;
    final border = borderColor ?? c.border;
    return Container(
      margin: margin,
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(borderRadius),
        border: showBorder ? Border.all(color: border, width: 0.6) : null,
        boxShadow: shadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(borderRadius),
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

/// 区块标题 — 左标题 + 右操作。
class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
    this.icon,
  });

  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        if (icon != null) ...[
          Icon(icon, size: 17, color: c.primary),
          const SizedBox(width: 6),
        ],
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: AppTypography.subtitle),
              if (subtitle != null) ...[
                const SizedBox(height: 2),
                Text(
                  subtitle!,
                  style: AppTypography.caption,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ],
          ),
        ),
        if (actionLabel != null && onAction != null)
          TextButton(
            onPressed: onAction,
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              minimumSize: const Size(0, 30),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: Text(actionLabel!, style: AppTypography.label),
          ),
      ],
    );
  }
}
