# CampusMate AI — Android 移动端

大学生校园事务智能陪伴助手的原生 Android 客户端。

## 技术栈

- **Kotlin** + **Jetpack Compose**(Material 3)
- **Navigation Compose** 路由
- **Retrofit** + **Moshi** + **OkHttp** 网络(Mock/Real 双模式)
- **DataStore Preferences** 本地持久化
- **CameraX** + **ML Kit** 人脸检测 + **LiteRT** 表情分类
- **Media3 ExoPlayer** 视频背景
- **Kotlin Coroutines + Flow** 异步

## 项目结构

```
app/src/main/java/com/example/campusai/
├── data/
│   ├── expression/          # 表情识别模块(CameraX + ML Kit + LiteRT, Mock/Real 双实现)
│   ├── focus/               # 专注状态处理
│   ├── local/               # DataStore 本地持久化
│   ├── model/               # 数据模型(User/Notice/Task/Course/ChatMessage/ext.)
│   ├── remote/              # Retrofit API 客户端与服务接口
│   └── repository/          # Repository 层(统一数据入口, Mock/Real 可切换)
├── ui/
│   ├── components/          # 通用组件与动效(EnterAnimation/CampusVideoBackground/ext.)
│   ├── navigation/          # AppNavHost(Navigation Compose 路由图)
│   ├── screens/             # 业务页面(17 个模块, 34 个 Screen 文件)
│   ├── strings/             # 字符串资源
│   └── theme/               # Material 3 主题(Color/Type/Motion)
└── MainActivity.kt          # 入口 Activity
```

## 业务页面

| 模块 | 路径 |
|------|------|
| 仪表盘 | `ui/screens/dashboard/` |
| 登录 | `ui/screens/login/` |
| 通知 | `ui/screens/notifications/` |
| 待办任务 | `ui/screens/tasks/` |
| AI 导员 | `ui/screens/counselor/` |
| 专注自习 | `ui/screens/focus/` |
| 课程 | `ui/screens/courses/` |
| 考试 | `ui/screens/exams/` |
| 失物招领 | `ui/screens/lostfound/` |
| 办事服务 | `ui/screens/services/` |
| 教室查询 | `ui/screens/classrooms/` |
| 个人中心 | `ui/screens/profile/` |
| 设置 | `ui/screens/profile/SettingsScreen.kt` |
| 教师端 | `ui/screens/teacher/` |
| 管理员 | `ui/screens/admin/` |

## 构建配置

| 配置 | 值 |
|------|-----|
| compileSdk | 34 |
| minSdk | 28 |
| targetSdk | 34 |
| JVM Target | 17 |
| Compose BOM | 2024.04.01 |
| 默认 API 地址 | `http://10.0.2.2:8000/api/v1/` |

### 构建命令

```bash
# 调试构建
gradlew.bat :app:assembleDebug        # Windows
./gradlew :app:assembleDebug          # Linux / macOS

# 发布构建
gradlew.bat :app:assembleRelease

# 自定义后端地址(真机调试)
gradlew.bat :app:assembleDebug -PAPI_BASE_URL=http://<LAN_IP>:8000/api/v1/
```

## 表情识别

专注自习页面已接入 CameraX + ML Kit 本机人脸检测 + LiteRT 表情分类，保留 Mock/Real 双模式。

- 模型文件: `app/src/main/assets/expression_model.tflite`
- 实现: `data/expression/` (含 `RealExpressionRecognitionService` / `MockExpressionRecognitionService`)
- 隐私: 画面不保存、不上传、不写日志，仅在用户主动授权且专注计时运行中分析
- 详见主 README 的"CNN 面部表情识别"章节

## 学习状态辅助（V3.2-A）与 Presence（V3.3.1）

专注自习页的学习状态辅助与表情识别共享同一条 CameraX pipeline；不会为行为识别启动第二个摄像头。

### 1. 当前能力与产品语义

V3.2-A 是「是否观察到明确可见学习行为」的二分类，而不是专注度或心理状态判断：

- **VISIBLE_STUDY（可见学习行为）**：阅读、书写、明显操作书本、纸张等学习材料。
- **IDLE（暂未观察到明确学习行为）**：人在画面中，但当前未看到明确学习动作；不应解读为“不专注”或“没有学习”。

UI 会将模型稳定状态进一步映射为 `OBSERVING`、`STUDYING`、`THINKING_OR_ADJUSTING` 和 `PAUSED`。学习中短暂出现 `IDLE` 时，前 8 秒仍保留学习状态，8～20 秒显示“短暂思考或调整中”，超过 20 秒才进入“暂时停顿”。

### 2. Android 数据流

```
CameraX
→ FocusCameraPipeline / CameraFrame
→ BehaviorAnalyzer（帧缓冲与单线程推理调度）
→ OnnxBehaviorRecognitionEngine
→ campusmate_visible_study_v32.onnx（本地 ONNX 推理）
→ BehaviorPrediction（IDLE / VISIBLE_STUDY 概率）
→ BehaviorSignalProcessor（启动观察、时间窗口与稳定判定）
→ LearningContinuityStateMachine（会话级连续性）
→ FocusScreen（学习状态、节奏与本次观察摘要）
```

同一条 `FocusCameraPipeline` 的 `CameraFrame` 还会低频送入 `PersonAnalyzer`。行为识别、表情识别和 person detector 共享这一个 CameraX pipeline；ONNX 与 TFLite 推理全部在设备端完成，不会启动第二个摄像头。

### 3. 当前部署模型

| 项 | 值 |
|------|------|
| Backbone | ResNet18 |
| Modality | RGB |
| Input | 224 × 224，RGB，ImageNet normalize |
| Runtime | ONNX Runtime Android |
| Output | `IDLE` / `VISIBLE_STUDY` |
| 当前模型 | `assets/models/behavior/campusmate_visible_study_v32.onnx` |
| 回退模型 | `assets/models/behavior/campusmate_visible_study_v31.onnx`、`assets/models/behavior/rgb_resnet18_v2.onnx`（历史 V2） |

### 4. 主要实现文件

- `data/behavior/OnnxBehaviorRecognitionEngine.kt` — 模型加载、预处理、推理、softmax 与 V3.2-A 类别映射
- `data/behavior/BehaviorAnalyzer.kt` — 帧缓冲、并发推理控制与 Bitmap 回收
- `data/behavior/BehaviorSignalProcessor.kt` — 观察期、时间窗口与稳定状态输出
- `data/behavior/LearningContinuityStateMachine.kt` — 会话级连续性状态
- `data/behavior/BehaviorObservationHistory.kt` — 当前 Focus session 的节奏与统计历史
- `data/expression/ExpressionSessionManager.kt` — 在共享 CameraX pipeline 中接入表情和行为结果
- `ui/focus/FocusScreen.kt` — 学习状态辅助产品 UI

### 5. Presence（在席）语义

Presence 不属于行为模型类别，状态为 `PRESENT`、`OBSERVING`、`ABSENT`：

- `PRESENT` 可以同时是 `VISIBLE_STUDY` 或 `IDLE`；`IDLE` 不表示离席。
- 本地 EfficientDet-Lite0 int8 COCO person detector 是主要证据（阈值 `0.45`、约 2 FPS、最近 person evidence 保持 2 秒）。稳定 `VISIBLE_STUDY` 与 ML Kit `faceDetected` 是辅助正向证据。
- 任意正向证据立即刷新 Presence；已经确认在席后，连续少于 12 秒没有证据仍保持 `PRESENT`，达到 12 秒才进入 `ABSENT`。`OBSERVING` 主要用于首次尚未确认的阶段。
- `ABSENT` 仅表示持续没有本地在席证据，不代表用户停止学习。

### 6. Debug 工具与隐私

Debug 构建在摄像头构图提示下方提供折叠的“开发者工具”。它支持本地视觉测试（不创建或上传正式后端 Focus session）及 `idle`、`visible_study`、`visible_study_hard` 目标域采集；Release 中不显示入口。采集来自行为模型实际使用的 CameraFrame 链路，以约 1 FPS 保存，每个 session 最多 120 张。开始采集有 5 秒准备倒计时，倒计时阶段不保存图片；metadata 记录 `session_started_at`、`capture_started_at`、`capture_delay_ms` 和图片信息。

正常运行时：

- 摄像头图像仅设备端处理
- 不上传服务器
- 不保存原始实时摄像头画面
- 不把原始图像写入日志
- 推理在设备端完成

详见专项研究文档：[`../docs/behavior-recognition.md`](../docs/behavior-recognition.md)

## 运行要求

- Android Studio Hedgehog (2023.1.1) 或更高版本
- JDK 17
- Android SDK 34
- 模拟器或 Android 8.0+ 真机

## 更多信息

- 项目规范: 参见仓库根目录 [`AGENTS.md`](../AGENTS.md)
- 后端 API: 参见 [`backend/README.md`](../backend/README.md)
- 表情识别训练: 参见 [`ml/expression_recognition/README.md`](../ml/expression_recognition/README.md)
