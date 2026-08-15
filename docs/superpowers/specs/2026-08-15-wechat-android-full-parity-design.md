# 微信小程序与安卓端全量等价迁移设计

## 目标

以当前安卓学生端为唯一产品、视觉、动效与接口行为基准，重构微信小程序的全部学生可达页面。最终小程序应具备相同的信息层级、主要交互、加载与错误状态，并默认连接本机正在运行的真实后端。

## 约束

- 不修改 `android/` 下的任何文件。
- 保留已经完成的微信登录页视觉结果，仅调整其真实后端初始化所必需的数据配置。
- 微信端使用原生 WXML、WXSS、TypeScript 与自定义 tab bar，不引入跨端框架。
- 不用静态截图伪装页面；控件、导航、表单和数据状态必须可操作。
- 安卓 Compose 源码与运行中安卓模拟器截图发生差异时，以运行中版本为最终视觉基准，并用源码解释组件状态。

## 路由范围

### 一级页面

| 安卓路由 | 微信页面 | 说明 |
| --- | --- | --- |
| `home` | `pages/index/index` | 首页仪表盘 |
| `courses` | `pages/courses/courses` | 课程 |
| `tasks` | `pages/tasks/tasks` | 待办 |
| `counselor` | `pages/counselor/counselor` | AI 校园助手 |
| `profile` | `pages/profile/profile` | 我的 |

### 首页与校园服务

| 安卓路由 | 微信目标页面 |
| --- | --- |
| `exams` | `pages/exams/exams` |
| `exam_detail/{examId}` | `pages/exam-detail/exam-detail` |
| `exam_edit/{examId}` | `pages/exam-edit/exam-edit` |
| `classrooms` | `pages/classrooms/classrooms` |
| `community` | `pages/community/community` |
| `focus?taskId={taskId}` | `pages/focus/focus` |
| `lostfound` | `pages/lostfound/lostfound` |
| `lostfound_publish` | `pages/lostfound-publish/lostfound-publish` |
| `lostfound_detail/{itemId}` | `pages/lostfound-detail/lostfound-detail` |
| `lostfound_mine` | `pages/lostfound-mine/lostfound-mine` |
| `university` | `pages/university/university` |
| `academic` | `pages/academic/academic` |
| `service_form/{kind}` | `pages/service-form/service-form` |

### 任务与通知

| 安卓路由 | 微信目标页面 |
| --- | --- |
| `task_calendar` | `pages/task-calendar/task-calendar` |
| `task_detail/{taskId}` | `pages/task-detail/task-detail` |
| `notifications` | `pages/notices/notices` |
| `campus-news` | `pages/campus-news/campus-news` |
| `campus-news-detail/{newsId}` | `pages/campus-news-detail/campus-news-detail` |

### 个人中心与集成

| 安卓路由 | 微信目标页面 |
| --- | --- |
| `settings` | `pages/settings/settings` |
| `help-feedback` | `pages/help-feedback/help-feedback` |
| `notification-settings` | `pages/notification-settings/notification-settings` |
| `chaoxing` | `pages/chaoxing/chaoxing` |
| `expression-contribution` | `pages/expression-contribution/expression-contribution` |
| `account` | `pages/account/account` |
| `files` / `activities` / `favorites` | `pages/personal-hub/personal-hub`，用查询参数切换区段 |

## 共享界面架构

微信端新增并统一使用以下页面级构件：

1. `secondary-nav`：状态栏安全区、返回按钮、居中标题，对齐安卓 `StickySecondaryNavigation`。
2. `section-card`：安卓白色大圆角内容卡，对齐边距、圆角、描边与阴影。
3. `state-view`：加载、空状态、错误状态和重试动作。
4. `form-field`：文本、选择、日期、开关与只读信息行。
5. `status-chip`：课程、考试、任务和服务状态标签。
6. `app-icon`：使用项目真实图标资产，不使用字符或临时 CSS 图形替代。

全局样式只提供令牌和明确前缀的共享类，页面私有类全部带页面或组件前缀，避免登录页曾出现的全局类名污染。

## 视觉规范

- 页面背景、主色、文字色、卡片色、分隔线和状态色从安卓 `ui/theme` 与页面 Compose 常量映射。
- 以 375/390/402 逻辑宽度分别检查，小程序截图与安卓截图按可视区域归一化后比较。
- 一级页面保留安卓悬浮底部 Dock；二级页面隐藏 Dock 并显示粘性返回导航。
- 字号、行高、左右 24dp 主边距、卡片圆角、图标槽尺寸和触控高度逐项映射，不通过整体缩放模拟。
- 首页必须包含安卓的五个快捷入口、课程双栏卡、学习总览、近期截止和后续校园动态内容。

## 动效规范

- 一级 tab 切换使用淡入与水平位移，时长映射安卓 `AppNavHost` 的 220–300ms。
- 二级页面进入与返回分别使用正向、反向水平位移与淡入淡出。
- 卡片首次出现沿用安卓 `enterAnimation` 的分段延迟；减少动态效果设置开启时全部禁用。
- 按压反馈、焦点、加载指示器、轮播分页和表单状态必须有对应动效，但不增加安卓端不存在的装饰动画。

## 真实后端与数据架构

- 开发默认地址为 `http://192.168.1.14:8000`，请求层统一追加 `/api/v1`。
- 默认 `mockMode` 设为 `false`，清理“空地址即进入 Mock”的产品路径；Mock 仅保留为显式开发开关。
- 登录、access token、refresh token、401 自动续期与会话过期回登录页的行为与安卓一致。
- 首页、课程、待办、通知和 AI 助手优先复用现有真实接口。
- 考试、空教室、专注、失物招领、校园动态、个人中心与集成页面按安卓 `ApiService` 契约补齐微信仓库方法和类型。
- 页面禁止静默回退到演示数据。接口失败时展示错误和重试；部分数据失败时保留已成功区域并显示局部提示。

## 错误与边界状态

- 401：尝试刷新一次；失败后清理会话并回登录页。
- 网络不可达或超时：保留当前页面结构，展示可重试状态。
- 空列表：使用与安卓一致的空状态文案和主操作。
- 表单校验：提交前显示字段级提示；服务端错误显示在表单顶部或对应字段。
- 后端不支持的安卓能力不得用假成功替代，应展示真实不可用状态并保留返回路径。

## 实施顺序

1. 共享令牌、二级导航、底部 Dock、图标与请求层。
2. 首页与五个一级页面。
3. 考试、空教室、社区、专注和失物招领。
4. 任务详情/日历、通知/校园动态详情。
5. 个人中心、设置、账号、学习通与个人内容中心。
6. 全量真实接口联调与错误状态。
7. 微信官方 CLI 预览编译、GUI 运行检查和逐页双模拟器视觉验收。

## 验收标准

- `android/` 工作区差异保持不变，不产生本任务新增修改。
- 微信 TypeScript 检查与官方 `preview` 编译成功。
- 真实后端健康检查、远程登录、课程、待办和通知请求有运行时证据。
- 每个一级页面与所有可达二级页面均能从 UI 导航进入并正确返回。
- 每个页面至少完成一次同状态、相近视口的安卓/微信并排截图比较。
- 不存在明显的布局溢出、裁切、错误间距、错误字号、错误圆角、缺失图标、静态假控件或 Mock 数据回退。

