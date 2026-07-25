import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/utils/date_utils.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../data/models/expression.dart';
import '../../../data/models/study.dart';
import '../../../mock/mock_services/mock_services.dart';

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
    final repo =
        ref.read(studySessionRepositoryProvider) as MockStudySessionRepository;
    await repo.start(
      goalId: _goalController.text.trim().isEmpty
          ? null
          : _goalController.text.trim(),
    );
    setState(() => _displayState = StudyState.focusing);
    _startRestCheck();
    if (ref.read(appSettingsProvider).expressionRecognitionEnabled) {
      ref.read(expressionRecognitionProvider).start();
    }
  }

  Future<void> _pause() async {
    final repo =
        ref.read(studySessionRepositoryProvider) as MockStudySessionRepository;
    await repo.pause();
    setState(() => _displayState = StudyState.paused);
    ref.read(expressionRecognitionProvider).pause();
  }

  Future<void> _resume() async {
    final repo =
        ref.read(studySessionRepositoryProvider) as MockStudySessionRepository;
    await repo.resume();
    setState(() => _displayState = StudyState.focusing);
    if (ref.read(appSettingsProvider).expressionRecognitionEnabled) {
      ref.read(expressionRecognitionProvider).start();
    }
  }

  Future<void> _end() async {
    final repo =
        ref.read(studySessionRepositoryProvider) as MockStudySessionRepository;
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

  void _injectMock(ExpressionLabel? label) {
    ref.read(expressionRecognitionProvider).injectMockLabel(label);
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(currentStudySessionProvider).valueOrNull;
    final settings = ref.watch(appSettingsProvider);
    final expressionAsync = ref.watch(expressionResultsProvider);

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

    return Scaffold(
      appBar: AppBar(
        title: const Text('学习陪伴'),
        actions: [
          IconButton(
            icon: const Icon(Icons.privacy_tip_outlined),
            onPressed: () => _showPrivacyDialog(context),
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
                child: _StateHero(
                  state: isStudying ? _displayState : _displayState,
                  durationSeconds: session?.durationSeconds ?? 0,
                  isStudying: isStudying,
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 60),
                child: _Controls(
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
                child: _ExpressionPanel(
                  enabled: settings.expressionRecognitionEnabled &&
                      settings.cameraPermissionGranted,
                  result: expressionAsync.valueOrNull,
                  recentStable: _recentStable,
                  onInject: _injectMock,
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 180),
                child: _CompanionSuggestion(
                  state: _displayState,
                  expression: expressionAsync.valueOrNull,
                  recentStable: _recentStable,
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 240),
                child: _HistorySummary(),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
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

  void _showPrivacyDialog(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('隐私说明'),
        content: const Text(
          '• 表情识别完全在本地进行,不会上传任何图像或视频。\n'
          '• 仅识别可观察到的面部表情,不进行心理诊断。\n'
          '• 识别结果仅供学习状态辅助参考,不代表情绪判定。\n'
          '• 你可以随时在"我的"中关闭表情识别。\n'
          '• 疲劳判断结合学习时长,不等同于表情类别。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('知道了'),
          ),
        ],
      ),
    );
  }
}

/// 学习状态英雄区 — 动态呼吸环 + 状态文字 + 计时器。
class _StateHero extends StatefulWidget {
  const _StateHero({
    required this.state,
    required this.durationSeconds,
    required this.isStudying,
  });

  final StudyState state;
  final int durationSeconds;
  final bool isStudying;

  @override
  State<_StateHero> createState() => _StateHeroState();
}

class _StateHeroState extends State<_StateHero> with TickerProviderStateMixin {
  late final AnimationController _breath;

  @override
  void initState() {
    super.initState();
    _breath = AnimationController(
      duration: const Duration(milliseconds: 2400),
      vsync: this,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _breath.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final (color, icon) = _stateVisual(widget.state);
    final h = widget.durationSeconds ~/ 3600;
    final m = (widget.durationSeconds % 3600) ~/ 60;
    final s = widget.durationSeconds % 60;
    final timeStr = h > 0
        ? '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}'
        : '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';

    return AppCard(
      padding: const EdgeInsets.symmetric(vertical: 28),
      backgroundColor: AppColors.bgSurface,
      child: Column(
        children: [
          SizedBox(
            height: 180,
            child: Stack(
              alignment: Alignment.center,
              children: [
                // 呼吸环
                AnimatedBuilder(
                  animation: _breath,
                  builder: (context, _) {
                    final scale = 1 + 0.08 * _breath.value;
                    final opacity = 0.25 + 0.25 * _breath.value;
                    return Transform.scale(
                      scale: scale,
                      child: Container(
                        width: 140,
                        height: 140,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: color.withValues(alpha: opacity),
                            width: 2,
                          ),
                        ),
                      ),
                    );
                  },
                ),
                AnimatedContainer(
                  duration: AppMotion.base,
                  width: 110,
                  height: 110,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: color.withValues(alpha: 0.12),
                    border: Border.all(
                      color: color.withValues(alpha: 0.4),
                      width: 1.5,
                    ),
                  ),
                  child: Icon(icon, color: color, size: 44),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          AnimatedSwitcher(
            duration: AppMotion.base,
            child: Text(
              widget.state.displayName,
              key: ValueKey(widget.state),
              style: AppTypography.subtitle.copyWith(color: color),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            timeStr,
            style: AppTypography.metric.copyWith(
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 4),
          Text(
            widget.isStudying ? '专注计时中' : '点击下方按钮开始学习',
            style: AppTypography.caption,
          ),
        ],
      ),
    );
  }

  (Color, IconData) _stateVisual(StudyState s) {
    switch (s) {
      case StudyState.idle:
        return (AppColors.textTertiary, Icons.self_improvement_rounded);
      case StudyState.focusing:
        return (AppColors.primary, Icons.center_focus_strong_rounded);
      case StudyState.distracted:
        return (AppColors.warning, Icons.visibility_off_rounded);
      case StudyState.fatigued:
        return (AppColors.accent, Icons.battery_alert_rounded);
      case StudyState.paused:
        return (AppColors.textSecondary, Icons.pause_circle_rounded);
      case StudyState.resting:
        return (AppColors.success, Icons.local_cafe_rounded);
      case StudyState.completed:
        return (AppColors.success, Icons.check_circle_rounded);
    }
  }
}

class _Controls extends StatelessWidget {
  const _Controls({
    required this.isStudying,
    required this.state,
    required this.goalController,
    required this.onStart,
    required this.onPause,
    required this.onResume,
    required this.onEnd,
  });

  final bool isStudying;
  final StudyState state;
  final TextEditingController goalController;
  final VoidCallback onStart;
  final VoidCallback onPause;
  final VoidCallback onResume;
  final VoidCallback onEnd;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!isStudying && state != StudyState.completed) ...[
            const Text('本次目标', style: AppTypography.label),
            const SizedBox(height: 6),
            TextField(
              controller: goalController,
              decoration: const InputDecoration(
                hintText: '例如:复习高数第三章',
                prefixIcon: Icon(Icons.flag_outlined, size: 20),
              ),
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: onStart,
              icon: const Icon(Icons.play_arrow_rounded),
              label: const Text('开始学习'),
            ),
          ] else if (state == StudyState.paused) ...[
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onResume,
                    icon: const Icon(Icons.play_arrow_rounded),
                    label: const Text('继续'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: onEnd,
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.danger,
                    ),
                    icon: const Icon(Icons.stop_rounded),
                    label: const Text('结束'),
                  ),
                ),
              ],
            ),
          ] else if (state == StudyState.completed) ...[
            const Icon(
              Icons.check_circle_rounded,
              color: AppColors.success,
              size: 40,
            ),
            const SizedBox(height: 8),
            const Text(
              '本次学习已完成',
              style: AppTypography.subtitle,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: onStart,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('再来一次'),
            ),
          ] else ...[
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onPause,
                    icon: const Icon(Icons.pause_rounded),
                    label: const Text('暂停'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: onEnd,
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.danger,
                    ),
                    icon: const Icon(Icons.stop_rounded),
                    label: const Text('结束'),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// 表情识别面板 + Mock 控制台。
class _ExpressionPanel extends StatelessWidget {
  const _ExpressionPanel({
    required this.enabled,
    required this.result,
    required this.recentStable,
    required this.onInject,
  });

  final bool enabled;
  final ExpressionResult? result;
  final List<ExpressionResult> recentStable;
  final void Function(ExpressionLabel?) onInject;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(
                Icons.face_retouching_natural_rounded,
                size: 18,
                color: AppColors.primary,
              ),
              const SizedBox(width: 6),
              const Text('表情识别', style: AppTypography.subtitle),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: enabled ? AppColors.successSubtle : AppColors.bgSunken,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  enabled ? '运行中' : '未开启',
                  style: AppTypography.label.copyWith(
                    color: enabled ? AppColors.success : AppColors.textTertiary,
                    fontSize: 10.5,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          const Text(
            'Mock 模式 · 模型 mock-v0.1 · 仅识别可观察表情,不作心理诊断',
            style: AppTypography.overline,
          ),
          const SizedBox(height: 14),
          if (!enabled) ...[
            _disabledHint(),
          ] else ...[
            _resultView(),
            const SizedBox(height: 16),
            _mockConsole(),
          ],
        ],
      ),
    );
  }

  Widget _disabledHint() {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 16),
      child: Column(
        children: [
          Icon(
            Icons.lock_outline_rounded,
            size: 30,
            color: AppColors.textTertiary,
          ),
          SizedBox(height: 8),
          Text(
            '请在"我的"中开启摄像头权限与表情识别',
            style: AppTypography.caption,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _resultView() {
    if (result == null) {
      return const Row(
        children: [
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: 10),
          Text('正在采集…', style: AppTypography.caption),
        ],
      );
    }
    final r = result!;
    final color = expressionColor(r.label.name);

    if (r.isLowConfidence || !r.hasFace) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.bgSunken,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            const Icon(
              Icons.help_outline_rounded,
              color: AppColors.textTertiary,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                r.label == ExpressionLabel.noFace
                    ? '未检测到人脸,请调整姿势。'
                    : '暂时无法稳定判断当前表情。',
                style: AppTypography.body.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            AnimatedContainer(
              duration: AppMotion.base,
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: Icon(_labelIcon(r.label), color: color, size: 20),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(r.label.displayName, style: AppTypography.subtitle),
                  Text(
                    '置信度 ${(r.confidence * 100).round()}% · ${r.isStable ? "已稳定" : "采集中"}',
                    style: AppTypography.caption,
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        // 概率分布条
        ...r.sortedProbabilities.take(4).map((e) {
          final isTop = e.key == r.label;
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              children: [
                SizedBox(
                  width: 48,
                  child: Text(
                    e.key.displayName,
                    style: AppTypography.label.copyWith(
                      fontSize: 11,
                      color: isTop
                          ? AppColors.textPrimary
                          : AppColors.textTertiary,
                      fontWeight: isTop ? FontWeight.w600 : FontWeight.w400,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(999),
                    child: LinearProgressIndicator(
                      value: e.value,
                      minHeight: 5,
                      backgroundColor: AppColors.bgSunken,
                      color: expressionColor(e.key.name),
                    ),
                  ),
                ),
                SizedBox(
                  width: 36,
                  child: Text(
                    '${(e.value * 100).round()}%',
                    style: AppTypography.label.copyWith(
                      fontSize: 10.5,
                      color: AppColors.textTertiary,
                    ),
                    textAlign: TextAlign.right,
                  ),
                ),
              ],
            ),
          );
        }),
        if (recentStable.length >= 2) ...[
          const SizedBox(height: 8),
          Text(
            '最近 ${recentStable.length} 帧稳定结果',
            style: AppTypography.overline,
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            children: recentStable.map((e) {
              final c = expressionColor(e.label.name);
              return Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: c,
                  shape: BoxShape.circle,
                ),
              );
            }).toList(),
          ),
        ],
      ],
    );
  }

  IconData _labelIcon(ExpressionLabel l) {
    switch (l) {
      case ExpressionLabel.happy:
        return Icons.sentiment_satisfied_rounded;
      case ExpressionLabel.neutral:
        return Icons.sentiment_neutral_rounded;
      case ExpressionLabel.sad:
        return Icons.sentiment_dissatisfied_rounded;
      case ExpressionLabel.angry:
        return Icons.sentiment_very_dissatisfied_rounded;
      case ExpressionLabel.fear:
        return Icons.warning_amber_rounded;
      case ExpressionLabel.surprise:
        return Icons.sentiment_satisfied_alt_rounded;
      case ExpressionLabel.disgust:
        return Icons.sick_rounded;
      default:
        return Icons.help_outline_rounded;
    }
  }

  Widget _mockConsole() {
    final labels = [
      ExpressionLabel.happy,
      ExpressionLabel.neutral,
      ExpressionLabel.sad,
      ExpressionLabel.angry,
      ExpressionLabel.fear,
      ExpressionLabel.surprise,
      ExpressionLabel.disgust,
      ExpressionLabel.noFace,
    ];
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.bgSunken,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border, width: 0.6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.tune_rounded,
                size: 14,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                'Mock 控制台(演示用)',
                style: AppTypography.overline.copyWith(fontSize: 10),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final l in labels)
                ActionChip(
                  label:
                      Text(l.displayName, style: const TextStyle(fontSize: 11)),
                  onPressed: () => onInject(l),
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ActionChip(
                label: const Text('随机漂移', style: TextStyle(fontSize: 11)),
                onPressed: () => onInject(null),
                visualDensity: VisualDensity.compact,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// AI 导员陪伴建议 — 遵循科学边界。
class _CompanionSuggestion extends StatelessWidget {
  const _CompanionSuggestion({
    required this.state,
    required this.expression,
    required this.recentStable,
  });

  final StudyState state;
  final ExpressionResult? expression;
  final List<ExpressionResult> recentStable;

  @override
  Widget build(BuildContext context) {
    final suggestion = _build();
    return AppCard(
      padding: const EdgeInsets.all(16),
      borderColor: AppColors.primarySubtle,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CircleAvatar(
            radius: 16,
            backgroundColor: AppColors.primarySubtle,
            child: Icon(
              Icons.smart_toy_rounded,
              size: 18,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('AI 导员陪伴', style: AppTypography.subtitle),
                const SizedBox(height: 6),
                Text(suggestion, style: AppTypography.body),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _build() {
    // 低置信度不触发情绪安慰
    if (expression != null &&
        (expression!.isLowConfidence || !expression!.hasFace)) {
      return '识别结果仅供辅助参考。继续专注吧,需要休息时随时告诉我。';
    }
    switch (state) {
      case StudyState.idle:
        return '准备好了就开始吧,定个小目标会更专注。';
      case StudyState.focusing:
        if (expression?.label == ExpressionLabel.happy) {
          return '状态看起来不错,保持节奏,记得适时休息。';
        }
        return '专注中,继续加油。每过一段时间可以抬头看看远处。';
      case StudyState.distracted:
        return '你好像有些走神,要不要把当前任务拆小一点?我们可以一起整理。';
      case StudyState.fatigued:
        return '你好像有些疲惫,需要休息一下吗?起来走走、喝口水都好。';
      case StudyState.paused:
        return '已暂停,休息好了再继续。';
      case StudyState.resting:
        return '休息中,放松一下眼睛和肩膀吧。';
      case StudyState.completed:
        return '本次学习完成,辛苦了!记得给自己一点正向反馈。';
    }
  }
}

class _HistorySummary extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(studyHistoryProvider);
    final todayAsync = ref.watch(todayStudyTotalProvider);
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(
                Icons.history_rounded,
                size: 18,
                color: AppColors.primary,
              ),
              SizedBox(width: 6),
              Text('学习记录', style: AppTypography.subtitle),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _stat(
                  '今日',
                  _formatDuration(todayAsync.valueOrNull),
                  AppColors.primary,
                ),
              ),
              Container(width: 1, height: 36, color: AppColors.border),
              Expanded(
                child: _stat(
                  '近 ${historyAsync.valueOrNull?.length ?? 0} 次',
                  '${historyAsync.valueOrNull?.length ?? 0} 次',
                  AppColors.success,
                ),
              ),
              Container(width: 1, height: 36, color: AppColors.border),
              Expanded(
                child: _stat(
                  '平均专注',
                  '${((historyAsync.valueOrNull?.fold<double>(0, (a, s) => a + s.focusRatio) ?? 0) / (historyAsync.valueOrNull?.length ?? 1) * 100).round()}%',
                  AppColors.accent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (historyAsync.valueOrNull?.isNotEmpty ?? false)
            ...historyAsync.valueOrNull!.take(3).map(
                  (s) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.circle,
                          size: 6,
                          color: AppColors.success,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          AppDateUtils.relativeTime(s.startedAt),
                          style: AppTypography.caption,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            '学习 ${s.durationMinutes} 分钟 · 专注 ${(s.focusRatio * 100).round()}%',
                            style: AppTypography.caption,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
        ],
      ),
    );
  }

  Widget _stat(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: AppTypography.subtitle.copyWith(color: color)),
        const SizedBox(height: 2),
        Text(label, style: AppTypography.overline),
      ],
    );
  }

  String _formatDuration(Duration? d) {
    if (d == null) return '0 分钟';
    final m = d.inMinutes;
    if (m < 60) return '$m 分钟';
    return '${m ~/ 60} 小时 ${m % 60} 分钟';
  }
}
