import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../app/providers/app_providers.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/cards.dart';
import '../../../../core/widgets/staggered_enter.dart';

/// 首页"即将截止"任务区 — 区段标题 + 任务列表 + 空状态。
class UrgentTaskSection extends ConsumerWidget {
  const UrgentTaskSection({super.key, this.maxItems = 3});

  final int maxItems;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final upcoming = ref.watch(upcomingTasksProvider);
    final showCount = upcoming.length > maxItems ? maxItems : upcoming.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
          child: SectionHeader(
            title: '即将截止',
            icon: Icons.access_time_rounded,
            actionLabel: '全部待办',
            onAction: () => context.go('/tasks'),
          ),
        ),
        const SizedBox(height: 8),
        if (upcoming.isEmpty)
          const _EmptyUpcoming()
        else
          Column(
            children: [
              for (int i = 0; i < showCount; i++)
                StaggeredEnter(
                  delay: const Duration(milliseconds: 300) +
                      Duration(milliseconds: 60 * i),
                  child: Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
                    child: TaskCard(
                      task: upcoming[i],
                      compact: true,
                      onToggle: () => ref
                          .read(taskListProvider.notifier)
                          .toggleComplete(upcoming[i]),
                    ),
                  ),
                ),
            ],
          ),
      ],
    );
  }
}

class _EmptyUpcoming extends StatelessWidget {
  const _EmptyUpcoming();

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding:
          const EdgeInsets.symmetric(horizontal: AppSpacing.edge, vertical: 4),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 24),
        decoration: BoxDecoration(
          color: c.bgSurface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: c.border, width: 0.6),
        ),
        child: Column(
          children: [
            Icon(
              Icons.event_available_rounded,
              size: 28,
              color: c.textTertiary,
            ),
            const SizedBox(height: 6),
            Text('近期没有截止任务', style: AppTypography.caption),
            TextButton(
              onPressed: () => context.go('/tasks'),
              child: const Text('去安排一下'),
            ),
          ],
        ),
      ),
    );
  }
}
