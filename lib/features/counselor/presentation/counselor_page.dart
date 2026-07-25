import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/chat.dart';
import 'widgets/chat_input_bar.dart';
import 'widgets/chat_message_bubble.dart';
import 'widgets/robot_avatar.dart';

/// AI 导员聊天页面 — 系统主要交互入口。
///
/// 科学边界:顶部标注"模拟模式",来源区标注"模拟资料来源",
/// 无可靠资料时提示用户咨询辅导员或学院办公室。
///
/// 本文件仅负责组合:
/// - 顶部 AppBar(机器人头像 + 标题 + 清空对话)
/// - 消息列表(空 / 流式 / 历史回复)
/// - 快捷问题栏
/// - 输入区(发送/停止)
///
/// 业务逻辑(发送/停止/重新生成/清空)位于 [ChatMessagesNotifier]。
/// 子组件位于 widgets/ 目录。
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
          child: RobotAvatar(size: 30, iconSize: 18),
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
                  ? const EmptyConversation()
                  : ListView.builder(
                      controller: _scrollController,
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
                            child: ChatMessageBubble(
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
            QuickQuestionBar(
              enabled: !isGenerating,
              onPick: _handleQuickQuestion,
            ),
            ChatComposer(
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
