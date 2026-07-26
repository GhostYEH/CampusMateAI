import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/skeleton_loader.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/course.dart';
import '../../../data/models/pagination.dart';

/// 教师班级详情页 — Tab 布局:成员 / 通知 / 任务。
///
/// 严格遵循 AGENTS.md §6.2 教师数据权限:
/// 只展示与当前课程相关字段,不返回私人 AI 对话 / 私人待办 /
/// 学习陪伴 / 摄像头 / 表情信息。
class TeacherClassDetailPage extends ConsumerStatefulWidget {
  const TeacherClassDetailPage({
    super.key,
    required this.courseId,
    required this.classId,
  });

  final String courseId;
  final String classId;

  @override
  ConsumerState<TeacherClassDetailPage> createState() =>
      _TeacherClassDetailPageState();
}

class _TeacherClassDetailPageState
    extends ConsumerState<TeacherClassDetailPage> {
  Course? _course;
  SchoolClass? _class;
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
      final svc = ref.read(courseServiceProvider);
      final course = await svc.getCourse(widget.courseId);
      final classes = await svc.listClasses(widget.courseId);
      final cls = classes.where((c) => c.id == widget.classId).firstOrNull;
      if (cls == null) {
        throw Exception('班级不存在');
      }
      if (!mounted) return;
      setState(() {
        _course = course;
        _class = cls;
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
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        backgroundColor: c.bgBase,
        body: _loading
            ? const _Loading()
            : _error != null
                ? ErrorStateView(message: '加载失败', onRetry: _load)
                : NestedScrollView(
                    headerSliverBuilder: (context, innerBoxIsScrolled) => [
                      SliverAppBar(
                        pinned: true,
                        expandedHeight: 144,
                        backgroundColor: c.bgSurface,
                        surfaceTintColor: Colors.transparent,
                        foregroundColor: c.textPrimary,
                        leading: IconButton(
                          icon: const Icon(Icons.arrow_back_rounded),
                          onPressed: () =>
                              context.go('/teacher/courses/${widget.courseId}'),
                        ),
                        title: Text(_class?.name ?? '班级详情'),
                        flexibleSpace: FlexibleSpaceBar(
                          background: _ClassHeader(
                            course: _course!,
                            cls: _class!,
                          ),
                        ),
                        bottom: TabBar(
                          labelColor: c.primary,
                          unselectedLabelColor: c.textSecondary,
                          indicatorColor: c.primary,
                          indicatorSize: TabBarIndicatorSize.label,
                          tabs: const [
                            Tab(text: '成员'),
                            Tab(text: '通知'),
                            Tab(text: '任务'),
                          ],
                        ),
                      ),
                    ],
                    body: TabBarView(
                      children: [
                        _MembersTab(classId: widget.classId),
                        _AnnouncementsTab(
                          course: _course!,
                          cls: _class!,
                        ),
                        _AssignmentsTab(
                          course: _course!,
                          cls: _class!,
                        ),
                      ],
                    ),
                  ),
      ),
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        SizedBox(height: 200),
        SkeletonCard(height: 100),
        SizedBox(height: AppSpacing.lg),
        SkeletonCard(height: 200),
      ],
    );
  }
}

class _ClassHeader extends StatelessWidget {
  const _ClassHeader({required this.course, required this.cls});
  final Course course;
  final SchoolClass cls;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        72,
        AppSpacing.edge,
        AppSpacing.md,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 8,
                  vertical: 2,
                ),
                decoration: BoxDecoration(
                  color: c.primarySubtle,
                  borderRadius: BorderRadius.circular(AppRadius.xs),
                ),
                child: Text(
                  course.code,
                  style: AppTypography.label.copyWith(
                    color: c.primary,
                    fontSize: 11,
                  ),
                ),
              ),
              const SizedBox(width: 6),
              Text(
                course.name,
                style: AppTypography.caption.copyWith(color: c.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Icon(Icons.vpn_key_outlined, size: 14, color: c.textSecondary),
              const SizedBox(width: 4),
              Text(
                cls.inviteCode,
                style: AppTypography.label.copyWith(
                  color: c.textSecondary,
                  fontSize: 12,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Icon(Icons.group_outlined, size: 14, color: c.textSecondary),
              const SizedBox(width: 4),
              Text(
                '${cls.studentCount} 学生',
                style: AppTypography.caption.copyWith(color: c.textSecondary),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// 成员 Tab — 显示班级成员(分页 + 搜索 + 筛选)。
///
/// 严格遵循教师数据权限:只显示课程相关字段。
class _MembersTab extends ConsumerStatefulWidget {
  const _MembersTab({required this.classId});
  final String classId;

  @override
  ConsumerState<_MembersTab> createState() => _MembersTabState();
}

class _MembersTabState extends ConsumerState<_MembersTab> {
  String _search = '';
  String? _statusFilter;

  static const _statusOptions = [
    (null, '全部'),
    ('submitted', '已提交'),
    ('not_submitted', '未提交'),
    ('overdue', '逾期'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final svc = ref.watch(courseServiceProvider);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(AppSpacing.edge),
          child: Column(
            children: [
              DebouncedSearchField(
                hint: '搜索姓名 / 学号',
                onChanged: (v) => setState(() => _search = v),
              ),
              const SizedBox(height: AppSpacing.sm),
              SizedBox(
                height: 32,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: _statusOptions.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 6),
                  itemBuilder: (context, i) {
                    final (value, label) = _statusOptions[i];
                    final selected = _statusFilter == value;
                    return Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: () => setState(() => _statusFilter = value),
                        borderRadius: BorderRadius.circular(999),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: selected ? c.primary : c.bgSurface,
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(
                              color: selected ? c.primary : c.border,
                              width: 1,
                            ),
                          ),
                          child: Text(
                            label,
                            style: AppTypography.label.copyWith(
                              color: selected ? c.onPrimary : c.textSecondary,
                              fontSize: 11,
                            ),
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: PagedListView<ClassMember>(
            fetchPage: (page, pageSize) => svc.listClassMembers(
              widget.classId,
              search: _search.isEmpty ? null : _search,
              submissionStatus: _statusFilter,
              page: PageRequest(page: page, pageSize: pageSize),
            ),
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.edge,
              0,
              AppSpacing.edge,
              AppSpacing.lg,
            ),
            separator: const SizedBox(height: AppSpacing.sm),
            emptyIcon: Icons.person_off_outlined,
            emptyTitle: '没有匹配的学生',
            emptyMessage: '尝试调整搜索或筛选条件',
            itemBuilder: (context, member, index) => StaggeredEnter(
              delay: Duration(milliseconds: (index * 30).clamp(0, 180)),
              child: _MemberTile(member: member),
            ),
          ),
        ),
      ],
    );
  }
}

class _MemberTile extends StatelessWidget {
  const _MemberTile({required this.member});
  final ClassMember member;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final hasOverdue = member.hasOverdue;
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: c.primarySubtle,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Center(
              child: Text(
                member.name.isNotEmpty ? member.name.characters.first : '?',
                style: AppTypography.subtitle.copyWith(
                  color: c.primary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        member.name,
                        style: AppTypography.subtitle.copyWith(
                          color: c.textPrimary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (hasOverdue) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          color: c.dangerSubtle,
                          borderRadius: BorderRadius.circular(AppRadius.xs),
                        ),
                        child: Text(
                          '逾期',
                          style: AppTypography.label.copyWith(
                            color: c.danger,
                            fontSize: 10,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Wrap(
                  spacing: 8,
                  children: [
                    if (member.studentId.isNotEmpty)
                      _MiniMeta(label: '学号 ${member.studentId}'),
                    if (member.grade != null && member.grade!.isNotEmpty)
                      _MiniMeta(label: member.grade!),
                    if (member.major != null && member.major!.isNotEmpty)
                      _MiniMeta(label: member.major!),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniMeta extends StatelessWidget {
  const _MiniMeta({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Text(
      label,
      style: AppTypography.label.copyWith(
        color: c.textTertiary,
        fontSize: 11,
      ),
    );
  }
}

class _AnnouncementsTab extends ConsumerWidget {
  const _AnnouncementsTab({required this.course, required this.cls});
  final Course course;
  final SchoolClass cls;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.appColors;
    final svc = ref.watch(announcementServiceProvider);
    return PagedListView(
      fetchPage: (page, pageSize) => svc.listAnnouncements(
        cls.id,
        page: PageRequest(page: page, pageSize: pageSize),
      ),
      padding: const EdgeInsets.all(AppSpacing.edge),
      separator: const SizedBox(height: AppSpacing.sm),
      emptyIcon: Icons.campaign_outlined,
      emptyTitle: '尚未发布通知',
      emptyMessage: '前往"发布"页发布通知',
      emptyActionLabel: '去发布',
      onEmptyAction: () => context.go('/teacher/publish'),
      itemBuilder: (context, ann, index) => StaggeredEnter(
        delay: Duration(milliseconds: (index * 30).clamp(0, 180)),
        child: AppCard(
          onTap: () => context.go('/announcements/${ann.id}'),
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      ann.title,
                      style: AppTypography.subtitle.copyWith(
                        color: c.textPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if (!ann.read)
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: c.accent,
                        shape: BoxShape.circle,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                '${ann.readCount}/${ann.totalStudents} 已读 · ${_formatDate(ann.publishedAt)}',
                style: AppTypography.caption.copyWith(color: c.textSecondary),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _formatDate(DateTime t) {
    return '${t.month}/${t.day} ${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }
}

class _AssignmentsTab extends ConsumerWidget {
  const _AssignmentsTab({required this.course, required this.cls});
  final Course course;
  final SchoolClass cls;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.appColors;
    final svc = ref.watch(assignmentServiceProvider);
    return PagedListView(
      fetchPage: (page, pageSize) => svc.listAssignments(
        cls.id,
        page: PageRequest(page: page, pageSize: pageSize),
      ),
      padding: const EdgeInsets.all(AppSpacing.edge),
      separator: const SizedBox(height: AppSpacing.sm),
      emptyIcon: Icons.assignment_outlined,
      emptyTitle: '尚未发布任务',
      emptyMessage: '前往"发布"页发布任务',
      emptyActionLabel: '去发布',
      onEmptyAction: () => context.go('/teacher/publish'),
      itemBuilder: (context, assignment, index) => StaggeredEnter(
        delay: Duration(milliseconds: (index * 30).clamp(0, 180)),
        child: AppCard(
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
                      style: AppTypography.subtitle.copyWith(
                        color: c.textPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  _DeadlineChip(deadline: assignment.deadline),
                ],
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  Expanded(
                    child: _SubmissionProgress(assignment: assignment),
                  ),
                  const SizedBox(width: 8),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: c.textTertiary,
                    size: 22,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DeadlineChip extends StatelessWidget {
  const _DeadlineChip({required this.deadline});
  final DateTime deadline;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final remaining = deadline.difference(DateTime.now());
    final isOverdue = remaining.isNegative;
    final isDueSoon = !isOverdue && remaining.inHours < 24;

    final color = isOverdue
        ? c.danger
        : isDueSoon
            ? c.warning
            : c.textSecondary;
    final bg = isOverdue
        ? c.dangerSubtle
        : isDueSoon
            ? c.warningSubtle
            : c.bgSunken;

    String label;
    if (isOverdue) {
      label = '已截止';
    } else if (remaining.inHours < 1) {
      label = '${remaining.inMinutes}分钟后';
    } else if (remaining.inHours < 24) {
      label = '${remaining.inHours}小时后';
    } else {
      label = '${remaining.inDays}天后';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppRadius.xs),
      ),
      child: Text(
        label,
        style: AppTypography.label.copyWith(color: color, fontSize: 10),
      ),
    );
  }
}

class _SubmissionProgress extends StatelessWidget {
  const _SubmissionProgress({required this.assignment});
  final dynamic assignment;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final total = assignment.totalStudents as int;
    final submitted = assignment.submittedCount as int;
    final rate = total == 0 ? 1.0 : submitted / total;
    final color = rate >= 0.8
        ? c.success
        : rate >= 0.5
            ? c.warning
            : c.danger;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(
            value: rate,
            backgroundColor: c.bgSunken,
            valueColor: AlwaysStoppedAnimation(color),
            minHeight: 4,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '$submitted/$total 已提交 · ${assignment.gradedCount} 已评分',
          style: AppTypography.caption.copyWith(color: c.textSecondary),
        ),
      ],
    );
  }
}
