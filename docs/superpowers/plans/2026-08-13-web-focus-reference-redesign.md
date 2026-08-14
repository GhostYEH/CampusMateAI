# Web Focus Reference Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the existing Vue Web `/study` screen to match the supplied desktop reference while preserving current study interactions and isolating all changes from other clients.

**Architecture:** Keep `StudentStudyView.vue` as the data and interaction owner, reorganize only its template, and add a dedicated `study-reference.css` stylesheet. Add a route-derived `study-mode` class to the existing Web shell so shared chrome can be adjusted only on `/study`.

**Tech Stack:** Vue 3, Vite, Pinia, Phosphor icons, CSS Grid, Node test runner.

## Global Constraints

- Only Web files and task documentation may change.
- Existing student API function signatures and route paths remain unchanged.
- The supplied 1678×941 screenshot is the visual source of truth.
- Use the existing Web robot illustration asset.
- All page styling must be scoped by `.study-reference` or `.study-mode`.

---

### Task 1: Lock the reference contract with a failing test

**Files:**
- Create: `web/tests/study-reference-layout.test.mjs`

**Interfaces:**
- Consumes: `StudentStudyView.vue`, `AppShell.vue`, `main.js`, `study-reference.css`.
- Produces: source-level regression coverage for required structure and isolation.

- [ ] Write assertions for `study-reference`, top/main/metric/bottom grids, interactive handlers, `study-mode`, stylesheet import, desktop grid ratios, and responsive breakpoint.
- [ ] Run `node --test tests/study-reference-layout.test.mjs` from `web` and confirm it fails because the new stylesheet and scope are absent.

### Task 2: Recompose the Web study template and shell scope

**Files:**
- Modify: `web/src/views/student/StudentStudyView.vue`
- Modify: `web/src/views/AppShell.vue`

**Interfaces:**
- Consumes: existing refs, computed values, API functions, and `UiIcon`.
- Produces: screenshot-matched semantic regions without changing the service layer.

- [ ] Add `study-mode` to the shell root when `route.path === "/study"`.
- [ ] Recompose the study page into the reference heading, focus stage, study plan, metric strip, recent records, trend, and pending-plan panels.
- [ ] Preserve bindings for preset selection, custom duration, start, pause/resume, finish, goal input, AI breakdown, toggles, refresh, and task selection.

### Task 3: Implement isolated reference styling

**Files:**
- Create: `web/src/styles/study-reference.css`
- Modify: `web/src/main.js`

**Interfaces:**
- Consumes: class names from Task 2 and existing Phosphor icon components/assets.
- Produces: desktop reference layout plus tablet/mobile collapse rules.

- [ ] Import the dedicated stylesheet after existing student styles.
- [ ] Implement scoped shell dimensions and page background under `.study-mode`.
- [ ] Implement the reference card hierarchy, 5:5 top split, 4-up metrics, 3-column bottom section, typography, spacing, controls, and states.
- [ ] Add breakpoints at 1320px, 1080px, 900px, and 700px to prevent overflow and collapse the page cleanly.

### Task 4: Verify behavior and visual parity

**Files:**
- Create: `design-qa.md` only after opening both reference and implementation captures.

**Interfaces:**
- Consumes: built app and supplied reference image.
- Produces: passing tests, production build, same-viewport screenshot, and design QA result.

- [ ] Run `node --test tests/*.test.mjs` from `web` and resolve regressions.
- [ ] Run `npm run build` from `web` and resolve build errors.
- [ ] Run the Web app, load `/study` with a local student session, and capture 1678×941.
- [ ] Compare the implementation and reference together, document P0-P3 differences in `design-qa.md`, fix P0-P2, recapture, and mark `final result: passed` only when the blocking differences are resolved.
- [ ] Run `git diff --name-only` and confirm no Android, HarmonyOS, wx, or backend file was changed by this task.
