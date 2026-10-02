# 端侧识别链路交接（行为识别 / 表情识别）

面向 Android、HarmonyOS 客户端重写，以及微信小程序 / Web 端后续开发的链路说明，覆盖模型资产、端到端数据流、类别与校准契约、各端实现现状、回退语义、隐私边界和已知缺口。

整理于 2026-09-30；2026-10-02 复核：§2 的 7 个部署模型 SHA-256 逐个重算，与本文记录逐位一致；§2.3 的 `ml/` 产物清单、§6 各端现状、§7 源码入口索引和 §8 新增缺口为本次按代码现状补充，行号对应复核时的文件状态。

统一口径：两项能力都在设备本地推理，画面**不上传服务器、不保存原始图像、不写图像日志**；识别结果只是辅助观察，不代表专注度、心理状态或学习效果。后端不加载任何推理运行时（`backend/requirements.txt` 无 onnxruntime / torch / tensorflow / mindspore / mediapipe），工作区内也没有任何模型权重文件；它只接收端侧算好的结构化信号。

## 1. 能力与运行时总览

| 能力 | Android | HarmonyOS | 微信小程序 | Web（`webreact/`） |
| --- | --- | --- | --- | --- |
| 行为识别 | CameraX + ONNX Runtime（V3.4 单帧、V4 TSM 8 帧，V3.2 回退）；人体检测用打包的 EfficientDet-Lite0 int8 | CameraKit + CoreVisionKit 系统人体检测（无打包模型）+ MindSpore Lite（V3.4、TSM V4） | 未实现 | 未实现 |
| 表情识别 | CameraX + ML Kit 人脸检测 + LiteRT（resnet18） | CameraKit + CoreVisionKit faceDetector + MindSpore Lite | 微信原生 `createInferenceSession` 本机跑 ONNX；模型不随包分发，需用户配置 HTTPS 下载地址 | 未实现 |
| 人脸/人体检测 | Android 打包模型或系统能力（见上） | 均为系统 CoreVisionKit 能力，不随应用打包 | 无独立检测环节：整帧中心正方形裁剪后直接送表情分类器（见 §6.1） | — |
| 成熟度 | 参考实现，资产与契约齐全 | 已实现，V3.2 回退资产缺失（§8.3） | 链路已接入代码，真机模型验证未完成（§6.1） | 零代码（§6.2） |

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

2026-10-02 实测产物清单（大小按 1 MB = 1048576 B 折算）。

**`ml/expression_recognition/`**

| 路径 | 大小 | SHA-256 前 16 位 | 说明 |
| --- | ---: | --- | --- |
| `exports/resnet18/expression_resnet18_dynamic_int8.tflite` | 10.74 MB | `c4f6852bbe45d302` | clean-v1 量化版；同目录 `model.sha256` 与 `model_metadata.json`（`model_version=expression-resnet18-clean-v1`）都指向该哈希 |
| `exports/resnet18/expression_resnet18_float32.tflite` | 42.64 MB | `69d9db82c9c61fdb` | clean-v1 浮点版 |
| `exports/resnet18/best_checkpoint.pt` | 128.06 MB | — | clean-v1 训练权重 |
| `exports_v2/expression_resnet18_float16.tflite` | 21.33 MB | — | multiv2，非部署变体 |
| `exports_v2/expression_resnet18_float32.tflite` | 42.64 MB | — | multiv2，非部署变体 |
| `exports_v2/expression_resnet18_full_int8.tflite` | 10.80 MB | `196854085c41e0be` | multiv2 full_int8，**与部署用的 dynamic_int8 不是同一个模型** |
| `exports_v2/best_checkpoint.pt` | 128.06 MB | — | multiv2 训练权重，重新导出时唯一可信起点 |
| `exports_v2/model_metadata.json` | — | — | `model_version=expression-resnet18-multiv2-v1`、`selected_variant=dynamic_int8`、`model_sha256=9cef0425…`，但**该 tflite 本体不在目录内** |
| `exports_v2/models_v1_backup/expression_model.tflite` | 10.74 MB | `c4f6852bbe45d302` | ⚠️ 文件名和大小都与 Android assets 的部署模型完全相同（11263264 B），内容却是旧 clean-v1 |

结论：部署中的 multiv2 dynamic_int8（`9cef0425…`）在整个仓库里只有 §2.1 那一份。按文件名或按大小挑选都会掉进 `models_v1_backup` 的同名同尺寸陷阱，必须校验 SHA-256。

导出脚本只覆盖 LiteRT 路线：`scripts/export_litert.ps1`、`export_litert_v2.ps1`、`reproduce_training.ps1`、`train_all_v2.ps1`、`compile_final_report.py`、`dataset_inventory.py`。目录内没有任何 ONNX 或 MindSpore 相关代码（对 `scripts/` 与 `src/` 搜 `onnx` 零命中），这是 §8.1、§8.2 两个缺口的根因。

**`ml/behavior_recognition/`**：训练、评估、导出与 MindSpore 转换代码齐全——`src/behavior_recognition/` 26 个模块（含 `train.py`、`temporal_train.py`、`export_onnx.py`、`export_temporal_onnx.py`、`calibrate.py`、`promotion_gate.py`、`offline_gate.py`），`configs/` 7 份 yaml，`tests/` 23 个 `test_*.py`。**`exports/`、`runs/`、`manifests/` 三个产物目录都不存在**，因此行为 ONNX 的当前唯一副本就是 §2.1 列出的 Android assets；鸿蒙 `.ms` 由这些 ONNX 经 `scripts/convert_v34_to_mindir_lite.ps1`、`scripts/convert_tsm_v4_to_mindir_lite.ps1` 转换（配合 `scripts/prepare_v34_for_mindspore.py` 做 HardSwish→HardSigmoid 等价替换，适配 MindSpore Lite 2.1），端侧一致性用例来自 `scripts/create_v34_parity_fixture.py`、`scripts/create_tsm_v4_parity_fixture.py`。

训练数据不随仓库分发，需要 `CAMPUSMATE_BEHAVIOR_DATASET_ROOT` / `CAMPUSMATE_EXPRESSION_DATASET_ROOT` 指向本地只读数据源。

## 3. 行为识别链路

### 3.1 端到端数据流

Android：

```text
CameraX
→ FocusCameraPipeline / CameraFrame
→ BehaviorAnalyzer（BehaviorModelConfig.DIRECT_224：400 ms 采样、16 帧缓冲、相机帧直接缩放到 224×224）
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
- 采集配置见 `android/app/src/main/java/com/example/campusai/data/behavior/BehaviorFrameBuffer.kt:6-34`：生产默认 `DIRECT_224`（`frameCount=16`、`224×224`、`sampleIntervalMs=400`、`confidenceThreshold=0.5`），相机帧直接缩放到 224×224，使引擎内的预处理成为空操作，从而与训练时的预处理完全一致；`LEGACY_192`（192×192、200 ms）只保留给上线前的 A/B 对比，不要用于新的分析器。

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
- **同一套阈值在三个地方各有一份副本，改一处必须同步另两处**：Android `assets/model_metadata.json`、HarmonyOS `rawfile/models/expression/preprocessing.json`（实测 `confidence_threshold=0.7` 与 7 类阈值逐类和 Android 相同）、后端 `emotion_context.py:21-29`。
- 鸿蒙 `preprocessing.json` 还带 `max_age_ms=5000`，与后端信号新鲜度窗口（§4.3）同值。信号超过 5 s 后端直接丢弃，端侧不要单独放大时效。
- 模型版本名各端不同：Android 是 `expression-resnet18-multiv2-v1`，鸿蒙是 `expression-resnet18-multiv2-v1-mslite`。上报 `model_version` 时按本端资产元数据原样填写，不要跨端统一。
- `NO_FACE` 由人脸检测产生；`UNKNOWN` 由低置信度、分散概率或多帧不稳定产生。
- 端侧建议触发有冷却（Android 为 10 分钟），咨询场景阈值策略见 `CounselorExpressionPolicy`。

### 4.3 与后端的关系（接口层）

- `ExpressionSignal` 契约（实测 `backend/app/schemas/chat.py:36-50`）：`label`（1–24 字符，`field_validator` 以 `strip().upper()` 归一）、`confidence`（0–1）、`is_stable`（默认 `false`）、`timestamp`（Unix epoch 毫秒，`gt=0`）、`model_version`（1–80 字符，必填——必填即反证模型在端侧）；**不包含也不允许包含图像数据**。
- 后端两条消费路径语义不同，重写时不要混为一谈：
  1. **对话路径不入库**：`POST /api/v1/counselor/chat` 与 `POST /api/v1/assistant/chat` 是同一个 handler 的两个路径别名（`backend/app/api/routes/counselor.py:660-661`，兼容旧客户端），由 `EmotionContextBuilder`（`backend/app/services/emotion_context.py`）按固定顺序校验：标签白名单 → `is_stable` → 新鲜度（`max_age_ms=5000`，未来偏移容忍 2000 ms）→ 类别阈值。任一不过则丢弃信号并追加一条中文 `context_warnings`（`routes/counselor.py:559`、`:703-712`，字段见 `schemas/chat.py:185-188`）；通过时 `context_used.expression_signal_used=true`，生成的提示词只用于微调回复措辞，且强制带上"不是心理或医学结论"的约束。信号内容本身不写库、不进日志（`routes/counselor.py:555`、`:899`）。
  2. **会话路径入库**：`PATCH /api/v1/study/sessions/{session_id}`（`routes/study.py:385`）把 `expression_signal` 以 JSON 字符串写入 `study_sessions.expression_signal` 列（`:415` → `repositories/study_session_repository.py:428-435`）；`POST /api/v1/study/sessions/{session_id}/finish`（`routes/study.py:327`）写入聚合后的 `behavior_summary`（`:349-353` → `study_session_repository.py:359-361`）。两列的建表与增量迁移在 `backend/app/database/sqlite_db.py:351-352` 和 `:2377-2378`。后端只序列化存储，不解析其语义，也不会用 `expression_signal` 代填 `self_report`（`routes/study.py:337`）。
- 后端复用的 7 类阈值与端侧 `model_metadata.json` 逐项相同：NEUTRAL 0.83 / HAPPY 0.30 / SAD 0.68 / ANGRY 0.81 / FEAR 0.80 / SURPRISE 0.78 / DISGUST 0.91（`emotion_context.py:21-29`）。**改端侧校准必须同步改这份后端副本**，否则端侧判为稳定的信号会被后端整批判为未达阈值。
- 样本共建（可选，也是唯一允许传图像的通道）：`POST /api/v1/contributions/expression-samples`（`routes/contributions.py:46`，multipart：`image` / `label` / `consent` / `model_version`，仅 JPG/PNG，需用户同意）与 `DELETE /api/v1/contributions/expression-samples/{sample_id}`（`:121`）；后端把字节写盘并保存元数据，不做任何推理，用途是离线重训。错误码与字段见接口文档：[AI 助手](api/10-assistant-knowledge.md)、[学习陪伴](api/05-study.md)、[字段字典](api/schemas.md)。

## 5. 隐私与产品边界（重写必须保留）

- 画面不上传服务器、不保存原始摄像头画面、不写图像日志；Debug 采样入口由 `BuildConfig.DEBUG` 守门并设数量上限（Android）。
- 识别结果只是本地辅助观察，不得表述为专注度、心理状态、疲劳程度或疾病诊断；各端对 Mock 演示内容必须继续标注。
- 相机启动条件：用户明确授权（含 CPM/AI 页同意）+ 获得相机权限 + 计时/会话运行中 + 页面可见且 App 在前台；任一条件不满足即停止。
- 微信小程序的模型文件是"从用户配置的 HTTPS 地址下载到本机缓存"（§6.1），属于入站取模型、不是出站传画面；帧数据始终留在设备侧。新增端时不要把这条下载误认成隐私例外，也不要放宽 `https://` 校验。
- 样本共建（§4.3）是唯一允许图像离开设备的通道，且必须用户主动同意才能触发，识别链路不得自动上传帧。

## 6. 各端实现现状（2026-10-02 实测）

### 6.1 微信小程序

- 推理入口 `wx/miniprogram/services/local-vision-session.ts`：能力探测 `wx.canIUse('createInferenceSession')`（`:49`）→ `wx.downloadFile` 下载模型并 `saveFile` 缓存到本机（`:141-154`）→ `createInferenceSession({ precisionLevel: 3, allowNPU: true, allowQuantize: false })`（`:159`）→ 帧回调里 `session.run`（`:117`）。采样间隔 750 ms（`:26`），7 类标签顺序与端侧一致（`:25`）。
- 页面接线：`wx/miniprogram/pages/counselor/counselor.ts:50` 实例化、`:123-127` 读取设置中的模型地址后 `prepare()` 再 `start(wx.createCameraContext())`；`wx/miniprogram/package-study/pages/study/study.ts:49`、`:245-253` 同理。
- 模型**不随小程序包分发**：`wx/scripts/audit-package-size.js:17,133` 会阻断任何 `.tflite/.onnx/.pt` 等进入包体；下载地址由用户在"我的"页配置，`wx/miniprogram/pages/profile/profile.ts:145-150` 强制 `https://` 前缀。因此这条链路依赖一个仓库外的模型托管域名，与 §2 的打包资产清单无关。
- ⚠️ **预处理与 Android / HarmonyOS 不等价**：`wx/miniprogram/services/vision-preprocess.ts:8-36` 取整帧的**中心正方形**裁边后直接重采样到 96×96 NHWC（灰度复制 + ImageNet 归一化），**没有人脸检测、没有人脸框、没有 0.16/0.20 的裁剪 padding**。同一个 `.tflite`/`.onnx` 分类器在这里拿到的是"含身体与桌面的整帧"而非"人脸 ROI"，输入分布与另外两端不同，置信度阈值与稳定性参数不能照抄，真机验证时必须单独校准。
- 完成度以 `wx/parity/feature-matrix.json` 为准：`:19` 将 `local-expression` 标为 `BLOCKED`（"运行链路已接入；需提供兼容 ONNX 下载地址并完成微信真机模型验证"），`:21` 将 `expression-contribution` 标为 `MISSING`（小程序尚无拍摄-同意-上传-删除流程）。

### 6.2 Web（`webreact/`）

- 现状是零实现：`webreact/src` 与 `webreact/tests` 中 `getUserMedia` / `mediaDevices` / `expression_signal` / `behavior_summary` 全部零命中；唯一与 "camera" 相关的代码是 `LearningIsland` 里 three.js 的相机对象。
- `webreact/package-lock.json:895` 出现的 `@mediapipe/tasks-vision@0.10.17` 是 `@react-three/drei@9.122.0` 的**传递依赖**（`package-lock.json:2522`），`webreact/package.json` 并未声明它，业务代码也没有 import。不要据此认为 Web 端已具备人脸检测能力。
- 若要补齐链路，Web 侧需要新增：摄像头采集与生命周期门控（对齐 §5 的启动条件）、人脸检测与 ROI 裁剪、两套互不复用的预处理（§8.5）、稳定性判定、`expression_signal` 装配上报。
- 可直接复用的资产：行为侧 `campusmate_behavior_v34.onnx`（5.81 MB）与 `campusmate_tsm_mobilenetv2_v4.onnx`（8.67 MB）本身就是 ONNX，可在 onnxruntime-web（WASM / WebGPU）直接加载，输入形状、softmax 温度与阈值契约按 §3.2 复用。
- 表情侧没有 Web 可用格式：部署模型只有 Android assets 里那份 `.tflite`，而 `ml/expression_recognition/` 内没有 ONNX 导出脚本（§2.3）。上 Web 需要从 `exports_v2/best_checkpoint.pt` 新增一条导出路线，并把产物的 SHA-256 登记回本文；不要用 `exports_v2/expression_resnet18_full_int8.tflite`（`19685408…`）或 `exports_v2/models_v1_backup/expression_model.tflite`（`c4f6852b…`，旧 clean-v1）冒名替代。
- Web 若落地，隐私边界必须与移动端一致：浏览器端同样不得把帧或人脸图发往后端，只发 §4.3 的结构化信号。

## 7. 各端源码入口索引

行号为 2026-10-02 实测，重写或做跨端对齐时先读这些位置。

| 环节 | Android | HarmonyOS | 微信小程序 |
| --- | --- | --- | --- |
| 相机与帧门控 | `android/.../data/camera/`（FocusCameraPipeline）、`data/behavior/BehaviorFrameBuffer.kt:6-34` | `harmony/.../service/FocusCameraPipeline.ets`、`service/FocusCameraContract.ts`（含 `PersonRoiSelector`；注意该文件是 `.ts` 而非 `.ets`） | `wx/.../services/local-vision-session.ts:82-99` |
| 人脸/人体检测 | `data/expression/RealExpressionRecognitionService.kt:13,39`（ML Kit） | 系统 CoreVisionKit：`objectDetection`、`faceDetector` | 无 |
| 表情推理 | `data/expression/ExpressionModelRunner.kt:59-64`（assets `openFd` + `Interpreter`）、`:127`（`run`） | `service/MindSporeExpressionProvider.ets:94-97`（`loadModelFromBuffer`）、`:249`（`predict`） | `services/local-vision-session.ts:159`（建会话）、`:117`（`run`） |
| 表情预处理 | `assets/preprocessing.json` + `ExpressionModelRunner.kt:148` | `resources/rawfile/models/expression/preprocessing.json` | `services/vision-preprocess.ts:8-36`（⚠️ 中心裁剪，无人脸 ROI） |
| 稳定判定 | `data/expression/ExpressionSignalProcessor.kt:6-13`（EMA 0.35、`minimumStableFrames=4`、700 ms、建议冷却 10 min） | `service/` 内同名处理器（3 帧、EMA 0.4、5 s 时效） | `services/expression-signal.ts` |
| 行为推理 | `data/behavior/OnnxBehaviorRecognitionEngine.kt:150-151,90`；`OnnxTsmBehaviorRecognitionEngine.kt:32-33,66` | `service/MindSporeBehaviorProvider.ets:305,378,546,579` | 未实现 |
| 行为决策契约 | `data/behavior/BehaviorV34Contract.kt`、`BehaviorHybridPolicy.kt`、`BehaviorModelSelection` | `service/BehaviorV34Decision.ets`、`BehaviorModelSelection.ets` | — |
| 上报装配 | `data/remote/ApiService.kt:52-65`（`ExpressionSignalRequest` / `ChatRequest`）、`:1165`（`counselor/chat`）、`:1400,1408`（样本共建）；`data/repository/AppRepository.kt:1234,1277` | `data/ExpressionSignalChatBridge.ets:5-18`、`pages/Index.ets:693,703`、`data/ApiClient.ets:384` | `services/repository.ts:559-566` |
| 运行时依赖 | `android/app/build.gradle.kts:87,98,126-138` | MindSpore Lite Kit + 系统 CoreVisionKit | 微信基础库 `createInferenceSession` |

后端消费侧：`backend/app/schemas/chat.py:36-50`（信号契约）、`services/emotion_context.py:21-59`（阈值与校验）、`api/routes/counselor.py:660-661,698-712`（对话路径，含 `/assistant/chat` 别名）、`api/routes/study.py:327,349-353,385,415`（会话入库）、`database/sqlite_db.py:351-352,2377-2378`（列与迁移）、`api/routes/contributions.py:46,121`（样本共建）。

## 8. 重写检查清单与已知缺口

1. **表情 multiv2 dynamic_int8 的真源只在 Android assets**：`exports_v2/model_metadata.json` 记录的 sha（`9cef0425…`）与 assets 文件一致，但该 tflite 本体不在 `ml/` 内（见 §2.3 全清单）。更危险的是 `exports_v2/models_v1_backup/expression_model.tflite` 与部署模型**同名且同字节数（11263264 B）**，内容却是旧 clean-v1（`c4f6852b…`）。重写时以 assets 文件为准并按 SHA-256 校验，不要从本地导出目录"重建"。
2. **表情 `.ms` 无仓库内转换脚本**：`ml/expression_recognition` 没有任何 MindSpore 相关代码，`campusmate_expression_v2.ms` 的哈希在任何元数据中均未记录（本文实测 `218eed91…`）。重写鸿蒙端时保留原件，建议补一个转换/校验脚本文档。
3. **鸿蒙 V3.2 回退是"代码在、资产缺"**：`MindSporeBehaviorProvider.ets:238` 声明了 `V32_MODEL_PATH`，`:473-484` 有完整加载与输入契约校验，`:539-547` 有推理分支，但 `rawfile/models/behavior/` 里只有 `campusmate_behavior_v34.ms` 与 `campusmate_tsm_mobilenetv2_v4.ms`，没有 `campusmate_visible_study_v32.ms`。`loadV32Model` 的 `catch` 返回 `null`（`:481-483`），`analyze` 把 `v32Model !== null` 作为可选条件交给 `BehaviorModelSelection.select`（`:352-357`），所以缺文件不会崩溃，而是让回退分支永远不可达，实际语义退化为"V3.4 不可用即 UNAVAILABLE"。重写时二选一：把 Android 那份 42.63 MB 的 `campusmate_visible_study_v32.onnx` 转成 `.ms`（体积代价大），或删掉死代码并明确"无 V3.2 回退"。
4. **运行时不可替换**：Android 依赖 ONNX Runtime（行为）、LiteRT（表情）、ML Kit（人脸）；鸿蒙依赖 MindSpore Lite 与系统 CoreVisionKit（人体/人脸检测是系统能力，不是打包模型）。类别顺序、输入形状、归一化、阈值/温度必须逐项对齐 metadata / model_card。
5. **两套预处理不复用**：行为是 224×224 / NCHW / ImageNet 归一化；表情是 96×96 / NHWC / 灰度复制 + ImageNet 归一化。不要跨链路复用一个预处理实现。
6. **稳定性参数两端现状不同**：Android 表情默认 4 帧 / 700 ms / EMA 0.35，鸿蒙为 3 帧 / EMA 0.4 / 5 s 时效（见各自配置）。若重写后要求跨端一致，先明确取舍再改。
7. **文档遗留**：`android/README.md` 引用"主 README 的 CNN 面部表情识别章节"，该章节不存在，重写时顺带修正。
8. **后端持有第二份表情阈值**：`backend/app/services/emotion_context.py:21-29` 的 7 类阈值必须与端侧 `model_metadata.json` 逐类相同。只改端侧会让已判稳定的信号被后端整批丢弃并回一条 `context_warnings`（§4.3）。
9. **两条上报路径语义不同**：对话（`counselor/chat`、`assistant/chat`）只用于调整措辞、不入库；会话（`PATCH /study/sessions/{session_id}`、`POST /study/sessions/{session_id}/finish`）才把 `expression_signal` / `behavior_summary` 写进 `study_sessions`。新端接入按 §4.3 分别装配，不要指望后端补算或代填 `self_report`。
10. **小程序的表情输入分布不同**：中心正方形整帧裁剪、无人脸检测（§6.1）。直接沿用 Android 的全局 0.70 阈值与 4 帧 / 700 ms 判定会得到不可比结果，先真机校准再谈跨端一致。
11. **Web 端表情没有可用格式**：需新增 ONNX 导出路线并把产物哈希登记回本文（§6.2）；行为侧两个 ONNX 可直接复用。
12. **Android 构建约束不可"顺手清理"**：`onnxruntime-android:1.24.3`（`android/app/build.gradle.kts:98`）；`tensorflow-lite-task-vision` 必须 `exclude(group = "org.tensorflow", module = "tensorflow-lite-api")`（`:132-137`），否则与 LiteRT 的同名 `org.tensorflow.lite` 类冲突；`noCompress += "tflite"`（`:87`）保证模型能 mmap 加载。三者都是运行前提，不是依赖冗余。

## 9. 参考索引

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
| 微信小程序本机推理与预处理 | [services/local-vision-session.ts](../wx/miniprogram/services/local-vision-session.ts)、[services/vision-preprocess.ts](../wx/miniprogram/services/vision-preprocess.ts)、[services/expression-signal.ts](../wx/miniprogram/services/expression-signal.ts) |
| 微信小程序完成度矩阵 | [parity/feature-matrix.json](../wx/parity/feature-matrix.json)（`local-expression` = BLOCKED、`expression-contribution` = MISSING） |
| 后端信号校验 | [services/emotion_context.py](../backend/app/services/emotion_context.py)、[schemas/chat.py](../backend/app/schemas/chat.py) |
| 后端消费与入库 | [routes/counselor.py](../backend/app/api/routes/counselor.py)、[routes/study.py](../backend/app/api/routes/study.py)、[repositories/study_session_repository.py](../backend/app/repositories/study_session_repository.py) |
| 行为模型 MindSpore 转换脚本 | [ml/behavior_recognition/scripts/](../ml/behavior_recognition/scripts) |