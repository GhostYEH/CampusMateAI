import 'package:flutter/material.dart';

/// 响应式布局断点。
///
/// 设计(遵循 AGENTS.md §8.7):
/// - 手机: 单列,底部导航
/// - 平板(>=768): 主从布局可启用
/// - 桌面(>=1100): NavigationRail / 双栏 / 多栏
class AppBreakpoints {
  AppBreakpoints._();

  static const double tablet = 768;
  static const double desktop = 1100;
  static const double wide = 1440;
}

/// 根据屏幕宽度派生布局类型。
enum LayoutTier { compact, medium, expanded }

extension LayoutTierX on LayoutTier {
  bool get isCompact => this == LayoutTier.compact;
  bool get isMedium => this == LayoutTier.medium;
  bool get isExpanded => this == LayoutTier.expanded;
  bool get isWide => this != LayoutTier.compact;
}

/// 当前 [BuildContext] 的 LayoutTier。
LayoutTier layoutTierOf(BuildContext context) {
  final w = MediaQuery.sizeOf(context).width;
  if (w >= AppBreakpoints.desktop) return LayoutTier.expanded;
  if (w >= AppBreakpoints.tablet) return LayoutTier.medium;
  return LayoutTier.compact;
}

/// 在不同断点下选择不同值。
T responsiveValue<T>(
  BuildContext context, {
  required T compact,
  T? medium,
  T? expanded,
}) {
  final tier = layoutTierOf(context);
  if (tier == LayoutTier.expanded && expanded != null) return expanded;
  if (tier != LayoutTier.compact && medium != null) return medium;
  return compact;
}

/// 主从布局容器 — 宽屏下显示左右双栏,窄屏下只显示单个子项。
///
/// 用于课程列表 / 详情、班级 / 成员等场景。
class MasterDetailContainer extends StatelessWidget {
  const MasterDetailContainer({
    super.key,
    required this.master,
    required this.detail,
    this.masterWidth = 340,
  });

  final Widget master;
  final Widget? detail;
  final double masterWidth;

  @override
  Widget build(BuildContext context) {
    final tier = layoutTierOf(context);
    if (tier.isCompact) {
      return master;
    }
    return Row(
      children: [
        SizedBox(width: masterWidth, child: master),
        if (detail != null) ...[
          Container(width: 1, color: Theme.of(context).dividerColor),
          Expanded(child: detail!),
        ] else
          Expanded(child: Container()),
      ],
    );
  }
}
