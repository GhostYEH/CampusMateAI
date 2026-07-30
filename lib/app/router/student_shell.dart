import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'adaptive_role_shell.dart';

/// 学生端导航：移动端五入口，桌面端常驻侧栏。
class StudentShell extends StatelessWidget {
  const StudentShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  static const destinations = [
    RoleShellDestination(
      icon: PhosphorIconsRegular.house,
      selectedIcon: PhosphorIconsFill.house,
      label: '首页',
    ),
    RoleShellDestination(
      icon: PhosphorIconsRegular.bookOpenText,
      selectedIcon: PhosphorIconsFill.bookOpenText,
      label: '课程',
    ),
    RoleShellDestination(
      icon: PhosphorIconsRegular.listChecks,
      selectedIcon: PhosphorIconsFill.listChecks,
      label: '任务',
    ),
    RoleShellDestination(
      icon: PhosphorIconsRegular.robot,
      selectedIcon: PhosphorIconsFill.robot,
      label: 'AI 导员',
    ),
    RoleShellDestination(
      icon: PhosphorIconsRegular.userCircle,
      selectedIcon: PhosphorIconsFill.userCircle,
      label: '我的',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return AdaptiveRoleShell(
      navigationShell: navigationShell,
      destinations: destinations,
      title: 'CampusMate',
      subtitle: '学生空间',
    );
  }
}
