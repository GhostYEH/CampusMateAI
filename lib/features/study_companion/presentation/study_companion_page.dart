import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/design_system/app_colors.dart';
import '../../../app/design_system/app_typography.dart';
import '../../../app/providers/app_providers.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/staggered_enter.dart';
import '../../../core/widgets/state_views.dart';
import '../../../data/models/expression.dart';
import '../../../data/models/study.dart';
import '../../../data/services/api/api_client.dart';
import '../../../data/services/service_interfaces.dart' show PermissionStatus;
import 'widgets/companion_suggestion_panel.dart';
import 'widgets/expression_panel.dart';
import 'widgets/privacy_notice.dart';
import 'widgets/study_controls.dart';
import 'widgets/study_history_summary.dart';
import 'widgets/study_state_hero.dart';
import 'widgets/task_breakdown_panel.dart';

/// 学习陪伴页面 — 学习计时 + 表情识别 + AI 陪伴建议 + 任务拆解。
///
/// 业务逻辑(均通过抽象接口,与 Mock 实现解耦):
/// - 学习会话开始/暂停/恢复/结束(通过 [StudySessionRepository])
/// - 休息记录与时长(由后端权威,UI 展示)
/// - 文字感受(用户主动填写,不根据表情自动填写)
/// - 任务拆解(通过 [TaskBreakdownService])
/// - 应用重启恢复未结束会话(通过 [StudySessionRepository.getActiveSession])
/// - 休息提醒(基于 [AppSettings.studyRestIntervalMinutes],本地触发)
/// - 表情监听 + 派生学习状态(低置信度不触发情绪安慰)
///
/// **科学边界**(AGENTS.md §3):
/// - selfReport 仅由用户主动输入,不根据表情自动填写
/// - 不进行心理疾病诊断,文案仅作日常辅助
///
/// **网络失败处理**(Flutter 要求 #8):
/// - 网络失败时显示错误 SnackBar,不伪造会话保存成功
/// - 错误信息附 ApiException.code 便于排查
///
/// 子组件均位于 widgets/ 目录。
class StudyCompanionPage extends ConsumerStatefulWidget {
  const StudyCompanionPage({super.key});

  @override
  ConsumerState<StudyCompanionPage> createState() => _StudyCompanionPageState();
}

class _StudyCompanionPageState extends ConsumerState<StudyCompanionPage>
    with WidgetsBindingObserver {
  late final TextEditingController _goalController;
  Timer? _restCheckTimer;
  DateTime? _lastRestPrompt;
  StudyState _displayState = StudyState.idle;
  List<ExpressionResult> _recentStable = [];

  /// 当前选中的关联任务 ID(可空)。
  String? _selectedRelatedTaskId;

  /// 是否正在执行异步操作(防止重复点击)。
  bool _busy = false;

  /// 是否已从后端恢复过未结束会话(避免重复拉取)。
  bool _recovered = false;

  // ===== 表情识别运行时状态 =====
  /// 服务是否已 initialize(避免重复初始化)。
  bool _expressionServiceInitialized = false;

  /// 用户是否主动开启了表情识别(独立于学习会话状态)。
  bool _expressionUserEnabled = false;

  /// 应用进入后台时是否正在运行摄像头,用于恢复时重启。
  bool _wasRunningBeforeBackground = false;

  /// 是否正在请求摄像头权限(防止重复点击)。
  bool _requestingCamera = false;

  /// 当前摄像头权限状态缓存(异步获取)。
  PermissionStatus? _cameraPermissionStatus;

  @override
  void initState() {
    super.initState();
    _goalController = TextEditingController();
    WidgetsBinding.instance.addObserver(this);
    // 启动后异步恢复未结束会话 + 查询权限状态(不弹窗)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _recoverActiveSession();
      _refreshCameraPermission();
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    // 应用进入后台/非活跃 → 立即停止摄像头帧处理
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive ||
        state == AppLifecycleState.detached) {
      _onAppBackgrounded();
    } else if (state == AppLifecycleState.resumed) {
      _onAppResumed();
    }
  }

  /// 应用进入后台 — 停止摄像头,记录是否需要恢复。
  void _onAppBackgrounded() {
    final service = ref.read(expressionRecognitionProvider);
    if (service.isRunning) {
      _wasRunningBeforeBackground = true;
      service.pause().catchError((_) {});
    } else {
      _wasRunningBeforeBackground = false;
    }
  }

  /// 应用恢复前台 — 若之前在运行,且用户仍开启,则恢复。
  Future<void> _onAppResumed() async {
    if (!_wasRunningBeforeBackground) return;
    _wasRunningBeforeBackground = false;
    if (!_expressionUserEnabled) return;
    if (!mounted) return;

    // 恢复前台后权限可能被用户在系统设置中撤销,需重新检查
    await _refreshCameraPermission();
    if (_cameraPermissionStatus == PermissionStatus.granted) {
      await _ensureExpressionInitializedAndStart();
    }
  }

  /// 确保服务已 initialize,然后 start 摄像头。
  Future<void> _ensureExpressionInitializedAndStart() async {
    final service = ref.read(expressionRecognitionProvider);
    if (!_expressionServiceInitialized) {
      await service.initialize();
      _expressionServiceInitialized = true;
    }
    try {
      await service.start();
    } catch (_) {
      // 启动失败 — UI 通过 status 流显示错误
    }
  }

  void _stopExpressionSafely() {
    // dispose 阶段 riverpod 已禁用 ref.read,mounted 为 false 时跳过手动 pause。
    // 服务由 Provider autoDispose 自动清理,隐私上仍满足"页面退出停止帧处理"。
    if (!mounted) return;
    try {
      ref.read(expressionRecognitionProvider).pause().catchError((_) {});
    } catch (_) {
      // Element 已被销毁 — 无需手动 pause
    }
  }

  /// 刷新摄像头权限状态缓存(不弹窗)。
  Future<void> _refreshCameraPermission() async {
    try {
      final service = ref.read(permissionServiceProvider);
      final status = await service.cameraPermissionStatus;
      if (!mounted) return;
      setState(() => _cameraPermissionStatus = status);
    } catch (_) {
      // 静默失败
    }
  }

  /// 用户点击"开启/关闭表情识别" — 执行完整权限流 + 服务初始化 + 摄像头启动。
  ///
  /// **不反复弹窗**(AGENTS.md §2.3):
  /// - 已授权 → 直接启动
  /// - notDetermined / denied → 调用 requestCamera(系统弹窗)
  /// - permanentlyDenied → 引导用户去系统设置,不调用 requestCamera
  Future<void> _toggleExpressionRecognition() async {
    if (_requestingCamera) return; // 防重复点击

    // 关闭流程
    if (_expressionUserEnabled) {
      setState(() => _expressionUserEnabled = false);
      _stopExpressionSafely();
      return;
    }

    // 开启流程:先检查权限
    await _refreshCameraPermission();
    final status = _cameraPermissionStatus;

    if (status == PermissionStatus.permanentlyDenied) {
      // 永久拒绝 — 引导去系统设置,不弹窗
      if (!mounted) return;
      _showOpenSettingsDialog();
      return;
    }

    if (status == PermissionStatus.granted) {
      // 已授权 — 直接启动
      setState(() => _expressionUserEnabled = true);
      await _ensureExpressionInitializedAndStart();
      return;
    }

    // notDetermined / denied — 主动请求一次(系统弹窗)
    setState(() => _requestingCamera = true);
    try {
      final service = ref.read(permissionServiceProvider);
      final granted = await service.requestCamera();
      await _refreshCameraPermission();
      if (!mounted) return;
      if (granted) {
        setState(() => _expressionUserEnabled = true);
        await _ensureExpressionInitializedAndStart();
      }
      // 拒绝后不反复弹窗,UI 显示"权限被拒"状态
    } catch (_) {
      // 静默失败,UI 通过权限状态展示引导
    } finally {
      if (mounted) setState(() => _requestingCamera = false);
    }
  }

  /// 引导用户去系统设置(永久拒绝场景)。
  Future<void> _showOpenSettingsDialog() async {
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('摄像头权限被拒绝'),
        content: const Text(
          '表情识别需要摄像头权限。由于您之前选择了"不再询问",'
          '请前往系统设置中手动授予摄像头权限,然后返回应用重试。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('去设置'),
          ),
        ],
      ),
    );
    if (result == true) {
      await ref.read(permissionServiceProvider).openAppSettings();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _goalController.dispose();
    _restCheckTimer?.cancel();
    // 页面退出立即停止帧处理(隐私要求 §5/§7)
    // 不 dispose 服务本身(由 Provider 管理),仅 pause 摄像头
    _stopExpressionSafely();
    super.dispose();
  }

  /// 应用重启后恢复未结束会话。
  ///
  /// 真实后端模式下,调用 [StudySessionRepository.getActiveSession] 拉取
  /// 当前用户在服务端的 active/paused 会话。若有,则根据 status 同步 UI 状态。
  /// 网络失败时静默处理(不阻塞页面),用户可手动开始新会话。
  Future<void> _recoverActiveSession() async {
    if (_recovered) return;
    _recovered = true;
    try {
      final repo = ref.read(studySessionRepositoryProvider);
      final active = await repo.getActiveSession();
      if (!mounted) return;
      if (active != null) {
        setState(() {
          _displayState = active.status == StudySessionStatus.paused
              ? StudyState.paused
              : StudyState.focusing;
          _selectedRelatedTaskId = active.taskId;
          if (active.goalId != null && active.goalId!.isNotEmpty) {
            _goalController.text = active.goalId!;
          }
        });
        if (active.status == StudySessionStatus.active) {
          _startRestCheck();
        }
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                active.status == StudySessionStatus.paused
                    ? '已恢复未结束的会话(暂停中)'
                    : '已恢复未结束的会话',
              ),
              duration: const Duration(seconds: 2),
            ),
          );
        }
      }
    } catch (_) {
      // 静默失败:不阻塞页面,不伪造恢复成功
    }
  }

  Future<void> _start() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final repo = ref.read(studySessionRepositoryProvider);
      await repo.start(
        goal: _goalController.text.trim().isEmpty
            ? null
            : _goalController.text.trim(),
        relatedTaskId: _selectedRelatedTaskId,
      );
      if (!mounted) return;
      setState(() => _displayState = StudyState.focusing);
      _startRestCheck();
      // 表情识别由用户主动开启,不与"开始学习"绑定(隐私要求 §4)
    } catch (e) {
      _showError('开始学习失败', e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pause() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final repo = ref.read(studySessionRepositoryProvider);
      await repo.pause();
      if (!mounted) return;
      setState(() => _displayState = StudyState.paused);
      // 暂停学习时停止摄像头(隐私要求 §5:用户离开学习状态后停止帧处理)
      _stopExpressionSafely();
    } catch (e) {
      _showError('暂停失败', e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resume() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final repo = ref.read(studySessionRepositoryProvider);
      await repo.resume();
      if (!mounted) return;
      setState(() => _displayState = StudyState.focusing);
      // 表情识别由用户主动开启,不与"恢复学习"绑定
      // 用户若之前开启了表情识别,这里不自动恢复(避免无意中开启摄像头)
    } catch (e) {
      _showError('恢复失败', e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _end() async {
    if (_busy) return;
    final session = ref.read(currentStudySessionProvider).valueOrNull;
    final durationSeconds = session?.durationSeconds ?? 0;
    final pauseSeconds = session?.pauseSeconds ?? 0;

    // 用户主动填写文字感受(科学边界:不根据表情自动填写)
    final result = await StudyFinishDialog.show(
      context,
      durationSeconds: durationSeconds,
      pauseSeconds: pauseSeconds,
    );

    setState(() => _busy = true);
    try {
      final repo = ref.read(studySessionRepositoryProvider);
      // result 为 null 表示用户点击"不填写并结束",仍正常结束会话(不带 self_report)
      await repo.finish(
        selfReport: result?.selfReport,
        selfReportTags: result?.tags,
      );
      // 结束学习 — 停止摄像头 + 重置表情识别状态(隐私要求 §5)
      _stopExpressionSafely();
      _restCheckTimer?.cancel();
      if (!mounted) return;
      setState(() {
        _displayState = StudyState.completed;
        _recentStable = [];
        _expressionUserEnabled = false;
      });
    } catch (e) {
      _showError('结束会话失败', e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// 显示错误 SnackBar(网络失败不伪造保存成功)。
  void _showError(String prefix, Object e) {
    if (!mounted) return;
    final msg = e is ApiException ? '${e.code}: ${e.message}' : e.toString();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$prefix: $msg'),
        duration: const Duration(seconds: 4),
        action: SnackBarAction(label: '知道了', onPressed: () {}),
      ),
    );
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
    // 休息提醒只是 UI 提示,不修改后端会话状态(用户可手动 pause 触发休息记录)
    setState(() => _displayState = StudyState.resting);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('已经学习一段时间了,起来活动一下吧~'),
        duration: const Duration(seconds: 4),
        action: SnackBarAction(
          label: '继续学习',
          onPressed: () {
            if (_displayState == StudyState.resting) {
              setState(() => _displayState = StudyState.focusing);
            }
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
    final config = ref.watch(appConfigProvider);
    final expressionAsync = ref.watch(expressionResultsProvider);
    final expressionStatusAsync = ref.watch(expressionStatusProvider);
    final reduceMotion = ref.watch(reduceMotionProvider);
    // 监听待办列表,用于关联待办选择
    final tasks = ref.watch(taskListProvider);
    // 仅显示未完成且未删除的待办作为可关联项
    final relatedTasks = tasks
        .where((t) => !t.completed && !t.deleted)
        .toList();

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

    // isStudying: 优先依据后端 session,但若本地 _displayState 已进入会话状态
    // (focusing/paused/resting/distracted),也视为学习中 — 避免 StreamProvider
    // 事件传播延迟导致恢复后短暂显示"开始学习"按钮。
    final isStudying = session != null
        ? session.state != StudyState.completed
        : (_displayState != StudyState.idle &&
            _displayState != StudyState.completed);
    // 表情识别启用条件:用户主动开启 + 权限已授权
    final expressionEnabled = _expressionUserEnabled &&
        _cameraPermissionStatus == PermissionStatus.granted;
    // Mock 控制台仅在 debug 模式且启用 Mock 后端时显示(普通用户不显示)
    // 正式参赛版本 Release 构建下 kDebugMode=false,Mock 控制台永远不可见
    final showMockConsole = kDebugMode && config.useMockBackend;
    final isMockMode = config.useMockExpressionRecognition;

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
                  state: _displayState,
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
                  relatedTasks: relatedTasks,
                  selectedRelatedTaskId: _selectedRelatedTaskId,
                  onRelatedTaskChanged: (v) {
                    setState(() => _selectedRelatedTaskId = v);
                  },
                  canStart: !_busy,
                ),
              ),
              // 进行中会话展示休息记录
              if (session != null && session.breaks.isNotEmpty) ...[
                const SizedBox(height: 16),
                StaggeredEnter(
                  delay: const Duration(milliseconds: 90),
                  child: _BreaksCard(breaks: session.breaks),
                ),
              ],
              // 进行中会话展示暂停时长
              if (session != null && session.pauseSeconds > 0) ...[
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Text(
                    '累计暂停 ${_formatPause(session.pauseSeconds)}',
                    style: AppTypography.caption,
                  ),
                ),
              ],
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 120),
                child: TaskBreakdownPanel(
                  relatedTasks: relatedTasks,
                  selectedRelatedTaskId: _selectedRelatedTaskId,
                  goalController: _goalController,
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 180),
                child: ExpressionPanel(
                  enabled: expressionEnabled,
                  result: expressionAsync.valueOrNull,
                  recentStable: _recentStable,
                  onInject: _injectMock,
                  showMockConsole: showMockConsole,
                  status: expressionStatusAsync.valueOrNull,
                  isMockMode: isMockMode,
                  userEnabled: _expressionUserEnabled,
                  isRequestingPermission: _requestingCamera,
                  cameraPermissionStatus: _cameraPermissionStatus,
                  onToggle: _toggleExpressionRecognition,
                ),
              ),
              const SizedBox(height: 16),
              StaggeredEnter(
                delay: const Duration(milliseconds: 240),
                child: CompanionSuggestionPanel(
                  state: _displayState,
                  expression: expressionAsync.valueOrNull,
                  recentStable: _recentStable,
                ),
              ),
              const SizedBox(height: 16),
              const StaggeredEnter(
                delay: Duration(milliseconds: 300),
                child: StudyHistorySummary(),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  String _formatPause(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    if (m == 0) return '$s 秒';
    return '$m 分 $s 秒';
  }
}

/// 休息记录卡片 — 展示当前会话的所有休息记录。
class _BreaksCard extends StatelessWidget {
  const _BreaksCard({required this.breaks});

  final List<StudyBreak> breaks;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.coffee_outlined, size: 18, color: c.primary),
              const SizedBox(width: 6),
              const Text('休息记录', style: AppTypography.subtitle),
            ],
          ),
          const SizedBox(height: 10),
          ...breaks.map((b) => _BreakRow(brk: b)),
        ],
      ),
    );
  }
}

class _BreakRow extends StatelessWidget {
  const _BreakRow({required this.brk});

  final StudyBreak brk;

  @override
  Widget build(BuildContext context) {
    final c = context.appColors;
    final dur = brk.duration;
    final durText = dur == null
        ? '进行中'
        : dur.inMinutes == 0
            ? '${dur.inSeconds} 秒'
            : '${dur.inMinutes} 分 ${dur.inSeconds % 60} 秒';
    final start = brk.startedAt;
    final startText =
        '${start.hour.toString().padLeft(2, "0")}:${start.minute.toString().padLeft(2, "0")}';
    final end = brk.endedAt;
    final endText = end == null
        ? '—'
        : '${end.hour.toString().padLeft(2, "0")}:${end.minute.toString().padLeft(2, "0")}';
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Icon(
            brk.isOpen ? Icons.timer_outlined : Icons.check_circle_outline,
            size: 14,
            color: brk.isOpen ? c.warning : c.success,
          ),
          const SizedBox(width: 6),
          Text('$startText → $endText', style: AppTypography.caption),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              brk.reason == null || brk.reason!.isEmpty
                  ? '未填写原因'
                  : '原因:${brk.reason}',
              style: AppTypography.caption,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            durText,
            style: AppTypography.caption.copyWith(color: c.textSecondary),
          ),
        ],
      ),
    );
  }
}
