import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/study.dart';

/// 学习控制按钮组 — 开始 / 暂停 / 继续 / 结束 / 再来一次。
///
/// 状态机:
/// - 未开始: 显示"本次目标"输入 + 开始按钮
/// - 暂停: 显示"继续" + "结束"
/// - 已完成: 显示完成图标 + "再来一次"
/// - 专注中: 显示"暂停" + "结束"
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
  });

  final bool isStudying;
  final StudyState state;
  final TextEditingController goalController;
  final VoidCallback onStart;
  final VoidCallback onPause;
  final VoidCallback onResume;
  final VoidCallback onEnd;

  @override
  Widget build(BuildContext context) {
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
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: onStart,
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
        ],
      ),
    );
  }
}
