import 'package:flutter/material.dart';

import '../../../../app/design_system/app_colors.dart';
import '../../../../app/design_system/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../data/models/expression.dart';
import '../../../../data/services/expression_service_status.dart';
import '../../../../data/services/service_interfaces.dart'
    show PermissionStatus;
import 'expression_result_view.dart';
import 'mock_expression_control.dart';

/// 表情识别面板 — 真实 CNN / Mock 双模式可视化。
///
/// 显示内容(对齐 AGENTS.md §6 UI 要求):
/// - **模型状态**:加载中 / 已就绪 / 失败 / 未安装(真实模式)/ Mock 标识(仅 Debug)
/// - **摄像头状态**:空闲 / 启动中 / 运行中 / 已停止 / 错误 / 权限拒绝
/// - **平台降级**:Web/桌面不支持 TFLite / ML Kit 时的明确提示
/// - **当前表情**:类别 + 置信度 + 概率分布
/// - **时序趋势**:最近 5 帧稳定结果
/// - **辅助提示**:仅识别可观察表情,不作心理诊断
///
/// **科学边界**(AGENTS.md §3):
/// - 低置信度/无人脸时显示"暂时无法稳定判断当前表情",不触发情绪安慰
/// - 禁止出现"你很焦虑""你抑郁了"等诊断式文案
class ExpressionPanel extends StatelessWidget {
  const ExpressionPanel({
    super.key,
    required this.enabled,
    required this.result,
    required this.recentStable,
    required this.onInject,
    required this.showMockConsole,
    this.status,
    this.isMockMode = false,
    required this.userEnabled,
    required this.isRequestingPermission,
    required this.cameraPermissionStatus,
    required this.onToggle,
  });

  /// 表情识别是否启用(用户开关 + 权限 + 模型就绪)。
  final bool enabled;

  /// 当前表情识别结果(可空)。
  final ExpressionResult? result;

  /// 最近稳定帧(用于趋势展示)。
  final List<ExpressionResult> recentStable;

  /// Mock 注入回调(仅 Mock 模式有效)。
  final void Function(ExpressionLabel?) onInject;

  /// 是否显示 Mock 控制台(仅 Debug + Mock 模式)。
  final bool showMockConsole;

  /// 服务状态流(模型/摄像头/平台降级)。
  final ExpressionServiceStatus? status;

  /// 当前是否为 Mock 模式(用于显示明显标识)。
  final bool isMockMode;

  /// 用户是否主动开启了表情识别(独立于学习会话状态)。
  final bool userEnabled;

  /// 是否正在请求权限(防止重复点击)。
  final bool isRequestingPermission;

  /// 当前摄像头权限状态(用于显示权限引导)。
  final PermissionStatus? cameraPermissionStatus;

  /// 用户点击开启/关闭表情识别的回调。
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 标题行 + 状态徽章
          _buildHeader(),
          const SizedBox(height: 4),
          // 副标题(模型版本 / Mock 标识)
          _buildSubHeader(),
          const SizedBox(height: 12),
          // 用户主动开启/关闭开关(对齐 AGENTS.md §2.3 "用户主动开启后才初始化摄像头")
          _buildToggleRow(),
          const SizedBox(height: 12),
          if (_hasPlatformDegradation) ...[
            _buildPlatformDegradation(),
          ] else if (userEnabled && _modelNotReady) ...[
            _buildModelNotReady(),
          ] else if (userEnabled) ...[
            _resultView(),
            if (showMockConsole) ...[
              const SizedBox(height: 16),
              MockExpressionControl(onInject: onInject),
            ],
          ] else ...[
            _buildDisabledHint(),
          ],
        ],
      ),
    );
  }

  Widget _buildHeader() {
    final isRunning = status?.isInferring ?? false;
    final isModelReady = status?.isModelReady ?? false;

    String badgeText;
    Color badgeBg;
    Color badgeFg;
    if (!userEnabled) {
      badgeText = '未开启';
      badgeBg = AppColors.bgSunken;
      badgeFg = AppColors.textTertiary;
    } else if (isRunning) {
      badgeText = '运行中';
      badgeBg = AppColors.successSubtle;
      badgeFg = AppColors.success;
    } else if (isModelReady) {
      badgeText = '已就绪';
      badgeBg = AppColors.primarySubtle;
      badgeFg = AppColors.primary;
    } else {
      badgeText = '未就绪';
      badgeBg = AppColors.bgSunken;
      badgeFg = AppColors.textTertiary;
    }

    return Row(
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
            color: badgeBg,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            badgeText,
            style: AppTypography.label.copyWith(
              color: badgeFg,
              fontSize: 10.5,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSubHeader() {
    final modelVersion = status?.modelVersion.isNotEmpty == true
        ? status!.modelVersion
        : (isMockMode ? 'mock-v0.1' : '加载中…');

    final modeText = isMockMode ? 'Mock 模式 · ' : '真实 CNN · ';
    const privacyText = ' · 仅识别可观察表情,不作心理诊断';

    return Text(
      modeText + modelVersion + privacyText,
      style: AppTypography.overline.copyWith(
        color: isMockMode ? AppColors.warning : AppColors.textTertiary,
        fontWeight: isMockMode ? FontWeight.w700 : FontWeight.w600,
      ),
    );
  }

  /// 开启/关闭开关 + 权限引导(永久拒绝时显示提示)。
  Widget _buildToggleRow() {
    // 永久拒绝 — 显示"去系统设置"提示
    if (cameraPermissionStatus == PermissionStatus.permanentlyDenied) {
      return Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: AppColors.dangerSubtle,
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Row(
          children: [
            Icon(
              Icons.no_photography_outlined,
              color: AppColors.danger,
              size: 18,
            ),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                '摄像头权限被永久拒绝。点击下方按钮前往系统设置。',
                style: AppTypography.caption,
              ),
            ),
          ],
        ),
      );
    }

    return Row(
      children: [
        Expanded(
          child: Text(
            userEnabled ? '已开启摄像头识别' : '主动开启后才会启动摄像头',
            style: AppTypography.caption.copyWith(
              color: userEnabled ? AppColors.success : AppColors.textSecondary,
            ),
          ),
        ),
        FilledButton.tonalIcon(
          onPressed: isRequestingPermission ? null : onToggle,
          icon: isRequestingPermission
              ? const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Icon(
                  userEnabled
                      ? Icons.videocam_off_outlined
                      : Icons.videocam_outlined,
                  size: 16,
                ),
          label: Text(
            isRequestingPermission ? '请求权限中…' : (userEnabled ? '关闭识别' : '开启识别'),
          ),
          style: FilledButton.styleFrom(
            backgroundColor:
                userEnabled ? AppColors.dangerSubtle : AppColors.primarySubtle,
            foregroundColor: userEnabled ? AppColors.danger : AppColors.primary,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            minimumSize: const Size(0, 32),
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
        ),
      ],
    );
  }

  /// 用户未开启时的提示(替代旧的 ExpressionDisabledHint)。
  Widget _buildDisabledHint() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(
        children: [
          const Icon(
            Icons.videocam_off_outlined,
            size: 28,
            color: AppColors.textTertiary,
          ),
          const SizedBox(height: 8),
          Text(
            '点击上方"开启识别"启动摄像头\n帧数据仅在本地处理,不会上传或保存',
            style: AppTypography.caption.copyWith(
              color: AppColors.textTertiary,
              height: 1.4,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  bool get _hasPlatformDegradation =>
      status?.platformDegradation != null &&
      status!.platformDegradation!.isNotEmpty;

  bool get _modelNotReady {
    final ms = status?.modelState;
    return ms == ExpressionModelState.loading ||
        ms == ExpressionModelState.failed ||
        ms == ExpressionModelState.notInstalled;
  }

  Widget _buildPlatformDegradation() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.warningSubtle,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.warning_amber_rounded,
            color: AppColors.warning,
            size: 20,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              status?.platformDegradation ?? '',
              style: AppTypography.body.copyWith(
                color: AppColors.textPrimary,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModelNotReady() {
    final ms = status?.modelState;
    String title;
    String? detail;
    IconData icon;
    Color color;

    switch (ms) {
      case ExpressionModelState.loading:
        title = '正在加载模型…';
        icon = Icons.hourglass_top_rounded;
        color = AppColors.textSecondary;
      case ExpressionModelState.notInstalled:
        title = '模型未安装';
        detail = status?.modelError ??
            '请等待 cnn-training 分支提供 expression_model.tflite '
                '与 preprocess.json,放入 assets/models/ 后重新构建应用。';
        icon = Icons.download_outlined;
        color = AppColors.warning;
      case ExpressionModelState.failed:
        title = '模型加载失败';
        detail = status?.modelError ?? '未知错误';
        icon = Icons.error_outline_rounded;
        color = AppColors.danger;
      default:
        title = '模型未就绪';
        icon = Icons.hourglass_disabled_outlined;
        color = AppColors.textTertiary;
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: AppTypography.bodyStrong.copyWith(color: color),),
                if (detail != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    detail,
                    style: AppTypography.caption.copyWith(fontSize: 11.5),
                  ),
                ],
                // 摄像头错误(如有)
                if (status?.cameraError != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    '摄像头: ${status!.cameraError}',
                    style: AppTypography.caption.copyWith(
                      fontSize: 11.5,
                      color: AppColors.danger,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _resultView() {
    // 摄像头未运行 — 显示状态
    final camState = status?.cameraState;
    if (camState == CameraState.starting) {
      return const Row(
        children: [
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: 10),
          Text('正在启动摄像头…', style: AppTypography.caption),
        ],
      );
    }
    if (camState == CameraState.denied) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.dangerSubtle,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Row(
          children: [
            Icon(Icons.no_photography_outlined, color: AppColors.danger),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                '摄像头权限被拒绝。请在系统设置中授予后重试。',
                style: AppTypography.body,
              ),
            ),
          ],
        ),
      );
    }
    if (camState == CameraState.error) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.dangerSubtle,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            const Icon(Icons.error_outline_rounded, color: AppColors.danger),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '摄像头错误: ${status?.cameraError ?? "未知"}',
                style: AppTypography.body,
              ),
            ),
          ],
        ),
      );
    }
    if (camState == CameraState.idle || camState == CameraState.stopped) {
      return Row(
        children: [
          const Icon(
            Icons.videocam_off_outlined,
            color: AppColors.textTertiary,
            size: 18,
          ),
          const SizedBox(width: 8),
          Text(
            '摄像头已停止,可重新开启',
            style: AppTypography.caption.copyWith(
              color: AppColors.textTertiary,
            ),
          ),
        ],
      );
    }
    // 摄像头运行中但还没结果
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
    return ExpressionResultView(
      result: result!,
      recentStable: recentStable,
      // 性能指标(推理延迟 / 帧数)
      inferenceMillis: status?.lastInferenceMillis,
      processedFrames: status?.processedFrames,
    );
  }
}
