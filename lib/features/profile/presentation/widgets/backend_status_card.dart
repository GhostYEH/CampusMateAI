import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../app/providers/app_providers.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../core/widgets/app_card.dart';

/// 后端连接状态卡片 — 显示当前模式与后端健康状态。
///
/// 设计原则(遵循 frontend-design skill 的"晨曦校园"方向):
/// - 状态色:成功用 success(绿)、未连接用 warning(暖)、未初始化用 accent(暖橙)
/// - 不用红色 — 后端不可用不应让用户感到惊吓
/// - 卡片克制,内嵌状态徽章 + 关键信息列表
/// - 失败时提供"重试"按钮,不清空已输入数据
class BackendStatusCard extends ConsumerWidget {
  const BackendStatusCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final config = ref.watch(appConfigProvider);
    final asyncStatus = ref.watch(backendStatusProvider);

    // Mock 模式:固定展示"演示模式"状态
    if (config.useMockBackend) {
      return _ModeBadge(
        mode: _BackendMode.demo,
        apiBaseUrl: config.apiBaseUrl,
        status: const BackendStatus(
          status: BackendConnectionStatus.demoMode,
        ),
      );
    }

    return asyncStatus.when(
      loading: () => _ModeBadge(
        mode: _BackendMode.checking,
        apiBaseUrl: config.apiBaseUrl,
        status: null,
      ),
      error: (e, _) => _ModeBadge(
        mode: _BackendMode.error,
        apiBaseUrl: config.apiBaseUrl,
        status: BackendStatus(
          status: BackendConnectionStatus.disconnected,
          errorMessage: e.toString(),
        ),
        onRetry: () => ref.read(backendStatusProvider.notifier).check(),
      ),
      data: (status) => _ModeBadge(
        mode: status.status == BackendConnectionStatus.connected
            ? _BackendMode.connected
            : (status.status == BackendConnectionStatus.knowledgeBaseEmpty
                ? _BackendMode.kbEmpty
                : (status.status == BackendConnectionStatus.disconnected
                    ? _BackendMode.error
                    : _BackendMode.checking)),
        apiBaseUrl: config.apiBaseUrl,
        status: status,
        onRetry: () => ref.read(backendStatusProvider.notifier).check(),
      ),
    );
  }
}

enum _BackendMode { demo, checking, connected, kbEmpty, error }

class _ModeBadge extends StatelessWidget {
  const _ModeBadge({
    required this.mode,
    required this.apiBaseUrl,
    required this.status,
    this.onRetry,
  });

  final _BackendMode mode;
  final String apiBaseUrl;
  final BackendStatus? status;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final info = _modeInfo(mode);
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: info.color,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: info.color.withValues(alpha: 0.4),
                      blurRadius: 6,
                      spreadRadius: 1,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(info.title, style: AppTypography.subtitle),
              ),
              if (mode == _BackendMode.error && onRetry != null)
                _RetryButton(onRetry: onRetry!),
              if (mode == _BackendMode.checking)
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppColors.textTertiary,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(info.subtitle, style: AppTypography.caption),
          const SizedBox(height: 8),
          _InfoRow(label: 'API 地址', value: apiBaseUrl),
          if (status != null) ...[
            if (status!.version.isNotEmpty)
              _InfoRow(label: '后端版本', value: status!.version),
            if (mode == _BackendMode.connected ||
                mode == _BackendMode.kbEmpty) ...[
              _InfoRow(
                label: '已索引文档',
                value: '${status!.documentCount} 份',
              ),
              _InfoRow(
                label: '索引分块',
                value: '${status!.chunkCount} 段',
              ),
              _InfoRow(
                label: 'LLM Provider',
                value: status!.llmAvailable ? '已启用' : '未配置(检索摘要模式)',
              ),
            ],
            if (status!.lastChecked != null)
              _InfoRow(
                label: '最近检查',
                value:
                    '${AppDateUtils.formatDate(status!.lastChecked!)} ${AppDateUtils.formatTime(status!.lastChecked!)}',
              ),
            if (status!.errorMessage != null && mode == _BackendMode.error)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.warningSubtle.withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(AppRadius.xs),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.info_outline_rounded,
                        size: 13,
                        color: AppColors.warning,
                      ),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          status!.errorMessage!,
                          style: AppTypography.caption.copyWith(
                            fontSize: 11,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }

  _ModeVisual _modeInfo(_BackendMode mode) {
    switch (mode) {
      case _BackendMode.demo:
        return const _ModeVisual(
          title: '演示模式',
          subtitle: '当前使用 Mock 数据,所有后端能力为本地模拟。可切换到真实后端模式以启用 RAG。',
          color: AppColors.accent,
        );
      case _BackendMode.checking:
        return const _ModeVisual(
          title: '检查中',
          subtitle: '正在连接后端服务,请稍候。',
          color: AppColors.textTertiary,
        );
      case _BackendMode.connected:
        return const _ModeVisual(
          title: '已连接 · 知识库就绪',
          subtitle: 'FastAPI 后端已连接,知识库可用,RAG 问答已启用。',
          color: AppColors.success,
        );
      case _BackendMode.kbEmpty:
        return const _ModeVisual(
          title: '已连接 · 知识库未初始化',
          subtitle: '后端可连接,但知识库尚未导入文档。请先导入校园资料后再使用 RAG 问答。',
          color: AppColors.accent,
        );
      case _BackendMode.error:
        return const _ModeVisual(
          title: '未连接',
          subtitle: '无法连接到后端服务。可点击重试,或切换到演示模式继续使用。',
          color: AppColors.warning,
        );
    }
  }
}

class _ModeVisual {
  const _ModeVisual({
    required this.title,
    required this.subtitle,
    required this.color,
  });
  final String title;
  final String subtitle;
  final Color color;
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
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
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RetryButton extends StatelessWidget {
  const _RetryButton({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onRetry,
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: AppColors.primarySubtle,
          borderRadius: BorderRadius.circular(AppRadius.xs),
          border: Border.all(color: AppColors.primary, width: 0.6),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.refresh_rounded,
              size: 12,
              color: AppColors.primary,
            ),
            const SizedBox(width: 3),
            Text(
              '重试',
              style: AppTypography.label.copyWith(
                fontSize: 10.5,
                color: AppColors.primary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
