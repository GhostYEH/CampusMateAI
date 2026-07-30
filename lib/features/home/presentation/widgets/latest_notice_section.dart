import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_typography.dart';
import '../../../../app/providers/app_providers.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/cards.dart';

/// 首页"校园通知"横向滑动区 — 紧凑卡片列表。
class LatestNoticeSection extends ConsumerWidget {
  const LatestNoticeSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notices = ref.watch(campusNoticesProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
          child: SectionHeader(
            title: '校园通知',
            icon: Icons.campaign_outlined,
            actionLabel: '查看全部',
            onAction: () => context.push('/notifications'),
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 124,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
            itemCount: notices.length,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (context, i) {
              final n = notices[i];
              return SizedBox(
                width: MediaQuery.of(context).size.width * 0.72,
                child: NoticeCard(
                  notice: n,
                  compact: true,
                  onTap: () => context.push('/notifications'),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}
