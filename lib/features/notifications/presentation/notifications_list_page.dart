import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/cards.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/notice.dart';

/// 校园通知列表页。
///
/// 从首页"查看全部"或通知铃铛进入。提供"智能整理通知"强调入口,
/// 列表分层进入,点击通知可标记已读并展开查看原文与操作。
class NotificationsListPage extends ConsumerWidget {
  const NotificationsListPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notices = ref.watch(campusNoticesProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('校园通知'),
        actions: [
          TextButton.icon(
            onPressed: () =>
                ref.read(campusNoticesProvider.notifier).markAllRead(),
            icon: const Icon(Icons.done_all_rounded, size: 18),
            label: const Text('全部已读'),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: SafeArea(
        child: notices.isEmpty
            ? const EmptyStateView(
                icon: Icons.notifications_none_rounded,
                title: '暂无校园通知',
                message: '新的通知到达后会显示在这里',
              )
            : Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.edge,
                      12,
                      AppSpacing.edge,
                      4,
                    ),
                    child: StaggeredEnter(
                      child: _ExtractEntryCard(
                        onTap: () => context.push('/notifications/extract'),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Expanded(
                    child: StaggeredListView(
                      itemCount: notices.length,
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.edge,
                        vertical: 4,
                      ),
                      separator: const SizedBox(height: 12),
                      itemBuilder: (context, i) {
                        return _NoticeListItem(notice: notices[i]);
                      },
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

/// 顶部"智能整理通知"强调入口(暖色 accent)。
class _ExtractEntryCard extends StatelessWidget {
  const _ExtractEntryCard({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      padding: const EdgeInsets.all(16),
      backgroundColor: AppColors.accentContainer,
      borderColor: AppColors.accentSubtle,
      child: const Row(
        children: [
          SizedBox(
            width: 40,
            height: 40,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: AppColors.accent,
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.auto_fix_high_rounded,
                color: AppColors.onAccent,
                size: 22,
              ),
            ),
          ),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('智能整理通知', style: AppTypography.subtitle),
                SizedBox(height: 2),
                Text(
                  '粘贴通知原文,自动提取任务、材料与截止时间',
                  style: AppTypography.caption,
                ),
              ],
            ),
          ),
          Icon(
            Icons.chevron_right_rounded,
            color: AppColors.accent,
            size: 22,
          ),
        ],
      ),
    );
  }
}

/// 单条通知项。点击标记已读并展开原文与操作。
class _NoticeListItem extends ConsumerStatefulWidget {
  const _NoticeListItem({required this.notice});

  final CampusNotice notice;

  @override
  ConsumerState<_NoticeListItem> createState() => _NoticeListItemState();
}

class _NoticeListItemState extends ConsumerState<_NoticeListItem> {
  bool _expanded = false;

  void _toggle() {
    final notice = widget.notice;
    if (!notice.read) {
      ref.read(campusNoticesProvider.notifier).markRead(notice.id);
    }
    setState(() => _expanded = !_expanded);
  }

  @override
  Widget build(BuildContext context) {
    final notice = widget.notice;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        NoticeCard(notice: notice, onTap: _toggle),
        AnimatedSize(
          duration: AppMotion.base,
          curve: AppMotion.emphasized,
          child: _expanded
              ? _ExpandedDetail(
                  notice: notice,
                  onExtract: () => context.push('/notifications/extract'),
                )
              : const SizedBox(width: double.infinity, height: 0),
        ),
      ],
    );
  }
}

/// 展开后的通知详情:完整原文、标签、整理入口。
class _ExpandedDetail extends StatelessWidget {
  const _ExpandedDetail({required this.notice, required this.onExtract});

  final CampusNotice notice;
  final VoidCallback onExtract;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(14),
      backgroundColor: AppColors.bgElevated,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(notice.content, style: AppTypography.body),
          if (notice.tags.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final tag in notice.tags)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.primarySubtle,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      tag,
                      style: AppTypography.label.copyWith(
                        color: AppColors.primary,
                        fontSize: 11,
                      ),
                    ),
                  ),
              ],
            ),
          ],
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onExtract,
              icon: const Icon(Icons.auto_fix_high_rounded, size: 18),
              label: const Text('智能整理此通知'),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.accent,
                foregroundColor: AppColors.onAccent,
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
