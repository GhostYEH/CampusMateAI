# 大学生校园事务智能陪伴助手 (Campus Companion)

一款面向大学生的移动端智能助手 Flutter 应用,解决校园通知分散、事务流程不清、学习状态难追踪、缺乏有温度的陪伴体验等问题。

> 计算机设计大赛参赛项目 · 第二阶段:可构建、可持久化、可维护、适合比赛演示的 Flutter 应用

## 核心功能

| 模块 | 说明 |
|------|------|
| 校园通知智能整理 | 粘贴通知原文 → 分步骤动态提取任务名/截止时间/材料/地点 → 人工修正 → 保存为待办 |
| 个人待办与截止提醒 | 今日/即将截止/已完成/全部/日历视图,优先级、倒计时、滑动操作、撤销删除 |
| AI 导员问答 | 流式回答、参考来源引用、快捷问题、建议操作、停止/重新生成、无资料时提示咨询辅导员 |
| 学习陪伴 | 学习计时、目标管理、Mock CNN 表情识别、多帧平滑、呼吸环状态指示、休息提醒 |
| 我的 | 用户信息、通知/提醒/权限设置、深色模式、减少动态效果、恢复演示数据、清除数据、隐私政策 |

## 科学边界

CNN 识别的是**可观察到的面部表情**,不进行心理诊断。界面文案使用:
- "系统观察到当前表情可能偏低落"
- "识别结果仅供辅助参考"
- "你好像有些疲惫,需要休息一下吗?"

禁止出现"检测出你患有焦虑症"等诊断性表述。疲劳状态结合连续学习时长、用户主观反馈和后续生理信号综合判断,不简单等同于 FER2013 表情类别。

## 技术栈

- **Flutter** + **Dart** (>=3.5.0, Flutter >=3.22.0)
- **Riverpod** 状态管理(`flutter_riverpod` + `riverpod_annotation`)
- **go_router** 声明式路由
- **Dio** 网络请求(封装,当前 Mock)
- **shared_preferences** 本地持久化(JSON 序列化)
- **flutter_local_notifications** 本地提醒(预留调度)
- **camera** 摄像头(后续 CNN 接入预留)
- **equatable** 模型相等性
- **google_fonts** 字体
- **mocktail** 单元测试 Mock

## 项目结构

```
lib/
  app/                    # 应用层
    config/               # AppConfig(运行环境 / Mock 切换入口)
    design_system/        # Design System(颜色/字号/间距/圆角/阴影/动画)
    providers/            # Riverpod Providers(依赖抽象接口注入)
    router/               # go_router 路由 + 底部导航
    theme/                # 主题(浅色 / 深色 完整适配)
  core/                   # 跨 Feature 基础设施
    storage/              # 本地持久化(LocalStorage 抽象 + SharedPreferences 实现 + 各 Storage + DataPersistenceService)
    utils/                # 工具(日期 / ID 生成)
    widgets/              # 通用组件(卡片 / 进度环 / 分层动画 / 状态视图)
  data/
    models/               # 数据模型(User / Task / Notice / Chat / Expression / Study / Settings)
    services/             # 抽象服务接口 + LiteRT 占位实现
  features/               # Feature-first 业务模块
    home/                 # 首页
    notifications/        # 通知列表 + 智能整理
    tasks/                # 待办(列表 + 创建)
    counselor/            # AI 导员聊天
    study_companion/      # 学习陪伴
    profile/              # 我的
  mock/                   # Mock 数据与 Mock 服务实现
    mock_data/            # 真实中文 Mock 数据
    mock_services/        # Mock 服务 + 表情多帧平滑
```

## 抽象服务接口

UI 层通过 Riverpod Provider 注入服务,所有 Provider **依赖抽象接口**,Mock 与真实实现可替换:

- `NotificationExtractionService` — 通知智能提取
- `TaskRepository` — 待办任务仓库(含 `snapshot` / `restoreFrom` / `clearAll` / `resetToDemo`)
- `CounselorChatService` — AI 导员聊天
- `KnowledgeBaseService` — 校园知识库
- `StudySessionRepository` — 学习会话仓库(含 `historySnapshot` / `restoreHistoryFrom` / `clearHistory` / `resetToDemo`)
- `ExpressionRecognitionService` — 表情识别(预留 LiteRT / Native Camera 实现)
- `PermissionService` — 权限管理
- `AnalyticsService` — 埋点分析

通过 `AppConfig`(`appConfigProvider`)统一决定实现注入策略,后续切换真实后端时只需修改 `useMockBackend` 标记。

## 本地数据持久化

第一阶段任务、设置、学习记录与通知仅存内存,重启即丢;第二阶段已落地完整的持久化链路:

- `LocalStorage`(抽象)+ `SharedPreferencesLocalStorage`(实现)+ `JsonCodecHelper`(JSON 编解码)
- 类型化 Storage:`SettingsStorage` / `TaskStorage` / `StudyStorage` / `NoticeStorage`
- 统一编排服务 `DataPersistenceService`,负责启动加载(`loadAll`)、运行时保存(`saveSettings/saveTasks/saveStudyHistory/saveNotices`)、清除(`clearAllData`)与恢复演示(`restoreDemoData`)
- `main.dart` 在启动时初始化 SharedPreferences、构造仓储实例、注入 Provider、加载持久化设置
- `app.dart` 监听 `appSettingsProvider` / `taskListProvider` / `campusNoticesProvider` 变化,自动写回本地
- 个人中心提供"恢复演示数据"与"清除本地数据"入口,带二次确认对话框
- 损坏 JSON 自动降级为空数据,启动失败也不阻断应用

## Design System

- **色彩**: 低饱和青蓝色为主强调色(`#2F6486`),暖色(琥珀)表达截止/关怀/提醒;上下文感知 `AppColorScheme` 自动适配深色模式
- **字号**: 统一排版层级(display/title/subtitle/body/label/caption/overline)
- **间距**: 8pt 网格(edge=16, lg=12, md=8, sm=6, xs=4)
- **圆角**: xs=4 / sm=8 / md=12 / lg=16 / xl=24
- **阴影**: subtle / elevated / focused(低饱和、不堆叠)
- **动画**: base=280ms / fast=180ms / slow=420ms;曲线 emphasized / decelerate / gentleSpring / standard
- **减少动态效果**: 全局 `reduceMotionProvider`,开启时跳过 StaggeredEnter / 呼吸环等动画;设置同步到 Provider,无障碍支持

## 深色模式

第二阶段已完整适配:

- `AppTheme.dark()` 提供完整的深色 ThemeData(scaffold / colorScheme / card / button / input / chip / navBar / switch / slider / snackbar 等)
- `AppColorScheme` 通过 `BuildContext` 自动选择浅色/深色变体,通过 `context.appColors.xxx` 使用
- 通用组件(`AppCard` / `SectionHeader` / `EmptyStateView` / `ErrorStateView` 等)已迁移到上下文感知色板
- `MaterialApp.themeMode` 跟随 `appSettingsProvider.darkMode` 切换
- 个人中心提供深色模式开关

## 动态交互

- 页面进入分层出现动画(StaggeredEnter)
- 卡片淡入 + 位移
- 待办完成勾选 + 进度变化 + 列表重排
- 截止时间倒计时实时更新
- 通知提取分步骤处理过程(6 步动态反馈)
- AI 导员打字中动画 + 逐字流式输出 + 闪烁光标
- 学习计时器实时变化
- 呼吸环 / 波形状态指示器
- 表情识别结果平滑过渡(多帧平滑)
- 空状态/加载/错误/成功完整反馈
- 按钮按下/禁用/加载/成功多状态
- 列表筛选/排序/搜索实时反馈

## 比赛演示模式

在"我的 → 比赛演示模式"中开启,提供完整数据链路:

1. 首页已有数条校园通知
2. 粘贴通知 → 动态提取 → 保存为待办
3. 首页任务进度更新
4. 向 AI 导员询问任务 → 引用模拟知识库回答
5. 开启学习陪伴 → 模拟 CNN 识别稳定表情
6. AI 导员结合任务和表情给出轻量回应
7. 完成任务 → 首页进度更新 + 完成反馈

支持"恢复演示数据"快速重置待办与学习记录为默认 MockData,带二次确认。

## CNN 接口设计(预留)

```dart
enum ExpressionLabel {
  happy, neutral, sad, angry, fear, surprise, disgust, unknown, noFace,
}

class ExpressionResult {
  final ExpressionLabel label;
  final double confidence;
  final Map<ExpressionLabel, double> probabilities;
  final DateTime timestamp;
  final bool isStable;
  final String modelVersion;
}

abstract interface class ExpressionRecognitionService {
  Stream<ExpressionResult> get results;
  Future<void> initialize();
  Future<void> start();
  Future<void> pause();
  Future<void> stop();
  Future<void> dispose();
}
```

当前实现 `MockExpressionRecognitionService`,包含:
- 多帧概率平滑(指数加权)
- 置信度阈值过滤
- 状态持续时间判断
- 建议冷却时间
- 低置信度显示"暂时无法稳定判断当前表情",且**不**触发情绪安慰

后续预留:
- `LiteRtExpressionRecognitionService`(LiteRT 部署 CNN,接口已预留,内部方法暂抛 UnimplementedError)
- `NativeCameraExpressionRecognitionService`(Platform Channel + CameraX)

## 运行

```bash
# 安装依赖
flutter pub get

# 运行(默认 Mock 模式)
flutter run

# 格式化
dart format lib test

# 静态检查
flutter analyze

# 测试
flutter test

# 构建 Android APK(debug)
flutter build apk --debug

# 构建 Web
flutter build web --release
```

## 测试覆盖

共 187 个测试,覆盖:

| 类别 | 测试文件 | 说明 |
|------|----------|------|
| 数据模型 | `test/data/models/notice_test.dart` | 通知提取结果模型 |
| 工具类 | `test/core/utils/date_utils_test.dart` | 日期/截止时间计算 |
| Provider | `test/app/providers/app_providers_test.dart` | Riverpod 状态管理 / 任务派生 Provider |
| 任务仓库 | `test/mock/mock_services/mock_task_repository_test.dart` | 增删改查/恢复 |
| 表情平滑 | `test/mock/mock_services/expression_smoother_test.dart` | 多帧平滑/低置信度 |
| 建议冷却 | `test/mock/mock_services/suggestion_cooldown_test.dart` | 提醒冷却时间 |
| 首页 | `test/features/home/home_page_test.dart` | Widget 测试 |
| 通知整理 | `test/features/notifications/notification_extract_page_test.dart` | 完整流程 Widget 测试 |
| AI 导员 | `test/features/counselor/counselor_page_test.dart` | 聊天/流式/来源/操作 Widget 测试 |
| 本地存储 | `test/core/storage/local_storage_test.dart` | SharedPreferencesLocalStorage / JsonCodecHelper |
| Storage 类 | `test/core/storage/storage_test.dart` | Settings/Task/Study/Notice Storage 往返与损坏降级 |
| 持久化服务 | `test/core/storage/data_persistence_service_test.dart` | loadAll/save/clearAllData/restoreDemoData 全链路 |
| 主题与色板 | `test/app/theme/app_theme_test.dart` | AppTheme.light/dark + AppColorScheme + expressionColor |
| App 集成 | `test/app/app_test.dart` | AppConfig / Provider 注入 / 深色模式 ThemeMode / 自动持久化监听 |

## 持续集成

[`.github/workflows/flutter_ci.yml`](.github/workflows/flutter_ci.yml) 在 push / PR 到 `main` / `master` 时触发:

1. **analyze-and-test**: 安装依赖 → `dart format --set-exit-if-changed` → `flutter analyze` → `flutter test`
2. **build-android**: 构建调试 APK 并上传为 artifact(依赖 1 通过)
3. **build-web**: 构建 Web release 并上传为 artifact(依赖 1 通过)

## 前端设计 Skill

本项目使用 **`trae-remote-official:frontend-design:frontend-design`** Skill 指导页面设计,遵循其工作流程:
1. 确定设计方向(青年校园 / 智能温和 / 简洁现代)
2. 建立 Design System(颜色/字号/间距/圆角/阴影/动画)
3. 按 Feature 落地页面,避免模板式 UI
4. 动画服务于信息反馈,支持减少动态效果

## 质量指标

- `dart format lib test` — 通过
- `flutter analyze` — No issues found
- `flutter test` — 187 tests passed
- Android APK 构建 — 通过(core library desugaring 已启用)
- Web 构建 — 通过

## 已知限制与下一阶段

### 当前阶段(已完成)
- Flutter 应用工程化(Android / Web 平台工程就绪,可构建)
- Mock 数据闭环 + 完整交互
- 抽象服务接口 + Mock 实现彻底解耦(Provider 依赖抽象,通过 AppConfig 切换)
- SharedPreferences 本地持久化 + 损坏数据降级
- 深色模式完整适配(主题 / 色板 / 通用组件 / 个人中心开关)
- 比赛演示模式稳定可重复(含"恢复演示数据")
- 页面文件拆分(首页 / 通知整理 等)
- 自动化测试与 CI

### 下一阶段(待实现)
- **后端**: Python + FastAPI + PostgreSQL + JWT 认证
- **RAG 校园知识库**: 向量数据库抽象接口已预留,待接入真实知识库
- **CNN 模型训练**: PyTorch + FER2013,对比自定义 CNN / ResNet18 / MobileNetV3-Small
- **LiteRT 部署**: `LiteRtExpressionRecognitionService` 真实实现
- **原生摄像头**: Platform Channel + Kotlin CameraX
- **本地提醒调度**: `flutter_local_notifications` 真实定时推送
- **Golden Test**: 主要页面截图测试

## 项目规范

参见 [AGENTS.md](AGENTS.md)。
