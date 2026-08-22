# Web Course Screen Design QA

- Source visual truth: `C:/Users/32883/AppData/Local/Temp/codex-clipboard-6a6edfa9-583b-4e4f-9bc3-35bb052fc2e9.png`
- Implementation route: `http://127.0.0.1:4174/courses`
- Viewport: 1672 x 943 desktop plus narrow mobile, authenticated through the real `student_demo` login flow; backend returned 28 courses and 7 assignment records
- Implementation evidence: Chrome viewport capture from this QA run (inline tool capture; file export was denied by the browser tool)
- Full-view comparison: completed against the supplied 1672 x 943 reference
- Focused comparison: hero, statistics dock, toolbar, and course-card footer were readable in the full-size captures, so separate crops were not required

## Findings

- P0: none in the course view.
- P1: none remaining in the course view after moving the hero subject to the right and restoring text/illustration separation.
- P2: none remaining. The final hero crop uses the existing transparent course illustration to keep the title and statistics unobscured at the reference viewport.
- P3: live course ordering and percentages vary with API data; this is intentional product behavior rather than visual drift.
- P3: a bare `/courses` link redirects to `/login` without a saved session. This is expected route-guard behavior, not a course-page defect.

## Required Fidelity Surfaces

- Typography: local Noto Sans SC matches the reference's compact Chinese UI hierarchy; title, labels, metadata, and card text use comparable optical weights and truncation.
- Spacing and layout: reference-like 252 px shell, compact top bar, 3-column desktop card grid, 10-14 px gaps, 15-19 px radii, and a floating four-part statistics dock.
- Colors and tokens: pale blue-white canvas, indigo primary, mint success, subtle blue-gray borders, and low-elevation shadows match the supplied target.
- Image quality: the existing high-resolution transparent course illustration is reused as a real raster asset; no placeholder or CSS illustration was introduced.
- Copy and content: hero title, explanatory copy, statistics labels, search/sort controls, metadata, progress, and material count follow the reference.

## Patches Made

- Removed the non-reference eyebrow and tip banner.
- Rebuilt the hero with a right-aligned course illustration and floating statistics dock.
- Rebuilt course cards with course badge, ellipsis action, compact metadata, progress ring, material count, and chevron footer.
- Added keyboard-accessible whole-card navigation and responsive 3/2/1-column behavior.
- Rechecked real login, live data, course search, sorting, course-detail navigation, desktop layout, and narrow mobile layout.

## Verification

- `node --test tests/courses-reference-layout.test.mjs`: passed.
- `npm run build`: passed (Vite production build, 1670 modules transformed).
- Browser console: no warnings or errors on the checked course screen.
- Mobile Lighthouse snapshot: accessibility 93 and best practices 100.

final result: passed

## CampusMate three-page redesign QA (2026-08-18)

- Source visuals: user-provided task, forum, and create-post screenshots.
- Prototype routes: `/tasks`, `/community`, `/community/create` at 1440 x 900 with an authenticated student session.
- Evidence: `F:/demo1/artifacts/web-ui/tasks.png`, `community.png`, `community-create.png`, and `create-preview.png`.

### Findings

- P0/P1: none. Shared AppShell/sidebar/header stay fixed across all three routes; primary layouts match the reference hierarchy and responsive collapse rules.
- P2: none. Task hero uses a generated raster illustration; forum includes two right-rail cards and hot-topic strip; create page includes real image uploader, draft, preview, and publish states.
- P3: the backend was not running during the visual pass, so list screens intentionally rendered their existing error/empty states. API calls remain wired to the existing student service layer.

### Verification

- `npm run build`: passed (Vite production build, 1685 modules transformed).
- Playwright/Chrome visual pass: passed for all three routes at 1440 x 900.
- Interaction smoke checks: task “新建待办” opens and closes its modal; create-post title/body fill and “预览” open the live preview modal; category chips, draft button, toggles, upload control, report, search, sort, and navigation are wired.

final result: passed
