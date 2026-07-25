import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/cards.dart';

/// 首页快捷入口区 — 整理通知 / 新建待办 / 问AI导员 / 开始学习。
///
/// 提取自原 HomePage 的 _QuickActions。
class QuickActionSection extends StatelessWidget {
  const QuickActionSection({super.key});

  @override
  Widget build(BuildContext context) {
    final actions = <_ActionData>[
      const _ActionData(
        Icons.auto_fix_high_rounded,
        '整理通知',
        '/notifications/extract',
        AppColors.accent,
      ),
      const _ActionData(
        Icons.add_task_rounded,
        '新建待办',
        '/tasks/create',
        AppColors.primary,
      ),
      const _ActionData(
        Icons.smart_toy_rounded,
        '问AI导员',
        '/counselor',
        AppColors.info,
      ),
      const _ActionData(
        Icons.self_improvement_rounded,
        '开始学习',
        '/study',
        AppColors.success,
      ),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: Row(
        children: [
          for (final a in actions) ...[
            Expanded(
              child: QuickActionTile(
                icon: a.icon,
                label: a.label,
                route: a.route,
                color: a.color,
              ),
            ),
            if (a != actions.last) const SizedBox(width: 10),
          ],
        ],
      ),
    );
  }
}

class _ActionData {
  final IconData icon;
  final String label;
  final String route;
  final Color color;
  const _ActionData(this.icon, this.label, this.route, this.color);
}
