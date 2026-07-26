import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'adaptive_role_shell.dart';

/// 教师 Shell — 5 Tab: 工作台 / 课程 / 发布 / 统计 / 我的。
class TeacherShell extends StatelessWidget {
  const TeacherShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  static const destinations = [
    RoleShellDestination(
      icon: Icons.dashboard_outlined,
      selectedIcon: Icons.dashboard_rounded,
      label: '工作台',
    ),
    RoleShellDestination(
      icon: Icons.class_outlined,
      selectedIcon: Icons.class_rounded,
      label: '课程',
    ),
    RoleShellDestination(
      icon: Icons.send_outlined,
      selectedIcon: Icons.send_rounded,
      label: '发布',
    ),
    RoleShellDestination(
      icon: Icons.insights_outlined,
      selectedIcon: Icons.insights_rounded,
      label: '统计',
    ),
    RoleShellDestination(
      icon: Icons.person_outline_rounded,
      selectedIcon: Icons.person_rounded,
      label: '我的',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return AdaptiveRoleShell(
      navigationShell: navigationShell,
      destinations: destinations,
      title: 'CampusMate AI · 教师',
    );
  }
}
