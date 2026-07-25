import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/notice.dart';
import 'notification_form_styles.dart';

/// 提取结果可编辑表单 — 由任务信息、办理方式、所需材料、原文来源 4 个卡片组成。
///
/// 提取自原 NotificationExtractPage 的 _ResultForm 及相关子组件。
class ExtractedNoticeForm extends StatelessWidget {
  const ExtractedNoticeForm({
    super.key,
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
            decoration: notificationInputDecoration('通知原文'),
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
          decoration: notificationInputDecoration(hint),
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
          decoration: notificationInputDecoration('选择重要程度'),
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
            decoration: notificationInputDecoration('选择截止时间').copyWith(
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
              decoration:
                  notificationInputDecoration('材料 ${index + 1}').copyWith(
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
