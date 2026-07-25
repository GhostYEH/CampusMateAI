import 'dart:async';

import '../models/expression.dart';
import 'service_interfaces.dart';

/// LiteRT 表情识别服务 — 真实 CNN 模型接入预留。
///
/// **当前阶段为占位骨架**,所有方法抛出 [UnimplementedError]。
///
/// 接入计划(后续阶段):
/// 1. PyTorch / torchvision 训练 ResNet18 / MobileNetV3-Small on FER2013
/// 2. 导出为 LiteRT(TFLite)格式
/// 3. 通过 Platform Channel 接入 Kotlin CameraX 帧数据
/// 4. 在 Native 层执行推理,通过 EventChannel 回传 [ExpressionResult]
///
/// 数据结构遵循 AGENTS.md §6 强制接口:
/// - 多帧概率平滑
/// - 置信度阈值
/// - 状态持续时间判断
/// - 提醒冷却时间
///
/// **科学边界**(AGENTS.md §3):
/// 仅识别可观察到的面部表情,不进行心理诊断。
/// 低置信度时返回 `ExpressionLabel.unknown` 并由 UI 提示
/// "暂时无法稳定判断当前表情",且不触发情绪安慰。
class LiteRtExpressionRecognitionService
    implements ExpressionRecognitionService {
  @override
  Stream<ExpressionResult> get results => throw UnimplementedError(
        '真实 LiteRT 模型尚未接入,请切换到 Mock 模式',
      );

  @override
  bool get isRunning => false;

  @override
  Future<void> initialize() {
    throw UnimplementedError(
      '真实 LiteRT 模型尚未接入,请切换到 Mock 模式',
    );
  }

  @override
  Future<void> start() {
    throw UnimplementedError(
      '真实 LiteRT 模型尚未接入,请切换到 Mock 模式',
    );
  }

  @override
  Future<void> pause() {
    throw UnimplementedError(
      '真实 LiteRT 模型尚未接入,请切换到 Mock 模式',
    );
  }

  @override
  Future<void> stop() {
    throw UnimplementedError(
      '真实 LiteRT 模型尚未接入,请切换到 Mock 模式',
    );
  }

  @override
  Future<void> dispose() {
    throw UnimplementedError(
      '真实 LiteRT 模型尚未接入,请切换到 Mock 模式',
    );
  }
}
