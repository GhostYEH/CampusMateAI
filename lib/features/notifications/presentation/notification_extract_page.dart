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
import '../../../data/services/service_interfaces.dart';
import 'widgets/extraction_progress.dart';
import 'widgets/extraction_save_button.dart';
import 'widgets/extraction_success_view.dart';
import 'widgets/extracted_notice_form.dart';
import 'widgets/mock_note_banner.dart';
import 'widgets/notice_input_panel.dart';

/// 通知智能整理页(核心交互流程)。
///
/// 流程: 粘贴/选择样例 → 智能提取(分步反馈) → 人工修正 → 保存为待办 → 返回首页。
///
/// 遵循科学边界(AGENTS.md §3): Mock 提取,结果可手动修正,顶部明确标注。
///
/// 子组件位于 widgets/ 目录,本文件仅负责组合与页面级状态。
class NotificationExtractPage extends ConsumerStatefulWidget {
  const NotificationExtractPage({super.key});

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
    });

    try {
      final service = ref.read(notificationExtractionProvider);
      final extracted = await service.extract(
        text,
        onProgress: (step) {
          if (!mounted) return;
          setState(() => _completedSteps.add(step));
        },
      );
      if (!mounted) return;
      _populateForm(extracted);
      setState(() {
        _result = extracted;
        _extracting = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _extracting = false);
      _showSnack('提取失败,请重试');
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

    setState(() => _saving = true);

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
                const StaggeredEnter(child: MockNoteBanner()),
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
                if (_result != null) ...[
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
