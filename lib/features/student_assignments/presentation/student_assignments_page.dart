import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/assignment.dart';
import '../../../data/models/pagination.dart';

/// 学生任务中心 — 状态筛选 + 课程筛选 + 搜索 + 排序。
///
/// 信息优先级(AGENTS.md §5.3):
/// 逾期 → 24h 内截止 → 普通任务
class StudentAssignmentsPage extends ConsumerStatefulWidget {
  const StudentAssignmentsPage({super.key});

  @override
  ConsumerState<StudentAssignmentsPage> createState() =>
      _StudentAssignmentsPageState();
}

class _StudentAssignmentsPageState
    extends ConsumerState<StudentAssignmentsPage> {
  String _search = '';
  String _status = 'all';
  String _sortBy = 'deadline';
  bool _sortDesc = false;

  static const _statusOptions = [
    ('all', '全部'),
    ('pending', '待提交'),
    ('submitted', '已提交'),
    ('overdue', '已逾期'),
    ('graded', '已完成'),
  ];

  static const _sortOptions = [
    ('deadline', '截止时间'),
    ('created_at', '发布时间'),
    ('title', '标题'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final svc = ref.watch(assignmentServiceProvider);

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('任务中心'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        actions: [
          IconButton(
            tooltip: '切换排序',
            onPressed: _showSortSheet,
            icon: const Icon(Icons.sort_rounded, size: 22),
          ),
        ],
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
            child: DebouncedSearchField(
              hint: '搜索任务标题',
              onChanged: (v) => setState(() => _search = v),
            ),
          ),
          SizedBox(
            height: 36,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.edge,
              ),
              itemCount: _statusOptions.length,
              separatorBuilder: (context, i) => const SizedBox(width: 6),
              itemBuilder: (context, i) {
                final (value, label) = _statusOptions[i];
                return _FilterChip(
                  label: label,
                  selected: _status == value,
                  onTap: () => setState(() => _status = value),
                );
              },
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Expanded(
            child: PagedListView<Assignment>(
              fetchPage: (page, pageSize) => svc.listStudentAssignments(
                status: _status == 'all' ? null : _status,
                search: _search.isEmpty ? null : _search,
                sortBy: _sortBy,
                sortDesc: _sortDesc,
                page: PageRequest(page: page, pageSize: pageSize),
              ),
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.edge,
                0,
                AppSpacing.edge,
                AppSpacing.xl,
              ),
              separator: const SizedBox(height: AppSpacing.sm + 2),
              emptyIcon: Icons.assignment_outlined,
              emptyTitle: '没有匹配的任务',
              emptyMessage: _status == 'all' ? null : '试试切换筛选条件',
              itemBuilder: (context, assignment, index) => StaggeredEnter(
                delay: Duration(milliseconds: (index * 35).clamp(0, 200)),
                child: _AssignmentCard(assignment: assignment),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showSortSheet() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.edge),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('排序方式', style: AppTypography.subtitle),
                const SizedBox(height: AppSpacing.md),
                RadioGroup<String>(
                  groupValue: _sortBy,
                  onChanged: (v) {
                    if (v == null) return;
                    setState(() => _sortBy = v);
                    Navigator.pop(sheetContext);
                  },
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final (value, label) in _sortOptions)
                        RadioListTile<String>(
                          value: value,
                          title: Text(label),
                        ),
                    ],
                  ),
                ),
                const Divider(),
                SwitchListTile(
                  value: _sortDesc,
                  title: const Text('降序'),
                  onChanged: (v) => setState(() => _sortDesc = v),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: selected ? c.primary : c.bgSurface,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: selected ? c.primary : c.border,
              width: 1,
            ),
          ),
          child: Center(
            child: Text(
              label,
              style: AppTypography.label.copyWith(
                color: selected ? c.onPrimary : c.textSecondary,
                fontSize: 12,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _AssignmentCard extends StatelessWidget {
  const _AssignmentCard({required this.assignment});
  final Assignment assignment;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final isOverdue = assignment.isOverdue;
    final isDueSoon = assignment.isDueSoon && !isOverdue;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => context.go('/tasks/assignment/${assignment.id}'),
        borderRadius: BorderRadius.circular(AppRadius.md),
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: c.bgSurface,
            borderRadius: BorderRadius.circular(AppRadius.md),
            border: Border.all(
              color: isOverdue
                  ? c.danger.withValues(alpha: 0.4)
                  : isDueSoon
                      ? c.accent.withValues(alpha: 0.3)
                      : c.border,
              width: isOverdue || isDueSoon ? 1.2 : 1,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (isOverdue)
                    Padding(
                      padding: const EdgeInsets.only(top: 4, right: 8),
                      child: Icon(
                        Icons.error_outline_rounded,
                        size: 16,
                        color: c.danger,
                      ),
                    )
                  else if (isDueSoon)
                    Padding(
                      padding: const EdgeInsets.only(top: 4, right: 8),
                      child: Icon(
                        Icons.access_time_rounded,
                        size: 16,
                        color: c.accent,
                      ),
                    ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          assignment.title,
                          style: AppTypography.bodyStrong.copyWith(
                            color: c.textPrimary,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        if (assignment.courseName != null)
                          Text(
                            '${assignment.courseName}${assignment.className != null ? ' · ${assignment.className}' : ''}',
                            style: AppTypography.caption.copyWith(
                              color: c.textSecondary,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(
                    Icons.calendar_today_rounded,
                    size: 14,
                    color: _deadlineColor(assignment.deadline, c),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    _formatDeadline(assignment.deadline, assignment.remaining),
                    style: AppTypography.caption.copyWith(
                      color: _deadlineColor(assignment.deadline, c),
                    ),
                  ),
                  const Spacer(),
                  Text(
                    assignment.submissionType.displayName,
                    style: AppTypography.label.copyWith(
                      color: c.textTertiary,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDeadline(DateTime deadline, Duration remaining) {
    if (remaining.isNegative) {
      final days = (-remaining.inDays);
      if (days > 0) return '已逾期 $days 天';
      final hours = -remaining.inHours;
      return '已逾期 $hours 小时';
    }
    if (remaining.inDays >= 1) {
      return '截止 ${deadline.month}/${deadline.day} · 剩 ${remaining.inDays}天';
    }
    return '截止 ${deadline.month}/${deadline.day} · 剩 ${remaining.inHours}小时';
  }

  Color _deadlineColor(DateTime dt, AppColorScheme c) {
    final now = DateTime.now();
    if (dt.isBefore(now)) return c.danger;
    if (dt.difference(now).inHours < 24) return c.accent;
    return c.textSecondary;
  }
}
