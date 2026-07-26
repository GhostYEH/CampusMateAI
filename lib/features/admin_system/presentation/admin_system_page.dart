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
import '../../../data/models/dashboard.dart';

/// 管理员系统状态页 — 只读展示系统健康度。
///
/// 仅做最小可用入口(AGENTS.md §2 "管理员最小能力"):
/// - 用户/课程/班级总数
/// - 活跃任务 / 今日提交
/// - 后端延迟 / 版本 / 健康度
/// - 警告列表
class AdminSystemPage extends ConsumerStatefulWidget {
  const AdminSystemPage({super.key});

  @override
  ConsumerState<AdminSystemPage> createState() => _AdminSystemPageState();
}

class _AdminSystemPageState extends ConsumerState<AdminSystemPage> {
  AdminSystemStatus? _status;
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
      final status = await svc.getAdminSystemStatus();
      if (!mounted) return;
      setState(() {
        _status = status;
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

  Future<void> _logout() async {
    await ref.read(authNotifierProvider.notifier).logout();
    if (!mounted) return;
    if (context.mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final user = ref.watch(currentAuthUserProvider);

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('系统状态'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        actions: [
          IconButton(
            onPressed: _logout,
            icon: const Icon(Icons.logout_rounded, size: 22),
            tooltip: '退出登录',
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: _loading
              ? const SkeletonPage(itemCount: 4)
              : _error != null
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        ErrorStateView(
                          message: '系统状态加载失败',
                          onRetry: _load,
                        ),
                      ],
                    )
                  : SingleChildScrollView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.edge,
                        vertical: AppSpacing.sm,
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          StaggeredEnter(
                            child: _HealthCard(status: _status!),
                          ),
                          const SizedBox(height: AppSpacing.md),
                          StaggeredEnter(
                            delay: const Duration(milliseconds: 60),
                            child: _OverviewGrid(status: _status!),
                          ),
                          if (_status!.warnings.isNotEmpty) ...[
                            const SizedBox(height: AppSpacing.md),
                            StaggeredEnter(
                              delay: const Duration(milliseconds: 120),
                              child: _WarningsCard(
                                warnings: _status!.warnings,
                              ),
                            ),
                          ],
                          const SizedBox(height: AppSpacing.md),
                          StaggeredEnter(
                            delay: const Duration(milliseconds: 180),
                            child: _MetaCard(status: _status!),
                          ),
                          if (user != null) ...[
                            const SizedBox(height: AppSpacing.md),
                            StaggeredEnter(
                              delay: const Duration(milliseconds: 240),
                              child: _AccountCard(
                                name: user.displayName,
                                role: user.role,
                              ),
                            ),
                          ],
                          const SizedBox(height: AppSpacing.lg),
                        ],
                      ),
                    ),
        ),
      ),
    );
  }
}

class _HealthCard extends StatelessWidget {
  const _HealthCard({required this.status});
  final AdminSystemStatus status;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final isHealthy = status.isHealthy;
    final color = isHealthy ? c.success : c.warning;
    final icon = isHealthy ? Icons.check_circle_rounded : Icons.warning_rounded;
    final label = isHealthy ? '系统运行正常' : '系统存在异常';

    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: AppTypography.subtitle.copyWith(color: c.textPrimary),
                ),
                const SizedBox(height: 2),
                Text(
                  status.lastCheckedAt != null
                      ? '最近检查于 ${_formatTime(status.lastCheckedAt!)}'
                      : '尚未检查',
                  style: AppTypography.caption.copyWith(
                    color: c.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: () => _showRefresh(context),
            icon: const Icon(Icons.refresh_rounded, size: 20),
            tooltip: '刷新',
            color: c.textSecondary,
          ),
        ],
      ),
    );
  }

  void _showRefresh(BuildContext context) {
    // 由父级 RefreshIndicator 处理;这里仅是触发提示
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      const SnackBar(
        content: Text('下拉刷新'),
        duration: Duration(seconds: 1),
      ),
    );
  }

  String _formatTime(DateTime dt) {
    return '${dt.hour.toString().padLeft(2, '0')}:'
        '${dt.minute.toString().padLeft(2, '0')}:'
        '${dt.second.toString().padLeft(2, '0')}';
  }
}

class _OverviewGrid extends StatelessWidget {
  const _OverviewGrid({required this.status});
  final AdminSystemStatus status;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('系统概览', style: AppTypography.subtitle),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: _Metric(
                  icon: Icons.group_outlined,
                  value: status.totalUsers,
                  label: '总用户',
                ),
              ),
              Expanded(
                child: _Metric(
                  icon: Icons.class_outlined,
                  value: status.totalCourses,
                  label: '课程',
                ),
              ),
              Expanded(
                child: _Metric(
                  icon: Icons.groups_2_outlined,
                  value: status.totalClasses,
                  label: '班级',
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: _Metric(
                  icon: Icons.assignment_outlined,
                  value: status.activeAssignments,
                  label: '活跃任务',
                ),
              ),
              Expanded(
                child: _Metric(
                  icon: Icons.upload_outlined,
                  value: status.todaySubmissions,
                  label: '今日提交',
                ),
              ),
              const Expanded(child: SizedBox()),
            ],
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({
    required this.icon,
    required this.value,
    required this.label,
  });
  final IconData icon;
  final int value;
  final String label;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: c.primary),
        const SizedBox(width: 6),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '$value',
                style: AppTypography.subtitle.copyWith(
                  color: c.textPrimary,
                ),
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

class _WarningsCard extends StatelessWidget {
  const _WarningsCard({required this.warnings});
  final List<String> warnings;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      backgroundColor: c.warningSubtle.withValues(alpha: 0.4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.warning_amber_rounded, color: c.warning, size: 18),
              const SizedBox(width: 6),
              Text(
                '系统警告',
                style: AppTypography.subtitle.copyWith(color: c.warning),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          for (int i = 0; i < warnings.length; i++) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 6, right: 6),
                    child: Container(
                      width: 4,
                      height: 4,
                      decoration: BoxDecoration(
                        color: c.warning,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      warnings[i],
                      style: AppTypography.caption.copyWith(
                        color: c.textPrimary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            if (i < warnings.length - 1) const SizedBox(height: 2),
          ],
        ],
      ),
    );
  }
}

class _MetaCard extends StatelessWidget {
  const _MetaCard({required this.status});
  final AdminSystemStatus status;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('系统信息', style: AppTypography.subtitle),
          const SizedBox(height: AppSpacing.sm),
          _MetaRow(
            label: '后端版本',
            value: status.backendVersion ?? '未知',
          ),
          _MetaRow(
            label: 'API 延迟',
            value: status.apiLatencyMs != null
                ? '${status.apiLatencyMs} ms'
                : '未知',
          ),
        ],
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  const _MetaRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: AppTypography.caption.copyWith(color: c.textTertiary),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTypography.body.copyWith(color: c.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

class _AccountCard extends StatelessWidget {
  const _AccountCard({required this.name, required this.role});
  final String name;
  final dynamic role; // UserRole

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: c.primary,
            child: Text(
              name.isNotEmpty ? name.characters.first : 'A',
              style: TextStyle(color: c.onPrimary, fontSize: 14),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: AppTypography.body),
                Text(
                  '管理员账号',
                  style: AppTypography.caption.copyWith(
                    color: c.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
