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

## Focus 架构与生命周期

`ExpressionSessionManager` 是 Activity-owned 的专注会话协调器。表情识别与行为识别共用一条 `FocusCameraPipeline`，不为行为识别启动第二个摄像头。CameraX 只有在“辅助开启 + 摄像头权限 + 计时运行 + 页面可见 + App 在前台”且模式为 `FOCUS` 时运行；暂停、离开页面或生命周期结束时会解绑/暂停 camera use case。

`attachLifecycle` / `detachLifecycle` 与 `attachPreview` / `detachPreview` 分别管理生命周期和预览；`release()` 会取消结果、状态和行为 collector jobs，解绑并释放 CameraX pipeline、行为 analyzer、表情服务和模型资源。

## 本地行为识别演进与学习状态辅助

行为识别是设备端辅助观察，不是专注度、心理状态或学习效果判断。当前模型演进如下：

| 版本 | 输出类别 | 模型 | 用途 |
|------|----------|------|------|
| V1 | `READING` / `WRITING` | `assets/models/behavior/rgb_resnet18.onnx` | 研究基线，识别阅读与书写 |
| V2 | `READING` / `WRITING` / `PHONE_USE` | `assets/models/behavior/rgb_resnet18_v2.onnx` | 扩展手机使用类别，保留回滚路径 |
| V3.2 | `IDLE` / `VISIBLE_STUDY` | `assets/models/behavior/campusmate_visible_study_v32.onnx` | 无人物 ROI 或 V3.4 不可用时的安全回退 |
| V3.4 | `READING` / `WRITING` / `PHONE_USE` / `IDLE` | `assets/models/behavior/campusmate_behavior_v34.onnx` | 当前单帧主模型，在人物 ROI 上运行 |
| V4 TSM | 上述类别 + `COMPUTER` | `assets/models/behavior/campusmate_tsm_mobilenetv2_v4.onnx` | 8 帧低频时序确认，与 V3.4 融合 |

当前默认使用 V3.4 单帧模型与 V4 TSM 时序模型的混合链路。历史 ONNX 文件都保留，因为目前是科研/开发阶段，需要比较模型演进、保证实验可复现并提供 V3.2 回退。

### V1.1 工程优化

V1.1 延续 V1 的 READ/WRITE 语义，但完善了共享 CameraX pipeline、异步单线程推理、16 帧滑动窗口、推理 busy 时不重复调度、Bitmap ownership/recycle 和 Focus 生命周期释放。UI 主线程只消费 Flow 结果，不执行 ONNX 推理。

### V3.4 + V4 产品语义与数据流

V3.4 对最新采样图片识别 `READING`、`WRITING`、`PHONE_USE` 和 `IDLE`。V4 TSM 从连续相机流中保留最近 8 张采样图片，仅在低置信度、类别变化、手机交互或周期确认时运行，并补充 `COMPUTER` 时序类别。

当人物 ROI 暂时不可用或 V3.4 加载失败时，系统回退到 V3.2 二分类。V3.2 的 `IDLE / VISIBLE_STUDY` 与 V4 标签空间不兼容，因此回退结果不会参与 TSM 融合，并会清空此前的时序证据。

数据流为：

```
CameraX
→ FocusCameraPipeline / CameraFrame
→ BehaviorAnalyzer（400 ms 采样与单线程推理调度）
→ HybridBehaviorRecognitionEngine
   ├─ OnnxBehaviorRecognitionEngine（V3.4 单帧；必要时回退 V3.2）
   └─ OnnxTsmBehaviorRecognitionEngine（最近 8 帧、按条件低频运行）
→ BehaviorHybridPolicy（仅融合标签兼容的 V3.4 + V4 输出）
→ BehaviorPredictionTemporalSmoother（EMA 概率平滑）
→ BehaviorSignalProcessor（启动观察、稳定判定）
→ LearningContinuityStateMachine（会话级连续性）
→ BehaviorObservationHistory（最近 5 分钟节奏统计）
→ FocusScreen（学习状态、节奏与本次观察摘要）
```

稳定结果会映射为 `OBSERVING`、`STUDYING`、`THINKING_OR_ADJUSTING` 和 `PAUSED`。学习中短暂出现 `IDLE` 时，前 8 秒仍保留学习状态，8～20 秒显示“短暂思考或调整中”，超过 20 秒才进入“暂时停顿”。`BehaviorSignalProcessor` 负责观察期、时间窗和稳定判定；`LearningContinuityStateMachine` 只改变产品层连续性，不改变底层模型标签。

`BehaviorObservationHistory` 是当前 Focus session 的内存历史，按最近 5 分钟裁剪统计学习、暂停、最长连续学习和 meaningful switch；`FocusScreen` 通过 `behaviorObservation` Flow 显示学习节奏卡片和本次观察摘要。

### V3.2 回退

`BehaviorModelSelection` 只有在 V3.4 可用且人物 ROI 有效时选择 V3.4，否则自动使用 V3.2。需要进行受控回滚时，可在调用 `select` 时传入：

```kotlin
enableV34 = false
```

混合引擎检测到 V3.2 或模型不可用状态时会绕过 TSM 并清空时序缓存，恢复 V3.4 后需要重新积累 8 张兼容帧。

### 主要实现文件

- `data/behavior/OnnxBehaviorRecognitionEngine.kt` — 模型加载、预处理、推理、softmax 与版本类别映射
- `data/behavior/HybridBehaviorRecognitionEngine.kt` — V3.4 单帧与 V4 TSM 调度、兼容性保护和结果融合
- `data/behavior/OnnxTsmBehaviorRecognitionEngine.kt` — 8 帧 TSM 模型加载与推理
- `data/behavior/BehaviorAnalyzer.kt` — 16 帧缓冲、并发推理控制、异常恢复与 Bitmap 回收
- `data/behavior/BehaviorSignalProcessor.kt` — 观察期、时间窗口与稳定状态输出
- `data/behavior/LearningContinuityStateMachine.kt` — 会话级连续性状态
- `data/behavior/BehaviorObservationHistory.kt` — 最近 5 分钟 Focus session 节奏历史
- `data/expression/ExpressionSessionManager.kt` — 共享 CameraX pipeline、collector jobs 与生命周期释放
- `ui/screens/focus/FocusScreen.kt` — 学习状态、节奏与开发者工具 UI

### 调试采集与隐私边界

Debug 构建可在专注页的开发者工具中采集 `idle` 与 `visible_study` 目标域样本；界面和 exporter 都由 `BuildConfig.DEBUG` 守门，Release 构建无法通过该入口开启图片采集。正常运行时：

- 摄像头图像只在设备端预处理和 ONNX 推理
- 不上传服务器、不写原始图像日志
- 默认不保存原始实时摄像头画面
- Debug 导出有 24 张图片、24 条待写预测、512 KB CSV、每个 session 180 张图片且每个标签最多 8 个 session 的上限；长期开发采集仍应定期清理 app-private debug/dataset 目录

详见专项研究文档：[`../docs/behavior-recognition.md`](../docs/behavior-recognition.md)

## 运行要求

- Android Studio Hedgehog (2023.1.1) 或更高版本
- JDK 21（项目使用 `android/.tools/jdk21-full/jdk-21.0.12+8`；JVM target 仍为 17）
- Android SDK 34
- 模拟器或 Android 8.0+ 真机

## 更多信息

- 项目规范: 参见仓库根目录 [`AGENTS.md`](../AGENTS.md)
- 后端 API: 参见 [`backend/README.md`](../backend/README.md)
- 表情识别训练: 参见 [`ml/expression_recognition/README.md`](../ml/expression_recognition/README.md)
