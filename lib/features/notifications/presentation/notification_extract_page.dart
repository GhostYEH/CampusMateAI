import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/utils/date_utils.dart';
import '../../../core/utils/id_generator.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/notice.dart';
import '../../../data/models/task.dart';
import '../../../data/services/service_interfaces.dart';
import '../../../mock/mock_data/mock_data.dart';

/// 通知智能整理页(核心交互流程)。
///
/// 流程: 粘贴/选择样例 → 智能提取(分步反馈) → 人工修正 → 保存为待办 → 返回首页。
///
/// 遵循科学边界(AGENTS.md §3): Mock 提取,结果可手动修正,顶部明确标注。
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
                const StaggeredEnter(child: _MockNoteBanner()),
                const SizedBox(height: 12),
                StaggeredEnter(
                  delay: const Duration(milliseconds: 60),
                  child: _InputSection(
                    controller: _textController,
                    extracting: _extracting,
                    onExtract: _runExtract,
                  ),
                ),
                if (_extracting || _completedSteps.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  StaggeredEnter(
                    delay: const Duration(milliseconds: 60),
                    child: _StepsCard(
                      steps: _completedSteps,
                      extracting: _extracting,
                    ),
                  ),
                ],
                if (_result != null) ...[
                  const SizedBox(height: 12),
                  StaggeredEnter(
                    delay: const Duration(milliseconds: 60),
                    child: _ResultForm(
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
                    child: _SaveButton(
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
                child: _SuccessOverlay(
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

/// 顶部模拟提取说明横幅(科学边界标注)。
class _MockNoteBanner extends StatelessWidget {
  const _MockNoteBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(
          color: AppColors.warning.withValues(alpha: 0.35),
          width: 0.8,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.info_outline_rounded,
            size: 16,
            color: AppColors.warning,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '模拟提取,结果可手动修正',
              style: AppTypography.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 输入区:多行文本 + 样例芯片 + 智能整理按钮。
class _InputSection extends StatelessWidget {
  const _InputSection({
    required this.controller,
    required this.extracting,
    required this.onExtract,
  });

  final TextEditingController controller;
  final bool extracting;
  final VoidCallback onExtract;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: '粘贴通知',
            subtitle: '将校园通知原文粘贴到下方',
            icon: Icons.content_paste_rounded,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: controller,
            maxLines: 5,
            minLines: 3,
            decoration: _inputDecoration('在此粘贴校园通知原文...'),
          ),
          const SizedBox(height: 12),
          const Text('示例样例', style: AppTypography.label),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (int i = 0; i < MockData.noticeSamples.length; i++)
                _SampleChip(
                  label: '样例 ${i + 1}',
                  onTap: () => controller.text = MockData.noticeSamples[i],
                ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: extracting ? null : onExtract,
              icon: extracting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.onPrimary,
                      ),
                    )
                  : const Icon(Icons.auto_fix_high_rounded, size: 20),
              label: Text(extracting ? '正在提取...' : '智能整理'),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: AppColors.onPrimary,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 示例样例芯片。
class _SampleChip extends StatelessWidget {
  const _SampleChip({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.primarySubtle,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: AppColors.border, width: 0.6),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.flash_on_rounded,
              size: 14,
              color: AppColors.primary,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTypography.label.copyWith(color: AppColors.primary),
            ),
          ],
        ),
      ),
    );
  }
}

/// 分步骤处理过程卡片。
///
/// 每个步骤按 onProgress 回调依次出现并淡入,完成项打勾,进行中项显示 spinner。
class _StepsCard extends StatelessWidget {
  const _StepsCard({required this.steps, required this.extracting});

  final List<ExtractionStep> steps;
  final bool extracting;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (extracting)
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                const Icon(
                  Icons.check_circle_rounded,
                  color: AppColors.success,
                  size: 18,
                ),
              const SizedBox(width: 8),
              Text(
                extracting ? '正在提取...' : '提取完成',
                style: AppTypography.subtitle,
              ),
            ],
          ),
          const SizedBox(height: 12),
          for (int i = 0; i < steps.length; i++)
            StaggeredEnter(
              child: _StepRow(
                label: steps[i].label,
                done: !extracting || i < steps.length - 1,
              ),
            ),
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({required this.label, required this.done});

  final String label;
  final bool done;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          SizedBox(
            width: 18,
            height: 18,
            child: done
                ? const Icon(
                    Icons.check_circle_rounded,
                    color: AppColors.success,
                    size: 18,
                  )
                : const CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: AppTypography.body.copyWith(
                color: done ? AppColors.textPrimary : AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 提取结果可编辑表单。
class _ResultForm extends StatelessWidget {
  const _ResultForm({
    required this.taskNameCtrl,
    required this.audienceCtrl,
    required this.submitMethodCtrl,
    required this.locationCtrl,
    required this.sourceCtrl,
    required this.deadline,
    required this.importance,
    required this.materials,
    required this.onPickDeadline,
    required this.onImportanceChanged,
    required this.onAddMaterial,
    required this.onRemoveMaterial,
    required this.onMaterialNameChanged,
  });

  final TextEditingController taskNameCtrl;
  final TextEditingController audienceCtrl;
  final TextEditingController submitMethodCtrl;
  final TextEditingController locationCtrl;
  final TextEditingController sourceCtrl;
  final DateTime? deadline;
  final NoticeImportance importance;
  final List<TaskMaterial> materials;
  final VoidCallback onPickDeadline;
  final ValueChanged<NoticeImportance> onImportanceChanged;
  final VoidCallback onAddMaterial;
  final ValueChanged<int> onRemoveMaterial;
  final void Function(int index, String name) onMaterialNameChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _TaskInfoCard(
          taskNameCtrl: taskNameCtrl,
          audienceCtrl: audienceCtrl,
          importance: importance,
          deadline: deadline,
          onImportanceChanged: onImportanceChanged,
          onPickDeadline: onPickDeadline,
        ),
        const SizedBox(height: 12),
        _MethodCard(
          submitMethodCtrl: submitMethodCtrl,
          locationCtrl: locationCtrl,
        ),
        const SizedBox(height: 12),
        _MaterialsCard(
          materials: materials,
          onAdd: onAddMaterial,
          onRemove: onRemoveMaterial,
          onNameChanged: onMaterialNameChanged,
        ),
        const SizedBox(height: 12),
        _SourceCard(sourceCtrl: sourceCtrl),
      ],
    );
  }
}

/// 任务信息卡片:任务名称、面向对象、重要程度、截止时间。
class _TaskInfoCard extends StatelessWidget {
  const _TaskInfoCard({
    required this.taskNameCtrl,
    required this.audienceCtrl,
    required this.importance,
    required this.deadline,
    required this.onImportanceChanged,
    required this.onPickDeadline,
  });

  final TextEditingController taskNameCtrl;
  final TextEditingController audienceCtrl;
  final NoticeImportance importance;
  final DateTime? deadline;
  final ValueChanged<NoticeImportance> onImportanceChanged;
  final VoidCallback onPickDeadline;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: '任务信息',
            icon: Icons.task_alt_rounded,
          ),
          const SizedBox(height: 12),
          _LabeledField(
            label: '任务名称',
            controller: taskNameCtrl,
            hint: '请输入任务名称',
            required: true,
          ),
          const SizedBox(height: 10),
          _LabeledField(
            label: '面向对象',
            controller: audienceCtrl,
            hint: '如:2024级、各班级',
          ),
          const SizedBox(height: 10),
          _ImportanceField(
            value: importance,
            onChanged: onImportanceChanged,
          ),
          const SizedBox(height: 10),
          _DeadlineField(deadline: deadline, onTap: onPickDeadline),
        ],
      ),
    );
  }
}

/// 办理方式卡片:提交方式、办理地点。
class _MethodCard extends StatelessWidget {
  const _MethodCard({
    required this.submitMethodCtrl,
    required this.locationCtrl,
  });

  final TextEditingController submitMethodCtrl;
  final TextEditingController locationCtrl;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: '办理方式',
            icon: Icons.place_outlined,
          ),
          const SizedBox(height: 12),
          _LabeledField(
            label: '提交方式',
            controller: submitMethodCtrl,
            hint: '如:纸质版交至办公室、系统提交',
            maxLines: 2,
          ),
          const SizedBox(height: 10),
          _LabeledField(
            label: '办理地点',
            controller: locationCtrl,
            hint: '如:行政楼302',
          ),
        ],
      ),
    );
  }
}

/// 所需材料卡片:可增删的材料列表。
class _MaterialsCard extends StatelessWidget {
  const _MaterialsCard({
    required this.materials,
    required this.onAdd,
    required this.onRemove,
    required this.onNameChanged,
  });

  final List<TaskMaterial> materials;
  final VoidCallback onAdd;
  final ValueChanged<int> onRemove;
  final void Function(int index, String name) onNameChanged;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: '所需材料',
            icon: Icons.inventory_2_outlined,
            actionLabel: '添加',
            onAction: onAdd,
          ),
          const SizedBox(height: 8),
          if (materials.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text(
                '暂无材料,点击"添加"新增',
                style: AppTypography.caption,
              ),
            )
          else
            for (int i = 0; i < materials.length; i++)
              _MaterialRow(
                key: ValueKey(materials[i].id),
                index: i,
                name: materials[i].name,
                onChanged: (v) => onNameChanged(i, v),
                onRemove: () => onRemove(i),
              ),
        ],
      ),
    );
  }
}

/// 原文来源卡片。
class _SourceCard extends StatelessWidget {
  const _SourceCard({required this.sourceCtrl});

  final TextEditingController sourceCtrl;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: '原文来源',
            icon: Icons.article_outlined,
          ),
          const SizedBox(height: 4),
          const Text('保留通知原文,便于核对', style: AppTypography.caption),
          const SizedBox(height: 8),
          TextFormField(
            controller: sourceCtrl,
            maxLines: 5,
            minLines: 3,
            decoration: _inputDecoration('通知原文'),
          ),
        ],
      ),
    );
  }
}

/// 带标签的输入字段。
class _LabeledField extends StatelessWidget {
  const _LabeledField({
    required this.label,
    required this.controller,
    required this.hint,
    this.maxLines = 1,
    this.required = false,
  });

  final String label;
  final TextEditingController controller;
  final String hint;
  final int maxLines;
  final bool required;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label, style: AppTypography.label),
            if (required)
              const Text(
                ' *',
                style: TextStyle(color: AppColors.danger, fontSize: 13),
              ),
          ],
        ),
        const SizedBox(height: 6),
        TextFormField(
          controller: controller,
          maxLines: maxLines,
          decoration: _inputDecoration(hint),
        ),
      ],
    );
  }
}

/// 重要程度下拉选择。
class _ImportanceField extends StatelessWidget {
  const _ImportanceField({required this.value, required this.onChanged});

  final NoticeImportance value;
  final ValueChanged<NoticeImportance> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('重要程度', style: AppTypography.label),
        const SizedBox(height: 6),
        DropdownButtonFormField<NoticeImportance>(
          initialValue: value,
          decoration: _inputDecoration('选择重要程度'),
          items: [
            for (final v in NoticeImportance.values)
              DropdownMenuItem(value: v, child: Text(v.displayName)),
          ],
          onChanged: (v) {
            if (v != null) onChanged(v);
          },
        ),
      ],
    );
  }
}

/// 截止时间行,点击弹出日期选择器。
class _DeadlineField extends StatelessWidget {
  const _DeadlineField({required this.deadline, required this.onTap});

  final DateTime? deadline;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('截止时间', style: AppTypography.label),
        const SizedBox(height: 6),
        InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          child: InputDecorator(
            decoration: _inputDecoration('选择截止时间').copyWith(
              suffixIcon: const Icon(
                Icons.calendar_today_rounded,
                size: 18,
              ),
            ),
            child: Text(
              deadline == null
                  ? '点击选择日期'
                  : AppDateUtils.formatDateFull(deadline!),
              style: AppTypography.body.copyWith(
                color: deadline == null
                    ? AppColors.textTertiary
                    : AppColors.textPrimary,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// 单行材料输入:TextFormField + 删除按钮。
class _MaterialRow extends StatelessWidget {
  const _MaterialRow({
    super.key,
    required this.index,
    required this.name,
    required this.onChanged,
    required this.onRemove,
  });

  final int index;
  final String name;
  final ValueChanged<String> onChanged;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: TextFormField(
              initialValue: name,
              onChanged: onChanged,
              decoration: _inputDecoration('材料 ${index + 1}').copyWith(
                prefixIcon: const Icon(
                  Icons.checklist_outlined,
                  size: 18,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            onPressed: onRemove,
            icon: const Icon(
              Icons.remove_circle_outline_rounded,
              color: AppColors.danger,
              size: 20,
            ),
            style: IconButton.styleFrom(
              backgroundColor: AppColors.dangerSubtle,
            ),
          ),
        ],
      ),
    );
  }
}

/// 保存按钮:多状态(默认 / 保存中 / 已保存),防重复点击。
class _SaveButton extends StatelessWidget {
  const _SaveButton({
    required this.saving,
    required this.saved,
    required this.onSave,
  });

  final bool saving;
  final bool saved;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    final disabled = saving || saved;
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: disabled ? null : onSave,
        icon: saving
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.onPrimary,
                ),
              )
            : Icon(
                saved ? Icons.check_rounded : Icons.save_rounded,
                size: 20,
              ),
        label: Text(
          saving ? '保存中...' : (saved ? '已保存' : '保存为待办'),
        ),
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.success,
          foregroundColor: AppColors.onPrimary,
          disabledBackgroundColor: AppColors.success.withValues(alpha: 0.5),
          disabledForegroundColor: AppColors.onPrimary,
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
      ),
    );
  }
}

/// 保存成功浮层:ScaleTransition + 勾选动画卡片。
class _SuccessOverlay extends StatelessWidget {
  const _SuccessOverlay({required this.scale, required this.taskName});

  final Animation<double> scale;
  final String taskName;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black.withValues(alpha: 0.35),
      alignment: Alignment.center,
      child: ScaleTransition(
        scale: scale,
        child: _SuccessCard(taskName: taskName),
      ),
    );
  }
}

class _SuccessCard extends StatelessWidget {
  const _SuccessCard({required this.taskName});

  final String taskName;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width * 0.72;
    return ConstrainedBox(
      constraints: BoxConstraints(maxWidth: width),
      child: AppCard(
        padding: const EdgeInsets.all(24),
        backgroundColor: AppColors.bgSurface,
        showBorder: false,
        shadow: AppShadows.elevated,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: const BoxDecoration(
                color: AppColors.successSubtle,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.check_rounded,
                color: AppColors.success,
                size: 40,
              ),
            ),
            const SizedBox(height: 16),
            const Text('已保存为待办', style: AppTypography.subtitle),
            const SizedBox(height: 6),
            Text(
              taskName.isEmpty ? '即将返回首页' : '「$taskName」已加入待办',
              style: AppTypography.caption,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

/// 统一输入框样式。
InputDecoration _inputDecoration(String hint) => InputDecoration(
      hintText: hint,
      hintStyle: AppTypography.body.copyWith(color: AppColors.textTertiary),
      filled: true,
      fillColor: AppColors.bgSunken,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 12,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: const BorderSide(color: AppColors.primary, width: 1.2),
      ),
    );
