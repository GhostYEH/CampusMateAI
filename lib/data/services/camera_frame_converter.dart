import 'dart:typed_data';

import 'package:image/image.dart' as img;

/// 摄像头帧转换工具 — 将 `camera` 插件的 CameraImage 转换为 img.Image。
///
/// **隐私保证**:所有转换仅在内存中进行,不写入文件系统,不上传。
///
/// 平台差异:
/// - Android: YUV420 格式(3 个 plane: Y 全分辨率, U/V 半分辨率)
/// - iOS: BGRA8888 格式(1 个 plane, 4 字节/像素)
/// - Web: RGBA 格式(camera 插件 Web 实现)
///
/// 性能优化:
/// - 灰度模型(channels=1):直接使用 Y 平面,跳过 YUV→RGB 转换
/// - RGB 模型(channels=3):完整 YUV→RGB 转换
class CameraFrameConverter {
  CameraFrameConverter();

  /// 从 YUV420 平面构造灰度 img.Image(仅取 Y 平面,最快)。
  ///
  /// [yBytes]: Y 平面字节
  /// [width]: 图像宽度
  /// [height]: 图像高度
  /// [bytesPerRow]: Y 平面每行字节数(可能 > width,有 padding)
  img.Image yPlaneToGrayscale(
    Uint8List yBytes,
    int width,
    int height,
    int bytesPerRow,
  ) {
    final image = img.Image(width: width, height: height, numChannels: 3);
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        final idx = y * bytesPerRow + x;
        final gray = yBytes[idx];
        image.setPixelRgb(x, y, gray, gray, gray);
      }
    }
    return image;
  }

  /// 从 BGRA 字节构造 RGB img.Image(iOS 格式)。
  ///
  /// [bgraBytes]: BGRA 字节流(每像素 4 字节)
  /// [width]: 图像宽度
  /// [height]: 图像高度
  /// [bytesPerRow]: 每行字节数
  img.Image bgraToRgb(
    Uint8List bgraBytes,
    int width,
    int height,
    int bytesPerRow,
  ) {
    final image = img.Image(width: width, height: height, numChannels: 3);
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        final idx = y * bytesPerRow + x * 4;
        final b = bgraBytes[idx];
        final g = bgraBytes[idx + 1];
        final r = bgraBytes[idx + 2];
        image.setPixelRgb(x, y, r, g, b);
      }
    }
    return image;
  }

  /// 从 RGBA 字节构造 RGB img.Image(Web 格式)。
  img.Image rgbaToRgb(
    Uint8List rgbaBytes,
    int width,
    int height,
    int bytesPerRow,
  ) {
    final image = img.Image(width: width, height: height, numChannels: 3);
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        final idx = y * bytesPerRow + x * 4;
        final r = rgbaBytes[idx];
        final g = rgbaBytes[idx + 1];
        final b = rgbaBytes[idx + 2];
        image.setPixelRgb(x, y, r, g, b);
      }
    }
    return image;
  }
}
