import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../app/providers/app_providers.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/state_views.dart';
import '../../../../data/models/models.dart';
import '../../../../data/services/api/api_client.dart';

/// 任务拆解面板 — 输入目标 → 请求拆解 → 展示结构化步骤 → 接受单步转待办。
///
/// 业务流程:
/// 1. 用户输入学习目标(可关联当前选中待办)
/// 2. 调用 [TaskBreakdownService.breakdown] 获取结构化步骤
/// 3. 展示步骤列表(含编号、标题、描述、预计时长、依赖、完成标准)
/// 4. 标注 mode(llm / rule_fallback)与政策步骤(依赖知识库)
/// 5. 用户可"接受"某一步,经确认对话框后转为个人待办子任务
///
/// **科学边界**:
/// - 步骤仅描述可观察、可执行的学习/事务动作
/// - 涉及校园政策的步骤必须依赖知识库(后端校验,标注 is_policy_step)
/// - 不进行心理诊断或情绪判断
class TaskBreakdownPanel extends ConsumerStatefulWidget {
  const TaskBreakdownPanel({
    super.key,
    required this.relatedTasks,
    this.selectedRelatedTaskId,
    this.goalController,
    this.onAcceptStep,
  });

  /// 可关联的待办列表(用于"接受步骤"时挂为子任务)。
  final List<Task> relatedTasks;

  /// 当前选中的关联任务 ID(可空)。
  final String? selectedRelatedTaskId;

  /// 外部共享的目标输入控制器(可选)。若提供则用于预填拆解目标。
  final TextEditingController? goalController;

  /// 接受步骤的回调(返回 true 表示已成功创建待办)。
  /// 若为 null,则使用默认行为(通过 taskListProvider 创建)。
  final Future<bool> Function(
    TaskBreakdownStep step,
    TaskBreakdownResponse resp,
  )? onAcceptStep;

  @override
  ConsumerState<TaskBreakdownPanel> createState() => _TaskBreakdownPanelState();
}

class _TaskBreakdownPanelState extends ConsumerState<TaskBreakdownPanel> {
  final _goalFieldController = TextEditingController();
  bool _loading = false;
  Object? _error;
  TaskBreakdownResponse? _response;
  final Set<int> _acceptedSteps = <int>{};
  final Map<int, String> _stepFeedback = <int, String>{};

  @override
  void dispose() {
    _goalFieldController.dispose();
    super.dispose();
  }

  Future<void> _requestBreakdown() async {
    final goalText = _goalFieldController.text.trim().isEmpty
        ? widget.goalController?.text.trim() ?? ''
        : _goalFieldController.text.trim();
    final taskId = widget.selectedRelatedTaskId;

    if (goalText.isEmpty && (taskId == null || taskId.isEmpty)) {
      setState(() {
        _error = '请输入学习目标或选择关联待办';
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
      _response = null;
      _acceptedSteps.clear();
      _stepFeedback.clear();
    });

    try {
      final service = ref.read(taskBreakdownServiceProvider);
      final resp = await service.breakdown(
        TaskBreakdownRequest(
          taskId: taskId,
          goal: goalText.isEmpty ? null : goalText,
        ),
      );
      if (!mounted) return;
      setState(() {
        _response = resp;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      String msg;
      if (e is ApiException) {
        msg = e.message;
      } else {
        msg = '拆解失败,请稍后重试';
      }
      setState(() {
        _error = msg;
        _loading = false;
      });
    }
  }

  Future<void> _acceptStep(TaskBreakdownStep step) async {
    final resp = _response;
    if (resp == null) return;
    if (_acceptedSteps.contains(step.stepNumber)) return;

    // 显式确认对话框(用户要求"必须明确确认")
    final confirmed = await _showAcceptConfirmDialog(step);
    if (confirmed != true) return;

    setState(() {
      _stepFeedback[step.stepNumber] = '正在创建待办...';
    });

    try {
      bool ok;
      if (widget.onAcceptStep != null) {
        ok = await widget.onAcceptStep!(step, resp);
      } else {
        ok = await _createTaskFromStep(step, resp);
      }
      if (!mounted) return;
      setState(() {
        if (ok) {
          _acceptedSteps.add(step.stepNumber);
          _stepFeedback[step.stepNumber] = '已添加到待办';
        } else {
          _stepFeedback[step.stepNumber] = '创建失败';
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _stepFeedback[step.stepNumber] =
            e is ApiException ? e.message : '创建失败,请稍后重试';
      });
    }
  }

  /// 默认行为:将步骤转为个人待办(标题前缀"【拆解步骤N】",带 deadline 估时)。
  Future<bool> _createTaskFromStep(
    TaskBreakdownStep step,
    TaskBreakdownResponse resp,
  ) async {
    final notifier = ref.read(taskListProvider.notifier);
    final now = DateTime.now();
    final deadline = now.add(Duration(minutes: step.estimatedMinutes));
    final title = '【拆解步骤${step.stepNumber}】${step.title}';
    final description = StringBuffer()
      ..writeln('来源目标:${resp.goal}')
      ..writeln('步骤描述:${step.description}')
      ..writeln('完成标准:${step.completionCriteria}')
      ..writeln('预计耗时:${step.estimatedMinutes} 分钟');
    if (step.dependencies.isNotEmpty) {
      description.writeln('依赖步骤:${step.dependencies.join(", ")}');
    }
    if (step.isPolicyStep) {
      description.writeln('类型:校园政策相关(已依赖知识库)');
      if (step.knowledgeSource != null) {
        description.writeln('参考来源:${step.knowledgeSource}');
      }
    }
    if (resp.relatedTaskId != null) {
      description.writeln('关联任务ID:${resp.relatedTaskId}');
    }
    final task = Task(
      id: 'task_${DateTime.now().millisecondsSinceEpoch}_${step.stepNumber}',
      title: title,
      category: step.isPolicyStep ? TaskCategory.material : TaskCategory.study,
      priority: TaskPriority.medium,
      createdAt: now,
      source: TaskSource.counselor,
      description: description.toString(),
      deadline: deadline,
    );
    await notifier.createTask(task);
    return true;
  }

  Future<bool?> _showAcceptConfirmDialog(TaskBreakdownStep step) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('将此步骤添加到待办?'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '步骤 ${step.stepNumber}: ${step.title}',
                style: AppTypography.subtitle,
              ),
              const SizedBox(height: 8),
              Text(
                '预计耗时: ${step.estimatedMinutes} 分钟',
                style: AppTypography.body,
              ),
              const SizedBox(height: 4),
              Text(
                '截止时间将设为:${_formatDeadline(step.estimatedMinutes)}',
                style: AppTypography.caption,
              ),
              const SizedBox(height: 12),
              Text(
                step.description,
                style: AppTypography.body,
              ),
              const SizedBox(height: 12),
              Text(
                '完成标准:${step.completionCriteria}',
                style: AppTypography.caption,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('添加到待办'),
          ),
        ],
      ),
    );
  }

  String _formatDeadline(int estimatedMinutes) {
    final dl = DateTime.now().add(Duration(minutes: estimatedMinutes));
    return '${dl.month}/${dl.day} ${dl.hour.toString().padLeft(2, "0")}:${dl.minute.toString().padLeft(2, "0")}';
  }

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.account_tree_outlined, size: 18, color: c.primary),
              const SizedBox(width: 6),
              const Text('任务拆解', style: AppTypography.subtitle),
              const Spacer(),
              if (_response != null) _ModeBadge(mode: _response!.mode),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _goalFieldController,
            decoration: const InputDecoration(
              hintText: '输入学习目标,例如:复习高数第三章',
              prefixIcon: Icon(Icons.flag_outlined, size: 20),
              isDense: true,
            ),
            maxLines: 2,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _loading ? null : _requestBreakdown(),
          ),
          if (widget.selectedRelatedTaskId != null) ...[
            const SizedBox(height: 8),
            Text(
              '将结合当前关联待办进行拆解',
              style: AppTypography.caption.copyWith(color: c.primary),
            ),
          ],
          const SizedBox(height: 10),
          FilledButton.tonalIcon(
            onPressed: _loading ? null : _requestBreakdown,
            icon: _loading
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.auto_awesome_outlined, size: 18),
            label: Text(_loading ? '拆解中...' : '请求拆解'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            ErrorStateView(
              message: _error!.toString(),
              onRetry: _requestBreakdown,
            ),
          ],
          if (_response != null) ...[
            const SizedBox(height: 12),
            _BreakdownResultView(
              response: _response!,
              acceptedSteps: _acceptedSteps,
              feedback: _stepFeedback,
              onAccept: _acceptStep,
            ),
          ],
        ],
      ),
    );
  }
}

/// 拆解模式徽章 — 区分 LLM / 规则降级。
class _ModeBadge extends StatelessWidget {
  const _ModeBadge({required this.mode});

  final TaskBreakdownMode mode;

  @override
  Widget build(BuildContext context) {
    final isLlm = mode == TaskBreakdownMode.llm;
    final color = isLlm ? AppColors.primary : AppColors.warning;
    final bg = isLlm ? AppColors.primarySubtle : AppColors.warningSubtle;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        mode.displayName,
        style: AppTypography.overline.copyWith(color: color),
      ),
    );
  }
}

/// 拆解结果视图 — 步骤列表 + 警告 + 总时长。
class _BreakdownResultView extends StatelessWidget {
  const _BreakdownResultView({
    required this.response,
    required this.acceptedSteps,
    required this.feedback,
    required this.onAccept,
  });

  final TaskBreakdownResponse response;
  final Set<int> acceptedSteps;
  final Map<int, String> feedback;
  final Future<void> Function(TaskBreakdownStep step) onAccept;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (response.warnings.isNotEmpty) ...[
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.warningSubtle,
              borderRadius: BorderRadius.circular(8),
              border:
                  Border.all(color: AppColors.warning.withValues(alpha: 0.4)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(
                      Icons.info_outline,
                      size: 14,
                      color: AppColors.warning,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '提示',
                      style: AppTypography.label
                          .copyWith(color: AppColors.warning),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                ...response.warnings.map(
                  (w) => Text('· $w', style: AppTypography.caption),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
        ],
        Row(
          children: [
            Text('共 ${response.steps.length} 步', style: AppTypography.label),
            const SizedBox(width: 12),
            Text(
              '预计总时长 ${_formatTotalMinutes(response.totalEstimatedMinutes)}',
              style: AppTypography.label.copyWith(color: c.primary),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ...response.steps.map(
          (s) => _StepCard(
            step: s,
            accepted: acceptedSteps.contains(s.stepNumber),
            feedback: feedback[s.stepNumber],
            onAccept: () => onAccept(s),
          ),
        ),
      ],
    );
  }

  String _formatTotalMinutes(int minutes) {
    if (minutes < 60) return '$minutes 分钟';
    final h = minutes ~/ 60;
    final m = minutes % 60;
    return m == 0 ? '$h 小时' : '$h 小时 $m 分钟';
  }
}

/// 单个拆解步骤卡片。
class _StepCard extends StatelessWidget {
  const _StepCard({
    required this.step,
    required this.accepted,
    required this.feedback,
    required this.onAccept,
  });

  final TaskBreakdownStep step;
  final bool accepted;
  final String? feedback;
  final VoidCallback onAccept;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: step.isPolicyStep ? AppColors.accentContainer : c.bgElevated,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: step.isPolicyStep
              ? AppColors.accent.withValues(alpha: 0.4)
              : c.border,
          width: 0.8,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: step.isPolicyStep ? AppColors.accent : c.primary,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Text(
                  '${step.stepNumber}',
                  style: AppTypography.label.copyWith(color: Colors.white),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(step.title, style: AppTypography.subtitle),
                    const SizedBox(height: 2),
                    Text(
                      '预计 ${step.estimatedMinutes} 分钟'
                      '${step.dependencies.isNotEmpty ? " · 依赖步骤 ${step.dependencies.join(",")}" : ""}',
                      style: AppTypography.caption,
                    ),
                  ],
                ),
              ),
              if (step.isPolicyStep)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.accent,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    '政策',
                    style: AppTypography.overline.copyWith(color: Colors.white),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(step.description, style: AppTypography.body),
          const SizedBox(height: 6),
          Text(
            '完成标准:${step.completionCriteria}',
            style: AppTypography.caption.copyWith(color: c.textSecondary),
          ),
          if (step.knowledgeSource != null) ...[
            const SizedBox(height: 4),
            Text(
              '参考来源:${step.knowledgeSource}',
              style: AppTypography.caption.copyWith(color: c.primary),
            ),
          ],
          const SizedBox(height: 8),
          if (feedback != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Text(
                feedback!,
                style: AppTypography.caption.copyWith(
                  color: accepted ? AppColors.success : AppColors.danger,
                ),
              ),
            ),
          SizedBox(
            width: double.infinity,
            child: accepted
                ? OutlinedButton.icon(
                    onPressed: null,
                    icon: const Icon(Icons.check, size: 16),
                    label: const Text('已添加到待办'),
                  )
                : FilledButton.tonalIcon(
                    onPressed: onAccept,
                    icon: const Icon(Icons.add, size: 16),
                    label: const Text('添加为待办'),
                  ),
          ),
        ],
      ),
    );
  }
}
