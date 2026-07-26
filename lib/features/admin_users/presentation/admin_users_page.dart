import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/role_chip.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/course.dart';
import '../../../data/models/pagination.dart';
import '../../../data/models/user.dart';

/// 管理员用户管理页 — 列出所有用户,支持角色筛选 + 启用/禁用。
///
/// 仅做最小可用入口(AGENTS.md §2 "管理员最小能力")。
/// 不暴露用户私人数据(对话/待办/学习记录)。
class AdminUsersPage extends ConsumerStatefulWidget {
  const AdminUsersPage({super.key});

  @override
  ConsumerState<AdminUsersPage> createState() => _AdminUsersPageState();
}

class _AdminUsersPageState extends ConsumerState<AdminUsersPage> {
  String _search = '';
  UserRole? _roleFilter;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final svc = ref.watch(userManagementServiceProvider);

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('用户管理'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.edge,
              AppSpacing.sm,
              AppSpacing.edge,
              AppSpacing.sm,
            ),
            child: Column(
              children: [
                DebouncedSearchField(
                  hint: '搜索姓名 / 用户名 / 学号',
                  onChanged: (v) => setState(() => _search = v),
                ),
                const SizedBox(height: AppSpacing.sm),
                _RoleFilterRow(
                  selected: _roleFilter,
                  onSelect: (r) => setState(
                    () => _roleFilter = _roleFilter == r ? null : r,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: PagedListView<UserSummary>(
              fetchPage: (page, pageSize) => svc.listUsers(
                role: _roleFilter,
                search: _search.isEmpty ? null : _search,
                activeOnly: false,
                page: PageRequest(page: page, pageSize: pageSize),
              ),
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.edge,
                AppSpacing.sm,
                AppSpacing.edge,
                96,
              ),
              separator: const SizedBox(height: AppSpacing.sm),
              emptyIcon: Icons.person_off_outlined,
              emptyTitle: '没有匹配的用户',
              itemBuilder: (context, user, index) => StaggeredEnter(
                delay: Duration(milliseconds: (index * 30).clamp(0, 180)),
                child: _UserTile(user: user),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RoleFilterRow extends StatelessWidget {
  const _RoleFilterRow({required this.selected, required this.onSelect});
  final UserRole? selected;
  final void Function(UserRole) onSelect;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return SizedBox(
      height: 32,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: UserRole.values.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final role = UserRole.values[index];
          final isSelected = selected == role;
          return GestureDetector(
            onTap: () => onSelect(role),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color:
                    isSelected ? c.primary.withValues(alpha: 0.14) : c.bgSunken,
                borderRadius: BorderRadius.circular(AppRadius.xs),
                border: Border.all(
                  color: isSelected ? c.primary : c.border,
                  width: isSelected ? 1.2 : 0.8,
                ),
              ),
              child: Text(
                role.displayName,
                style: AppTypography.label.copyWith(
                  color: isSelected ? c.primary : c.textSecondary,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _UserTile extends ConsumerStatefulWidget {
  const _UserTile({required this.user});
  final UserSummary user;

  @override
  ConsumerState<_UserTile> createState() => _UserTileState();
}

class _UserTileState extends ConsumerState<_UserTile> {
  bool _toggling = false;

  Future<void> _toggleActive() async {
    final user = widget.user;
    setState(() => _toggling = true);
    final scaffold = ScaffoldMessenger.maybeOf(context);
    try {
      final svc = ref.read(userManagementServiceProvider);
      final updated = await svc.setUserActive(user.id, !user.isActive);
      if (!mounted) return;
      setState(() => _toggling = false);
      // 由于 PagedListView 持有旧 items,这里通过 snackbar 反馈,
      // 真实列表刷新由用户下拉触发(避免破坏分页状态)
      scaffold?.showSnackBar(
        SnackBar(
          content: Text(
            updated.isActive ? '已启用 ${updated.name}' : '已禁用 ${updated.name}',
          ),
          duration: const Duration(seconds: 2),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() => _toggling = false);
      scaffold?.showSnackBar(
        const SnackBar(
          content: Text('操作失败,请重试'),
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final user = widget.user;
    final initial = user.name.isNotEmpty ? user.name.characters.first : '?';

    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor:
                user.isActive ? c.primary.withValues(alpha: 0.14) : c.bgSunken,
            child: Text(
              initial,
              style: AppTypography.body.copyWith(
                color: user.isActive ? c.primary : c.textSecondary,
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        user.name,
                        style: AppTypography.body.copyWith(
                          color: c.textPrimary,
                          decoration:
                              user.isActive ? null : TextDecoration.lineThrough,
                          decorationColor: c.textTertiary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    RoleChip(role: user.role),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  _buildSubtitle(user),
                  style: AppTypography.caption.copyWith(
                    color: c.textSecondary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          _ToggleSwitch(
            value: user.isActive,
            onChanged: _toggling ? null : _toggleActive,
          ),
        ],
      ),
    );
  }

  String _buildSubtitle(UserSummary user) {
    final parts = <String>[];
    if (user.username != null && user.username!.isNotEmpty) {
      parts.add('@${user.username}');
    }
    if (user.studentId != null) {
      parts.add('学号 ${user.studentId}');
    } else if (user.teacherId != null) {
      parts.add('工号 ${user.teacherId}');
    }
    if (user.college != null) {
      parts.add(user.college!);
    }
    return parts.isEmpty ? user.id : parts.join(' · ');
  }
}

class _ToggleSwitch extends StatelessWidget {
  const _ToggleSwitch({required this.value, required this.onChanged});
  final bool value;
  final VoidCallback? onChanged;

  @override
  Widget build(BuildContext context) {
    return Switch.adaptive(
      value: value,
      onChanged: onChanged == null ? null : (_) => onChanged!(),
    );
  }
}
