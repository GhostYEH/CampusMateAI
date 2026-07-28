// Web 平台 stub —— 在不支持 dart:ffi / TFLite / ML Kit 的 Web 环境下使用。
//
// 通过 conditional import 在 Web 构建时替换真实的 LiteRtExpressionRecognitionService:
//   import 'lite_rt_expression_recognition_service_web.dart'
//       if (dart.library.io) 'lite_rt_expression_recognition_service.dart';
//
// 行为(对齐 AGENTS.md §2.4 与 lite_rt_expression_recognition_service.dart 的平台策略):
// - 不静默回退 Mock,通过 status 流明确发出平台降级说明
// - results 流不产生任何表情结果(UI 应根据 status 显示降级提示)
// - 所有控制方法(start/pause/stop)为 no-op,不抛异常
//
// 此文件仅在 Web 构建时被引用;原生平台(Android/iOS/桌面)使用真实实现。
import 'dart:async';

import '../models/expression.dart';
import 'expression_service_status.dart';
import 'service_interfaces.dart';

/// Web 平台的 LiteRt 表情识别服务 stub。
///
/// 不导入 tflite_flutter / google_mlkit_face_detection(二者依赖 dart:ffi,
/// 在 Web/Wasm 下不可用)。此 stub 仅暴露同名类与 [ExpressionRecognitionService]
/// 接口,初始化时通过 status 流发出平台降级说明。
class LiteRtExpressionRecognitionService
    implements ExpressionRecognitionService {
  LiteRtExpressionRecognitionService({
    this.modelAssetPath = 'assets/models/expression_model.tflite',
    this.configBasePath = 'assets/models',
  });

  final String modelAssetPath;
  final String configBasePath;

  final _resultController = StreamController<ExpressionResult>.broadcast();
  final _statusController =
      StreamController<ExpressionServiceStatus>.broadcast();

  bool _initialized = false;
  bool _running = false;
  bool _disposed = false;

  @override
  Stream<ExpressionResult> get results => _resultController.stream;

  @override
  Stream<ExpressionServiceStatus> get status => _statusController.stream;

  @override
  bool get isRunning => _running;

  @override
  Future<void> initialize() async {
    if (_initialized || _disposed) return;
    _initialized = true;
    // 明确发出平台降级说明,不静默回退 Mock(对齐 AGENTS.md §2.4)。
    _statusController.add(
      const ExpressionServiceStatus(
        modelState: ExpressionModelState.notInstalled,
        cameraState: CameraState.idle,
        modelVersion: '',
        platformDegradation:
            'Web 平台不支持 TFLite 与 ML Kit,表情识别功能不可用。请在 Android/iOS 设备上使用。',
      ),
    );
  }

  @override
  Future<void> start() async {
    _running = true;
  }

  @override
  Future<void> pause() async {
    _running = false;
  }

  @override
  Future<void> stop() async {
    _running = false;
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    _running = false;
    await _resultController.close();
    await _statusController.close();
  }
}
