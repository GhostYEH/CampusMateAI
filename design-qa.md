# AI 校园助手视觉 QA

- source visual truth path: `C:/Users/32883/AppData/Local/Temp/codex-clipboard-14b05518-5754-4e86-8b09-8b92000d5b5a.png`
- implementation screenshot path: `F:/demo1/web/counselor-implementation.png`
- comparison evidence: `F:/demo1/web/counselor-visual-comparison.png`
- viewport: `1672 x 941`, DPR 1
- state: student demo session, `/counselor`, seeded exam-week conversation

## Full-view comparison evidence

Reference and implementation were combined into one same-scale side-by-side image. The implementation matches the reference's 272 px navigation rail, 89 px toolbar, 211 px hero, three-column content grid, card hierarchy, cool blue-violet palette, and dense first-screen composition.

## Focused region comparison evidence

- Header and hero: search/date/sync controls align to the same horizontal zones; headline and copy occupy the reference's left negative space. The replacement robot illustration uses the same white, indigo, cyan, and periwinkle 3D direction.
- Main workspace: session list, user prompt, assistant answer, source chips, action row, composer, and campus-service cards preserve the reference ordering, density, radii, and hierarchy.
- Sidebar and promotion card: navigation labels, active state, badge, utility section, CTA, and robot imagery are present and functional.

## Findings

- No actionable P0/P1/P2 mismatch remains.
- P3: generated hero robot is cropped larger than the source robot. This is acceptable because the focal subject, palette, negative-space division, and copy readability remain faithful.
- P3: a few microcopy labels and icon silhouettes differ because the implementation uses the project's Phosphor icon system and functional product copy.

## Required fidelity surfaces

- Fonts and typography: Noto Sans SC is loaded locally; heading weight, body hierarchy, line height, and truncation match the reference closely.
- Spacing and layout rhythm: desktop frame, navigation width, grid tracks, gaps, card padding, radii, and first-screen vertical rhythm were verified at the exact reference viewport.
- Colors and visual tokens: cool white, ice blue, periwinkle, indigo, muted slate, and subtle border/shadow values map closely to the source.
- Image quality and asset fidelity: hero and promotion card use real raster assets; no placeholder or code-drawn illustration replaces visible source art.
- Copy and content: all key screenshot copy is present in clean Simplified Chinese, including hero, sessions, recommendations, answer, service help, promo, and composer.

## Patches made since previous QA pass

- Rebuilt the student shell's corrupted Chinese labels and assistant-specific header state.
- Replaced the assistant view with the screenshot-matched three-column workspace.
- Added a generated campus robot hero asset and reused the existing robot art in the promo card.
- Added functional new-chat, history, recommendation rotation, shortcut, service, composer, attachment, and web-search states.
- Tuned the hero crop and chat spacing after the first browser screenshot.

## Follow-up polish

- Optional P3: commission an illustration with the source robot's exact smaller body crop if an even tighter art match is required.

final result: passed

## 2026-08-13 微信小程序前后端联调强化

- 修复真实待办路由：`/personal-tasks/` 改为后端实际 `/tasks`。
- 修复通知解析：请求使用 `content`，适配多任务响应并逐项异步保存。
- 修复 AI 辅导员：使用 `conversation_id` 并明确 `stream: false`。
- 增加 access/refresh token 生命周期、401 刷新、远端注销和会话模式隔离。
- 真实模式课程、通知、首页、待办角标统一从后端异步读取，不再用 Mock 掩盖错误。
- 增加登录页后端地址配置、健康检查和 Mock/真实模式恢复入口。
- 学习专注会话接入后端启动、暂停、恢复、完成与失败重试。
- 动态生成本周日期，支持“今天/明天/月日”截止时间解析并拒绝无法识别的日期。
- 微信端检查：31 项后端联调契约、6 项日期契约、10 项安卓视觉契约、TypeScript、事件处理器和 WXML 标签审计通过。
- 后端检查：新增 5 项微信端到端契约；全量 173 项测试通过。
- Android 目录保持只读，本轮未执行任何 Android 写入。

final integration result: passed

---

# Android 失物招领沉浸式视觉 QA

- source visual truth path: `C:/Users/32883/AppData/Local/Temp/codex-clipboard-86b01556-5b74-40b0-9464-26a18e116ce2.png`
- implementation screenshot path: `F:/demo1/android/qa-lostfound-final.png`
- comparison evidence: `F:/demo1/android/qa-lostfound-final-comparison.png`
- dark-theme evidence: `F:/demo1/android/qa-lostfound-fixed-dark.png`
- viewport: `1280 x 2856`, emulator density 480 dpi
- state: student demo session, lost-found browse screen, light theme; dark theme checked separately

## Full-view comparison evidence

The source and implementation were normalized by content width and combined into one side-by-side image. The Android screen preserves the source hierarchy: immersed pale-blue hero, top actions, lost/found switch, search, six category chips, location/sort controls, item cards, and floating bottom dock. The implementation viewport is taller and does not include the source phone frame; this expected crop difference was not treated as design drift.

## Focused region comparison evidence

- Hero and system bars: the pale-blue art extends behind the transparent status bar; status icons are dark over this always-light surface in both app themes. The back surface is translucent and remains readable.
- Filters: all six categories, including `其他`, fit at 432dp without clipping. Search, location, and sort controls retain aligned heights and tap targets.
- Cards: raster product imagery is sharp, rounded masks have no halo, title/status chips align, and long descriptions truncate without colliding with the dock.
- Bottom dock: `AI校园助手` remains selected on the lost-found route, matching the source navigation context. Gesture navigation stays transparent and theme-aware.

## Findings

- No actionable P0/P1/P2 mismatch remains.
- P3: the implementation uses the project's taller Android viewport and a slightly denser card body, so more description text is visible than in the framed reference. This is acceptable and does not cause overlap or hierarchy loss.
- P3: the hero raster composition differs slightly in props and crop, but preserves the reference subject, palette, lighting, negative-space split, and text readability.

## Required fidelity surfaces

- Fonts and typography: Chinese fallback rendering, display weight, body hierarchy, line height, ellipsis, and navigation labels were checked at device density; no wrapping or clipping remains.
- Spacing and layout rhythm: status inset, hero height, filter grouping, chip gaps, card padding, radii, shadows, dock clearance, and gesture inset were checked in light and dark themes.
- Colors and visual tokens: the cool blue-violet hero, primary selection, white/light surfaces, muted slate copy, semantic orange status, and theme-aware system icons preserve contrast.
- Image quality and asset fidelity: the hero and item thumbnails use real raster assets with correct crop and masking; no placeholder or code-drawn replacement is visible.
- Copy and content: the page title, helper copy, modes, categories, locations, item titles, status, timestamps, and dock labels are coherent Simplified Chinese and match the target structure.

## Patches made since the previous QA pass

- Made lost-found status-bar icon contrast follow its always-light hero instead of the global dark-theme flag.
- Tightened compact-width category chip padding so `其他` remains fully visible.
- Kept `AI校园助手` selected in the bottom dock while the lost-found route is open.
- Added regression tests for system-bar contrast, compact category layout, and dock route selection.

## Verification

- `:app:testDebugUnitTest :app:assembleDebug` returned `BUILD SUCCESSFUL`.
- The rebuilt APK installed successfully on `emulator-5556` and the final target screen was recaptured after installation.
- `git diff --check` reported no whitespace errors; only the repository's existing LF-to-CRLF notices were emitted.

final result: passed
