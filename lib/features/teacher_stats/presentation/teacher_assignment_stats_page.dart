import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/skeleton_loader.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/assignment.dart';
import '../../../data/models/pagination.dart';

/// 教师任务统计详情页 — 单个任务的提交统计与学生状态列表。
///
/// 功能(AGENTS.md §6.4):
/// - 顶部统计:提交率 / 准时率 / 评分率 / 逾期 / 未提交
/// - 学生状态列表(分页 + 搜索 + 状态筛选)
/// - 点击学生 → 查看提交详情 + 评分
/// - 催交未提交学生(返回提醒人数)
class TeacherAssignmentStatsPage extends ConsumerStatefulWidget {
  const TeacherAssignmentStatsPage({super.key, required this.assignmentId});

  final String assignmentId;

  @override
  ConsumerState<TeacherAssignmentStatsPage> createState() =>
      _TeacherAssignmentStatsPageState();
}

class _TeacherAssignmentStatsPageState
    extends ConsumerState<TeacherAssignmentStatsPage> {
  Assignment? _assignment;
  AssignmentStats? _stats;
  bool _loading = true;
  Object? _error;

  String _search = '';
  String? _statusFilter; // 'submitted' / 'not_submitted' / 'overdue' / 'graded'

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
      final assignSvc = ref.read(assignmentServiceProvider);
      final assignment = await assignSvc.getAssignment(widget.assignmentId);
      AssignmentStats? stats;
      try {
        stats = await assignSvc.getAssignmentStats(widget.assignmentId);
      } catch (_) {
        // 统计可选 — 失败时仍展示任务和列表
      }
      if (!mounted) return;
      setState(() {
        _assignment = assignment;
        _stats = stats;
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

  Future<void> _remindUnsubmitted() async {
    final scaffold = ScaffoldMessenger.maybeOf(context);
    try {
      final svc = ref.read(submissionServiceProvider);
      final count = await svc.remindUnsubmitted(widget.assignmentId);
      if (!mounted) return;
      scaffold?.showSnackBar(
        SnackBar(
          content: Text(count > 0 ? '已提醒 $count 名未提交学生' : '没有未提交学生需要提醒'),
          duration: const Duration(seconds: 2),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      scaffold?.showSnackBar(
        const SnackBar(
          content: Text('催交失败,请稍后重试'),
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: Text(
          _assignment?.title ?? '任务统计',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        actions: [
          if (_assignment != null && !_assignment!.isOverdue)
            IconButton(
              onPressed: _remindUnsubmitted,
              icon: const Icon(Icons.notifications_active_outlined, size: 22),
              tooltip: '催交未提交学生',
            ),
        ],
      ),
      body: _loading
          ? const SkeletonPage(itemCount: 4)
          : _error != null
              ? ErrorStateView(
                  message: '加载统计失败',
                  onRetry: _load,
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: CustomScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    slivers: [
                      if (_stats != null)
                        SliverToBoxAdapter(
                          child: StaggeredEnter(
                            child: _StatsOverview(
                              stats: _stats!,
                              assignment: _assignment!,
                            ),
                          ),
                        ),
                      SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.fromLTRB(
                            AppSpacing.edge,
                            AppSpacing.md,
                            AppSpacing.edge,
                            AppSpacing.sm,
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                '学生提交状态',
                                style: AppTypography.subtitle,
                              ),
                              const SizedBox(height: AppSpacing.sm),
                              DebouncedSearchField(
                                hint: '搜索姓名 / 学号',
                                onChanged: (v) => setState(() => _search = v),
                              ),
                              const SizedBox(height: AppSpacing.sm),
                              _StatusFilterRow(
                                selected: _statusFilter,
                                onSelect: (s) => setState(
                                  () => _statusFilter =
                                      _statusFilter == s ? null : s,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      SliverFillRemaining(
                        hasScrollBody: true,
                        child: _StudentStatusList(
                          assignmentId: widget.assignmentId,
                          search: _search,
                          statusFilter: _statusFilter,
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }
}

/// 顶部统计概览 — 提交率 / 准时率 / 评分率 / 状态分布。
class _StatsOverview extends StatelessWidget {
  const _StatsOverview({required this.stats, required this.assignment});
  final AssignmentStats stats;
  final Assignment assignment;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.md,
        AppSpacing.edge,
        0,
      ),
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.bgSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: c.border, width: 0.8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            assignment.title,
            style: AppTypography.subtitle.copyWith(color: c.textPrimary),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Text(
            '${assignment.courseName ?? ''} · ${assignment.className ?? ''}',
            style: AppTypography.caption.copyWith(color: c.textSecondary),
          ),
          const SizedBox(height: AppSpacing.md),
          // 三栏比例
          Row(
            children: [
              Expanded(
                child: _RateCell(
                  label: '提交率',
                  value: stats.submissionRate,
                  color: c.primary,
                ),
              ),
              _divider(c),
              Expanded(
                child: _RateCell(
                  label: '准时率',
                  value: stats.onTimeRate,
                  color: c.success,
                ),
              ),
              _divider(c),
              Expanded(
                child: _RateCell(
                  label: '评分率',
                  value: stats.gradedRate,
                  color: c.accent,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          // 状态分布进度条
          _DistributionBar(stats: stats),
          if (stats.averageScore != null) ...[
            const SizedBox(height: AppSpacing.sm + 2),
            Row(
              children: [
                Icon(
                  Icons.trending_up_rounded,
                  size: 16,
                  color: c.textSecondary,
                ),
                const SizedBox(width: 4),
                Text(
                  '平均分 ${stats.averageScore!.toStringAsFixed(1)} / ${stats.maxScore.toStringAsFixed(0)}',
                  style: AppTypography.label.copyWith(color: c.textSecondary),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _divider(AppColorScheme c) {
    return Container(
      width: 1,
      height: 32,
      margin: const EdgeInsets.symmetric(horizontal: 4),
      color: c.border,
    );
  }
}

class _RateCell extends StatelessWidget {
  const _RateCell({
    required this.label,
    required this.value,
    required this.color,
  });
  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '${(value * 100).round()}%',
          style: AppTypography.title.copyWith(color: color),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: AppTypography.caption.copyWith(color: c.textSecondary),
        ),
      ],
    );
  }
}

class _DistributionBar extends StatelessWidget {
  const _DistributionBar({required this.stats});
  final AssignmentStats stats;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final total = stats.total;
    if (total == 0) return const SizedBox.shrink();

    final segments = <_Segment>[
      _Segment(value: stats.graded, color: c.primary, label: '已评分'),
      _Segment(
        value: stats.submitted - stats.graded,
        color: c.success,
        label: '待批阅',
      ),
      _Segment(value: stats.overdue, color: c.danger, label: '逾期'),
      _Segment(value: stats.notSubmitted, color: c.bgSunken, label: '未提交'),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.xs),
          child: SizedBox(
            height: 8,
            child: Row(
              children: segments
                  .where((s) => s.value > 0)
                  .map(
                    (s) => Expanded(
                      flex: s.value,
                      child: ColoredBox(
                        color: s.color,
                        child: const SizedBox(height: 8),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.sm + 2),
        Wrap(
          spacing: AppSpacing.md,
          runSpacing: 4,
          children: segments
              .where((s) => s.value > 0)
              .map(
                (s) => _LegendItem(
                  color: s.color,
                  label: '${s.label} ${s.value}',
                ),
              )
              .toList(),
        ),
      ],
    );
  }
}

class _Segment {
  const _Segment({
    required this.value,
    required this.color,
    required this.label,
  });
  final int value;
  final Color color;
  final String label;
}

class _LegendItem extends StatelessWidget {
  const _LegendItem({required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: AppTypography.label.copyWith(color: c.textSecondary),
        ),
      ],
    );
  }
}

class _StatusFilterRow extends StatelessWidget {
  const _StatusFilterRow({required this.selected, required this.onSelect});
  final String? selected;
  final void Function(String) onSelect;

  static const _filters = [
    ('submitted', '已提交'),
    ('not_submitted', '未提交'),
    ('overdue', '逾期'),
    ('graded', '已评分'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return SizedBox(
      height: 32,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _filters.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final (value, label) = _filters[index];
          final isSelected = selected == value;
          return GestureDetector(
            onTap: () => onSelect(value),
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
                label,
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

class _StudentStatusList extends ConsumerWidget {
  const _StudentStatusList({
    required this.assignmentId,
    required this.search,
    required this.statusFilter,
  });
  final String assignmentId;
  final String search;
  final String? statusFilter;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final svc = ref.watch(assignmentServiceProvider);
    // 使用 ValueKey 包含 search/statusFilter:当搜索关键词或筛选条件改变时,
    // 强制 PagedListView 重建以重新触发 _loadFirst(),避免显示过期数据。
    // (PagedListView 仅在 initState 中获取首屏,不会响应 fetchPage 闭包变化。)
    return PagedListView<StudentStatus>(
      key: ValueKey('$assignmentId|$search|$statusFilter'),
      fetchPage: (page, pageSize) => svc.listAssignmentStudentStatuses(
        assignmentId,
        search: search.isEmpty ? null : search,
        status: statusFilter,
        page: PageRequest(page: page, pageSize: pageSize),
      ),
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.sm,
        AppSpacing.edge,
        96,
      ),
      separator: const SizedBox(height: AppSpacing.sm),
      emptyIcon: Icons.person_outline_rounded,
      emptyTitle: '没有匹配的学生',
      itemBuilder: (context, status, index) => StaggeredEnter(
        delay: Duration(milliseconds: (index * 30).clamp(0, 180)),
        child: _StudentStatusTile(
          status: status,
          onTap: () => _showSubmissionDetail(context, ref, status),
        ),
      ),
    );
  }

  void _showSubmissionDetail(
    BuildContext context,
    WidgetRef ref,
    StudentStatus status,
  ) {
    final c = context.appColors;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: c.bgSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.md)),
      ),
      builder: (_) => _SubmissionDetailSheet(
        assignmentId: assignmentId,
        status: status,
      ),
    );
  }
}

class _StudentStatusTile extends StatelessWidget {
  const _StudentStatusTile({required this.status, required this.onTap});
  final StudentStatus status;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final statusColor = _statusColor(status.status, c);
    return AppCard(
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: c.bgSunken,
            child: Text(
              status.name.isNotEmpty ? status.name.characters.first : '?',
              style: AppTypography.label.copyWith(color: c.textSecondary),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        status.name,
                        style:
                            AppTypography.body.copyWith(color: c.textPrimary),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: statusColor.withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(AppRadius.xs),
                      ),
                      child: Text(
                        status.status.displayName,
                        style: AppTypography.label.copyWith(
                          color: statusColor,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '${status.studentNo} · ${status.className}',
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
          if (status.grade != null)
            Text(
              status.grade!.toStringAsFixed(1),
              style: AppTypography.subtitle.copyWith(color: c.primary),
            )
          else
            Icon(Icons.chevron_right_rounded, color: c.textTertiary, size: 22),
        ],
      ),
    );
  }

  Color _statusColor(SubmissionStatus s, AppColorScheme c) {
    switch (s) {
      case SubmissionStatus.submitted:
        return c.success;
      case SubmissionStatus.graded:
        return c.primary;
      case SubmissionStatus.late:
        return c.danger;
      case SubmissionStatus.draft:
        return c.textTertiary;
      case SubmissionStatus.notSubmitted:
        return c.warning;
    }
  }
}

class _SubmissionDetailSheet extends ConsumerStatefulWidget {
  const _SubmissionDetailSheet({
    required this.assignmentId,
    required this.status,
  });
  final String assignmentId;
  final StudentStatus status;

  @override
  ConsumerState<_SubmissionDetailSheet> createState() =>
      _SubmissionDetailSheetState();
}

class _SubmissionDetailSheetState
    extends ConsumerState<_SubmissionDetailSheet> {
  Submission? _submission;
  bool _loading = true;
  Object? _error;

  // 评分表单
  late final TextEditingController _gradeController;
  late final TextEditingController _commentController;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _gradeController = TextEditingController();
    _commentController = TextEditingController();
    _load();
  }

  @override
  void dispose() {
    _gradeController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final svc = ref.read(submissionServiceProvider);
      final submissions = await svc.listSubmissions(
        widget.assignmentId,
        search: widget.status.studentNo,
        page: const PageRequest(page: 1, pageSize: 5),
      );
      final sub = submissions.items.isNotEmpty ? submissions.items.first : null;
      if (!mounted) return;
      setState(() {
        _submission = sub;
        if (sub != null) {
          if (sub.grade != null) {
            _gradeController.text = sub.grade!.toStringAsFixed(1);
          }
          if (sub.comment != null) {
            _commentController.text = sub.comment!;
          }
        }
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

  Future<void> _saveGrade() async {
    final sub = _submission;
    if (sub == null) return;
    final gradeStr = _gradeController.text.trim();
    if (gradeStr.isEmpty) {
      _toast('请输入成绩');
      return;
    }
    final grade = double.tryParse(gradeStr);
    if (grade == null || grade < 0) {
      _toast('成绩必须为非负数字');
      return;
    }
    setState(() => _saving = true);
    try {
      final svc = ref.read(submissionServiceProvider);
      final updated = await svc.gradeSubmission(
        submissionId: sub.id,
        grade: grade,
        comment: _commentController.text.trim().isEmpty
            ? null
            : _commentController.text.trim(),
      );
      if (!mounted) return;
      setState(() {
        _submission = updated;
        _saving = false;
      });
      _toast('评分已保存');
    } catch (_) {
      if (!mounted) return;
      setState(() => _saving = false);
      _toast('评分失败,请重试');
    }
  }

  void _toast(String message) {
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: EdgeInsets.only(
        left: AppSpacing.edge,
        right: AppSpacing.edge,
        top: AppSpacing.lg,
        bottom: MediaQuery.of(context).viewInsets.bottom + AppSpacing.edge,
      ),
      child: _loading
          ? const SizedBox(
              height: 240,
              child: Center(child: CircularProgressIndicator()),
            )
          : _error != null
              ? SizedBox(
                  height: 200,
                  child: ErrorStateView(
                    message: '加载提交失败',
                    onRetry: _load,
                  ),
                )
              : _buildContent(c),
    );
  }

  Widget _buildContent(AppColorScheme c) {
    final sub = _submission;
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 学生信息
          Row(
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: c.bgSunken,
                child: Text(
                  widget.status.name.isNotEmpty
                      ? widget.status.name.characters.first
                      : '?',
                  style: AppTypography.body.copyWith(color: c.textSecondary),
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.status.name,
                      style: AppTypography.subtitle,
                    ),
                    Text(
                      '${widget.status.studentNo} · ${widget.status.className}',
                      style: AppTypography.caption
                          .copyWith(color: c.textSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),

          if (sub == null) ...[
            Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: c.bgSunken,
                borderRadius: BorderRadius.circular(AppRadius.sm),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline_rounded, color: c.textSecondary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '该学生尚未提交,无法评分。可点击"催交"提醒其提交。',
                      style: AppTypography.caption
                          .copyWith(color: c.textSecondary),
                    ),
                  ),
                ],
              ),
            ),
          ] else ...[
            // 提交内容
            const _SectionLabel(text: '提交内容'),
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: c.bgSunken,
                borderRadius: BorderRadius.circular(AppRadius.sm),
              ),
              child: SelectableText(
                sub.content.isEmpty ? '(无文字内容)' : sub.content,
                style: AppTypography.body.copyWith(color: c.textPrimary),
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // 提交元数据
            _MetaRow(
              label: '提交时间',
              value: _formatDateTime(sub.submittedAt),
            ),
            if (sub.updatedAt != null)
              _MetaRow(
                label: '最近更新',
                value: _formatDateTime(sub.updatedAt!),
              ),
            _MetaRow(
              label: '附件数',
              value: '${sub.attachments.length}',
            ),
            _MetaRow(
              label: '重新提交',
              value: '${sub.resubmissionCount} 次',
            ),
            if (sub.isLate)
              _MetaRow(
                label: '状态',
                value: '逾期提交',
                valueColor: c.danger,
              ),

            const SizedBox(height: AppSpacing.md),
            // 评分表单
            const _SectionLabel(text: '评分与评论'),
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: _gradeController,
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: '成绩',
                hintText: '例如 90',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: _commentController,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: '评论(可选)',
                hintText: '给学生的反馈',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _saving ? null : _saveGrade,
                icon: _saving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.check_rounded, size: 18),
                label: Text(_saving ? '保存中...' : '保存评分'),
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.lg),
        ],
      ),
    );
  }

  String _formatDateTime(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-'
        '${dt.day.toString().padLeft(2, '0')} '
        '${dt.hour.toString().padLeft(2, '0')}:'
        '${dt.minute.toString().padLeft(2, '0')}';
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Text(
      text,
      style: AppTypography.label.copyWith(color: c.textSecondary),
    );
  }
}

class _MetaRow extends StatelessWidget {
  const _MetaRow({
    required this.label,
    required this.value,
    this.valueColor,
  });
  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 72,
            child: Text(
              label,
              style: AppTypography.caption.copyWith(color: c.textTertiary),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTypography.body.copyWith(
                color: valueColor ?? c.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
