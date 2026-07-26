import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/course.dart';
import '../../../data/models/pagination.dart';

/// 管理员课程与班级页 — 全部课程的只读视图(管理员最小能力)。
///
/// 不提供创建/编辑入口 — 由教师管理自己的课程。
/// 管理员只能查看以便了解系统整体使用情况。
class AdminCoursesPage extends ConsumerStatefulWidget {
  const AdminCoursesPage({super.key});

  @override
  ConsumerState<AdminCoursesPage> createState() => _AdminCoursesPageState();
}

class _AdminCoursesPageState extends ConsumerState<AdminCoursesPage> {
  String _search = '';

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final svc = ref.watch(courseServiceProvider);

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('课程与班级'),
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
              AppSpacing.md,
            ),
            child: DebouncedSearchField(
              hint: '搜索课程名 / 课程代码',
              onChanged: (v) => setState(() => _search = v),
            ),
          ),
          Expanded(
            child: PagedListView<Course>(
              fetchPage: (page, pageSize) => svc.listCourses(
                search: _search.isEmpty ? null : _search,
                page: PageRequest(page: page, pageSize: pageSize),
              ),
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.edge,
                AppSpacing.sm,
                AppSpacing.edge,
                96,
              ),
              separator: const SizedBox(height: AppSpacing.sm + 2),
              emptyIcon: Icons.class_outlined,
              emptyTitle: '暂无课程',
              itemBuilder: (context, course, index) => StaggeredEnter(
                delay: Duration(milliseconds: (index * 30).clamp(0, 180)),
                child: _AdminCourseCard(course: course),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AdminCourseCard extends ConsumerStatefulWidget {
  const _AdminCourseCard({required this.course});
  final Course course;

  @override
  ConsumerState<_AdminCourseCard> createState() => _AdminCourseCardState();
}

class _AdminCourseCardState extends ConsumerState<_AdminCourseCard> {
  List<SchoolClass> _classes = [];
  bool _loadingClasses = false;
  bool _expanded = false;

  Future<void> _loadClasses() async {
    if (_classes.isNotEmpty) {
      setState(() => _expanded = !_expanded);
      return;
    }
    setState(() {
      _loadingClasses = true;
      _expanded = true;
    });
    try {
      final svc = ref.read(courseServiceProvider);
      final classes = await svc.listClasses(widget.course.id);
      if (!mounted) return;
      setState(() {
        _classes = classes;
        _loadingClasses = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingClasses = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final course = widget.course;
    final courseColor = Color(course.color);

    return AppCard(
      onTap: _loadClasses,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
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
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            course.name,
                            style: AppTypography.subtitle.copyWith(
                              color: c.textPrimary,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          course.code,
                          style: AppTypography.label.copyWith(
                            color: c.textTertiary,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${course.teacher.name} · ${course.semester.shortName}',
                      style: AppTypography.caption.copyWith(
                        color: c.textSecondary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              Icon(
                _expanded
                    ? Icons.expand_less_rounded
                    : Icons.expand_more_rounded,
                color: c.textTertiary,
                size: 22,
              ),
            ],
          ),
          if (_expanded) ...[
            const SizedBox(height: AppSpacing.md),
            const Divider(height: 1),
            const SizedBox(height: AppSpacing.sm),
            if (_loadingClasses)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
                child: Center(
                  child: SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              )
            else if (_classes.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                child: Text(
                  '该课程下没有班级',
                  style: AppTypography.caption.copyWith(
                    color: c.textSecondary,
                  ),
                ),
              )
            else
              Column(
                children: [
                  for (int i = 0; i < _classes.length; i++) ...[
                    _ClassRow(
                      cls: _classes[i],
                      onTap: () => context.go(
                        '/teacher/courses/${course.id}/classes/${_classes[i].id}',
                      ),
                    ),
                    if (i < _classes.length - 1) const SizedBox(height: 4),
                  ],
                ],
              ),
          ],
        ],
      ),
    );
  }
}

class _ClassRow extends StatelessWidget {
  const _ClassRow({required this.cls, required this.onTap});
  final SchoolClass cls;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
        child: Row(
          children: [
            Icon(Icons.groups_2_outlined, size: 16, color: c.textSecondary),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                cls.name,
                style: AppTypography.body.copyWith(color: c.textPrimary),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: c.bgSunken,
                borderRadius: BorderRadius.circular(AppRadius.xs),
              ),
              child: Text(
                '邀请码 ${cls.inviteCode}',
                style: AppTypography.label.copyWith(
                  color: c.textSecondary,
                  fontSize: 10,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
