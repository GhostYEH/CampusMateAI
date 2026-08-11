# Campus News Hub Design QA

- Source visual truth: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-cdd4f785-03fa-4e47-a3c0-13270a6ad128.png`
- Implementation evidence: `F:\demo1\.worktrees\campus-news-hub\artifacts\news-main.png`, `news-bottom.png`, `news-no-result.png`, `news-360dp-list.png`, and `news-font130-target2.png`
- Comparison evidence: `F:\demo1\.worktrees\campus-news-hub\artifacts\campus-news-comparison.png` and `campus-news-focused-comparison.png`
- Viewport and states: Pixel 10 Pro at 426.7dp, plus 360x800dp; populated/latest, scrolled-to-bottom, search with IME, no-result search, and 130% system font scale.

## Findings

No actionable P0, P1, or P2 findings remain. Chinese typography is readable at both tested font scales; the category row scrolls at 360dp; app theme tokens preserve the cool-neutral and blue-violet direction; all controls retain practical touch targets; and the last card scrolls above the floating dock.

## Open Questions

- The reference does not specify loading, refresh-error, or secondary-page detail visuals; those use existing shared components and were code/build verified.
- At 130% font scale on a 360dp viewport, the pre-existing global dock label `AI Campus Assistant` becomes visually tight, but it does not overlap campus-news content or block navigation.

## Implementation Checklist

- [x] Verify status-bar clearance, search, categories, sorting/read controls, populated cards, IME, no-result state, final content scroll, 360dp resilience, and 130% text scaling.
- [x] Compare source and implementation in full-view and focused composite images.

## Follow-up Polish

- Optional P3: shorten or responsively size the existing global dock's longest label for additional comfort at large system font scales.

Final result: passed

# Collapsed Student Sidebar Top Alignment Design QA

- Source visual truth: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-01e90251-e5fa-41f6-b49d-301c76c3d388.png`
- Implementation screenshot: `F:\demo1\artifacts\sidebar-qa\sidebar-after-profile.png`
- Viewport: 1440 x 944 desktop (DPR 1), authenticated student mock session at `/profile`, collapsed desktop sidebar.
- Comparison evidence: `F:\demo1\artifacts\sidebar-qa\sidebar-comparison.png` and `sidebar-top-comparison.png`.

## Findings

No actionable P0, P1, or P2 mismatches remain in the requested brand-and-avatar alignment scope.

- The visual rail center is `40.6px`; the 46px brand mark, 44px avatar, eight primary navigation icons, and four bottom action icons have the same `centerX`, with a maximum measured offset of `0px`.
- Existing tokens, Phosphor cap icon, text avatar, labels, tooltips, profile routes, click handlers, and expanded desktop behavior are unchanged.
- At 820 x 944, the mobile drawer remains 270px wide, retains its expanded labels and 47/49px top visuals, and has `0px` horizontal document overflow.

## Implementation Checklist

- [x] Add desktop-only collapsed rules at the winning student stylesheet specificity and replace the regression test with coverage for those final rules.
- [x] Verify focused test behavior, rendered element bounds at 1440 x 944, expanded desktop and mobile drawer behavior, and source/implementation comparison images.

## Patches Made Since Previous QA Pass

- Reset the collapsed brand horizontal padding and centered its 46px square.
- Replaced the collapsed profile's retained three-column grid with one centered track.
- Reset collapsed profile horizontal padding, fixed the avatar to a 44px square, and scoped profile-copy/caret hiding to desktop student collapsed mode.

## Follow-up Polish

- No top-rail P3 items remain.

Final result: passed

# Tasks and Focus visual QA

- Source visual truth: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-4e19b777-b07f-4bba-b974-5208d8205c79.png` and `C:\Users\32883\AppData\Local\Temp\codex-clipboard-807bbdcc-c992-456c-9d79-5f6c2c99df56.png`
- Implementation screenshots: `qa/tasks.png` and `qa/focus-final.png`
- Full-view comparison evidence: `qa/tasks-comparison.png` and `qa/focus-comparison.png`
- Viewport: Android emulator, 1080 x 2400, light theme, unauthenticated/stale-backend error state.

## Findings

- [P3] Without an authenticated backend session, task and focus reference content is correctly replaced by an explicit retry state. Verify with a signed-in account that has personal tasks and study sessions before release acceptance.
- [P3] The reference has richer decorative micro-illustrations around the focus header and task cards. The implementation preserves the blue-violet cards, ring, chrome, and a transparent goal illustration; exact ornamental parity remains optional polish.

## Required fidelity surfaces

- Typography: strong bold page titles, 25:00 timer hierarchy, compact mode labels, and muted secondary copy use the app's Chinese system fallback.
- Layout: single-column mobile cadence, large rounded primary card, separate task/date/search modules, floating action placement, and reserved bottom-dock space were verified.
- Visual tokens: pale lavender canvas, white cards, blue-violet actions, orange deadline accents, and soft indigo tracks were verified.
- Asset fidelity: `focus_goal_illustration.png` is a clean transparent raster asset rendered in the goal card.
- Content: task counts, rows, records, goals, and statistics are backend-sourced; empty/error wording explains unavailable backend state.

## Implementation Checklist

1. Sign in against a reachable HTTPS backend and create at least one personal task.
2. Verify task creation, edit, completion, deletion, calendar, and focus flows write and reread the same server record.
3. Verify start, pause, resume, finish, daily-goal update, and recent-record sync on a second device/account session.

## Follow-up Polish

- Add optional background sparkle/decorative ring accents only if exact ornamental parity is required after real-data acceptance testing.

Patches made since the previous QA pass: rebuilt the task dashboard, added the task calendar route, rebuilt the focus timer, added backend daily-goal and session flows, added the focus-goal raster asset, and restricted cleartext networking to the Debug emulator bridge.

Final result: passed
