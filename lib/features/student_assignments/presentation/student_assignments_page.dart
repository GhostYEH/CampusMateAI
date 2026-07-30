import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/assignment.dart';
import '../../../data/models/pagination.dart';

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
    final wide = MediaQuery.sizeOf(context).width >= 1100;

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        toolbarHeight: wide ? 72 : 58,
        titleSpacing: wide ? 28 : 16,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('任务', style: AppTypography.headline),
            if (wide)
              Text(
                '按截止时间整理本学期作业',
                style: AppTypography.caption.copyWith(color: c.textTertiary),
              ),
          ],
        ),
        backgroundColor: c.bgBase,
        actions: [
          Padding(
            padding: EdgeInsets.only(right: wide ? 24 : 8),
            child: IconButton(
              tooltip: '切换排序',
              onPressed: _showSortSheet,
              icon: const PhosphorIcon(
                PhosphorIconsRegular.slidersHorizontal,
                size: 21,
              ),
            ),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1180),
          child: Column(
            children: [
              Padding(
                padding: EdgeInsets.fromLTRB(
                  wide ? 24 : 16,
                  4,
                  wide ? 24 : 16,
                  12,
                ),
                child: DebouncedSearchField(
                  hint: '搜索任务标题',
                  onChanged: (v) => setState(() => _search = v),
                ),
              ),
              _StatusTabs(
                options: _statusOptions,
                value: _status,
                onChanged: (value) => setState(() => _status = value),
              ),
              Expanded(
                child: PagedListView<Assignment>(
                  key: ValueKey(
                    'student_assignments_$_status-$_search-$_sortBy-$_sortDesc',
                  ),
                  fetchPage: (page, pageSize) => svc.listStudentAssignments(
                    status: _status == 'all' ? null : _status,
                    search: _search.isEmpty ? null : _search,
                    sortBy: _sortBy,
                    sortDesc: _sortDesc,
                    page: PageRequest(page: page, pageSize: pageSize),
                  ),
                  padding: EdgeInsets.fromLTRB(
                    wide ? 24 : 16,
                    14,
                    wide ? 24 : 16,
                    32,
                  ),
                  separator: const SizedBox(height: 1),
                  emptyIcon: PhosphorIconsRegular.tray,
                  emptyTitle: '没有匹配的任务',
                  emptyMessage: _status == 'all' ? null : '换个筛选条件，或搜索其他关键词',
                  itemBuilder: (context, assignment, index) => StaggeredEnter(
                    delay: Duration(milliseconds: (index * 28).clamp(0, 160)),
                    child: _AssignmentRow(
                      assignment: assignment,
                      first: index == 0,
                      wide: wide,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showSortSheet() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('排序方式', style: AppTypography.subtitle),
              const SizedBox(height: 12),
              RadioGroup<String>(
                groupValue: _sortBy,
                onChanged: (value) {
                  if (value == null) return;
                  setState(() => _sortBy = value);
                  Navigator.pop(sheetContext);
                },
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (final (value, label) in _sortOptions)
                      RadioListTile<String>(
                        value: value,
                        title: Text(label),
                        contentPadding: EdgeInsets.zero,
                      ),
                  ],
                ),
              ),
              const Divider(),
              SwitchListTile(
                value: _sortDesc,
                contentPadding: EdgeInsets.zero,
                title: const Text('降序排列'),
                onChanged: (value) => setState(() => _sortDesc = value),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusTabs extends StatelessWidget {
  const _StatusTabs({
    required this.options,
    required this.value,
    required this.onChanged,
  });

  final List<(String, String)> options;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final wide = MediaQuery.sizeOf(context).width >= 1100;
    return Container(
      height: 45,
      margin: EdgeInsets.symmetric(horizontal: wide ? 24 : 16),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: c.border)),
      ),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: options.length,
        separatorBuilder: (_, __) => SizedBox(width: wide ? 26 : 18),
        itemBuilder: (context, index) {
          final (optionValue, label) = options[index];
          final selected = optionValue == value;
          return Semantics(
            button: true,
            selected: selected,
            child: InkWell(
              onTap: () => onChanged(optionValue),
              child: Stack(
                alignment: Alignment.bottomCenter,
                children: [
                  Center(
                    child: AnimatedDefaultTextStyle(
                      duration: AppMotion.fast,
                      style: AppTypography.body.copyWith(
                        color: selected ? c.textPrimary : c.textTertiary,
                        fontWeight:
                            selected ? FontWeight.w600 : FontWeight.w400,
                      ),
                      child: Text(label),
                    ),
                  ),
                  AnimatedContainer(
                    duration: AppMotion.fast,
                    width: selected ? 22 : 0,
                    height: 2,
                    color: selected ? c.primary : Colors.transparent,
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _AssignmentRow extends StatefulWidget {
  const _AssignmentRow({
    required this.assignment,
    required this.first,
    required this.wide,
  });

  final Assignment assignment;
  final bool first;
  final bool wide;

  @override
  State<_AssignmentRow> createState() => _AssignmentRowState();
}

class _AssignmentRowState extends State<_AssignmentRow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final assignment = widget.assignment;
    final isOverdue = assignment.isOverdue;
    final isDueSoon = assignment.isDueSoon && !isOverdue;
    final accent = isOverdue
        ? c.danger
        : isDueSoon
            ? c.accent
            : c.primary;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => context.go('/tasks/assignment/${assignment.id}'),
          child: AnimatedContainer(
            duration: AppMotion.fast,
            padding: EdgeInsets.symmetric(
              horizontal: widget.wide ? 18 : 12,
              vertical: widget.wide ? 17 : 15,
            ),
            decoration: BoxDecoration(
              color: _hovered ? c.primary.withValues(alpha: .045) : c.bgSurface,
              border: Border(
                top: BorderSide(
                  color: widget.first ? c.border : Colors.transparent,
                ),
                bottom: BorderSide(color: c.border),
                left: BorderSide(
                  color: isOverdue || isDueSoon ? accent : Colors.transparent,
                  width: 2,
                ),
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 34,
                  height: 34,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: .1),
                    shape: BoxShape.circle,
                  ),
                  child: PhosphorIcon(
                    isOverdue
                        ? PhosphorIconsRegular.warningCircle
                        : isDueSoon
                            ? PhosphorIconsRegular.clockCountdown
                            : PhosphorIconsRegular.fileText,
                    size: 18,
                    color: accent,
                  ),
                ),
                const SizedBox(width: 13),
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
                      Text(
                        [
                          if (assignment.courseName != null)
                            assignment.courseName!,
                          if (assignment.className != null)
                            assignment.className!,
                          _formatDeadline(
                            assignment.deadline,
                            assignment.remaining,
                          ),
                        ].join('  ·  '),
                        style: AppTypography.caption.copyWith(
                          color:
                              isOverdue || isDueSoon ? accent : c.textSecondary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                if (widget.wide) ...[
                  const SizedBox(width: 18),
                  Text(
                    assignment.submissionType.displayName,
                    style: AppTypography.caption.copyWith(
                      color: c.textTertiary,
                    ),
                  ),
                ],
                const SizedBox(width: 12),
                AnimatedSlide(
                  offset: _hovered ? const Offset(.12, 0) : Offset.zero,
                  duration: AppMotion.fast,
                  child: PhosphorIcon(
                    PhosphorIconsRegular.caretRight,
                    size: 16,
                    color: c.textTertiary,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _formatDeadline(DateTime deadline, Duration remaining) {
    if (remaining.isNegative) {
      final days = -remaining.inDays;
      return days > 0 ? '已逾期 $days 天' : '已逾期 ${-remaining.inHours} 小时';
    }
    if (remaining.inDays >= 1) {
      return '截止 ${deadline.month}/${deadline.day} · 剩 ${remaining.inDays} 天';
    }
    return '截止 ${deadline.month}/${deadline.day} · 剩 ${remaining.inHours} 小时';
  }
}
