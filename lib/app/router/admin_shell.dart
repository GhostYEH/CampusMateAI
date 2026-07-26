import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'adaptive_role_shell.dart';

/// 管理员 Shell — 最小 3 Tab: 用户 / 课程与班级 / 系统状态。
class AdminShell extends StatelessWidget {
  const AdminShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  static const destinations = [
    RoleShellDestination(
      icon: Icons.group_outlined,
      selectedIcon: Icons.group_rounded,
      label: '用户',
    ),
    RoleShellDestination(
      icon: Icons.class_outlined,
      selectedIcon: Icons.class_rounded,
      label: '课程与班级',
    ),
    RoleShellDestination(
      icon: Icons.monitor_heart_outlined,
      selectedIcon: Icons.monitor_heart_rounded,
      label: '系统状态',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return AdaptiveRoleShell(
      navigationShell: navigationShell,
      destinations: destinations,
      title: 'CampusMate AI · 管理员',
    );
  }
}
