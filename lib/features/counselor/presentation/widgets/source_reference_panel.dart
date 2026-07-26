import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../data/models/chat.dart';

/// 参考来源区 — 展示知识库引用列表。
///
/// 设计原则(遵循 frontend-design skill 的"晨曦校园"方向):
/// - 真实后端模式: 标题"知识库来源",展示部门、版本、适用对象、官方/过期/仿真徽章
/// - Mock 模式: 标题"参考来源(模拟)",简化展示
/// - 过期资料用 warning 色徽章,官方资料用 success 色徽章,仿真资料用 accent 色徽章
/// - 资料冲突时同时展示相关来源,标记较新官方资料,提示人工核实
/// - 引用片段简短,不展示内部向量 ID
/// - 来源多于 2 条时默认折叠,展开后显示全部
class SourceReferencePanel extends StatefulWidget {
  const SourceReferencePanel({
    super.key,
    required this.sources,
    this.isRealBackend = false,
    this.hasConflict = false,
  });

  final List<KnowledgeSource> sources;

  /// 是否为真实后端模式(影响标题与字段展示密度)。
  ///
  /// 由调用方根据 AppConfig 注入,默认 false(Mock 模式标题)。
  final bool isRealBackend;

  /// 是否检测到资料冲突 — 影响是否显示冲突提示横幅。
  final bool hasConflict;

  @override
  State<SourceReferencePanel> createState() => _SourceReferencePanelState();
}

class _SourceReferencePanelState extends State<SourceReferencePanel> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final title = widget.isRealBackend ? '知识库来源' : '参考来源(模拟)';
    // 来源多于 2 条时默认折叠,仅展示前 2 条
    final showAll = _expanded || widget.sources.length <= 2;
    final visibleSources =
        showAll ? widget.sources : widget.sources.sublist(0, 2);
    final hiddenCount = widget.sources.length - visibleSources.length;

    // 推断"较新官方资料" — 仅在冲突时高亮
    final newestOfficialId =
        widget.hasConflict ? _findNewestOfficialId(widget.sources) : null;

    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.bgSunken,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(
          color: widget.hasConflict
              ? AppColors.warning.withValues(alpha: 0.6)
              : AppColors.border,
          width: widget.hasConflict ? 0.8 : 0.6,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                widget.hasConflict
                    ? Icons.warning_amber_rounded
                    : Icons.menu_book_rounded,
                size: 13,
                color: widget.hasConflict
                    ? AppColors.warning
                    : AppColors.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                widget.hasConflict ? '$title · 资料冲突' : title,
                style: AppTypography.label.copyWith(
                  fontSize: 10.5,
                  color: widget.hasConflict
                      ? AppColors.warning
                      : AppColors.textSecondary,
                ),
              ),
            ],
          ),
          if (widget.hasConflict) ...[
            const SizedBox(height: 6),
            _ConflictHintBanner(newestOfficialId: newestOfficialId),
          ],
          const SizedBox(height: 8),
          for (var i = 0; i < visibleSources.length; i++) ...[
            _SourceItem(
              source: visibleSources[i],
              isRealBackend: widget.isRealBackend,
              isNewestOfficial: newestOfficialId == visibleSources[i].id &&
                  newestOfficialId != null,
            ),
            if (i != visibleSources.length - 1) const SizedBox(height: 10),
          ],
          if (hiddenCount > 0) ...[
            const SizedBox(height: 8),
            _expandButton(hiddenCount),
          ],
        ],
      ),
    );
  }

  Widget _expandButton(int hiddenCount) {
    return InkWell(
      onTap: () => setState(() => _expanded = true),
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
        decoration: BoxDecoration(
          color: AppColors.bgSurface,
          borderRadius: BorderRadius.circular(AppRadius.xs),
          border: Border.all(color: AppColors.border, width: 0.5),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.unfold_more_rounded,
              size: 11,
              color: AppColors.textSecondary,
            ),
            const SizedBox(width: 4),
            Text(
              '展开剩余 $hiddenCount 条来源',
              style: AppTypography.label.copyWith(
                fontSize: 10.5,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 在冲突场景下,找出"最新官方资料"的 ID 用于高亮。
  String? _findNewestOfficialId(List<KnowledgeSource> sources) {
    final official =
        sources.where((s) => s.isOfficial && !s.isExpired).toList();
    if (official.isEmpty) return null;
    official.sort((a, b) {
      final aDate = a.publishedAt ?? a.updatedAt;
      final bDate = b.publishedAt ?? b.updatedAt;
      return bDate.compareTo(aDate);
    });
    return official.first.id;
  }
}

class _ConflictHintBanner extends StatelessWidget {
  const _ConflictHintBanner({this.newestOfficialId});

  final String? newestOfficialId;

  @override
  Widget build(BuildContext context) {
    final text = newestOfficialId == null
        ? '资料存在冲突,以下来源仅供对比参考,请向学院办公室或辅导员核实最新规定。'
        : '资料存在冲突,已标记较新的官方资料。请以官方最新文件为准,必要时向学院办公室核实。';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(AppRadius.xs),
        border: Border.all(color: AppColors.warningSubtle, width: 0.5),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.warning_amber_rounded,
            size: 11,
            color: AppColors.warning,
          ),
          const SizedBox(width: 4),
          Expanded(
            child: Text(
              text,
              style: AppTypography.overline.copyWith(
                fontSize: 9.5,
                color: AppColors.warning,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SourceItem extends StatelessWidget {
  const _SourceItem({
    required this.source,
    required this.isRealBackend,
    this.isNewestOfficial = false,
  });

  final KnowledgeSource source;
  final bool isRealBackend;
  final bool isNewestOfficial;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                source.title,
                style: AppTypography.bodyStrong.copyWith(fontSize: 12.5),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (isNewestOfficial)
              Container(
                margin: const EdgeInsets.only(left: 4),
                padding: const EdgeInsets.symmetric(
                  horizontal: 5,
                  vertical: 1,
                ),
                decoration: BoxDecoration(
                  color: AppColors.successSubtle,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: AppColors.success, width: 0.5),
                ),
                child: Text(
                  '较新官方',
                  style: AppTypography.overline.copyWith(
                    fontSize: 9,
                    color: AppColors.success,
                  ),
                ),
              ),
            if (source.isOfficial)
              Container(
                margin: const EdgeInsets.only(left: 4),
                padding: const EdgeInsets.symmetric(
                  horizontal: 5,
                  vertical: 1,
                ),
                decoration: BoxDecoration(
                  color: AppColors.successSubtle,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: AppColors.success, width: 0.5),
                ),
                child: Text(
                  '官方',
                  style: AppTypography.overline.copyWith(
                    fontSize: 9,
                    color: AppColors.success,
                  ),
                ),
              ),
            if (source.isExpired)
              Container(
                margin: const EdgeInsets.only(left: 4),
                padding: const EdgeInsets.symmetric(
                  horizontal: 5,
                  vertical: 1,
                ),
                decoration: BoxDecoration(
                  color: AppColors.warningSubtle,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: AppColors.warning, width: 0.5),
                ),
                child: Text(
                  '已过期',
                  style: AppTypography.overline.copyWith(
                    fontSize: 9,
                    color: AppColors.warning,
                  ),
                ),
              ),
            if (source.isDemo)
              Container(
                margin: const EdgeInsets.only(left: 4),
                padding: const EdgeInsets.symmetric(
                  horizontal: 5,
                  vertical: 1,
                ),
                decoration: BoxDecoration(
                  color: AppColors.accentSubtle,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: AppColors.accent, width: 0.5),
                ),
                child: Text(
                  '仿真资料',
                  style: AppTypography.overline.copyWith(
                    fontSize: 9,
                    color: AppColors.accent,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 4),
        Wrap(
          spacing: 5,
          runSpacing: 2,
          children: [
            if (isRealBackend && source.sourceDepartment != null)
              _tag(source.sourceDepartment!, icon: Icons.apartment_rounded),
            if (!isRealBackend) _tag(source.source, icon: Icons.layers_rounded),
            _tag(
              '更新于 ${AppDateUtils.formatDate(source.updatedAt)}',
              icon: Icons.event_outlined,
            ),
            if (isRealBackend && source.version != null)
              _tag('v${source.version}', icon: Icons.history_edu_rounded),
            if (isRealBackend && source.applicableStudents != null)
              _tag(
                source.applicableStudents!,
                icon: Icons.group_outlined,
              ),
            if (isRealBackend && source.section != null)
              _tag(
                source.section!,
                icon: Icons.subdirectory_arrow_right_rounded,
              ),
            if (source.publishedAt != null)
              _tag(
                '发布于 ${AppDateUtils.formatDate(source.publishedAt!)}',
                icon: Icons.calendar_today_outlined,
              ),
          ],
        ),
        if (source.isExpired) ...[
          const SizedBox(height: 4),
          Text(
            '此资料已过期,仅作为历史参考,请以最新规定为准。',
            style: AppTypography.overline.copyWith(
              fontSize: 9.5,
              color: AppColors.warning,
              height: 1.3,
            ),
          ),
        ],
        if (source.snippet != null && source.snippet!.isNotEmpty) ...[
          const SizedBox(height: 5),
          Text(
            source.snippet!,
            style: AppTypography.caption.copyWith(
              fontSize: 11.5,
              color: AppColors.textSecondary,
            ),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ],
    );
  }

  Widget _tag(String text, {IconData? icon}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AppColors.border, width: 0.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 9, color: AppColors.textTertiary),
            const SizedBox(width: 2),
          ],
          Text(text, style: AppTypography.overline.copyWith(fontSize: 9.5)),
        ],
      ),
    );
  }
}

/// 无可靠资料提示 — 引导用户咨询辅导员或学院办公室。
///
/// 体现科学边界:不伪造学校政策。
class NoSourcesHint extends StatelessWidget {
  const NoSourcesHint({super.key, this.reason});

  /// 可选的原因说明(如"知识库为空"或"检索无匹配")。
  final String? reason;

  @override
  Widget build(BuildContext context) {
    final text = reason == null
        ? '该问题暂无可靠资料,建议咨询辅导员或学院办公室'
        : '该问题暂无可靠资料($reason),建议咨询辅导员或学院办公室';
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: AppColors.warningSubtle, width: 0.6),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.info_outline_rounded,
            size: 14,
            color: AppColors.warning,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              text,
              style: AppTypography.caption.copyWith(
                fontSize: 11.5,
                color: AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
