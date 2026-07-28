import 'dart:typed_data';

import 'package:image/image.dart' as img;

import 'expression_model_config.dart';

/// CNN 图像预处理流水线 — 纯逻辑,无副作用,便于单元测试。
///
/// 流程(严格遵循 preprocess.json):
/// 1. **人脸裁剪**: 将 [faceBox] 区域裁剪出来(可选,由 config.faceCropEnabled 决定)
/// 2. **尺寸调整**: 缩放到 [ExpressionModelConfig.inputWidth] x [inputHeight]
/// 3. **通道转换**: RGB → 灰度(config.channels==1)或保持 RGB(config.channels==3)
/// 4. **归一化**: 按 [ExpressionNormalization] 应用 /255.0 或标准化
/// 5. **张量重塑**: 输出 NHWC 格式 [1, H, W, C] 的 Float32List
///
/// **隐私保证**(AGENTS.md §3):
/// - 输入图像仅在内存中处理,不写入文件系统
/// - 不上传任何图像数据
/// - 处理完成后输入引用立即丢弃,等待 GC 回收
class ExpressionPreprocessor {
  ExpressionPreprocessor(this.config);

  final ExpressionModelConfig config;

  /// 对一张 RGB 图像执行完整预处理,返回 TFLite 输入张量。
  ///
  /// [input]: 已解码的 RGB 图像(image 包格式)
  /// [faceBox]: 人脸边界框(可选)。若 config.faceCropEnabled=true 且
  ///   faceBox 不为 null,则裁剪到该区域(含 padding)。
  ///   若 faceBox 为 null 且 faceCropEnabled=true,返回 null 表示"无人脸"。
  ///
  /// 返回 NHWC 格式的 Float32List,长度 = H * W * C。
  /// 若无人脸且 faceCropEnabled=true,返回 null。
  Float32List? process(img.Image input, FaceBox? faceBox) {
    img.Image working = input;

    // 1. 人脸裁剪
    if (config.faceCropEnabled) {
      if (faceBox == null) return null; // 无人脸,无法处理
      working = _cropWithPadding(working, faceBox);
    }

    // 2. 尺寸调整
    working = _resize(working, config.inputWidth, config.inputHeight);

    // 3 + 4 + 5. 通道转换 + 归一化 + 张量重塑
    return _toTensor(working);
  }

  /// 裁剪人脸区域(含 padding 外扩)。
  ///
  /// padding_ratio=0.2 时,边界框向外扩 20% 以包含完整下巴/额头。
  img.Image _cropWithPadding(img.Image src, FaceBox box) {
    final w = src.width;
    final h = src.height;
    final padW = (box.width * config.faceCropPaddingRatio).toInt();
    final padH = (box.height * config.faceCropPaddingRatio).toInt();

    final left = (box.left - padW).clamp(0, w - 1).toInt();
    final top = (box.top - padH).clamp(0, h - 1).toInt();
    final right = (box.right + padW).clamp(left + 1, w).toInt();
    final bottom = (box.bottom + padH).clamp(top + 1, h).toInt();

    final cropW = right - left;
    final cropH = bottom - top;
    if (cropW <= 0 || cropH <= 0) {
      // 边界框异常,返回原图(不应发生)
      return src;
    }
    return img.copyCrop(
      src,
      x: left,
      y: top,
      width: cropW,
      height: cropH,
    );
  }

  /// 尺寸调整。
  img.Image _resize(img.Image src, int targetW, int targetH) {
    if (src.width == targetW && src.height == targetH) return src;
    switch (config.resizeMethod) {
      case 'nearest':
        return img.copyResize(
          src,
          width: targetW,
          height: targetH,
          interpolation: img.Interpolation.nearest,
        );
      case 'area':
        // image 包没有 area 方法,用 average 近似
        return img.copyResize(
          src,
          width: targetW,
          height: targetH,
          interpolation: img.Interpolation.average,
        );
      case 'bilinear':
      default:
        return img.copyResize(
          src,
          width: targetW,
          height: targetH,
          interpolation: img.Interpolation.linear,
        );
    }
  }

  /// 将 RGB 图像转换为 TFLite 输入张量(NHWC 格式)。
  ///
  /// 输出长度 = H * W * C,数值为 float32。
  /// - channels=1: 灰度,按 ITU-R BT.601: Y = 0.299R + 0.587G + 0.114B
  /// - channels=3: RGB 或 BGR(由 config.colorMode 决定)
  Float32List _toTensor(img.Image src) {
    final w = config.inputWidth;
    final h = config.inputHeight;
    final c = config.channels;
    final tensor = Float32List(w * h * c);

    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final pixel = src.getPixel(x, y);
        final r = pixel.r.toInt();
        final g = pixel.g.toInt();
        final b = pixel.b.toInt();

        if (c == 1) {
          // 灰度
          final gray = (0.299 * r + 0.587 * g + 0.114 * b).round().clamp(0, 255);
          tensor[(y * w + x)] = config.normalization.apply(gray, 0);
        } else if (c == 3) {
          // RGB 或 BGR
          final baseIdx = (y * w + x) * 3;
          if (config.colorMode == 'bgr') {
            tensor[baseIdx] = config.normalization.apply(b, 0);
            tensor[baseIdx + 1] = config.normalization.apply(g, 1);
            tensor[baseIdx + 2] = config.normalization.apply(r, 2);
          } else {
            // rgb
            tensor[baseIdx] = config.normalization.apply(r, 0);
            tensor[baseIdx + 1] = config.normalization.apply(g, 1);
            tensor[baseIdx + 2] = config.normalization.apply(b, 2);
          }
        }
      }
    }
    return tensor;
  }
}

/// 人脸边界框(归一化或像素坐标,由调用方保证一致)。
class FaceBox {
  const FaceBox({
    required this.left,
    required this.top,
    required this.right,
    required this.bottom,
  });

  final double left;
  final double top;
  final double right;
  final double bottom;

  double get width => right - left;
  double get height => bottom - top;

  factory FaceBox.fromLtrb({
    required double left,
    required double top,
    required double right,
    required double bottom,
  }) {
    return FaceBox(
      left: left,
      top: top,
      right: right,
      bottom: bottom,
    );
  }
}
