# 端侧识别链路交接（行为识别 / 表情识别）

面向 Android 与 HarmonyOS 客户端重写的链路说明，覆盖模型资产、端到端数据流、类别与校准契约、回退语义、隐私边界和已知缺口。整理于 2026-09-30，部署模型的 SHA-256 已对工作区文件实测校验。

统一口径：两项能力都在设备本地推理，画面**不上传服务器、不保存原始图像、不写图像日志**；识别结果只是辅助观察，不代表专注度、心理状态或学习效果。

## 1. 能力与运行时总览

| 能力 | Android | HarmonyOS |
| --- | --- | --- |
| 行为识别 | CameraX + ONNX Runtime（V3.4 单帧、V4 TSM 8 帧，V3.2 回退）；人体检测用打包的 EfficientDet-Lite0 int8 | CameraKit + CoreVisionKit 系统人体检测（无打包模型）+ MindSpore Lite（V3.4、TSM V4） |
| 表情识别 | CameraX + ML Kit 人脸检测 + LiteRT（resnet18） | CameraKit + CoreVisionKit faceDetector + MindSpore Lite |
| 人脸/人体检测 | Android 打包模型或系统能力（见上） | 均为系统 CoreVisionKit 能力，不随应用打包 |

## 2. 模型资产（已核验）

### 2.1 Android（`android/app/src/main/assets/`）

| 文件 | 大小 | 角色 | SHA-256（前 16 位） |
| --- | ---: | --- | --- |
| `expression_model.tflite` | 10.74 MB | 表情主模型（resnet18 / 多数据集 v2 / dynamic_int8 / 7 类） | `9cef0425496d8161` |
| `models/behavior/campusmate_behavior_v34.onnx` | 5.81 MB | 行为主模型（单帧 4 类） | `9abe029d18e1bfc1` |
| `models/behavior/campusmate_tsm_mobilenetv2_v4.onnx` | 8.67 MB | 行为时序模型（8 帧 5 类） | `f5acc4e5614a9fbf` |
| `models/behavior/campusmate_visible_study_v32.onnx` | 42.63 MB | V3.2 二分类回退 | — |
| `models/behavior/campusmate_visible_study_v31.onnx` | 42.63 MB | V3.1 回退（历史） | — |
| `models/behavior/rgb_resnet18.onnx` / `rgb_resnet18_v2.onnx` | 42.70 / 42.71 MB | V1 / V2 历史基线 | — |
| `models/person/efficientdet_lite0_int8.tflite` | 4.35 MB | 人体检测（ROI 与在席证据）；COCO 预训练，Apache-2.0 | `2e04c53bfeac0ac2`（见 MODEL_INFO.md） |

配套契约文件（assets 根目录）：

- `labels.txt`：表情类别顺序 0-6（angry…surprise，含 Android 大写映射）
- `model_metadata.json`：`model_version=expression-resnet18-multiv2-v1`、`selected_variant=dynamic_int8`、全局/类别阈值、测试指标、导出信息
- `preprocessing.json`：96×96、NHWC、灰度复制为 RGB、ImageNet 归一化、人脸裁剪 padding
- `training_config.json`：训练超参（重训对比用）
- `models/person/MODEL_INFO.md`：人体检测模型来源与许可

### 2.2 HarmonyOS（`harmony/entry/src/main/resources/rawfile/models/`）

| 文件 | 大小 | 角色 | SHA-256（前 16 位） |
| --- | ---: | --- | --- |
| `behavior/campusmate_behavior_v34.ms` | 5.83 MB | MindSpore Lite 版行为主模型 | `b1c40c708ae1c2ad`（与 model_card 一致） |
| `behavior/campusmate_tsm_mobilenetv2_v4.ms` | 8.56 MB | MindSpore Lite 版 TSM V4 | `d70b2a5c3c3d8d5a`（与 model_card 一致） |
| `behavior/model_card.json` | — | 运行时契约：输入输出、校准、TSM 与回退语义 | — |
| `expression/campusmate_expression_v2.ms` | 10.78 MB | MindSpore Lite 版表情模型（mslite） | `218eed91b64a96dd`（仓库内无记录，实测值） |
| `expression/preprocessing.json` | — | 表情预处理与稳定性参数（稳定帧 3、EMA 0.4、max_age 5000 ms） | — |

HarmonyOS 未打包人体/人脸检测模型，由系统 CoreVisionKit 提供（`objectDetection`、`faceDetector`）。

### 2.3 训练与导出（`ml/`）

- `ml/behavior_recognition/`：训练、导出、转换代码与测试。**导出产物（exports/runs/manifests）不在工作区**，ONNX 产物当前只存在于两端部署资产中。鸿蒙 `.ms` 的转换脚本在此：`scripts/convert_v34_to_mindir_lite.ps1`、`scripts/convert_tsm_v4_to_mindir_lite.ps1`（配合 `scripts/prepare_v34_for_mindspore.py` 做 HardSwish→HardSigmoid 等价替换，适配 MindSpore Lite 2.1）。
- `ml/expression_recognition/`：`exports/`（clean-v1 dynamic_int8 `c4f6852b…`、float32、`best_checkpoint.pt` 128 MB）、`exports_v2/`（multiv2 的 float16 / float32 / full_int8、`best_checkpoint.pt`、`models_v1_backup/`）；导出脚本 `scripts/export_litert*.ps1`、`reproduce_training.ps1`、`train_all_v2.ps1`。
- 训练数据不随仓库分发，需要 `CAMPUSMATE_BEHAVIOR_DATASET_ROOT` / `CAMPUSMATE_EXPRESSION_DATASET_ROOT` 指向本地只读数据源。

## 3. 行为识别链路

### 3.1 端到端数据流

Android：

```text
CameraX
→ FocusCameraPipeline / CameraFrame
→ BehaviorAnalyzer（约 400 ms 采样、16 帧缓冲、单线程推理调度）
→ HybridBehaviorRecognitionEngine
   ├─ OnnxBehaviorRecognitionEngine（V3.4 单帧；必要时回退 V3.2）
   └─ OnnxTsmBehaviorRecognitionEngine（最近 8 帧、按条件低频运行）
→ BehaviorHybridPolicy（仅融合标签兼容的 V3.4 + V4 输出）
→ BehaviorPredictionTemporalSmoother（EMA 概率平滑）
→ BehaviorSignalProcessor（启动观察、稳定判定）
→ LearningContinuityStateMachine（会话级连续性）
→ BehaviorObservationHistory（最近 5 分钟节奏统计）
→ FocusScreen
```

HarmonyOS：

```text
FocusCameraPipeline（CameraKit 取帧 + CoreVisionKit objectDetection；FrameAnalysisGate 最快 500 ms 一次；ImageArrivalGate 防并发读帧）
→ PersonRoiSelector（COCO person label=13，score ≥ 0.50，取最优框）
→ BehaviorRoiPreprocessor（人物 ROI 外扩 10%，224×224 NCHW，ImageNet 归一化）
→ MindSporeBehaviorProvider（v34.ms；低置信、类别变化、手机交互或周期确认时运行 tsm v4.ms）
→ BehaviorHybridPolicy → BehaviorPredictionTemporalSmoother → BehaviorSignalProcessor
→ LearningContinuityStateMachine + PresenceStateMachine（在席状态）
→ UI（学习状态 / 学习节奏卡片）
```

### 3.2 类别与决策契约

- V3.4 输出顺序固定为 `READ` / `WRITE` / `PHONE_INTERACTION` / `NO_VISIBLE_STUDY`（见 `ml/behavior_recognition` 输出契约与 model_card）。各端命名对应如下，顺序不可调换：

| ml 侧 | Android 枚举 | HarmonyOS 标签 | 中文 |
| --- | --- | --- | --- |
| READ | READING | READ | 阅读 |
| WRITE | WRITING | WRITE | 书写 |
| PHONE_INTERACTION | PHONE_USE | PHONE_INTERACTION | 使用手机 |
| NO_VISIBLE_STUDY | IDLE | NO_VISIBLE_STUDY | 未观察到学习行为 |
| COMPUTER（仅 TSM V4） | COMPUTER | COMPUTER | 使用电脑 |

- 单帧决策（两端一致）：`softmax(logits / 4.841172366232762)`；top ≥ 0.30 且 margin ≥ 0.05 才接受，否则按 `UNCERTAIN` 处理（Android 见 `BehaviorV34Contract.kt`，Harmony 见 `BehaviorV34Decision.ets`）。
- TSM V4 只做时序确认：8 帧输入 `1×8×3×224×224`（NCHW，归一化内嵌），输出 5 类 logits；缺失或不足 8 帧时保留 V3.4 单帧结果，不伪造时序结论。融合权重（Android `BehaviorHybridPolicy.kt`）：READING 0.65/0.35、WRITING 0.90/0.10、PHONE_USE 0.45/0.55；COMPUTER 仅时序确认时进入候选；窄 margin（0.10）有单独处理。
- V3.2 回退：仅 `IDLE` / `VISIBLE_STUDY` 二分类，与 V4 标签空间不兼容——回退时绕过 TSM、清空时序缓存，恢复 V3.4 后重新积累 8 张兼容帧。选择逻辑：V3.4 可用且人物 ROI 有效才选 V3.4，否则用 V3.2（Android `BehaviorModelSelection.select`，`enableV34=false` 可强制回退；Harmony 同名策略类）。
- 产品层连续性：稳定结果映射为 `OBSERVING` / `STUDYING` / `THINKING_OR_ADJUSTING` / `PAUSED`。学习中短暂出现 IDLE：前 8 秒仍保留学习状态，8-20 秒显示"短暂思考或调整中"，超过 20 秒进入"暂时停顿"；该状态机只改变产品连续性，不改变模型标签。
- `StudyBehavior` 枚举保留了大量历史标签（TYPING、DRINKING、LOOKING_AWAY 等），当前链路只使用上表类别与运行期 `UNCERTAIN`。

### 3.3 相机与生命周期

- Android：CameraX 仅在"辅助开启 + 摄像头权限 + 计时运行 + 页面可见 + App 在前台"且模式为 FOCUS 时运行；行为与表情共用一条 FocusCameraPipeline，不为行为识别启动第二个摄像头；暂停、离开页面或生命周期结束会解绑/暂停 use case，`ExpressionSessionManager.release()` 统一释放相机、分析器与模型资源。
- HarmonyOS：仅在后端成功创建或恢复 `focus` 专注会话后启动（`FocusCameraActivationPolicy`：`focusMode === 'focus'` 且 `sessionMode === 'SMART_GUARD'`）；短休/长休不启动；生命周期事件 START/RESUME 启动，PAUSE/FINISH/HIDE/LEAVE/RESET 停止；相机或模型失败不回滚已成功的后端会话。相机帧最快每 500 ms 分析一次。

## 4. 表情识别链路

### 4.1 端到端数据流

Android：

```text
CameraX（与行为共用 FocusCameraPipeline）
→ ML Kit 人脸检测（NO_FACE 由此产生，不是分类器输出）
→ 人脸裁剪（水平 padding 0.16 / 垂直 0.20）
→ 96×96、NHWC、灰度复制为 3 通道、[0,255]→[0,1]、ImageNet 归一化
→ LiteRT resnet18（7 类）
→ ExpressionSignalProcessor（默认 EMA α=0.35；同一类别连续 ≥4 帧且 ≥700 ms 才算稳定；类别阈值取自 model_metadata.json；低于阈值输出 UNKNOWN）
→ ExpressionSignal 随请求上报后端
```

HarmonyOS：

```text
CameraKit → CoreVisionKit faceDetector
→ 同规格 96×96 预处理（JPEG → RGBA_8888 → 镜像 PixelMap，灰度复制）
→ MindSpore Lite campusmate_expression_v2.ms
→ ExpressionSignalProcessor（稳定帧 3、EMA α=0.4、max_age 5000 ms，见 preprocessing.json）
→ withExpressionSignal 随对话上报
```

### 4.2 类别与阈值

- 类别顺序固定（不得变更）：`angry, disgust, fear, happy, neutral, sad, surprise`；Android 映射为大写 `ANGRY…SURPRISE`（`labels.txt`）。
- 全局阈值 0.70，另按类别阈值：angry 0.81 / disgust 0.91 / fear 0.80 / happy 0.30 / neutral 0.83 / sad 0.68 / surprise 0.78（validation 上以 0.80 精度为目标的弃权校准）。
- `NO_FACE` 由人脸检测产生；`UNKNOWN` 由低置信度、分散概率或多帧不稳定产生。
- 端侧建议触发有冷却（Android 为 10 分钟），咨询场景阈值策略见 `CounselorExpressionPolicy`。

### 4.3 与后端的关系（接口层）

- `ExpressionSignal` 字段：`label`（提交前大写化，≤24 字符）、`confidence`（0-1）、`is_stable`、`timestamp`（epoch 毫秒）、`model_version`；**不包含也不允许包含图像数据**。
- 透传位置：`POST /api/v1/assistant/chat`、`POST /api/v1/counselor/chat`（白名单校验后仅用于调整措辞，不用于心理或医学判断），以及专注会话字段。后端不做 CNN 推理，该字段目前标注为"仅透传存储"。
- 样本共建（可选）：`POST /api/v1/contributions/expression-samples`（multipart：`image` / `label` / `consent` / `model_version`，仅 JPG/PNG，需同意）与 `DELETE /api/v1/contributions/expression-samples/{sample_id}`；错误码见接口文档。接口细节：[AI 助手](api/10-assistant-knowledge.md)、[学习陪伴](api/05-study.md)、[字段字典](api/schemas.md)。

## 5. 隐私与产品边界（重写必须保留）

- 画面不上传服务器、不保存原始摄像头画面、不写图像日志；Debug 采样入口由 `BuildConfig.DEBUG` 守门并设数量上限（Android）。
- 识别结果只是本地辅助观察，不得表述为专注度、心理状态、疲劳程度或疾病诊断；各端对 Mock 演示内容必须继续标注。
- 相机启动条件：用户明确授权（含 CPM/AI 页同意）+ 获得相机权限 + 计时/会话运行中 + 页面可见且 App 在前台；任一条件不满足即停止。

## 6. 重写检查清单与已知缺口

1. **表情 multiv2 dynamic_int8 的真源只在 Android assets**：`exports_v2/model_metadata.json` 记录的 sha（`9cef0425…`）与 assets 文件一致，但该 tflite 本体不在 `ml/` 内；本地另一份 dynamic_int8（`c4f6852b…`）是旧 clean-v1 版。重写时以 assets 文件为准，不要从本地导出"重建"。
2. **表情 `.ms` 无仓库内转换脚本**：`ml/expression_recognition` 没有任何 MindSpore 相关代码，`campusmate_expression_v2.ms` 的哈希在任何元数据中均未记录（本文实测 `218eed91…`）。重写鸿蒙端时保留原件，建议补一个转换/校验脚本文档。
3. **鸿蒙没有 V3.2 回退模型**：rawfile 里只有 V3.4 与 TSM V4 两个 `.ms`；model_card 的 V3.2 回退语义来自 Android 链路。重写时二选一：补转换 V3.2 的 `.ms`，或保持"TSM 失败→V3.4 单帧"的现状。
4. **运行时不可替换**：Android 依赖 ONNX Runtime（行为）、LiteRT（表情）、ML Kit（人脸）；鸿蒙依赖 MindSpore Lite 与系统 CoreVisionKit（人体/人脸检测是系统能力，不是打包模型）。类别顺序、输入形状、归一化、阈值/温度必须逐项对齐 metadata / model_card。
5. **两套预处理不复用**：行为是 224×224 / NCHW / ImageNet 归一化；表情是 96×96 / NHWC / 灰度复制 + ImageNet 归一化。不要跨链路复用一个预处理实现。
6. **稳定性参数两端现状不同**：Android 表情默认 4 帧 / 700 ms / EMA 0.35，鸿蒙为 3 帧 / EMA 0.4 / 5 s 时效（见各自配置）。若重写后要求跨端一致，先明确取舍再改。
7. **文档遗留**：`android/README.md` 引用"主 README 的 CNN 面部表情识别章节"，该章节不存在，重写时顺带修正。

## 7. 参考索引

| 主题 | 位置 |
| --- | --- |
| Android 表情识别 / Focus 架构 / 行为识别演进 | [android/README.md](../android/README.md) |
| HarmonyOS 本地表情与学习行为识别 | [harmony/README.md](../harmony/README.md) |
| 行为模型训练、导出与 MindSpore 转换 | [ml/behavior_recognition/README.md](../ml/behavior_recognition/README.md) |
| 表情模型训练与 LiteRT 导出 | [ml/expression_recognition/README.md](../ml/expression_recognition/README.md) |
| Android 运行时契约与元数据 | [model_metadata.json](../android/app/src/main/assets/model_metadata.json)、[preprocessing.json](../android/app/src/main/assets/preprocessing.json)、[labels.txt](../android/app/src/main/assets/labels.txt) |
| HarmonyOS 运行时契约 | [model_card.json](../harmony/entry/src/main/resources/rawfile/models/behavior/model_card.json)、[expression/preprocessing.json](../harmony/entry/src/main/resources/rawfile/models/expression/preprocessing.json) |
| 后端透传与样本共建接口 | [AI 助手接口](api/10-assistant-knowledge.md)、[学习陪伴接口](api/05-study.md) |
| Android 关键源码 | [data/behavior/](../android/app/src/main/java/com/example/campusai/data/behavior)、[data/expression/](../android/app/src/main/java/com/example/campusai/data/expression) |
| HarmonyOS 关键源码 | [service/](../harmony/entry/src/main/ets/service)（MindSporeBehaviorProvider、MindSporeExpressionProvider、FocusCameraPipeline、FocusCameraContract 等） |