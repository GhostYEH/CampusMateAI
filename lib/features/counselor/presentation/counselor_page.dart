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
/// - 上下文条幅(若从课程/通知/任务进入,显示 "正在询问:xxx")
/// - 消息列表(空 / 流式 / 历史回复)
/// - 快捷问题栏
/// - 输入区(发送/停止)
///
/// 业务逻辑(发送/停止/重新生成/清空)位于 [ChatMessagesNotifier]。
/// 子组件位于 widgets/ 目录。
class CounselorPage extends ConsumerStatefulWidget {
  const CounselorPage({
    super.key,
    this.context = const CounselorContext(),
  });

  /// 路由层注入的对话上下文(课程/班级/任务/通知 ID)。
  final CounselorContext context;

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
    // 注入路由层传入的上下文到 Provider,供 ChatMessagesNotifier 读取
    if (widget.context.hasContext) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        ref.read(counselorContextProvider.notifier).state = widget.context;
      });
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToBottom(animated: false);
      // 进入页面时触发后端状态检查(Real 模式)
      final config = ref.read(appConfigProvider);
      if (!config.useMockBackend) {
        ref.read(backendStatusProvider.notifier).check();
      }
    });
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
    } else if (action.type == SuggestedActionType.createTask) {
      // 后端建议的"创建待办" — 跳转到通知整理页人工确认
      _navigateToExtractWithPrefill(action.payload);
    }
  }

  /// "根据回答创建待办" — 把 AI 回答内容作为预填文本,
  /// 跳转到通知整理页让用户人工确认后再保存。
  ///
  /// 满足"不得直接保存模型生成内容"要求。
  void _navigateToExtractWithPrefill(String? prefilledText) {
    final text = prefilledText?.isNotEmpty == true ? prefilledText! : '';
    context.push('/notifications/extract', extra: text);
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
    // 同时清除上下文 — 用户主动清空对话意味着开始新会话
    ref.read(counselorContextProvider.notifier).state =
        const CounselorContext();
  }

  @override
  Widget build(BuildContext context) {
    final messages = ref.watch(chatMessagesProvider);
    final isGenerating = _isGenerating(messages);
    final config = ref.watch(appConfigProvider);
    final asyncStatus = ref.watch(backendStatusProvider);
    final counselorCtx = ref.watch(counselorContextProvider);

    // 新消息或流式更新时自动滚动到底部
    ref.listen(chatMessagesProvider, (_, __) {
      _scrollToBottom();
    });

    // 根据 BackendStatus 派生状态副标题(不再暴露 Mock / 演示模式字样)
    String statusSubtitle;
    Color statusColor;
    final s = asyncStatus.valueOrNull;
    if (s == null) {
      statusSubtitle = '连接中...';
      statusColor = AppColors.textTertiary;
    } else {
      switch (s.status) {
        case BackendConnectionStatus.connected:
          statusSubtitle = '知识库已就绪';
          statusColor = AppColors.success;
        case BackendConnectionStatus.knowledgeBaseEmpty:
          statusSubtitle = '已连接 · 知识库未初始化';
          statusColor = AppColors.accent;
        case BackendConnectionStatus.demoMode:
          // 不再向用户展示"演示模式"字样,统一显示为服务不可用
          statusSubtitle = '服务暂时不可用';
          statusColor = AppColors.warning;
        case BackendConnectionStatus.disconnected:
          statusSubtitle = '服务暂时不可用';
          statusColor = AppColors.warning;
        case BackendConnectionStatus.unknown:
          statusSubtitle = '...';
          statusColor = AppColors.textTertiary;
      }
    }

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
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: statusColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 4),
                Text(
                  statusSubtitle,
                  style: AppTypography.overline.copyWith(
                    fontSize: 10.5,
                    color: statusColor,
                  ),
                ),
              ],
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
            if (counselorCtx.hasContext) _ContextBanner(context: counselorCtx),
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
                              isRealBackend: !config.useMockBackend,
                              onCopy: () => _copyMessage(msg.content),
                              onRegenerate: () => _regenerate(msg.id),
                              onStop: _handleStop,
                              onAction: _handleAction,
                              onAddToTasks:
                                  msg.sender == MessageSender.counselor
                                      ? () => _navigateToExtractWithPrefill(
                                            msg.content,
                                          )
                                      : null,
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

/// AI 导员对话上下文条幅 — 显示 "正在询问:高等数学 · 第 3 次作业"。
///
/// 仅当 `context.hasContext == true` 时显示。
/// 点击右侧 X 按钮可清除上下文,回到通用问答模式。
class _ContextBanner extends StatelessWidget {
  const _ContextBanner({required this.context});
  final CounselorContext context;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final label = this.context.contextLabel ?? _buildFallbackLabel();
    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.edge,
        AppSpacing.sm,
        AppSpacing.edge,
        0,
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm + 2,
      ),
      decoration: BoxDecoration(
        color: c.primaryContainer.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: c.primarySubtle, width: 0.8),
      ),
      child: Row(
        children: [
          Icon(Icons.school_rounded, size: 16, color: c.primary),
          const SizedBox(width: 6),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '正在询问',
                  style: AppTypography.label.copyWith(
                    color: c.textSecondary,
                    fontSize: 10,
                  ),
                ),
                Text(
                  label,
                  style: AppTypography.body.copyWith(
                    color: c.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// 没有 contextLabel 时的回退文案。
  String _buildFallbackLabel() {
    final parts = <String>[];
    if (context.assignmentId != null) parts.add('当前任务');
    if (context.announcementId != null) parts.add('当前通知');
    if (context.courseId != null) parts.add('当前课程');
    return parts.isEmpty ? '当前上下文' : parts.join(' · ');
  }
}
