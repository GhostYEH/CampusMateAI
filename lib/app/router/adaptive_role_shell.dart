import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../design_system/app_colors.dart';
import '../design_system/app_typography.dart';

/// 角色 Shell 的导航项。
class RoleShellDestination {
  const RoleShellDestination({
    required this.icon,
    required this.selectedIcon,
    required this.label,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
}

/// 自适应角色 Shell — 手机底部导航 / 宽屏侧栏。
///
/// 设计原则(遵循 frontend-design skill):
/// - 不"简单拉伸手机页面"
/// - 宽屏(>=1100)使用 NavigationRail,左侧 + 内容主区
/// - 窄屏使用底部 NavigationBar,贴近拇指区域
/// - 复用 AppColors,深色模式自动适配
/// - reduceMotion 开启时不使用弹性过渡
class AdaptiveRoleShell extends StatelessWidget {
  const AdaptiveRoleShell({
    super.key,
    required this.navigationShell,
    required this.destinations,
    this.title,
    this.showRailLabelAlways = true,
  });

  final StatefulNavigationShell navigationShell;
  final List<RoleShellDestination> destinations;
  final String? title;
  final bool showRailLabelAlways;

  static const double _railBreakpoint = 1100;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    if (width >= _railBreakpoint) {
      return _WideLayout(
        navigationShell: navigationShell,
        destinations: destinations,
        title: title,
      );
    }
    return _CompactLayout(
      navigationShell: navigationShell,
      destinations: destinations,
    );
  }
}

class _CompactLayout extends StatelessWidget {
  const _CompactLayout({
    required this.navigationShell,
    required this.destinations,
  });

  final StatefulNavigationShell navigationShell;
  final List<RoleShellDestination> destinations;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      body: SafeArea(
        top: false,
        child: navigationShell,
      ),
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(
              color: isDark ? AppColors.darkBorder : AppColors.border,
              width: 0.8,
            ),
          ),
        ),
        child: NavigationBar(
          selectedIndex: navigationShell.currentIndex,
          onDestinationSelected: _onTap,
          backgroundColor: c.bgSurface,
          indicatorColor: c.primarySubtle,
          labelTextStyle: WidgetStateProperty.resolveWith((states) {
            final selected = states.contains(WidgetState.selected);
            return AppTypography.label.copyWith(
              fontSize: 11,
              color: selected ? c.primary : c.textTertiary,
            );
          }),
          destinations: [
            for (final d in destinations)
              NavigationDestination(
                icon: Icon(d.icon, color: c.textSecondary),
                selectedIcon: Icon(d.selectedIcon, color: c.primary),
                label: d.label,
              ),
          ],
        ),
      ),
    );
  }

  void _onTap(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }
}

class _WideLayout extends StatelessWidget {
  const _WideLayout({
    required this.navigationShell,
    required this.destinations,
    required this.title,
  });

  final StatefulNavigationShell navigationShell;
  final List<RoleShellDestination> destinations;
  final String? title;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Scaffold(
      body: Row(
        children: [
          Container(
            width: 248,
            decoration: BoxDecoration(
              color: c.bgSurface,
              border: Border(
                right: BorderSide(color: c.border, width: 1),
              ),
            ),
            child: SafeArea(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (title != null) ...[
                    Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.lg,
                        AppSpacing.lg,
                        AppSpacing.lg,
                        AppSpacing.md,
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              color: c.primary,
                              borderRadius: BorderRadius.circular(AppRadius.sm),
                            ),
                            child: const Icon(
                              Icons.school_rounded,
                              color: AppColors.onPrimary,
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm + 2),
                          Expanded(
                            child: Text(
                              title!,
                              style: AppTypography.subtitle.copyWith(
                                color: c.textPrimary,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                  ],
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.symmetric(
                        vertical: AppSpacing.sm,
                      ),
                      children: [
                        for (var i = 0; i < destinations.length; i++)
                          _RailItem(
                            destination: destinations[i],
                            selected: i == navigationShell.currentIndex,
                            onTap: () => navigationShell.goBranch(
                              i,
                              initialLocation:
                                  i == navigationShell.currentIndex,
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          Expanded(
            child: SafeArea(
              child: navigationShell,
            ),
          ),
        ],
      ),
    );
  }
}

class _RailItem extends StatelessWidget {
  const _RailItem({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  final RoleShellDestination destination;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          margin: const EdgeInsets.symmetric(
            horizontal: AppSpacing.sm + 2,
            vertical: 2,
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm + 2,
          ),
          decoration: BoxDecoration(
            color: selected ? c.primarySubtle : Colors.transparent,
            borderRadius: BorderRadius.circular(AppRadius.md),
          ),
          child: Row(
            children: [
              Icon(
                selected ? destination.selectedIcon : destination.icon,
                size: 20,
                color: selected ? c.primary : c.textSecondary,
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Text(
                  destination.label,
                  style: AppTypography.body.copyWith(
                    color: selected ? c.primary : c.textSecondary,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
