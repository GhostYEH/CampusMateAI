import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/state_views.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/assignment.dart';
import '../../../data/models/course.dart';
import '../../../data/models/notice.dart';
import '../../../data/services/service_interfaces.dart';

/// 教师发布中心 — 双入口:发布通知 / 发布任务。
///
/// 功能(AGENTS.md §6.3):
/// - 手动填写
/// - 粘贴长通知 → 调用 AI 抽取 → 自动预填标题/截止/材料/地点
/// - 多任务拆分建议
/// - 人工确认后发布(AI 结果不能未经确认直接发布)
/// - 保存草稿
/// - 选择一个或多个班级
class TeacherPublishCenterPage extends ConsumerStatefulWidget {
  const TeacherPublishCenterPage({super.key});

  @override
  ConsumerState<TeacherPublishCenterPage> createState() =>
      _TeacherPublishCenterPageState();
}

class _TeacherPublishCenterPageState
    extends ConsumerState<TeacherPublishCenterPage>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  List<Course> _courses = [];
  bool _loadingCourses = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadCourses();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadCourses() async {
    try {
      final svc = ref.read(courseServiceProvider);
      final result = await svc.listCourses();
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

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('发布中心'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        bottom: TabBar(
          controller: _tabController,
          labelColor: c.primary,
          unselectedLabelColor: c.textSecondary,
          indicatorColor: c.primary,
          indicatorSize: TabBarIndicatorSize.label,
          tabs: const [
            Tab(icon: Icon(Icons.campaign_outlined), text: '发布通知'),
            Tab(icon: Icon(Icons.assignment_outlined), text: '发布任务'),
          ],
        ),
      ),
      body: _loadingCourses
          ? const LoadingView(label: '加载课程...')
          : _courses.isEmpty
              ? EmptyStateView(
                  icon: Icons.class_outlined,
                  title: '尚未开设课程',
                  message: '请先在课程页创建课程',
                  actionLabel: '去创建',
                  onAction: () => context.go('/teacher/courses'),
                )
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _PublishAnnouncementTab(courses: _courses),
                    _PublishAssignmentTab(courses: _courses),
                  ],
                ),
    );
  }
}

// ============================================================
// 发布通知 Tab
// ============================================================

class _PublishAnnouncementTab extends ConsumerStatefulWidget {
  const _PublishAnnouncementTab({required this.courses});
  final List<Course> courses;

  @override
  ConsumerState<_PublishAnnouncementTab> createState() =>
      _PublishAnnouncementTabState();
}

class _PublishAnnouncementTabState
    extends ConsumerState<_PublishAnnouncementTab> {
  String? _courseId;
  List<SchoolClass> _classes = [];
  final Set<String> _selectedClassIds = {};
  bool _loadingClasses = false;

  final _titleController = TextEditingController();
  final _contentController = TextEditingController();
  final _rawNoticeController = TextEditingController();
  NoticeImportance _importance = NoticeImportance.normal;

  bool _extracting = false;
  MultiExtractResult? _extractResult;
  int _activeTaskIndex = 0;

  bool _publishing = false;

  @override
  void initState() {
    super.initState();
    if (widget.courses.isNotEmpty) {
      _courseId = widget.courses.first.id;
      _loadClasses();
    }
  }

  @override
  void dispose() {
    _titleController.dispose();
    _contentController.dispose();
    _rawNoticeController.dispose();
    super.dispose();
  }

  Future<void> _loadClasses() async {
    if (_courseId == null) return;
    setState(() => _loadingClasses = true);
    try {
      final svc = ref.read(courseServiceProvider);
      final classes = await svc.listClasses(_courseId!);
      if (!mounted) return;
      setState(() {
        _classes = classes;
        _selectedClassIds.clear();
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
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.edge),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ===== 选择课程与班级 =====
          StaggeredEnter(
            child: AppCard(
              padding: const EdgeInsets.all(AppSpacing.base),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const _SectionLabel(icon: Icons.class_rounded, text: '发布到'),
                  const SizedBox(height: AppSpacing.sm),
                  DropdownButtonFormField<String>(
                    initialValue: _courseId,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                    ),
                    items: widget.courses
                        .map(
                          (c) => DropdownMenuItem(
                            value: c.id,
                            child: Text('${c.code} · ${c.name}'),
                          ),
                        )
                        .toList(),
                    onChanged: (v) {
                      setState(() => _courseId = v);
                      _loadClasses();
                    },
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Text(
                    '选择班级(可多选)',
                    style: AppTypography.label.copyWith(color: c.textSecondary),
                  ),
                  const SizedBox(height: 6),
                  if (_loadingClasses)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 8),
                      child: LoadingView(),
                    )
                  else if (_classes.isEmpty)
                    Text(
                      '当前课程暂无班级',
                      style:
                          AppTypography.caption.copyWith(color: c.textTertiary),
                    )
                  else
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        for (final cls in _classes)
                          FilterChip(
                            label: Text(cls.name),
                            selected: _selectedClassIds.contains(cls.id),
                            onSelected: (selected) {
                              setState(() {
                                if (selected) {
                                  _selectedClassIds.add(cls.id);
                                } else {
                                  _selectedClassIds.remove(cls.id);
                                }
                              });
                            },
                            selectedColor: c.primary,
                            labelStyle: AppTypography.label.copyWith(
                              color: _selectedClassIds.contains(cls.id)
                                  ? c.onPrimary
                                  : c.textSecondary,
                            ),
                            backgroundColor: c.bgSurface,
                            side: BorderSide(color: c.border),
                          ),
                      ],
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ===== AI 抽取区 =====
          StaggeredEnter(
            delay: const Duration(milliseconds: 60),
            child: AppCard(
              padding: const EdgeInsets.all(AppSpacing.base),
              borderColor: c.accent.withValues(alpha: 0.3),
              backgroundColor: c.accentContainer.withValues(alpha: 0.25),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.auto_fix_high_rounded,
                        size: 16,
                        color: c.accent,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'AI 智能预填',
                        style: AppTypography.subtitle.copyWith(color: c.accent),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    '粘贴长通知文本,AI 自动抽取标题、截止时间、材料和地点,人工确认后填入。',
                    style:
                        AppTypography.caption.copyWith(color: c.textSecondary),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    controller: _rawNoticeController,
                    maxLines: 4,
                    decoration: InputDecoration(
                      hintText: '在此粘贴通知原文...',
                      border: const OutlineInputBorder(),
                      filled: true,
                      fillColor: c.bgSurface,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Row(
                    children: [
                      OutlinedButton.icon(
                        onPressed: _extracting ? null : _runExtract,
                        icon: _extracting
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.bolt_rounded, size: 16),
                        label: Text(_extracting ? '抽取中...' : 'AI 抽取'),
                      ),
                      const Spacer(),
                      if (_extractResult != null)
                        TextButton.icon(
                          onPressed: () {
                            setState(() {
                              _extractResult = null;
                              _rawNoticeController.clear();
                            });
                          },
                          icon: const Icon(Icons.clear, size: 16),
                          label: const Text('清除'),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ===== AI 抽取结果(可编辑确认) =====
          if (_extractResult != null) ...[
            StaggeredEnter(
              delay: const Duration(milliseconds: 120),
              child: _ExtractedResultCard(
                result: _extractResult!,
                activeIndex: _activeTaskIndex,
                onIndexChanged: (i) => setState(() => _activeTaskIndex = i),
                onApply: _applyExtracted,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
          ],

          // ===== 手动填写表单 =====
          StaggeredEnter(
            delay: const Duration(milliseconds: 180),
            child: AppCard(
              padding: const EdgeInsets.all(AppSpacing.base),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const _SectionLabel(
                    icon: Icons.edit_note_rounded,
                    text: '通知内容',
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  TextField(
                    controller: _titleController,
                    decoration: const InputDecoration(
                      labelText: '通知标题',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    controller: _contentController,
                    maxLines: 6,
                    decoration: const InputDecoration(
                      labelText: '通知正文',
                      alignLabelWithHint: true,
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  _ImportanceSelector(
                    value: _importance,
                    onChanged: (v) => setState(() => _importance = v),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ===== 底部操作 =====
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _publishing ? null : _saveDraft,
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: const Text('保存草稿'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    foregroundColor: c.textSecondary,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                flex: 2,
                child: FilledButton.icon(
                  onPressed: _publishing ? null : _publish,
                  icon: _publishing
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.send_rounded, size: 18),
                  label: Text(_publishing ? '发布中...' : '发布'),
                  style: FilledButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    backgroundColor: c.primary,
                    foregroundColor: c.onPrimary,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _runExtract() async {
    final raw = _rawNoticeController.text.trim();
    if (raw.isEmpty) {
      _toast('请先粘贴通知原文');
      return;
    }
    setState(() => _extracting = true);
    try {
      final svc = ref.read(notificationExtractionProvider);
      final result = await svc.extractMulti(raw);
      if (!mounted) return;
      setState(() {
        _extractResult = result;
        _activeTaskIndex = 0;
        _extracting = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _extracting = false);
      _toast('AI 抽取失败,请手动填写或重试');
    }
  }

  void _applyExtracted(ExtractedNotice task) {
    setState(() {
      if (_titleController.text.isEmpty) {
        _titleController.text = task.taskName;
      }
      if (_contentController.text.isEmpty) {
        _contentController.text = _rawNoticeController.text;
      }
      if (task.importance != NoticeImportance.unknown) {
        _importance = task.importance;
      }
    });
    _toast('已应用 AI 抽取结果到表单,请确认后发布');
  }

  Future<void> _saveDraft() async {
    if (!_validateSelection()) return;
    if (_titleController.text.trim().isEmpty) {
      _toast('请输入通知标题');
      return;
    }
    final draft = AnnouncementDraft(
      classIds: _selectedClassIds.toList(),
      courseId: _courseId!,
      title: _titleController.text.trim(),
      content: _contentController.text.trim(),
      importance: _importance,
      isDraft: true,
      useAiPrefill: _extractResult != null,
      rawNoticeText: _rawNoticeController.text.trim().isEmpty
          ? null
          : _rawNoticeController.text.trim(),
    );
    try {
      final svc = ref.read(announcementServiceProvider);
      await svc.saveAnnouncementDraft(draft);
      if (!mounted) return;
      _toast('草稿已保存');
    } catch (e) {
      if (!mounted) return;
      _toast('保存失败:$e');
    }
  }

  Future<void> _publish() async {
    if (!_validateSelection()) return;
    if (_titleController.text.trim().isEmpty) {
      _toast('请输入通知标题');
      return;
    }
    if (_contentController.text.trim().isEmpty) {
      _toast('请输入通知正文');
      return;
    }
    // 二次确认
    final confirmed = await _confirmPublish();
    if (confirmed != true) return;

    setState(() => _publishing = true);
    final draft = AnnouncementDraft(
      classIds: _selectedClassIds.toList(),
      courseId: _courseId!,
      title: _titleController.text.trim(),
      content: _contentController.text.trim(),
      importance: _importance,
      isDraft: false,
      useAiPrefill: _extractResult != null,
      rawNoticeText: _rawNoticeController.text.trim().isEmpty
          ? null
          : _rawNoticeController.text.trim(),
    );
    try {
      final svc = ref.read(announcementServiceProvider);
      await svc.publishAnnouncement(draft);
      if (!mounted) return;
      _toast('已发布到 ${_selectedClassIds.length} 个班级');
      _reset();
    } catch (e) {
      if (!mounted) return;
      _toast('发布失败:$e');
    } finally {
      if (mounted) setState(() => _publishing = false);
    }
  }

  bool _validateSelection() {
    if (_courseId == null) {
      _toast('请选择课程');
      return false;
    }
    if (_selectedClassIds.isEmpty) {
      _toast('请至少选择一个班级');
      return false;
    }
    return true;
  }

  Future<bool?> _confirmPublish() {
    return showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('确认发布'),
        content: Text(
          '将通知发布到 ${_selectedClassIds.length} 个班级?\n标题:${_titleController.text.trim()}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认发布'),
          ),
        ],
      ),
    );
  }

  void _reset() {
    _titleController.clear();
    _contentController.clear();
    _rawNoticeController.clear();
    setState(() {
      _extractResult = null;
      _importance = NoticeImportance.normal;
    });
  }

  void _toast(String msg) {
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      SnackBar(
        content: Text(msg),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}

class _ExtractedResultCard extends StatelessWidget {
  const _ExtractedResultCard({
    required this.result,
    required this.activeIndex,
    required this.onIndexChanged,
    required this.onApply,
  });

  final MultiExtractResult result;
  final int activeIndex;
  final ValueChanged<int> onIndexChanged;
  final void Function(ExtractedNotice) onApply;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final task = result.tasks[activeIndex.clamp(0, result.tasks.length - 1)];
    return AppCard(
      borderColor: c.accent.withValues(alpha: 0.4),
      backgroundColor: c.accentContainer.withValues(alpha: 0.3),
      padding: const EdgeInsets.all(AppSpacing.base),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.checklist_rounded, size: 16, color: c.accent),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'AI 抽取结果(${result.tasks.length} 个任务)',
                  style: AppTypography.subtitle.copyWith(color: c.accent),
                ),
              ),
              if (result.needsUserConfirmation)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                    color: c.warningSubtle,
                    borderRadius: BorderRadius.circular(AppRadius.xs),
                  ),
                  child: Text(
                    '需确认',
                    style: AppTypography.label.copyWith(
                      color: c.warning,
                      fontSize: 10,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            result.splitReason,
            style: AppTypography.caption.copyWith(color: c.textSecondary),
          ),
          if (result.tasks.length > 1) ...[
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: 6,
              children: [
                for (int i = 0; i < result.tasks.length; i++)
                  GestureDetector(
                    onTap: () => onIndexChanged(i),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: i == activeIndex ? c.accent : c.bgSurface,
                        borderRadius: BorderRadius.circular(AppRadius.xs),
                        border: Border.all(
                          color: c.accent.withValues(alpha: 0.4),
                        ),
                      ),
                      child: Text(
                        '任务 ${i + 1}',
                        style: AppTypography.label.copyWith(
                          color: i == activeIndex ? Colors.white : c.accent,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          _ExtractedField(label: '任务名称', value: task.taskName),
          if (task.deadline != null)
            _ExtractedField(
              label: '截止时间',
              value: _formatDeadline(task.deadline!),
            ),
          if (task.location != null)
            _ExtractedField(label: '办理地点', value: task.location!),
          if (task.submitMethod != null)
            _ExtractedField(label: '提交方式', value: task.submitMethod!),
          if (task.materials.isNotEmpty)
            _ExtractedField(
              label: '所需材料',
              value: task.materials.map((m) => m.name).join('、'),
            ),
          if (task.warnings.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Container(
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(
                color: c.warningSubtle,
                borderRadius: BorderRadius.circular(AppRadius.xs),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final w in task.warnings)
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          Icons.info_outline_rounded,
                          size: 12,
                          color: c.warning,
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            w,
                            style: AppTypography.caption
                                .copyWith(color: c.warning),
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.icon(
              onPressed: () => onApply(task),
              icon: const Icon(Icons.check_rounded, size: 16),
              label: const Text('应用到表单'),
              style: FilledButton.styleFrom(
                backgroundColor: c.accent,
                foregroundColor: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }

  static String _formatDeadline(DateTime t) {
    return '${t.year}/${t.month}/${t.day} ${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }
}

class _ExtractedField extends StatelessWidget {
  const _ExtractedField({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 64,
            child: Text(
              label,
              style: AppTypography.label.copyWith(
                color: c.textTertiary,
                fontSize: 11,
              ),
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              value,
              style: AppTypography.body.copyWith(color: c.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

class _ImportanceSelector extends StatelessWidget {
  const _ImportanceSelector({
    required this.value,
    required this.onChanged,
  });

  final NoticeImportance value;
  final ValueChanged<NoticeImportance> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '重要程度',
          style: AppTypography.label.copyWith(color: c.textSecondary),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          children: [
            for (final imp in [
              NoticeImportance.normal,
              NoticeImportance.important,
              NoticeImportance.urgent,
            ])
              ChoiceChip(
                label: Text(imp.displayName),
                selected: value == imp,
                onSelected: (_) => onChanged(imp),
                selectedColor: imp == NoticeImportance.urgent
                    ? c.danger
                    : imp == NoticeImportance.important
                        ? c.warning
                        : c.primary,
                labelStyle: AppTypography.label.copyWith(
                  color: value == imp ? Colors.white : c.textSecondary,
                ),
                backgroundColor: c.bgSurface,
                side: BorderSide(color: c.border),
              ),
          ],
        ),
      ],
    );
  }
}

// ============================================================
// 发布任务 Tab
// ============================================================

class _PublishAssignmentTab extends ConsumerStatefulWidget {
  const _PublishAssignmentTab({required this.courses});
  final List<Course> courses;

  @override
  ConsumerState<_PublishAssignmentTab> createState() =>
      _PublishAssignmentTabState();
}

class _PublishAssignmentTabState extends ConsumerState<_PublishAssignmentTab> {
  String? _courseId;
  List<SchoolClass> _classes = [];
  String? _selectedClassId;

  final _titleController = TextEditingController();
  final _descController = TextEditingController();
  DateTime? _deadline;
  SubmissionType _submissionType = SubmissionType.text;
  bool _allowResubmit = true;
  double _maxScore = 100;
  bool _hasReminder = true;
  int _reminderLeadMinutes = 60;

  final _rawNoticeController = TextEditingController();
  bool _extracting = false;
  MultiExtractResult? _extractResult;
  int _activeTaskIndex = 0;
  bool _publishing = false;

  @override
  void initState() {
    super.initState();
    if (widget.courses.isNotEmpty) {
      _courseId = widget.courses.first.id;
      _loadClasses();
    }
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descController.dispose();
    _rawNoticeController.dispose();
    super.dispose();
  }

  Future<void> _loadClasses() async {
    if (_courseId == null) return;
    try {
      final svc = ref.read(courseServiceProvider);
      final classes = await svc.listClasses(_courseId!);
      if (!mounted) return;
      setState(() {
        _classes = classes;
        _selectedClassId = classes.isNotEmpty ? classes.first.id : null;
      });
    } catch (_) {
      if (!mounted) return;
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.edge),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ===== 选择课程与班级 =====
          StaggeredEnter(
            child: AppCard(
              padding: const EdgeInsets.all(AppSpacing.base),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const _SectionLabel(icon: Icons.class_rounded, text: '发布到'),
                  const SizedBox(height: AppSpacing.sm),
                  DropdownButtonFormField<String>(
                    initialValue: _courseId,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                    ),
                    items: widget.courses
                        .map(
                          (c) => DropdownMenuItem(
                            value: c.id,
                            child: Text('${c.code} · ${c.name}'),
                          ),
                        )
                        .toList(),
                    onChanged: (v) {
                      setState(() => _courseId = v);
                      _loadClasses();
                    },
                  ),
                  const SizedBox(height: AppSpacing.md),
                  DropdownButtonFormField<String>(
                    initialValue: _selectedClassId,
                    decoration: const InputDecoration(
                      labelText: '选择班级',
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                    ),
                    items: _classes
                        .map(
                          (c) => DropdownMenuItem(
                            value: c.id,
                            child: Text(c.name),
                          ),
                        )
                        .toList(),
                    onChanged: (v) => setState(() => _selectedClassId = v),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ===== AI 抽取区(可选) =====
          StaggeredEnter(
            delay: const Duration(milliseconds: 60),
            child: AppCard(
              padding: const EdgeInsets.all(AppSpacing.base),
              borderColor: c.accent.withValues(alpha: 0.3),
              backgroundColor: c.accentContainer.withValues(alpha: 0.25),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.auto_fix_high_rounded,
                        size: 16,
                        color: c.accent,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'AI 智能预填(可选)',
                        style: AppTypography.subtitle.copyWith(color: c.accent),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  TextField(
                    controller: _rawNoticeController,
                    maxLines: 3,
                    decoration: InputDecoration(
                      hintText: '粘贴通知原文,AI 自动抽取标题与截止时间...',
                      border: const OutlineInputBorder(),
                      filled: true,
                      fillColor: c.bgSurface,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  OutlinedButton.icon(
                    onPressed: _extracting ? null : _runExtract,
                    icon: _extracting
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.bolt_rounded, size: 16),
                    label: Text(_extracting ? '抽取中...' : 'AI 抽取并预填'),
                  ),
                ],
              ),
            ),
          ),
          if (_extractResult != null) ...[
            const SizedBox(height: AppSpacing.lg),
            StaggeredEnter(
              delay: const Duration(milliseconds: 120),
              child: _ExtractedResultCard(
                result: _extractResult!,
                activeIndex: _activeTaskIndex,
                onIndexChanged: (i) => setState(() => _activeTaskIndex = i),
                onApply: _applyExtracted,
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.lg),

          // ===== 任务表单 =====
          StaggeredEnter(
            delay: const Duration(milliseconds: 180),
            child: AppCard(
              padding: const EdgeInsets.all(AppSpacing.base),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const _SectionLabel(
                    icon: Icons.assignment_outlined,
                    text: '任务详情',
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  TextField(
                    controller: _titleController,
                    decoration: const InputDecoration(
                      labelText: '任务标题',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    controller: _descController,
                    maxLines: 5,
                    decoration: const InputDecoration(
                      labelText: '任务描述',
                      alignLabelWithHint: true,
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  // 截止时间
                  _DeadlineField(
                    deadline: _deadline,
                    onChanged: (v) => setState(() => _deadline = v),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  // 提交类型
                  _SubmissionTypeField(
                    value: _submissionType,
                    onChanged: (v) => setState(() => _submissionType = v),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  // 满分
                  TextField(
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: '满分分值',
                      border: OutlineInputBorder(),
                    ),
                    controller: TextEditingController(
                      text: _maxScore.toStringAsFixed(0),
                    ),
                    onChanged: (v) {
                      final d = double.tryParse(v);
                      if (d != null) _maxScore = d;
                    },
                  ),
                  const SizedBox(height: AppSpacing.md),
                  // 重交开关
                  SwitchListTile(
                    value: _allowResubmit,
                    onChanged: (v) => setState(() => _allowResubmit = v),
                    title: const Text('允许重新提交'),
                    subtitle: Text(
                      _allowResubmit ? '学生可重新提交多次' : '只能提交一次',
                      style: AppTypography.caption
                          .copyWith(color: c.textSecondary),
                    ),
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                  ),
                  const Divider(),
                  SwitchListTile(
                    value: _hasReminder,
                    onChanged: (v) => setState(() => _hasReminder = v),
                    title: const Text('截止前提醒学生'),
                    subtitle: Text(
                      _hasReminder
                          ? '截止前 $_reminderLeadMinutes 分钟自动提醒'
                          : '不发送提醒',
                      style: AppTypography.caption
                          .copyWith(color: c.textSecondary),
                    ),
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                  ),
                  if (_hasReminder) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Row(
                      children: [
                        Expanded(
                          child: Slider(
                            value: _reminderLeadMinutes.toDouble(),
                            min: 15,
                            max: 1440,
                            divisions: 10,
                            label: _formatLeadMinutes(_reminderLeadMinutes),
                            onChanged: (v) => setState(
                              () => _reminderLeadMinutes = v.round(),
                            ),
                          ),
                        ),
                        Text(
                          _formatLeadMinutes(_reminderLeadMinutes),
                          style: AppTypography.label,
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          // ===== 底部操作 =====
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _publishing ? null : _saveDraft,
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: const Text('保存草稿'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    foregroundColor: c.textSecondary,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                flex: 2,
                child: FilledButton.icon(
                  onPressed: _publishing ? null : _publish,
                  icon: _publishing
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.send_rounded, size: 18),
                  label: Text(_publishing ? '发布中...' : '发布'),
                  style: FilledButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    backgroundColor: c.primary,
                    foregroundColor: c.onPrimary,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _runExtract() async {
    final raw = _rawNoticeController.text.trim();
    if (raw.isEmpty) {
      _toast('请先粘贴通知原文');
      return;
    }
    setState(() => _extracting = true);
    try {
      final svc = ref.read(notificationExtractionProvider);
      final result = await svc.extractMulti(raw);
      if (!mounted) return;
      setState(() {
        _extractResult = result;
        _activeTaskIndex = 0;
        _extracting = false;
      });
      // 自动应用到表单
      if (result.tasks.isNotEmpty) {
        _applyExtracted(result.tasks.first);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() => _extracting = false);
      _toast('AI 抽取失败,请手动填写或重试');
    }
  }

  void _applyExtracted(ExtractedNotice task) {
    setState(() {
      if (_titleController.text.isEmpty) {
        _titleController.text = task.taskName;
      }
      if (_descController.text.isEmpty) {
        _descController.text = task.sourceText ?? _rawNoticeController.text;
      }
      if (_deadline == null && task.deadline != null) {
        _deadline = task.deadline;
      }
      if (task.submitMethod != null) {
        final m = task.submitMethod!.toLowerCase();
        if (m.contains('附件') || m.contains('文件')) {
          _submissionType = SubmissionType.file;
        } else if (m.contains('文字') || m.contains('文本')) {
          _submissionType = SubmissionType.text;
        }
      }
    });
    _toast('已应用 AI 抽取结果,请确认后发布');
  }

  Future<void> _saveDraft() async {
    if (!_validate()) return;
    final draft = AssignmentDraft(
      classId: _selectedClassId!,
      courseId: _courseId!,
      title: _titleController.text.trim(),
      description: _descController.text.trim(),
      deadline: _deadline!,
      submissionType: _submissionType,
      allowResubmit: _allowResubmit,
      maxScore: _maxScore,
      reminderLeadMinutes: _reminderLeadMinutes,
      hasReminder: _hasReminder,
      isDraft: true,
    );
    try {
      final svc = ref.read(assignmentServiceProvider);
      await svc.saveAssignmentDraft(draft);
      if (!mounted) return;
      _toast('草稿已保存');
    } catch (e) {
      if (!mounted) return;
      _toast('保存失败:$e');
    }
  }

  Future<void> _publish() async {
    if (!_validate()) return;
    final confirmed = await _confirmPublish();
    if (confirmed != true) return;

    setState(() => _publishing = true);
    final draft = AssignmentDraft(
      classId: _selectedClassId!,
      courseId: _courseId!,
      title: _titleController.text.trim(),
      description: _descController.text.trim(),
      deadline: _deadline!,
      submissionType: _submissionType,
      allowResubmit: _allowResubmit,
      maxScore: _maxScore,
      reminderLeadMinutes: _reminderLeadMinutes,
      hasReminder: _hasReminder,
      isDraft: false,
    );
    try {
      final svc = ref.read(assignmentServiceProvider);
      await svc.publishAssignment(draft);
      if (!mounted) return;
      _toast('任务已发布');
      _reset();
    } catch (e) {
      if (!mounted) return;
      _toast('发布失败:$e');
    } finally {
      if (mounted) setState(() => _publishing = false);
    }
  }

  bool _validate() {
    if (_courseId == null) {
      _toast('请选择课程');
      return false;
    }
    if (_selectedClassId == null) {
      _toast('请选择班级');
      return false;
    }
    if (_titleController.text.trim().isEmpty) {
      _toast('请输入任务标题');
      return false;
    }
    if (_deadline == null) {
      _toast('请选择截止时间');
      return false;
    }
    return true;
  }

  Future<bool?> _confirmPublish() {
    return showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('确认发布任务'),
        content: Text(
          '将任务发布到所选班级?\n标题:${_titleController.text.trim()}\n截止:${_formatDeadline(_deadline!)}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认发布'),
          ),
        ],
      ),
    );
  }

  void _reset() {
    _titleController.clear();
    _descController.clear();
    _rawNoticeController.clear();
    setState(() {
      _extractResult = null;
      _deadline = null;
      _submissionType = SubmissionType.text;
      _allowResubmit = true;
      _maxScore = 100;
    });
  }

  void _toast(String msg) {
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      SnackBar(
        content: Text(msg),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  static String _formatDeadline(DateTime t) {
    return '${t.year}/${t.month}/${t.day} ${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }

  static String _formatLeadMinutes(int minutes) {
    if (minutes < 60) return '$minutes 分钟';
    if (minutes < 1440) return '${(minutes / 60).round()} 小时';
    return '${(minutes / 1440).round()} 天';
  }
}

class _DeadlineField extends StatelessWidget {
  const _DeadlineField({required this.deadline, required this.onChanged});
  final DateTime? deadline;
  final ValueChanged<DateTime> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return InkWell(
      onTap: () async {
        final now = DateTime.now();
        final date = await showDatePicker(
          context: context,
          initialDate: deadline ?? now.add(const Duration(days: 7)),
          firstDate: now,
          lastDate: now.add(const Duration(days: 365)),
        );
        if (date == null) return;
        if (!context.mounted) return;
        final time = await showTimePicker(
          context: context,
          initialTime: TimeOfDay.fromDateTime(
            deadline ?? now.add(const Duration(hours: 12)),
          ),
        );
        if (time == null) return;
        onChanged(
          DateTime(date.year, date.month, date.day, time.hour, time.minute),
        );
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: '截止时间',
          border: const OutlineInputBorder(),
          suffixIcon: Icon(Icons.event_outlined, color: c.textSecondary),
        ),
        child: Text(
          deadline == null
              ? '请选择截止时间'
              : '${deadline!.year}/${deadline!.month}/${deadline!.day} ${deadline!.hour.toString().padLeft(2, '0')}:${deadline!.minute.toString().padLeft(2, '0')}',
          style: AppTypography.body.copyWith(
            color: deadline == null ? c.textTertiary : c.textPrimary,
          ),
        ),
      ),
    );
  }
}

class _SubmissionTypeField extends StatelessWidget {
  const _SubmissionTypeField({
    required this.value,
    required this.onChanged,
  });

  final SubmissionType value;
  final ValueChanged<SubmissionType> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '提交方式',
          style: AppTypography.label.copyWith(color: c.textSecondary),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          children: [
            for (final t in SubmissionType.values)
              ChoiceChip(
                label: Text(t.displayName),
                selected: value == t,
                onSelected: (_) => onChanged(t),
                selectedColor: c.primary,
                labelStyle: AppTypography.label.copyWith(
                  color: value == t ? Colors.white : c.textSecondary,
                ),
                backgroundColor: c.bgSurface,
                side: BorderSide(color: c.border),
              ),
          ],
        ),
      ],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      children: [
        Icon(icon, size: 16, color: c.primary),
        const SizedBox(width: 6),
        Text(text, style: AppTypography.subtitle),
      ],
    );
  }
}
