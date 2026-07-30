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
  final bool isRealBackend;
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
          const RobotAvatar(size: 26, iconSize: 15),
          const SizedBox(width: 8),
        ],
        Flexible(
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.76,
            ),
            child: Column(
              crossAxisAlignment:
                  isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                _bubble(context),
                const SizedBox(height: 3),
                Padding(
                  padding: EdgeInsets.only(left: isUser ? 0 : 4),
                  child: Text(
                    AppDateUtils.formatTime(message.timestamp),
                    style: AppTypography.caption.copyWith(
                      fontSize: 10,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ),
                if (!isUser && !_isStreaming) ...[
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
                    const Padding(
                      padding: EdgeInsets.only(left: 4),
                      child: NoSourcesHint(),
                    ),
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
                if (!isUser && _isStreaming)
                  StreamingActions(onStop: onStop),
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
        border: isUser
            ? null
            : Border.all(color: AppColors.border, width: 0.6),
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(14),
          topRight: const Radius.circular(14),
          bottomLeft: Radius.circular(isUser ? 14 : 6),
          bottomRight: Radius.circular(isUser ? 6 : 14),
        ),
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
    if (isUser) {
      return Text(
        content,
        style: AppTypography.body.copyWith(color: AppColors.onPrimary),
      );
    }
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
    if (content.trim().isEmpty) {
      return const SizedBox.shrink();
    }
    return CounselorMarkdownBody(content: content);
  }
}
