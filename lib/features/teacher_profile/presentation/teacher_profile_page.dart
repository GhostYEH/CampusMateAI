import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../app/providers/auth_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/role_chip.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/dashboard.dart';
import '../../../data/models/user.dart';

/// 教师个人页 — 教师信息 + 课程统计概览 + 退出登录。
///
/// 不复用学生 ProfilePage — 教师没有学习陪伴 / 表情识别等学生专属功能。
class TeacherProfilePage extends ConsumerStatefulWidget {
  const TeacherProfilePage({super.key});

  @override
  ConsumerState<TeacherProfilePage> createState() => _TeacherProfilePageState();
}

class _TeacherProfilePageState extends ConsumerState<TeacherProfilePage> {
  TeacherDashboard? _dashboard;
  bool _loadingDashboard = true;
  bool _loggingOut = false;

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  Future<void> _loadDashboard() async {
    try {
      final svc = ref.read(dashboardServiceProvider);
      final dashboard = await svc.getTeacherDashboard();
      if (!mounted) return;
      setState(() {
        _dashboard = dashboard;
        _loadingDashboard = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingDashboard = false);
    }
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('退出登录'),
        content: const Text('确认退出当前账号?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('退出'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _loggingOut = true);
    await ref.read(authNotifierProvider.notifier).logout();
    if (!mounted) return;
    setState(() => _loggingOut = false);
    if (context.mounted) {
      context.go('/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final user = ref.watch(currentAuthUserProvider);

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('我的'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadDashboard,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.edge,
              vertical: AppSpacing.sm,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                StaggeredEnter(
                  child: _TeacherHeader(user: user),
                ),
                const SizedBox(height: AppSpacing.md),
                if (!_loadingDashboard && _dashboard != null) ...[
                  StaggeredEnter(
                    delay: const Duration(milliseconds: 60),
                    child: _TeachingSummaryCard(dashboard: _dashboard!),
                  ),
                  const SizedBox(height: AppSpacing.md),
                ],
                StaggeredEnter(
                  delay: const Duration(milliseconds: 120),
                  child: _MenuGroup(
                    title: '教学',
                    children: [
                      _MenuTile(
                        icon: Icons.class_outlined,
                        label: '我的课程',
                        subtitle: '查看、编辑、创建班级',
                        onTap: () => context.go('/teacher/courses'),
                      ),
                      _MenuTile(
                        icon: Icons.insights_outlined,
                        label: '任务统计',
                        subtitle: '查看提交与评分情况',
                        onTap: () => context.go('/teacher/stats'),
                      ),
                      _MenuTile(
                        icon: Icons.send_outlined,
                        label: '发布中心',
                        subtitle: '发布通知与任务',
                        onTap: () => context.go('/teacher/publish'),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                StaggeredEnter(
                  delay: const Duration(milliseconds: 180),
                  child: _MenuGroup(
                    title: '账号',
                    children: [
                      _MenuTile(
                        icon: Icons.logout_rounded,
                        label: _loggingOut ? '退出中...' : '退出登录',
                        subtitle: '退出后需重新登录',
                        onTap: _loggingOut ? null : _logout,
                        iconColor: c.danger,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.lg),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TeacherHeader extends StatelessWidget {
  const _TeacherHeader({required this.user});
  final AppUser? user;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final name = user?.displayName ?? '老师';
    final initial = name.isNotEmpty ? name.characters.first : 'T';

    return AppCard(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: c.primary,
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                initial,
                style: TextStyle(
                  color: c.onPrimary,
                  fontSize: 26,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        name,
                        style: AppTypography.headline,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (user?.role != null) ...[
                      const SizedBox(width: 8),
                      RoleChip(role: user!.role),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  user?.roleSubtitle ?? '教师',
                  style: AppTypography.caption,
                ),
                const SizedBox(height: 2),
                if (user?.teacherId != null)
                  Text(
                    '工号 ${user!.teacherId}',
                    style: AppTypography.overline,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TeachingSummaryCard extends StatelessWidget {
  const _TeachingSummaryCard({required this.dashboard});
  final TeacherDashboard dashboard;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('教学概览', style: AppTypography.subtitle),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: _StatBlock(
                  icon: Icons.class_rounded,
                  value: dashboard.courseCount,
                  label: '课程',
                  color: c.primary,
                ),
              ),
              Expanded(
                child: _StatBlock(
                  icon: Icons.groups_2_rounded,
                  value: dashboard.classCount,
                  label: '班级',
                  color: c.accent,
                ),
              ),
              Expanded(
                child: _StatBlock(
                  icon: Icons.person_outline_rounded,
                  value: dashboard.studentCount,
                  label: '学生',
                  color: c.success,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: _StatBlock(
                  icon: Icons.assignment_outlined,
                  value: dashboard.activeAssignmentCount,
                  label: '活跃任务',
                  color: c.primary,
                ),
              ),
              Expanded(
                child: _StatBlock(
                  icon: Icons.mark_email_unread_outlined,
                  value: dashboard.pendingSubmissions,
                  label: '待批阅',
                  color: c.warning,
                ),
              ),
              Expanded(
                child: _StatBlock(
                  icon: Icons.error_outline_rounded,
                  value: dashboard.overdueStudents,
                  label: '逾期',
                  color: c.danger,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatBlock extends StatelessWidget {
  const _StatBlock({
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
  });
  final IconData icon;
  final int value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: color),
        const SizedBox(width: 6),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '$value',
                style: AppTypography.subtitle.copyWith(color: c.textPrimary),
              ),
              Text(
                label,
                style: AppTypography.caption.copyWith(
                  color: c.textSecondary,
                  fontSize: 10,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _MenuGroup extends StatelessWidget {
  const _MenuGroup({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(title, style: AppTypography.label),
        ),
        AppCard(
          padding: EdgeInsets.zero,
          child: Column(
            children: [
              for (int i = 0; i < children.length; i++) ...[
                children[i],
                if (i != children.length - 1)
                  const Divider(height: 1, indent: 56),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _MenuTile extends StatelessWidget {
  const _MenuTile({
    required this.icon,
    required this.label,
    required this.onTap,
    this.subtitle,
    this.iconColor = AppColors.textSecondary,
  });
  final IconData icon;
  final String label;
  final String? subtitle;
  final VoidCallback? onTap;
  final Color iconColor;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: iconColor),
      title: Text(label, style: AppTypography.body),
      subtitle: subtitle != null
          ? Text(
              subtitle!,
              style: AppTypography.caption,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            )
          : null,
      trailing: Icon(
        Icons.chevron_right_rounded,
        color: context.appColors.textTertiary,
        size: 20,
      ),
      visualDensity: VisualDensity.compact,
    );
  }
}
