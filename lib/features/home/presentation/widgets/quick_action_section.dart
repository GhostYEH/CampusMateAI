import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';

/// 首页快捷入口区 — 整理通知 / 新建待办 / 问AI导员 / 开始学习。
///
/// 提取自原 HomePage 的 _QuickActions。
class QuickActionSection extends StatelessWidget {
  const QuickActionSection({super.key});

  @override
  Widget build(BuildContext context) {
    final actions = <_ActionData>[
      const _ActionData(
        '整理通知',
        '粘贴即识别',
        '/notifications/extract',
        'assets/images/home/quick_notice.png',
        AppColors.accent,
        Color(0xFFFFF3E9),
      ),
      const _ActionData(
        '新建待办',
        '安排今天',
        '/tasks/create',
        'assets/images/home/quick_task.png',
        AppColors.primary,
        Color(0xFFEAF3F8),
      ),
      const _ActionData(
        '问AI导员',
        '校园问答',
        '/counselor',
        'assets/images/home/quick_counselor.png',
        AppColors.info,
        Color(0xFFE8F1F4),
      ),
      const _ActionData(
        '开始学习',
        '进入专注',
        '/study',
        'assets/images/home/quick_study.png',
        AppColors.success,
        Color(0xFFEBF3EC),
      ),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('现在想做什么？', style: AppTypography.title),
          const SizedBox(height: 12),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisExtent: 112,
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
            ),
            itemCount: actions.length,
            itemBuilder: (context, index) => _ActionTile(data: actions[index]),
          ),
        ],
      ),
    );
  }
}

class _ActionData {
  final String label;
  final String hint;
  final String route;
  final String asset;
  final Color color;
  final Color background;
  const _ActionData(
    this.label,
    this.hint,
    this.route,
    this.asset,
    this.color,
    this.background,
  );
}

class _ActionTile extends StatefulWidget {
  const _ActionTile({required this.data});
  final _ActionData data;

  @override
  State<_ActionTile> createState() => _ActionTileState();
}

class _ActionTileState extends State<_ActionTile> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final data = widget.data;
    return Semantics(
      button: true,
      label: '${data.label}，${data.hint}',
      child: AnimatedScale(
        scale: _pressed ? 0.97 : 1,
        duration: AppMotion.fast,
        curve: AppMotion.emphasized,
        child: Material(
          color: data.background,
          borderRadius: BorderRadius.circular(20),
          child: InkWell(
            onTap: () => context.push(data.route),
            onHighlightChanged: (value) => setState(() => _pressed = value),
            borderRadius: BorderRadius.circular(20),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 10, 10),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(data.label, style: AppTypography.subtitle),
                        const SizedBox(height: 4),
                        Text(
                          data.hint,
                          style: AppTypography.caption.copyWith(
                            color: data.color,
                          ),
                        ),
                      ],
                    ),
                  ),
                  SizedBox(
                    width: 66,
                    height: 82,
                    child: Image.asset(
                      data.asset,
                      fit: BoxFit.contain,
                      filterQuality: FilterQuality.medium,
                      errorBuilder: (_, __, ___) => Icon(
                        Icons.widgets_rounded,
                        color: data.color,
                        size: 34,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
