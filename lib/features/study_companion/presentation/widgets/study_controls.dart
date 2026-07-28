import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/models.dart';

/// 学习控制按钮组 — 开始 / 暂停 / 继续 / 结束 / 再来一次。
///
/// 状态机:
/// - 未开始: 显示"本次目标"输入 + 关联待办选择 + 开始按钮
/// - 暂停: 显示"继续" + "结束"
/// - 已完成: 显示完成图标 + "再来一次"
/// - 专注中: 显示"暂停" + "结束"
///
/// 关联待办选择仅显示前 [kMaxRelatedTaskOptions] 项,避免下拉过长。
class StudyControls extends StatelessWidget {
  const StudyControls({
    super.key,
    required this.isStudying,
    required this.state,
    required this.goalController,
    required this.onStart,
    required this.onPause,
    required this.onResume,
    required this.onEnd,
    this.relatedTasks = const [],
    this.selectedRelatedTaskId,
    this.onRelatedTaskChanged,
    this.canStart = true,
  });

  final bool isStudying;
  final StudyState state;
  final TextEditingController goalController;
  final VoidCallback onStart;
  final VoidCallback onPause;
  final VoidCallback onResume;
  final VoidCallback onEnd;

  /// 可关联的待办列表(未完成且未删除)。
  final List<Task> relatedTasks;

  /// 当前选中的关联任务 ID(可空表示不关联)。
  final String? selectedRelatedTaskId;

  /// 关联任务切换回调。
  final ValueChanged<String?>? onRelatedTaskChanged;

  /// 是否允许开始(可用于在恢复未结束会话时禁用开始按钮)。
  final bool canStart;

  static const int kMaxRelatedTaskOptions = 8;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!isStudying && state != StudyState.completed) ...[
            const Text('本次目标', style: AppTypography.label),
            const SizedBox(height: 6),
            TextField(
              controller: goalController,
              decoration: const InputDecoration(
                hintText: '例如:复习高数第三章',
                prefixIcon: Icon(Icons.flag_outlined, size: 20),
              ),
              maxLines: 2,
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 12),
            if (relatedTasks.isNotEmpty) ...[
              const Text('关联待办(可选)', style: AppTypography.label),
              const SizedBox(height: 6),
              DropdownButtonFormField<String?>(
                initialValue: selectedRelatedTaskId,
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.link_outlined, size: 20),
                  isDense: true,
                ),
                items: [
                  const DropdownMenuItem<String?>(
                    value: null,
                    child: Text('不关联', style: AppTypography.body),
                  ),
                  ...relatedTasks.take(kMaxRelatedTaskOptions).map(
                        (t) => DropdownMenuItem<String?>(
                          value: t.id,
                          child: Text(
                            t.title,
                            style: AppTypography.body,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                ],
                onChanged: onRelatedTaskChanged,
              ),
              const SizedBox(height: 14),
            ] else ...[
              const SizedBox(height: 4),
            ],
            FilledButton.icon(
              onPressed: canStart ? onStart : null,
              icon: const Icon(Icons.play_arrow_rounded),
              label: const Text('开始学习'),
            ),
          ] else if (state == StudyState.paused) ...[
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onResume,
                    icon: const Icon(Icons.play_arrow_rounded),
                    label: const Text('继续'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: onEnd,
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.danger,
                    ),
                    icon: const Icon(Icons.stop_rounded),
                    label: const Text('结束'),
                  ),
                ),
              ],
            ),
          ] else if (state == StudyState.completed) ...[
            const Icon(
              Icons.check_circle_rounded,
              color: AppColors.success,
              size: 40,
            ),
            const SizedBox(height: 8),
            const Text(
              '本次学习已完成',
              style: AppTypography.subtitle,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: onStart,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('再来一次'),
            ),
          ] else ...[
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onPause,
                    icon: const Icon(Icons.pause_rounded),
                    label: const Text('暂停'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: onEnd,
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.danger,
                    ),
                    icon: const Icon(Icons.stop_rounded),
                    label: const Text('结束'),
                  ),
                ),
              ],
            ),
          ],
          if (isStudying &&
              state != StudyState.completed &&
              selectedRelatedTaskId != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: c.primarySubtle,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.link, size: 14, color: c.primary),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      '关联待办:${_taskTitle(selectedRelatedTaskId)}',
                      style: AppTypography.caption.copyWith(color: c.primary),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _taskTitle(String? id) {
    if (id == null) return '';
    for (final t in relatedTasks) {
      if (t.id == id) return t.title;
    }
    return id;
  }
}

/// 结束会话时填写文字感受的对话框。
///
/// **科学边界**:selfReport 仅由用户主动输入,不根据表情自动填写。
/// 不进行心理疾病诊断,文案仅作日常辅助。
class StudyFinishDialog extends StatefulWidget {
  const StudyFinishDialog({
    super.key,
    required this.durationSeconds,
    required this.pauseSeconds,
  });

  final int durationSeconds;
  final int pauseSeconds;

  /// 显示对话框,返回 (selfReport, tags) 或 null(用户取消)。
  static Future<({String? selfReport, List<String> tags})?> show(
    BuildContext context, {
    required int durationSeconds,
    required int pauseSeconds,
  }) {
    return showDialog<({String? selfReport, List<String> tags})>(
      context: context,
      barrierDismissible: false,
      builder: (_) => StudyFinishDialog(
        durationSeconds: durationSeconds,
        pauseSeconds: pauseSeconds,
      ),
    );
  }

  @override
  State<StudyFinishDialog> createState() => _StudyFinishDialogState();
}

class _StudyFinishDialogState extends State<StudyFinishDialog> {
  final _controller = TextEditingController();
  final Set<String> _selectedTags = {};

  static const List<String> _presetTags = [
    '专注',
    '分心',
    '疲惫',
    '有收获',
    '需要复盘',
    '进度顺利',
  ];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final durationMin = (widget.durationSeconds / 60).round();
    final pauseMin = (widget.pauseSeconds / 60).round();
    return AlertDialog(
      title: const Text('本次学习感受'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '本次学习时长 $durationMin 分钟,休息 $pauseMin 分钟。',
              style: AppTypography.caption,
            ),
            const SizedBox(height: 12),
            const Text('本次感受(可选)', style: AppTypography.label),
            const SizedBox(height: 4),
            TextField(
              controller: _controller,
              maxLines: 3,
              maxLength: 500,
              decoration: const InputDecoration(
                hintText: '例如:这章难点在多元函数求导,需要再练两道题。',
                alignLabelWithHint: false,
              ),
            ),
            const SizedBox(height: 8),
            const Text('标签(可选)', style: AppTypography.label),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: _presetTags.map((tag) {
                final selected = _selectedTags.contains(tag);
                return FilterChip(
                  label: Text(tag),
                  selected: selected,
                  onSelected: (sel) {
                    setState(() {
                      if (sel) {
                        _selectedTags.add(tag);
                      } else {
                        _selectedTags.remove(tag);
                      }
                    });
                  },
                );
              }).toList(),
            ),
            const SizedBox(height: 8),
            Text(
              '说明:文字感受仅作日常辅助参考,不进行心理诊断。'
              '如需专业支持,请咨询辅导员或学校心理咨询中心。',
              style: AppTypography.caption.copyWith(
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).maybePop(),
          child: const Text('不填写并结束'),
        ),
        FilledButton(
          onPressed: () {
            final text = _controller.text.trim();
            Navigator.of(context).pop(
              (
                selfReport: text.isEmpty ? null : text,
                tags: _selectedTags.toList(),
              ),
            );
          },
          child: const Text('保存并结束'),
        ),
      ],
    );
  }
}
