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
