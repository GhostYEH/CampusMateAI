import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../app/providers/app_providers.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../core/widgets/app_card.dart';

/// 学习记录摘要 — 今日总时长 / 近期次数 / 平均专注率。
class StudyHistorySummary extends ConsumerWidget {
  const StudyHistorySummary({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(studyHistoryProvider);
    final todayAsync = ref.watch(todayStudyTotalProvider);
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.history_rounded, size: 18, color: AppColors.primary),
              SizedBox(width: 6),
              Text('学习记录', style: AppTypography.subtitle),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _stat(
                  '今日',
                  _formatDuration(todayAsync.valueOrNull),
                  AppColors.primary,
                ),
              ),
              Container(width: 1, height: 36, color: AppColors.border),
              Expanded(
                child: _stat(
                  '近 ${historyAsync.valueOrNull?.length ?? 0} 次',
                  '${historyAsync.valueOrNull?.length ?? 0} 次',
                  AppColors.success,
                ),
              ),
              Container(width: 1, height: 36, color: AppColors.border),
              Expanded(
                child: _stat(
                  '平均专注',
                  '${((historyAsync.valueOrNull?.fold<double>(0, (a, s) => a + s.focusRatio) ?? 0) / (historyAsync.valueOrNull?.length ?? 1) * 100).round()}%',
                  AppColors.accent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (historyAsync.valueOrNull?.isNotEmpty ?? false)
            ...historyAsync.valueOrNull!.take(3).map(
                  (s) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.circle,
                          size: 6,
                          color: AppColors.success,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          AppDateUtils.relativeTime(s.startedAt),
                          style: AppTypography.caption,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            '学习 ${s.durationMinutes} 分钟 · 专注 ${(s.focusRatio * 100).round()}%',
                            style: AppTypography.caption,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
        ],
      ),
    );
  }

  Widget _stat(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: AppTypography.subtitle.copyWith(color: color)),
        const SizedBox(height: 2),
        Text(label, style: AppTypography.overline),
      ],
    );
  }

  String _formatDuration(Duration? d) {
    if (d == null) return '0 分钟';
    final m = d.inMinutes;
    if (m < 60) return '$m 分钟';
    return '${m ~/ 60} 小时 ${m % 60} 分钟';
  }
}
