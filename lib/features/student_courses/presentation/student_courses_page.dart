import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/debounced_search_field.dart';
import '../../../core/widgets/paged_list_view.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/models.dart';

/// 学生课程列表页 — 学期筛选 + 搜索 + 加入班级入口。
class StudentCoursesPage extends ConsumerStatefulWidget {
  const StudentCoursesPage({super.key});

  @override
  ConsumerState<StudentCoursesPage> createState() => _StudentCoursesPageState();
}

class _StudentCoursesPageState extends ConsumerState<StudentCoursesPage> {
  String _search = '';
  String? _semesterFilter;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final courseSvc = ref.watch(courseServiceProvider);
    final user = ref.watch(currentAuthUserProvider);

    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('我的课程'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
      ),
      body: Column(
        children: [
          _FilterBar(
            search: _search,
            semester: _semesterFilter,
            onSearchChanged: (v) => setState(() => _search = v),
            onSemesterChanged: (v) => setState(() => _semesterFilter = v),
          ),
          Expanded(
            child: _CourseList(
              fetchPage: (page, pageSize) => courseSvc.listCourses(
                semester: _semesterFilter,
                search: _search.isEmpty ? null : _search,
                page: PageRequest(page: page, pageSize: pageSize),
              ),
              onJoinByInviteCode: _showJoinDialog,
              currentUserRole: user?.role,
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showJoinDialog,
        icon: const Icon(Icons.add_rounded, size: 22),
        label: const Text('加入班级'),
        backgroundColor: c.primary,
        foregroundColor: c.onPrimary,
      ),
    );
  }

  void _showJoinDialog() {
    final codeController = TextEditingController();
    final c = context.appColors;
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('输入邀请码加入班级'),
        content: TextField(
          controller: codeController,
          autofocus: true,
          textCapitalization: TextCapitalization.characters,
          decoration: InputDecoration(
            hintText: '例如 HM2024-1',
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () async {
              final code = codeController.text.trim();
              if (code.isEmpty) return;
              Navigator.pop(dialogContext);
              await _joinByCode(code);
            },
            style: FilledButton.styleFrom(
              backgroundColor: c.primary,
              foregroundColor: c.onPrimary,
            ),
            child: const Text('加入'),
          ),
        ],
      ),
    );
  }

  Future<void> _joinByCode(String code) async {
    final courseSvc = ref.read(courseServiceProvider);
    final messenger = ScaffoldMessenger.maybeOf(context);
    try {
      final classJoined = await courseSvc.joinByInviteCode(code);
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(
          content: Text('已加入班级: ${classJoined.name}'),
          duration: const Duration(seconds: 2),
        ),
      );
      // 触发刷新
      setState(() {});
    } catch (e) {
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(
          content: Text('加入失败: $e'),
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }
}

class _FilterBar extends StatelessWidget {
  const _FilterBar({
    required this.search,
    required this.semester,
    required this.onSearchChanged,
    required this.onSemesterChanged,
  });

  final String search;
  final String? semester;
  final ValueChanged<String> onSearchChanged;
  final ValueChanged<String?> onSemesterChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      color: c.bgBase,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.sm,
        AppSpacing.edge,
        AppSpacing.md,
      ),
      child: Column(
        children: [
          DebouncedSearchField(
            hint: '搜索课程名 / 课程代码',
            onChanged: onSearchChanged,
          ),
          const SizedBox(height: AppSpacing.sm),
          SizedBox(
            height: 34,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                _FilterChip(
                  label: '全部学期',
                  selected: semester == null,
                  onTap: () => onSemesterChanged(null),
                ),
                const SizedBox(width: AppSpacing.sm),
                // 简化: 演示学期为当前学期
                _FilterChip(
                  label: '本学期',
                  selected: semester != null,
                  onTap: () => onSemesterChanged('current'),
                ),
              ],
            ),
          ),
        ],
      ),
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
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
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

class _CourseList extends StatelessWidget {
  const _CourseList({
    required this.fetchPage,
    required this.onJoinByInviteCode,
    required this.currentUserRole,
  });

  final Future<PaginatedResult<Course>> Function(int, int) fetchPage;
  final VoidCallback onJoinByInviteCode;
  final UserRole? currentUserRole;

  @override
  Widget build(BuildContext context) {
    return PagedListView<Course>(
      fetchPage: fetchPage,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.sm,
        AppSpacing.edge,
        88,
      ),
      separator: const SizedBox(height: AppSpacing.sm + 2),
      emptyIcon: Icons.class_outlined,
      emptyTitle: '还没有加入任何课程',
      emptyMessage: '点击右下角"加入班级"输入邀请码',
      emptyActionLabel: '加入班级',
      onEmptyAction: onJoinByInviteCode,
      itemBuilder: (context, course, index) => StaggeredEnter(
        delay: Duration(milliseconds: (index * 40).clamp(0, 240)),
        child: _CourseCard(course: course),
      ),
    );
  }
}

class _CourseCard extends StatelessWidget {
  const _CourseCard({required this.course});
  final Course course;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final courseColor = Color(course.color);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => context.go('/courses/${course.id}'),
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
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: courseColor.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                ),
                child: Icon(
                  Icons.book_rounded,
                  size: 22,
                  color: courseColor,
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
                      '${course.teacher.name} · ${course.classCount}个班 · ${course.studentCount}人',
                      style: AppTypography.caption.copyWith(
                        color: c.textSecondary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
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
}
