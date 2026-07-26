import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/skeleton_loader.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/course.dart';

/// 教师课程详情页 — 展示课程信息 + 班级列表(管理入口)。
///
/// 功能(AGENTS.md §6.2):
/// - 课程基本信息(代码 / 教师 / 学期 / 描述 / 学分)
/// - 班级列表(点击进入班级详情 — 成员/通知/任务)
/// - 创建班级(底部按钮)
/// - 重置邀请码
class TeacherCourseDetailPage extends ConsumerStatefulWidget {
  const TeacherCourseDetailPage({super.key, required this.courseId});

  final String courseId;

  @override
  ConsumerState<TeacherCourseDetailPage> createState() =>
      _TeacherCourseDetailPageState();
}

class _TeacherCourseDetailPageState
    extends ConsumerState<TeacherCourseDetailPage> {
  Course? _course;
  List<SchoolClass> _classes = [];
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
      if (!mounted) return;
      setState(() {
        _course = course;
        _classes = classes;
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
    return Scaffold(
      backgroundColor: c.bgBase,
      body: _loading
          ? const _Loading()
          : _error != null
              ? ErrorStateView(message: '加载失败', onRetry: _load)
              : CustomScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  slivers: [
                    SliverAppBar(
                      pinned: true,
                      expandedHeight: 156,
                      backgroundColor: c.bgSurface,
                      surfaceTintColor: Colors.transparent,
                      foregroundColor: c.textPrimary,
                      leading: IconButton(
                        icon: const Icon(Icons.arrow_back_rounded),
                        onPressed: () => context.go('/teacher/courses'),
                      ),
                      title: const Text('课程详情'),
                      flexibleSpace: FlexibleSpaceBar(
                        background: _CourseHero(course: _course!),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: StaggeredEnter(
                        child: _CourseInfoCard(course: _course!),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: StaggeredEnter(
                        delay: const Duration(milliseconds: 60),
                        child: _ClassesSection(
                          course: _course!,
                          classes: _classes,
                          onCreateClass: _showCreateClassDialog,
                          onResetInviteCode: _resetInviteCode,
                        ),
                      ),
                    ),
                    const SliverToBoxAdapter(child: SizedBox(height: 24)),
                  ],
                ),
    );
  }

  Future<void> _showCreateClassDialog() async {
    final result = await showDialog<_ClassFormResult>(
      context: context,
      builder: (_) => const _ClassFormDialog(),
    );
    if (result == null || !mounted) return;
    final messenger = ScaffoldMessenger.maybeOf(context);
    try {
      final svc = ref.read(courseServiceProvider);
      final cls = await svc.createClass(
        courseId: widget.courseId,
        name: result.name,
        year: result.year,
        major: result.major,
      );
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(
          content: Text('已创建班级:${cls.name}'),
          duration: const Duration(seconds: 2),
        ),
      );
      _load();
    } catch (e) {
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(content: Text('创建失败:$e')),
      );
    }
  }

  Future<void> _resetInviteCode(SchoolClass cls) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('重置邀请码'),
        content: Text('重置后,原邀请码将失效。班级:${cls.name}'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('重置'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final messenger = ScaffoldMessenger.maybeOf(context);
    try {
      final svc = ref.read(courseServiceProvider);
      final updated = await svc.resetInviteCode(cls.id);
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(
          content: Text('已重置邀请码:${updated.inviteCode}'),
          duration: const Duration(seconds: 3),
        ),
      );
      _load();
    } catch (e) {
      if (!mounted) return;
      messenger?.showSnackBar(SnackBar(content: Text('重置失败:$e')));
    }
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
        SkeletonCard(height: 140),
        SizedBox(height: AppSpacing.lg),
        SkeletonCard(height: 140),
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
        72,
        AppSpacing.edge,
        AppSpacing.md,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: courseColor,
              borderRadius: BorderRadius.circular(AppRadius.xs),
            ),
            child: Text(
              course.code,
              style: AppTypography.label.copyWith(
                color: Colors.white,
                fontSize: 11,
                letterSpacing: 0.5,
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            course.name,
            style: AppTypography.headline.copyWith(color: c.textPrimary),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class _CourseInfoCard extends StatelessWidget {
  const _CourseInfoCard({required this.course});
  final Course course;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.md,
        AppSpacing.edge,
        0,
      ),
      child: AppCard(
        padding: const EdgeInsets.all(AppSpacing.base),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.person_outline_rounded, size: 16, color: c.primary),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    course.teacher.displayName,
                    style: AppTypography.body.copyWith(color: c.textPrimary),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                Icon(Icons.event_outlined, size: 16, color: c.textSecondary),
                const SizedBox(width: 4),
                Text(
                  course.semester.name,
                  style: AppTypography.caption.copyWith(color: c.textSecondary),
                ),
                const SizedBox(width: AppSpacing.md),
                Icon(Icons.school_rounded, size: 16, color: c.textSecondary),
                const SizedBox(width: 4),
                Text(
                  '${course.creditHours} 学分',
                  style: AppTypography.caption.copyWith(color: c.textSecondary),
                ),
              ],
            ),
            if (course.description != null &&
                course.description!.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              Text(
                course.description!,
                style: AppTypography.body.copyWith(color: c.textSecondary),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ClassesSection extends StatelessWidget {
  const _ClassesSection({
    required this.course,
    required this.classes,
    required this.onCreateClass,
    required this.onResetInviteCode,
  });

  final Course course;
  final List<SchoolClass> classes;
  final VoidCallback onCreateClass;
  final void Function(SchoolClass) onResetInviteCode;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.lg,
        AppSpacing.edge,
        0,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.groups_2_rounded, size: 18, color: c.primary),
              const SizedBox(width: 6),
              const Text('班级', style: AppTypography.subtitle),
              const Spacer(),
              TextButton.icon(
                onPressed: onCreateClass,
                icon: const Icon(Icons.add_rounded, size: 18),
                label: const Text('创建'),
                style: TextButton.styleFrom(
                  foregroundColor: c.primary,
                  minimumSize: const Size(0, 32),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm + 2),
          if (classes.isEmpty)
            EmptyStateView(
              icon: Icons.group_outlined,
              title: '还没有班级',
              message: '创建班级后可邀请学生加入',
              actionLabel: '创建班级',
              onAction: onCreateClass,
            )
          else
            Column(
              children: [
                for (int i = 0; i < classes.length; i++) ...[
                  _ClassTile(
                    course: course,
                    cls: classes[i],
                    onResetInviteCode: onResetInviteCode,
                  ),
                  if (i < classes.length - 1)
                    const SizedBox(height: AppSpacing.sm),
                ],
              ],
            ),
        ],
      ),
    );
  }
}

class _ClassTile extends StatelessWidget {
  const _ClassTile({
    required this.course,
    required this.cls,
    required this.onResetInviteCode,
  });

  final Course course;
  final SchoolClass cls;
  final void Function(SchoolClass) onResetInviteCode;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      onTap: () => context.go(
        '/teacher/courses/${course.id}/classes/${cls.id}',
      ),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  cls.name,
                  style: AppTypography.subtitle.copyWith(color: c.textPrimary),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 8,
                  vertical: 2,
                ),
                decoration: BoxDecoration(
                  color: c.bgSunken,
                  borderRadius: BorderRadius.circular(AppRadius.xs),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.vpn_key_outlined,
                      size: 12,
                      color: c.textTertiary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      cls.inviteCode,
                      style: AppTypography.label.copyWith(
                        color: c.textSecondary,
                        fontSize: 11,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              if (cls.year != null) ...[
                _MetaChip(label: cls.year!),
                const SizedBox(width: 6),
              ],
              if (cls.major != null) ...[
                _MetaChip(label: cls.major!),
                const SizedBox(width: 6),
              ],
              _MetaChip(label: '${cls.studentCount} 学生'),
              const Spacer(),
              IconButton(
                onPressed: () => onResetInviteCode(cls),
                icon: Icon(
                  Icons.refresh_rounded,
                  size: 16,
                  color: c.textSecondary,
                ),
                tooltip: '重置邀请码',
                visualDensity: VisualDensity.compact,
              ),
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

class _MetaChip extends StatelessWidget {
  const _MetaChip({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: c.bgSunken,
        borderRadius: BorderRadius.circular(AppRadius.xs),
      ),
      child: Text(
        label,
        style: AppTypography.label.copyWith(
          color: c.textSecondary,
          fontSize: 11,
        ),
      ),
    );
  }
}

class _ClassFormResult {
  _ClassFormResult({
    required this.name,
    this.year,
    this.major,
  });

  final String name;
  final String? year;
  final String? major;
}

class _ClassFormDialog extends StatefulWidget {
  const _ClassFormDialog();

  @override
  State<_ClassFormDialog> createState() => _ClassFormDialogState();
}

class _ClassFormDialogState extends State<_ClassFormDialog> {
  late final TextEditingController _nameController;
  late final TextEditingController _yearController;
  late final TextEditingController _majorController;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController();
    _yearController = TextEditingController();
    _majorController = TextEditingController();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _yearController.dispose();
    _majorController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('创建班级'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _nameController,
            decoration: const InputDecoration(
              labelText: '班级名称',
              hintText: '如 计科2024-1班',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _yearController,
            decoration: const InputDecoration(
              labelText: '年级(可选)',
              hintText: '如 2024级',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _majorController,
            decoration: const InputDecoration(
              labelText: '专业(可选)',
              border: OutlineInputBorder(),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: _submit,
          child: const Text('创建'),
        ),
      ],
    );
  }

  void _submit() {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        const SnackBar(content: Text('请输入班级名称')),
      );
      return;
    }
    Navigator.pop(
      context,
      _ClassFormResult(
        name: name,
        year: _yearController.text.trim().isEmpty
            ? null
            : _yearController.text.trim(),
        major: _majorController.text.trim().isEmpty
            ? null
            : _majorController.text.trim(),
      ),
    );
  }
}
