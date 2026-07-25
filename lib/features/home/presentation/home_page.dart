import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/utils/date_utils.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/cards.dart';
import '../../../core/widgets/progress_ring.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/task.dart';
import '../../../mock/mock_data/mock_data.dart';

class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = DateTime.now();
    final user = ref.watch(currentUserProvider);
    final todayProgress = ref.watch(todayProgressProvider);
    final nearest = ref.watch(nearestDeadlineTaskProvider);
    final upcoming = ref.watch(upcomingTasksProvider);
    final notices = ref.watch(campusNoticesProvider);
    final unread = ref.watch(unreadNoticeCountProvider);
    final todayTotal = ref.watch(todayStudyTotalProvider);
    final todayTasks = ref.watch(todayTasksProvider);
    final greeting = AppDateUtils.greeting(now);

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async =>
              await Future.delayed(const Duration(milliseconds: 600)),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // ===== 顶部问候区 =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  child: _Header(
                    greeting: greeting,
                    name: user.nickname,
                    date: now,
                    unread: unread,
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 12)),

              // ===== 今日概览(英雄卡片) =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 60),
                  child: _TodayOverview(
                    progress: todayProgress,
                    nearest: nearest,
                    todayTaskCount: todayTasks.length,
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== 快捷入口 =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 120),
                  child: _QuickActions(),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== AI 导员问候 =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 180),
                  child: _CounselorGreeting(),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== 即将截止任务 =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 240),
                  child: Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
                    child: SectionHeader(
                      title: '即将截止',
                      icon: Icons.access_time_rounded,
                      actionLabel: '全部待办',
                      onAction: () => context.go('/tasks'),
                    ),
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 10)),
              upcoming.isEmpty
                  ? const SliverToBoxAdapter(child: _EmptyUpcoming())
                  : SliverList.separated(
                      itemCount: upcoming.length > 3 ? 3 : upcoming.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (context, i) {
                        final task = upcoming[i];
                        return StaggeredEnter(
                          delay: const Duration(milliseconds: 300) +
                              Duration(milliseconds: 60 * i),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.edge,
                            ),
                            child: TaskCard(
                              task: task,
                              compact: true,
                              onToggle: () => ref
                                  .read(taskListProvider.notifier)
                                  .toggleComplete(task),
                            ),
                          ),
                        );
                      },
                    ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== 最新通知(横向滑动) =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 360),
                  child: Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
                    child: SectionHeader(
                      title: '校园通知',
                      icon: Icons.campaign_outlined,
                      actionLabel: '查看全部',
                      onAction: () => context.push('/notifications'),
                    ),
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 10)),
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 420),
                  child: SizedBox(
                    height: 132,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.edge,
                      ),
                      itemCount: notices.length,
                      separatorBuilder: (_, __) => const SizedBox(width: 10),
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
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 20)),

              // ===== 学习时长概览 =====
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  delay: const Duration(milliseconds: 480),
                  child: _StudyOverview(todayTotal: todayTotal.valueOrNull),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 24)),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
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
                  '$greeting,$name',
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
                      const SizedBox(width: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 7,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.accentSubtle,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          '$unread 条未读',
                          style: AppTypography.label.copyWith(
                            color: AppColors.accent,
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
          const SizedBox(width: 12),
          GestureDetector(
            onTap: () => context.push('/notifications'),
            child: Stack(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: AppColors.primarySubtle,
                    shape: BoxShape.circle,
                    border: Border.all(color: AppColors.border, width: 0.8),
                  ),
                  child: const Icon(
                    Icons.notifications_none_rounded,
                    color: AppColors.primary,
                    size: 22,
                  ),
                ),
                if (unread > 0)
                  Positioned(
                    right: 2,
                    top: 2,
                    child: Container(
                      padding: const EdgeInsets.all(3),
                      decoration: const BoxDecoration(
                        color: AppColors.accent,
                        shape: BoxShape.circle,
                      ),
                      constraints:
                          const BoxConstraints(minWidth: 16, minHeight: 16),
                      child: Text(
                        '$unread',
                        style: const TextStyle(
                          color: AppColors.onAccent,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: () => context.go('/profile'),
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppColors.primary,
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.border, width: 0.8),
              ),
              child: const Center(
                child: Text(
                  '知',
                  style: TextStyle(
                    color: AppColors.onPrimary,
                    fontSize: 18,
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

class _TodayOverview extends StatelessWidget {
  const _TodayOverview({
    required this.progress,
    required this.nearest,
    required this.todayTaskCount,
  });

  final double progress;
  final Task? nearest;
  final int todayTaskCount;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: AppCard(
        padding: const EdgeInsets.all(18),
        backgroundColor: AppColors.primary,
        borderColor: AppColors.primary,
        showBorder: false,
        shadow: AppShadows.elevated,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                AnimatedProgressRing(
                  progress: progress,
                  size: 64,
                  strokeWidth: 6,
                  color: AppColors.onPrimary,
                  trackColor: AppColors.onPrimary.withValues(alpha: 0.2),
                  showLabel: true,
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '今日任务进度',
                        style: AppTypography.label.copyWith(
                          color: AppColors.onPrimary.withValues(alpha: 0.8),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        todayTaskCount == 0
                            ? '今天暂无截止任务'
                            : '今天有 $todayTaskCount 项截止',
                        style: AppTypography.subtitle.copyWith(
                          color: AppColors.onPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Divider(color: Color(0x33FFFFFF), height: 1),
            const SizedBox(height: 14),
            if (nearest != null)
              _NearestTask(nearest: nearest!)
            else
              Text(
                '没有临近截止的任务,可以安排一些自主学习',
                style: AppTypography.caption.copyWith(
                  color: AppColors.onPrimary.withValues(alpha: 0.85),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _NearestTask extends StatelessWidget {
  const _NearestTask({required this.nearest});
  final Task nearest;

  @override
  Widget build(BuildContext context) {
    final countdown = AppDateUtils.deadlineCountdown(nearest.deadline);
    return GestureDetector(
      onTap: () => context.go('/tasks'),
      child: Row(
        children: [
          const Icon(Icons.flag_rounded, color: AppColors.onPrimary, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '最紧急',
                  style: AppTypography.label.copyWith(
                    color: AppColors.onPrimary.withValues(alpha: 0.7),
                    fontSize: 11,
                  ),
                ),
                Text(
                  nearest.title,
                  style: AppTypography.bodyStrong.copyWith(
                    color: AppColors.onPrimary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: AppColors.onPrimary.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              countdown.text,
              style: AppTypography.label.copyWith(
                color: AppColors.onPrimary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickActions extends StatelessWidget {
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

class _CounselorGreeting extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: AppCard(
        onTap: () => context.go('/counselor'),
        padding: const EdgeInsets.all(16),
        borderColor: AppColors.primarySubtle,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: const BoxDecoration(
                color: AppColors.primarySubtle,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.smart_toy_rounded,
                color: AppColors.primary,
                size: 22,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text('AI 导员', style: AppTypography.subtitle),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.bgSunken,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '模拟模式',
                          style: AppTypography.overline.copyWith(fontSize: 10),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    MockData.counselorGreeting,
                    style: AppTypography.body,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              color: AppColors.textTertiary,
            ),
          ],
        ),
      ),
    );
  }
}

class _StudyOverview extends StatelessWidget {
  const _StudyOverview({required this.todayTotal});
  final Duration? todayTotal;

  @override
  Widget build(BuildContext context) {
    final minutes = todayTotal?.inMinutes ?? 0;
    final h = minutes ~/ 60;
    final m = minutes % 60;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: AppCard(
        onTap: () => context.go('/study'),
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const _BreathingDot(),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('今日学习', style: AppTypography.label),
                  const SizedBox(height: 2),
                  Text(
                    h > 0 ? '$h 小时 $m 分钟' : '$m 分钟',
                    style: AppTypography.metric,
                  ),
                ],
              ),
            ),
            const Icon(Icons.trending_up_rounded, color: AppColors.success),
            const SizedBox(width: 4),
            const Text(
              '专注还不错的样子',
              style: AppTypography.caption,
            ),
          ],
        ),
      ),
    );
  }
}

class _BreathingDot extends StatefulWidget {
  const _BreathingDot();
  @override
  State<_BreathingDot> createState() => _BreathingDotState();
}

class _BreathingDotState extends State<_BreathingDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      duration: const Duration(milliseconds: 1600),
      vsync: this,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (context, _) {
        return Container(
          width: 14,
          height: 14,
          decoration: BoxDecoration(
            color: AppColors.success.withValues(alpha: 0.3 + 0.5 * _c.value),
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: AppColors.success.withValues(alpha: 0.3 * _c.value),
                blurRadius: 8 + 6 * _c.value,
                spreadRadius: 1,
              ),
            ],
          ),
          child: Center(
            child: Container(
              width: 6,
              height: 6,
              decoration: const BoxDecoration(
                color: AppColors.success,
                shape: BoxShape.circle,
              ),
            ),
          ),
        );
      },
    );
  }
}

class _EmptyUpcoming extends StatelessWidget {
  const _EmptyUpcoming();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding:
          const EdgeInsets.symmetric(horizontal: AppSpacing.edge, vertical: 8),
      child: AppCard(
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: Column(
          children: [
            const Icon(
              Icons.event_available_rounded,
              size: 30,
              color: AppColors.textTertiary,
            ),
            const SizedBox(height: 8),
            const Text('近期没有截止任务', style: AppTypography.caption),
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
