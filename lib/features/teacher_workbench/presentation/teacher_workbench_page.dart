import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../app/providers/auth_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/skeleton_loader.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/models.dart';

/// 教师工作台 — 视觉重点是"下一步行动",而非统计数字堆叠。
///
/// 布局(遵循 frontend-design skill 与 AGENTS.md §6.1):
/// 1. 顶部问候 + 角色徽章
/// 2. 下一步行动卡片(主要视觉重点,优先级 high 用琥珀强调)
/// 3. 概览统计(横向紧凑展示:课程/班级/学生/活跃任务)
/// 4. 待办统计(待批阅/未读通知/逾期 — 三色状态条)
/// 5. 最近活动流(时间线样式)
class TeacherWorkbenchPage extends ConsumerStatefulWidget {
  const TeacherWorkbenchPage({super.key});

  @override
  ConsumerState<TeacherWorkbenchPage> createState() =>
      _TeacherWorkbenchPageState();
}

class _TeacherWorkbenchPageState extends ConsumerState<TeacherWorkbenchPage> {
  TeacherDashboard? _dashboard;
  bool _loading = true;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final svc = ref.read(dashboardServiceProvider);
      final dashboard = await svc.getTeacherDashboard();
      if (!mounted) return;
      setState(() {
        _dashboard = dashboard;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final user = ref.watch(currentAuthUserProvider);

    return Scaffold(
      backgroundColor: c.bgBase,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            cacheExtent: 2400,
            slivers: [
              SliverToBoxAdapter(
                child: StaggeredEnter(
                  child: _Header(
                    name: user?.displayName ?? '老师',
                    subtitle: user?.roleSubtitle ?? '教师',
                    role: user?.role,
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 8)),
              SliverToBoxAdapter(
                child: _loading
                    ? const _SkeletonBody()
                    : _error != null
                        ? ErrorStateView(
                            message: '工作台加载失败',
                            onRetry: _load,
                          ).padVertical(48)
                        : _Body(dashboard: _dashboard!),
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
    required this.name,
    required this.subtitle,
    this.role,
  });

  final String name;
  final String subtitle;
  final UserRole? role;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final now = DateTime.now();
    final greeting = _greeting(now.hour);
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.md,
        AppSpacing.edge,
        AppSpacing.sm,
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$greeting,$name',
                  style: AppTypography.headline.copyWith(color: c.textPrimary),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: AppTypography.caption.copyWith(color: c.textSecondary),
                ),
              ],
            ),
          ),
          if (role != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: c.primarySubtle,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                role!.displayName,
                style: AppTypography.label.copyWith(color: c.primary),
              ),
            ),
        ],
      ),
    );
  }

  static String _greeting(int hour) {
    if (hour < 6) return '深夜辛苦了';
    if (hour < 11) return '早上好';
    if (hour < 14) return '中午好';
    if (hour < 18) return '下午好';
    return '晚上好';
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.dashboard});

  final TeacherDashboard dashboard;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ===== 下一步行动(主要视觉重点) =====
          if (dashboard.nextActions.isNotEmpty)
            StaggeredEnter(
              delay: const Duration(milliseconds: 60),
              child: _NextActionsSection(actions: dashboard.nextActions),
            ),
          const SizedBox(height: AppSpacing.lg),

          // ===== 待办统计(三色状态条) =====
          StaggeredEnter(
            delay: const Duration(milliseconds: 120),
            child: _PendingStatsCard(dashboard: dashboard),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ===== 概览统计 =====
          StaggeredEnter(
            delay: const Duration(milliseconds: 180),
            child: _OverviewGrid(dashboard: dashboard),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ===== 最近活动 =====
          if (dashboard.recentActivities.isNotEmpty)
            StaggeredEnter(
              delay: const Duration(milliseconds: 240),
              child: _RecentActivitiesSection(
                activities: dashboard.recentActivities,
              ),
            ),
          const SizedBox(height: AppSpacing.lg),

          // ===== 我的课程(快捷入口) =====
          if (dashboard.courses.isNotEmpty)
            StaggeredEnter(
              delay: const Duration(milliseconds: 300),
              child: _CoursesSection(courses: dashboard.courses),
            ),
        ],
      ),
    );
  }
}

class _NextActionsSection extends StatelessWidget {
  const _NextActionsSection({required this.actions});
  final List<TeacherNextAction> actions;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          title: '下一步行动',
          subtitle: '优先处理这里',
          icon: Icons.flag_rounded,
        ),
        const SizedBox(height: AppSpacing.sm + 2),
        Column(
          children: [
            for (int i = 0; i < actions.length; i++) ...[
              _NextActionTile(action: actions[i]),
              if (i < actions.length - 1) const SizedBox(height: AppSpacing.sm),
            ],
          ],
        ),
      ],
    );
  }
}

class _NextActionTile extends StatelessWidget {
  const _NextActionTile({required this.action});
  final TeacherNextAction action;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final style = _ActionStyle.of(action, c);
    return AppCard(
      onTap: action.targetPath == null
          ? null
          : () => context.go(action.targetPath!),
      borderColor: style.accent.withValues(alpha: 0.18),
      backgroundColor: style.bg,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: style.accent.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Icon(style.icon, size: 20, color: style.accent),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  action.label,
                  style: AppTypography.subtitle.copyWith(color: c.textPrimary),
                ),
                const SizedBox(height: 2),
                Text(
                  action.actionType.displayName,
                  style: AppTypography.caption.copyWith(color: c.textSecondary),
                ),
              ],
            ),
          ),
          if (action.count > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: style.accent.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '${action.count}',
                style: AppTypography.label.copyWith(
                  color: style.accent,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
            ),
          const SizedBox(width: 4),
          Icon(Icons.chevron_right_rounded, color: c.textTertiary, size: 22),
        ],
      ),
    );
  }
}

class _ActionStyle {
  const _ActionStyle({
    required this.accent,
    required this.bg,
    required this.icon,
  });

  final Color accent;
  final Color bg;
  final IconData icon;

  static _ActionStyle of(TeacherNextAction action, AppColorScheme c) {
    switch (action.priority) {
      case NextActionPriority.high:
        return _ActionStyle(
          accent: c.warning,
          bg: c.warningSubtle.withValues(alpha: 0.35),
          icon: _iconFor(action.actionType),
        );
      case NextActionPriority.normal:
        return _ActionStyle(
          accent: c.primary,
          bg: c.primarySubtle.withValues(alpha: 0.4),
          icon: _iconFor(action.actionType),
        );
      case NextActionPriority.low:
        return _ActionStyle(
          accent: c.textSecondary,
          bg: c.bgSunken,
          icon: _iconFor(action.actionType),
        );
    }
  }

  static IconData _iconFor(NextActionType type) {
    switch (type) {
      case NextActionType.gradeSubmission:
        return Icons.grading_rounded;
      case NextActionType.publishAnnouncement:
        return Icons.campaign_outlined;
      case NextActionType.publishAssignment:
        return Icons.assignment_outlined;
      case NextActionType.remindUnread:
        return Icons.notifications_active_outlined;
      case NextActionType.remindUnsubmitted:
        return Icons.schedule_outlined;
      case NextActionType.viewOverdue:
        return Icons.warning_amber_rounded;
      case NextActionType.viewStats:
        return Icons.insights_outlined;
      case NextActionType.other:
        return Icons.bolt_outlined;
    }
  }
}

class _PendingStatsCard extends StatelessWidget {
  const _PendingStatsCard({required this.dashboard});
  final TeacherDashboard dashboard;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.base),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.pending_actions_rounded, size: 18, color: c.primary),
              const SizedBox(width: 6),
              const Text('待处理', style: AppTypography.subtitle),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: _StatChip(
                  label: '待批阅',
                  value: dashboard.pendingSubmissions,
                  color: c.primary,
                  bg: c.primarySubtle,
                  onTap: () => context.go('/teacher/stats'),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: _StatChip(
                  label: '未读通知',
                  value: dashboard.unreadAnnouncementStudents,
                  color: c.warning,
                  bg: c.warningSubtle,
                  onTap: () => context.go('/teacher/courses'),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: _StatChip(
                  label: '逾期',
                  value: dashboard.overdueStudents,
                  color: c.danger,
                  bg: c.dangerSubtle,
                  onTap: () => context.go('/teacher/stats'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  const _StatChip({
    required this.label,
    required this.value,
    required this.color,
    required this.bg,
    this.onTap,
  });

  final String label;
  final int value;
  final Color color;
  final Color bg;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(AppRadius.sm),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$value',
                style: AppTypography.metric.copyWith(
                  color: color,
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: AppTypography.label.copyWith(
                  color: color,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _OverviewGrid extends StatelessWidget {
  const _OverviewGrid({required this.dashboard});
  final TeacherDashboard dashboard;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          title: '教学概览',
          icon: Icons.school_rounded,
        ),
        const SizedBox(height: AppSpacing.sm + 2),
        Row(
          children: [
            Expanded(
              child: _OverviewTile(
                icon: Icons.class_rounded,
                label: '课程',
                value: dashboard.courseCount,
                onTap: () => context.go('/teacher/courses'),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: _OverviewTile(
                icon: Icons.groups_2_rounded,
                label: '班级',
                value: dashboard.classCount,
                onTap: () => context.go('/teacher/courses'),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: _OverviewTile(
                icon: Icons.person_outline_rounded,
                label: '学生',
                value: dashboard.studentCount,
                onTap: () => context.go('/teacher/courses'),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: _OverviewTile(
                icon: Icons.assignment_outlined,
                label: '活跃任务',
                value: dashboard.activeAssignmentCount,
                onTap: () => context.go('/teacher/stats'),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _OverviewTile extends StatelessWidget {
  const _OverviewTile({
    required this.icon,
    required this.label,
    required this.value,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final int value;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      onTap: onTap,
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
      child: Column(
        children: [
          Icon(icon, size: 18, color: c.primary),
          const SizedBox(height: 6),
          Text(
            '$value',
            style: AppTypography.subtitle.copyWith(
              color: c.textPrimary,
              fontSize: 17,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: AppTypography.label.copyWith(
              color: c.textTertiary,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}

class _RecentActivitiesSection extends StatelessWidget {
  const _RecentActivitiesSection({required this.activities});
  final List<TeacherActivity> activities;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          title: '最近活动',
          icon: Icons.history_rounded,
        ),
        const SizedBox(height: AppSpacing.sm + 2),
        AppCard(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            children: [
              for (int i = 0; i < activities.length; i++) ...[
                _ActivityTile(activity: activities[i]),
                if (i < activities.length - 1)
                  Divider(
                    height: 1,
                    color: c.border,
                    indent: 56,
                    endIndent: 16,
                  ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _ActivityTile extends StatelessWidget {
  const _ActivityTile({required this.activity});
  final TeacherActivity activity;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final style = _ActionStyle.of(
      TeacherNextAction(
        id: activity.id,
        label: activity.label,
        actionType: activity.actionType ?? NextActionType.other,
        count: 0,
        priority: NextActionPriority.normal,
      ),
      c,
    );
    return InkWell(
      onTap: activity.targetPath == null
          ? null
          : () => context.go(activity.targetPath!),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm + 2,
        ),
        child: Row(
          children: [
            Container(
              width: 30,
              height: 30,
              decoration: BoxDecoration(
                color: style.accent.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(AppRadius.xs),
              ),
              child: Icon(style.icon, size: 16, color: style.accent),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    activity.label,
                    style: AppTypography.body.copyWith(color: c.textPrimary),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _relativeTime(activity.timestamp),
                    style: AppTypography.caption.copyWith(
                      color: c.textTertiary,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _relativeTime(DateTime t) {
    final diff = DateTime.now().difference(t);
    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
    if (diff.inHours < 24) return '${diff.inHours}小时前';
    if (diff.inDays < 7) return '${diff.inDays}天前';
    return '${t.month}/${t.day}';
  }
}

class _CoursesSection extends StatelessWidget {
  const _CoursesSection({required this.courses});
  final List<Course> courses;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: '我的课程',
          actionLabel: '全部',
          onAction: () => context.go('/teacher/courses'),
          icon: Icons.book_rounded,
        ),
        const SizedBox(height: AppSpacing.sm + 2),
        Column(
          children: [
            for (int i = 0; i < courses.length && i < 3; i++) ...[
              _CourseTile(course: courses[i]),
              if (i < courses.length - 1 && i < 2)
                const SizedBox(height: AppSpacing.sm),
            ],
          ],
        ),
      ],
    );
  }
}

class _CourseTile extends StatelessWidget {
  const _CourseTile({required this.course});
  final Course course;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final courseColor = Color(course.color);
    return AppCard(
      onTap: () => context.go('/teacher/courses/${course.id}'),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: courseColor.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Icon(Icons.book_rounded, size: 20, color: courseColor),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  course.name,
                  style: AppTypography.subtitle.copyWith(color: c.textPrimary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  '${course.code} · ${course.classCount}班 · ${course.studentCount}人',
                  style: AppTypography.caption.copyWith(
                    color: c.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Icon(Icons.chevron_right_rounded, color: c.textTertiary, size: 22),
        ],
      ),
    );
  }
}

class _SkeletonBody extends StatelessWidget {
  const _SkeletonBody();

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SkeletonCard(height: 120),
        SizedBox(height: AppSpacing.lg),
        SkeletonCard(height: 100),
        SizedBox(height: AppSpacing.lg),
        SkeletonCard(height: 80),
        SizedBox(height: AppSpacing.lg),
        SkeletonCard(height: 180),
      ],
    );
  }
}

extension on Widget {
  Widget padVertical(double v) => Padding(
        padding: EdgeInsets.symmetric(vertical: v),
        child: this,
      );
}
