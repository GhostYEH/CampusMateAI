import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:campus_companion/app/providers/app_providers.dart';
import 'package:campus_companion/core/widgets/state_views.dart';
import 'package:campus_companion/data/models/models.dart';
import 'package:campus_companion/data/services/api/api_client.dart';
import 'package:campus_companion/data/services/service_interfaces.dart';
import 'package:campus_companion/features/study_companion/presentation/study_companion_page.dart';
import 'package:campus_companion/mock/mock_services/mock_services.dart';

/// 自定义学习会话仓库 — 用于测试特定场景(如恢复、错误)。
class _ScriptedStudySessionRepository extends MockStudySessionRepository {
  _ScriptedStudySessionRepository({this.preActiveSession});

  /// 预设的"未结束会话",用于测试应用重启后恢复。
  ///
  /// 在 [getActiveSession] 首次被调用时通过 [injectForRecovery] 注入到父类,
  /// 以模拟 [ApiStudySessionRepository.getActiveSession] 拉取后 _emit(session) 的行为
  /// (使 [currentStudySessionProvider] 通过流收到更新,UI 才能切换状态)。
  StudySession? preActiveSession;
  bool _recoveredInjected = false;

  @override
  Future<StudySession?> getActiveSession() async {
    await Future.delayed(const Duration(milliseconds: 10));
    if (preActiveSession != null && !_recoveredInjected) {
      _recoveredInjected = true;
      injectForRecovery(preActiveSession!);
      return preActiveSession;
    }
    return current;
  }
}

/// 始终抛出 ApiException 的学习会话仓库 — 用于测试网络失败场景。
class _FailingStudySessionRepository implements StudySessionRepository {
  @override
  StudySession? get current => null;

  @override
  Stream<StudySession> watchCurrent() => const Stream.empty();

  @override
  Future<StudySession> start({String? goal, String? relatedTaskId}) async {
    throw const ApiException(
      code: 'NETWORK_ERROR',
      message: '无法连接到后端服务',
    );
  }

  @override
  Future<StudySession> pause({String? reason}) async {
    throw const ApiException(code: 'NETWORK_ERROR', message: '网络错误');
  }

  @override
  Future<StudySession> resume() async {
    throw const ApiException(code: 'NETWORK_ERROR', message: '网络错误');
  }

  @override
  Future<StudySession> finish({
    String? selfReport,
    List<String>? selfReportTags,
  }) async {
    throw const ApiException(code: 'NETWORK_ERROR', message: '网络错误');
  }

  @override
  Future<StudySession> updateSession({
    String? goal,
    String? relatedTaskId,
    String? selfReport,
    List<String>? selfReportTags,
    Map<String, dynamic>? expressionSignal,
  }) async {
    throw const ApiException(code: 'NETWORK_ERROR', message: '网络错误');
  }

  @override
  Future<StudySession?> getActiveSession() async {
    throw const ApiException(code: 'NETWORK_ERROR', message: '无法连接');
  }

  @override
  Future<StudySession?> getSession(String sessionId) async => null;

  @override
  Future<List<StudySession>> history({int limit = 30}) async => const [];

  @override
  Future<Duration> todayTotal() async => Duration.zero;

  @override
  List<StudySession> get historySnapshot => const [];

  @override
  Future<void> restoreHistoryFrom(List<StudySession> saved) async {}

  @override
  Future<void> clearHistory() async {}

  @override
  Future<void> resetToDemo() async {}
}

void main() {
  /// 构造一个可覆盖学习会话仓库的 ProviderContainer。
  ///
  /// 开启"减少动态效果"以跳过 StaggeredEnter 动画:
  /// 动画期间 Opacity 可能为 0,Flutter 会用 IgnorePointer 替换子树,
  /// 导致按钮无法接收点击事件。
  ProviderContainer makeContainer({
    StudySessionRepository? studyRepo,
    TaskRepository? taskRepo,
  }) {
    final repo = studyRepo ?? MockStudySessionRepository();
    // 显式 dispose 学习会话仓库,取消 Mock 实现内部的 tick Timer
    // (injectForRecovery 与 start 会启动 Timer.periodic,
    // 若不取消会在测试结束后留下 pending timer 触发断言失败)
    addTearDown(() {
      if (repo is MockStudySessionRepository) {
        repo.dispose();
      }
    });
    final container = ProviderContainer(
      overrides: [
        appConfigProvider.overrideWith((ref) {
          return const AppConfig(
            environment: AppEnvironment.development,
            useMockBackend: true,
            useMockExpressionRecognition: true,
            apiBaseUrl: 'http://10.0.2.2:8000',
          );
        }),
        taskRepositoryProvider.overrideWithValue(
          taskRepo ?? MockTaskRepository(initial: const []),
        ),
        studySessionRepositoryProvider.overrideWithValue(repo),
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

  /// 推进首帧 + 少量时间让初始渲染与 postFrameCallback 完成。
  Future<void> pumpIdle(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
  }

  group('StudyCompanionPage - 初始渲染', () {
    testWidgets('未开始会话时显示"本次目标"输入与"开始学习"按钮', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      expect(find.text('本次目标'), findsOneWidget);
      expect(find.text('开始学习'), findsOneWidget);
      expect(find.text('学习陪伴'), findsOneWidget);
    });

    testWidgets('显示任务拆解面板入口', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      expect(find.text('任务拆解'), findsOneWidget);
      expect(find.text('请求拆解'), findsOneWidget);
    });
  });

  group('StudyCompanionPage - 会话生命周期交互', () {
    testWidgets('点击"开始学习"后切换到专注中状态,显示暂停/结束按钮', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 输入目标
      await tester.enterText(find.byType(TextField).first, '复习高数第三章');
      await tester.pump();

      // 点击开始学习
      await tester.runAsync(() async {
        await tester.tap(find.text('开始学习'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示暂停 + 结束按钮
      expect(find.text('暂停'), findsOneWidget);
      expect(find.text('结束'), findsOneWidget);
      // 不应再显示开始按钮
      expect(find.text('开始学习'), findsNothing);
    });

    testWidgets('点击"暂停"后切换到暂停状态,显示继续/结束按钮', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 开始学习
      await tester.runAsync(() async {
        await tester.tap(find.text('开始学习'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();

      // 暂停
      await tester.runAsync(() async {
        await tester.tap(find.text('暂停'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示继续 + 结束按钮
      expect(find.text('继续'), findsOneWidget);
      expect(find.text('结束'), findsOneWidget);
      expect(find.text('暂停'), findsNothing);
    });

    testWidgets('暂停后点击"继续"恢复到专注中', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 开始 → 暂停 → 继续
      await tester.runAsync(() async {
        await tester.tap(find.text('开始学习'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.runAsync(() async {
        await tester.tap(find.text('暂停'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.runAsync(() async {
        await tester.tap(find.text('继续'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应恢复到专注中状态,显示暂停按钮
      expect(find.text('暂停'), findsOneWidget);
      expect(find.text('继续'), findsNothing);
    });

    testWidgets('点击"结束"弹出感受对话框,保存后会话完成', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 开始
      await tester.runAsync(() async {
        await tester.tap(find.text('开始学习'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();

      // 点击结束 → 应弹出对话框
      await tester.tap(find.text('结束'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应看到对话框标题
      expect(find.text('本次学习感受'), findsOneWidget);
      // 应有不填写并结束 / 保存并结束 两个按钮
      expect(find.text('不填写并结束'), findsOneWidget);
      expect(find.text('保存并结束'), findsOneWidget);

      // 输入感受
      await tester.enterText(
        find.byType(TextField).first,
        '今天复习了积分,收获很大',
      );
      await tester.pump();

      // 点击保存并结束
      await tester.runAsync(() async {
        await tester.tap(find.text('保存并结束'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示完成状态
      expect(find.text('本次学习已完成'), findsOneWidget);
      expect(find.text('再来一次'), findsOneWidget);
    });
  });

  group('StudyCompanionPage - 应用重启后恢复未结束会话', () {
    testWidgets('启动时检测到未结束 active 会话,自动恢复到专注中状态',
        (tester) async {
      setPhoneViewport(tester);
      // 预设一个 active 会话(模拟应用重启前未结束)
      final now = DateTime.now();
      final preSession = StudySession(
        id: 'sess_recover_active',
        startedAt: now.subtract(const Duration(minutes: 10)),
        durationSeconds: 600,
        state: StudyState.focusing,
        goalId: '恢复的目标',
        status: StudySessionStatus.active,
        breaks: const [],
      );
      final repo = _ScriptedStudySessionRepository(preActiveSession: preSession);
      final container = makeContainer(studyRepo: repo);

      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      // 等待 postFrameCallback + getActiveSession 延迟
      await tester.runAsync(() async {
        await tester.pump();
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 应恢复到专注中状态,显示暂停/结束按钮
      expect(find.text('暂停'), findsOneWidget);
      expect(find.text('结束'), findsOneWidget);
      // 不应显示开始学习按钮
      expect(find.text('开始学习'), findsNothing);
    });

    testWidgets('启动时检测到未结束 paused 会话,自动恢复到暂停状态',
        (tester) async {
      setPhoneViewport(tester);
      final now = DateTime.now();
      final preSession = StudySession(
        id: 'sess_recover_paused',
        startedAt: now.subtract(const Duration(minutes: 15)),
        durationSeconds: 800,
        state: StudyState.paused,
        goalId: '暂停中恢复',
        status: StudySessionStatus.paused,
        pausedAt: now.subtract(const Duration(minutes: 2)),
        breaks: [
          StudyBreak(
            id: 'brk_1',
            sessionId: 'sess_recover_paused',
            startedAt: now.subtract(const Duration(minutes: 2)),
            reason: '喝水',
          ),
        ],
      );
      final repo = _ScriptedStudySessionRepository(preActiveSession: preSession);
      final container = makeContainer(studyRepo: repo);

      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await tester.runAsync(() async {
        await tester.pump();
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 应恢复到暂停状态,显示继续/结束按钮
      expect(find.text('继续'), findsOneWidget);
      expect(find.text('结束'), findsOneWidget);
      expect(find.text('开始学习'), findsNothing);

      // 应显示休息记录卡片
      expect(find.text('休息记录'), findsOneWidget);
    });

    testWidgets('启动时无未结束会话,显示开始学习入口', (tester) async {
      setPhoneViewport(tester);
      final repo = _ScriptedStudySessionRepository(preActiveSession: null);
      final container = makeContainer(studyRepo: repo);

      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await tester.runAsync(() async {
        await tester.pump();
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 无恢复时显示开始学习
      expect(find.text('开始学习'), findsOneWidget);
      expect(find.text('暂停'), findsNothing);
    });
  });

  group('StudyCompanionPage - 网络失败不伪造保存成功', () {
    testWidgets('开始学习失败时显示错误 SnackBar,不切换到专注中状态',
        (tester) async {
      setPhoneViewport(tester);
      final repo = _FailingStudySessionRepository();
      final container = makeContainer(studyRepo: repo);

      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 点击开始学习(会失败)
      await tester.runAsync(() async {
        await tester.tap(find.text('开始学习'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示错误 SnackBar
      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.textContaining('开始学习失败'), findsOneWidget);

      // 仍应显示开始学习按钮(未切换状态)
      expect(find.text('开始学习'), findsOneWidget);
      expect(find.text('暂停'), findsNothing);
    });

    testWidgets('恢复未结束会话失败时静默处理,不阻塞页面', (tester) async {
      setPhoneViewport(tester);
      final repo = _FailingStudySessionRepository();
      final container = makeContainer(studyRepo: repo);

      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      // 等待 _recoverActiveSession 完成(会失败,但应静默)
      await tester.runAsync(() async {
        await tester.pump();
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 页面应正常显示开始学习入口(恢复失败不阻塞)
      expect(find.text('开始学习'), findsOneWidget);
      // 不应显示错误 SnackBar(恢复失败是静默的)
      expect(find.byType(SnackBar), findsNothing);
    });
  });

  group('StudyCompanionPage - 任务拆解交互', () {
    testWidgets('输入目标并点击"请求拆解"显示结构化步骤', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 在任务拆解面板的输入框输入目标
      // (study_companion_page 有两个 TextField:本次目标 + 任务拆解目标)
      // 任务拆解面板的输入框在"任务拆解"标题下方
      // 找到任务拆解面板内的输入框(第二个 TextField)
      await tester.enterText(
        find.byType(TextField).at(1),
        '复习高数第三章',
      );
      await tester.pump();

      // 点击"请求拆解"按钮
      await tester.runAsync(() async {
        await tester.tap(find.text('请求拆解'));
        await Future.delayed(const Duration(milliseconds: 500));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 应显示拆解结果(规则化降级模式)
      expect(find.text('规则建议'), findsOneWidget);
      // 应至少有一个步骤
      expect(find.textContaining('共'), findsOneWidget);
      // 第一步标题应可见
      expect(find.text('明确目标与范围'), findsOneWidget);
    });

    testWidgets('无目标且无关联待办时显示错误提示', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 直接点击请求拆解(不输入目标)
      await tester.tap(find.text('请求拆解'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示错误提示
      expect(find.text('请输入学习目标或选择关联待办'), findsOneWidget);
    });

    testWidgets('拆解步骤可"添加为待办"且需明确确认', (tester) async {
      setPhoneViewport(tester);
      final container = makeContainer();
      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 输入目标
      await tester.enterText(
        find.byType(TextField).at(1),
        '复习数据结构链表',
      );
      await tester.pump();

      // 请求拆解
      await tester.runAsync(() async {
        await tester.tap(find.text('请求拆解'));
        await Future.delayed(const Duration(milliseconds: 500));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // 第一步应有"添加为待办"按钮
      expect(find.text('添加为待办'), findsWidgets);

      // 点击第一个"添加为待办"
      await tester.tap(find.text('添加为待办').first);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应弹出确认对话框
      expect(find.text('将此步骤添加到待办?'), findsOneWidget);
      expect(find.text('添加到待办'), findsOneWidget);
      expect(find.text('取消'), findsOneWidget);

      // 取消 — 不应创建待办
      await tester.tap(find.text('取消'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      // 对话框关闭
      expect(find.text('将此步骤添加到待办?'), findsNothing);
    });
  });

  group('StudyCompanionPage - 关联待办选择', () {
    testWidgets('有未完成任务时显示关联待办下拉', (tester) async {
      setPhoneViewport(tester);
      final now = DateTime.now();
      final taskRepo = MockTaskRepository(
        initial: [
          Task(
            id: 'task_1',
            title: '完成高数作业',
            category: TaskCategory.study,
            priority: TaskPriority.high,
            createdAt: now,
            source: TaskSource.manual,
          ),
          Task(
            id: 'task_2',
            title: '复习英语',
            category: TaskCategory.study,
            priority: TaskPriority.medium,
            createdAt: now,
            source: TaskSource.manual,
          ),
        ],
      );
      final container = makeContainer(taskRepo: taskRepo);

      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 应显示"关联待办(可选)"标签
      expect(find.text('关联待办(可选)'), findsOneWidget);
      // 默认显示"不关联"
      expect(find.text('不关联'), findsOneWidget);
    });

    testWidgets('关联待办后开始学习,显示当前关联任务', (tester) async {
      setPhoneViewport(tester);
      final now = DateTime.now();
      final taskRepo = MockTaskRepository(
        initial: [
          Task(
            id: 'task_link',
            title: '复习数据结构',
            category: TaskCategory.study,
            priority: TaskPriority.high,
            createdAt: now,
            source: TaskSource.manual,
          ),
        ],
      );
      final container = makeContainer(taskRepo: taskRepo);

      await tester.pumpWidget(
        wrapWithMaterial(container, const StudyCompanionPage()),
      );
      await pumpIdle(tester);

      // 点击下拉选择关联待办
      await tester.tap(find.text('不关联'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 选择"复习数据结构"
      await tester.tap(find.text('复习数据结构').last);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 开始学习
      await tester.runAsync(() async {
        await tester.tap(find.text('开始学习'));
        await Future.delayed(const Duration(milliseconds: 200));
      });
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 应显示当前关联任务
      expect(find.textContaining('关联待办'), findsWidgets);
    });
  });
}
