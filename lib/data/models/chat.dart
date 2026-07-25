import 'package:equatable/equatable.dart';

/// 消息发送方。
enum MessageSender { user, counselor, system }

/// AI 导员回答的"建议操作"按钮。
class SuggestedAction extends Equatable {
  const SuggestedAction({
    required this.id,
    required this.label,
    this.type = SuggestedActionType.navigate,
    this.payload,
  });

  final String id;
  final String label;
  final SuggestedActionType type;
  final String? payload; // 路由路径或预填问题

  @override
  List<Object?> get props => [id, label, type, payload];
}

enum SuggestedActionType { navigate, prefillQuestion, createTask, none }

/// 知识库引用来源。
///
/// Mock 阶段标注 "模拟资料来源",不得伪造真实学校政策文件。
class KnowledgeSource extends Equatable {
  const KnowledgeSource({
    required this.id,
    required this.title,
    required this.updatedAt,
    this.source = '模拟资料来源',
    this.url,
    this.snippet,
    this.relevance = 0,
  });

  final String id;
  final String title; // 文件名称
  final DateTime updatedAt; // 更新时间
  final String source; // 来源标注
  final String? url;
  final String? snippet; // 引用片段
  final double relevance; // 相关度 0~1

  @override
  List<Object?> get props =>
      [id, title, updatedAt, source, url, snippet, relevance];
}

/// 聊天消息。
class ChatMessage extends Equatable {
  const ChatMessage({
    required this.id,
    required this.sender,
    required this.content,
    required this.timestamp,
    this.sources = const [],
    this.actions = const [],
    this.isStreaming = false,
    this.streamError,
  });

  final String id;
  final MessageSender sender;
  final String content;
  final DateTime timestamp;
  final List<KnowledgeSource> sources; // 引用来源
  final List<SuggestedAction> actions; // 建议操作
  final bool isStreaming; // 是否正在流式输出
  final String? streamError; // 生成错误

  ChatMessage copyWith({
    String? id,
    MessageSender? sender,
    String? content,
    DateTime? timestamp,
    List<KnowledgeSource>? sources,
    List<SuggestedAction>? actions,
    bool? isStreaming,
    String? streamError,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      sender: sender ?? this.sender,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      sources: sources ?? this.sources,
      actions: actions ?? this.actions,
      isStreaming: isStreaming ?? this.isStreaming,
      streamError: streamError ?? this.streamError,
    );
  }

  @override
  List<Object?> get props => [
        id,
        sender,
        content,
        timestamp,
        sources,
        actions,
        isStreaming,
        streamError,
      ];
}
