# 微信小程序系统性 Android 视觉对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以现有 Android 截图和 Compose 源码为唯一视觉基准，统一微信端尺度体系并完成课程、待办、AI 校园助手、我的、失物招领和专注自习的响应式视觉与交互对齐。

**Architecture:** 保留原生微信小程序与现有真实后端仓库层；在 `app.wxss` 建立统一令牌，在 `utils/layout.ts` 统一计算状态栏、胶囊与导航高度，由公共导航和 TabBar 消费。页面仅重构 WXML/WXSS 和必要的前端状态映射，不修改 Android、FastAPI、数据库或 API 协议。

**Tech Stack:** 微信小程序 WXML/WXSS/TypeScript、自定义 TabBar、现有 FastAPI `/api/v1`、微信开发者工具官方 CLI。

**Spec:** `C:/Users/32883/.codex/attachments/386fcd4b-8ed9-4697-b972-762824f9b26a/pasted-text.txt`

## Global Constraints

- 只修改 `wx/` 与本计划文档；禁止修改 `android/`、`backend/`、数据库和 API 协议。
- 保持 `mockMode: false` 和真实后端模式；接口失败只影响对应数据区，不能破坏页面骨架。
- 不使用整页 `scale()`、主要内容绝对定位、负边距堆叠、截图背景或 emoji 图标。
- 375、390、393、414px 宽度均需正常；所有正文预留实际 TabBar 与底部安全区。
- 每个页面完成后必须生成 Android/微信同视口并排图并检查标题、边距、卡片、字号、圆角、图标、底部和错误态。

---

### Task 1: 全局尺寸令牌与平台安全区

**Files:**
- Create: `wx/miniprogram/utils/layout.ts`
- Modify: `wx/miniprogram/app.wxss`
- Modify: `wx/miniprogram/components/campus-header/campus-header.ts`
- Modify: `wx/miniprogram/components/campus-header/campus-header.wxml`
- Modify: `wx/miniprogram/components/campus-header/campus-header.wxss`
- Modify: `wx/miniprogram/components/secondary-nav/secondary-nav.ts`
- Modify: `wx/miniprogram/components/secondary-nav/secondary-nav.wxml`
- Modify: `wx/miniprogram/components/secondary-nav/secondary-nav.wxss`
- Modify: `wx/miniprogram/custom-tab-bar/index.wxss`
- Create: `wx/scripts/check_layout_tokens.js`

**Interfaces:**
- Produces: `getMiniProgramLayoutMetrics(): { statusBarHeight: number; menuTop: number; menuBottom: number; menuHeight: number; navContentHeight: number; navTotalHeight: number; contentTop: number }`.
- Produces: `--campus-page-gutter`, `--campus-title-size`, `--campus-subtitle-size`, `--campus-card-radius-lg`, `--campus-card-padding`, `--campus-section-gap`, `--campus-tab-reserve`.

- [ ] **Step 1: Add a failing static contract**

Assert that the utility calls `wx.getMenuButtonBoundingClientRect()`, both nav components consume `navContentHeight`, and the global token names exist.

- [ ] **Step 2: Run the contract and confirm failure**

Run: `cd wx; node scripts/check_layout_tokens.js`

Expected: non-zero before the utility and token migration.

- [ ] **Step 3: Implement shared layout metrics and tokens**

Use the system status bar and menu button rectangle with a safe fallback. Do not hardcode a device-specific `top`; derive `navContentHeight = max(44, (menuTop - statusBarHeight) * 2 + menuHeight)` and `navTotalHeight = statusBarHeight + navContentHeight`.

- [ ] **Step 4: Migrate shared navigation and bottom reserve**

Use the derived values for title/back-button alignment and preserve a right spacer equal to the system capsule zone. Keep the Dock floating shape but expose its full reserved height through the global token.

- [ ] **Step 5: Verify**

Run: `cd wx; node scripts/check_layout_tokens.js; npm run typecheck`.

### Task 2: 课程与待办尺度校准

**Files:**
- Modify: `wx/miniprogram/pages/courses/courses.wxml`
- Modify: `wx/miniprogram/pages/courses/courses.wxss`
- Modify: `wx/miniprogram/pages/tasks/tasks.wxml`
- Modify: `wx/miniprogram/pages/tasks/tasks.wxss`
- Modify: `wx/scripts/check_android_parity.js`

**Interfaces:**
- Consumes: shared page/title/card/tab tokens.
- Preserves: existing course/task repository methods and handlers.

- [ ] **Step 1: Extend parity checks**

Assert the Android section order, five course filters, task filters, safe bottom reserve, long-title ellipsis and no fixed page width.

- [ ] **Step 2: Calibrate course hierarchy**

Match Android title, hero, 7-day strip, four metrics, filter chips and 142–160px list-card rhythm at a 380px viewport; keep long course names in a flexible center column.

- [ ] **Step 3: Calibrate task hierarchy**

Match Android summary, week selector, search/filter card, focus card, list cards and floating button; ensure the final card scrolls above the Dock.

- [ ] **Step 4: Capture and compare**

Capture both pages from the running DevTools, normalize to 380 × 820 and save side-by-side artifacts.

- [ ] **Step 5: Verify**

Run: `cd wx; npm run check:parity; npm run typecheck`.

### Task 3: AI 校园助手与我的尺度校准

**Files:**
- Modify: `wx/miniprogram/pages/counselor/counselor.wxml`
- Modify: `wx/miniprogram/pages/counselor/counselor.wxss`
- Modify: `wx/miniprogram/pages/profile/profile.wxml`
- Modify: `wx/miniprogram/pages/profile/profile.wxss`

**Interfaces:**
- Preserves: counselor message flow, real-backend state and profile service navigation.

- [ ] **Step 1: Match counselor proportions**

Use the Android robot resource, 2 × 2 suggestion grid, two-paragraph welcome bubble and fixed composer with Dock-safe bottom; all icons remain real asset files.

- [ ] **Step 2: Match profile proportions**

Keep the Android hero height, avatar and four shortcuts; use `min-width: 0`, `flex-shrink: 0` and ellipsis so long identity text never forces the arrow or avatar off-screen.

- [ ] **Step 3: Capture and compare**

Generate same-state side-by-side images for both pages and correct visible P0–P2 differences.

- [ ] **Step 4: Verify**

Run: `cd wx; npm run check:shell; npm run typecheck`.

### Task 4: 失物招领完整重构与局部错误态

**Files:**
- Modify: `wx/miniprogram/pages/lostfound/lostfound.ts`
- Modify: `wx/miniprogram/pages/lostfound/lostfound.wxml`
- Modify: `wx/miniprogram/pages/lostfound/lostfound.wxss`
- Modify: `wx/miniprogram/services/repository.ts` only if the existing request path or DTO mapping is inconsistent with the current API definition
- Create: `wx/scripts/check_lostfound_layout.js`

**Interfaces:**
- Preserves: `repository.getLostFoundAsync(): Promise<LostFoundItem[]>`.
- Produces: kind, category, location, sort and keyword filters that only transform fetched real data.

- [ ] **Step 1: Add failing structural checks**

Assert the top actions, Android hero asset, two-mode switch, six categories, location/sort controls, item metadata and list-only error container.

- [ ] **Step 2: Implement Android hierarchy**

Rebuild the hero and filter card from `LostFoundScreen.kt`, reuse the copied Android resources and retain normal document flow.

- [ ] **Step 3: Implement resilient state handling**

Keep Hero and all controls visible during loading/error. Map university-required 409 to a friendly list-area gate; do not generate fake records or silently enable Mock.

- [ ] **Step 4: Verify interactions and screenshot**

Exercise kind/category/search/location/sort controls and retry; capture Android/微信 comparison at 380 × 820.

- [ ] **Step 5: Verify**

Run: `cd wx; node scripts/check_lostfound_layout.js; npm run check:student-tools; npm run typecheck`.

### Task 5: 专注自习完整重构并保留真实会话逻辑

**Files:**
- Modify: `wx/miniprogram/pages/study/study.ts`
- Modify: `wx/miniprogram/pages/study/study.wxml`
- Modify: `wx/miniprogram/pages/study/study.wxss`
- Add: focus-goal/icon assets generated from the existing Android/Phosphor asset sources when missing
- Create: `wx/scripts/check_focus_layout.js`

**Interfaces:**
- Preserves: start/pause/resume/finish calls and local timer lifecycle.
- Produces: modes `focus=25`, `shortBreak=5`, `longBreak=15`; derived timer ring progress; real-device capability copy without claiming ONNX/camera availability.

- [ ] **Step 1: Add failing focus structure checks**

Assert title `专注自习`, 25/5/15 modes, circular timer, assistance card, three stats, goal card and recent-record section.

- [ ] **Step 2: Rebuild timer card**

Use the Android 258dp ring proportion, large `25:00`, single primary action and an optional end-session action; preserve existing asynchronous handlers.

- [ ] **Step 3: Rebuild assistance/stats/goal/records**

Display device-determined capability truthfully, sync real focus records where available, and reserve Dock + safe-area space for all lower content.

- [ ] **Step 4: Verify timer states**

Check idle → running → paused → resumed and unload cleanup without waiting for a full 25-minute completion.

- [ ] **Step 5: Capture and compare**

Capture Android and微信 at the same idle state, fix all P0–P2 differences and save the combined image.

- [ ] **Step 6: Verify**

Run: `cd wx; node scripts/check_focus_layout.js; npm run check:student-tools; npm run typecheck`.

### Task 6: 多宽度与受影响页面回归

**Files:**
- Modify: only `wx/miniprogram/**` files with an observed regression
- Modify: `wx/design-qa.md`

- [ ] **Step 1: Check 375/390/393/414 layouts**

Verify capsule clearance, long titles, long user names, long course names, horizontal chips and final-list-item scrolling without scaling the page.

- [ ] **Step 2: Check shared-style consumers**

Open首页、考试、空教室、校园社区、通知 and profile service routes; confirm shared navigation and card tokens did not regress them.

- [ ] **Step 3: Complete design QA**

Open each Android reference and latest微信 capture together, record the visible decision for every target page, and require `final result: passed`.

### Task 7: Final validation and official preview

**Files:**
- Modify: `wx/design-qa.md`
- Create/Modify: generated artifacts under `wx/artifacts/`

- [ ] **Step 1: Run project validation**

Run: `cd wx; node ../.agents/skills/wechat-miniprogram-auto-port-deploy/scripts/inspect-project.js; node ../.agents/skills/wechat-miniprogram-auto-port-deploy/scripts/validate-miniprogram.js; npm run check; git diff --check -- wx`.

- [ ] **Step 2: Verify the live backend**

Log in through the existing real-backend flow and request courses, tasks, focus and lost-found endpoints without printing credentials or tokens.

- [ ] **Step 3: Run official preview and GUI checks**

Run the official DevTools `preview`, then open and exercise each target page in the already-running simulator. Record compile size, route state, runtime exceptions and screenshots.

- [ ] **Step 4: Confirm scope**

Run: `git diff --name-only -- android` and compare with the pre-task Android diff so this task introduces no Android change.

