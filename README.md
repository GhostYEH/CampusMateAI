# 大学生校园事务智能陪伴助手 (Campus Companion)

一款面向大学生的移动端智能助手 Flutter 应用,解决校园通知分散、事务流程不清、学习状态难追踪、缺乏有温度的陪伴体验等问题。

> 计算机设计大赛参赛项目 · 第一阶段:高质量可运行前端原型(Mock 数据闭环)

## 核心功能

| 模块 | 说明 |
|------|------|
| 校园通知智能整理 | 粘贴通知原文 → 分步骤动态提取任务名/截止时间/材料/地点 → 人工修正 → 保存为待办 |
| 个人待办与截止提醒 | 今日/即将截止/已完成/全部/日历视图,优先级、倒计时、滑动操作、撤销删除 |
| AI 导员问答 | 流式回答、参考来源引用、快捷问题、建议操作、停止/重新生成、无资料时提示咨询辅导员 |
| 学习陪伴 | 学习计时、目标管理、Mock CNN 表情识别、多帧平滑、呼吸环状态指示、休息提醒 |
| 我的 | 用户信息、通知/提醒/权限设置、深色模式、减少动态效果、清除数据、隐私政策 |

## 科学边界

CNN 识别的是**可观察到的面部表情**,不进行心理诊断。界面文案使用:
- "系统观察到当前表情可能偏低落"
- "识别结果仅供辅助参考"
- "你好像有些疲惫,需要休息一下吗?"

禁止出现"检测出你患有焦虑症"等诊断性表述。疲劳状态结合连续学习时长、用户主观反馈和后续生理信号综合判断,不简单等同于 FER2013 表情类别。

## 技术栈

- **Flutter** + **Dart** (>=3.5.0)
- **Riverpod** 状态管理
- **go_router** 路由管理
- **Dio** 网络请求(预留)
- **shared_preferences** 本地存储
- **flutter_local_notifications** 本地提醒
- **camera** 摄像头(后续 CNN 接入预留)
- **equatable** 模型相等性
- **google_fonts** 字体

## 项目结构

```
lib/
  app/                    # 应用层
    design_system/        # Design System(颜色/字号/间距/圆角/阴影/动画)
    providers/            # Riverpod Providers(依赖注入)
    router/               # go_router 路由 + 底部导航
    theme/                # 主题(浅色/深色)
  core/                   # 基础设施
    utils/                # 工具(日期/ID 生成)
    widgets/              # 通用组件(卡片/进度环/分层动画/状态视图)
  data/
    models/               # 数据模型(User/Task/Notice/Chat/Expression/Study/Settings)
    services/             # 抽象服务接口
  features/               # Feature-first 业务模块
    home/                 # 首页
    notifications/        # 通知列表 + 智能整理
    tasks/                # 待办(列表 + 创建)
    counselor/            # AI 导员聊天
    study_companion/      # 学习陪伴
    expression_recognition/  # 表情识别(预留)
    profile/              # 我的
  mock/                   # Mock 数据与 Mock 服务实现
    mock_data/            # 真实中文 Mock 数据
    mock_services/        # Mock 服务 + 表情多帧平滑
```

## 抽象服务接口

UI 层通过 Riverpod Provider 注入服务,Mock 与真实实现可替换:

- `NotificationExtractionService` — 通知智能提取
- `TaskRepository` — 待办任务仓库
- `CounselorChatService` — AI 导员聊天
- `KnowledgeBaseService` — 校园知识库
- `StudySessionRepository` — 学习会话仓库
- `ExpressionRecognitionService` — 表情识别(预留 LiteRT / Native Camera 实现)
- `PermissionService` — 权限管理
- `AnalyticsService` — 埋点分析

## Design System

- **色彩**: 低饱和蓝紫色为主强调色,暖色表达截止/关怀/提醒;预留深色模式
- **字号**: 统一排版层级(display/title/subtitle/body/label/caption/overline)
- **间距**: 8pt 网格(edge=16, lg=12, md=8, sm=6, xs=4)
- **圆角**: xs=4 / sm=8 / md=12 / lg=16 / xl=24
- **阴影**: subtle / elevated / focused(低饱和、不堆叠)
- **动画**: base=280ms / fast=180ms / slow=420ms;曲线 emphasized / decelerate / gentleSpring / standard
- **减少动态效果**: 全局 `reduceMotionProvider`,开启时跳过 StaggeredEnter / 呼吸环等动画

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

后续预留:
- `LiteRtExpressionRecognitionService`(LiteRT 部署 CNN)
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
```

## 测试覆盖

共 117 个测试,覆盖:

| 类别 | 测试文件 | 说明 |
|------|----------|------|
| 数据模型 | `test/data/models/notice_test.dart` | 通知提取结果模型 |
| 工具类 | `test/core/utils/date_utils_test.dart` | 日期/截止时间计算 |
| Provider | `test/app/providers/app_providers_test.dart` | Riverpod 状态管理 |
| 任务仓库 | `test/mock/mock_services/mock_task_repository_test.dart` | 增删改查/恢复 |
| 表情平滑 | `test/mock/mock_services/expression_smoother_test.dart` | 多帧平滑/低置信度 |
| 建议冷却 | `test/mock/mock_services/suggestion_cooldown_test.dart` | 提醒冷却时间 |
| 首页 | `test/features/home/home_page_test.dart` | Widget 测试 |
| 通知整理 | `test/features/notifications/notification_extract_page_test.dart` | 完整流程 Widget 测试 |
| AI 导员 | `test/features/counselor/counselor_page_test.dart` | 聊天/流式/来源/操作 Widget 测试 |

## 前端设计 Skill

本项目使用 **`trae-remote-official:frontend-design:frontend-design`** Skill 指导页面设计,遵循其工作流程:
1. 确定设计方向(青年校园 / 智能温和 / 简洁现代)
2. 建立 Design System(颜色/字号/间距/圆角/阴影/动画)
3. 按 Feature 落地页面,避免模板式 UI
4. 动画服务于信息反馈,支持减少动态效果

## 质量指标

- `dart format lib test` — 通过
- `flutter analyze lib` — **No issues found!**
- `flutter test` — **117 tests passed**

## 已知限制与下一阶段

### 当前阶段(已完成)
- Flutter 前端原型,Mock 数据闭环
- 所有核心页面可交互、可演示
- 抽象服务接口 + Mock 实现
- 表情识别多帧平滑逻辑(前端模拟)
- 完整测试覆盖

### 下一阶段(待实现)
- **后端**: Python + FastAPI + PostgreSQL/MySQL + JWT 认证
- **RAG 校园知识库**: 向量数据库抽象接口已预留,待接入真实知识库
- **CNN 模型训练**: PyTorch + FER2013,对比自定义 CNN / ResNet18 / MobileNetV3-Small
- **LiteRT 部署**: `LiteRtExpressionRecognitionService` 实现
- **原生摄像头**: Platform Channel + Kotlin CameraX
- **本地提醒**: `flutter_local_notifications` 实际调度
- **深色模式**: 主题已预留,待完整适配
- **Golden Test**: 主要页面截图测试

## 项目规范

参见 [AGENTS.md](AGENTS.md)。
