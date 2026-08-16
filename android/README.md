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

## 本地动作识别

专注自习页面已接入本地动作识别（行为识别），与表情识别共享同一 CameraX pipeline。

### 1. 当前能力

当前 Android 专注模式动作识别部署：

- **READING**：阅读
- **WRITING**：书写

后续候选类别（**尚未部署**）：

- `phone_use`
- `away`
- `resting`

### 2. Android 数据流

```
CameraX
→ CameraFrame
→ BehaviorAnalyzer（帧缓冲 + 单线程推理调度）
→ OnnxBehaviorRecognitionEngine
→ ResNet18 ONNX（本地推理）
→ BehaviorPrediction（READING / WRITING 概率）
→ ExpressionSessionManager
→ BehaviorSignalProcessor → FocusSupervisor
→ 专注辅助状态系统（focusState）
```

- 动作识别与已有表情识别共享现有 CameraX pipeline，**不额外启动第二个摄像头**
- ONNX 推理全部在 Android 本地完成

### 3. 主要实现文件

- `data/behavior/OnnxBehaviorRecognitionEngine.kt` — ONNX 模型加载、预处理、推理、softmax、类别映射
- `data/behavior/BehaviorModelMath.kt` — 稳定 softmax 与输出后处理
- `data/behavior/BehaviorAnalyzer.kt` — 帧缓冲、并发推理控制、Bitmap 回收
- `data/behavior/BehaviorRecognitionEngine.kt` — 引擎接口与 NoOp 实现
- `data/expression/ExpressionSessionManager.kt` — 将动作识别接入专注模式、共享 CameraX pipeline
- `assets/models/behavior/rgb_resnet18.onnx` — 部署模型

### 4. 当前部署模型

| 项 | 值 |
|------|------|
| Backbone | ResNet18 |
| Modality | RGB |
| Input | 224 × 224 |
| Runtime | ONNX Runtime Android |
| Output | READ / WRITE |

当前 Android v1 只部署 RGB 模型（未部署 Pose，未部署 RGB + Pose 融合）。

### 5. 隐私

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
