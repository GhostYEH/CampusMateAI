import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/knowledge.dart';

/// 知识库状态卡片 — 显示当前知识库类型、文档数、分块数、问答模式等。
///
/// 设计原则:
/// - 不用红色,知识库不可用是预期状态而非错误
/// - 仿真资料声明用 warning 暖色,体现"非真实学校制度"的谨慎
/// - 信息密度适中,关键指标用 metric 风格突出
class KnowledgeStatusCard extends StatelessWidget {
  const KnowledgeStatusCard({
    super.key,
    required this.status,
    required this.isMockMode,
  });

  final KnowledgeStatusInfo status;
  final bool isMockMode;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.menu_book_rounded,
                size: 18,
                color: AppColors.primary,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  isMockMode ? '演示模式知识库' : status.knowledgeBaseType.displayName,
                  style: AppTypography.subtitle,
                ),
              ),
              _IndexBadge(status: status.indexStatus),
            ],
          ),
          const SizedBox(height: 12),
          // 关键指标
          Row(
            children: [
              _Metric(
                label: '文档',
                value: '${status.documentCount}',
                unit: '份',
                color: AppColors.primary,
              ),
              _Metric(
                label: '分块',
                value: '${status.chunkCount}',
                unit: '段',
                color: AppColors.accent,
              ),
              _Metric(
                label: '演示资料',
                value: '${status.demoDocumentCount}',
                unit: '份',
                color: AppColors.warning,
              ),
              _Metric(
                label: '用户导入',
                value: '${status.userDocumentCount}',
                unit: '份',
                color: AppColors.success,
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Divider(height: 1, color: AppColors.border),
          const SizedBox(height: 10),
          _InfoRow(
            label: '检索方式',
            value: _retrievalMethodLabel(status.retrievalMethod),
          ),
          _InfoRow(
            label: 'LLM 状态',
            value: status.llmAvailable ? '已启用(LLM RAG 模式可用)' : '未配置(使用检索摘要)',
            valueColor: status.llmAvailable
                ? AppColors.success
                : AppColors.textSecondary,
          ),
          _InfoRow(
            label: '问答模式',
            value: _qaModeLabel(status.qaMode),
          ),
          if (status.lastUpdated != null)
            _InfoRow(
              label: '最近更新',
              value: AppDateUtils.formatDateFull(status.lastUpdated!),
            ),
          if (status.hasDemoDocuments) ...[
            const SizedBox(height: 10),
            _DemoDataNotice(),
          ],
        ],
      ),
    );
  }

  String _retrievalMethodLabel(String method) {
    switch (method.toLowerCase()) {
      case 'bm25':
        return 'BM25 关键词检索';
      case 'vector':
        return '向量检索';
      case 'hybrid':
        return '混合检索(BM25 + 向量)';
      default:
        return method;
    }
  }

  String _qaModeLabel(QaMode mode) {
    switch (mode) {
      case QaMode.retrievalSummary:
        return '检索摘要(基于检索片段归纳)';
      case QaMode.llmRag:
        return 'LLM RAG(基于检索片段生成)';
      case QaMode.noKnowledge:
        return '无知识库依据(需导入资料)';
    }
  }
}

class _IndexBadge extends StatelessWidget {
  const _IndexBadge({required this.status});
  final IndexStatus status;

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (status) {
      IndexStatus.ready => ('索引就绪', AppColors.success),
      IndexStatus.empty => ('索引为空', AppColors.warning),
      IndexStatus.error => ('索引异常', AppColors.danger),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color, width: 0.6),
      ),
      child: Text(
        label,
        style: AppTypography.overline.copyWith(fontSize: 9.5, color: color),
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({
    required this.label,
    required this.value,
    required this.unit,
    required this.color,
  });

  final String label;
  final String value;
  final String unit;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: AppTypography.overline.copyWith(fontSize: 10),
          ),
          const SizedBox(height: 2),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                value,
                style: AppTypography.metric.copyWith(
                  fontSize: 22,
                  color: color,
                ),
              ),
              const SizedBox(width: 2),
              Text(
                unit,
                style: AppTypography.overline.copyWith(
                  fontSize: 10,
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value, this.valueColor});
  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 76,
            child: Text(
              label,
              style: AppTypography.overline.copyWith(fontSize: 10.5),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTypography.caption.copyWith(
                fontSize: 11.5,
                color: valueColor ?? AppColors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 仿真校园演示资料声明 — 必须始终显示,只要当前包含演示资料。
class _DemoDataNotice extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(AppRadius.xs),
        border: Border.all(color: AppColors.warningSubtle, width: 0.6),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.info_outline_rounded,
            size: 13,
            color: AppColors.warning,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              '当前包含仿真校园演示资料,并非用户所在学校的真实现行制度,请勿直接作为实际办事依据。',
              style: AppTypography.caption.copyWith(
                fontSize: 11,
                color: AppColors.textSecondary,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
