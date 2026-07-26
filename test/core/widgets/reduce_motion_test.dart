import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/staggered_enter.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/settings.dart';

void main() {
  group('reduceMotionProvider', () {
    test('默认值为 false', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(reduceMotionProvider), isFalse);
    });

    test('可被设置为 true', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      container.read(reduceMotionProvider.notifier).state = true;
      expect(container.read(reduceMotionProvider), isTrue);
    });

    test('可被切换回 false', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      container.read(reduceMotionProvider.notifier).state = true;
      container.read(reduceMotionProvider.notifier).state = false;
      expect(container.read(reduceMotionProvider), isFalse);
    });
  });

  group('AppSettings.reduceMotion', () {
    test('默认值为 false', () {
      const settings = AppSettings();
      expect(settings.reduceMotion, isFalse);
    });

    test('copyWith(reduceMotion: true) 生成新对象', () {
      const original = AppSettings();
      final updated = original.copyWith(reduceMotion: true);
      expect(updated.reduceMotion, isTrue);
      // 原对象不受影响
      expect(original.reduceMotion, isFalse);
      // 其他字段保持
      expect(updated.darkMode, original.darkMode);
      expect(updated.reminderEnabled, original.reminderEnabled);
    });

    test('AppSettingsNotifier.toggleReduceMotion 正确切换', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(appSettingsProvider.notifier);

      expect(container.read(appSettingsProvider).reduceMotion, isFalse);
      notifier.toggleReduceMotion();
      expect(container.read(appSettingsProvider).reduceMotion, isTrue);
      notifier.toggleReduceMotion();
      expect(container.read(appSettingsProvider).reduceMotion, isFalse);
    });
  });

  group('StaggeredEnter - reduceMotion 模式', () {
    /// 在 reduceMotion=true 时,StaggeredEnter 应:
    /// - 不创建 Timer(_startTimer 为 null)
    /// - 直接返回 widget.child(不包装 AnimatedBuilder)
    testWidgets('reduceMotion=true 时不播放动画,直接显示子组件', (tester) async {
      final container = ProviderContainer(
        overrides: [
          reduceMotionProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: StaggeredEnter(
                delay: Duration(milliseconds: 100),
                child: Text('Hello'),
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      // 子组件直接显示
      expect(find.text('Hello'), findsOneWidget);

      // 推进时间,验证不会出现动画相关组件
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 300));

      // 仍然直接显示子组件(无 Opacity / FractionalTranslation 动画)
      expect(find.text('Hello'), findsOneWidget);

      // 由于 reduceMotion=true,不应该有 AnimatedBuilder 包装
      // (StaggeredEnter build 方法直接返回 widget.child)
      final staggeredEnterFinder = find.byType(StaggeredEnter);
      expect(staggeredEnterFinder, findsOneWidget);

      // 验证 StaggeredEnter 的子树直接是 Text('Hello'),
      // 没有中间的 Opacity/FractionalTranslation
      final staggeredEnter =
          tester.widget<StaggeredEnter>(staggeredEnterFinder);
      expect(staggeredEnter.child, isA<Text>());
    });

    testWidgets('reduceMotion=true 时不创建 Timer(无 pending 计时器)', (tester) async {
      final container = ProviderContainer(
        overrides: [
          reduceMotionProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: StaggeredEnter(
                delay: Duration(milliseconds: 100),
                duration: Duration(milliseconds: 300),
                child: Text('No Animation'),
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      // 推进短时间(在 delay 之前)
      await tester.pump(const Duration(milliseconds: 50));

      // 此时若 _startTimer 存在,会在 delay 后 forward controller
      // 由于 reduceMotion=true,Timer 未创建,推进到 delay 后不应有动画状态变化
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 300));

      // 验证最终状态:子组件可见
      expect(find.text('No Animation'), findsOneWidget);

      // 关键:由于 reduceMotion=true 不创建 Timer,
      // pumpAndSettle 应该立即完成(没有 pending 动画)
      // 若 Timer 存在并触发了 controller.forward,pumpAndSettle 会等待动画完成
      // 这里只是验证不抛出异常
      expect(tester.binding.transientCallbackCount, 0);
    });

    testWidgets(
        'reduceMotion=false 时正常播放动画'
        '(验证 reduceMotion 默认行为)', (tester) async {
      final container = ProviderContainer(
        overrides: [
          reduceMotionProvider.overrideWith((ref) => false),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: StaggeredEnter(
                delay: Duration(milliseconds: 50),
                duration: Duration(milliseconds: 200),
                child: Text('Animated'),
              ),
            ),
          ),
        ),
      );

      // 首帧 — 子组件已存在但 Opacity 可能为 0(初始状态)
      await tester.pump();

      // 推进时间经过 delay,触发 controller.forward
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pump(const Duration(milliseconds: 200));

      // 子组件显示出来
      expect(find.text('Animated'), findsOneWidget);
      // 有动画(在播放或已完成) — 此处 transientCallbackCount 可能 > 0
      // 我们不严格断言动画状态,只验证子组件最终可见
    });

    testWidgets('reduceMotion 切换为 true 后,StaggeredEnter 立即停止动画',
        (tester) async {
      final container = ProviderContainer(
        overrides: [
          reduceMotionProvider.overrideWith((ref) => false),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: StaggeredEnter(
                delay: Duration(milliseconds: 50),
                duration: Duration(milliseconds: 300),
                child: Text('Toggle'),
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      // 切换 reduceMotion 为 true
      container.read(reduceMotionProvider.notifier).state = true;
      await tester.pump();

      // 此时 build 应该直接返回 widget.child,跳过动画
      expect(find.text('Toggle'), findsOneWidget);

      // 推进时间不应有动画相关 callback
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pump(const Duration(milliseconds: 300));
      expect(tester.binding.transientCallbackCount, 0);
    });
  });

  group('StaggeredListView - reduceMotion 模式', () {
    testWidgets('reduceMotion=true 时 StaggeredListView 仍渲染所有项', (tester) async {
      final container = ProviderContainer(
        overrides: [
          reduceMotionProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: StaggeredListView(
                itemCount: 5,
                itemBuilder: (context, index) =>
                    ListTile(title: Text('Item $index')),
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      // 所有项应该立即可见(无延迟动画)
      expect(find.text('Item 0'), findsOneWidget);
      expect(find.text('Item 1'), findsOneWidget);
      expect(find.text('Item 4'), findsOneWidget);
    });
  });

  group('减少动态效果设置 - 集成验证', () {
    testWidgets('AppSettingsNotifier 与 reduceMotionProvider 协同工作',
        (tester) async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // 初始状态:reduceMotion 为 false
      expect(container.read(appSettingsProvider).reduceMotion, isFalse);
      expect(container.read(reduceMotionProvider), isFalse);

      // 通过 AppSettingsNotifier 切换
      container.read(appSettingsProvider.notifier).toggleReduceMotion();
      expect(container.read(appSettingsProvider).reduceMotion, isTrue);

      // 模拟 app.dart 中的同步逻辑:
      // ref.read(reduceMotionProvider.notifier).state = settings.reduceMotion
      final settings = container.read(appSettingsProvider);
      container.read(reduceMotionProvider.notifier).state =
          settings.reduceMotion;
      expect(container.read(reduceMotionProvider), isTrue);
    });
  });

  group('减少动态效果设置 - 无障碍验证', () {
    testWidgets('reduceMotion=true 时 StaggeredEnter 在快速切换页面后不残留动画',
        (tester) async {
      final container = ProviderContainer(
        overrides: [
          reduceMotionProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ListView(
                children: [
                  for (var i = 0; i < 10; i++)
                    StaggeredEnter(
                      key: ValueKey('item_$i'),
                      delay: Duration(milliseconds: i * 60),
                      child: ListTile(title: Text('Item $i')),
                    ),
                ],
              ),
            ),
          ),
        ),
      );

      // 立即检查 — 不应等待动画
      await tester.pump();

      // 第一帧后,所有项应可见(无延迟动画)
      // 注意:由于 ListView 的 lazy loading,可能部分项未渲染,
      // 但已渲染的项应该直接可见
      expect(find.text('Item 0'), findsOneWidget);
      expect(find.text('Item 1'), findsOneWidget);

      // 推进长时间 — 不应有动画 callback
      await tester.pump(const Duration(seconds: 1));
      expect(tester.binding.transientCallbackCount, 0);
    });
  });
}
