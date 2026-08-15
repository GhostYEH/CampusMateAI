# 微信小程序与安卓端全量等价迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将微信小程序全部学生页面迁移为与安卓端视觉、动效、交互和真实后端行为等价的实现。

**Architecture:** 保留现有五个 tab 页面，将安卓二级路由按学业、校园、任务通知、个人中心四个领域拆成原生微信页面；共享二级导航、状态视图和视觉令牌。请求层统一连接真实后端并扩展领域接口，页面只消费类型化仓库方法。

**Tech Stack:** 微信小程序 WXML/WXSS/TypeScript、微信开发者工具官方 CLI、现有 FastAPI `/api/v1`、PowerShell/Node 静态契约检查。

**Spec:** `docs/superpowers/specs/2026-08-15-wechat-android-full-parity-design.md`

## Global Constraints

- 不修改 `android/` 下的任何文件。
- 微信页面必须使用原生组件和真实项目图标资产，不使用静态截图伪装页面。
- 开发默认后端为 `http://192.168.1.14:8000`，请求层追加 `/api/v1`。
- 默认关闭 Mock；接口失败不得静默回退演示数据。
- 构建前若调用 Java 工具，必须使用 `F:\demo1\android\.tools\jdk21-full\jdk-21.0.12+8`。
- 每个页面域完成后运行静态契约检查、TypeScript 检查和微信官方 `preview`。
- 安卓端只读；所有视觉验收使用相同页面状态的安卓/微信截图并排检查。

---

### Task 1: 真实后端默认配置与契约检查

**Files:**
- Create: `wx/scripts/check_real_backend.js`
- Modify: `wx/package.json`
- Modify: `wx/miniprogram/services/repository.ts`
- Modify: `wx/miniprogram/services/types.ts`
- Modify: `wx/miniprogram/app.ts`
- Test: `wx/scripts/check_real_backend.js`

**Interfaces:**
- Produces: `repository.getConnectionState(): { mode: 'remote' | 'mock'; apiBaseUrl: string; authenticated: boolean }`
- Produces: `repository.probeRealBackend(): Promise<{ status: string; mode: string }>`
- Produces: remote-by-default `AppSettings` with `mockMode: false` and `apiBaseUrl: 'http://192.168.1.14:8000'`.

- [ ] **Step 1: Write the failing source-contract check**

```js
const assert = require('node:assert/strict')
const fs = require('node:fs')
const source = fs.readFileSync('miniprogram/services/repository.ts', 'utf8')
assert.match(source, /mockMode:\s*false/)
assert.match(source, /apiBaseUrl:\s*'http:\/\/192\.168\.1\.14:8000'/)
assert.match(source, /getConnectionState\(\)/)
assert.match(source, /probeRealBackend\(\)/)
console.log('real backend contract ok')
```

- [ ] **Step 2: Run the check and verify RED**

Run: `cd wx; node scripts/check_real_backend.js`

Expected: FAIL because the current defaults are Mock and the connection methods do not exist.

- [ ] **Step 3: Implement remote defaults without overwriting an explicit saved choice**

`bootstrap()` must migrate only settings whose stored `apiBaseUrl` is empty and whose session mode is absent. Existing explicit settings remain intact. `probeRealBackend()` must call `/health` unauthenticated and return the response object.

- [ ] **Step 4: Run backend and TypeScript checks**

Run: `cd wx; node scripts/check_real_backend.js; npm run typecheck`

Expected: both exit 0.

- [ ] **Step 5: Commit only Task 1 files**

```powershell
git add -- wx/scripts/check_real_backend.js wx/package.json wx/miniprogram/services/repository.ts wx/miniprogram/services/types.ts wx/miniprogram/app.ts
git commit -m "feat(wx): default student app to real backend"
```

### Task 2: 共享视觉令牌、二级导航和路由壳层

**Files:**
- Create: `wx/miniprogram/components/secondary-nav/secondary-nav.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/components/state-view/state-view.{json,ts,wxml,wxss}`
- Create: `wx/scripts/check_shell_parity.js`
- Modify: `wx/miniprogram/app.wxss`
- Modify: `wx/miniprogram/app.json`
- Modify: `wx/package.json`
- Test: `wx/scripts/check_shell_parity.js`

**Interfaces:**
- Produces: `<secondary-nav title="..." bind:back="..." />` with `statusBarHeight`, sticky placement and 54px content height.
- Produces: `<state-view state="loading|empty|error" message="..." action="..." bind:action="..." />`.
- Produces: prefixed `.campus-*` tokens for surfaces, 24px page gutters, 28px cards and motion durations.

- [ ] **Step 1: Write failing component registration checks**

```js
const assert = require('node:assert/strict')
const fs = require('node:fs')
for (const component of ['secondary-nav', 'state-view']) {
  for (const ext of ['json', 'ts', 'wxml', 'wxss']) {
    assert.ok(fs.existsSync(`miniprogram/components/${component}/${component}.${ext}`))
  }
}
const appStyle = fs.readFileSync('miniprogram/app.wxss', 'utf8')
assert.match(appStyle, /--campus-primary:\s*#596AF0/i)
assert.match(appStyle, /--campus-page-gutter:\s*24px/i)
```

- [ ] **Step 2: Run check and verify RED**

Run: `cd wx; node scripts/check_shell_parity.js`

Expected: FAIL because shared components do not exist.

- [ ] **Step 3: Implement components and prefixed tokens**

Use the Android `StickySecondaryNavigation` dimensions and existing project icon assets. Back behavior calls `wx.navigateBack()` with a home fallback; state actions emit a component event.

- [ ] **Step 4: Run shell check and typecheck**

Run: `cd wx; node scripts/check_shell_parity.js; npm run typecheck`

Expected: both exit 0.

- [ ] **Step 5: Commit Task 2 files**

```powershell
git add -- wx/miniprogram/components wx/miniprogram/app.wxss wx/miniprogram/app.json wx/scripts/check_shell_parity.js wx/package.json
git commit -m "feat(wx): add Android-parity navigation shell"
```

### Task 3: 首页和五个一级页面

**Files:**
- Modify: `wx/miniprogram/pages/index/index.{ts,wxml,wxss}`
- Modify: `wx/miniprogram/pages/courses/courses.{ts,wxml,wxss}`
- Modify: `wx/miniprogram/pages/tasks/tasks.{ts,wxml,wxss}`
- Modify: `wx/miniprogram/pages/counselor/counselor.{ts,wxml,wxss}`
- Modify: `wx/miniprogram/pages/profile/profile.{ts,wxml,wxss}`
- Modify: `wx/miniprogram/custom-tab-bar/index.{ts,wxml,wxss}`
- Create: `wx/scripts/check_primary_routes.js`
- Test: `wx/scripts/check_primary_routes.js`

**Interfaces:**
- Consumes: `repository.getConnectionState()`, existing task/course/notice/chat methods.
- Produces: five root screens matching Android Dock navigation and root-page motion.
- Produces: home quick routes `exams`, `classrooms`, `community`, `focus`, `lostfound`.

- [ ] **Step 1: Write failing primary-route assertions**

```js
const assert = require('node:assert/strict')
const fs = require('node:fs')
const home = fs.readFileSync('miniprogram/pages/index/index.wxml', 'utf8')
for (const label of ['考试安排', '空教室', '校园社区', '专注自习', '失物招领']) {
  assert.ok(home.includes(label), `missing ${label}`)
}
assert.doesNotMatch(home, /办事大厅/)
const dock = fs.readFileSync('miniprogram/custom-tab-bar/index.wxml', 'utf8')
for (const label of ['首页', '课程', '待办', 'AI校园助手', '我的']) assert.ok(dock.includes(label))
```

- [ ] **Step 2: Run check and verify RED**

Run: `cd wx; node scripts/check_primary_routes.js`

Expected: FAIL on the current `办事大厅` shortcut and Android-inconsistent root layouts.

- [ ] **Step 3: Port root layouts and navigation**

Map Android page sections in source order. Preserve real data binding and existing handlers; replace wrong routes with the secondary routes created in Tasks 4–6. The Dock must show the real pending count.

- [ ] **Step 4: Verify root screens**

Run: `cd wx; node scripts/check_primary_routes.js; npm run check`

Expected: exit 0 with five root routes present.

- [ ] **Step 5: Commit Task 3 files**

```powershell
git add -- wx/miniprogram/pages/index wx/miniprogram/pages/courses wx/miniprogram/pages/tasks wx/miniprogram/pages/counselor wx/miniprogram/pages/profile wx/miniprogram/custom-tab-bar wx/scripts/check_primary_routes.js
git commit -m "feat(wx): match Android primary student screens"
```

### Task 4: 学业领域页面

**Files:**
- Create: `wx/miniprogram/pages/exams/exams.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/exam-detail/exam-detail.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/exam-edit/exam-edit.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/classrooms/classrooms.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/university/university.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/academic/academic.{json,ts,wxml,wxss}`
- Modify: `wx/miniprogram/services/types.ts`
- Modify: `wx/miniprogram/services/repository.ts`
- Modify: `wx/miniprogram/app.json`
- Create: `wx/scripts/check_academic_routes.js`
- Test: `wx/scripts/check_academic_routes.js`

**Interfaces:**
- Produces: `getExams`, `getExam`, `saveExam`, `deleteExam`, `getClassrooms` repository methods matching backend DTOs.
- Produces: list/detail/edit navigation with `id` query parameters and Android-equivalent filters and form states.

- [ ] **Step 1: Write failing route and repository checks**

The check must assert all six page paths are in `app.json`, all page files exist, and repository source contains the five method names above.

- [ ] **Step 2: Run check and verify RED**

Run: `cd wx; node scripts/check_academic_routes.js`

Expected: FAIL because the pages and methods are absent.

- [ ] **Step 3: Implement academic pages from Android Compose sources**

Copy the visible hierarchy, filters, status chips, form fields and empty/error states from `ExamsScreen`, `ExamDetailScreen`, `ExamEditScreen`, `ClassroomsScreen`, `UniversityScreen` and `AcademicScreen`. Use `<secondary-nav>` on every page.

- [ ] **Step 4: Verify academic domain**

Run: `cd wx; node scripts/check_academic_routes.js; npm run check`

Expected: exit 0.

- [ ] **Step 5: Commit Task 4 files**

```powershell
git add -- wx/miniprogram/pages/exams wx/miniprogram/pages/exam-detail wx/miniprogram/pages/exam-edit wx/miniprogram/pages/classrooms wx/miniprogram/pages/university wx/miniprogram/pages/academic wx/miniprogram/services wx/miniprogram/app.json wx/scripts/check_academic_routes.js
git commit -m "feat(wx): add Android-parity academic flows"
```

### Task 5: 校园社区、专注和失物招领

**Files:**
- Create: `wx/miniprogram/pages/community/community.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/focus/focus.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/lostfound/lostfound.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/lostfound-publish/lostfound-publish.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/lostfound-detail/lostfound-detail.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/lostfound-mine/lostfound-mine.{json,ts,wxml,wxss}`
- Modify: `wx/miniprogram/services/types.ts`
- Modify: `wx/miniprogram/services/repository.ts`
- Modify: `wx/miniprogram/app.json`
- Create: `wx/scripts/check_campus_routes.js`
- Test: `wx/scripts/check_campus_routes.js`

**Interfaces:**
- Produces: focus session start/pause/resume/finish using existing study endpoints.
- Produces: lost-found list/detail/create/mine repository methods with typed items.
- Produces: real interactive filter tabs, timer states, publish form and detail actions.

- [ ] **Step 1: Write failing page and method checks**

Assert all six routes, required page files, focus methods, and lost-found method names.

- [ ] **Step 2: Run check and verify RED**

Run: `cd wx; node scripts/check_campus_routes.js`

Expected: FAIL because community/focus/lost-found parity routes are missing.

- [ ] **Step 3: Implement campus domain from Android sources**

Use `CommunityScreen`, `FocusScreen`, `LostFoundScreen`, `LostFoundPublishScreen`, `LostFoundDetailScreen`, and `MyLostFoundScreen` as the exact content and state order. Reuse project image assets and native picker/input controls.

- [ ] **Step 4: Verify campus domain**

Run: `cd wx; node scripts/check_campus_routes.js; npm run check`

Expected: exit 0.

- [ ] **Step 5: Commit Task 5 files**

```powershell
git add -- wx/miniprogram/pages/community wx/miniprogram/pages/focus wx/miniprogram/pages/lostfound* wx/miniprogram/services wx/miniprogram/app.json wx/scripts/check_campus_routes.js
git commit -m "feat(wx): add campus community focus and lost-found flows"
```

### Task 6: 任务、通知与校园动态二级页面

**Files:**
- Create: `wx/miniprogram/pages/task-calendar/task-calendar.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/task-detail/task-detail.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/campus-news/campus-news.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/campus-news-detail/campus-news-detail.{json,ts,wxml,wxss}`
- Modify: `wx/miniprogram/pages/notices/notices.{ts,wxml,wxss}`
- Modify: `wx/miniprogram/services/types.ts`
- Modify: `wx/miniprogram/services/repository.ts`
- Modify: `wx/miniprogram/app.json`
- Create: `wx/scripts/check_information_routes.js`
- Test: `wx/scripts/check_information_routes.js`

**Interfaces:**
- Produces: task detail/calendar navigation and complete/delete mutations.
- Produces: notification inbox and campus news list/detail methods with read-state handling.

- [ ] **Step 1: Write failing route and method checks**

Assert four new routes, page files, task detail/calendar handlers, and campus-news methods.

- [ ] **Step 2: Run check and verify RED**

Run: `cd wx; node scripts/check_information_routes.js`

Expected: FAIL because detail and campus-news routes are absent.

- [ ] **Step 3: Port Android task and notification states**

Match `TaskCalendarScreen`, `TaskDetailScreen`, `NotificationsScreen`, `CampusNewsScreen`, and `CampusNewsDetailScreen`; all list items must navigate to working detail screens.

- [ ] **Step 4: Verify information domain**

Run: `cd wx; node scripts/check_information_routes.js; npm run check`

Expected: exit 0.

- [ ] **Step 5: Commit Task 6 files**

```powershell
git add -- wx/miniprogram/pages/task-* wx/miniprogram/pages/notices wx/miniprogram/pages/campus-news* wx/miniprogram/services wx/miniprogram/app.json wx/scripts/check_information_routes.js
git commit -m "feat(wx): add task and campus information detail flows"
```

### Task 7: 个人中心、设置和集成页面

**Files:**
- Create: `wx/miniprogram/pages/settings/settings.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/help-feedback/help-feedback.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/notification-settings/notification-settings.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/chaoxing/chaoxing.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/expression-contribution/expression-contribution.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/account/account.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/personal-hub/personal-hub.{json,ts,wxml,wxss}`
- Create: `wx/miniprogram/pages/service-form/service-form.{json,ts,wxml,wxss}`
- Modify: `wx/miniprogram/pages/profile/profile.{ts,wxml,wxss}`
- Modify: `wx/miniprogram/services/types.ts`
- Modify: `wx/miniprogram/services/repository.ts`
- Modify: `wx/miniprogram/app.json`
- Create: `wx/scripts/check_profile_routes.js`
- Test: `wx/scripts/check_profile_routes.js`

**Interfaces:**
- Produces: settings persistence, account display, feedback submission, notification/Chaoxing state, contribution submission, and personal hub sections.
- Consumes: real backend tokens and `getConnectionState()`; no hidden Mock fallback.

- [ ] **Step 1: Write failing route and visible-label checks**

Assert all eight routes and files, profile entry labels, and repository integration method names.

- [ ] **Step 2: Run check and verify RED**

Run: `cd wx; node scripts/check_profile_routes.js`

Expected: FAIL because Android personal routes do not exist in the miniapp.

- [ ] **Step 3: Implement profile domain from Android Compose sources**

Match `SettingsScreen`, `HelpFeedbackScreen`, `NotificationSettingsScreen`, `ChaoxingScreen`, `ExpressionContributionScreen`, `AccountScreen`, `PersonalHubScreen`, and `GenericServiceFormScreen`. Keep development-only backend controls out of normal student UI.

- [ ] **Step 4: Verify profile domain**

Run: `cd wx; node scripts/check_profile_routes.js; npm run check`

Expected: exit 0.

- [ ] **Step 5: Commit Task 7 files**

```powershell
git add -- wx/miniprogram/pages/settings wx/miniprogram/pages/help-feedback wx/miniprogram/pages/notification-settings wx/miniprogram/pages/chaoxing wx/miniprogram/pages/expression-contribution wx/miniprogram/pages/account wx/miniprogram/pages/personal-hub wx/miniprogram/pages/service-form wx/miniprogram/pages/profile wx/miniprogram/services wx/miniprogram/app.json wx/scripts/check_profile_routes.js
git commit -m "feat(wx): complete Android-parity personal flows"
```

### Task 8: 官方编译、真实接口与逐页视觉动效验收

**Files:**
- Create: `wx/scripts/check_route_manifest.js`
- Create: `wx/visual-qa/route-matrix.json`
- Modify: only mismatching `wx/miniprogram/**` files found during QA
- Test: all `wx/scripts/check_*.js`, `npm run check`, official DevTools `preview`, GUI route smoke reports and screenshots.

**Interfaces:**
- Produces: route matrix with Android source route, WeChat route, required state and screenshot status.
- Produces: fresh preview artifacts outside the repository and GUI runtime evidence.

- [ ] **Step 1: Write the complete manifest assertion**

The script reads the spec route tables and `app.json`, asserts every target page is registered, and checks that every WXML page has either the custom tab bar or `<secondary-nav>`.

- [ ] **Step 2: Run all local checks**

Run: `cd wx; node scripts/check_route_manifest.js; npm run check`

Expected: all commands exit 0 with no TypeScript errors.

- [ ] **Step 3: Verify the real backend**

Run: `Invoke-WebRequest http://192.168.1.14:8000/api/v1/health` and use the running miniapp to log in remotely, then inspect runtime storage for `mockMode: false`, `session-mode: remote`, and non-empty tokens.

Expected: health HTTP 200 with `mode: real_backend`; miniapp session mode is `remote`.

- [ ] **Step 4: Run official WeChat preview compile**

Run `H:\Dev\微信web开发者工具\cli.bat open --project F:\demo1\wx`, use its reported live port, then run `preview` with base64 QR and info outputs in a timestamped temporary directory.

Expected: command exits 0 and both preview artifacts exist.

- [ ] **Step 5: Capture and compare each route**

For every entry in `visual-qa/route-matrix.json`, navigate both running simulators to the same state, capture screenshots, combine the reference and miniapp screenshots, and inspect layout, crop, spacing, type, weight, border, radius, icons, selected state and motion. Fix visible mismatches and repeat until the route passes.

- [ ] **Step 6: Run final clean verification**

Run: `cd wx; npm run check`, official `preview`, all GUI route smoke checks, `git diff --check -- wx`, and `git diff --name-only -- android`.

Expected: all checks pass; no new Android diff exists.

- [ ] **Step 7: Commit final QA fixes**

```powershell
git add -- wx
git commit -m "test(wx): verify full Android visual and backend parity"
```
