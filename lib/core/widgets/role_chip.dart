import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/design_system/app_colors.dart';
import '../../app/design_system/app_typography.dart';
import '../../data/models/models.dart';

/// 角色徽章 — 在多处复用显示当前用户角色。
///
/// 设计: 小面积状态色,不喧宾夺主。
/// - 学生: 青蓝
/// - 教师: 暖色琥珀
/// - 管理员: 中性灰
class RoleChip extends ConsumerWidget {
  const RoleChip({
    super.key,
    required this.role,
    this.compact = false,
    this.showIcon = true,
  });

  final UserRole role;
  final bool compact;
  final bool showIcon;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.appColors;
    final style = _styleOf(role, c);
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : 8,
        vertical: compact ? 1 : 2,
      ),
      decoration: BoxDecoration(
        color: style.bg,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: style.fg.withValues(alpha: 0.2), width: 0.8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showIcon) ...[
            Icon(style.icon, size: 12, color: style.fg),
            const SizedBox(width: 3),
          ],
          Text(
            style.label,
            style: AppTypography.label.copyWith(
              color: style.fg,
              fontSize: compact ? 10 : 11,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }

  _RoleChipStyle _styleOf(UserRole role, AppColorScheme c) {
    switch (role) {
      case UserRole.student:
        return _RoleChipStyle(
          label: '学生',
          icon: Icons.school_rounded,
          bg: c.primarySubtle,
          fg: c.primary,
        );
      case UserRole.teacher:
        return _RoleChipStyle(
          label: '教师',
          icon: Icons.co_present_rounded,
          bg: c.accentSubtle,
          fg: c.accent,
        );
      case UserRole.admin:
        return _RoleChipStyle(
          label: '管理员',
          icon: Icons.admin_panel_settings_outlined,
          bg: c.bgSunken,
          fg: c.textSecondary,
        );
    }
  }
}

class _RoleChipStyle {
  const _RoleChipStyle({
    required this.label,
    required this.icon,
    required this.bg,
    required this.fg,
  });

  final String label;
  final IconData icon;
  final Color bg;
  final Color fg;
}
