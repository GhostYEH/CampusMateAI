# CampusMateAI Android 行为识别：V3.2 部署基线与历史研究

本文档记录 CampusMateAI Android 专注模式下的本地行为识别研究、实验、模型与部署情况。文首说明当前 V3.2 部署基线，后续章节保留 V1/V2 历史研究记录，便于追溯实验结论。

## 当前部署状态：学习状态辅助 V3.2

当前 Android 默认模型为 `android/app/src/main/assets/models/behavior/campusmate_visible_study_v32.onnx`。它是 RGB ResNet18 的 ONNX 模型，输入为 `1×3×224×224` 的 RGB 图像（`/255` 后使用 ImageNet mean/std 标准化），输出类别顺序固定为：

1. `idle` → `IDLE`：暂未观察到明确可见学习行为。
2. `visible_study` → `VISIBLE_STUDY`：观察到阅读、书写或明显操作学习材料等明确学习动作。

这不是“专注 vs 不专注”的判断：`IDLE` 只表示当前视觉帧没有足够明确的可观察学习动作。旧模型 `campusmate_visible_study_v31.onnx` 和 `rgb_resnet18_v2.onnx` 保留在 assets 中，仅用于回退或历史对照，不是当前默认模型。

Android 的当前数据流为：

```
同一条 FocusCameraPipeline / CameraFrame
→ BehaviorAnalyzer
→ OnnxBehaviorRecognitionEngine
→ BehaviorSignalProcessor（启动观察期、时间窗口、置信度与多数判定）
→ LearningContinuityStateMachine
→ FocusScreen 学习状态辅助 UI
```

V3.3 稳定化在 `BehaviorAnalyzer` 输出与产品层规则之间增加 EMA 概率平滑（默认 `alpha=0.35`）。第一次有效预测不等待预热，后续瞬时反向尖峰会先被压低；当专注会话暂停、重置、释放、模型版本改变或推理返回空概率时，平滑历史会清空。EMA 只改变进入产品层的概率，不改变 V3.2 的 `IDLE` / `VISIBLE_STUDY` 标签定义。

行为识别和表情识别共享这同一条 CameraX pipeline，不会启动第二个摄像头。连续性状态将短暂的 `IDLE`、`UNKNOWN`、遮挡或姿势调整吸收在学习上下文中：学习后 0～8 秒的短暂 `IDLE` 保持 `STUDYING`，8～20 秒进入 `THINKING_OR_ADJUSTING`，超过 20 秒才进入 `PAUSED`。因此，最近节奏、累计学习时长和最长连续学习均基于产品连续性状态，而不是单次模型跳变。

当前已知限制：侧面书写且手臂严重遮挡时可能不稳定；“坐在电脑前学习”这类单帧视觉语义模糊的场景不能可靠推断；多用户、多环境泛化尚未验证。表情识别是独立能力，仍需继续优化。

### V3.2.1 基线收口状态

生产默认的 `BehaviorModelConfig()` 已直接将相机帧缩放至 `224×224`，与训练预处理一致，避免旧的 `192×192 → 224×224` 双重缩放。旧路径保留为 `BehaviorModelConfig.LEGACY_192`，只用于上线前 A/B 对照，不应作为新的生产配置。

当前已完成：

- 生产默认输入尺寸与训练尺寸一致；
- 直连路径和旧双重缩放路径均有单元测试；
- 模型版本、标签顺序和 Android 推理路径已在本文档固定。

仍待真实设备完成：

- 直连路径与旧路径的真实前置摄像头 A/B；
- 人工标签一致率、混淆矩阵与置信度校准对比；
- 目标机上的推理 P50/P95、内存、温度、耗电和帧丢弃率记录。

## 历史 V1/V2 研究记录（非当前部署）

## 1. 研究背景与目标

CampusMateAI 在 Android 专注模式下，使用前置摄像头辅助识别学习行为，用于专注状态辅助（学习陪伴）。摄像头画面仅在设备端处理，不上传、不保存。

历史 Android v1 曾部署：

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

历史 Android v1 最终选择 RGB ResNet18 作为部署模型。

> 注意：历史 Android v1 现场推理出现的 90%、99% 等预测 confidence 是单帧 softmax 置信度，不是模型准确率（Accuracy）。二者含义不同，不可混用。

## 5. Pose 对比实验

> 本节属于历史研究阶段，Android 当前 V3.1 未部署 Pose 模型。

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

> 说明：这些阈值是在同一验证集上探索得到的，没有独立测试集验证，因此不能作为最终泛化性能结论。当前 V3.1 不部署 Rule B。

## 8. 历史：为什么 V1 最终先部署 RGB Only

- RGB 主模型整体性能更稳定
- RGB 不依赖 Pose 成功提取
- Pose 原始数据有效率只有 43.17%
- Rule B 虽有提升，但阈值在同一验证集探索
- Android 第一阶段优先保证部署稳定性
- 降低移动端推理链路复杂度

历史阶段：

- **阶段 1**：RGB ResNet18 → 曾部署为 V1
- **阶段 2**：Pose MLP → 研究中 / 未部署
- **阶段 3**：RGB + Pose fusion → 研究中 / 未部署

## 9. 历史 V1 ONNX 导出

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

## 10. 历史 V1 Android 部署架构

以下描述以当前分支 `feature/behavior-recognition` 中的真实代码为准。

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
- 通过 `BehaviorFrameBuffer` 做帧缓冲（默认 200ms 采样间隔、最多 16 帧、缩放到 192 × 192）
- 使用单线程 `ExecutorService` 控制并发推理（`AtomicBoolean` 防止重复提交）
- 对时间窗口做 Bitmap snapshot（copy，交给推理任务持有）
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

历史 V1 的 `FocusScreen`「学习状态辅助」卡片只显示固定文案（本机 LiteRT、当前辅助观察、稳定表情、本次专注时长等），**尚未直接渲染 READ / WRITE 的概率文本**。

历史 V1 的行为预测已经接入 `ExpressionSessionManager`（暴露 `behaviorPrediction` StateFlow，并经 `FocusSupervisor` 更新 `focusState`），但当时该 `focusState` / `behaviorPrediction` 尚未被 `FocusScreen` 展示。当前 V3.1 已完成产品化 UI、稳定状态与会话级连续性展示，具体以本文开头的部署状态为准。

## 11. 历史 V1 隐私与端侧推理

- 原始摄像头画面仅在 Android 设备内存中处理
- 不上传服务器
- 不保存实时图像
- 不把原始画面写入日志
- ONNX Runtime 推理在设备端完成

## 12. 历史 V1 限制

1. 历史 Android v1 只有 READ / WRITE 两类。
2. 训练数据场景与真实手机前置摄像头存在 domain gap。
3. 训练阶段的人物区域和实时摄像头输入分布可能不同。
4. 高 softmax confidence 不代表真实场景一定判断正确。
5. Pose 尚未部署。
6. Rule B 尚未部署。
7. Rule B 阈值没有独立测试集验证。
8. phone_use / away / resting 尚未实现。
9. 仍需真实手机端数据进行进一步评估。

## 13. 历史后续工作

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

## 14. 历史版本总结（V1）

**Android Behavior Recognition v1**

当前部署：

```
RGB ResNet18
→ ONNX
→ ONNX Runtime Android
→ READ / WRITE
```

研究阶段：

```
Pose MLP
RGB + Pose fusion / Rule B
```
