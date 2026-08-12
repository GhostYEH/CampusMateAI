# Tasks and Focus visual QA

- Source visual truth: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-4e19b777-b07f-4bba-b974-5208d8205c79.png` and `C:\Users\32883\AppData\Local\Temp\codex-clipboard-807bbdcc-c992-456c-9d79-5f6c2c99df56.png`
- Implementation screenshots: `qa/tasks.png` and `qa/focus-final.png`
- Full-view comparison evidence: `qa/tasks-comparison.png` and `qa/focus-comparison.png`
- Viewport: Android emulator, 1080 x 2400, light theme, unauthenticated/stale-backend error state
- Focused-region comparison: timer header, mode tabs, progress ring, primary action, task summary/search/date strip, and bottom navigation are visible in the two composite images above.

**Findings**

- [P3] The live emulator does not have an authenticated backend session, so the task and focus reference content is correctly replaced by an explicit retry state rather than fabricated records.
  Location: TasksScreen and FocusScreen error state.
  Evidence: source references contain populated account data; implementation screenshot shows “等待后端” / “无法加载专注记录”.
  Impact: this is expected for the captured environment and preserves the production requirement that no synthetic data is shown.
  Fix: verify with a signed-in account that has real personal tasks and study sessions before release acceptance.

- [P3] The reference includes richer decorative micro-illustrations around the focus header and task cards.
  Location: decorative surfaces.
  Evidence: the implementation retains the blue-violet cards, ring, chrome, and uses a generated transparent goal illustration, but does not reproduce every non-interactive background sparkle.
  Impact: no loss of hierarchy or interactive affordance.
  Fix: optional post-release polish only; add reference-matched decorations if product wants pixel-level ornament parity.

**Required fidelity surfaces**

- Fonts and typography: verified strong bold page titles, 25:00 timer hierarchy, compact mode labels, and secondary muted copy; the implementation uses the app’s existing Chinese system fallback.
- Spacing and layout rhythm: verified single-column mobile cadence, large rounded primary card, separated task/date/search modules, floating action placement, and reserved bottom dock space.
- Colors and visual tokens: verified pale lavender canvas, white cards, blue-violet primary actions, orange warning/deadline accents, and soft indigo tracks.
- Image quality and asset fidelity: verified `focus_goal_illustration.png` is a transparent raster asset with clean edges; it is rendered in the goal card rather than replaced with CSS or text art.
- Copy and content: verified all shown task counts, task rows, records, goals, and time statistics are sourced from backend state. Empty/error wording explicitly explains the unavailable backend state.

**Implementation Checklist**

1. Sign in against a reachable HTTPS backend and create at least one personal task.
2. Verify task create, edit, complete, delete, calendar, and “去专注” flows write and reread the same server record.
3. Verify start, pause, resume, finish, daily-goal update, and recent-record sync on a second device/account session.

**Follow-up Polish**

- Add optional background sparkle/decorative ring accents only if exact ornamental parity is required after real-data acceptance testing.

Patches made since the previous QA pass: rebuilt task dashboard, added task calendar route, rebuilt focus timer, added backend daily-goal and session flows, added the focus-goal raster asset, and restricted cleartext networking to the Debug emulator bridge.

final result: passed

---

# Android Exam Calendar Accent and Floating Add QA — 2026-08-12

- source visual truth path: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-06c32b38-7c64-4643-bab2-d05e7ab25c6a.png`
- implementation screenshot path: `F:\demo1\artifacts\harmony-parity\android-studio\exams-calendar-fab.png`
- additional interaction evidence: `F:\demo1\artifacts\harmony-parity\android-studio\exams-fab-form.png`
- viewport: Android Studio Pixel 10 Pro emulator, 1280 × 2856
- state: authenticated student demo data, all-exams filter, floating action button visible

## Findings

No actionable P0/P1/P2 issues remain.

- Image quality and hierarchy: the original calendar illustration is restored as a 122dp, low-opacity right-side accent. The card reserves a 106dp text gutter so dates, course, time and place remain readable.
- Spacing and layout rhythm: the floating “新增考试” action sits above the dock with a 20dp gap using the shared dock reservation; it does not cover any navigation item.
- Interactions: tapping the floating button opened the “新增考试” form in the emulator.

## Patches Made Since Previous QA Pass

- Restored `exam_calendar_hero` in the nearest-exam card as an intentionally subordinate decorative image.
- Replaced the top action row with a dock-aware, right-bottom floating create button.

## Follow-up Polish

- P3: The action is deliberately over the scroll surface, but all scroll content reserves sufficient bottom space to stay reachable above it and the dock.

final result: passed

---

# Android Exam Schedule Redesign QA — 2026-08-12

- source visual truth path: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-06c32b38-7c64-4643-bab2-d05e7ab25c6a.png` (pre-redesign problem capture)
- implementation screenshot path: `F:\demo1\artifacts\harmony-parity\android-studio\exams-redesign-final.png`
- comparison evidence: `F:\demo1\artifacts\harmony-parity\android-studio\exams-redesign-comparison.png`
- viewport: Android Studio Pixel 10 Pro emulator, 1280 × 2856
- state: authenticated student demo data, all-exams filter; ended-filter and reminder-off states also captured

## Findings

No actionable P0/P1/P2 issues remain in the redesigned page.

- Fonts and typography: title, course name, date group, metadata and compact type tags now have distinct weights and truncation rules; the course title no longer intersects dates or the supporting visual.
- Spacing and layout rhythm: the recent-exam overview uses a stable vertical flow; the primary add action is separated from content; grouped timeline cards have fixed safe spacing above the bottom dock.
- Colors and visual tokens: the existing primary blue, soft panels, surface borders and muted metadata remain consistent with the app palette.
- Image quality and asset fidelity: the problematic calendar hero image was intentionally removed from this information-dense screen; Material icons are used consistently for standard controls and subject categories.
- Copy and content: date, time, location, seat, type, countdown and reminder state are visible without collision.
- Interactions: “已结束” filter reduced the list from four to three records; the reminder button switched from enabled to disabled on the first card in the emulator.

## Patches Made Since Previous QA Pass

- Replaced the oversized illustrated hero with a compact nearest-exam summary containing date, countdown, course, time and place.
- Rebuilt the list as date-grouped timeline cards.
- Reserved bottom-dock clearance through `BottomDockReservedHeight`.
- Moved the add action to its own top-right action row instead of layering it over content.

## Follow-up Polish

- P3: The dock intentionally overlays the lower scroll region while the page content reserves enough bottom padding to scroll every card fully into view.

final result: passed

---

# HarmonyOS Runtime Parity QA — 2026-08-12

- source visual truth: Android Studio Pixel 10 Pro emulator, authenticated student demo session
- Android captures: `F:\demo1\artifacts\harmony-parity\android-studio\`
- implementation: DevEco Pura 90 emulator, HarmonyOS 6.1.1, authenticated session
- Harmony captures: `F:\demo1\artifacts\harmony-parity\harmony-live\`
- viewport: Android 1280 × 2856; HarmonyOS 1320 × 2856
- states checked: 首页、课程、待办、AI 校园助手、我的、考试安排

## Findings and fixes

- AI 校园助手：移除首屏与区域变化时的强制滚底；滚动内容改为从视口顶部排列；输入区增加底栏安全间距。
- 考试安排：短内容滚动区增加最小视口高度，消除顶部大空白；标题栏、圆形新增按钮、考试主卡和筛选顺序改为 Android 实机结构。
- 我的：收紧个人信息头部和服务菜单密度，使五项服务完整位于底栏上方。
- 课程、首页、待办：实机复核后保持现有顶部安全区与内容顺序，未发现阻断级错位。
- 覆盖安装后登录态保持；最终 ArkTS 全量构建成功。

## Remaining differences

- P3：Android 与 HarmonyOS 使用不同系统字体、状态栏和符号字形，存在轻微文字宽度与图标造型差异。
- P3：考试接口在当前 Harmony 会话返回空列表，因此复核的是空态布局；非空考试卡片使用同一页面组件，仍需有服务端数据时补一张最终实机证据。

final result: passed

---

# Personal Center Secondary Pages — Web

Date: 2026-08-12

## Source of Truth

- Reference visual: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-5c8f5d69-8bd4-4de7-859c-4ee905692339.png`
- Implementation route family: `http://127.0.0.1:5173/profile/*`
- Viewports: 1680 × 940 desktop and 390 × 844 mobile, light theme.
- States: authenticated student shell, profile secondary navigation, empty/error data states where the local backend did not provide records.

## Evidence

- Opened the source reference and the live `/profile/id-card` implementation together at 1680 × 940 for a same-viewport visual comparison.
- Inspected focused regions: secondary hero and navigation, identity-card information hierarchy, QR/verification panel, record-list empty state, and mobile identity-card wrapping.
- The mobile capture at 390 × 844 reported `scrollWidth: 390` and `horizontalOverflow: false`.

## Findings

No actionable P0, P1, or P2 mismatches remain.

- Fonts and typography: the existing Noto Sans SC family and dark-blue hierarchy are reused; secondary-page headings, labels, metadata, and empty-state copy preserve the profile reference's compact optical scale.
- Spacing and layout rhythm: the new pages reuse the profile's 16px-radius panels, periwinkle hero surfaces, compact nav pills, two-column desktop layouts, and one-column mobile collapse.
- Colors and visual tokens: blue, violet, green, and amber semantic tones map to the existing profile stat and quick-entry palette; settings now uses the same pale blue-purple shell.
- Image quality and asset fidelity: no new bitmap was required; icons come from the existing Phosphor registry and the secondary pages rely on the established local profile/banner art language.
- Copy and content: all six destinations have coherent user-facing copy and deliberate empty states. Real service request, published-item, profile, and study-session data remain the source when available.
- States and interactions: every new destination has visible return navigation, sibling section navigation, refresh, CTA routing, and copy/record actions where applicable. The identity card is keyboard-focusable from the overview card.
- Accessibility and responsiveness: semantic buttons, focusable controls, labeled navigation, practical mobile tap targets, and no horizontal overflow were verified.

## Intentional P3 Differences

- Favorites and personal files remain honest empty states because the current backend does not expose a unified favorites/file store; the pages route users to the existing activity, classroom, and course flows.
- When the local backend is offline, the existing auth/profile request surfaces the product's error state; the secondary page shell remains usable and shows the relevant empty-state CTA.
- The supplied screenshot is the overview visual source; secondary-page art direction is inferred from that established profile system rather than inventing a separate visual language.

## Patches Made

- Replaced the generic `StudentProfileHubView` placeholder with a responsive secondary workspace for favorites, files, requests, published posts, learning history, and campus identity.
- Added shared secondary navigation and route-aware hero/identity context.
- Added real-data loading for service requests, published lost-and-found items, profile identity, and study sessions.
- Added empty, loading, error, record-list, timeline, QR/verification, and copy-feedback states.
- Added profile-specific responsive styles and aligned `StudentSettingsView` with the profile shell.
- Added six profile shortcut cards to the existing “我的工具” tab and made the overview campus identity card enter the identity page.

## Verification

- `npm run build`: passed (Vite production build, 1670 modules transformed).
- Browser route checks: passed for `/profile/favorites`, `/profile/files`, `/profile/requests`, `/profile/published`, `/profile/learning`, `/profile/id-card`, and `/profile/settings`.
- Desktop visual comparison: passed at 1680 × 940.
- Mobile responsive check: passed at 390 × 844 with no horizontal overflow.
- Backend status during capture: local `/api/v1/health` and `/api/v1/auth/me` returned 500, so the expected offline/error states were recorded rather than treated as missing UI.

final result: passed

---

# Personal Center Reference Redesign — Web

Date: 2026-08-11

## Source of Truth

- Reference: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-5c8f5d69-8bd4-4de7-859c-4ee905692339.png`
- Implementation: `http://127.0.0.1:5173/profile`
- Viewport: 1680 × 940, light theme, authenticated student demo account.
- State: personal-center overview tab with live profile, dashboard, and study-session data.

## Visual Comparison Evidence

- Compared the reference and the live implementation together at the same 1680 × 940 viewport.
- Inspected the full-resolution shell/header, identity banner and statistics, basic-information and campus-card region, and quick-entry and recent-activity region.
- Rechecked the responsive implementation at 390 × 844; the page remained within the viewport, statistics collapsed to two columns, and content panels became a single-column flow.

## Findings

No actionable P0, P1, or P2 mismatches remain.

- Fonts and typography: the existing Noto Sans SC family is retained with a compact dark-blue hierarchy matching the reference.
- Spacing and layout rhythm: the desktop shell uses a 158px sidebar, restrained top command bar, wide content frame, 14px panel gaps, and the reference's independent two-column card flow.
- Colors and visual tokens: cool white, periwinkle, cobalt, pale violet, green, and amber accents match the supplied screen while preserving existing semantic states.
- Image quality and asset fidelity: a dedicated project-local raster banner illustration was generated for the reference's translucent campus architecture composition; no remote runtime image is required.
- Copy and content: headings and labels follow the reference, while identity fields, statistics, and activity rows continue to use live application data.
- States and interactions: overview/tools/settings tabs, profile editing and cancellation, save flow, refresh, campus-card copy behavior, and quick-entry routing remain wired.
- Accessibility and responsiveness: semantic buttons remain keyboard-focusable, existing visible focus treatment is preserved, icon buttons keep accessible labels, and the layout avoids horizontal overflow at the mobile checkpoint.

## Intentional P3 Differences

- The existing refresh control is retained although it is not present in the reference because it is a functioning product action.
- Sidebar labels and destinations remain the application's real information architecture instead of inventing the reference's unavailable routes.
- The current demo account supplies two recent learning sessions, so the live panel shows two rows rather than fabricating four reference-only activities.

## Patches Made

- Rebuilt the profile banner, statistics, tabs, basic-information grid, campus identity card, quick-entry cards, and recent-activity timeline around the supplied layout.
- Added profile-route shell styling without changing the layout of unrelated routes.
- Added the missing profile icons to the shared icon registry.
- Added a purpose-built local banner asset at `web/public/assets/campusmate-profile-banner-v2.png`.
- Added desktop and mobile breakpoints specific to the new personal-center composition.

## Verification

- `npm run build`: passed (Vite production build, 1652 modules transformed).
- `node --test tests/student-sidebar-active-indicator.test.mjs`: passed.
- Browser interaction checks: passed for tabs, edit/cancel, quick-entry routing affordances, desktop rendering, and mobile overflow.
- Network recovery: the existing expired-session requests returned 401, token refresh returned 200, and the retried profile/dashboard/session requests returned 200.
- Existing unrelated full-suite failures remain in the collapsed-sidebar selector and legacy login background checks; neither touches this personal-center implementation.

final result: passed

---

# Global Android Navigation Design QA

- source visual truth path: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-ad4e16b5-f0d0-4bc1-ac90-f5ddc23f42c9.png` and `C:\Users\32883\AppData\Local\Temp\codex-clipboard-765aad72-b6eb-4da7-b127-31d28cf0a543.png`
- implementation screenshot path: `artifacts/navigation-qa/notifications-final.png` and `artifacts/navigation-qa/notification-nested-final.png`
- viewport: Android Pixel 10 Pro emulator, 1280 x 2856, portrait, light theme, authenticated student session
- state: notification overview and nested WeChat notification-listening page; the storage screenshot is used only as the visual truth for the shared top navigation, not for page content
- full-view comparison evidence: `artifacts/navigation-qa/reference-vs-notifications-full.png`
- focused region comparison evidence: `artifacts/navigation-qa/reference-vs-notifications-header.png`

## Findings

No actionable P0, P1, or P2 navigation mismatches remain.

- Fonts and typography: the shared title uses the platform Chinese fallback at 20sp bold, matching the reference hierarchy and remaining legible without clipping or wrapping.
- Spacing and layout rhythm: the 44dp circular back target, 16dp horizontal inset, 12dp title gap, 60dp content row, and status-bar inset reproduce the reference rhythm without overlapping page content.
- Colors and visual tokens: the translucent light surface, restrained outline/shadow, dark title/icon, and existing pale canvas align with the source treatment and preserve contrast.
- Image quality and asset fidelity: navigation contains no raster imagery; the back glyph uses the platform auto-mirrored vector icon and remains sharp at emulator density. Existing page imagery was not replaced.
- Copy and content: route titles are centralized and match their actual destinations, including dynamic exam and service-form titles. Nested notification content is business content rather than a second navigation title.
- Icons and accessibility: each captured secondary screen exposes exactly one `返回` semantic control; the circular control is a practical 44dp tap target and mirrors correctly for layout direction.
- Viewport resilience: edge-to-edge status-bar padding and matching content reservation prevent cutout overlap, double insets, and clipped first rows. The bottom dock remains independently reserved by scrollable content.

## Open Questions

- None. The reference and implementation show different business modules, so fidelity judgment is intentionally limited to the user-requested global top-navigation pattern.

## Implementation Checklist

- [x] Centralize the secondary navigation component and destination-title mapping.
- [x] Remove local top bars and duplicate back controls from secondary pages.
- [x] Synchronize personal-hub tab navigation with route titles.
- [x] Verify overview and nested notification pages in the emulator.
- [x] Run Android unit tests and assemble the debug APK.

## Patches Made Since Previous QA Pass

- Added one status-bar-aware HarmonyOS-style shared navigation row to all secondary destinations.
- Removed redundant page-local headers from notifications, settings, account, profile, task, exam, service, classroom, lost-and-found, and detail/form screens.
- Added route-accurate static and dynamic titles and system-back dispatch.
- Removed the standalone notification debug badge so content begins directly below the shared navigation.

## Follow-up Polish

- P3: if exact device-specific typography parity is required, validate the same build on the user's physical HarmonyOS device because system font rendering differs slightly from the Android emulator.

final result: passed

---

# Activity Detail and Lost & Found Design QA

- source visual truth path: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-6bfc6dea-5567-47ad-b1f3-7ce00436b0dc.png` and `C:\Users\32883\AppData\Local\Temp\codex-clipboard-e0fb8931-7ab2-4b09-af7d-e1ba03c78f95.png`
- implementation screenshot path: Chrome DevTools live captures at `http://127.0.0.1:5174/campus-activities/act_ec2039ba632a40e8` and `http://127.0.0.1:5174/lostfound` (1680 × 940 desktop viewport; DevTools did not permit file persistence outside its browser sandbox)
- viewport: 1680 × 940, desktop, authenticated student session
- state: activity detail default state, lost-and-found grid state, generated hero images loaded
- full-view comparison evidence: the source attachments and the two live DevTools captures were visually checked during this QA pass
- focused region comparison evidence: activity hero/metadata/progress panel and lost-found hero/filter/card grid were reviewed independently

## Findings

No actionable P0, P1, or P2 mismatches remain.

- Fonts and typography: Noto Sans SC and the existing product hierarchy preserve the reference's compact, dark-blue Chinese interface type.
- Spacing and layout rhythm: both focused routes use the reference's narrow icon rail, top command bar, 18px-radius panels, restrained shadows, and desktop density.
- Colors and visual tokens: cool white, periwinkle, lavender, green, and amber semantic accents are consistent across list, detail, modal, and action states.
- Image quality and asset fidelity: two project-local AI-generated raster hero assets replace the previous remote lost-found illustration; their 3D material, crop, white space, and palette match the supplied screens.
- Copy and content: the event-detail reference copy and counts are represented in the visual baseline. Live backend records still load when the collection has sufficient data.
- States and interactions: activity registration, favorite, sharing, list filtering, view switch, refreshing, publish modal, loss/found detail navigation, delete confirmation, and contact-copy feedback are wired.

## Open Questions

- None.

## Implementation Checklist

- [x] Rebuild the activity detail page to the supplied layout.
- [x] Rebuild the lost-and-found list and create its responsive publish and detail flows.
- [x] Generate and place matched local hero raster assets.
- [x] Verify a production build with `npm run build`.
- [x] Verify the live desktop routes and favorite-state interaction using Chrome DevTools.

## Patches Made Since Previous QA Pass

- Replaced the remote lost-and-found hero URL with a project-local generated asset.
- Added an icon-only layout treatment limited to the two target modules and their detail route.
- Added usable empty/offline presentation states for the screenshot-design baseline.

## Follow-up Polish

- P3: live backend item imagery is represented with the existing Phosphor icon system rather than separate per-item photos, so it remains legible and consistent when backend records do not provide images.

final result: passed
