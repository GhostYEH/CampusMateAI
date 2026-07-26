import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/data/services/service_interfaces.dart';
import 'package:campus_companion/features/counselor/presentation/counselor_page.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

void main() {
  /// 构造一个可覆盖 AI 导员服务的 ProviderContainer。
  ///
  /// 开启"减少动态效果"以跳过 StaggeredEnter 动画:
  /// 动画期间 Opacity 可能为 0,Flutter 会用 IgnorePointer 替换子树,
  /// 导致按钮无法接收点击事件。
  ProviderContainer makeContainer({
    CounselorChatService? chatService,
    KnowledgeBaseService? knowledgeBase,
  }) {
    final container = ProviderContainer(
      overrides: [
        // 显式注入 Mock 模式配置(仅开发/测试场景)
        appConfigProvider.overrideWith((ref) {
          return const AppConfig(
            environment: AppEnvironment.development,
            useMockBackend: true,
            useMockExpressionRecognition: true,
            apiBaseUrl: 'http://10.0.2.2:8000',
          );
        }),
        taskRepositoryProvider.overrideWithValue(
          MockTaskRepository(initial: const []),
        ),
        if (knowledgeBase != null)
          knowledgeBaseProvider.overrideWithValue(knowledgeBase),
        if (chatService != null)
          counselorChatProvider.overrideWithValue(chatService),
        reduceMotionProvider.overrideWith((ref) => true),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  Widget wrapWithMaterial(ProviderContainer container, Widget child) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: child,
      ),
    );
  }

  /// 设置手机视口,避免默认 800x600 下部分组件超出可视区域。
  void setPhoneViewport(WidgetTester tester) {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  /// 推进首帧 + 少量时间让初始渲染完成。
  Future<void> pumpIdle(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
  }

  /// 找到底部输入框(Composer 中的 TextField)。
  Finder findComposerInput() => find.byType(TextField);

  /// 找到"发送"按钮(Composer 中的 FilledButton,文本为"发送")。
  Finder findSendButton() => find.ancestor(
        of: find.text('发送'),
        matching: find.byType(FilledButton),
      );

  testWidgets('AI 导员页:渲染 AppBar、状态副标题与初始问候', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // AppBar 标题
    expect(find.text('AI 导员'), findsOneWidget);
    // 参赛版本约束:不向用户暴露"演示模式"字样,
    // Mock 模式下统一显示为"服务暂时不可用"
    expect(find.text('模拟模式 · 校园知识库'), findsNothing);
    expect(find.text('演示模式'), findsNothing);
  });

  testWidgets('AI 导员页:初始问候消息来自 MockData', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 初始问候包含"知夏"(MockData.currentUser.nickname)
    expect(find.textContaining('知夏'), findsWidgets);
  });

  testWidgets('AI 导员页:空输入时点发送不会产生新消息', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 输入框为空,点发送
    await tester.tap(findSendButton());
    await tester.pump();

    // 不应有用户消息气泡(只有初始 AI 问候)
    // 初始状态有 1 条 AI 问候消息
    final userBubbles = find.byWidgetPredicate(
      (w) => w is Text && w.data != null && w.data!.contains('测试问题'),
    );
    expect(userBubbles, findsNothing);
  });

  testWidgets('AI 导员页:输入问题后点发送,出现用户消息与流式回复', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 输入问题
    await tester.enterText(findComposerInput(), '综合测评需要准备什么材料?');
    await tester.pump();

    // 点击发送
    await tester.tap(findSendButton());
    await tester.pump();

    // 用户消息应立即出现
    expect(find.text('综合测评需要准备什么材料?'), findsWidgets);

    // 等待流式回复完成:
    // MockCounselorChatService.send 内部:
    //   1) onTyping + delay 420ms
    //   2) knowledgeBase.search delay 180ms
    //   3) onSources + delay 220ms
    //   4) 逐字流式输出(每字 22ms,回复约 130 字 ~2860ms)
    //   5) onActions
    // 总计约 3680ms,推进 4600ms 确保完成
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));

    // AI 回复应包含"综合测评"关键词(MockCounselorChatService._buildReply)
    expect(find.textContaining('综合测评由'), findsWidgets);
  });

  testWidgets('AI 导员页:点击快捷问题触发对话', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 找到第一个快捷问题 chip(MockData.quickQuestions[0])
    const quickQuestionText = '综合测评需要准备什么材料?';
    final chip = find.text(quickQuestionText);
    expect(chip, findsWidgets);

    // 点击快捷问题(选择最后一个匹配,因为快捷问题栏在底部)
    await tester.ensureVisible(chip.last);
    await tester.pump();
    await tester.tap(chip.last, warnIfMissed: false);
    await tester.pump();

    // 用户消息应出现
    expect(find.text(quickQuestionText), findsWidgets);

    // 推进时间让流式回复完成(约 3680ms,推进 4600ms)
    await tester.pump(const Duration(milliseconds: 4600));

    // AI 回复应出现
    expect(find.textContaining('综合测评由'), findsWidgets);
  });

  testWidgets('AI 导员页:回复完成后显示参考来源区(模拟资料来源)', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 输入并发送
    await tester.enterText(findComposerInput(), '实践学分怎样申请?');
    await tester.pump();
    await tester.tap(findSendButton());
    await tester.pump();

    // 推进时间让流式回复完成(约 3680ms,推进 4600ms)
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));

    // 参考来源区标题应出现
    expect(find.text('参考来源(模拟)'), findsOneWidget);
    // 模拟资料来源标签
    expect(find.textContaining('模拟资料来源'), findsWidgets);
  });

  testWidgets('AI 导员页:回复完成后显示消息底部操作行(复制/重新生成)', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 输入并发送
    await tester.enterText(findComposerInput(), '奖学金申请有什么要求?');
    await tester.pump();
    await tester.tap(findSendButton());
    await tester.pump();

    // 推进时间让流式回复完成
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));

    // 找到 AI 回复(非首条)的底部操作行
    expect(find.text('复制'), findsWidgets);
    // 非首条 AI 消息才显示"重新生成"
    expect(find.text('重新生成'), findsOneWidget);
  });

  testWidgets('AI 导员页:点击"复制"显示成功 SnackBar', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 输入并发送
    await tester.enterText(findComposerInput(), '实践学分怎样申请?');
    await tester.pump();
    await tester.tap(findSendButton());
    await tester.pump();

    // 推进时间让流式回复完成
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));

    // 滚动到底部确保"复制"按钮可见
    final copyButton = find.text('复制').last;
    await tester.ensureVisible(copyButton);
    await tester.pump();
    await tester.tap(copyButton, warnIfMissed: false);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    // 应显示"已复制到剪贴板"
    expect(find.text('已复制到剪贴板'), findsOneWidget);

    // SnackBar 默认 4s 自动消失,推进时间避免 pending timer
    await tester.pump(const Duration(seconds: 5));
  });

  testWidgets('AI 导员页:点击"清空对话"重置为初始问候', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 先发送一条消息(使用不在快捷问题列表中的自定义问题,
    // 避免 find.text 同时匹配到快捷问题 chip)
    const customQuestion = '明天我需要准备什么?';
    await tester.enterText(findComposerInput(), customQuestion);
    await tester.pump();
    await tester.tap(findSendButton());
    await tester.pump();

    // 等待流式回复完成
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));

    // 应有用户消息(仅 1 处,因为该文本不在快捷问题列表中)
    expect(find.text(customQuestion), findsOneWidget);

    // 点击清空对话(AppBar 上的 refresh 图标按钮)
    final clearButton = find.byTooltip('清空对话');
    expect(clearButton, findsOneWidget);
    await tester.tap(clearButton);
    await tester.pump();

    // 用户消息应消失(重置为初始问候)
    expect(find.text(customQuestion), findsNothing);
    // 仍应保留 AI 问候(包含"知夏")
    expect(find.textContaining('知夏'), findsWidgets);
  });

  testWidgets('AI 导员页:流式生成中显示"停止"按钮', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 输入并发送
    await tester.enterText(findComposerInput(), '帮我把今天的任务拆分一下。');
    await tester.pump();
    await tester.tap(findSendButton());
    await tester.pump();

    // 立即推进少量时间(应处于流式中,发送按钮变为停止按钮)
    await tester.pump(const Duration(milliseconds: 100));

    // 流式中应显示"停止"按钮(Composer 中)
    expect(find.text('停止'), findsWidgets);

    // 推进足够时间让流式回复完成,避免 pending timer
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pump(const Duration(milliseconds: 1200));
  });

  testWidgets('AI 导员页:无可靠资料时显示"咨询辅导员"提示', (tester) async {
    setPhoneViewport(tester);
    // 使用一个返回无来源回复的 Mock 服务
    final fakeService = _NoSourceCounselorService();
    final container = makeContainer(chatService: fakeService);
    await tester.pumpWidget(
      wrapWithMaterial(container, const CounselorPage()),
    );
    await pumpIdle(tester);

    // 输入并发送
    await tester.enterText(findComposerInput(), '你好');
    await tester.pump();
    await tester.tap(findSendButton());
    await tester.pump();

    // 推进时间让回复完成
    await tester.pump(const Duration(milliseconds: 600));

    // 应显示"咨询辅导员或学院办公室"提示
    expect(
      find.textContaining('咨询辅导员或学院办公室'),
      findsWidgets,
    );

    // 推进剩余时间避免 pending timer
    await tester.pump(const Duration(milliseconds: 600));
  });
}

/// 一个总是返回无来源回复的 Mock AI 导员服务,
/// 用于测试"无可靠资料时显示咨询辅导员提示"。
class _NoSourceCounselorService implements CounselorChatService {
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
    onTyping?.call();
    await Future.delayed(const Duration(milliseconds: 50));
    onSources?.call(const []);
    await Future.delayed(const Duration(milliseconds: 50));

    const reply = '这是一个无来源的回复。';
    for (final ch in reply.split('')) {
      onChunk?.call(ch);
      await Future.delayed(const Duration(milliseconds: 5));
    }
    onActions?.call(const []);
    return reply;
  }

  @override
  Future<String?> generateProactiveReminder(List<Task> tasks) async => null;

  @override
  void stop() {}
}
