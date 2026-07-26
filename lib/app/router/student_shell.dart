import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'adaptive_role_shell.dart';

/// 学生 Shell — 5 Tab: 首页 / 课程 / 任务 / AI 导员 / 我的。
///
/// 沿用学生原有体验: 个人待办、AI 导员、知识库、学习陪伴、精确提醒。
/// 新增 "课程" Tab 整合班级通知 / 任务 / 资料。
class StudentShell extends StatelessWidget {
  const StudentShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  static const destinations = [
    RoleShellDestination(
      icon: Icons.home_outlined,
      selectedIcon: Icons.home_rounded,
      label: '首页',
    ),
    RoleShellDestination(
      icon: Icons.class_outlined,
      selectedIcon: Icons.class_rounded,
      label: '课程',
    ),
    RoleShellDestination(
      icon: Icons.checklist_outlined,
      selectedIcon: Icons.checklist_rounded,
      label: '任务',
    ),
    RoleShellDestination(
      icon: Icons.smart_toy_outlined,
      selectedIcon: Icons.smart_toy_rounded,
      label: 'AI导员',
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
      title: 'CampusMate AI · 学生',
    );
  }
}
