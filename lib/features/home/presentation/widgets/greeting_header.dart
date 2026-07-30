import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';

/// 首页顶部问候区 — 时间问候 + 日期 + 未读角标 + 通知/头像入口。
class GreetingHeader extends StatelessWidget {
  const GreetingHeader({
    super.key,
    required this.greeting,
    required this.name,
    required this.date,
    required this.unread,
  });

  final String greeting;
  final String name;
  final DateTime date;
  final int unread;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding:
          const EdgeInsets.fromLTRB(AppSpacing.edge, 16, AppSpacing.edge, 0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$greeting，$name',
                  style: AppTypography.headline,
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      AppDateUtils.formatDateFull(date),
                      style: AppTypography.caption,
                    ),
                    if (unread > 0) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 7,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: c.accentSubtle,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          '$unread 条未读',
                          style: AppTypography.label.copyWith(
                            color: c.accent,
                            fontSize: 10.5,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: () => context.push('/notifications'),
            child: Stack(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: c.primarySubtle,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.notifications_none_rounded,
                    color: c.primary,
                    size: 20,
                  ),
                ),
                if (unread > 0)
                  Positioned(
                    right: 1,
                    top: 1,
                    child: Container(
                      padding: const EdgeInsets.all(3),
                      decoration: BoxDecoration(
                        color: c.accent,
                        shape: BoxShape.circle,
                      ),
                      constraints:
                          const BoxConstraints(minWidth: 15, minHeight: 15),
                      child: Text(
                        '$unread',
                        style: const TextStyle(
                          color: AppColors.onAccent,
                          fontSize: 9,
                          fontWeight: FontWeight.w600,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: () => context.go('/profile'),
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: c.primary,
                shape: BoxShape.circle,
              ),
              child: const Center(
                child: Text(
                  '知',
                  style: TextStyle(
                    color: AppColors.onPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
