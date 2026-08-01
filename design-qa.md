# Student workspace redesign QA

## Comparison target

- Source visual truth: `C:/Users/32883/AppData/Local/Temp/codex-clipboard-cd83bd5f-b92b-4a6c-b168-5fbd18dc93b5.png` (个人中心), `C:/Users/32883/AppData/Local/Temp/codex-clipboard-7a41edd2-01a6-4d47-b7e4-9dcda8a1ed35.png` (空教室), `C:/Users/32883/AppData/Local/Temp/codex-clipboard-89f1beca-763f-4bc5-90f9-980b456cbb9e.png` (专注模式)
- Implementation screenshots: `web/qa/redesign/profile-viewport.png`, `web/qa/redesign/classrooms-viewport.png`, `web/qa/redesign/study-viewport.png`
- Viewport: 1680 × 944 CSS pixels, desktop, authenticated `student_demo` state, light theme
- State: profile data loaded; classroom API returned its current empty list; study history loaded with existing server record

## Full-view comparison evidence

The three implementation captures were compared in the same visual review pass as their corresponding reference images. The shared shell, blue-white campus workspace, left navigation, top command bar, heading rhythm, rounded panels, quiet shadows, warm status accents, and primary action treatment are consistent with the reference direction.

The wide desktop composition now follows the references more closely: the profile quick-access cards sit under the left information column, while the identity/activity column continues independently; the study page places the plan and four metrics on the right of the focus stage, then uses a full-width records/trend/todo row.

## Focused region comparison evidence

- Profile: identity banner, tab strip, basic-information table, campus identity card, activity card, and six quick-access cards were checked for alignment and readable Chinese copy.
- Empty classroom: five-field query bar, summary metrics, result toolbar, empty state, tips, and source note were checked. The implementation intentionally shows a truthful empty state because the current classroom endpoint returns no records.
- Study: timer/preset/action cluster, right-side study plan, metrics row, trend bars, recent records, todo card, and footer note were checked. The implementation uses the existing CampusMate illustration asset as a soft decorative background; the reference's desk-clock illustration is not available as a standalone project asset.

## Findings

- No actionable P0/P1/P2 findings remain.
- [P3] Classroom populated-result imagery cannot be compared in the current runtime because the API returns an empty list. The result-card renderer still accepts `image_url`, `image`, and `photo_url` when a real school data source supplies them; no fake classroom records were added.
- [P3] The focus illustration is intentionally reused from the existing CampusMate asset rather than introducing a new unmaintained image or a CSS/emoji approximation.

## Patches made since the previous QA pass

- Rebuilt the profile, empty-classroom, and study-companion views around the reference information hierarchy and real repository/API states.
- Reworked the student shell copy and reduced-motion class handling.
- Added shared redesign tokens, panel/button states, loading/error/empty/success feedback, responsive breakpoints, and interaction transitions.
- Added missing Phosphor icon mappings used by the classroom facilities and study controls.
- Corrected default classroom/study date keys to use local calendar dates instead of UTC.
- Tightened wide-screen profile and study composition after screenshot comparison.

## Implementation checklist

- [x] Desktop full-view comparison at the reference viewport
- [x] Focused comparison of typography, spacing/layout rhythm, colors/tokens, imagery, and app-specific copy
- [x] Loading, error, empty, success, disabled, and interaction states represented
- [x] Existing API/repository data preserved; no fabricated classroom results
- [x] Reduced-motion preference preserved and wired to the page shell
- [x] Production build verified with `npm run build`
- [x] Browser console checked on all three routes with no runtime errors

final result: passed

## Campus activity, notice and AI counselor reference QA — 2026-08-01

- Source visual truth: the three supplied CampusMate reference screenshots in `C:\Users\32883\AppData\Local\Temp\`.
- Desktop evidence: `F:\demo1\artifacts\qa-activities-1680-v5.png`, `F:\demo1\artifacts\qa-notifications-1680-final.png`, `F:\demo1\artifacts\qa-counselor-1680-final-v2.png`.
- Responsive evidence: `F:\demo1\artifacts\qa-activities-390-v2.png`, `F:\demo1\artifacts\qa-notifications-390-v2.png`, `F:\demo1\artifacts\qa-counselor-390-v2.png`.
- Desktop viewport: 1680 × 950 CSS px. Mobile viewport: 390 × 844 CSS px.
- States reviewed: populated activity cards, unread notice list with AI extraction preview, seeded AI counselor conversation, responsive mobile layouts.

### Findings

- The desktop activity page now matches the reference hierarchy: sidebar, heading/filter rhythm, 198 px feature banner, and two full-width 254 px activity cards.
- The notification page now uses one complete left panel and one equal-width extraction panel; the four-row draft preview and save footer match the supplied anatomy.
- The AI counselor page now uses the reference's top hero spanning the left two columns with the campus-help rail aligned at the top, followed by compact history, chat and recommendation surfaces.
- The pages use repository/API data, preserve loading/error/empty feedback, and keep the extraction and chat actions interactive.
- No actionable P0, P1 or P2 layout findings remain in the reviewed desktop state. Mobile screenshots show single-column stacking without a horizontal page scrollbar after the final responsive overrides.

### Patches made during this pass

- Rebuilt the activity, notification and counselor student views with natural Chinese reference content and functional interactions.
- Added the reference-matched campus activity, notice and AI counselor illustration assets under `web/public/assets/`.
- Added final specificity-safe responsive and desktop layout overrides at the end of `web/src/styles.css`.

final result: passed
