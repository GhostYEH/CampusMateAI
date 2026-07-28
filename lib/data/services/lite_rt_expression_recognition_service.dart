import 'dart:async';
import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:camera/camera.dart';
import 'package:crypto/crypto.dart' as crypto;
import 'package:flutter/foundation.dart';
import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';
import 'package:image/image.dart' as img;
import 'package:tflite_flutter/tflite_flutter.dart';

import '../models/expression.dart';
import '../../mock/mock_services/expression_smoother.dart';
import 'camera_frame_converter.dart';
import 'expression_model_config.dart';
import 'expression_preprocessor.dart';
import 'expression_service_status.dart';
import 'service_interfaces.dart';

/// 真实 LiteRT(TFLite)CNN 表情识别服务。
///
/// 完整链路:
/// 摄像头帧(CameraImage) → 平台帧转换(img.Image) →
/// ML Kit 人脸检测(FaceBox) → 图像预处理(Float32 张量) →
/// TFLite CNN 推理(七类概率) → ExpressionSmoother 时序平滑 →
/// ExpressionResult 流。
///
/// **隐私保证**(AGENTS.md §3):
/// - 摄像头帧仅在内存中处理,不写入文件系统
/// - 不上传任何图像数据(无 Dio/网络调用)
/// - 处理完成后输入引用立即丢弃,等待 GC 回收
/// - 人脸边界框仅用于裁剪,不存储人脸特征
///
/// **科学边界**(AGENTS.md §3):
/// - 仅识别可观察到的面部表情,不进行心理诊断
/// - 低置信度时返回 `unknown`,UI 提示"暂时无法稳定判断当前表情",
///   且不触发情绪安慰
/// - 疲劳(fatigued)不是 CNN 七分类标签,需独立规则判断
///   (本服务不输出 fatigue,由 UI 结合学习时长等独立判断)
///
/// **平台策略**(AGENTS.md §2.4):
/// - Android: 完整支持(真实摄像头 + ML Kit + TFLite)
/// - iOS: 完整支持(权限/编译已配置,实机验证待设备)
/// - Web: 不支持 TFLite 与 ML Kit → 通过 [platformDegradation] 明确降级,
///   不静默回退 Mock
/// - Release: 模型加载失败时通过 [status] 暴露错误,不静默回退 Mock
/// - Debug: Mock 只能通过 [AppConfig.useMockExpressionRecognition] 显式启用,
///   UI 显示明显 Mock 标识
class LiteRtExpressionRecognitionService
    implements ExpressionRecognitionService {
  LiteRtExpressionRecognitionService({
    this.modelAssetPath = 'assets/models/expression_model.tflite',
    this.configBasePath = 'assets/models',
    ExpressionSmoother? smoother,
    this.targetFps = 8,
  }) : _smoother = smoother ??
            ExpressionSmoother(
              confidenceThreshold: 0.45,
              stableFrames: 5,
              windowSize: 7,
            );

  final String modelAssetPath;
  final String configBasePath;
  final ExpressionSmoother _smoother;
  final int targetFps;

  // 流控制器
  final _resultController = StreamController<ExpressionResult>.broadcast();
  final _statusController =
      StreamController<ExpressionServiceStatus>.broadcast();

  // 推理相关
  Interpreter? _interpreter;
  ExpressionModelConfig? _config;
  ExpressionPreprocessor? _preprocessor;
  final _frameConverter = CameraFrameConverter();
  FaceDetector? _faceDetector;

  // 摄像头相关
  CameraController? _cameraController;
  bool _isStartingCamera = false;
  bool _running = false;
  bool _disposed = false;
  int _processedFrames = 0;
  int? _lastInferenceMillis;

  // 帧节流(避免在 CPU 上排队)
  DateTime? _lastFrameAt;
  final Duration _minFrameInterval =
      const Duration(milliseconds: 125); // ~8 FPS 上限

  // 平台降级标记(初始化时检查一次,后续不再变化)
  String? _platformDegradation;
  bool _platformSupported = true;

  @override
  Stream<ExpressionResult> get results => _resultController.stream;

  @override
  Stream<ExpressionServiceStatus> get status => _statusController.stream;

  @override
  bool get isRunning => _running;

  /// 当前平台是否支持真实 CNN 推理。
  ///
  /// Web 平台不支持 tflite_flutter 与 google_mlkit_face_detection,
  /// 桌面平台(Linux/Windows)TFLite 支持有限。
  static bool get isPlatformSupported {
    if (kIsWeb) return false;
    return Platform.isAndroid || Platform.isIOS;
  }

  @override
  Future<void> initialize() async {
    if (_disposed) {
      throw StateError('LiteRtExpressionRecognitionService already disposed');
    }

    // 1. 平台检查 — Web/桌面明确降级,不静默回退 Mock
    if (!isPlatformSupported) {
      _platformSupported = false;
      _platformDegradation = _platformDegradationMessage();
      _emitStatus(
        ExpressionServiceStatus(
          modelState: ExpressionModelState.idle,
          cameraState: CameraState.idle,
          modelVersion: '',
          platformDegradation: _platformDegradation,
        ),
      );
      return;
    }

    // 2. 加载模型配置(labels.json / preprocess.json / model_card.json)
    _emitStatus(
      const ExpressionServiceStatus(
        modelState: ExpressionModelState.loading,
        cameraState: CameraState.idle,
        modelVersion: '',
      ),
    );

    try {
      _config = await ExpressionModelConfig.loadFromAssets(
        basePath: configBasePath,
      );
    } on ModelConfigException catch (e) {
      // 配置文件缺失 — 视为模型未安装(等待 cnn-training 分支提供)
      _emitStatus(
        ExpressionServiceStatus(
          modelState: ExpressionModelState.notInstalled,
          cameraState: CameraState.idle,
          modelVersion: '',
          modelError: e.message,
        ),
      );
      return;
    } catch (e) {
      _emitStatus(
        ExpressionServiceStatus(
          modelState: ExpressionModelState.failed,
          cameraState: CameraState.idle,
          modelVersion: '',
          modelError: '模型配置加载失败: $e',
        ),
      );
      return;
    }

    // 3. 加载 TFLite 模型字节
    final modelBytes = await loadModelBytes(modelAssetPath);
    if (modelBytes == null) {
      _emitStatus(
        ExpressionServiceStatus(
          modelState: ExpressionModelState.notInstalled,
          cameraState: CameraState.idle,
          modelVersion: _config!.modelVersion,
          modelError: 'expression_model.tflite 未找到。'
              '请等待 cnn-training 分支提供模型文件,放入 assets/models/ 后重新构建。',
        ),
      );
      return;
    }

    // 4. SHA-256 完整性校验(可选,若 config 中提供 modelSha256)
    if (_config!.modelSha256 != null && _config!.modelSha256!.isNotEmpty) {
      final actualSha = _computeSha256(modelBytes);
      if (actualSha != _config!.modelSha256) {
        _emitStatus(
          ExpressionServiceStatus(
            modelState: ExpressionModelState.failed,
            cameraState: CameraState.idle,
            modelVersion: _config!.modelVersion,
            modelError: '模型 SHA-256 校验失败:期望 ${_config!.modelSha256},'
                '实际 $actualSha。模型文件可能已损坏或被替换。',
          ),
        );
        return;
      }
    }

    // 5. 构造 TFLite Interpreter
    try {
      _interpreter = Interpreter.fromBuffer(
        modelBytes,
        options: InterpreterOptions()..threads = 2,
      );
    } catch (e) {
      _emitStatus(
        ExpressionServiceStatus(
          modelState: ExpressionModelState.failed,
          cameraState: CameraState.idle,
          modelVersion: _config!.modelVersion,
          modelError: 'TFLite Interpreter 初始化失败: $e',
        ),
      );
      return;
    }

    // 6. 构造预处理器与人脸检测器
    _preprocessor = ExpressionPreprocessor(_config!);
    _faceDetector = FaceDetector(
      options: FaceDetectorOptions(
        performanceMode: FaceDetectorMode.fast,
        // 关键点/分类会增加延迟,FER2013 不需要
        enableLandmarks: false,
        enableContours: false,
        enableClassification: false,
        enableTracking: false,
        minFaceSize: 0.15,
      ),
    );

    _emitStatus(
      ExpressionServiceStatus(
        modelState: ExpressionModelState.ready,
        cameraState: CameraState.idle,
        modelVersion: _config!.modelVersion,
      ),
    );
  }

  @override
  Future<void> start() async {
    if (_disposed) return;
    if (!_platformSupported) {
      // 平台不支持时,不启动摄像头,保持降级状态
      return;
    }
    if (_interpreter == null || _config == null || _preprocessor == null) {
      // 模型未就绪 — 不启动摄像头,UI 通过 status 流显示错误
      return;
    }
    if (_running) return;
    if (_isStartingCamera) return; // 防止重复点击
    _isStartingCamera = true;

    _emitStatus(
      ExpressionServiceStatus(
        modelState: ExpressionModelState.ready,
        cameraState: CameraState.starting,
        modelVersion: _config!.modelVersion,
      ),
    );

    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        _emitStatus(
          ExpressionServiceStatus(
            modelState: ExpressionModelState.ready,
            cameraState: CameraState.error,
            modelVersion: _config!.modelVersion,
            cameraError: '设备无可用摄像头',
          ),
        );
        _isStartingCamera = false;
        return;
      }

      // 优先使用前置摄像头
      final frontCamera = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );

      _cameraController = CameraController(
        frontCamera,
        // 低分辨率够用于 48x48 模型,降低 CPU/带宽
        ResolutionPreset.low,
        enableAudio: false,
        imageFormatGroup: Platform.isIOS
            ? ImageFormatGroup.bgra8888
            : ImageFormatGroup.yuv420,
      );

      await _cameraController!.initialize();
      await _cameraController!.startImageStream(_onCameraFrame);

      _running = true;
      _isStartingCamera = false;
      _processedFrames = 0;
      _smoother.reset();

      _emitStatus(
        ExpressionServiceStatus(
          modelState: ExpressionModelState.ready,
          cameraState: CameraState.running,
          modelVersion: _config!.modelVersion,
          processedFrames: 0,
        ),
      );
    } catch (e) {
      _isStartingCamera = false;
      _emitStatus(
        ExpressionServiceStatus(
          modelState: ExpressionModelState.ready,
          cameraState: CameraState.error,
          modelVersion: _config?.modelVersion ?? '',
          cameraError: '摄像头启动失败: $e',
        ),
      );
    }
  }

  @override
  Future<void> pause() async {
    await _stopCameraOnly();
    _emitStatus(
      ExpressionServiceStatus(
        modelState: _interpreter != null
            ? ExpressionModelState.ready
            : ExpressionModelState.idle,
        cameraState: CameraState.stopped,
        modelVersion: _config?.modelVersion ?? '',
        processedFrames: _processedFrames,
        platformDegradation: _platformDegradation,
      ),
    );
  }

  @override
  Future<void> stop() async {
    await _stopCameraOnly();
    _smoother.reset();
    _processedFrames = 0;
    _emitStatus(
      ExpressionServiceStatus(
        modelState: _interpreter != null
            ? ExpressionModelState.ready
            : ExpressionModelState.idle,
        cameraState: CameraState.stopped,
        modelVersion: _config?.modelVersion ?? '',
        processedFrames: 0,
        platformDegradation: _platformDegradation,
      ),
    );
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    _running = false;
    await _stopCameraOnly();
    _interpreter?.close();
    _interpreter = null;
    await _faceDetector?.close();
    _faceDetector = null;
    await _resultController.close();
    await _statusController.close();
  }

  /// 仅停止摄像头(不释放模型),用于 pause/页面退出/应用后台。
  Future<void> _stopCameraOnly() async {
    _running = false;
    final c = _cameraController;
    if (c == null) return;
    _cameraController = null;
    try {
      // 必须先停止帧流,再 dispose,否则会泄漏
      if (c.value.isStreamingImages) {
        await c.stopImageStream();
      }
      await c.dispose();
    } catch (_) {
      // 忽略 dispose 异常(可能在页面退出时已被回收)
    }
  }

  /// 摄像头帧回调 — 在 camera 插件的后台线程触发。
  ///
  /// **隐私关键**: 此方法仅处理内存中的帧数据,
  /// 不调用任何 IO/网络 API,不写入文件。
  void _onCameraFrame(CameraImage frame) {
    if (!_running || _disposed) return;
    if (_interpreter == null || _preprocessor == null || _config == null) {
      return;
    }

    // 帧节流:避免在低性能设备上堆积帧
    final now = DateTime.now();
    if (_lastFrameAt != null &&
        now.difference(_lastFrameAt!) < _minFrameInterval) {
      return;
    }
    _lastFrameAt = now;

    // 异步处理,避免阻塞 camera 线程
    _processFrame(frame).catchError((_) {
      // 单帧处理失败不影响后续帧
    });
  }

  Future<void> _processFrame(CameraImage frame) async {
    final sw = Stopwatch()..start();

    try {
      // 1. 平台帧转换 → img.Image(RGB)
      final imgImage = _convertFrame(frame);
      if (imgImage == null) return;

      // 2. ML Kit 人脸检测
      final faceBox = await _detectFace(imgImage);

      // 3. 预处理(含人脸裁剪、resize、归一化)
      //    无人脸时 preprocessor.process 返回 null
      final tensor = _preprocessor!.process(imgImage, faceBox);
      if (tensor == null) {
        // 无人脸 — 输出 noFace 结果
        _emitNoFaceResult();
        return;
      }

      // 4. TFLite 推理
      final probabilities = _runInference(tensor);
      if (probabilities == null) return;

      // 5. 时序平滑
      final result = _smoother.smooth(
        probabilities,
        DateTime.now(),
        modelVersion: _config!.modelVersion,
      );

      _processedFrames++;
      _lastInferenceMillis = sw.elapsedMilliseconds;

      if (!_resultController.isClosed) {
        _resultController.add(result);
      }

      // 周期性更新状态(每 5 帧更新一次,避免过度刷新 UI)
      if (_processedFrames % 5 == 0) {
        _emitStatus(
          ExpressionServiceStatus(
            modelState: ExpressionModelState.ready,
            cameraState: CameraState.running,
            modelVersion: _config!.modelVersion,
            lastInferenceMillis: _lastInferenceMillis,
            processedFrames: _processedFrames,
          ),
        );
      }
    } catch (_) {
      // 单帧处理失败 — 静默,下一帧重试
    }
  }

  /// 将 CameraImage 转换为 img.Image。
  ///
  /// Android: YUV420 → 灰度(因 FER2013 是灰度模型,直接用 Y 平面最快)
  /// iOS: BGRA8888 → RGB
  /// Web: 不应到达此处(平台降级已拦截)
  img.Image? _convertFrame(CameraImage frame) {
    if (Platform.isIOS) {
      // iOS: BGRA8888 单 plane
      final plane = frame.planes.first;
      return _frameConverter.bgraToRgb(
        plane.bytes,
        frame.width,
        frame.height,
        plane.bytesPerRow,
      );
    }
    // Android: YUV420,取 Y 平面即可(灰度模型)
    // 若 config.channels == 3,需要完整 YUV→RGB,这里仅在灰度时走快路径
    final yPlane = frame.planes.first;
    return _frameConverter.yPlaneToGrayscale(
      yPlane.bytes,
      frame.width,
      frame.height,
      yPlane.bytesPerRow,
    );
  }

  /// 使用 ML Kit 检测人脸,返回归一化坐标的边界框。
  ///
  /// 返回 null 表示未检测到人脸。
  Future<FaceBox?> _detectFace(img.Image image) async {
    if (_faceDetector == null) return null;

    // img.Image → InputImage
    // ML Kit 需要 RGBA 格式的字节数据
    final rgbaBytes = _imageToRgbaBytes(image);
    final inputImage = InputImage.fromBytes(
      bytes: rgbaBytes,
      metadata: InputImageMetadata(
        size: ui.Size(image.width.toDouble(), image.height.toDouble()),
        rotation: InputImageRotation.rotation0deg,
        format: Platform.isIOS
            ? InputImageFormat.bgra8888
            : InputImageFormat.yuv420,
        // 单 plane
        bytesPerRow: image.width * 4,
      ),
    );

    final faces = await _faceDetector!.processImage(inputImage);
    if (faces.isEmpty) return null;

    // 取最大的人脸(按面积)
    final face = faces.reduce(
      (a, b) => ((b.boundingBox.width * b.boundingBox.height) >
              (a.boundingBox.width * a.boundingBox.height))
          ? b
          : a,
    );

    final box = face.boundingBox;
    return FaceBox(
      left: box.left.toDouble(),
      top: box.top.toDouble(),
      right: box.right.toDouble(),
      bottom: box.bottom.toDouble(),
    );
  }

  /// 将 img.Image 转换为 RGBA 字节流(供 ML Kit 使用)。
  ///
  /// 此处内存仅短暂持有,转换完成后立即丢弃。
  Uint8List _imageToRgbaBytes(img.Image image) {
    final rgba = Uint8List(image.width * image.height * 4);
    var i = 0;
    for (var y = 0; y < image.height; y++) {
      for (var x = 0; x < image.width; x++) {
        final p = image.getPixel(x, y);
        rgba[i++] = p.r.toInt();
        rgba[i++] = p.g.toInt();
        rgba[i++] = p.b.toInt();
        rgba[i++] = 255;
      }
    }
    return rgba;
  }

  /// 运行 TFLite 推理,返回七类概率分布。
  ///
  /// 返回 null 表示推理失败。
  Map<ExpressionLabel, double>? _runInference(Float32List inputTensor) {
    final interpreter = _interpreter;
    final config = _config;
    if (interpreter == null || config == null) return null;

    try {
      // 输出张量形状 [1, 7]
      final outputShape = interpreter.getOutputTensor(0).shape;
      final outputSize = outputShape.reduce((a, b) => a * b);
      final outputBuffer =
          List.filled(outputSize, 0.0).reshape([1, outputSize]);

      // NHWC 输入 [1, H, W, C]
      final input = inputTensor.reshape([
        1,
        config.inputHeight,
        config.inputWidth,
        config.channels,
      ]);

      interpreter.run(input, outputBuffer);

      // 取出 [1, N] 的第一行
      final raw = (outputBuffer[0] as List).cast<double>();
      if (raw.length != config.outputClasses) {
        // 输出维度与期望不符 — 不静默回退 Mock,标记为失败
        return null;
      }

      // 根据 outputFormat 转换为概率分布
      final probabilities = _toProbabilityMap(raw, config);

      // 验证概率总和(允许少量误差)
      final sum = probabilities.values.fold<double>(0, (a, b) => a + b);
      if (sum < 0.9 || sum > 1.1) {
        // 异常输出,跳过本帧
        return null;
      }

      return probabilities;
    } catch (_) {
      return null;
    }
  }

  /// 将原始输出转换为七类概率分布。
  ///
  /// - softmax: 直接使用(已归一化)
  /// - logits: 手动 softmax
  /// - sigmoid: 不归一化(本项目不使用)
  Map<ExpressionLabel, double> _toProbabilityMap(
    List<double> raw,
    ExpressionModelConfig config,
  ) {
    List<double> probs;
    switch (config.outputFormat) {
      case 'logits':
        probs = _softmax(raw);
        break;
      case 'softmax':
      default:
        probs = raw;
        break;
    }

    // 映射到 ExpressionLabel(注意:ExpressionLabel 含 unknown/noFace,
    // 但 CNN 七分类不含这两类,故此处只填前 7 个,其余补 0)
    final result = <ExpressionLabel, double>{
      for (final l in ExpressionLabel.values) l: 0,
    };
    for (var i = 0; i < config.labels.length; i++) {
      final label = config.labelForIndex(i);
      result[label] = probs[i];
    }
    return result;
  }

  /// 手动 softmax(用于 logits 输出)。
  ///
  /// 数值稳定实现:先减去 max(logits) 防止 exp 溢出。
  List<double> _softmax(List<double> logits) {
    if (logits.isEmpty) return const [];
    final maxLogit = logits.reduce(math.max);
    final exps = logits
        .map((l) => (l - maxLogit) < -700 ? 0.0 : math.exp(l - maxLogit))
        .toList();
    final sum = exps.fold<double>(0, (a, b) => a + b);
    if (sum == 0) return List.filled(logits.length, 1.0 / logits.length);
    return exps.map((e) => e / sum).toList();
  }

  void _emitNoFaceResult() {
    if (_resultController.isClosed) return;
    final result = ExpressionResult(
      label: ExpressionLabel.noFace,
      confidence: 0,
      probabilities: {
        for (final l in ExpressionLabel.values) l: 0,
      },
      timestamp: DateTime.now(),
      isStable: false,
      modelVersion: _config?.modelVersion ?? 'unknown',
    );
    _resultController.add(result);
  }

  void _emitStatus(ExpressionServiceStatus s) {
    if (_statusController.isClosed) return;
    _statusController.add(s);
  }

  String _platformDegradationMessage() {
    if (kIsWeb) {
      return 'Web 平台不支持 TFLite CNN 推理与 ML Kit 人脸检测,'
          '表情识别功能不可用。请在 Android 或 iOS 设备上使用。';
    }
    if (!Platform.isAndroid && !Platform.isIOS) {
      return '当前平台不支持摄像头表情识别,请在 Android 或 iOS 设备上使用。';
    }
    return '';
  }

  /// 计算 SHA-256(用于模型完整性校验,与 cnn-training 分支提供的一致)。
  ///
  /// 使用 `crypto` 包的纯 Dart 实现,跨 Android/iOS/Web 一致。
  String _computeSha256(Uint8List bytes) {
    return crypto.sha256.convert(bytes).toString();
  }
}
