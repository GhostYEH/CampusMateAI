# HarmonyOS Motion System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 HarmonyOS 全部页面建立统一、可降级且经过构建验证的动效系统。

**Architecture:** 新增纯 ArkTS `MotionSpec` 作为统一数值策略，通过 `reduceMotion` 控制正常和低动态两套输出。`Index` 将该偏好传入主导航、公共页头和每个功能页面，各页面只在现有布局上增加入场、状态及按压反馈，不修改业务数据流。

**Tech Stack:** ArkTS、ArkUI、Hypium、Hvigor、HarmonyOS API 24（compatible API 21）

**Spec:** `docs/superpowers/specs/2026-08-16-harmony-motion-system-design.md`

## Global Constraints

- 必须保留当前工作区未提交的社区功能改动。
- 不新增第三方依赖，不修改 Harmony 端之外的平台。
- “减少动态效果”关闭位移、缩放、错峰和持续动画，只保留即时更新或不超过 80ms 的淡入。
- 不改变 API 请求、数据模型、权限、业务状态机和页面信息架构。

---

### Task 1: MotionSpec 策略

**Files:**
- Create: `harmony/entry/src/main/ets/ui/MotionSpec.ets`
- Create: `harmony/entry/src/test/ets/ui/MotionSpec.test.ets`
- Modify: `harmony/entry/src/test/List.test.ets`

**Interfaces:**
- Consumes: `reduceMotion: boolean`
- Produces: `MotionSpec.duration(reduceMotion, token)`、`MotionSpec.distance(reduceMotion, value)`、`MotionSpec.scale(reduceMotion, value)`、`MotionSpec.stagger(reduceMotion, index)`

- [ ] **Step 1: 写失败测试**

```ts
expect(MotionSpec.duration(false, MotionDuration.PAGE)).assertEqual(300);
expect(MotionSpec.duration(true, MotionDuration.PAGE)).assertEqual(0);
expect(MotionSpec.distance(true, 24)).assertEqual(0);
expect(MotionSpec.scale(true, 0.96)).assertEqual(1);
expect(MotionSpec.stagger(false, 3)).assertEqual(105);
expect(MotionSpec.stagger(true, 3)).assertEqual(0);
```

- [ ] **Step 2: 运行测试并确认因模块不存在而失败**

Run: `hvigorw.bat test --no-daemon`

Expected: FAIL，错误指向 `MotionSpec` 导入不存在。

- [ ] **Step 3: 实现最小策略类**

```ts
export enum MotionDuration { INSTANT = 80, PRESS = 150, STATE = 220, TAB = 260, PAGE = 300 }

export class MotionSpec {
  static duration(reduceMotion: boolean, value: MotionDuration): number { return reduceMotion ? 0 : value; }
  static fadeDuration(reduceMotion: boolean, value: MotionDuration): number { return reduceMotion ? 80 : value; }
  static distance(reduceMotion: boolean, value: number): number { return reduceMotion ? 0 : value; }
  static scale(reduceMotion: boolean, value: number): number { return reduceMotion ? 1 : value; }
  static stagger(reduceMotion: boolean, index: number): number { return reduceMotion ? 0 : Math.min(Math.max(index, 0), 3) * 35; }
}
```

- [ ] **Step 4: 运行测试并确认通过**

Run: `hvigorw.bat test --no-daemon`

Expected: PASS，新增策略测试与既有测试均无失败。

### Task 2: 导航与公共组件

**Files:**
- Modify: `harmony/entry/src/main/ets/pages/Index.ets`
- Modify: `harmony/entry/src/main/ets/ui/AppDock.ets`
- Modify: `harmony/entry/src/main/ets/ui/SecondaryHeader.ets`

**Interfaces:**
- Consumes: Task 1 的 `MotionSpec` 与根状态 `reduceMotion`
- Produces: 主 Tab、二级路由、底栏和返回按钮统一的动效行为

- [ ] **Step 1: 为 `AppDock` 和 `SecondaryHeader` 增加 `reduceMotion` Prop**

```ts
@Prop reduceMotion: boolean = false;
```

- [ ] **Step 2: 用 MotionSpec 替换公共组件硬编码参数**

```ts
.scale({ x: MotionSpec.scale(this.reduceMotion, 0.92), y: MotionSpec.scale(this.reduceMotion, 0.92) })
.animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
```

- [ ] **Step 3: 调整根页面转场并传递低动态偏好**

```ts
.animationDuration(MotionSpec.duration(this.reduceMotion, MotionDuration.TAB))
.transition(TransitionEffect.OPACITY
  .combine(TransitionEffect.translate({ x: MotionSpec.distance(this.reduceMotion, 24), y: 0 }))
  .animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
```

- [ ] **Step 4: 运行完整构建**

Run: `hvigorw.bat assembleApp --no-daemon`

Expected: BUILD SUCCESSFUL，无 Prop 或动画 API 编译错误。

### Task 3: 五个主页面

**Files:**
- Modify: `harmony/entry/src/main/ets/features/dashboard/DashboardPage.ets`
- Modify: `harmony/entry/src/main/ets/features/courses/CoursesPage.ets`
- Modify: `harmony/entry/src/main/ets/features/tasks/TasksPage.ets`
- Modify: `harmony/entry/src/main/ets/features/counselor/CounselorPage.ets`
- Modify: `harmony/entry/src/main/ets/features/profile/ProfilePage.ets`

**Interfaces:**
- Consumes: `@Prop reduceMotion` 与 MotionSpec
- Produces: 统一的首屏分组入场、按压和状态反馈

- [ ] **Step 1: 为所有主页面增加 `reduceMotion` 并由 Index 传入**

- [ ] **Step 2: 首页与个人中心接入最多四组首屏入场**

```ts
.transition(TransitionEffect.OPACITY
  .combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) }))
  .animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), delay: MotionSpec.stagger(this.reduceMotion, group), curve: Curve.EaseOut }))
```

- [ ] **Step 3: 课程、待办和 AI 助手统一列表/消息与状态反馈**

使用 `STATE` 时长处理筛选、完成状态、展开详情和发送状态；使用 `PRESS` 时长处理卡片和按钮按压。

- [ ] **Step 4: 运行完整构建**

Run: `hvigorw.bat assembleApp --no-daemon`

Expected: BUILD SUCCESSFUL，五个主页面全部通过 ArkTS 检查。

### Task 4: 全部二级页面

**Files:**
- Modify: `harmony/entry/src/main/ets/features/classrooms/ClassroomsPage.ets`
- Modify: `harmony/entry/src/main/ets/features/exams/ExamsPage.ets`
- Modify: `harmony/entry/src/main/ets/features/focus/FocusPage.ets`
- Modify: `harmony/entry/src/main/ets/features/lostfound/LostFoundPage.ets`
- Modify: `harmony/entry/src/main/ets/features/notifications/NotificationsPage.ets`
- Modify: `harmony/entry/src/main/ets/features/profile/AccountPage.ets`
- Modify: `harmony/entry/src/main/ets/features/profile/EduSystemPage.ets`
- Modify: `harmony/entry/src/main/ets/features/profile/PersonalHubPage.ets`
- Modify: `harmony/entry/src/main/ets/features/profile/SettingsPage.ets`
- Modify: `harmony/entry/src/main/ets/features/services/ServicesPage.ets`
- Modify: `harmony/entry/src/main/ets/features/v3/V3CorePage.ets`
- Modify: `harmony/entry/src/main/ets/features/v3/CommunityReferencePage.ets`

**Interfaces:**
- Consumes: `@Prop reduceMotion`、MotionSpec、统一的 SecondaryHeader
- Produces: 二级页面一致的内容入场、筛选、详情、表单和状态反馈

- [ ] **Step 1: 将 `reduceMotion` 贯穿所有二级页面与页头**

- [ ] **Step 2: 将既有硬编码动画替换为 MotionSpec**

- [ ] **Step 3: 为无反馈的高频交互补充按压和状态动画**

只修改已有卡片、按钮、筛选和详情容器的显示属性，不新增业务状态或循环定时器。

- [ ] **Step 4: 运行完整构建**

Run: `hvigorw.bat assembleApp --no-daemon`

Expected: BUILD SUCCESSFUL，全部二级页面通过 ArkTS 检查。

### Task 5: 最终验证与范围审计

**Files:**
- Verify: `harmony/entry/src/main/ets/**`
- Verify: `harmony/entry/src/test/**`

**Interfaces:**
- Consumes: 前四个任务的最终实现
- Produces: 可复现的测试、构建和差异证据

- [ ] **Step 1: 运行完整单元测试**

Run: `hvigorw.bat test --no-daemon`

Expected: PASS，0 failed。

- [ ] **Step 2: 运行完整应用构建**

Run: `hvigorw.bat assembleApp --no-daemon`

Expected: BUILD SUCCESSFUL，exit code 0。

- [ ] **Step 3: 检查差异范围**

Run: `git diff -- harmony/entry/src/main/ets harmony/entry/src/test docs/superpowers`

Expected: 仅包含动效系统、参数传递、测试与文档；社区业务逻辑差异保持不变。
