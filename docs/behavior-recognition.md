# CampusMateAI Android 专注模式动作识别

本文档记录 CampusMateAI Android 专注模式下的本地动作识别（行为识别）的完整研究、实验、模型与部署情况，适合作为计算机设计大赛项目仓库的专项说明。

> 说明：本文严格区分「已部署」与「研究阶段」。Android v1 只部署了 RGB ResNet18 单一模型，Pose、融合等均为研究阶段产物，未部署到移动端。

## 1. 研究背景与目标

CampusMateAI 在 Android 专注模式下，使用前置摄像头辅助识别学习行为，用于专注状态辅助（学习陪伴）。摄像头画面仅在设备端处理，不上传、不保存。

当前 Android v1 已部署：

- **READING**：阅读
- **WRITING**：书写

后续研究候选类别（**尚未实现**）：

- `phone_use`
- `away`
- `resting`

## 2. 整体技术路线

研究路线：

```
RGB 图像
→ ResNet18
→ READ / WRITE 二分类
→ ONNX 导出
→ ONNX Runtime Android
→ CampusMateAI 专注模式
```

研究阶段还做过（**当前未部署到 Android v1**）：

- Pose MLP
- RGB / Pose 对比
- RGB + Pose 融合探索

## 3. 数据与任务定义

处理后的 READ / WRITE 数据总样本数：

**32,343**

二分类标签：

- `0` = READ / READING
- `1` = WRITE / WRITING

RGB 输入预处理：

- resize：224 × 224
- RGB
- 除以 255
- ImageNet mean/std normalization
- NCHW
- float input

## 4. RGB ResNet18 主实验

主模型：

**ResNet18 RGB**

验证集结果：

- Accuracy = **79.78%**
- Macro-F1 = **77.23%**

当前 Android v1 最终选择 RGB ResNet18 作为部署模型。

> 注意：Android 现场推理出现的 90%、99% 等预测 confidence 是单帧 softmax 置信度，不是模型准确率（Accuracy）。二者含义不同，不可混用。

## 5. Pose 对比实验

> 本节属于研究阶段，当前 Android v1 未部署 Pose 模型。

MediaPipe Pose 在原始数据上的有效可用率：

**43.17%**

RGB 与 Pose 都可用的 common subset：

**13,962**

Pose MLP 在 common subset 上的结果：

- Accuracy = **69.39%**
- Macro-F1 = **65.1354%**

RGB ResNet18 在 common subset 上的结果：

- Accuracy = **79.3823%**
- Macro-F1 = **74.9270%**

结论：Pose 单模型效果低于 RGB，但后续错误分析发现二者具有一定互补性。

## 6. RGB / Pose 错误互补性

RGB 错误样本：

**741**

其中 Pose 能纠正：

**365**

约：

**49.26%**

Oracle one-correct：

约 **89.54%**

> 说明：Oracle one-correct 只是用来分析两个模型互补性的理论上界，它不是实际部署模型，不能把 89.54% 写成最终模型准确率。

## 7. 融合实验探索

### 7.1 Late Fusion

RGB / Pose 权重：

`0.5 / 0.5`

Macro-F1：

**75.60%**

### 7.2 Rule B

当 RGB 与 Pose 一致：

→ 使用 RGB

当 RGB 与 Pose 不一致：

- RGB 预测 READ 且 confidence < 0.90 → 使用 Pose
- RGB 预测 WRITE 且 confidence < 0.80 → 使用 Pose
- 其他情况 → 使用 RGB

结果：

- Accuracy = **80.47%**
- Macro-F1 = **76.29%**

> 说明：这些阈值是在同一验证集上探索得到的，没有独立测试集验证，因此不能作为最终泛化性能结论。当前 Android v1 不部署 Rule B。

## 8. 为什么最终先部署 RGB Only

- RGB 主模型整体性能更稳定
- RGB 不依赖 Pose 成功提取
- Pose 原始数据有效率只有 43.17%
- Rule B 虽有提升，但阈值在同一验证集探索
- Android 第一阶段优先保证部署稳定性
- 降低移动端推理链路复杂度

当前阶段：

- **阶段 1**：RGB ResNet18 → 已部署
- **阶段 2**：Pose MLP → 研究中 / 未部署
- **阶段 3**：RGB + Pose fusion → 研究中 / 未部署

## 9. ONNX 导出

模型路径：

```
android/app/src/main/assets/models/behavior/rgb_resnet18.onnx
```

模型大小：

约 **42.70 MB**

ONNX 信息：

- opset = 18
- input name = `input`
- input shape = `[1, 3, 224, 224]`
- output name = `logits`
- output shape = `[1, 2]`

类别：

- `0` = READ
- `1` = WRITE

PyTorch / ONNX Runtime 一致性验证：

最大 logit difference ≈ **4.77e-6**

> 说明：该指标用于证明模型导出前后数值基本一致，不是分类准确率。

## 10. Android 部署架构

以下描述以当前 master / Android Behavior Recognition v1 中的真实代码为准。

### OnnxBehaviorRecognitionEngine.kt

职责：

- 加载 ONNX 模型（从 assets 复制到 app 私有存储 `noBackupFilesDir`，避免每次初始化重复分配约 43 MB）
- resize 到 224 × 224
- RGB 处理（从像素中提取 R/G/B 通道）
- 除以 255
- ImageNet mean/std normalization
- NCHW 布局写入 FloatBuffer
- ONNX Runtime 推理
- softmax（`BehaviorModelMath.softmax2`）
- READ / WRITE 映射

V1 为单帧推理：`BehaviorAnalyzer` 可提供时间窗口，但该引擎只取最新一帧（`frames.lastOrNull()`）。

### BehaviorModelMath.kt

职责：

- 稳定 softmax（减去最大值避免数值溢出）
- 模型输出后处理（两 logit → 概率分布）

### BehaviorAnalyzer.kt

职责（以代码实际实现为准）：

- 实现 `FrameAnalyzer` 接口，接收 `CameraFrame`
- V1 在第一张有效画面上立即推理；不走 `BehaviorFrameBuffer` 的未来时序模型路径
- 使用单线程 `ExecutorService` 控制并发推理（`AtomicBoolean` 防止堆积；繁忙时直接保留 CameraX 的最新帧）
- 每次推理仅持有一张原始画面的安全 Bitmap snapshot，推理结束后回收
- 原始 snapshot 直接在引擎中 resize 到 224 × 224，不经过 192 × 192 中间缩放
- 对 READ / WRITE 概率做 EMA、confidence / margin gate 和滞后切换；不可靠时输出 `UNCERTAIN`
- 推理完成后回收 snapshot Bitmap
- 初始化 `BehaviorRecognitionEngine`（`ensureInitialized`）
- 通过 `predictions` StateFlow 暴露推理结果

### BehaviorRecognitionEngine.kt

职责：

- 定义引擎接口：`isAvailable` / `initialize` / `analyzeTemporalWindow` / `close`
- 提供 `NoOpBehaviorRecognitionEngine`（`isAvailable = false`，用于模型不可用场景）

### ExpressionSessionManager.kt

职责：

- 持有 `BehaviorAnalyzer(OnnxBehaviorRecognitionEngine(application))`
- 在专注会话满足条件时，将 `BehaviorAnalyzer` 注册进 `FocusCameraPipeline`，与表情识别 service 共享同一 CameraX pipeline（不额外启动第二个摄像头）
- 通过 `collectLatest` 收集 `behaviorAnalyzer.predictions`，更新 `behaviorPrediction` StateFlow
- 将预测送入 `BehaviorSignalProcessor` 生成稳定行为事件
- 将事件送入 `FocusSupervisor` 得到 `FocusState`，更新 `focusState` StateFlow
- 专注结束时可读取 `FocusSupervisor.stats`（当前尚未并入 `FocusSessionSummary`）

### FocusScreen.kt

`FocusScreen` 的「学习状态辅助」卡片会显示稳定后的动作结果：阅读、书写或暂不确定；初始化、模型不可用和推理异常也会分别显示。界面最多约每 500ms 更新一次，展示的百分比为 EMA 平滑后的概率，而不是高速变化的原始单帧 softmax。

## 11. 隐私与端侧推理

- 原始摄像头画面仅在 Android 设备内存中处理
- 不上传服务器
- 不保存实时图像
- 不把原始画面写入日志
- ONNX Runtime 推理在设备端完成

## 12. 当前限制

1. 当前 Android v1 只有 READ / WRITE 两类。
2. 训练数据场景与真实手机前置摄像头存在 domain gap。
3. 训练阶段的人物区域和实时摄像头输入分布可能不同。
4. 高 softmax confidence 不代表真实场景一定判断正确。
5. Pose 尚未部署。
6. Rule B 尚未部署。
7. Rule B 阈值没有独立测试集验证。
8. phone_use / away / resting 尚未实现。
9. 仍需真实手机端数据进行进一步评估。

## 13. 后续工作

以下为计划 / 后续研究 / 候选方向，**尚未完成**：

- 收集真实手机学习场景数据
- 人体 / 上半身 ROI
- `phone_use`
- `away`
- `resting`
- Pose MLP 部署
- RGB + Pose fusion
- 独立测试集验证
- fine-tuning
- domain adaptation
- 时序行为识别
- 多帧稳定性处理

## 14. 当前版本总结

**Android Behavior Recognition v1**

已实现：

```
RGB ResNet18
→ ONNX
→ ONNX Runtime Android
→ 单帧推理
→ READ / WRITE
→ runtime smoothing / UNCERTAIN
```

- ResNet18，input [1, 3, 224, 224]，output [1, 2]
- 类别：0 = READING，1 = WRITING
- 预处理：RGB → resize 224×224 → /255 → ImageNet mean/std → NCHW → float32
- 模型从 assets 复制到 noBackupFilesDir 后由 ONNX Runtime 打开
- BehaviorAnalyzer 持有 Bitmap snapshot，推理完成后 recycle
- FocusCameraPipeline 支持 lifecycle/preview 分离，ImageAnalysis 无需 PreviewView
- ExpressionSessionManager 在 FocusMode.FOCUS 时运行分析，休息阶段暂停
- FocusScreen 显示真实行为识别结果（动作识别：阅读 83% / 书写 91%）

研究阶段（未实现）：

```
phone_use
away
resting
Pose fusion
时序模型（16 帧）
CampusFocusNet V2
MobileNetV4
TCN / LTG / Mamba
13 类行为
Engagement Head
Alertness Head
连续 0–100 Focus Score
```

V1 作为未来 CampusFocusNet 的 baseline。
