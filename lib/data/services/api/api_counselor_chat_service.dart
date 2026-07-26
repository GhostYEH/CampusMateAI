import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../../../data/models/models.dart';
import '../service_interfaces.dart';
import 'api_client.dart';

/// 真实后端 AI 导员聊天服务 — 调用 FastAPI SSE 流式接口。
///
/// SSE 事件协议(与后端 `/api/v1/counselor/chat` 对齐):
/// - `event: sources` data: {"sources": [...]}
/// - `event: chunk`    data: {"text": "增量内容", "mode": "llm|retrieval_summary|no_knowledge"}
/// - `event: done`     data: {完整 ChatFinalMeta}
/// - `event: error`     data: {"code": "...", "message": "..."}
///
/// 网络中断/后端不可用:
/// - 保留已生成内容
/// - 通过 [streamError] 返回温和错误信息
class ApiCounselorChatService implements CounselorChatService {
  ApiCounselorChatService(this._client);

  final ApiClient _client;

  CancelToken? _cancelToken;

  /// SSE 事件块分隔符正则(\r\n\r\n 或 \n\n)。
  static final RegExp _sepRegex = RegExp(r'\r?\n\r?\n');

  @override
  Future<String> send(
    String message, {
    required String conversationId,
    void Function(String chunk)? onChunk,
    void Function(List<KnowledgeSource> sources)? onSources,
    void Function(List<SuggestedAction> actions)? onActions,
    void Function(ChatFinalMeta meta)? onFinalMeta,
    void Function()? onTyping,
  }) async {
    _cancelToken = CancelToken();

    final fullContent = StringBuffer();
    List<KnowledgeSource> finalSources = [];
    List<SuggestedAction> finalActions = [];

    try {
      final response = _client.dio.post<ResponseBody>(
        '/api/v1/counselor/chat',
        data: {
          'message': message,
          'conversation_id': conversationId,
          'stream': true,
        },
        options: Options(
          responseType: ResponseType.stream,
          headers: {'Accept': 'text/event-stream'},
        ),
        cancelToken: _cancelToken,
      );

      final stream = await response;
      // 处理 SSE 流:使用缓冲区累积未完成的块
      // (一个 SSE 事件可能跨多个 TCP chunk 传输)
      final buffer = StringBuffer();
      await for (final chunk in stream.data!.stream) {
        buffer.write(utf8.decode(chunk));
        final content = buffer.toString();
        // 找出所有完整事件块的分隔符(\r\n\r\n 或 \n\n)
        final sepMatches = _sepRegex.allMatches(content).toList();
        if (sepMatches.isEmpty) continue;

        // 最后一个分隔符之前的内容都是完整事件块
        final lastSepEnd = sepMatches.last.end;
        final complete = content.substring(0, lastSepEnd);
        // 剩余部分(可能为空,或为下一个事件的开始)保留到 buffer
        final remaining = content.substring(lastSepEnd);
        buffer
          ..clear()
          ..write(remaining);

        final events = _parseSse(complete);
        for (final ev in events) {
          switch (ev.event) {
            case 'sources':
              finalSources = _parseSources(ev.data);
              onSources?.call(finalSources);
              break;
            case 'chunk':
              final chunkText = (ev.data['text'] as String?) ?? '';
              if (chunkText.isNotEmpty) {
                fullContent.write(chunkText);
                onChunk?.call(chunkText);
              }
              onTyping?.call();
              break;
            case 'done':
              final answer = (ev.data['answer'] as String?) ?? '';
              if (answer.isNotEmpty && fullContent.isEmpty) {
                fullContent.write(answer);
                onChunk?.call(answer);
              }
              final sources = _parseSources(ev.data);
              if (sources.isNotEmpty) {
                finalSources = sources;
                onSources?.call(finalSources);
              }
              final actions = _parseActions(ev.data);
              if (actions.isNotEmpty) {
                finalActions = actions;
                onActions?.call(finalActions);
              } else if (finalActions.isNotEmpty) {
                onActions?.call(finalActions);
              }
              // 解析最终元数据(mode / evidence_level / confidence / warnings)
              final meta = _parseFinalMeta(ev.data, finalSources);
              if (meta != null) {
                onFinalMeta?.call(meta);
              }
              break;
            case 'error':
              final msg = (ev.data['message'] as String?) ?? '生成失败,请重试';
              // 不抛异常,保留已生成内容,UI 通过 streamError 显示
              throw _SseErrorException(msg);
            default:
              break;
          }
        }
      }

      // 处理 buffer 中剩余的完整事件(流结束时)
      if (buffer.toString().trim().isNotEmpty) {
        final events = _parseSse(buffer.toString());
        for (final ev in events) {
          switch (ev.event) {
            case 'done':
              final answer = (ev.data['answer'] as String?) ?? '';
              if (answer.isNotEmpty && fullContent.isEmpty) {
                fullContent.write(answer);
                onChunk?.call(answer);
              }
              final sources = _parseSources(ev.data);
              if (sources.isNotEmpty) {
                finalSources = sources;
                onSources?.call(finalSources);
              }
              final actions = _parseActions(ev.data);
              if (actions.isNotEmpty) {
                finalActions = actions;
                onActions?.call(finalActions);
              }
              final meta = _parseFinalMeta(ev.data, finalSources);
              if (meta != null) {
                onFinalMeta?.call(meta);
              }
              break;
            default:
              break;
          }
        }
      }

      // 若没有任何事件,后端可能返回了非流式 JSON
      if (fullContent.isEmpty) {
        return '';
      }
      return fullContent.toString();
    } on DioException catch (e) {
      if (e.type == DioExceptionType.cancel) {
        // 用户主动停止:保留已生成内容,正常返回
        return fullContent.toString();
      }
      final apiErr = ApiException.fromDio(e);
      throw apiErr;
    } on _SseErrorException {
      // SSE 错误事件:保留已生成内容,正常返回(由 UI 显示 streamError)
      return fullContent.toString();
    } finally {
      _cancelToken = null;
    }
  }

  /// 从 `done` 事件 data 解析最终元数据。
  ///
  /// 推导 hasUserDocs / hasDemoDocs: 通过 sources 列表中的 isDemo 标志判断。
  ChatFinalMeta? _parseFinalMeta(
    Map<String, dynamic> data,
    List<KnowledgeSource> sources,
  ) {
    final mode = (data['mode'] as String?) ?? '';
    if (mode.isEmpty) return null;
    final evidenceLevel = (data['evidence_level'] as String?) ?? 'low';
    final confidence = ((data['confidence'] as num?) ?? 0).toDouble();
    final warnings = ((data['warnings'] as List?) ?? [])
        .map((e) => e.toString())
        .toList(growable: false);
    final needsHumanConfirmation =
        (data['needs_human_confirmation'] as bool?) ?? false;
    final hasUserDocs = sources.any((s) => !s.isDemo);
    final hasDemoDocs = sources.any((s) => s.isDemo);
    return ChatFinalMeta(
      mode: mode,
      evidenceLevel: evidenceLevel,
      confidence: confidence,
      warnings: warnings,
      needsHumanConfirmation: needsHumanConfirmation,
      hasUserDocs: hasUserDocs,
      hasDemoDocs: hasDemoDocs,
    );
  }

  @override
  Future<String?> generateProactiveReminder(List<Task> tasks) async {
    // 真实后端不实现主动提醒,返回 null(由 Mock 模式或后续接入)
    return null;
  }

  @override
  void stop() {
    _cancelToken?.cancel('用户主动停止生成');
    _cancelToken = null;
  }

  // ===== SSE 解析 =====

  List<_SseEvent> _parseSse(String text) {
    final events = <_SseEvent>[];
    // SSE 以两个换行分隔事件块
    final blocks = text.split(RegExp(r'\r?\n\r?\n'));
    for (final block in blocks) {
      if (block.trim().isEmpty) continue;
      String? eventName;
      String? dataStr;
      for (final line in block.split(RegExp(r'\r?\n'))) {
        if (line.startsWith('event:')) {
          eventName = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
          dataStr = line.substring(5).trim();
        }
      }
      if (eventName == null && dataStr == null) continue;
      Map<String, dynamic> data = {};
      if (dataStr != null && dataStr.isNotEmpty) {
        try {
          final decoded = jsonDecode(dataStr);
          if (decoded is Map<String, dynamic>) {
            data = decoded;
          }
        } catch (_) {
          // 非合法 JSON,跳过
          continue;
        }
      }
      events.add(_SseEvent(eventName ?? 'message', data));
    }
    return events;
  }

  List<KnowledgeSource> _parseSources(Map<String, dynamic> data) {
    final sources = <KnowledgeSource>[];
    final list = (data['sources'] as List?) ?? [];
    for (final s in list) {
      if (s is! Map<String, dynamic>) continue;
      final title = (s['title'] as String?) ?? '未命名文档';
      final publishedAtStr = s['published_at'] as String?;
      final updatedAtStr = s['updated_at'] as String?;
      final dtStr = updatedAtStr ?? publishedAtStr;
      DateTime dt = DateTime.now();
      if (dtStr != null && dtStr.isNotEmpty) {
        try {
          dt = DateTime.parse(dtStr);
        } catch (_) {
          // 保留默认值
        }
      }
      DateTime? publishedAt;
      if (publishedAtStr != null && publishedAtStr.isNotEmpty) {
        try {
          publishedAt = DateTime.parse(publishedAtStr);
        } catch (_) {
          publishedAt = null;
        }
      }
      // 标注来源是否为过期资料
      final isExpired = s['is_expired'] as bool? ?? false;
      final isOfficial = s['is_official'] as bool? ?? false;
      final isDemo = s['is_demo'] as bool? ?? false;
      final dept =
          (s['source_department'] as String?)?.trim().isNotEmpty == true
              ? (s['source_department'] as String).trim()
              : (isDemo ? '仿真演示资料' : '校园资料');
      final sourceLabel =
          isExpired ? '$dept · 已过期' : (isOfficial ? '$dept · 官方' : dept);

      sources.add(
        KnowledgeSource(
          id: (s['document_id'] as String?) ?? '',
          title: title,
          updatedAt: dt,
          source: sourceLabel,
          snippet: (s['excerpt'] as String?)?.trim(),
          relevance: ((s['relevance_score'] as num?) ?? 0).toDouble(),
          sourceDepartment:
              (s['source_department'] as String?)?.trim().isEmpty == true
                  ? null
                  : (s['source_department'] as String?)?.trim(),
          publishedAt: publishedAt,
          version: (s['version'] as String?)?.trim().isEmpty == true
              ? null
              : (s['version'] as String?)?.trim(),
          applicableStudents:
              (s['applicable_students'] as String?)?.trim().isEmpty == true
                  ? null
                  : (s['applicable_students'] as String?)?.trim(),
          section: (s['section'] as String?)?.trim().isEmpty == true
              ? null
              : (s['section'] as String?)?.trim(),
          isOfficial: isOfficial,
          isExpired: isExpired,
          isDemo: isDemo,
          evidenceLevel: (s['evidence_level'] as String?) ?? 'medium',
        ),
      );
    }
    return sources;
  }

  List<SuggestedAction> _parseActions(Map<String, dynamic> data) {
    final actions = <SuggestedAction>[];
    final list = (data['suggested_actions'] as List?) ?? [];
    for (final a in list) {
      if (a is! Map<String, dynamic>) continue;
      final id = (a['id'] as String?) ?? 'act_${actions.length}';
      final label = (a['label'] as String?) ?? '';
      if (label.isEmpty) continue;
      final typeStr = (a['type'] as String?) ?? 'none';
      SuggestedActionType type;
      switch (typeStr) {
        case 'navigate':
          type = SuggestedActionType.navigate;
          break;
        case 'prefillQuestion':
          type = SuggestedActionType.prefillQuestion;
          break;
        case 'createTask':
          type = SuggestedActionType.createTask;
          break;
        default:
          type = SuggestedActionType.none;
      }
      actions.add(
        SuggestedAction(
          id: id,
          label: label,
          type: type,
          payload: a['payload'] as String?,
        ),
      );
    }
    return actions;
  }
}

class _SseEvent {
  const _SseEvent(this.event, this.data);
  final String event;
  final Map<String, dynamic> data;
}

class _SseErrorException implements Exception {
  const _SseErrorException(this.message);
  final String message;
  @override
  String toString() => message;
}
