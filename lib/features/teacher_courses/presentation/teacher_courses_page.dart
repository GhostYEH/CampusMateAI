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

/// 教师课程管理页 — 列出教师开设的课程,支持创建/编辑/查看。
///
/// 功能(AGENTS.md §6.2):
/// - 课程列表(分页 + 搜索)
/// - 创建课程(FAB)
/// - 编辑课程
/// - 点击进入详情页(班级/通知/任务)
class TeacherCoursesPage extends ConsumerStatefulWidget {
  const TeacherCoursesPage({super.key});

  @override
  ConsumerState<TeacherCoursesPage> createState() => _TeacherCoursesPageState();
}

class _TeacherCoursesPageState extends ConsumerState<TeacherCoursesPage> {
  String _search = '';

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final courseSvc = ref.watch(courseServiceProvider);

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
              fetchPage: (page, pageSize) => courseSvc.listCourses(
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
              emptyTitle: '尚未开设课程',
              emptyMessage: '点击右下角"创建课程"开始',
              emptyActionLabel: '创建课程',
              onEmptyAction: _showCreateCourseDialog,
              itemBuilder: (context, course, index) => StaggeredEnter(
                delay: Duration(milliseconds: (index * 40).clamp(0, 240)),
                child: _CourseCard(
                  course: course,
                  onEdit: () => _showEditCourseDialog(course),
                ),
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateCourseDialog,
        icon: const Icon(Icons.add_rounded, size: 22),
        label: const Text('创建课程'),
        backgroundColor: c.primary,
        foregroundColor: c.onPrimary,
      ),
    );
  }

  Future<void> _showCreateCourseDialog() async {
    final result = await showDialog<_CourseFormResult>(
      context: context,
      builder: (_) => const _CourseFormDialog(mode: _CourseFormMode.create),
    );
    if (result == null || !mounted) return;
    final messenger = ScaffoldMessenger.maybeOf(context);
    try {
      final svc = ref.read(courseServiceProvider);
      final course = await svc.createCourse(
        code: result.code,
        name: result.name,
        semesterId: result.semesterId,
        description: result.description,
        creditHours: result.creditHours,
        color: result.color,
      );
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(
          content: Text('已创建课程:${course.name}'),
          duration: const Duration(seconds: 2),
        ),
      );
      setState(() {});
    } catch (e) {
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(
          content: Text('创建失败:$e'),
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }

  Future<void> _showEditCourseDialog(Course course) async {
    final result = await showDialog<_CourseFormResult>(
      context: context,
      builder: (_) =>
          _CourseFormDialog(mode: _CourseFormMode.edit, course: course),
    );
    if (result == null || !mounted) return;
    final messenger = ScaffoldMessenger.maybeOf(context);
    try {
      final svc = ref.read(courseServiceProvider);
      final updated = await svc.updateCourse(
        course.id,
        name: result.name,
        description: result.description,
        creditHours: result.creditHours,
        color: result.color,
      );
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(
          content: Text('已更新:${updated.name}'),
          duration: const Duration(seconds: 2),
        ),
      );
      setState(() {});
    } catch (e) {
      if (!mounted) return;
      messenger?.showSnackBar(
        SnackBar(
          content: Text('更新失败:$e'),
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }
}

/// 课程卡片 — 显示课程基本信息,点击进入详情。
class _CourseCard extends StatelessWidget {
  const _CourseCard({required this.course, required this.onEdit});
  final Course course;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final courseColor = Color(course.color);
    return AppCard(
      onTap: () => context.go('/teacher/courses/${course.id}'),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: courseColor.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                ),
                child: Icon(Icons.book_rounded, size: 22, color: courseColor),
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
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              _CourseStat(
                icon: Icons.groups_2_rounded,
                value: '${course.classCount}',
                label: '班级',
              ),
              const SizedBox(width: AppSpacing.lg),
              _CourseStat(
                icon: Icons.person_outline_rounded,
                value: '${course.studentCount}',
                label: '学生',
              ),
              const Spacer(),
              IconButton(
                onPressed: onEdit,
                icon:
                    Icon(Icons.edit_outlined, size: 18, color: c.textSecondary),
                tooltip: '编辑课程',
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

class _CourseStat extends StatelessWidget {
  const _CourseStat({
    required this.icon,
    required this.value,
    required this.label,
  });

  final IconData icon;
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: c.textTertiary),
        const SizedBox(width: 4),
        Text(
          value,
          style: AppTypography.label.copyWith(
            color: c.textPrimary,
            fontSize: 13,
          ),
        ),
        const SizedBox(width: 3),
        Text(
          label,
          style: AppTypography.label.copyWith(
            color: c.textTertiary,
            fontSize: 11,
          ),
        ),
      ],
    );
  }
}

enum _CourseFormMode { create, edit }

class _CourseFormResult {
  _CourseFormResult({
    required this.code,
    required this.name,
    required this.semesterId,
    required this.description,
    required this.creditHours,
    required this.color,
  });

  final String code;
  final String name;
  final String semesterId;
  final String? description;
  final int creditHours;
  final int color;
}

class _CourseFormDialog extends StatefulWidget {
  const _CourseFormDialog({required this.mode, this.course});

  final _CourseFormMode mode;
  final Course? course;

  @override
  State<_CourseFormDialog> createState() => _CourseFormDialogState();
}

class _CourseFormDialogState extends State<_CourseFormDialog> {
  late final TextEditingController _codeController;
  late final TextEditingController _nameController;
  late final TextEditingController _descController;
  late final TextEditingController _creditsController;
  int _color = 0xFF2F6486;
  bool _submitting = false;

  static const _colorOptions = [
    0xFF2F6486, // 青蓝
    0xFF4E8C6A, // 绿
    0xFFD49A3D, // 琥珀
    0xFFCB645C, // 珊瑚
    0xFF6A7FB8, // 蓝紫
    0xFF5AA9A8, // 青绿
  ];

  @override
  void initState() {
    super.initState();
    final c = widget.course;
    _codeController = TextEditingController(text: c?.code ?? '');
    _nameController = TextEditingController(text: c?.name ?? '');
    _descController = TextEditingController(text: c?.description ?? '');
    _creditsController = TextEditingController(text: '${c?.creditHours ?? 3}');
    if (c != null) _color = c.color;
  }

  @override
  void dispose() {
    _codeController.dispose();
    _nameController.dispose();
    _descController.dispose();
    _creditsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final isCreate = widget.mode == _CourseFormMode.create;
    return AlertDialog(
      title: Text(isCreate ? '创建课程' : '编辑课程'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isCreate)
              TextField(
                controller: _codeController,
                decoration: const InputDecoration(
                  labelText: '课程代码',
                  hintText: '如 CS101',
                  border: OutlineInputBorder(),
                ),
              ),
            if (isCreate) const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _nameController,
              decoration: const InputDecoration(
                labelText: '课程名称',
                hintText: '如 数据结构',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _descController,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: '课程描述(可选)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _creditsController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: '学分',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text('主题色'),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              children: [
                for (final color in _colorOptions)
                  GestureDetector(
                    onTap: () => setState(() => _color = color),
                    child: Container(
                      width: 28,
                      height: 28,
                      decoration: BoxDecoration(
                        color: Color(color),
                        shape: BoxShape.circle,
                        border: _color == color
                            ? Border.all(color: c.textPrimary, width: 3)
                            : null,
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _submitting ? null : () => Navigator.pop(context),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: _submitting ? null : _submit,
          style: FilledButton.styleFrom(
            backgroundColor: c.primary,
            foregroundColor: c.onPrimary,
          ),
          child: Text(_submitting ? '保存中...' : '保存'),
        ),
      ],
    );
  }

  Future<void> _submit() async {
    final code = _codeController.text.trim();
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        const SnackBar(content: Text('请输入课程名称')),
      );
      return;
    }
    if (widget.mode == _CourseFormMode.create && code.isEmpty) {
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        const SnackBar(content: Text('请输入课程代码')),
      );
      return;
    }

    setState(() => _submitting = true);
    final credits = int.tryParse(_creditsController.text.trim()) ?? 3;
    final result = _CourseFormResult(
      code: code,
      name: name,
      semesterId: 'current',
      description: _descController.text.trim().isEmpty
          ? null
          : _descController.text.trim(),
      creditHours: credits,
      color: _color,
    );
    if (!mounted) return;
    Navigator.pop(context, result);
  }
}
