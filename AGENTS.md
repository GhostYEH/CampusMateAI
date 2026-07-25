# AGENTS.md — 大学生校园事务智能陪伴助手 项目长期规范

本文件是本项目所有协作者(人类开发者与 AI Agent)必须遵守的长期规范。任何对仓库进行修改的 Agent 在动手前必须完整阅读本文件。

---

## 1. 项目定位

- 面向大学生的移动端智能陪伴助手,参赛计算机设计大赛。
- 核心能力: 校园通知智能整理、个人待办与截止提醒、AI 导员问答(基于本校知识库)、基于 CNN 的面部表情识别、学习状态记录与轻量陪伴。
- 当前阶段: **第一阶段 — 高质量可运行前端原型**(Mock 业务闭环)。
- 后续阶段: 后端(FastAPI + RAG)、CNN 训练与 LiteRT 部署。

## 2. 强制规范

### 2.1 必须使用前端设计 Skill
- 任何涉及 UI / 页面 / 组件的设计与实现,必须先参考 `trae-remote-official:frontend-design:frontend-design` Skill 的设计哲学。
- 设计关键词: 青年校园、智能但不冰冷、温和陪伴、简洁现代、低饱和青蓝色为主、暖色点缀、清晰信息层级、有节制的动效。
- 禁止: 紫色渐变白底、满屏玻璃拟态、堆叠阴影、所有内容都变成相同矩形卡片、AI slop 通用美学。

### 2.2 页面不能只是静态表单
- 必须包含: 分层进入动画、卡片淡入位移、状态切换过渡、加载/空/错误/成功反馈、按钮多状态、列表实时筛选反馈。
- 动画必须服务于信息与操作反馈,不为动画而动画。
- 支持减少动态效果设置(无障碍)。

### 2.3 不允许粗糙模板式 UI
- 不允许为赶进度生成 Lorem Ipsum 或无意义占位文本。
- 中文 Mock 数据必须自然、真实、贴近校园场景。
- 大型组件必须拆分,命名统一,避免过度抽象。

### 2.4 接口优先,Mock 可替换
- UI 层不得直接依赖写死的 Mock 数据,必须通过抽象接口 + 依赖注入。
- 真实实现与 Mock 实现必须可替换。
- 当前所有后端、知识库、CNN 能力必须明确标注 Mock 模式,不得伪造真实结果。

## 3. 科学边界(强制)

CNN 识别的是**可观察到的面部表情**,不是心理诊断。代码与文案中禁止出现:
- "检测出你患有焦虑症"
- "你现在一定很难过"
- "AI 已确认你的心理状态"

应使用谨慎表达:
- "系统观察到当前表情可能偏低落"
- "识别结果仅供辅助参考"
- "你好像有些疲惫,需要休息一下吗?"
- "最近任务是不是有些多?我们可以一起整理。"

疲劳状态 ≠ FER2013 表情类别。疲劳判断需结合: 连续学习时长、用户主动填写的学习感受、后续闭眼/眨眼/头部姿态信号。

情绪陪伴只提供日常辅助,不进行疾病诊断,不替代专业心理咨询。

## 4. 技术栈

- 应用主体: Flutter / Dart
- 状态管理: Riverpod (`flutter_riverpod`)
- 路由: `go_router`
- 网络: `Dio`(封装,当前 Mock)
- 本地数据: 当前内存 + `shared_preferences`(后续可迁移 Drift/SQLite)
- 本地提醒: `flutter_local_notifications`
- 摄像头: `camera`(后续 Platform Channel 接 Kotlin CameraX)
- CNN 部署: 后续 LiteRT
- 后端(预留): Python / FastAPI / PostgreSQL / RAG / JWT
- CNN 训练(预留): PyTorch / torchvision / FER2013 / 对比 ResNet18、MobileNetV3-Small

## 5. 代码架构(Feature-first)

```
lib/
  app/                 # 应用入口、路由、主题、设计系统
  core/                # 跨Feature通用: 常量、错误、网络、存储、工具、通用组件
  features/            # 按业务Feature组织,每个含 data/domain/presentation/widgets/providers
  data/                # 全局数据模型、仓库、服务抽象
  mock/                # Mock数据与Mock服务实现
```

抽象接口(必须存在,UI 通过 Provider 注入):
- `NotificationExtractionService`
- `TaskRepository`
- `CounselorChatService`
- `KnowledgeBaseService`
- `StudySessionRepository`
- `ExpressionRecognitionService`
- `PermissionService`
- `AnalyticsService`

## 6. CNN 接入接口(强制数据结构)

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

当前实现 `MockExpressionRecognitionService`,必须包含: 多帧概率平滑、置信度阈值、状态持续时间判断、提醒冷却时间。
预留 `LiteRtExpressionRecognitionService` / `NativeCameraExpressionRecognitionService`。

低置信度显示: "暂时无法稳定判断当前表情。" 且**不得**触发情绪安慰。

## 7. 质量要求

- 项目必须可运行(`flutter run`)。
- 通过 `flutter analyze`。
- 核心单元测试通过。
- 页面无明显溢出,适配常见手机尺寸。
- 键盘弹出不遮挡关键输入。
- 处理加载/空/错误/离线状态。
- 防重复点击、异步可取消。
- 不写死密钥,敏感配置用环境变量。
- 列表使用懒加载组件。
- 动画不影响性能。

## 8. 测试要求

至少覆盖: 通知提取模型、待办增删完成恢复、截止时间计算、多帧表情平滑、低置信度处理、提醒冷却、Provider、首页/通知整理/AI导员 Widget 测试。

## 9. 比赛演示模式

设置中可开启"比赛演示模式",提供完整数据链路: 首页通知 → 粘贴通知 → 智能提取 → 保存待办 → 首页进度更新 → 询问 AI 导员 → 引用模拟知识库 → 开启学习陪伴 → Mock CNN 稳定表情 → AI 导员轻量回应 → 完成任务 → 首页反馈。演示数据必须真实自然。

## 10. 工作纪律

- 不删除已有有效代码。
- 不覆盖用户未要求修改的重要配置。
- 遇到合理小问题自行决定,不频繁停下询问。
- 发现技术风险记录在 README,但继续完成可行部分。
- 不留下大量 TODO 假装完成,不虚构后端/知识库/CNN 真实结果。
