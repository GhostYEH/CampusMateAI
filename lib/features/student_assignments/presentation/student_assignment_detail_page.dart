import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/assignment.dart';
import '../../../data/models/course.dart';

/// 学生任务详情页。
///
/// 功能(AGENTS.md §5.3):
/// - 显示任务详情(教师、课程班级、截止、提交要求、附件、提交状态、重交)
/// - 提交文字 + 上传附件
/// - 保存草稿 / 正式提交 / 修改或重新提交
/// - 同步到个人待办
/// - 设置精确提醒
/// - 向 AI 导员询问此任务(携带 assignment_id 上下文)
///
/// 正式提交前必须二次确认。
class StudentAssignmentDetailPage extends ConsumerStatefulWidget {
  const StudentAssignmentDetailPage({super.key, required this.assignmentId});

  final String assignmentId;

  @override
  ConsumerState<StudentAssignmentDetailPage> createState() =>
      _StudentAssignmentDetailPageState();
}

class _StudentAssignmentDetailPageState
    extends ConsumerState<StudentAssignmentDetailPage> {
  Assignment? _assignment;
  Submission? _mySubmission;
  bool _loading = true;
  Object? _error;
  late final TextEditingController _contentController;
  bool _isSaving = false;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _contentController = TextEditingController();
    _loadAll();
  }

  @override
  void dispose() {
    _contentController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final assignmentSvc = ref.read(assignmentServiceProvider);
      final submissionSvc = ref.read(submissionServiceProvider);
      final assignment = await assignmentSvc.getAssignment(widget.assignmentId);
      final submission =
          await submissionSvc.getMySubmission(widget.assignmentId);
      if (!mounted) return;
      setState(() {
        _assignment = assignment;
        _mySubmission = submission;
        if (submission != null) {
          _contentController.text = submission.content;
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

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Scaffold(
      backgroundColor: c.bgBase,
      appBar: AppBar(
        title: const Text('任务详情'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        foregroundColor: c.textPrimary,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => context.go('/tasks'),
        ),
        actions: [
          if (_assignment != null)
            IconButton(
              tooltip: '向 AI 导员询问',
              onPressed: _askCounselor,
              icon: const Icon(Icons.smart_toy_outlined),
            ),
          PopupMenuButton<String>(
            onSelected: (v) {
              if (v == 'sync_todo') _syncToTodo();
              if (v == 'set_reminder') _setReminder();
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'sync_todo',
                child: ListTile(
                  leading: Icon(Icons.add_task_rounded),
                  title: Text('同步到个人待办'),
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                ),
              ),
              const PopupMenuItem(
                value: 'set_reminder',
                child: ListTile(
                  leading: Icon(Icons.alarm_add_rounded),
                  title: Text('设置精确提醒'),
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                ),
              ),
            ],
          ),
        ],
      ),
      body: _loading
          ? const _Loading()
          : _error != null
              ? ErrorStateView(
                  message: '加载任务失败',
                  onRetry: _loadAll,
                )
              : _buildBody(),
      bottomNavigationBar: _assignment == null ? null : _buildBottomBar(),
    );
  }

  Widget _buildBody() {
    final assignment = _assignment!;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.sm,
        AppSpacing.edge,
        120,
      ),
      children: [
        StaggeredEnter(
          child: _AssignmentHeader(
            assignment: assignment,
            submissionStatus: _mySubmission?.status,
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        StaggeredEnter(
          delay: const Duration(milliseconds: 60),
          child: _DescriptionCard(assignment: assignment),
        ),
        const SizedBox(height: AppSpacing.md),
        StaggeredEnter(
          delay: const Duration(milliseconds: 120),
          child: _AttachmentsCard(
            title: '任务附件',
            attachments: assignment.attachments,
            emptyHint: '本任务无附件',
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        StaggeredEnter(
          delay: const Duration(milliseconds: 180),
          child: _SubmissionCard(
            assignment: assignment,
            submission: _mySubmission,
            contentController: _contentController,
          ),
        ),
        if (_mySubmission?.attachments != null &&
            _mySubmission!.attachments.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          StaggeredEnter(
            delay: const Duration(milliseconds: 240),
            child: _AttachmentsCard(
              title: '已提交附件',
              attachments: _mySubmission!.attachments,
              emptyHint: '',
            ),
          ),
        ],
        if (_mySubmission?.isGraded == true) ...[
          const SizedBox(height: AppSpacing.md),
          StaggeredEnter(
            delay: const Duration(milliseconds: 300),
            child: _GradeCard(
              submission: _mySubmission!,
              maxScore: assignment.maxScore,
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildBottomBar() {
    final assignment = _assignment!;
    final canSubmit = !assignment.isOverdue ||
        (assignment.allowResubmit && _mySubmission != null);
    final hasDraft = _mySubmission?.status == SubmissionStatus.draft;
    final hasSubmitted = _mySubmission?.status == SubmissionStatus.submitted;

    return SafeArea(
      child: Container(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.edge,
          AppSpacing.sm,
          AppSpacing.edge,
          AppSpacing.sm,
        ),
        decoration: BoxDecoration(
          color: context.appColors.bgSurface,
          border: Border(
            top: BorderSide(color: context.appColors.border, width: 0.8),
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _isSaving || _isSubmitting ? null : _saveDraft,
                icon: _isSaving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.save_outlined, size: 20),
                label: const Text('保存草稿'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(AppRadius.md),
                  ),
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.sm + 2),
            Expanded(
              child: FilledButton.icon(
                onPressed: (_isSaving || _isSubmitting || !canSubmit)
                    ? null
                    : (hasSubmitted && !assignment.allowResubmit
                        ? null
                        : _confirmSubmit),
                icon: _isSubmitting
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor:
                              AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : Icon(
                        hasSubmitted
                            ? Icons.refresh_rounded
                            : Icons.check_rounded,
                        size: 20,
                      ),
                label: Text(
                  hasSubmitted
                      ? (assignment.allowResubmit ? '重新提交' : '已提交')
                      : (hasDraft ? '正式提交' : '提交任务'),
                ),
                style: FilledButton.styleFrom(
                  backgroundColor: context.appColors.primary,
                  foregroundColor: context.appColors.onPrimary,
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(AppRadius.md),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ===== 操作 =====

  Future<void> _saveDraft() async {
    final content = _contentController.text.trim();
    if (content.isEmpty) {
      _toast('草稿内容不能为空');
      return;
    }
    setState(() => _isSaving = true);
    try {
      final svc = ref.read(submissionServiceProvider);
      final submission = await svc.saveDraft(
        assignmentId: widget.assignmentId,
        content: content,
        attachments: _mySubmission?.attachments ?? const [],
      );
      if (!mounted) return;
      setState(() {
        _mySubmission = submission;
        _isSaving = false;
      });
      _toast('草稿已保存');
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      _toast('保存失败: $e');
    }
  }

  Future<void> _confirmSubmit() async {
    // 二次确认(AGENTS.md §5.3)
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('确认提交'),
        content: const Text('提交后将无法修改(除非允许重交)。是否确认提交?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('确认提交'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final content = _contentController.text.trim();
    if (content.isEmpty && _assignment!.submissionType != SubmissionType.file) {
      _toast('内容不能为空');
      return;
    }

    setState(() => _isSubmitting = true);
    try {
      final svc = ref.read(submissionServiceProvider);
      final isResubmit = _mySubmission?.status == SubmissionStatus.submitted;
      final submission = isResubmit
          ? await svc.resubmit(
              assignmentId: widget.assignmentId,
              content: content,
              attachments: _mySubmission?.attachments ?? const [],
            )
          : await svc.submit(
              assignmentId: widget.assignmentId,
              content: content,
              attachments: _mySubmission?.attachments ?? const [],
            );
      if (!mounted) return;
      setState(() {
        _mySubmission = submission;
        _isSubmitting = false;
      });
      _toast(isResubmit ? '重新提交成功' : '提交成功');
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);
      _toast('提交失败: $e');
    }
  }

  void _syncToTodo() {
    final assignment = _assignment;
    if (assignment == null) return;
    // 把任务同步到个人待办(复用现有 taskListProvider)
    // 这里简化为 toast + 跳到任务创建页预填
    context.push('/tasks/create', extra: assignment.title);
  }

  void _setReminder() {
    final assignment = _assignment;
    if (assignment == null) return;
    _toast('已为此任务设置精确提醒(模拟)');
  }

  void _askCounselor() {
    final assignment = _assignment;
    if (assignment == null) return;
    // 跳转到 AI 导员,携带 assignment_id 上下文
    context.go(
      '/counselor',
      extra: {
        'assignment_id': assignment.id,
        'course_id': assignment.courseId,
        'class_id': assignment.classId,
        'context_title': assignment.title,
      },
    );
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

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      physics: const NeverScrollableScrollPhysics(),
      itemCount: 6,
      itemBuilder: (context, i) => const Padding(
        padding: EdgeInsets.symmetric(
          horizontal: AppSpacing.edge,
          vertical: AppSpacing.sm + 2,
        ),
        child: Row(
          children: [
            SizedBox(
              width: 28,
              height: 28,
              child: CircularProgressIndicator(strokeWidth: 1.8),
            ),
            SizedBox(width: 12),
            Text('加载中...'),
          ],
        ),
      ),
    );
  }
}

class _AssignmentHeader extends StatelessWidget {
  const _AssignmentHeader({
    required this.assignment,
    required this.submissionStatus,
  });

  final Assignment assignment;
  final SubmissionStatus? submissionStatus;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
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
                  style: AppTypography.headline.copyWith(color: c.textPrimary),
                ),
              ),
              _StatusChip(
                assignment: assignment,
                submissionStatus: submissionStatus,
              ),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            children: [
              _Meta(
                icon: Icons.person_outline_rounded,
                text: assignment.authorName,
              ),
              if (assignment.courseName != null)
                _Meta(
                  icon: Icons.class_outlined,
                  text: assignment.courseName!,
                ),
              if (assignment.className != null)
                _Meta(
                  icon: Icons.group_outlined,
                  text: assignment.className!,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Meta extends StatelessWidget {
  const _Meta({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: c.textSecondary),
        const SizedBox(width: 3),
        Text(
          text,
          style: AppTypography.caption.copyWith(color: c.textSecondary),
        ),
      ],
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.assignment,
    required this.submissionStatus,
  });

  final Assignment assignment;
  final SubmissionStatus? submissionStatus;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final (label, fg, bg) = switch (submissionStatus) {
      SubmissionStatus.submitted => (
          '已提交',
          c.success,
          c.success.withValues(alpha: 0.12)
        ),
      SubmissionStatus.graded => (
          '已评分',
          c.info,
          c.info.withValues(alpha: 0.12)
        ),
      SubmissionStatus.late => (
          '逾期提交',
          c.danger,
          c.danger.withValues(alpha: 0.12)
        ),
      SubmissionStatus.draft => ('草稿', c.textSecondary, c.bgSunken),
      SubmissionStatus.notSubmitted || null => assignment.isOverdue
          ? ('已逾期', c.danger, c.danger.withValues(alpha: 0.12))
          : assignment.isDueSoon
              ? ('即将截止', c.accent, c.accent.withValues(alpha: 0.12))
              : ('待提交', c.textSecondary, c.bgSunken),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
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

class _DescriptionCard extends StatelessWidget {
  const _DescriptionCard({required this.assignment});
  final Assignment assignment;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.bgSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: c.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('任务说明', style: AppTypography.subtitle),
          const SizedBox(height: AppSpacing.sm),
          Text(
            assignment.description.isEmpty ? '无说明' : assignment.description,
            style: AppTypography.body.copyWith(color: c.textPrimary),
          ),
          const SizedBox(height: AppSpacing.md),
          const Divider(),
          const SizedBox(height: AppSpacing.sm),
          _MetaRow(
            label: '截止时间',
            value: _formatDateTime(assignment.deadline),
            color: assignment.isOverdue ? c.danger : c.textPrimary,
          ),
          _MetaRow(
            label: '提交方式',
            value: assignment.submissionType.displayName,
          ),
          _MetaRow(
            label: '允许重交',
            value: assignment.allowResubmit ? '是' : '否',
          ),
          _MetaRow(
            label: '满分',
            value: assignment.maxScore.toStringAsFixed(0),
          ),
        ],
      ),
    );
  }

  String _formatDateTime(DateTime dt) =>
      '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
      '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
}

class _MetaRow extends StatelessWidget {
  const _MetaRow({
    required this.label,
    required this.value,
    this.color,
  });

  final String label;
  final String value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
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
              style: AppTypography.body.copyWith(color: color ?? c.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

class _AttachmentsCard extends StatelessWidget {
  const _AttachmentsCard({
    required this.title,
    required this.attachments,
    required this.emptyHint,
  });

  final String title;
  final List<Attachment> attachments;
  final String emptyHint;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.bgSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: c.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AppTypography.subtitle),
          const SizedBox(height: AppSpacing.sm),
          if (attachments.isEmpty)
            Text(
              emptyHint.isEmpty ? '暂无附件' : emptyHint,
              style: AppTypography.caption.copyWith(color: c.textTertiary),
            )
          else
            for (final att in attachments) _AttachmentTile(attachment: att),
        ],
      ),
    );
  }
}

class _AttachmentTile extends StatelessWidget {
  const _AttachmentTile({required this.attachment});
  final Attachment attachment;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final iconData = _iconFor(attachment.iconKind);
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm + 2,
      ),
      decoration: BoxDecoration(
        color: c.bgSunken,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        children: [
          Icon(iconData, size: 18, color: c.textSecondary),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  attachment.name,
                  style: AppTypography.body.copyWith(
                    color: c.textPrimary,
                    fontSize: 13,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  attachment.sizeLabel,
                  style: AppTypography.overline.copyWith(
                    color: c.textTertiary,
                    fontSize: 10,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  IconData _iconFor(String kind) {
    switch (kind) {
      case 'image':
        return Icons.image_outlined;
      case 'pdf':
        return Icons.picture_as_pdf_outlined;
      case 'doc':
        return Icons.description_outlined;
      case 'sheet':
        return Icons.table_chart_outlined;
      case 'archive':
        return Icons.folder_zip_outlined;
      case 'video':
        return Icons.video_file_outlined;
      case 'audio':
        return Icons.audio_file_outlined;
      default:
        return Icons.insert_drive_file_outlined;
    }
  }
}

class _SubmissionCard extends StatelessWidget {
  const _SubmissionCard({
    required this.assignment,
    required this.submission,
    required this.contentController,
  });

  final Assignment assignment;
  final Submission? submission;
  final TextEditingController contentController;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final allowText = assignment.submissionType == SubmissionType.text ||
        assignment.submissionType == SubmissionType.both;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.bgSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: c.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('我的提交', style: AppTypography.subtitle),
          const SizedBox(height: AppSpacing.sm),
          if (submission != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Icon(
                    Icons.history_rounded,
                    size: 14,
                    color: c.textTertiary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    '上次提交: ${_formatDateTime(submission!.submittedAt)}'
                    '${submission!.isLate ? ' (逾期)' : ''}',
                    style: AppTypography.caption.copyWith(
                      color: c.textTertiary,
                    ),
                  ),
                ],
              ),
            ),
          if (allowText)
            TextField(
              controller: contentController,
              maxLines: 8,
              minLines: 4,
              textInputAction: TextInputAction.newline,
              inputFormatters: [
                LengthLimitingTextInputFormatter(4000),
              ],
              decoration: InputDecoration(
                hintText: '请输入提交内容...',
                filled: true,
                fillColor: c.bgBase,
                contentPadding: const EdgeInsets.all(AppSpacing.md),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                  borderSide: BorderSide(color: c.border, width: 1),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                  borderSide: BorderSide(color: c.primary, width: 1.4),
                ),
              ),
            )
          else
            Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: c.bgSunken,
                borderRadius: BorderRadius.circular(AppRadius.sm),
              ),
              child: Row(
                children: [
                  Icon(Icons.attach_file, size: 18, color: c.textTertiary),
                  const SizedBox(width: 6),
                  Text(
                    '本任务仅支持附件提交',
                    style: AppTypography.caption.copyWith(
                      color: c.textTertiary,
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: AppSpacing.sm),
          // 附件上传按钮(Mock 模式仅展示提示)
          OutlinedButton.icon(
            onPressed: () {
              ScaffoldMessenger.maybeOf(context)?.showSnackBar(
                const SnackBar(
                  content: Text('Mock 模式不支持真实上传,提交时将保留现有附件'),
                  duration: Duration(seconds: 2),
                ),
              );
            },
            icon: const Icon(Icons.attach_file, size: 18),
            label: Text(
              submission?.attachments.isNotEmpty == true
                  ? '附件(${submission!.attachments.length})'
                  : '添加附件',
            ),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm + 2,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(AppRadius.sm),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatDateTime(DateTime dt) =>
      '${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
      '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
}

class _GradeCard extends StatelessWidget {
  const _GradeCard({required this.submission, required this.maxScore});
  final Submission submission;
  final double maxScore;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final grade = submission.grade ?? 0;
    final ratio = (grade / maxScore).clamp(0.0, 1.0);
    final passed = ratio >= 0.6;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.bgSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(
          color: (passed ? c.success : c.danger).withValues(alpha: 0.4),
          width: 1.2,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.workspace_premium_outlined,
                size: 20,
                color: passed ? c.success : c.danger,
              ),
              const SizedBox(width: 6),
              const Text('评分结果', style: AppTypography.subtitle),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                grade.toStringAsFixed(1),
                style: AppTypography.metric.copyWith(
                  color: passed ? c.success : c.danger,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                '/ ${maxScore.toStringAsFixed(0)}',
                style: AppTypography.caption.copyWith(color: c.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: 6,
              backgroundColor: c.bgSunken,
              valueColor: AlwaysStoppedAnimation(
                passed ? c.success : c.danger,
              ),
            ),
          ),
          if (submission.comment != null && submission.comment!.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            const Text('教师评语', style: AppTypography.label),
            const SizedBox(height: 4),
            Text(
              submission.comment!,
              style: AppTypography.body.copyWith(color: c.textPrimary),
            ),
          ],
          if (submission.gradedByName != null) ...[
            const SizedBox(height: 6),
            Text(
              '评分人: ${submission.gradedByName}'
              '${submission.gradedAt != null ? ' · ${_formatDate(submission.gradedAt!)}' : ''}',
              style: AppTypography.overline.copyWith(color: c.textTertiary),
            ),
          ],
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) =>
      '${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
}
