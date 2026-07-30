import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';

/// 快捷操作 — 2x2 网格,符合青年校园风格。
class QuickActionSection extends StatelessWidget {
  const QuickActionSection({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final actions = [
      _ActionData(
        label: '整理通知',
        hint: '粘贴通知，提取时间与材料',
        route: '/notifications/extract',
        icon: PhosphorIconsRegular.trayArrowDown,
        color: c.accent,
      ),
      _ActionData(
        label: '新建待办',
        hint: '把临时事项放进今天',
        route: '/tasks/create',
        icon: PhosphorIconsRegular.notePencil,
        color: c.primary,
      ),
      _ActionData(
        label: '问AI导员',
        hint: '查询校园流程与规定',
        route: '/counselor',
        icon: PhosphorIconsRegular.chatsCircle,
        color: c.info,
      ),
      _ActionData(
        label: '开始学习',
        hint: '记录一段专注时间',
        route: '/study',
        icon: PhosphorIconsRegular.timer,
        color: c.success,
      ),
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.edge),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('快捷操作', style: AppTypography.subtitle),
          const SizedBox(height: 10),
          LayoutBuilder(
            builder: (context, constraints) {
              final desktop = constraints.maxWidth >= 560;
              return GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: desktop ? 4 : 2,
                  mainAxisExtent: 100,
                  crossAxisSpacing: desktop ? 8 : 10,
                  mainAxisSpacing: 10,
                ),
                itemCount: actions.length,
                itemBuilder: (context, index) => _ActionTile(
                  data: actions[index],
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _ActionData {
  const _ActionData({
    required this.label,
    required this.hint,
    required this.route,
    required this.icon,
    required this.color,
  });

  final String label;
  final String hint;
  final String route;
  final IconData icon;
  final Color color;
}

class _ActionTile extends StatefulWidget {
  const _ActionTile({required this.data});

  final _ActionData data;

  @override
  State<_ActionTile> createState() => _ActionTileState();
}

class _ActionTileState extends State<_ActionTile> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final data = widget.data;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: Semantics(
        button: true,
        label: '${data.label}，${data.hint}',
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: () => context.push(data.route),
            borderRadius: BorderRadius.circular(10),
            child: AnimatedContainer(
              duration: AppMotion.fast,
              padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
              decoration: BoxDecoration(
                color: _hovered
                    ? data.color.withValues(alpha: .09)
                    : c.bgSurface,
                border: Border.all(
                  color:
                      _hovered ? data.color.withValues(alpha: .45) : c.border,
                  width: _hovered ? 1 : .6,
                ),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: data.color.withValues(alpha: .1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: PhosphorIcon(
                      data.icon,
                      size: 17,
                      color: data.color,
                    ),
                  ),
                  const Spacer(),
                  Text(data.label, style: AppTypography.bodyStrong),
                  const SizedBox(height: 1),
                  Text(
                    data.hint,
                    style: AppTypography.caption.copyWith(
                      color: c.textTertiary,
                      fontSize: 11,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
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
