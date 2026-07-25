import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/expression.dart';
import 'expression_result_view.dart';
import 'mock_expression_control.dart';

/// 表情识别面板 — 包含标题/状态/Mock 模式说明/结果区/Mock 控制台。
///
/// 当 enabled=false 时显示禁用提示。
/// 当 enabled=true 时显示当前结果 + Mock 控制台。
/// Mock 控制台仅在开发模式或比赛演示模式显示(由调用方控制 showMockConsole)。
class ExpressionPanel extends StatelessWidget {
  const ExpressionPanel({
    super.key,
    required this.enabled,
    required this.result,
    required this.recentStable,
    required this.onInject,
    required this.showMockConsole,
  });

  final bool enabled;
  final ExpressionResult? result;
  final List<ExpressionResult> recentStable;
  final void Function(ExpressionLabel?) onInject;
  final bool showMockConsole;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(
                Icons.face_retouching_natural_rounded,
                size: 18,
                color: AppColors.primary,
              ),
              const SizedBox(width: 6),
              const Text('表情识别', style: AppTypography.subtitle),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: enabled ? AppColors.successSubtle : AppColors.bgSunken,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  enabled ? '运行中' : '未开启',
                  style: AppTypography.label.copyWith(
                    color: enabled ? AppColors.success : AppColors.textTertiary,
                    fontSize: 10.5,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          const Text(
            'Mock 模式 · 模型 mock-v0.1 · 仅识别可观察表情,不作心理诊断',
            style: AppTypography.overline,
          ),
          const SizedBox(height: 14),
          if (!enabled) ...[
            const ExpressionDisabledHint(),
          ] else ...[
            _resultView(),
            if (showMockConsole) ...[
              const SizedBox(height: 16),
              MockExpressionControl(onInject: onInject),
            ],
          ],
        ],
      ),
    );
  }

  Widget _resultView() {
    if (result == null) {
      return const Row(
        children: [
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: 10),
          Text('正在采集…', style: AppTypography.caption),
        ],
      );
    }
    return ExpressionResultView(
      result: result!,
      recentStable: recentStable,
    );
  }
}
