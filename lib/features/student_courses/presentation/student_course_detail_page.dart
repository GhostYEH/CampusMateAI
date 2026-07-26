import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/announcement.dart';
import '../../../data/models/assignment.dart';
import '../../../data/models/course.dart';
import '../../../data/models/pagination.dart';

/// 学生课程详情页 — Tab: 通知 / 任务 / 资料 / 班级信息。
class StudentCourseDetailPage extends ConsumerStatefulWidget {
  const StudentCourseDetailPage({super.key, required this.courseId});

  final String courseId;

  @override
  ConsumerState<StudentCourseDetailPage> createState() =>
      _StudentCourseDetailPageState();
}

class _StudentCourseDetailPageState
    extends ConsumerState<StudentCourseDetailPage> {
  Course? _course;
  bool _loading = true;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _loadCourse();
  }

  Future<void> _loadCourse() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final svc = ref.read(courseServiceProvider);
      final course = await svc.getCourse(widget.courseId);
      if (!mounted) return;
      setState(() {
        _course = course;
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

  /// 跳转到 AI 导员,携带课程上下文(course_id)。
  ///
  /// 满足 AGENTS.md §7 — 学生从课程进入 AI 导员时携带 course_id,
  /// AI 导员页面顶部显示 "正在询问:高等数学"。
  void _askCounselorForCourse(Course course) {
    context.go(
      '/counselor',
      extra: <String, dynamic>{
        'course_id': course.id,
        'context_title': course.name,
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        backgroundColor: c.bgBase,
        body: _loading
            ? _buildLoading()
            : _error != null
                ? ErrorStateView(
                    message: '加载课程失败',
                    onRetry: _loadCourse,
                  )
                : _buildBody(),
      ),
    );
  }

  Widget _buildLoading() {
    final c = context.appColors;
    return Scaffold(
      backgroundColor: c.bgBase,
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 200),
            Expanded(
              child: ListView.builder(
                physics: const NeverScrollableScrollPhysics(),
                itemCount: 6,
                itemBuilder: (context, i) => const _SkeletonRow(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    final course = _course!;
    final c = context.appColors;
    return CustomScrollView(
      slivers: [
        SliverAppBar(
          pinned: true,
          expandedHeight: 168,
          backgroundColor: c.bgSurface,
          surfaceTintColor: Colors.transparent,
          foregroundColor: c.textPrimary,
          title: Text(course.name, style: AppTypography.subtitle),
          flexibleSpace: FlexibleSpaceBar(
            background: SafeArea(
              bottom: false,
              child: _CourseHero(course: course),
            ),
          ),
          actions: [
            IconButton(
              tooltip: '询问 AI 导员',
              onPressed: () => _askCounselorForCourse(course),
              icon: const Icon(Icons.smart_toy_outlined),
            ),
            const SizedBox(width: 4),
          ],
          bottom: TabBar(
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            labelColor: c.primary,
            unselectedLabelColor: c.textSecondary,
            indicatorColor: c.primary,
            indicatorSize: TabBarIndicatorSize.label,
            labelStyle: AppTypography.label,
            tabs: const [
              Tab(text: '通知'),
              Tab(text: '任务'),
              Tab(text: '资料'),
              Tab(text: '班级信息'),
            ],
          ),
        ),
        SliverFillRemaining(
          hasScrollBody: true,
          child: TabBarView(
            children: [
              _AnnouncementsTab(course: course),
              _AssignmentsTab(course: course),
              _MaterialsTab(course: course),
              _ClassInfoTab(course: course),
            ],
          ),
        ),
      ],
    );
  }
}

class _CourseHero extends StatelessWidget {
  const _CourseHero({required this.course});
  final Course course;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final courseColor = Color(course.color);
    return Container(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.xl + 24,
        AppSpacing.edge,
        AppSpacing.md,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: courseColor,
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                ),
                child: const Icon(
                  Icons.book_rounded,
                  size: 22,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      course.code,
                      style: AppTypography.overline.copyWith(
                        color: c.textSecondary,
                        fontSize: 11,
                      ),
                    ),
                    Text(
                      '${course.teacher.name} · ${course.teacher.title ?? '教师'}',
                      style: AppTypography.caption.copyWith(
                        color: c.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            course.description ?? '',
            style: AppTypography.body.copyWith(color: c.textSecondary),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class _SkeletonRow extends StatelessWidget {
  const _SkeletonRow();
  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.edge,
        vertical: AppSpacing.sm + 2,
      ),
      child: Row(
        children: [
          SizedBox(
            width: 40,
            height: 40,
            child: CircularProgressIndicator(strokeWidth: 1.4),
          ),
        ],
      ),
    );
  }
}

class _AnnouncementsTab extends ConsumerStatefulWidget {
  const _AnnouncementsTab({required this.course});
  final Course course;

  @override
  ConsumerState<_AnnouncementsTab> createState() => _AnnouncementsTabState();
}

class _AnnouncementsTabState extends ConsumerState<_AnnouncementsTab>
    with AutomaticKeepAliveClientMixin {
  String _search = '';

  @override
  bool get wantKeepAlive => true;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final svc = ref.watch(announcementServiceProvider);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.edge,
            AppSpacing.sm,
            AppSpacing.edge,
            AppSpacing.sm,
          ),
          child: DebouncedSearchField(
            hint: '搜索通知',
            onChanged: (v) => setState(() => _search = v),
          ),
        ),
        Expanded(
          child: PagedListView<Announcement>(
            fetchPage: (page, pageSize) => svc.listStudentAnnouncements(
              courseId: widget.course.id,
              search: _search.isEmpty ? null : _search,
              page: PageRequest(page: page, pageSize: pageSize),
            ),
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.edge,
              0,
              AppSpacing.edge,
              AppSpacing.xl,
            ),
            separator: const SizedBox(height: AppSpacing.sm + 2),
            emptyIcon: Icons.notifications_none_rounded,
            emptyTitle: '该课程暂无通知',
            itemBuilder: (context, ann, index) => StaggeredEnter(
              delay: Duration(milliseconds: (index * 40).clamp(0, 200)),
              child: _AnnouncementTile(announcement: ann),
            ),
          ),
        ),
      ],
    );
  }
}

class _AssignmentsTab extends ConsumerStatefulWidget {
  const _AssignmentsTab({required this.course});
  final Course course;

  @override
  ConsumerState<_AssignmentsTab> createState() => _AssignmentsTabState();
}

class _AssignmentsTabState extends ConsumerState<_AssignmentsTab>
    with AutomaticKeepAliveClientMixin {
  String _search = '';

  @override
  bool get wantKeepAlive => true;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final svc = ref.watch(assignmentServiceProvider);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.edge,
            AppSpacing.sm,
            AppSpacing.edge,
            AppSpacing.sm,
          ),
          child: DebouncedSearchField(
            hint: '搜索任务',
            onChanged: (v) => setState(() => _search = v),
          ),
        ),
        Expanded(
          child: PagedListView<Assignment>(
            fetchPage: (page, pageSize) => svc.listStudentAssignments(
              courseId: widget.course.id,
              search: _search.isEmpty ? null : _search,
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
            emptyTitle: '该课程暂无任务',
            itemBuilder: (context, assignment, index) => StaggeredEnter(
              delay: Duration(milliseconds: (index * 40).clamp(0, 200)),
              child: _AssignmentTile(assignment: assignment),
            ),
          ),
        ),
      ],
    );
  }
}

class _MaterialsTab extends StatelessWidget {
  const _MaterialsTab({required this.course});
  final Course course;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.folder_outlined, size: 56, color: c.textTertiary),
            const SizedBox(height: AppSpacing.md),
            const Text('课程资料功能开发中', style: AppTypography.bodyStrong),
            const SizedBox(height: 4),
            Text(
              'Mock 模式暂未提供资料下载',
              style: AppTypography.caption.copyWith(color: c.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

class _ClassInfoTab extends ConsumerStatefulWidget {
  const _ClassInfoTab({required this.course});
  final Course course;

  @override
  ConsumerState<_ClassInfoTab> createState() => _ClassInfoTabState();
}

class _ClassInfoTabState extends ConsumerState<_ClassInfoTab> {
  Future<List<SchoolClass>>? _future;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    final svc = ref.read(courseServiceProvider);
    setState(() {
      _future = svc.listClasses(widget.course.id);
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return FutureBuilder<List<SchoolClass>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return ListView.builder(
            itemCount: 4,
            itemBuilder: (context, i) => const _SkeletonRow(),
          );
        }
        if (snap.hasError || !snap.hasData) {
          return ErrorStateView(
            message: '加载班级信息失败',
            onRetry: _reload,
          );
        }
        final classes = snap.data!;
        return ListView(
          padding: const EdgeInsets.all(AppSpacing.edge),
          children: [
            for (final cls in classes)
              Container(
                margin: const EdgeInsets.only(bottom: AppSpacing.sm + 2),
                padding: const EdgeInsets.all(AppSpacing.md),
                decoration: BoxDecoration(
                  color: c.bgSurface,
                  borderRadius: BorderRadius.circular(AppRadius.md),
                  border: Border.all(color: c.border, width: 1),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(cls.name, style: AppTypography.subtitle),
                    const SizedBox(height: 4),
                    Text(
                      '${cls.year ?? ''} · ${cls.major ?? ''} · ${cls.studentCount}人',
                      style: AppTypography.caption,
                    ),
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: c.bgSunken,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        '邀请码: ${cls.inviteCode}',
                        style: AppTypography.label.copyWith(fontSize: 11),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }
}

class _AnnouncementTile extends StatelessWidget {
  const _AnnouncementTile({required this.announcement});
  final Announcement announcement;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => context.push('/announcements/${announcement.id}'),
        borderRadius: BorderRadius.circular(AppRadius.md),
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: c.bgSurface,
            borderRadius: BorderRadius.circular(AppRadius.md),
            border: Border.all(color: c.border, width: 1),
          ),
          child: Row(
            children: [
              if (!announcement.read)
                Container(
                  width: 8,
                  height: 8,
                  margin: const EdgeInsets.only(right: 10),
                  decoration: BoxDecoration(
                    color: c.accent,
                    shape: BoxShape.circle,
                  ),
                ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      announcement.title,
                      style: AppTypography.bodyStrong.copyWith(
                        color: c.textPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _formatDate(announcement.publishedAt),
                      style: AppTypography.overline.copyWith(
                        color: c.textTertiary,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right_rounded,
                color: c.textTertiary,
                size: 22,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime dt) =>
      '${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
}

class _AssignmentTile extends StatelessWidget {
  const _AssignmentTile({required this.assignment});
  final Assignment assignment;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
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
            border: Border.all(color: c.border, width: 1),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      assignment.title,
                      style: AppTypography.bodyStrong.copyWith(
                        color: c.textPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  _StatusBadge(assignment: assignment),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                '截止 ${_formatDate(assignment.deadline)}',
                style: AppTypography.caption.copyWith(
                  color: _deadlineColor(assignment.deadline, c),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime dt) =>
      '${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';

  Color _deadlineColor(DateTime dt, AppColorScheme c) {
    final now = DateTime.now();
    if (dt.isBefore(now)) return c.danger;
    if (dt.difference(now).inHours < 24) return c.accent;
    return c.textSecondary;
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.assignment});
  final Assignment assignment;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final (label, fg, bg) = assignment.isOverdue
        ? ('已逾期', c.danger, c.danger.withValues(alpha: 0.12))
        : assignment.isDueSoon
            ? ('即将截止', c.accent, c.accent.withValues(alpha: 0.12))
            : ('进行中', c.success, c.success.withValues(alpha: 0.12));
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: AppTypography.label.copyWith(color: fg, fontSize: 11),
      ),
    );
  }
}
