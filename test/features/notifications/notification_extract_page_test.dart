import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/notice.dart';
import 'package:campus_companion/data/models/task.dart';
import 'package:campus_companion/data/services/service_interfaces.dart';
import 'package:campus_companion/features/notifications/presentation/notification_extract_page.dart';
import 'package:campus_companion/features/home/presentation/home_page.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

void main() {
  /// 构造一个包含 /home 与 /notifications/extract 的简单 GoRouter,
  /// 使 NotificationExtractPage 在保存后能正常跳转回首页。
  GoRouter buildRouter() {
    return GoRouter(
      initialLocation: '/notifications/extract',
      routes: [
        GoRoute(
          path: '/home',
          builder: (context, state) => const HomePage(),
        ),
        GoRoute(
          path: '/notifications/extract',
          builder: (context, state) => const NotificationExtractPage(),
        ),
      ],
    );
  }

  ProviderContainer makeContainer({
    List<Task>? initialTasks,
    NotificationExtractionService? extractionService,
  }) {
    final container = ProviderContainer(
      overrides: [
        taskRepositoryProvider.overrideWithValue(
          MockTaskRepository(initial: initialTasks ?? const []),
        ),
        if (extractionService != null)
          notificationExtractionProvider.overrideWithValue(extractionService),
        // 开启"减少动态效果",跳过 StaggeredEnter 的 Opacity 动画。
        // 动画期间 Opacity 可能为 0,Flutter 会用 IgnorePointer 替换,
        // 导致按钮无法接收点击事件。
        reduceMotionProvider.overrideWith((ref) => true),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  Widget wrapApp(ProviderContainer container) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        theme: ThemeData.light(useMaterial3: true),
        routerConfig: buildRouter(),
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

  /// 推进足够时间让首帧渲染完成。
  Future<void> pumpIdle(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
  }

  /// 找到主输入框(_InputSection 中的第一个 TextFormField)。
  /// 在结果表单出现前,页面仅有 1 个 TextFormField;出现后会有多个,
  /// 因此在提取前调用本方法定位主输入框。
  Finder findMainInput() => find.byType(TextFormField).first;

  /// 找到智能整理按钮(FilledButton,位于 _InputSection)。
  /// 提取前页面仅 1 个 FilledButton。
  Finder findExtractButton() => find.byType(FilledButton);

  /// 找到保存按钮(通过文本"保存为待办"定位到对应的 FilledButton)。
  Finder findSaveButton() => find.ancestor(
        of: find.text('保存为待办'),
        matching: find.byType(FilledButton),
      );

  testWidgets(
    '通知整理页:渲染标题、Mock 说明横幅、输入区与示例样例',
    (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(wrapApp(container));
      await pumpIdle(tester);

      // AppBar 标题
      expect(find.text('智能整理通知'), findsOneWidget);
      // Mock 提取说明横幅
      expect(find.text('模拟提取,结果可手动修正'), findsOneWidget);
      // 输入区标题与示例样例标签
      expect(find.text('粘贴通知'), findsOneWidget);
      expect(find.text('示例样例'), findsOneWidget);
      // 3 个样例 chip(MockData.noticeSamples 长度为 3)
      expect(find.text('样例 1'), findsOneWidget);
      expect(find.text('样例 2'), findsOneWidget);
      expect(find.text('样例 3'), findsOneWidget);
      // 智能整理按钮
      expect(find.text('智能整理'), findsOneWidget);
    },
  );

  testWidgets('通知整理页:通过 enterText 填充文本框', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(wrapApp(container));
    await pumpIdle(tester);

    // 直接在主输入框输入文本
    await tester.enterText(
      findMainInput(),
      '请2024级学生于10月20日前填写实践申请表,并将申请表和证明材料提交至学院办公室。',
    );
    await tester.pump();

    // 文本框应被填充
    expect(find.textContaining('实践申请表'), findsWidgets);
  });

  testWidgets(
    '通知整理页:点击智能整理触发分步骤处理并显示结果表单',
    (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(wrapApp(container));
      await pumpIdle(tester);

      // 直接输入通知原文,避免 chip 点击命中问题
      await tester.enterText(
        findMainInput(),
        '请2024级学生于10月20日前填写实践申请表,'
        '并将申请表和证明材料提交至学院办公室。',
      );
      await tester.pump();

      // 点击智能整理按钮
      await tester.tap(findExtractButton());
      await tester.pump();

      // 等待分步骤动画与 Mock 服务延迟(6 步 * 360ms = ~2160ms)
      await tester.pump(const Duration(milliseconds: 800));
      await tester.pump(const Duration(milliseconds: 800));
      await tester.pump(const Duration(milliseconds: 800));

      // 至少出现一个步骤行(正在提取或提取完成)
      expect(
        find.byWidgetPredicate(
          (w) => w is Text && (w.data == '正在提取...' || w.data == '提取完成'),
        ),
        findsWidgets,
      );

      // 等待提取完成,结果表单出现
      await tester.pump(const Duration(milliseconds: 400));

      // 结果表单应出现 "任务信息" 与 "办理方式" 卡片标题
      expect(find.text('任务信息'), findsOneWidget);
      expect(find.text('办理方式'), findsOneWidget);
      expect(find.text('所需材料'), findsOneWidget);
      expect(find.text('原文来源'), findsOneWidget);
      // 保存按钮出现
      expect(find.text('保存为待办'), findsOneWidget);
    },
  );

  testWidgets('通知整理页:任务名称为空时点击保存提示错误', (tester) async {
    setPhoneViewport(tester);
    // 使用一个返回空 taskName 的 Mock 提取服务
    final fakeService = _EmptyTaskNameExtractionService();
    final container = makeContainer(extractionService: fakeService);
    await tester.pumpWidget(wrapApp(container));
    await pumpIdle(tester);

    // 填入文本以触发提取
    await tester.enterText(findMainInput(), '某条通知');
    await tester.pump();

    await tester.tap(findExtractButton());
    await tester.pump();

    // 等待提取完成(fakeService 仅 2 步,约 20ms)
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(milliseconds: 200));

    // 任务信息表单应出现(空 taskName)
    expect(find.text('任务信息'), findsOneWidget);

    // 点击保存(滚动到按钮可见后再点击)
    await tester.ensureVisible(findSaveButton());
    await tester.pump();
    await tester.tap(findSaveButton());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // 应提示 "请填写任务名称"
    expect(find.text('请填写任务名称'), findsOneWidget);
  });

  testWidgets('通知整理页:成功保存后显示成功浮层', (tester) async {
    setPhoneViewport(tester);
    final container = makeContainer();
    await tester.pumpWidget(wrapApp(container));
    await pumpIdle(tester);

    // 直接输入通知原文
    await tester.enterText(
      findMainInput(),
      '请2024级学生于10月20日前填写实践申请表,'
      '并将申请表和证明材料提交至学院办公室。',
    );
    await tester.pump();

    // 点击智能整理
    await tester.tap(findExtractButton());
    await tester.pump();

    // 等待提取完成
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pump(const Duration(milliseconds: 400));

    // 确认结果表单已出现
    expect(find.text('任务信息'), findsOneWidget);

    // 任务名称已被自动填入(样例 1 包含实践申请,taskName = "提交实践申请")
    expect(find.textContaining('提交实践申请'), findsWidgets);

    // 滚动到保存按钮可见后点击
    await tester.ensureVisible(findSaveButton());
    await tester.pump();
    await tester.tap(findSaveButton());
    await tester.pump();

    // _save() 现在会先执行重复检测(Mock 150ms 延迟),再实际保存。
    // 推进足够时间让重复检测完成 + _saved=true + 成功动画启动
    await tester.pump(const Duration(milliseconds: 400));

    // 应出现成功浮层 "已保存为待办"(此时 1200ms 跳转 timer 仍 pending)
    expect(find.text('已保存为待办'), findsWidgets);

    // 推进剩余时间让 1200ms timer 完成,触发 context.go('/home')
    await tester.pump(const Duration(milliseconds: 1100));
    await tester.pump(const Duration(milliseconds: 100));

    // SnackBar 默认 4s 自动消失,推进足够时间让其 timer 完成,
    // 避免 test 结束时 "Timer is still pending" 报错。
    await tester.pump(const Duration(seconds: 5));
  });
}

/// 一个返回空 taskName 的 Mock 提取服务,用于测试空任务名场景。
class _EmptyTaskNameExtractionService implements NotificationExtractionService {
  @override
  Future<ExtractedNotice> extract(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  }) async {
    final steps = [
      const ExtractionStep(label: '步骤1', order: 0),
      const ExtractionStep(label: '步骤2', order: 1),
    ];
    for (final step in steps) {
      onProgress?.call(step);
      await Future.delayed(const Duration(milliseconds: 10));
    }
    return const ExtractedNotice(
      taskName: '',
      sourceText: '某条通知',
    );
  }

  @override
  Future<MultiExtractResult> extractMulti(
    String rawNotice, {
    void Function(ExtractionStep step)? onProgress,
  }) async {
    final single = await extract(rawNotice, onProgress: onProgress);
    return MultiExtractResult(
      tasks: [single],
      splitReason: '测试:单任务',
      needsUserConfirmation: false,
    );
  }

  @override
  Future<DuplicateCheckResult> checkDuplicate({
    required String content,
    String? sourceName,
    String? taskName,
    DateTime? deadline,
    required List<RecentNoticeItem> recentNotices,
  }) async {
    return const DuplicateCheckResult(
      isDuplicate: false,
      matches: [],
      contentHash: 'test_hash',
      note: '测试:无重复',
    );
  }
}
