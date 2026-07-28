import 'package:equatable/equatable.dart';

/// 表情识别服务整体状态。
///
/// UI 通过此状态显示:
/// - 模型加载情况(加载中 / 已就绪 / 失败 / 未安装)
/// - 摄像头状态(空闲 / 启动中 / 运行中 / 已停止 / 错误 / 权限拒绝)
/// - 平台降级说明(Web / 桌面不支持时的明确提示)
///
/// **科学边界**(AGENTS.md §3):
/// 状态信息仅描述服务运行情况,不进行心理诊断,
/// 不出现"你很焦虑""你抑郁了"等诊断式文案。
class ExpressionServiceStatus extends Equatable {
  const ExpressionServiceStatus({
    required this.modelState,
    required this.cameraState,
    required this.modelVersion,
    this.modelError,
    this.cameraError,
    this.platformDegradation,
    this.lastInferenceMillis,
    this.processedFrames,
  });

  /// 初始空状态(尚未 initialize)。
  factory ExpressionServiceStatus.initial() => const ExpressionServiceStatus(
        modelState: ExpressionModelState.idle,
        cameraState: CameraState.idle,
        modelVersion: '',
      );

  final ExpressionModelState modelState;
  final CameraState cameraState;
  final String modelVersion;
  final String? modelError;
  final String? cameraError;

  /// 平台降级说明(Web / 桌面等不支持 TFLite / ML Kit 时填入,
  /// UI 应明确显示,不静默回退 Mock)。
  final String? platformDegradation;

  /// 最近一次推理耗时(ms),用于 UI 显示性能指标。
  final int? lastInferenceMillis;

  /// 已处理帧数(用于 UI 显示运行情况)。
  final int? processedFrames;

  /// 当前服务是否可用(模型已加载且无平台降级)。
  bool get isModelReady =>
      modelState == ExpressionModelState.ready && platformDegradation == null;

  /// 当前是否正在推理(模型就绪 + 摄像头运行中)。
  bool get isInferring =>
      isModelReady && cameraState == CameraState.running;

  ExpressionServiceStatus copyWith({
    ExpressionModelState? modelState,
    CameraState? cameraState,
    String? modelVersion,
    String? modelError,
    String? cameraError,
    String? platformDegradation,
    int? lastInferenceMillis,
    int? processedFrames,
  }) {
    return ExpressionServiceStatus(
      modelState: modelState ?? this.modelState,
      cameraState: cameraState ?? this.cameraState,
      modelVersion: modelVersion ?? this.modelVersion,
      modelError: modelError ?? this.modelError,
      cameraError: cameraError ?? this.cameraError,
      platformDegradation: platformDegradation ?? this.platformDegradation,
      lastInferenceMillis: lastInferenceMillis ?? this.lastInferenceMillis,
      processedFrames: processedFrames ?? this.processedFrames,
    );
  }

  @override
  List<Object?> get props => [
        modelState,
        cameraState,
        modelVersion,
        modelError,
        cameraError,
        platformDegradation,
        lastInferenceMillis,
        processedFrames,
      ];
}

/// 模型加载状态机。
enum ExpressionModelState {
  /// 尚未调用 initialize。
  idle,

  /// 正在加载模型/标签/预处理配置。
  loading,

  /// 模型已就绪,可执行推理。
  ready,

  /// 模型加载失败(文件缺失/解析失败/校验失败)。
  /// Release 模式下显示明确错误,不静默回退 Mock。
  failed,

  /// 模型未安装(assets/models/ 下无 expression_model.tflite)。
  /// 与 failed 区分:未安装是预期状态(等待 cnn-training 分支提供),
  /// failed 是加载过程中发生异常。
  notInstalled,
}

/// 摄像头状态机。
enum CameraState {
  /// 尚未启动。
  idle,

  /// 正在启动(初始化摄像头控制器)。
  starting,

  /// 摄像头运行中,正在采集帧。
  running,

  /// 已主动停止(用户暂停 / 页面退出 / 应用后台)。
  stopped,

  /// 摄像头错误(设备占用 / 初始化失败)。
  error,

  /// 摄像头权限被拒绝。
  denied,
}
