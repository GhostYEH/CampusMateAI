import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/utils/date_utils.dart';
import '../../../core/utils/id_generator.dart';
import '../../../core/widgets/app_card.dart';
import '../../../data/models/models.dart';
import '../../notifications/presentation/widgets/reminder_permission_banner.dart';

/// 新建待办页面 — 表单驱动,支持校验、加载态与防重复提交。
class TaskCreatePage extends ConsumerStatefulWidget {
  const TaskCreatePage({super.key});

  @override
  ConsumerState<TaskCreatePage> createState() => _TaskCreatePageState();
}

class _TaskCreatePageState extends ConsumerState<TaskCreatePage> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _descriptionController = TextEditingController();
  final TextEditingController _locationController = TextEditingController();
  final List<TextEditingController> _materialControllers = [];

  TaskCategory _category = TaskCategory.study;
  TaskPriority _priority = TaskPriority.medium;
  DateTime? _deadline;
  bool _reminderEnabled = false;
  int _reminderLeadMinutes = 15;
  bool _saving = false;

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    _locationController.dispose();
    for (final c in _materialControllers) {
      c.dispose();
    }
    super.dispose();
  }

  void _addMaterial() {
    setState(() {
      _materialControllers.add(TextEditingController());
    });
  }

  void _removeMaterial(int index) {
    setState(() {
      _materialControllers[index].dispose();
      _materialControllers.removeAt(index);
    });
  }

  Future<void> _pickDeadline() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: _deadline ?? now,
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 5),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_deadline ?? now),
    );
    if (time == null || !mounted) return;
    setState(() {
      _deadline = DateTime(
        date.year,
        date.month,
        date.day,
        time.hour,
        time.minute,
      );
    });
  }

  Future<void> _save() async {
    if (_saving) return;
    final form = _formKey.currentState;
    if (form == null || !form.validate()) return;
    setState(() => _saving = true);

    final materials = _materialControllers
        .where((c) => c.text.trim().isNotEmpty)
        .map(
          (c) => TaskMaterial(
            id: IdGenerator.newId('mat'),
            name: c.text.trim(),
          ),
        )
        .toList();

    final task = Task(
      id: IdGenerator.newId('task'),
      title: _titleController.text.trim(),
      category: _category,
      priority: _priority,
      createdAt: DateTime.now(),
      source: TaskSource.manual,
      description: _descriptionController.text.trim().isEmpty
          ? null
          : _descriptionController.text.trim(),
      deadline: _deadline,
      location: _locationController.text.trim().isEmpty
          ? null
          : _locationController.text.trim(),
      materials: materials,
      reminderEnabled: _reminderEnabled,
      reminderAt: _reminderEnabled && _deadline != null
          ? _deadline!.subtract(Duration(minutes: _reminderLeadMinutes))
          : null,
    );

    try {
      await ref.read(taskListProvider.notifier).createTask(task);
      if (!mounted) return;
      // 检查提醒调度结果 — 失败时仍保存任务,但单独提示提醒部分
      // (不虚报"提醒已设置" — Android 精确提醒完整闭环要求)
      final scheduleResult =
          ref.read(taskListProvider.notifier).lastScheduleResult;
      final reminderFeedback =
          ReminderScheduleFeedback.messageFor(scheduleResult);
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor:
              reminderFeedback == null ? AppColors.success : AppColors.warning,
          content: Row(
            children: [
              Icon(
                reminderFeedback == null
                    ? Icons.check_circle_rounded
                    : Icons.info_outline_rounded,
                color: AppColors.onPrimary,
                size: 18,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(reminderFeedback ?? '已添加待办'),
              ),
            ],
          ),
        ),
      );
      context.go('/tasks');
    } catch (_) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('保存失败,请重试')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('新建待办')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.edge),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _basicInfoSection(),
                const SizedBox(height: 16),
                _scheduleSection(),
                const SizedBox(height: 16),
                _materialsSection(),
                const SizedBox(height: 16),
                _reminderSection(),
                const SizedBox(height: 24),
                _saveButton(),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _basicInfoSection() {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('基本信息', style: AppTypography.subtitle),
          const SizedBox(height: 12),
          TextFormField(
            controller: _titleController,
            decoration: const InputDecoration(
              labelText: '任务标题 *',
              hintText: '例如:完成数据结构实验报告',
            ),
            textInputAction: TextInputAction.next,
            validator: (v) {
              if (v == null || v.trim().isEmpty) return '请输入任务标题';
              return null;
            },
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _descriptionController,
            decoration: const InputDecoration(
              labelText: '描述(可选)',
              hintText: '补充说明、注意事项等',
            ),
            maxLines: 3,
            minLines: 2,
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<TaskCategory>(
                  initialValue: _category,
                  decoration: const InputDecoration(labelText: '类别'),
                  items: TaskCategory.values
                      .map(
                        (c) => DropdownMenuItem(
                          value: c,
                          child: Text(c.displayName),
                        ),
                      )
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => _category = v);
                  },
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: DropdownButtonFormField<TaskPriority>(
                  initialValue: _priority,
                  decoration: const InputDecoration(labelText: '优先级'),
                  items: TaskPriority.values
                      .map(
                        (p) => DropdownMenuItem(
                          value: p,
                          child: Text(p.displayName),
                        ),
                      )
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => _priority = v);
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _scheduleSection() {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('时间与地点', style: AppTypography.subtitle),
          const SizedBox(height: 12),
          InkWell(
            onTap: _pickDeadline,
            borderRadius: BorderRadius.circular(AppRadius.md),
            child: InputDecorator(
              decoration: InputDecoration(
                labelText: '截止时间',
                suffixIcon: _deadline != null
                    ? IconButton(
                        icon: const Icon(Icons.close_rounded, size: 18),
                        onPressed: () => setState(() => _deadline = null),
                      )
                    : const Icon(Icons.event_rounded, size: 20),
              ),
              child: Text(
                _deadline != null
                    ? '${AppDateUtils.formatDate(_deadline!)} '
                        '${AppDateUtils.formatTime(_deadline!)}'
                    : '点击选择日期与时间',
                style: _deadline != null
                    ? AppTypography.body
                    : AppTypography.body
                        .copyWith(color: AppColors.textTertiary),
              ),
            ),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _locationController,
            decoration: const InputDecoration(
              labelText: '地点(可选)',
              hintText: '例如:教学楼B302',
              prefixIcon: Icon(Icons.place_outlined, size: 20),
            ),
            textInputAction: TextInputAction.done,
          ),
        ],
      ),
    );
  }

  Widget _materialsSection() {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.inventory_2_outlined,
                size: 18,
                color: AppColors.primary,
              ),
              const SizedBox(width: 6),
              const Text('材料清单', style: AppTypography.subtitle),
              const Spacer(),
              Text(
                '${_materialControllers.length} 项',
                style: AppTypography.caption,
              ),
            ],
          ),
          const SizedBox(height: 12),
          for (var i = 0; i < _materialControllers.length; i++)
            Padding(
              key: ValueKey(_materialControllers[i]),
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _materialControllers[i],
                      decoration: InputDecoration(
                        hintText: '材料 ${i + 1} 名称',
                        isDense: true,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(
                      Icons.remove_circle_outline_rounded,
                      size: 20,
                    ),
                    color: AppColors.danger,
                    onPressed: () => _removeMaterial(i),
                  ),
                ],
              ),
            ),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: _addMaterial,
              icon: const Icon(Icons.add_rounded, size: 18),
              label: const Text('添加材料'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _reminderSection() {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.notifications_active_outlined,
                size: 18,
                color: AppColors.primary,
              ),
              const SizedBox(width: 6),
              const Expanded(
                child: Text('截止提醒', style: AppTypography.subtitle),
              ),
              Switch(
                value: _reminderEnabled,
                onChanged: (v) => setState(() => _reminderEnabled = v),
              ),
            ],
          ),
          // 权限引导横幅 — 始终展示,提前告知用户权限状态
          const ReminderPermissionBanner(compact: true),
          if (_reminderEnabled) ...[
            const SizedBox(height: 8),
            DropdownButtonFormField<int>(
              initialValue: _reminderLeadMinutes,
              decoration: const InputDecoration(
                labelText: '提前提醒时间',
                prefixIcon: Icon(Icons.schedule_rounded, size: 20),
              ),
              items: const [
                DropdownMenuItem(value: 5, child: Text('提前 5 分钟')),
                DropdownMenuItem(value: 10, child: Text('提前 10 分钟')),
                DropdownMenuItem(value: 15, child: Text('提前 15 分钟')),
                DropdownMenuItem(value: 30, child: Text('提前 30 分钟')),
                DropdownMenuItem(value: 60, child: Text('提前 1 小时')),
                DropdownMenuItem(value: 1440, child: Text('提前 1 天')),
              ],
              onChanged: (v) {
                if (v != null) setState(() => _reminderLeadMinutes = v);
              },
            ),
            if (_deadline == null) ...[
              const SizedBox(height: 8),
              Text(
                '提示:未设置截止时间,提醒将无法生效',
                style: AppTypography.caption.copyWith(
                  color: AppColors.warning,
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _saveButton() {
    return SizedBox(
      width: double.infinity,
      child: FilledButton(
        onPressed: _saving ? null : _save,
        style: FilledButton.styleFrom(
          disabledBackgroundColor: AppColors.primaryHover,
          disabledForegroundColor: AppColors.onPrimary,
        ),
        child: _saving
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2.2,
                  color: AppColors.onPrimary,
                ),
              )
            : const Text('保存'),
      ),
    );
  }
}
