# 微信小程序安卓界面对齐实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让微信小程序现有八个页面在视觉层级与交互反馈上对齐当前安卓学生端，同时保持安卓代码零修改。

**Architecture:** 以 `app.wxss` 和自定义底栏作为全局设计系统层；每个页面保留原 TypeScript 数据与业务逻辑，仅在需要补充展示数据或入口反馈时做小范围修改。通过静态视觉契约测试、TypeScript 与处理器检查防止回归。

**Tech Stack:** 原生微信小程序、WXML、WXSS、TypeScript、Node.js 静态契约测试。

## Global Constraints

- 只修改 `wx/` 以及本次设计/计划文档，不修改 `android/`。
- 安卓当前工作区和实机画面是唯一视觉基准。
- 不新增小程序当前没有承载能力的安卓业务模块。
- 保留 Mock/真实后端、深色模式和减少动态效果。

---

### Task 1: 视觉契约与全局设计系统

**Files:**
- Create: `wx/scripts/check_android_parity.js`
- Modify: `wx/package.json`
- Modify: `wx/miniprogram/app.wxss`
- Modify: `wx/miniprogram/custom-tab-bar/index.wxss`

- [ ] 先编写断言安卓主色、全局圆角、浮动底栏和五个页面关键骨架的失败测试。
- [ ] 运行测试并确认因旧青蓝令牌与旧页面结构失败。
- [ ] 更新全局令牌、公共控件与浮动底栏。
- [ ] 运行测试确认全局契约通过。

### Task 2: 首页与课程页

**Files:**
- Modify: `wx/miniprogram/pages/index/index.wxml`
- Modify: `wx/miniprogram/pages/index/index.wxss`
- Modify: `wx/miniprogram/pages/index/index.ts`
- Modify: `wx/miniprogram/pages/courses/courses.wxml`
- Modify: `wx/miniprogram/pages/courses/courses.wxss`
- Modify: `wx/miniprogram/pages/courses/courses.ts`

- [ ] 对齐首页安卓模块顺序、横幅、快捷入口、课程与统计卡。
- [ ] 对齐课程页下一节课、周日期条、统计、筛选和课程列表。
- [ ] 运行视觉契约与类型检查。

### Task 3: 待办与 AI 校园助手

**Files:**
- Modify: `wx/miniprogram/pages/tasks/tasks.wxml`
- Modify: `wx/miniprogram/pages/tasks/tasks.wxss`
- Modify: `wx/miniprogram/pages/tasks/tasks.ts`
- Modify: `wx/miniprogram/pages/counselor/counselor.wxml`
- Modify: `wx/miniprogram/pages/counselor/counselor.wxss`

- [ ] 对齐待办汇总、日期、筛选、智能聚焦、列表和新建面板。
- [ ] 对齐助手品牌卡、建议问题、对话区和输入区。
- [ ] 运行视觉契约、处理器检查和类型检查。

### Task 4: 我的与二级页面

**Files:**
- Modify: `wx/miniprogram/pages/profile/profile.wxml`
- Modify: `wx/miniprogram/pages/profile/profile.wxss`
- Modify: `wx/miniprogram/pages/profile/profile.ts`
- Modify: `wx/miniprogram/pages/login/login.wxml`
- Modify: `wx/miniprogram/pages/login/login.wxss`
- Modify: `wx/miniprogram/pages/notices/notices.wxss`
- Modify: `wx/miniprogram/pages/study/study.wxss`
- Modify: `wx/miniprogram/components/campus-header/campus-header.wxss`

- [ ] 对齐我的身份头图、快捷入口、服务列表与设置面板。
- [ ] 统一登录、通知、专注页和二级标题栏。
- [ ] 运行全部静态与类型验证。

### Task 5: 视觉 QA 与路径保护

**Files:**
- Modify: `design-qa.md`

- [ ] 尝试使用微信开发者工具构建和截图。
- [ ] 对照同状态安卓截图，修复 P0/P1/P2 可见差异。
- [ ] 运行完整验证命令。
- [ ] 检查本次变更路径，确认没有新增安卓差异。
