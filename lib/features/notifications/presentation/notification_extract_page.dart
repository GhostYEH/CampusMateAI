import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/utils/id_generator.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/notice.dart';
import '../../../data/models/task.dart';
import '../../../data/services/api/api_client.dart';
import '../../../data/services/service_interfaces.dart';
import 'widgets/duplicate_warning_banner.dart';
import 'widgets/extraction_progress.dart';
import 'widgets/extraction_save_button.dart';
import 'widgets/extraction_success_view.dart';
import 'widgets/extraction_warnings_banner.dart';
import 'widgets/extracted_notice_form.dart';
import 'widgets/mock_note_banner.dart';
import 'widgets/multi_task_selector.dart';
import 'widgets/notice_input_panel.dart';
import 'widgets/reminder_section.dart';

/// 通知智能整理页(核心交互流程)。
///
/// 流程: 粘贴/选择样例 → 智能提取(分步反馈) → 人工修正 → 保存为待办 → 返回首页。
///
/// 遵循科学边界(AGENTS.md §3): Mock 提取,结果可手动修正,顶部明确标注。
///
/// 子组件位于 widgets/ 目录,本文件仅负责组合与页面级状态。
class NotificationExtractPage extends ConsumerStatefulWidget {
  const NotificationExtractPage({super.key, this.prefilledText});

  /// 由 AI 导员"根据回答创建待办"跳转时预填的文本。
  /// 用户仍可编辑,不会自动触发抽取 — 必须人工点击"智能提取"。
  final String? prefilledText;

  @override
  ConsumerState<NotificationExtractPage> createState() =>
      _NotificationExtractPageState();
}

class _NotificationExtractPageState
    extends ConsumerState<NotificationExtractPage>
    with SingleTickerProviderStateMixin {
  final _textController = TextEditingController();

  bool _extracting = false;
  final List<ExtractionStep> _completedSteps = [];
  ExtractedNotice? _result;

  /// 多任务抽取结果(当通知包含多个独立任务时)。
  MultiExtractResult? _multiResult;
  int _selectedTaskIndex = 0;

  /// 重复通知检测结果。
  bool _checkingDuplicate = false;
  DuplicateCheckResult? _duplicateResult;
  bool _duplicateDismissed = false;

  /// 提醒设置。
  bool _reminderEnabled = false;
  int _reminderLeadMinutes = 120; // 默认截止前 2 小时

  /// 提取失败的错误信息(null 表示无错误)。
  /// 不清空 [_textController],保留用户输入便于重试。
  String? _extractError;

  // 可编辑表单字段
  final _taskNameCtrl = TextEditingController();
  final _audienceCtrl = TextEditingController();
  final _submitMethodCtrl = TextEditingController();
  final _locationCtrl = TextEditingController();
  final _sourceCtrl = TextEditingController();
  DateTime? _deadline;
  NoticeImportance _importance = NoticeImportance.unknown;
  List<TaskMaterial> _materials = [];

  bool _saving = false;
  bool _saved = false;

  late final AnimationController _successController;
  late final Animation<double> _successScale;

  @override
  void initState() {
    super.initState();
    _successController = AnimationController(
      duration: AppMotion.base,
      vsync: this,
    );
    _successScale = CurvedAnimation(
      parent: _successController,
      curve: AppMotion.gentleSpring,
    );
    // 预填文本 — 不自动触发抽取,等用户主动点击
    if (widget.prefilledText != null && widget.prefilledText!.isNotEmpty) {
      _textController.text = widget.prefilledText!;
    }
  }

  @override
  void dispose() {
    _textController.dispose();
    _taskNameCtrl.dispose();
    _audienceCtrl.dispose();
    _submitMethodCtrl.dispose();
    _locationCtrl.dispose();
    _sourceCtrl.dispose();
    _successController.dispose();
    super.dispose();
  }

  Future<void> _runExtract() async {
    final text = _textController.text.trim();
    if (_extracting || text.isEmpty) return;

    setState(() {
      _extracting = true;
      _completedSteps.clear();
      _result = null;
      _multiResult = null;
      _selectedTaskIndex = 0;
      _duplicateResult = null;
      _duplicateDismissed = false;
      _extractError = null;
    });

    try {
      final service = ref.read(notificationExtractionProvider);
      // 使用多任务抽取(自动判断是否需要拆分)
      final multi = await service.extractMulti(
        text,
        onProgress: (step) {
          if (!mounted) return;
          setState(() => _completedSteps.add(step));
        },
      );
      if (!mounted) return;
      final tasks = multi.tasks;
      if (tasks.isEmpty) {
        // 后端返回空,降级为单任务
        final single = await service.extract(text);
        if (!mounted) return;
        _populateForm(single);
        setState(() {
          _result = single;
          _multiResult = null;
          _extracting = false;
        });
        return;
      }
      _populateForm(tasks.first);
      setState(() {
        _result = tasks.first;
        _multiResult = tasks.length >= 2 ? multi : null;
        _selectedTaskIndex = 0;
        _extracting = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      // 保留用户输入的文本(_textController 不变)
      setState(() {
        _extracting = false;
        _extractError = e.message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _extracting = false;
        _extractError = '提取失败,请重试';
      });
    }
  }

  /// 切换到多任务中的指定任务,重新填充表单。
  void _selectTask(int index) {
    final multi = _multiResult;
    if (multi == null || index < 0 || index >= multi.tasks.length) return;
    final task = multi.tasks[index];
    _populateForm(task);
    setState(() {
      _selectedTaskIndex = index;
      _result = task;
      // 切换任务后重置重复检测
      _duplicateResult = null;
      _duplicateDismissed = false;
    });
  }

  /// 检查当前通知是否与已保存待办重复。
  Future<void> _checkForDuplicates() async {
    if (_checkingDuplicate) return;
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    setState(() => _checkingDuplicate = true);
    try {
      final service = ref.read(notificationExtractionProvider);
      final existingTasks = ref.read(taskListProvider);
      final recentNotices = <RecentNoticeItem>[];
      for (final t in existingTasks) {
        if (t.deleted) continue;
        recentNotices.add(
          RecentNoticeItem(
            noticeId: t.id,
            title: t.title,
            task: t.title,
            sourceName: t.description,
            sourceText: t.description,
            deadline: t.deadline,
          ),
        );
      }
      final result = await service.checkDuplicate(
        content: text,
        sourceName:
            _sourceCtrl.text.trim().isEmpty ? null : _sourceCtrl.text.trim(),
        taskName: _taskNameCtrl.text.trim().isEmpty
            ? null
            : _taskNameCtrl.text.trim(),
        deadline: _deadline,
        recentNotices: recentNotices,
      );
      if (!mounted) return;
      setState(() {
        _duplicateResult = result;
        _checkingDuplicate = false;
      });
    } catch (_) {
      if (!mounted) return;
      // 重复检测失败不阻止保存
      setState(() => _checkingDuplicate = false);
    }
  }

  void _populateForm(ExtractedNotice r) {
    _taskNameCtrl.text = r.taskName;
    _audienceCtrl.text = r.targetAudience ?? '';
    _submitMethodCtrl.text = r.submitMethod ?? '';
    _locationCtrl.text = r.location ?? '';
    _sourceCtrl.text = r.sourceText ?? '';
    _deadline = r.deadline;
    _importance = r.importance;
    _materials = List.of(r.materials);
  }

  Future<void> _pickDeadline() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _deadline ?? now.add(const Duration(days: 7)),
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 3),
      locale: const Locale('zh'),
    );
    if (picked != null && mounted) {
      setState(() => _deadline = picked);
    }
  }

  void _addMaterial() {
    setState(() {
      _materials = [
        ..._materials,
        TaskMaterial(id: IdGenerator.newId('mat'), name: ''),
      ];
    });
  }

  void _removeMaterial(int index) {
    setState(() {
      _materials = List.of(_materials)..removeAt(index);
    });
  }

  void _updateMaterialName(int index, String name) {
    setState(() {
      _materials = List.of(_materials)
        ..[index] = _materials[index].copyWith(name: name);
    });
  }

  Future<void> _save() async {
    if (_saving || _saved) return;
    final taskName = _taskNameCtrl.text.trim();
    if (taskName.isEmpty) {
      _showSnack('请填写任务名称');
      return;
    }

    // 若尚未检查重复,先检查(不阻止保存,仅提示)
    if (_duplicateResult == null && !_duplicateDismissed) {
      await _checkForDuplicates();
      // 若发现重复且用户未忽略,先提示
      if (_duplicateResult?.isDuplicate == true && !_duplicateDismissed) {
        _showSnack('检测到可能重复,请确认后再次点击保存');
        return;
      }
    }

    setState(() => _saving = true);

    // 计算提醒时间
    DateTime? reminderAt;
    if (_reminderEnabled && _deadline != null) {
      reminderAt = _deadline!.subtract(
        Duration(minutes: _reminderLeadMinutes),
      );
      // 若提醒时间已过去,不设置提醒
      if (reminderAt.isBefore(DateTime.now())) {
        reminderAt = null;
      }
    }

    final task = Task(
      id: IdGenerator.newId('task'),
      title: taskName,
      category: TaskCategory.material,
      priority: _importance.weight >= 3
          ? TaskPriority.high
          : (_importance.weight >= 2 ? TaskPriority.medium : TaskPriority.low),
      createdAt: DateTime.now(),
      source: TaskSource.noticeExtraction,
      description:
          _sourceCtrl.text.trim().isEmpty ? null : _sourceCtrl.text.trim(),
      deadline: _deadline,
      materials: _materials.where((m) => m.name.trim().isNotEmpty).toList(),
      location:
          _locationCtrl.text.trim().isEmpty ? null : _locationCtrl.text.trim(),
      reminderEnabled: _reminderEnabled && reminderAt != null,
      reminderAt: reminderAt,
      // ===== 后端 personal_tasks 对齐字段(确保原文可追溯)=====
      // sourceText 保留原通知全文(_textController 为用户粘贴的原文)
      sourceText: _textController.text.trim().isEmpty
          ? null
          : _textController.text.trim(),
      // sourceName 来自表单的"通知来源"字段
      sourceName: _sourceCtrl.text.trim().isEmpty
          ? null
          : _sourceCtrl.text.trim(),
      // targetStudents 来自"面向对象"字段
      targetStudents: _audienceCtrl.text.trim().isEmpty
          ? null
          : _audienceCtrl.text.trim(),
      // submissionMethod 来自"提交方式"字段
      submissionMethod: _submitMethodCtrl.text.trim().isEmpty
          ? null
          : _submitMethodCtrl.text.trim(),
      // reminderMinutes 提前提醒分钟数(对齐后端字段)
      reminderMinutes: (_reminderEnabled && reminderAt != null)
          ? _reminderLeadMinutes
          : null,
    );

    try {
      await ref.read(taskListProvider.notifier).createTask(task);
      if (!mounted) return;
      setState(() {
        _saving = false;
        _saved = true;
      });
      _successController.forward();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.success,
          content: Row(
            children: [
              Icon(
                Icons.check_circle_rounded,
                color: AppColors.onPrimary,
                size: 18,
              ),
              SizedBox(width: 8),
              Text('已保存为待办'),
            ],
          ),
        ),
      );
      await Future.delayed(const Duration(milliseconds: 1200));
      if (!mounted) return;
      context.go('/home');
    } on ApiException catch (e) {
      // 后端真实失败:不静默伪装成功(对齐 Flutter 要求 #8)
      if (!mounted) return;
      setState(() => _saving = false);
      _showSnack('保存失败:${e.message}');
    } catch (_) {
      if (!mounted) return;
      setState(() => _saving = false);
      _showSnack('保存失败,请重试');
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final config = ref.watch(appConfigProvider);
    final isRealBackend = !config.useMockBackend;

    return Scaffold(
      backgroundColor: AppColors.bgBase,
      appBar: AppBar(
        title: const Text('智能整理通知'),
        backgroundColor: AppColors.bgSurface,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0.5,
      ),
      body: SafeArea(
        child: Stack(
          children: [
            ListView(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.edge,
                12,
                AppSpacing.edge,
                96,
              ),
              children: [
                StaggeredEnter(
                  child: MockNoteBanner(isRealBackend: isRealBackend),
                ),
                const SizedBox(height: 12),
                StaggeredEnter(
                  delay: const Duration(milliseconds: 60),
                  child: NoticeInputPanel(
                    controller: _textController,
                    extracting: _extracting,
                    onExtract: _runExtract,
                  ),
                ),
                if (_extracting || _completedSteps.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  StaggeredEnter(
                    delay: const Duration(milliseconds: 60),
                    child: ExtractionProgress(
                      steps: _completedSteps,
                      extracting: _extracting,
                    ),
                  ),
                ],
                if (_extractError != null && !_extracting) ...[
                  const SizedBox(height: 12),
                  StaggeredEnter(
                    delay: const Duration(milliseconds: 60),
                    child: _ExtractionErrorBanner(
                      message: _extractError!,
                      onRetry: _runExtract,
                    ),
                  ),
                ],
                if (_result != null) ...[
                  if (_result!.warnings.isNotEmpty ||
                      _result!.extractorMode == 'rules') ...[
                    const SizedBox(height: 12),
                    StaggeredEnter(
                      delay: const Duration(milliseconds: 60),
                      child: ExtractionWarningsBanner(
                        warnings: _result!.warnings,
                        extractorMode: _result!.extractorMode,
                        confidence: _result!.confidence,
                      ),
                    ),
                  ],
                  if (_multiResult != null &&
                      _multiResult!.tasks.length >= 2) ...[
                    const SizedBox(height: 12),
                    StaggeredEnter(
                      delay: const Duration(milliseconds: 60),
                      child: MultiTaskSelector(
                        result: _multiResult!,
                        selectedIndex: _selectedTaskIndex,
                        onSelect: _selectTask,
                      ),
                    ),
                  ],
                  const SizedBox(height: 12),
                  StaggeredEnter(
                    delay: const Duration(milliseconds: 60),
                    child: ExtractedNoticeForm(
                      taskNameCtrl: _taskNameCtrl,
                      audienceCtrl: _audienceCtrl,
                      submitMethodCtrl: _submitMethodCtrl,
                      locationCtrl: _locationCtrl,
                      sourceCtrl: _sourceCtrl,
                      deadline: _deadline,
                      importance: _importance,
                      materials: _materials,
                      onPickDeadline: _pickDeadline,
                      onImportanceChanged: (v) =>
                          setState(() => _importance = v),
                      onAddMaterial: _addMaterial,
                      onRemoveMaterial: _removeMaterial,
                      onMaterialNameChanged: _updateMaterialName,
                    ),
                  ),
                  const SizedBox(height: 12),
                  StaggeredEnter(
                    delay: const Duration(milliseconds: 80),
                    child: ReminderSection(
                      enabled: _reminderEnabled,
                      leadMinutes: _reminderLeadMinutes,
                      deadline: _deadline,
                      onToggle: (v) => setState(() => _reminderEnabled = v),
                      onLeadChanged: (m) =>
                          setState(() => _reminderLeadMinutes = m),
                    ),
                  ),
                  if (_checkingDuplicate) ...[
                    const SizedBox(height: 12),
                    StaggeredEnter(
                      child: _DuplicateCheckingIndicator(),
                    ),
                  ],
                  if (_duplicateResult?.isDuplicate == true &&
                      !_duplicateDismissed) ...[
                    const SizedBox(height: 12),
                    StaggeredEnter(
                      delay: const Duration(milliseconds: 60),
                      child: DuplicateWarningBanner(
                        result: _duplicateResult!,
                        onDismiss: () => setState(
                          () => _duplicateDismissed = true,
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: 12),
                  StaggeredEnter(
                    delay: const Duration(milliseconds: 120),
                    child: ExtractionSaveButton(
                      saving: _saving,
                      saved: _saved,
                      onSave: _save,
                    ),
                  ),
                ],
              ],
            ),
            if (_saved)
              Positioned.fill(
                child: ExtractionSuccessOverlay(
                  scale: _successScale,
                  taskName: _taskNameCtrl.text,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// 提取失败的内联错误横幅 — 温和不吓人,提供重试入口。
class _ExtractionErrorBanner extends StatelessWidget {
  const _ExtractionErrorBanner({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: AppColors.warningSubtle, width: 0.8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.cloud_off_rounded,
                size: 16,
                color: AppColors.warning,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '无法连接后端服务',
                  style: AppTypography.label.copyWith(
                    fontSize: 12,
                    color: AppColors.warning,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.only(left: 24),
            child: Text(
              message,
              style: AppTypography.caption.copyWith(
                fontSize: 11.5,
                color: AppColors.textSecondary,
                height: 1.4,
              ),
            ),
          ),
          const SizedBox(height: 10),
          Padding(
            padding: const EdgeInsets.only(left: 24),
            child: Row(
              children: [
                _PillButton(
                  label: '重试',
                  icon: Icons.refresh_rounded,
                  isPrimary: true,
                  onTap: onRetry,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PillButton extends StatelessWidget {
  const _PillButton({
    required this.label,
    required this.icon,
    required this.isPrimary,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool isPrimary;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = isPrimary ? AppColors.primary : AppColors.textSecondary;
    final bg = isPrimary ? AppColors.primarySubtle : AppColors.bgSurface;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(AppRadius.xs),
          border: Border.all(color: color, width: 0.6),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 12, color: color),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTypography.label.copyWith(fontSize: 10.5, color: color),
            ),
          ],
        ),
      ),
    );
  }
}

/// 重复检测进行中指示器。
class _DuplicateCheckingIndicator extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.primarySubtle.withValues(alpha: 0.35),
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        children: [
          const SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 1.8,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '正在检测是否与已保存待办重复...',
            style: AppTypography.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
