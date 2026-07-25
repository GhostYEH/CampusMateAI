import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/expression.dart';
import '../../../data/models/study.dart';
import 'widgets/companion_suggestion_panel.dart';
import 'widgets/expression_panel.dart';
import 'widgets/privacy_notice.dart';
import 'widgets/study_controls.dart';
import 'widgets/study_history_summary.dart';
import 'widgets/study_state_hero.dart';

/// 学习陪伴页面 — 学习计时 + 表情识别 + AI 陪伴建议。
///
/// 业务逻辑(均通过抽象接口,与 Mock 实现解耦):
/// - 学习会话开始/暂停/恢复/结束(通过 [StudySessionRepository])
/// - 休息提醒(基于 [AppSettings.studyRestIntervalMinutes])
/// - 表情监听 + 派生学习状态(低置信度不触发情绪安慰)
///
/// 子组件均位于 widgets/ 目录。
class StudyCompanionPage extends ConsumerStatefulWidget {
  const StudyCompanionPage({super.key});

  @override
  ConsumerState<StudyCompanionPage> createState() => _StudyCompanionPageState();
}

class _StudyCompanionPageState extends ConsumerState<StudyCompanionPage> {
  late final TextEditingController _goalController;
  Timer? _restCheckTimer;
  DateTime? _lastRestPrompt;
  StudyState _displayState = StudyState.idle;
  List<ExpressionResult> _recentStable = [];

  @override
  void initState() {
    super.initState();
    _goalController = TextEditingController();
  }

  @override
  void dispose() {
    _goalController.dispose();
    _restCheckTimer?.cancel();
    super.dispose();
  }

  Future<void> _start() async {
    final repo = ref.read(studySessionRepositoryProvider);
    await repo.start(
      goalId: _goalController.text.trim().isEmpty
          ? null
          : _goalController.text.trim(),
    );
    setState(() => _displayState = StudyState.focusing);
    _startRestCheck();
    if (ref.read(appSettingsProvider).expressionRecognitionEnabled) {
      await ref.read(expressionRecognitionProvider).start();
    }
  }

  Future<void> _pause() async {
    final repo = ref.read(studySessionRepositoryProvider);
    await repo.pause();
    setState(() => _displayState = StudyState.paused);
    ref.read(expressionRecognitionProvider).pause();
  }

  Future<void> _resume() async {
    final repo = ref.read(studySessionRepositoryProvider);
    await repo.resume();
    setState(() => _displayState = StudyState.focusing);
    if (ref.read(appSettingsProvider).expressionRecognitionEnabled) {
      await ref.read(expressionRecognitionProvider).start();
    }
  }

  Future<void> _end() async {
    final repo = ref.read(studySessionRepositoryProvider);
    await repo.end();
    ref.read(expressionRecognitionProvider).stop();
    _restCheckTimer?.cancel();
    setState(() {
      _displayState = StudyState.completed;
      _recentStable = [];
    });
  }

  void _startRestCheck() {
    _restCheckTimer?.cancel();
    final interval = ref.read(appSettingsProvider).studyRestIntervalMinutes;
    _restCheckTimer = Timer.periodic(Duration(minutes: interval), (_) {
      if (!mounted) return;
      _showRestReminder();
    });
  }

  void _showRestReminder() {
    final now = DateTime.now();
    if (_lastRestPrompt != null &&
        now.difference(_lastRestPrompt!).inMinutes <
            ref.read(appSettingsProvider).suggestionCooldownMinutes) {
      return;
    }
    _lastRestPrompt = now;
    setState(() => _displayState = StudyState.resting);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('已经学习一段时间了,起来活动一下吧~'),
        duration: const Duration(seconds: 4),
        action: SnackBarAction(
          label: '继续学习',
          onPressed: () {
            setState(() => _displayState = StudyState.focusing);
          },
        ),
      ),
    );
  }

  /// Mock 表情注入 — 通过 mockExpressionControlProvider 获取 Mock 控制,
  /// 真实模式下该方法为 no-op,UI 不依赖具体实现类型。
  void _injectMock(ExpressionLabel? label) {
    final mock = ref.read(mockExpressionControlProvider);
    if (mock != null) {
      mock.injectMockLabel(label);
    }
  }

  void _updateStateFromExpression(ExpressionResult result) {
    if (_displayState == StudyState.paused ||
        _displayState == StudyState.completed ||
        _displayState == StudyState.resting) {
      return;
    }
    // 低置信度不触发情绪安慰,也不改变状态判定
    if (result.isLowConfidence || !result.hasFace) {
      return;
    }
    // 仅基于稳定表情 *辅助* 判断"可能分心",而非诊断
    if (result.label == ExpressionLabel.sad ||
        result.label == ExpressionLabel.angry ||
        result.label == ExpressionLabel.disgust) {
      setState(() => _displayState = StudyState.distracted);
    } else if (result.label == ExpressionLabel.neutral ||
        result.label == ExpressionLabel.happy) {
      setState(() => _displayState = StudyState.focusing);
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(currentStudySessionProvider).valueOrNull;
    final settings = ref.watch(appSettingsProvider);
    final expressionAsync = ref.watch(expressionResultsProvider);
    final reduceMotion = ref.watch(reduceMotionProvider);

    // 监听表情结果,更新最近稳定结果 & 派生学习状态
    ref.listen(expressionResultsProvider, (prev, next) {
      next.whenData((result) {
        if (result.isStable) {
          setState(() {
            _recentStable = [..._recentStable, result].toList();
            if (_recentStable.length > 5) {
              _recentStable = _recentStable.sublist(_recentStable.length - 5);
            }
            _updateStateFromExpression(result);
          });
        }
      });
    });

    final isStudying = session != null && session.state != StudyState.completed;
    final expressionEnabled = settings.expressionRecognitionEnabled &&
        settings.cameraPermissionGranted;
    // Mock 控制台仅在演示模式显示(普通用户不显示)
    final showMockConsole = settings.demoMode;

    return Scaffold(
      appBar: AppBar(
        title: const Text('学习陪伴'),
        actions: [
          IconButton(
            icon: const Icon(Icons.privacy_tip_outlined),
            onPressed: () => showStudyPrivacyDialog(context),
            tooltip: '隐私说明',
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.edge,
            vertical: 8,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              StaggeredEnter(
                child: StudyStateHero(
                  state: isStudying ? _displayState : _displayState,
                  durationSeconds: session?.durationSeconds ?? 0,
                  isStudying: isStudying,
                  reduceMotion: reduceMotion,
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 60),
                child: StudyControls(
                  isStudying: isStudying,
                  state: _displayState,
                  goalController: _goalController,
                  onStart: _start,
                  onPause: _pause,
                  onResume: _resume,
                  onEnd: _end,
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 120),
                child: ExpressionPanel(
                  enabled: expressionEnabled,
                  result: expressionAsync.valueOrNull,
                  recentStable: _recentStable,
                  onInject: _injectMock,
                  showMockConsole: showMockConsole,
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 180),
                child: CompanionSuggestionPanel(
                  state: _displayState,
                  expression: expressionAsync.valueOrNull,
                  recentStable: _recentStable,
                ),
              ),
              const SizedBox(height: 16),
              const StaggeredEnter(
                delay: Duration(milliseconds: 240),
                child: StudyHistorySummary(),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}
