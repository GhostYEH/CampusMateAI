# CampusMate Home Footer Interaction Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with tests and build checkpoints.

**Goal:** Add the approved CampusMate footer information area and TRAE-style interactive brand canvas to the student home content column without changing the existing dashboard sections.

**Architecture:** `HomeFooter` is a composition boundary mounted after the existing quick-entry section. `FooterInfo` owns static links, contact cards, QR visuals, and smooth return-to-top behavior. `InteractiveBrand` owns its canvas lifecycle, fixed text slices, pointer velocity/inertia, local distortion field, reveal observer, resize/DPR handling, and motion/accessibility fallbacks.

**Tech Stack:** Vue 3 Composition API with `<script setup>`, Canvas 2D, `IntersectionObserver`, `ResizeObserver`, existing `UiIcon`, Vite, and Node's built-in test runner.

**Spec:** `C:/Users/32883/.codex/attachments/3b3f843a-5f27-4419-ba26-42d87df9a1d7/pasted-text.txt` (Codex task sheet: CampusMate home footer and TRAE-style interaction).

## Global Constraints

- Modify only the student home footer area; do not change Sidebar, Header, Hero, overview, priority panel, schedule panel, hot-topics panel, quick-entry content, other pages, or backend APIs.
- Footer width is 100% of the home main content column, never viewport-wide, fixed, or sticky.
- Normal brand text is a complete readable `CAMPUSMATE`; glitch is local to the pointer and uses horizontal slices, not a global cursor glow.
- Pointer movement data stays in ordinary local variables; animation work is not Vue-reactive per frame.
- Clean every `requestAnimationFrame`, `ResizeObserver`, `IntersectionObserver`, and pointer listener during component teardown.
- Respect `prefers-reduced-motion` and coarse pointers by keeping the brand text static and usable.
- Preserve unrelated pre-existing worktree changes.

---

### Task 1: Lock down the footer contract

**Files:**
- Create: `web/tests/home-footer.test.mjs`
- Create: `web/src/components/home/footer/HomeFooter.vue`
- Create: `web/src/components/home/footer/FooterInfo.vue`
- Create: `web/src/components/home/footer/InteractiveBrand.vue`

- [ ] Add static contract tests for the component split, existing routes, footer copy, Canvas lifecycle cleanup, pointer velocity, local slice distortion, reveal, resize/DPR, and reduced-motion/coarse-pointer fallbacks.
- [ ] Run `node --test tests/home-footer.test.mjs` and confirm it fails because the footer components do not exist yet.
- [ ] Implement `FooterInfo` with semantic footer sections, existing-route links, keyboard-focusable controls, deterministic QR-card visuals, and `document.scrollingElement.scrollTo({ behavior: "smooth" })`.
- [ ] Implement `InteractiveBrand` with an offscreen text canvas, stable 3–8px slices, Gaussian X/Y influence, alternating slice direction/noise, velocity-scaled amplitude, lerped pointer/settle state, and teardown-safe event/observer handling.
- [ ] Run the focused test again and confirm it passes.

### Task 2: Mount the footer and style the content-column layout

**Files:**
- Modify: `web/src/views/student/StudentHomeView.vue`
- Modify: `web/src/components/home/footer/HomeFooter.vue`
- Modify: `web/src/components/home/footer/FooterInfo.vue`
- Modify: `web/src/components/home/footer/InteractiveBrand.vue`

- [ ] Import and render `HomeFooter` immediately after `.student-quick-section`, keeping the existing quick-entry markup unchanged.
- [ ] Add white footer layout, link groups, contact cards, QR cards, return-to-top control, gradient brand area, `clamp()` sizing, focus-visible states, and responsive breakpoints for 320px, 768px, 1024px, and desktop widths.
- [ ] Keep footer reveal inside document flow and ensure the sidebar remains outside the footer's containing column.
- [ ] Re-run the focused test and `npm run build`.

### Task 3: Browser interaction and regression verification

**Files:**
- No additional production files; inspect the changed footer components and generated screenshots under `artifacts/web-ui/` only if needed.

- [ ] Start the existing Vite app with the repository's scripts and use the local Chrome Playwright setup to open `/home` with demo session state.
- [ ] Verify footer reveal after scrolling, complete brand text at rest, local slow/fast pointer distortion, settle after pointer stop, smooth recovery on leave, repeat enter/leave stability, keyboard focus, and mobile/coarse-pointer static fallback.
- [ ] Check console errors and capture desktop/mobile footer screenshots for visual review.
- [ ] Run `node --test tests/*.test.mjs` and `npm run build` after all changes.
- [ ] Inspect `git diff --stat` and `git status --short` to confirm only the intended Web files were changed by this task.
