# CampusMateAI 行为识别 V3.2.1 基线测试报告

日期：2026-08-22
基线对象：`campusmate_visible_study_v32.onnx`
测试范围：Android 端预处理、模型契约、Debug 可观测性和预处理 A/B

## 1. 结论摘要

静态代码、模型文件和 JVM 单元测试已完成核验；当前代码具备在 Android 真机上采集 V3.2.1 基线数据的条件。

真机基线尚未完成：当前环境 `adb devices` 未发现设备，因此没有虚构推理延迟、温度、内存、耗电或人工准确率结果。

## 2. 当前模型契约

模型文件：

```text
android/app/src/main/assets/models/behavior/campusmate_visible_study_v32.onnx
```

文件信息：

| 项目 | 结果 |
|---|---|
| 文件大小 | 44,700,648 bytes |
| SHA-256 | `d037cd6294c8c5ba91f10415d22afda49d50b7675ba395a140b66a8f023ffc0c` |
| ONNX opset | 18 |
| 输入名称 | `input` |
| 输入类型 | float32 |
| 输入形状 | `[1, 3, 224, 224]` |
| 输出名称 | `logits` |
| 输出类型 | float32 |
| 输出形状 | `[1, 2]` |

Android 代码中的类别映射与模型契约一致：

```text
logits[0] → IDLE
logits[1] → VISIBLE_STUDY
```

模型由 `OnnxBehaviorRecognitionEngine` 默认选择 `V32_MODEL`，加载路径与上述文件一致。

## 3. 训练侧与 Android 侧预处理核对

| 项目 | 训练/导出资料 | Android V3.2.1 | 结论 |
|---|---|---|---|
| resize | 224×224 | `Bitmap.createScaledBitmap(..., 224, 224)` | 一致 |
| crop | 行为模型训练源码未纳入仓库；历史行为文档未规定额外 crop | 不做 crop，直接缩放整帧 | Android 侧无 crop；训练侧需保留原始训练记录作最终证明 |
| 颜色 | RGB | 从 Bitmap 提取 red/green/blue | 一致 |
| 通道顺序 | RGB | 写入 R、G、B 平面 | 一致 |
| 归一化 | `/255`，ImageNet mean/std | mean `[0.485, 0.456, 0.406]`，std `[0.229, 0.224, 0.225]` | 一致 |
| tensor layout | NCHW | `[R plane, G plane, B plane]` | 一致 |
| 输入 dtype | float32 | float32 `FloatBuffer` / ONNX tensor | 一致 |

注意：`ml/expression_recognition` 下的 `96×96 grayscale replicated` 是表情模型配置，不是本行为模型的训练配置，不能用于解释 V3.2 行为模型。

## 4. A/B 预处理测试

定义：

```text
A（当前生产路径）:
CameraFrame → BehaviorModelConfig() → 224×224 → ONNX preprocess

B（direct 224×224）:
CameraFrame → BehaviorModelConfig.DIRECT_224 → 224×224 → ONNX preprocess
```

当前生产默认已与 B 相同。自动化测试确认：

- A 与 B 的输出尺寸均为 `224×224`；
- 对同一合成输入帧，A/B 缩放后的像素逐点一致；
- 旧的 `192×192 → 224×224` 路径保留为 `BehaviorModelConfig.LEGACY_192`；
- 合成高频图测试确认旧路径与 direct 224 的输入 tensor 确实不同。

因此，A/B 的下一步不再是代码路径差异，而是真机真实前摄帧上的模型输出、人工标签和延迟对比。

## 5. Debug 可观测性

Debug Logcat 每 10 次推理输出：

```text
inference count
dropped/busy count
average inference interval
first prediction time
frame timestamp
top prediction label
top prediction confidence
preprocessing latency
inference latency
```

Debug CSV `behavior_debug_predictions.csv` 额外记录：

```text
timestamp
raw IDLE / VISIBLE_STUDY probability
raw top-1 class / confidence
preprocessing_latency_ms
inference_latency_ms
stabilized behavior
UI behavior state
```

CSV 中的 `raw_*` 来自 ONNX 引擎原始输出；`stabilized_behavior` 和 `ui_behavior_state` 仍是产品层稳定化结果，二者不能混作模型准确率。

## 6. 真机执行步骤

1. 安装 Debug APK，确认应用使用 `campusmate_visible_study_v32.onnx`。
2. 在专注页开启行为识别 Debug 采集。
3. 分别录制平衡的 `IDLE` 和 `VISIBLE_STUDY` 片段，并保存人工标签。
4. 导出 `behavior_debug_predictions.csv` 和 Logcat `BehaviorPerf` 日志。
5. 记录设备型号、Android 版本、光照、摄像头距离和前摄角度。
6. 计算 preprocessing/inference P50、P95、Top-1 翻转数、平均置信度和人工标签一致率。
7. 对同一批帧比较 A（生产配置）与 `LEGACY_192` 对照路径；不修改模型文件。

## 7. 当前限制与验收状态

已完成：

- V3.2 模型文件、输入输出契约和标签映射核验；
- Android resize、RGB、normalization、NCHW 核验；
- A/B 预处理自动化测试；
- Debug latency、timestamp、confidence 输出；
- Android 单元测试和 Debug 构建验证。

待完成：

- 真机推理 P50/P95；
- 真机内存、温度、耗电和丢帧率；
- 人工标签准确率、混淆矩阵和置信度校准；
- 训练侧原始行为数据处理脚本对 crop/resize 的最终签字确认。
