# CampusMateAI 表情识别端侧优化报告

## 范围与约束

本阶段只优化 Android 端链路，保留当前 ResNet18 表情模型、七个类别和现有 EMA；没有改训练数据、类别，也没有引入 GRU/LSTM。

## 1. 当前链路与问题定位

```text
CameraX ImageAnalysis (KEEP_ONLY_LATEST, 640x480, 200 ms 节流)
  -> ImageProxyBitmapConverter
     YUV_420_888 -> NV21 -> JPEG -> Bitmap -> rotation/mirror
  -> CameraFrame（共享给表情/行为/人员分析器）
  -> ML Kit FAST 人脸检测、tracking、eyes/smile classification
  -> 最大脸 + 16%/20% padding crop
  -> 96x96 bilinear resize
  -> 灰度化并复制为 RGB 三通道 + ImageNet mean/std
  -> LiteRT ResNet18 dynamic-int8 权重、float32 I/O、4 threads
  -> softmax -> EMA(alpha=0.35)
  -> 同类至少 4 帧且持续 700 ms
  -> ExpressionResult
```

基线审查发现：

- 最大的端侧 CPU/GC 风险在全帧 JPEG 往返，而不是 96x96 ResNet18 本身。
- `preprocessing.json` 已有 `class_thresholds`，旧端侧只使用全局 `confidence_threshold=0.7`。
- 原链路没有人脸尺寸、姿态和模糊质量门。
- EMA 本身计算很轻，但会带来约 700 ms 的稳定等待。

## 2. 本次修改

### P0：匿名端侧性能统计

新增 `ExpressionPerformanceStats`，只在内存中保存时延样本和计数，不保存图片、Bitmap、概率向量、用户标识或人脸数据。

统计字段：

- `face_detection_ms`
- `preprocess_ms`
- `inference_ms`
- `postprocess_ms`（softmax + EMA/结果整理）
- `total_latency_ms`
- `fps`
- `dropped_frames`（CameraX KEEP_ONLY_LATEST 丢帧，以及表情服务节流或 busy 时丢弃的帧）
- `NO_FACE` 比例
- `UNKNOWN` 比例

`RealExpressionRecognitionService.performanceSnapshot()` 返回平均值、P50、P95。统计会在首次 `start()` 时开始，暂停/恢复不会清空；释放服务后对象消失，不上传也不落盘。

10 分钟真机运行后可读取：

```kotlin
val snapshot = service.performanceSnapshot()
```

其中比例分母是已完成分析帧；`NO_FACE` 不重复计入 `UNKNOWN`。

### P1：逐类别阈值

`ExpressionPreprocessing` 现在解析可选的 `class_thresholds`。缺少该字段的旧模型仍回退到全局 `confidence_threshold`。

EMA 后取 top-1 类别，再使用该类别阈值：

```text
threshold = class_thresholds[topLabel] ?: confidence_threshold
```

当前资产中的示例阈值包含 `happy=0.30`、`fear=0.93`。因此容易可靠识别的类别可以获得更高有效覆盖率，而容易误报的类别仍保持保守拒识。

### P2：图像转换链路

生产路径已从：

```text
YUV -> NV21 -> JPEG -> Bitmap
```

替换为：

```text
YUV_420_888 planes -> 直接 RGB/ARGB buffer -> Bitmap -> crop -> 96x96
```

RGB 数值转换、rotation、镜像和模型输入契约保持不变。新增 `ImageProxyBitmapConverter.benchmark()` 可在真机 instrumentation 中对同一 `ImageProxy` 对比 direct RGB 与 legacy JPEG 路径；两张临时 Bitmap 会立即回收。

`ExpressionModelRunner` 复用输入 DirectByteBuffer、像素数组和输出数组，减少每次推理的 Java 对象分配；ImageNet normalization 和灰度复制 RGB 规则保持不变。

### P3：Face Quality Gate

模型推理前新增质量门：

- 人脸宽度小于 100 px：`UNKNOWN`
- pitch/yaw/roll 任一绝对值大于 25°：`UNKNOWN`
- crop 的低成本边缘能量低于 sharpness 阈值：`UNKNOWN`

质量拒识仍保留 `facePresent=true`，不会伪造 `NO_FACE`，也不会进入 ResNet18 推理。

## 3. 性能变化

本仓库当前没有连接 Android 真机，因此本报告不伪造平均/P50/P95 数字。需要在低/中/高三档真机各连续运行 10 分钟后记录：

| 指标 | 旧链路 | 新链路 | 目标 |
|---|---:|---:|---:|
| face detection p95 | 待测 | 待测 | 对比，不回归 |
| preprocess p95 | 待测 | 待测 | 明显下降 |
| inference p95 | 待测 | 待测 | 不回归 |
| total latency p95 | 待测 | 待测 | 中端机 ≤ 250 ms |
| FPS | 待测 | 待测 | 稳定运行 10 分钟 |
| dropped frames | 待测 | 待测 | 下降或可解释 |
| NO_FACE 比例 | 待测 | 待测 | 不因转换改变 |
| UNKNOWN 比例 | 待测 | 待测 | 结合有效准确率判断 |

`UNKNOWN` 降低不等于准确性提高；必须同时使用人工标注的目标域验证集报告“接受结果准确率 + 覆盖率”。

## 4. 准确性变化

本阶段没有改模型权重，因此离线模型 accuracy/macro-F1 理论上不变。可观察变化来自：

1. 逐类别阈值接入，减少全局 0.7 对不同类别造成的过度拒识/误接受。
2. 小脸、严重侧脸、模糊帧提前拒识，减少低质量误报。
3. `NO_FACE` 仍由 ML Kit 产生，质量门不会把检测到的人脸改写成 `NO_FACE`。

建议真机验收至少报告：总体 accuracy、macro-F1、每类 precision/recall、接受覆盖率、接受样本 accuracy、UNKNOWN 率和 NO_FACE 率。

## 5. 测试体系

新增/完善：

- `ExpressionPerformanceStatsTest`：平均值、P50、P95、FPS、丢帧和比例。
- `ExpressionSignalProcessorTest`：逐类别阈值、全局阈值回退、UNKNOWN、NO_FACE、EMA 稳定与冷却。
- `ImageProxyBitmapConverterTest`：直接 YUV→RGB 数值契约。
- `FaceQualityGateTest`：小脸、姿态、模糊和可用样本。
- `expression_recognition_android_test.ExpressionRecognitionAndroidTest`：上述回归测试套件入口。

## 6. 后续模型阶段建议

端侧基准和目标域验收集稳定后，再考虑模型升级。下一阶段仍应先用当前 ResNet18 作教师，比较真实 RGB/灰度、ML Kit crop 抖动增强、蒸馏轻量模型和 full-int8；模型替换必须同时满足真实设备 p95、接受覆盖率和每类 macro-F1 门槛。
