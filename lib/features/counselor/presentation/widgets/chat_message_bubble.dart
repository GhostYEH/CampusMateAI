import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/utils/date_utils.dart';
import '../../../../data/models/chat.dart';
import 'answer_meta_badge.dart';
import 'counselor_markdown_body.dart';
import 'source_reference_panel.dart';
import 'suggested_action_chips.dart';
import 'typing_indicator.dart';
import 'robot_avatar.dart';

/// AI 导员/用户 消息气泡。
///
/// 用户气泡: 主色填充,无来源/操作区。
/// AI 气泡: 白底 + 边框,可附带来源区、建议操作、复制/重新生成。
/// 流式输出时: 末尾追加闪烁光标,内容为空时显示三点跳动。
class ChatMessageBubble extends StatelessWidget {
  const ChatMessageBubble({
    super.key,
    required this.message,
    required this.isFirst,
    required this.onCopy,
    required this.onRegenerate,
    required this.onStop,
    required this.onAction,
    this.isRealBackend = false,
    this.onAddToTasks,
  });

  final ChatMessage message;
  final bool isFirst;
  final VoidCallback onCopy;
  final VoidCallback onRegenerate;
  final VoidCallback onStop;
  final void Function(SuggestedAction) onAction;

  /// 是否为真实后端模式 — 影响来源区标题与字段展示。
  final bool isRealBackend;

  /// "根据回答创建待办"回调 — 由父组件注入,跳转到通知整理页人工确认。
  final VoidCallback? onAddToTasks;

  bool get _isUser => message.sender == MessageSender.user;
  bool get _isStreaming => message.isStreaming;

  @override
  Widget build(BuildContext context) {
    final isUser = _isUser;
    return Row(
      mainAxisAlignment:
          isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (!isUser) ...[
          const RobotAvatar(size: 28, iconSize: 16),
          const SizedBox(width: 8),
        ],
        Flexible(
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.78,
            ),
            child: Column(
              crossAxisAlignment:
                  isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                _bubble(context),
                const SizedBox(height: 4),
                Text(
                  AppDateUtils.formatTime(message.timestamp),
                  style: AppTypography.caption.copyWith(
                    fontSize: 10.5,
                    color: AppColors.textTertiary,
                  ),
                ),
                if (!isUser && !_isStreaming) ...[
                  // 模式徽章 + 证据等级 + 创建待办按钮
                  AnswerMetaBadge(
                    message: message,
                    onAddToTasks: onAddToTasks,
                  ),
                  if (message.sources.isNotEmpty)
                    SourceReferencePanel(
                      sources: message.sources,
                      isRealBackend: isRealBackend,
                      hasConflict:
                          message.evidenceLevel == EvidenceLevel.conflict,
                    )
                  else if (!isFirst && message.content.isNotEmpty)
                    const NoSourcesHint(),
                  if (message.actions.isNotEmpty)
                    SuggestedActionChips(
                      actions: message.actions,
                      onAction: onAction,
                    ),
                  MessageActions(
                    onCopy: onCopy,
                    onRegenerate: onRegenerate,
                    canRegenerate: !isFirst,
                  ),
                ],
                if (!isUser && _isStreaming) StreamingActions(onStop: onStop),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _bubble(BuildContext context) {
    final isUser = _isUser;
    final content = message.content;
    final showTypingDots = _isStreaming && content.isEmpty;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: isUser ? AppColors.primary : AppColors.bgSurface,
        border: isUser ? null : Border.all(color: AppColors.border, width: 0.8),
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(AppRadius.md),
          topRight: const Radius.circular(AppRadius.md),
          bottomLeft: Radius.circular(isUser ? AppRadius.md : AppRadius.xs),
          bottomRight: Radius.circular(isUser ? AppRadius.xs : AppRadius.md),
        ),
        boxShadow: isUser ? null : AppShadows.subtle,
      ),
      child:
          showTypingDots ? const TypingDots() : _contentText(content, isUser),
    );
  }

  Widget _contentText(String content, bool isUser) {
    if (message.streamError != null) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.error_outline_rounded,
            size: 14,
            color: AppColors.danger,
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              message.streamError!,
              style: AppTypography.body.copyWith(color: AppColors.danger),
            ),
          ),
        ],
      );
    }
    // 用户消息: 永远使用纯文本
    if (isUser) {
      return Text(
        content,
        style: AppTypography.body.copyWith(color: AppColors.onPrimary),
      );
    }
    // AI 流式输出中: 纯文本 + 闪烁光标(避免半截 Markdown 抖动)
    if (_isStreaming) {
      return Text.rich(
        TextSpan(
          children: [
            TextSpan(
              text: content,
              style: AppTypography.body.copyWith(
                color: AppColors.textPrimary,
              ),
            ),
            const WidgetSpan(
              alignment: PlaceholderAlignment.baseline,
              baseline: TextBaseline.alphabetic,
              child: BlinkingCursor(color: AppColors.primary),
            ),
          ],
        ),
      );
    }
    // AI 输出完成: 切换为 Markdown 排版
    if (content.trim().isEmpty) {
      return const SizedBox.shrink();
    }
    return CounselorMarkdownBody(content: content);
  }
}
