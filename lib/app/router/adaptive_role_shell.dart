import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../design_system/app_colors.dart';
import '../design_system/app_typography.dart';

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

/// 移动端与桌面端共用路由,但使用两套针对设备设计的导航。
class AdaptiveRoleShell extends StatelessWidget {
  const AdaptiveRoleShell({
    super.key,
    required this.navigationShell,
    required this.destinations,
    this.title,
    this.subtitle,
    this.showRailLabelAlways = true,
  });

  final StatefulNavigationShell navigationShell;
  final List<RoleShellDestination> destinations;
  final String? title;
  final String? subtitle;
  final bool showRailLabelAlways;

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.sizeOf(context).width >= 1100) {
      return _DesktopShell(
        navigationShell: navigationShell,
        destinations: destinations,
        title: title,
        subtitle: subtitle,
      );
    }
    return _MobileShell(
      navigationShell: navigationShell,
      destinations: destinations,
    );
  }
}

class _DesktopShell extends StatelessWidget {
  const _DesktopShell({
    required this.navigationShell,
    required this.destinations,
    required this.title,
    required this.subtitle,
  });

  final StatefulNavigationShell navigationShell;
  final List<RoleShellDestination> destinations;
  final String? title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Scaffold(
      body: Row(
        children: [
          Container(
            width: 220,
            color: c.bgSurface,
            child: SafeArea(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 20, 18, 16),
                    child: Row(
                      children: [
                        Container(
                          width: 30,
                          height: 30,
                          decoration: BoxDecoration(
                            color: c.primary,
                            borderRadius: BorderRadius.circular(8),
                            boxShadow: [
                              BoxShadow(
                                color: c.primary.withValues(alpha: .18),
                                blurRadius: 10,
                                offset: const Offset(0, 3),
                              ),
                            ],
                          ),
                          child: PhosphorIcon(
                            PhosphorIconsBold.graduationCap,
                            color: c.bgSurface,
                            size: 16,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                title ?? 'CampusMate',
                                style: AppTypography.subtitle.copyWith(
                                  color: c.textPrimary,
                                  letterSpacing: -.2,
                                ),
                              ),
                              Text(
                                subtitle ?? '校园工作台',
                                style: AppTypography.overline.copyWith(
                                  color: c.textTertiary,
                                  letterSpacing: .6,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 2, 16, 6),
                    child: Text(
                      '导航',
                      style: AppTypography.overline.copyWith(
                        color: c.textTertiary,
                        letterSpacing: .8,
                      ),
                    ),
                  ),
                  for (var i = 0; i < destinations.length; i++)
                    _DesktopNavItem(
                      destination: destinations[i],
                      selected: i == navigationShell.currentIndex,
                      onTap: () => navigationShell.goBranch(
                        i,
                        initialLocation: i == navigationShell.currentIndex,
                      ),
                    ),
                  const Spacer(),
                ],
              ),
            ),
          ),
          Container(width: 1, color: c.border.withValues(alpha: .6)),
          Expanded(
            child: ColoredBox(
              color: c.bgBase,
              child: SafeArea(child: navigationShell),
            ),
          ),
        ],
      ),
    );
  }
}

class _DesktopNavItem extends StatefulWidget {
  const _DesktopNavItem({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  final RoleShellDestination destination;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_DesktopNavItem> createState() => _DesktopNavItemState();
}

class _DesktopNavItemState extends State<_DesktopNavItem> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final active = widget.selected;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: Semantics(
        button: true,
        selected: active,
        label: widget.destination.label,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: widget.onTap,
            child: AnimatedContainer(
              duration: AppMotion.fast,
              curve: AppMotion.emphasized,
              height: 44,
              margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
              padding: const EdgeInsets.only(left: 10),
              decoration: BoxDecoration(
                color: active
                    ? c.primary.withValues(alpha: .07)
                    : _hovered
                        ? c.bgSunken.withValues(alpha: .6)
                        : Colors.transparent,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  AnimatedContainer(
                    duration: AppMotion.fast,
                    width: 3,
                    height: active ? 18 : 0,
                    decoration: BoxDecoration(
                      color: c.primary,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: 12),
                  PhosphorIcon(
                    active ? widget.destination.selectedIcon : widget.destination.icon,
                    size: 18,
                    color: active ? c.primary : c.textSecondary,
                  ),
                  const SizedBox(width: 10),
                  Text(
                    widget.destination.label,
                    style: AppTypography.body.copyWith(
                      color: active ? c.textPrimary : c.textSecondary,
                      fontWeight: active ? FontWeight.w600 : FontWeight.w400,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _MobileShell extends StatelessWidget {
  const _MobileShell({
    required this.navigationShell,
    required this.destinations,
  });

  final StatefulNavigationShell navigationShell;
  final List<RoleShellDestination> destinations;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Scaffold(
      body: SafeArea(top: false, child: navigationShell),
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          color: c.bgSurface,
          border: Border(top: BorderSide(color: c.border, width: .6)),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 58,
            child: Row(
              children: [
                for (var i = 0; i < destinations.length; i++)
                  Expanded(
                    child: _MobileNavItem(
                      destination: destinations[i],
                      selected: i == navigationShell.currentIndex,
                      onTap: () => navigationShell.goBranch(
                        i,
                        initialLocation: i == navigationShell.currentIndex,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MobileNavItem extends StatelessWidget {
  const _MobileNavItem({
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
    return Semantics(
      selected: selected,
      button: true,
      label: destination.label,
      child: InkResponse(
        onTap: onTap,
        radius: 24,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 4),
            AnimatedContainer(
              duration: AppMotion.fast,
              width: selected ? 20 : 0,
              height: 2,
              decoration: BoxDecoration(
                color: c.primary,
                borderRadius: BorderRadius.circular(1),
              ),
            ),
            const SizedBox(height: 5),
            PhosphorIcon(
              selected ? destination.selectedIcon : destination.icon,
              size: 20,
              color: selected ? c.primary : c.textTertiary,
            ),
            const SizedBox(height: 2),
            Text(
              destination.label,
              style: AppTypography.overline.copyWith(
                fontSize: 10,
                letterSpacing: 0,
                color: selected ? c.primary : c.textTertiary,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
