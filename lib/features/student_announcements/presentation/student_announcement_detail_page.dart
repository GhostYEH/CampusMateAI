import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/announcement.dart';

/// 学生通知详情页。
///
/// 功能(AGENTS.md §5.4):
/// - 显示发布教师和班级
/// - 自动发送已读回执(由服务层调用 /api/v1/announcements/{id}/read)
/// - 可同步为个人待办
/// - 可查看 AI 结构化结果(aiSummary / aiExtractedTasks)
/// - 不允许伪造已读状态(由后端 / Mock 服务确认)
class StudentAnnouncementDetailPage extends ConsumerStatefulWidget {
  const StudentAnnouncementDetailPage({
    super.key,
    required this.announcementId,
  });

  final String announcementId;

  @override
  ConsumerState<StudentAnnouncementDetailPage> createState() =>
      _StudentAnnouncementDetailPageState();
}

class _StudentAnnouncementDetailPageState
    extends ConsumerState<StudentAnnouncementDetailPage> {
  Announcement? _announcement;
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
      final svc = ref.read(announcementServiceProvider);
      // getAnnouncement 内部自动标记已读回执
      final ann = await svc.getAnnouncement(widget.announcementId);
      if (!mounted) return;
      setState(() {
        _announcement = ann;
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
        title: const Text('通知详情'),
        backgroundColor: c.bgSurface,
        surfaceTintColor: Colors.transparent,
        foregroundColor: c.textPrimary,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/home');
            }
          },
        ),
        actions: [
          if (_announcement != null)
            IconButton(
              tooltip: '同步到个人待办',
              onPressed: _syncToTodo,
              icon: const Icon(Icons.add_task_outlined),
            ),
          if (_announcement != null)
            IconButton(
              tooltip: '询问 AI 导员',
              onPressed: _askCounselor,
              icon: const Icon(Icons.smart_toy_outlined),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorStateView(
                  message: '加载通知失败',
                  onRetry: _load,
                )
              : _buildBody(),
    );
  }

  Widget _buildBody() {
    final ann = _announcement!;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.sm,
        AppSpacing.edge,
        AppSpacing.xxl,
      ),
      children: [
        StaggeredEnter(
          child: _Header(announcement: ann),
        ),
        const SizedBox(height: AppSpacing.md),
        StaggeredEnter(
          delay: const Duration(milliseconds: 60),
          child: _ContentCard(announcement: ann),
        ),
        if (ann.attachments.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          StaggeredEnter(
            delay: const Duration(milliseconds: 120),
            child: _AttachmentsCard(announcement: ann),
          ),
        ],
        if (ann.aiSummary != null && ann.aiSummary!.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          StaggeredEnter(
            delay: const Duration(milliseconds: 180),
            child: _AiSummaryCard(announcement: ann),
          ),
        ],
        if (ann.aiExtractedTasks.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          StaggeredEnter(
            delay: const Duration(milliseconds: 240),
            child: _AiExtractedTasksCard(
              announcement: ann,
              onSyncTask: _syncExtractedTask,
            ),
          ),
        ],
      ],
    );
  }

  void _syncToTodo() {
    final ann = _announcement;
    if (ann == null) return;
    context.push('/notifications/extract', extra: ann.content);
  }

  void _syncExtractedTask(AnnouncementExtractedTask task) {
    final ann = _announcement;
    if (ann == null) return;
    // 把抽取的任务项作为预填文本,跳到通知整理页确认后保存
    final prefill =
        '${task.title}${task.deadline != null ? '\n截止: ${task.deadline}' : ''}${task.location != null ? '\n地点: ${task.location}' : ''}${task.materials.isNotEmpty ? '\n材料: ${task.materials.join('、')}' : ''}';
    context.push('/notifications/extract', extra: prefill);
  }

  void _askCounselor() {
    final ann = _announcement;
    if (ann == null) return;
    context.go(
      '/counselor',
      extra: {
        'announcement_id': ann.id,
        'course_id': ann.courseId,
        'class_id': ann.classId,
        'context_title': ann.title,
      },
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.announcement});
  final Announcement announcement;

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
          if (announcement.importance.name == 'high')
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: c.danger.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.priority_high, size: 12, color: c.danger),
                  const SizedBox(width: 2),
                  Text(
                    '重要',
                    style: AppTypography.label.copyWith(
                      color: c.danger,
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            ),
          Text(
            announcement.title,
            style: AppTypography.headline.copyWith(color: c.textPrimary),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Icon(
                Icons.person_outline_rounded,
                size: 14,
                color: c.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                announcement.authorName,
                style: AppTypography.caption.copyWith(
                  color: c.textSecondary,
                ),
              ),
              const SizedBox(width: 12),
              Icon(
                Icons.access_time_rounded,
                size: 14,
                color: c.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                _formatDate(announcement.publishedAt),
                style: AppTypography.caption.copyWith(
                  color: c.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Icon(Icons.class_outlined, size: 14, color: c.textTertiary),
              const SizedBox(width: 4),
              Text(
                '${announcement.read ? '已读' : '未读'} · 已读 ${announcement.readCount}/${announcement.totalStudents}',
                style: AppTypography.overline.copyWith(
                  color: c.textTertiary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) =>
      '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
      '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
}

class _ContentCard extends StatelessWidget {
  const _ContentCard({required this.announcement});
  final Announcement announcement;

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
          const Text('通知内容', style: AppTypography.subtitle),
          const SizedBox(height: AppSpacing.sm),
          Text(
            announcement.content,
            style: AppTypography.body.copyWith(
              color: c.textPrimary,
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }
}

class _AttachmentsCard extends StatelessWidget {
  const _AttachmentsCard({required this.announcement});
  final Announcement announcement;

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
          const Text('附件', style: AppTypography.subtitle),
          const SizedBox(height: AppSpacing.sm),
          for (final att in announcement.attachments)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Icon(
                    Icons.attach_file,
                    size: 16,
                    color: c.textSecondary,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      att.name,
                      style: AppTypography.body.copyWith(fontSize: 13),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Text(
                    att.sizeLabel,
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
}

class _AiSummaryCard extends StatelessWidget {
  const _AiSummaryCard({required this.announcement});
  final Announcement announcement;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.primarySubtle,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: c.primary.withValues(alpha: 0.2), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.auto_awesome_rounded, size: 18, color: c.primary),
              const SizedBox(width: 6),
              Text(
                'AI 结构化摘要',
                style: AppTypography.subtitle.copyWith(color: c.primary),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            announcement.aiSummary!,
            style: AppTypography.body.copyWith(color: c.textPrimary),
          ),
        ],
      ),
    );
  }
}

class _AiExtractedTasksCard extends StatelessWidget {
  const _AiExtractedTasksCard({
    required this.announcement,
    required this.onSyncTask,
  });

  final Announcement announcement;
  final ValueChanged<AnnouncementExtractedTask> onSyncTask;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.accentSubtle,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: c.accent.withValues(alpha: 0.25), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.task_alt_rounded, size: 18, color: c.accent),
              const SizedBox(width: 6),
              Text(
                'AI 抽取的任务项',
                style: AppTypography.subtitle.copyWith(color: c.accent),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '点击「同步为待办」可跳转到通知整理页人工确认后保存,不允许直接保存模型生成内容。',
            style: AppTypography.overline.copyWith(
              color: c.textSecondary,
              fontSize: 11,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final task in announcement.aiExtractedTasks) ...[
            _ExtractedTaskItem(task: task, onSync: () => onSyncTask(task)),
            const SizedBox(height: 6),
          ],
        ],
      ),
    );
  }
}

class _ExtractedTaskItem extends StatelessWidget {
  const _ExtractedTaskItem({required this.task, required this.onSync});

  final AnnouncementExtractedTask task;
  final VoidCallback onSync;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: c.bgSurface,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            task.title,
            style: AppTypography.bodyStrong.copyWith(color: c.textPrimary),
          ),
          if (task.deadline != null) ...[
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(
                  Icons.calendar_today_rounded,
                  size: 12,
                  color: c.textTertiary,
                ),
                const SizedBox(width: 3),
                Text(
                  _formatDate(task.deadline!),
                  style: AppTypography.caption.copyWith(
                    color: c.textTertiary,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ],
          if (task.location != null) ...[
            const SizedBox(height: 2),
            Row(
              children: [
                Icon(
                  Icons.place_outlined,
                  size: 12,
                  color: c.textTertiary,
                ),
                const SizedBox(width: 3),
                Text(
                  task.location!,
                  style: AppTypography.caption.copyWith(
                    color: c.textTertiary,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ],
          if (task.materials.isNotEmpty) ...[
            const SizedBox(height: 2),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.inventory_2_outlined,
                  size: 12,
                  color: c.textTertiary,
                ),
                const SizedBox(width: 3),
                Expanded(
                  child: Text(
                    task.materials.join('、'),
                    style: AppTypography.caption.copyWith(
                      color: c.textTertiary,
                      fontSize: 11,
                    ),
                  ),
                ),
              ],
            ),
          ],
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: onSync,
              icon: const Icon(Icons.add_task, size: 16),
              label: const Text('同步为待办', style: TextStyle(fontSize: 12)),
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                minimumSize: const Size(0, 28),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) =>
      '截止 ${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
      '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
}
