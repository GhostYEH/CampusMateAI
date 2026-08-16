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

## 学习状态辅助（V3.1）

专注自习页的学习状态辅助与表情识别共享同一条 CameraX pipeline；不会为行为识别启动第二个摄像头。

### 1. 当前能力与产品语义

V3.1 是「是否观察到明确可见学习行为」的二分类，而不是专注度或心理状态判断：

- **VISIBLE_STUDY（可见学习行为）**：阅读、书写、明显操作书本、纸张等学习材料。
- **IDLE（暂未观察到明确学习行为）**：人在画面中，但当前未看到明确学习动作；不应解读为“不专注”或“没有学习”。

UI 会将模型稳定状态进一步映射为 `OBSERVING`、`STUDYING`、`THINKING_OR_ADJUSTING` 和 `PAUSED`。学习中短暂出现 `IDLE` 时，前 8 秒仍保留学习状态，8～20 秒显示“短暂思考或调整中”，超过 20 秒才进入“暂时停顿”。

### 2. Android 数据流

```
CameraX
→ FocusCameraPipeline / CameraFrame
→ BehaviorAnalyzer（帧缓冲与单线程推理调度）
→ OnnxBehaviorRecognitionEngine
→ campusmate_visible_study_v31.onnx（本地 ONNX 推理）
→ BehaviorPrediction（IDLE / VISIBLE_STUDY 概率）
→ BehaviorSignalProcessor（启动观察、时间窗口与稳定判定）
→ LearningContinuityStateMachine（会话级连续性）
→ FocusScreen（学习状态、节奏与本次观察摘要）
```

行为识别与表情识别继续共享现有 CameraX pipeline；ONNX 推理全部在设备端完成。

### 3. 当前部署模型

| 项 | 值 |
|------|------|
| Backbone | ResNet18 |
| Modality | RGB |
| Input | 224 × 224，RGB，ImageNet normalize |
| Runtime | ONNX Runtime Android |
| Output | `IDLE` / `VISIBLE_STUDY` |
| 当前模型 | `assets/models/behavior/campusmate_visible_study_v31.onnx` |
| 回退模型 | `assets/models/behavior/rgb_resnet18_v2.onnx`（历史 V2） |

### 4. 主要实现文件

- `data/behavior/OnnxBehaviorRecognitionEngine.kt` — 模型加载、预处理、推理、softmax 与 V3.1 类别映射
- `data/behavior/BehaviorAnalyzer.kt` — 帧缓冲、并发推理控制与 Bitmap 回收
- `data/behavior/BehaviorSignalProcessor.kt` — 观察期、时间窗口与稳定状态输出
- `data/behavior/LearningContinuityStateMachine.kt` — 会话级连续性状态
- `data/behavior/BehaviorObservationHistory.kt` — 当前 Focus session 的节奏与统计历史
- `data/expression/ExpressionSessionManager.kt` — 在共享 CameraX pipeline 中接入表情和行为结果
- `ui/focus/FocusScreen.kt` — 学习状态辅助产品 UI

### 5. 调试采集与隐私

Debug 构建可在开发者工具中采集 `idle` 与 `visible_study` 目标域样本；该入口在 Release 中不可见。正常运行时：

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
