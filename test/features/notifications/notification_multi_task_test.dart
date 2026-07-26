import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/notice.dart';
import 'package:campus_companion/data/services/service_interfaces.dart';
import 'package:campus_companion/features/notifications/presentation/notification_extract_page.dart';
import 'package:campus_companion/features/notifications/presentation/widgets/duplicate_warning_banner.dart';
import 'package:campus_companion/features/notifications/presentation/widgets/multi_task_selector.dart';
import 'package:campus_companion/features/notifications/presentation/widgets/reminder_section.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

void main() {
  /// 包裹子组件并提供 MaterialApp + Directionality,便于直接 pump 单个 widget。
  Widget wrap(Widget child) {
    return MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: Scaffold(
        body: SingleChildScrollView(child: child),
      ),
    );
  }

  // ============================================================
  // MultiTaskSelector — 直接 pump widget
  // ============================================================
  group('MultiTaskSelector', () {
    MultiExtractResult makeResult({
      int taskCount = 2,
      String splitReason = '识别到 2 个独立截止时间,已拆分为多任务',
      bool needsUserConfirmation = false,
    }) {
      return MultiExtractResult(
        tasks: List.generate(taskCount, (i) {
          return ExtractedNotice(
            taskName: '任务 ${i + 1}',
            deadline: DateTime(2024, 8, 1 + i),
          );
        }),
        splitReason: splitReason,
        needsUserConfirmation: needsUserConfirmation,
      );
    }

    testWidgets(
      'shows "已拆分为多个任务" when multiple tasks',
      (tester) async {
        final result = makeResult(taskCount: 2);
        await tester.pumpWidget(wrap(
          MultiTaskSelector(
            result: result,
            selectedIndex: 0,
            onSelect: (_) {},
          ),
        ),);

        expect(find.text('已拆分为多个任务'), findsOneWidget);
      },
    );

    testWidgets('shows task count badge "2 个任务"', (tester) async {
      final result = makeResult(taskCount: 2);
      await tester.pumpWidget(wrap(
        MultiTaskSelector(
          result: result,
          selectedIndex: 0,
          onSelect: (_) {},
        ),
      ),);

      expect(find.text('2 个任务'), findsOneWidget);
    });

    testWidgets('shows split reason text', (tester) async {
      const reason = '识别到 2 个独立截止时间,已拆分为多任务';
      final result = makeResult(splitReason: reason);
      await tester.pumpWidget(wrap(
        MultiTaskSelector(
          result: result,
          selectedIndex: 0,
          onSelect: (_) {},
        ),
      ),);

      expect(find.text(reason), findsOneWidget);
    });

    testWidgets(
      'shows "需要人工确认" hint when needsUserConfirmation=true',
      (tester) async {
        final result = makeResult(needsUserConfirmation: true);
        await tester.pumpWidget(wrap(
          MultiTaskSelector(
            result: result,
            selectedIndex: 0,
            onSelect: (_) {},
          ),
        ),);

        expect(
          find.text('拆分结果仅供参考,请人工确认各任务字段后再保存'),
          findsOneWidget,
        );
      },
    );

    testWidgets('tapping a task chip calls onSelect callback', (tester) async {
      final result = makeResult(taskCount: 2);
      int? selected;
      await tester.pumpWidget(wrap(
        MultiTaskSelector(
          result: result,
          selectedIndex: 0,
          onSelect: (index) => selected = index,
        ),
      ),);

      // 点击第二个任务 chip(通过任务名定位)
      final secondChip = find.text('任务 2');
      expect(secondChip, findsOneWidget);
      await tester.tap(secondChip);
      await tester.pump();

      expect(selected, equals(1));
    });

    testWidgets('shows "当前编辑第 N 个任务" text', (tester) async {
      final result = makeResult(taskCount: 2);
      await tester.pumpWidget(wrap(
        MultiTaskSelector(
          result: result,
          selectedIndex: 1,
          onSelect: (_) {},
        ),
      ),);

      expect(
        find.text('当前编辑第 2 个任务,保存后将单独生成一条待办'),
        findsOneWidget,
      );
    });
  });

  // ============================================================
  // DuplicateWarningBanner — 直接 pump widget
  // ============================================================
  group('DuplicateWarningBanner', () {
    DuplicateCheckResult makeResult({
      bool isDuplicate = true,
      List<DuplicateMatch> matches = const [],
    }) {
      return DuplicateCheckResult(
        isDuplicate: isDuplicate,
        matches: matches,
        contentHash: 'hash_test',
        note: '仅提示可能重复,不会自动覆盖原待办。请人工确认后决定是否继续保存。',
      );
    }

    DuplicateMatch makeMatch({
      String title = '已存在待办',
      double similarity = 0.85,
      List<String> reasons = const ['content_similarity'],
    }) {
      return DuplicateMatch(
        noticeId: 'notice_1',
        title: title,
        similarity: similarity,
        reasons: reasons,
      );
    }

    testWidgets(
      'shows "可能存在重复通知" when isDuplicate=true',
      (tester) async {
        final result = makeResult(matches: [makeMatch()]);
        await tester.pumpWidget(wrap(
          DuplicateWarningBanner(result: result, onDismiss: () {}),
        ),);

        expect(find.text('可能存在重复通知'), findsOneWidget);
      },
    );

    testWidgets('shows match titles', (tester) async {
      final result = makeResult(
        matches: [makeMatch(title: '提交实践申请表')],
      );
      await tester.pumpWidget(wrap(
        DuplicateWarningBanner(result: result, onDismiss: () {}),
      ),);

      expect(find.text('提交实践申请表'), findsOneWidget);
    });

    testWidgets('shows similarity percentage', (tester) async {
      final result = makeResult(
        matches: [makeMatch(similarity: 0.85)],
      );
      await tester.pumpWidget(wrap(
        DuplicateWarningBanner(result: result, onDismiss: () {}),
      ),);

      expect(find.text('相似度 85%'), findsOneWidget);
    });

    testWidgets('shows "仍要保存" button', (tester) async {
      final result = makeResult(matches: [makeMatch()]);
      await tester.pumpWidget(wrap(
        DuplicateWarningBanner(result: result, onDismiss: () {}),
      ),);

      expect(find.text('仍要保存'), findsOneWidget);
    });

    testWidgets('tapping "仍要保存" calls onDismiss', (tester) async {
      final result = makeResult(matches: [makeMatch()]);
      bool dismissed = false;
      await tester.pumpWidget(wrap(
        DuplicateWarningBanner(
          result: result,
          onDismiss: () => dismissed = true,
        ),
      ),);

      await tester.tap(find.text('仍要保存'));
      await tester.pump();

      expect(dismissed, isTrue);
    });

    testWidgets(
      'returns SizedBox.shrink when isDuplicate=false',
      (tester) async {
        final result = makeResult(isDuplicate: false);
        await tester.pumpWidget(wrap(
          DuplicateWarningBanner(result: result, onDismiss: () {}),
        ),);

        expect(find.text('可能存在重复通知'), findsNothing);
        expect(find.text('仍要保存'), findsNothing);
      },
    );
  });

  // ============================================================
  // ReminderSection — 直接 pump widget
  // ============================================================
  group('ReminderSection', () {
    testWidgets('shows "截止提醒" title', (tester) async {
      await tester.pumpWidget(wrap(
        ReminderSection(
          enabled: false,
          leadMinutes: 120,
          deadline: null,
          onToggle: (_) {},
          onLeadChanged: (_) {},
        ),
      ),);

      expect(find.text('截止提醒'), findsOneWidget);
    });

    testWidgets('switch is disabled when deadline is null', (tester) async {
      await tester.pumpWidget(wrap(
        ReminderSection(
          enabled: false,
          leadMinutes: 120,
          deadline: null,
          onToggle: (_) {},
          onLeadChanged: (_) {},
        ),
      ),);

      final sw = tester.widget<Switch>(find.byType(Switch));
      expect(sw.onChanged, isNull);
    });

    testWidgets(
      'shows "需先设置截止时间才能开启提醒" when no deadline',
      (tester) async {
        await tester.pumpWidget(wrap(
          ReminderSection(
            enabled: false,
            leadMinutes: 120,
            deadline: null,
            onToggle: (_) {},
            onLeadChanged: (_) {},
          ),
        ),);

        expect(find.text('需先设置截止时间才能开启提醒'), findsOneWidget);
      },
    );

    testWidgets(
      'shows preset chips "截止前 2 小时" and "截止前 24 小时" when enabled + has deadline',
      (tester) async {
        await tester.pumpWidget(wrap(
          ReminderSection(
            enabled: true,
            leadMinutes: 120,
            deadline: DateTime(2099, 12, 31, 23, 59),
            onToggle: (_) {},
            onLeadChanged: (_) {},
          ),
        ),);

        expect(find.text('截止前 2 小时'), findsOneWidget);
        expect(find.text('截止前 24 小时'), findsOneWidget);
      },
    );

    testWidgets('tapping a preset chip calls onLeadChanged', (tester) async {
      int? lead;
      await tester.pumpWidget(wrap(
        ReminderSection(
          enabled: true,
          leadMinutes: 120,
          deadline: DateTime(2099, 12, 31, 23, 59),
          onToggle: (_) {},
          onLeadChanged: (m) => lead = m,
        ),
      ),);

      await tester.tap(find.text('截止前 24 小时'));
      await tester.pump();

      expect(lead, equals(1440));
    });

    testWidgets(
      'shows reminder preview text with date when enabled',
      (tester) async {
        await tester.pumpWidget(wrap(
          ReminderSection(
            enabled: true,
            leadMinutes: 120,
            deadline: DateTime(2099, 12, 31, 23, 59),
            onToggle: (_) {},
            onLeadChanged: (_) {},
          ),
        ),);

        // 预览文案: "将在 $dateStr 发送系统通知"
        expect(find.textContaining('将在'), findsOneWidget);
        expect(find.textContaining('发送系统通知'), findsOneWidget);
      },
    );
  });

  // ============================================================
  // NotificationExtractPage — 多任务完整流程(ProviderScope)
  // ============================================================
  group('NotificationExtractPage multi-task extraction', () {
    GoRouter buildRouter() {
      return GoRouter(
        initialLocation: '/notifications/extract',
        routes: [
          GoRoute(
            path: '/home',
            builder: (context, state) =>
                const Scaffold(body: Center(child: Text('Home'))),
          ),
          GoRoute(
            path: '/notifications/extract',
            builder: (context, state) => const NotificationExtractPage(),
          ),
        ],
      );
    }

    ProviderContainer makeContainer() {
      final container = ProviderContainer(
        overrides: [
          taskRepositoryProvider.overrideWithValue(
            MockTaskRepository(initial: const []),
          ),
          notificationExtractionProvider.overrideWithValue(
            MockNotificationExtractionService(),
          ),
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

    void setPhoneViewport(WidgetTester tester) {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
    }

    /// 找到主输入框(结果表单出现前仅有 1 个 TextFormField)。
    Finder findMainInput() => find.byType(TextFormField).first;

    /// 找到智能整理按钮(提取前仅有 1 个 FilledButton)。
    Finder findExtractButton() => find.byType(FilledButton);

    testWidgets(
      'multi-task notice: extracts and shows MultiTaskSelector with 2 tasks',
      (tester) async {
        setPhoneViewport(tester);
        final container = makeContainer();
        await tester.pumpWidget(wrapApp(container));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        // 输入包含两个独立截止时间的多任务通知
        await tester.enterText(
          findMainInput(),
          '请于8月1日前提交报名表,并于8月5日参加现场答辩',
        );
        await tester.pump();

        // 点击智能整理按钮
        await tester.tap(findExtractButton());
        await tester.pump();

        // 等待提取完成: Mock 5 步 × 300ms ≈ 1500ms
        await tester.pump(const Duration(milliseconds: 600));
        await tester.pump(const Duration(milliseconds: 600));
        await tester.pump(const Duration(milliseconds: 600));

        // 额外推进一帧,让结果表单与 MultiTaskSelector 完成渲染
        await tester.pump(const Duration(milliseconds: 200));

        // MultiTaskSelector 应出现,显示 "已拆分为多个任务"
        expect(find.text('已拆分为多个任务'), findsOneWidget);
        // 任务数徽章 "2 个任务"
        expect(find.text('2 个任务'), findsOneWidget);

        // 清理 StaggeredEnter 的 Future.delayed 残留定时器(60/80/120ms)
        await tester.pump(const Duration(milliseconds: 400));
      },
    );
  });
}
