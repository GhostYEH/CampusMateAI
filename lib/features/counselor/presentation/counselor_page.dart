import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/utils/date_utils.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/chat.dart';
import '../../../mock/mock_data/mock_data.dart';

/// AI 导员聊天页面 — 系统主要交互入口。
///
/// 科学边界:顶部标注"模拟模式",来源区标注"模拟资料来源",
/// 无可靠资料时提示用户咨询辅导员或学院办公室。
class CounselorPage extends ConsumerStatefulWidget {
  const CounselorPage({super.key});

  @override
  ConsumerState<CounselorPage> createState() => _CounselorPageState();
}

class _CounselorPageState extends ConsumerState<CounselorPage> {
  late final TextEditingController _inputController;
  late final ScrollController _scrollController;

  @override
  void initState() {
    super.initState();
    _inputController = TextEditingController();
    _scrollController = ScrollController();
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _scrollToBottom(animated: false),
    );
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom({bool animated = true}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      final max = _scrollController.position.maxScrollExtent;
      if (max <= 0) return;
      if (animated) {
        _scrollController.animateTo(
          max,
          duration: AppMotion.base,
          curve: AppMotion.standard,
        );
      } else {
        _scrollController.jumpTo(max);
      }
    });
  }

  bool _isGenerating(List<ChatMessage> messages) =>
      messages.any((m) => m.isStreaming);

  void _handleSend() {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;
    final messages = ref.read(chatMessagesProvider);
    if (_isGenerating(messages)) return;
    _inputController.clear();
    ref.read(chatMessagesProvider.notifier).send(text);
  }

  void _handleStop() {
    ref.read(chatMessagesProvider.notifier).stop();
  }

  void _handleQuickQuestion(String question) {
    final messages = ref.read(chatMessagesProvider);
    if (_isGenerating(messages)) return;
    ref.read(chatMessagesProvider.notifier).send(question);
  }

  void _handleAction(SuggestedAction action) {
    if (action.type == SuggestedActionType.navigate) {
      final payload = action.payload;
      if (payload == null || payload.isEmpty) return;
      const tabRoutes = <String>{
        '/home',
        '/tasks',
        '/counselor',
        '/study',
        '/profile',
      };
      if (tabRoutes.contains(payload)) {
        context.go(payload);
      } else {
        context.push(payload);
      }
    } else if (action.type == SuggestedActionType.prefillQuestion) {
      final q = action.payload;
      if (q != null && q.isNotEmpty) {
        _inputController.text = q;
        _inputController.selection = TextSelection.fromPosition(
          TextPosition(offset: _inputController.text.length),
        );
      }
    }
  }

  void _copyMessage(String content) {
    Clipboard.setData(ClipboardData(text: content));
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      const SnackBar(
        content: Text('已复制到剪贴板'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _regenerate(String id) {
    final messages = ref.read(chatMessagesProvider);
    if (_isGenerating(messages)) return;
    ref.read(chatMessagesProvider.notifier).regenerate(id);
  }

  void _clearConversation() {
    ref.read(chatMessagesProvider.notifier).clear();
  }

  @override
  Widget build(BuildContext context) {
    final messages = ref.watch(chatMessagesProvider);
    final isGenerating = _isGenerating(messages);

    // 新消息或流式更新时自动滚动到底部
    ref.listen(chatMessagesProvider, (_, __) {
      _scrollToBottom();
    });

    return Scaffold(
      backgroundColor: AppColors.bgBase,
      appBar: AppBar(
        automaticallyImplyLeading: false,
        backgroundColor: AppColors.bgSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleSpacing: 8,
        leading: const Padding(
          padding: EdgeInsets.all(10),
          child: _RobotAvatar(size: 30, iconSize: 18),
        ),
        leadingWidth: 44,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('AI 导员', style: AppTypography.subtitle),
            Text(
              '模拟模式 · 校园知识库',
              style: AppTypography.overline.copyWith(fontSize: 10.5),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: '清空对话',
            onPressed: _clearConversation,
            icon: const Icon(Icons.refresh_rounded, size: 22),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: messages.isEmpty
                  ? const _EmptyConversation()
                  : ListView.builder(
                      controller: _scrollController,
                      reverse: false,
                      keyboardDismissBehavior:
                          ScrollViewKeyboardDismissBehavior.onDrag,
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.edge,
                        12,
                        AppSpacing.edge,
                        12,
                      ),
                      itemCount: messages.length,
                      itemBuilder: (context, index) {
                        final msg = messages[index];
                        return StaggeredEnter(
                          key: ValueKey('msg_item_${msg.id}'),
                          child: Padding(
                            padding: const EdgeInsets.only(bottom: 14),
                            child: _MessageBubble(
                              key: ValueKey(msg.id),
                              message: msg,
                              isFirst: index == 0,
                              onCopy: () => _copyMessage(msg.content),
                              onRegenerate: () => _regenerate(msg.id),
                              onStop: _handleStop,
                              onAction: _handleAction,
                            ),
                          ),
                        );
                      },
                    ),
            ),
            _QuickQuestionBar(
              enabled: !isGenerating,
              onPick: _handleQuickQuestion,
            ),
            _Composer(
              controller: _inputController,
              isGenerating: isGenerating,
              onSend: _handleSend,
              onStop: _handleStop,
            ),
          ],
        ),
      ),
    );
  }
}

// ===== 消息气泡 =====

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    super.key,
    required this.message,
    required this.isFirst,
    required this.onCopy,
    required this.onRegenerate,
    required this.onStop,
    required this.onAction,
  });

  final ChatMessage message;
  final bool isFirst;
  final VoidCallback onCopy;
  final VoidCallback onRegenerate;
  final VoidCallback onStop;
  final void Function(SuggestedAction) onAction;

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
          const _RobotAvatar(size: 28, iconSize: 16),
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
                  if (message.sources.isNotEmpty)
                    _SourceList(sources: message.sources)
                  else if (!isFirst && message.content.isNotEmpty)
                    const _NoSourcesHint(),
                  if (message.actions.isNotEmpty)
                    _ActionChips(
                      actions: message.actions,
                      onAction: onAction,
                    ),
                  _MessageActions(
                    onCopy: onCopy,
                    onRegenerate: onRegenerate,
                    canRegenerate: !isFirst,
                  ),
                ],
                if (!isUser && _isStreaming) _StreamingActions(onStop: onStop),
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
          showTypingDots ? const _TypingDots() : _contentText(content, isUser),
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
    return Text.rich(
      TextSpan(
        children: [
          TextSpan(
            text: content,
            style: AppTypography.body.copyWith(
              color: isUser ? AppColors.onPrimary : AppColors.textPrimary,
            ),
          ),
          if (!isUser && _isStreaming)
            WidgetSpan(
              alignment: PlaceholderAlignment.baseline,
              baseline: TextBaseline.alphabetic,
              child: _BlinkingCursor(
                color: isUser ? AppColors.onPrimary : AppColors.primary,
              ),
            ),
        ],
      ),
    );
  }
}

// ===== 机器人头像 =====

class _RobotAvatar extends StatelessWidget {
  const _RobotAvatar({this.size = 28, this.iconSize = 16});

  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: AppColors.primarySubtle,
        shape: BoxShape.circle,
      ),
      child: Icon(
        Icons.smart_toy_rounded,
        color: AppColors.primary,
        size: iconSize,
      ),
    );
  }
}

// ===== 流式打字光标(闪烁竖线 ▍)=====

class _BlinkingCursor extends StatefulWidget {
  const _BlinkingCursor({this.color = AppColors.textPrimary});

  final Color color;

  @override
  State<_BlinkingCursor> createState() => _BlinkingCursorState();
}

class _BlinkingCursorState extends State<_BlinkingCursor>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 560),
      vsync: this,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Opacity(
          opacity: (0.2 + 0.8 * _controller.value).clamp(0.0, 1.0),
          child: Padding(
            padding: const EdgeInsets.only(left: 1),
            child: Text(
              '▍',
              style: AppTypography.body.copyWith(
                color: widget.color,
                fontWeight: FontWeight.w700,
                height: 1.2,
              ),
            ),
          ),
        );
      },
    );
  }
}

// ===== 正在输入(三点跳动,内容为空时显示)=====

class _TypingDots extends StatefulWidget {
  const _TypingDots();

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Widget _dot(int index) {
    final begin = (index * 0.2).clamp(0.0, 0.8);
    final end = (begin + 0.4).clamp(0.0, 1.0);
    final tween = Tween<double>(begin: 0.35, end: 1.0)
        .chain(CurveTween(curve: Curves.easeInOut));
    final anim = tween.animate(
      CurvedAnimation(
        parent: _controller,
        curve: Interval(begin, end, curve: Curves.easeInOut),
      ),
    );
    return AnimatedBuilder(
      animation: anim,
      builder: (context, child) {
        return Opacity(opacity: anim.value, child: child);
      },
      child: Container(
        width: 6,
        height: 6,
        margin: const EdgeInsets.symmetric(horizontal: 1.5),
        decoration: const BoxDecoration(
          color: AppColors.textTertiary,
          shape: BoxShape.circle,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 16,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(3, _dot),
      ),
    );
  }
}

// ===== 参考来源区 =====

class _SourceList extends StatelessWidget {
  const _SourceList({required this.sources});

  final List<KnowledgeSource> sources;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.bgSunken,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: AppColors.border, width: 0.6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.menu_book_rounded,
                size: 13,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                '参考来源(模拟)',
                style: AppTypography.label.copyWith(fontSize: 10.5),
              ),
            ],
          ),
          const SizedBox(height: 8),
          for (var i = 0; i < sources.length; i++) ...[
            _SourceItem(source: sources[i]),
            if (i != sources.length - 1) const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _SourceItem extends StatelessWidget {
  const _SourceItem({required this.source});

  final KnowledgeSource source;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          source.title,
          style: AppTypography.bodyStrong.copyWith(fontSize: 12.5),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 3),
        Wrap(
          spacing: 5,
          runSpacing: 2,
          children: [
            _tag(source.source),
            _tag('更新于 ${AppDateUtils.formatDate(source.updatedAt)}'),
          ],
        ),
        if (source.snippet != null && source.snippet!.isNotEmpty) ...[
          const SizedBox(height: 4),
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

  Widget _tag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AppColors.border, width: 0.5),
      ),
      child: Text(
        text,
        style: AppTypography.overline.copyWith(fontSize: 9.5),
      ),
    );
  }
}

// ===== 无可靠资料提示 =====

class _NoSourcesHint extends StatelessWidget {
  const _NoSourcesHint();

  @override
  Widget build(BuildContext context) {
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
              '该问题暂无可靠资料,建议咨询辅导员或学院办公室',
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

// ===== 建议操作 chips =====

class _ActionChips extends StatelessWidget {
  const _ActionChips({required this.actions, required this.onAction});

  final List<SuggestedAction> actions;
  final void Function(SuggestedAction) onAction;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      child: Wrap(
        spacing: 6,
        runSpacing: 6,
        children: [
          for (final a in actions)
            ActionChip(
              label: Text(
                a.label,
                style: AppTypography.label.copyWith(fontSize: 11.5),
              ),
              onPressed: () => onAction(a),
              backgroundColor: AppColors.primarySubtle,
              side: const BorderSide(
                color: AppColors.primarySubtle,
                width: 0.5,
              ),
              labelPadding: const EdgeInsets.symmetric(horizontal: 2),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              visualDensity: VisualDensity.compact,
            ),
        ],
      ),
    );
  }
}

// ===== AI 消息底部操作行(复制 / 重新生成)=====

class _MessageActions extends StatelessWidget {
  const _MessageActions({
    required this.onCopy,
    required this.onRegenerate,
    required this.canRegenerate,
  });

  final VoidCallback onCopy;
  final VoidCallback onRegenerate;
  final bool canRegenerate;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 6),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _inlineButton(
            icon: Icons.copy_rounded,
            label: '复制',
            onTap: onCopy,
          ),
          if (canRegenerate) ...[
            const SizedBox(width: 6),
            _inlineButton(
              icon: Icons.refresh_rounded,
              label: '重新生成',
              onTap: onRegenerate,
            ),
          ],
        ],
      ),
    );
  }

  Widget _inlineButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.xs),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: AppColors.textTertiary),
            const SizedBox(width: 3),
            Text(
              label,
              style: AppTypography.overline.copyWith(fontSize: 10),
            ),
          ],
        ),
      ),
    );
  }
}

// ===== 流式时停止生成按钮 =====

class _StreamingActions extends StatelessWidget {
  const _StreamingActions({required this.onStop});

  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 6),
      child: InkWell(
        onTap: onStop,
        borderRadius: BorderRadius.circular(AppRadius.xs),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.stop_circle_rounded,
                size: 13,
                color: AppColors.danger,
              ),
              const SizedBox(width: 3),
              Text(
                '停止生成',
                style: AppTypography.overline.copyWith(
                  fontSize: 10,
                  color: AppColors.danger,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ===== 空对话占位 =====

class _EmptyConversation extends StatelessWidget {
  const _EmptyConversation();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
              color: AppColors.primarySubtle,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.smart_toy_rounded,
              size: 32,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 16),
          const Text('开始和 AI 导员对话吧', style: AppTypography.subtitle),
          const SizedBox(height: 6),
          const Text('模拟模式 · 校园知识库', style: AppTypography.caption),
        ],
      ),
    );
  }
}

// ===== 快捷问题栏 =====

class _QuickQuestionBar extends StatelessWidget {
  const _QuickQuestionBar({required this.enabled, required this.onPick});

  final bool enabled;
  final void Function(String) onPick;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 38,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.edge,
          vertical: 2,
        ),
        itemCount: MockData.quickQuestions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final q = MockData.quickQuestions[index];
          return ActionChip(
            label: Text(
              q,
              style: AppTypography.label.copyWith(fontSize: 11.5),
            ),
            onPressed: enabled ? () => onPick(q) : null,
            backgroundColor: AppColors.bgSurface,
            side: const BorderSide(color: AppColors.border, width: 0.6),
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            visualDensity: VisualDensity.compact,
          );
        },
      ),
    );
  }
}

// ===== 输入区 =====

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.isGenerating,
    required this.onSend,
    required this.onStop,
  });

  final TextEditingController controller;
  final bool isGenerating;
  final VoidCallback onSend;
  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        6,
        AppSpacing.edge,
        8,
      ),
      decoration: const BoxDecoration(
        color: AppColors.bgSurface,
        border: Border(
          top: BorderSide(color: AppColors.border, width: 0.6),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => onSend(),
              style: AppTypography.body,
              decoration: InputDecoration(
                hintText: '问问 AI 导员...',
                hintStyle: AppTypography.body.copyWith(
                  color: AppColors.textTertiary,
                ),
                filled: true,
                fillColor: AppColors.bgSunken,
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 10,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                  borderSide: BorderSide.none,
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                  borderSide: const BorderSide(
                    color: AppColors.primary,
                    width: 1.2,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          if (isGenerating)
            FilledButton.icon(
              onPressed: onStop,
              icon: const Icon(Icons.stop_rounded, size: 18),
              label: const Text('停止'),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.danger,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                ),
              ),
            )
          else
            FilledButton.icon(
              onPressed: onSend,
              icon: const Icon(Icons.send_rounded, size: 18),
              label: const Text('发送'),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: AppColors.onPrimary,
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
