import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../app/providers/auth_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/skeleton_loader.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/assignment.dart';
import '../../../data/models/course.dart';
import '../../../data/models/dashboard.dart';
import '../../../data/models/pagination.dart';

/// 教师统计概览页 — 列出所有任务的提交统计。
///
/// 功能(AGENTS.md §6.4):
/// - 总览:活跃任务 / 待批阅 / 已评分 / 逾期人数
/// - 任务列表(分页 + 搜索 + 课程筛选)
/// - 点击进入单任务统计详情(`/teacher/stats/:assignmentId`)
///
/// 视觉原则:图表克制,优先使用进度条和分组列表,不堆叠大量统计卡片。
class TeacherStatsPage extends ConsumerStatefulWidget {
  const TeacherStatsPage({super.key});

  @override
  ConsumerState<TeacherStatsPage> createState() => _TeacherStatsPageState();
}

class _TeacherStatsPageState extends ConsumerState<TeacherStatsPage> {
  String _search = '';
  String? _courseFilter;
  List<Course> _courses = [];
  bool _loadingCourses = true;
  TeacherDashboard? _dashboard;

  @override
  void initState() {
    super.initState();
    _loadCourses();
    _loadDashboard();
  }

  Future<void> _loadCourses() async {
    try {
      final svc = ref.read(courseServiceProvider);
      final result = await svc.listCourses(
        page: const PageRequest(page: 1, pageSize: 100),
      );
      if (!mounted) return;
      setState(() {
        _courses = result.items;
        _loadingCourses = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingCourses = false);
    }
  }

  Future<void> _loadDashboard() async {
    try {
      final svc = ref.read(dashboardServiceProvider);
      final dashboard = await svc.getTeacherDashboard();
      if (!mounted) return;
      setState(() => _dashboard = dashboard);
    } catch (_) {
      // 静默失败 — 总览数据非关键
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final assignmentSvc = ref.watch(assignmentServiceProvider);

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('任务统计'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
      ),
      body: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          if (_dashboard != null)
            SliverToBoxAdapter(
              child: StaggeredEnter(
                child: _OverviewStrip(dashboard: _dashboard!),
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
                  const Text('任务列表', style: AppTypography.subtitle),
                  const SizedBox(height: AppSpacing.sm),
                  DebouncedSearchField(
                    hint: '搜索任务标题',
                    onChanged: (v) => setState(() => _search = v),
                  ),
                  if (!_loadingCourses && _courses.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.sm),
                    _CourseFilterChips(
                      courses: _courses,
                      selectedCourseId: _courseFilter,
                      onSelect: (id) => setState(
                        () => _courseFilter = _courseFilter == id ? null : id,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          SliverFillRemaining(
            hasScrollBody: false,
            child: _TaskListSection(
              assignmentSvc: assignmentSvc,
              search: _search,
              courseFilter: _courseFilter,
              courses: _courses,
            ),
          ),
        ],
      ),
    );
  }
}

class _OverviewStrip extends StatelessWidget {
  const _OverviewStrip({required this.dashboard});
  final TeacherDashboard dashboard;

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
      child: Row(
        children: [
          Expanded(
            child: _StatCell(
              label: '活跃任务',
              value: dashboard.activeAssignmentCount,
              color: c.primary,
            ),
          ),
          _divider(c),
          Expanded(
            child: _StatCell(
              label: '待批阅',
              value: dashboard.pendingSubmissions,
              color: c.accent,
            ),
          ),
          _divider(c),
          Expanded(
            child: _StatCell(
              label: '逾期人数',
              value: dashboard.overdueStudents,
              color: c.danger,
            ),
          ),
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

class _StatCell extends StatelessWidget {
  const _StatCell({
    required this.label,
    required this.value,
    required this.color,
  });
  final String label;
  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '$value',
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

class _CourseFilterChips extends StatelessWidget {
  const _CourseFilterChips({
    required this.courses,
    required this.selectedCourseId,
    required this.onSelect,
  });
  final List<Course> courses;
  final String? selectedCourseId;
  final void Function(String) onSelect;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return SizedBox(
      height: 32,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: courses.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final course = courses[index];
          final selected = course.id == selectedCourseId;
          return GestureDetector(
            onTap: () => onSelect(course.id),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color:
                    selected ? c.primary.withValues(alpha: 0.14) : c.bgSunken,
                borderRadius: BorderRadius.circular(AppRadius.xs),
                border: Border.all(
                  color: selected ? c.primary : c.border,
                  width: selected ? 1.2 : 0.8,
                ),
              ),
              child: Text(
                course.name,
                style: AppTypography.label.copyWith(
                  color: selected ? c.primary : c.textSecondary,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _TaskListSection extends ConsumerWidget {
  const _TaskListSection({
    required this.assignmentSvc,
    required this.search,
    required this.courseFilter,
    required this.courses,
  });
  final dynamic assignmentSvc;
  final String search;
  final String? courseFilter;
  final List<Course> courses;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 当前教师可能有多门课程下的任务;按课程筛选时优先按所选课程班级加载。
    // 简化实现:遍历所有课程的班级,合并任务列表,前端再次过滤。
    // 性能上仍使用 PagedListView,服务端分页(由 Mock/Real 决定)。
    if (courses.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(48),
          child: EmptyStateView(
            icon: Icons.insights_outlined,
            title: '暂无统计数据',
            message: '创建课程和班级后,这里会显示任务统计',
          ),
        ),
      );
    }

    // 按 courseFilter 找出对应课程下的班级,否则用第一个课程班级
    final targetCourse = courseFilter != null
        ? courses.where((c) => c.id == courseFilter).firstOrNull
        : courses.first;

    if (targetCourse == null) {
      return const SizedBox.shrink();
    }

    // 列出该课程第一个班级的任务作为统计入口
    // 真实场景下应由后端提供"按课程聚合"接口
    return FutureBuilder<List<SchoolClass>>(
      future: ref.read(courseServiceProvider).listClasses(targetCourse.id),
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const SkeletonPage(itemCount: 4);
        }
        final classes = snapshot.data!;
        if (classes.isEmpty) {
          return Center(
            child: EmptyStateView(
              icon: Icons.group_outlined,
              title: '课程下还没有班级',
              message: '在"课程"页创建班级后才能查看统计',
              actionLabel: '去创建班级',
              onAction: () => context.go('/teacher/courses'),
            ),
          );
        }
        final firstClass = classes.first;
        return PagedListView<Assignment>(
          fetchPage: (page, pageSize) => assignmentSvc.listAssignments(
            firstClass.id,
            search: search.isEmpty ? null : search,
            page: PageRequest(page: page, pageSize: pageSize),
          ),
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.edge,
            AppSpacing.sm,
            AppSpacing.edge,
            96,
          ),
          separator: const SizedBox(height: AppSpacing.sm + 2),
          emptyIcon: Icons.assignment_outlined,
          emptyTitle: '暂无任务',
          emptyMessage: '前往"发布"页发布任务',
          emptyActionLabel: '去发布',
          onEmptyAction: () => context.go('/teacher/publish'),
          itemBuilder: (context, assignment, index) => StaggeredEnter(
            delay: Duration(milliseconds: (index * 30).clamp(0, 180)),
            child: _AssignmentStatCard(
              assignment: assignment,
              courseName: targetCourse.name,
            ),
          ),
        );
      },
    );
  }
}

/// 单任务统计卡片 — 显示标题、截止、提交进度、状态分布。
class _AssignmentStatCard extends StatelessWidget {
  const _AssignmentStatCard({
    required this.assignment,
    required this.courseName,
  });
  final Assignment assignment;
  final String courseName;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final isOverdue = assignment.isOverdue;
    final isDueSoon = assignment.isDueSoon;

    return AppCard(
      onTap: () => context.go('/teacher/stats/${assignment.id}'),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  assignment.title,
                  style: AppTypography.subtitle.copyWith(color: c.textPrimary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (isOverdue)
                _StatusChip(label: '已截止', color: c.danger)
              else if (isDueSoon)
                _StatusChip(label: '即将截止', color: c.warning),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '$courseName · ${assignment.className ?? ''}',
            style: AppTypography.caption.copyWith(color: c.textSecondary),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: AppSpacing.md),
          // 提交进度条
          _SubmissionProgress(assignment: assignment),
          const SizedBox(height: AppSpacing.sm + 2),
          // 状态分布
          Row(
            children: [
              _MiniStat(
                label: '已交',
                value: assignment.submittedCount,
                color: c.success,
              ),
              const SizedBox(width: AppSpacing.md),
              _MiniStat(
                label: '已评分',
                value: assignment.gradedCount,
                color: c.primary,
              ),
              const SizedBox(width: AppSpacing.md),
              _MiniStat(
                label: '逾期',
                value: assignment.overdueCount,
                color: c.danger,
              ),
              const Spacer(),
              Icon(
                Icons.chevron_right_rounded,
                color: c.textTertiary,
                size: 22,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.color});
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(AppRadius.xs),
      ),
      child: Text(
        label,
        style: AppTypography.label.copyWith(color: color, fontSize: 11),
      ),
    );
  }
}

class _SubmissionProgress extends StatelessWidget {
  const _SubmissionProgress({required this.assignment});
  final Assignment assignment;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final rate = assignment.submissionRate;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              '提交率',
              style: AppTypography.label.copyWith(color: c.textSecondary),
            ),
            const Spacer(),
            Text(
              '${(rate * 100).round()}% · ${assignment.submittedCount}/${assignment.totalStudents}',
              style: AppTypography.label.copyWith(color: c.textPrimary),
            ),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.xs),
          child: LinearProgressIndicator(
            value: rate,
            minHeight: 6,
            backgroundColor: c.bgSunken,
            valueColor: AlwaysStoppedAnimation<Color>(
              rate >= 0.8
                  ? c.success
                  : rate >= 0.5
                      ? c.primary
                      : c.warning,
            ),
          ),
        ),
      ],
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({
    required this.label,
    required this.value,
    required this.color,
  });
  final String label;
  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(
          '$value $label',
          style: AppTypography.label.copyWith(color: c.textSecondary),
        ),
      ],
    );
  }
}
