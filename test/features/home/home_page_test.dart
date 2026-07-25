import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:campus_companion/features/home/presentation/home_page.dart';
import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/data/models/task.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';
import 'package:campus_companion/core/widgets/state_views.dart';

void main() {
  /// 构造一个可覆盖任务仓库的 ProviderContainer,便于测试首页在不同数据下的表现。
  ProviderContainer makeContainerWithTasks(List<Task> tasks) {
    final repo = MockTaskRepository(initial: tasks);
    final container = ProviderContainer(overrides: [
      taskRepositoryProvider.overrideWithValue(repo),
    ]);
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

  /// 由于首页存在持续动画(_BreathingDot 使用 repeat()),
  /// 不能使用 pumpAndSettle,需用 pump + 固定时长让分层进入动画完成。
  Future<void> pumpHome(WidgetTester tester) async {
    // 触发首帧
    await tester.pump();
    // 推进时间,让 StaggeredEnter 的延迟动画有机会启动并完成
    // (最大 delay 是 480ms,加上动画时长 280ms,800ms 足够)
    await tester.pump(const Duration(milliseconds: 800));
  }

  testWidgets('首页渲染:问候语、用户昵称、AI导员入口、快捷入口', (tester) async {
    final container = makeContainerWithTasks(const []);
    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    // 用户昵称 "知夏" 出现
    expect(find.textContaining('知夏'), findsWidgets);
    // AI 导员入口
    expect(find.text('AI 导员'), findsWidgets);
    // 快捷入口标签
    expect(find.text('整理通知'), findsOneWidget);
    expect(find.text('新建待办'), findsOneWidget);
    expect(find.text('问AI导员'), findsOneWidget);
    expect(find.text('开始学习'), findsOneWidget);
  });

  testWidgets('首页渲染:今日任务进度卡片显示', (tester) async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day, 23, 59);
    final container = makeContainerWithTasks([
      Task(
        id: 'today_task',
        title: '今日截止任务',
        category: TaskCategory.study,
        priority: TaskPriority.high,
        createdAt: now,
        source: TaskSource.manual,
        deadline: today,
      ),
    ]);

    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    // 今日任务进度文字
    expect(find.text('今日任务进度'), findsOneWidget);
    expect(find.textContaining('今天有 1 项截止'), findsOneWidget);
  });

  testWidgets('首页渲染:无今日任务时显示空状态文案', (tester) async {
    final now = DateTime.now();
    final container = makeContainerWithTasks([
      Task(
        id: 'far_task',
        title: '远期任务',
        category: TaskCategory.study,
        priority: TaskPriority.medium,
        createdAt: now,
        source: TaskSource.manual,
        deadline: now.add(const Duration(days: 30)),
      ),
    ]);

    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    expect(find.text('今日任务进度'), findsOneWidget);
    expect(find.text('今天暂无截止任务'), findsOneWidget);
  });

  testWidgets('首页渲染:最紧急任务区显示任务标题', (tester) async {
    final now = DateTime.now();
    final soon = now.add(const Duration(days: 1));
    final container = makeContainerWithTasks([
      Task(
        id: 'urgent_task',
        title: '提交实践申请表',
        category: TaskCategory.practice,
        priority: TaskPriority.high,
        createdAt: now,
        source: TaskSource.noticeExtraction,
        deadline: soon,
      ),
      Task(
        id: 'later_task',
        title: '远期任务',
        category: TaskCategory.study,
        priority: TaskPriority.medium,
        createdAt: now,
        source: TaskSource.manual,
        deadline: now.add(const Duration(days: 10)),
      ),
    ]);

    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    // 最紧急任务标题出现
    expect(find.text('提交实践申请表'), findsWidgets);
    // "最紧急" 标签
    expect(find.text('最紧急'), findsOneWidget);
  });

  testWidgets('首页渲染:即将截止区域无任务时显示空状态', (tester) async {
    final container = makeContainerWithTasks(const []);

    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    expect(find.text('近期没有截止任务'), findsOneWidget);
  });

  testWidgets('首页渲染:校园通知横向滑动区域显示通知标题', (tester) async {
    // 设置较大的视口,确保 CustomScrollView 中下方的 sliver 都被构建
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final container = makeContainerWithTasks(const []);

    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    // "校园通知" 区块标题
    expect(find.text('校园通知'), findsOneWidget);
    // 来自 MockData 的通知标题
    expect(
      find.text('关于2024级学生实践学分申请的通知'),
      findsWidgets,
    );
  });

  testWidgets('首页渲染:今日学习时长区域显示', (tester) async {
    // 设置较大的视口,确保 CustomScrollView 中下方的 sliver 都被构建
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final container = makeContainerWithTasks(const []);

    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    expect(find.text('今日学习'), findsOneWidget);
  });

  testWidgets('首页:减少动态效果模式下不报错并正常渲染', (tester) async {
    final container = ProviderContainer(overrides: [
      taskRepositoryProvider.overrideWithValue(
        MockTaskRepository(initial: const []),
      ),
    ]);
    addTearDown(container.dispose);
    // 开启减少动态效果
    container.read(reduceMotionProvider.notifier).state = true;

    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    expect(find.text('AI 导员'), findsWidgets);
  });

  testWidgets('首页:点击通知铃铛图标可触发交互(tap 不报错)', (tester) async {
    final container = makeContainerWithTasks(const []);

    await tester.pumpWidget(wrapWithMaterial(container, const HomePage()));
    await pumpHome(tester);

    // 找到通知铃铛图标(位于 _Header)
    final bellIcon = find.descendant(
      of: find.byType(Stack),
      matching: find.byIcon(Icons.notifications_none_rounded),
    );
    expect(bellIcon, findsOneWidget);
    // 点击不应抛出异常(MaterialApp 没有 GoRouter,这里只验证 tap 不崩溃)
    await tester.tap(bellIcon, warnIfMissed: false);
    await tester.pump(const Duration(milliseconds: 100));
  });
}
