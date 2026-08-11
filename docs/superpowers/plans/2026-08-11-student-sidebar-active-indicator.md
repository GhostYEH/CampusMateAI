# Student Sidebar Active Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the student sidebar active button's curved inset accent with a clean, vertically centered rounded bar.

**Architecture:** Keep the existing Vue template and navigation behavior unchanged. Add one focused Node regression test for the active-state CSS contract, then update only the active navigation styles in `student-redesign.css`.

**Tech Stack:** Vue 3, CSS, Node.js built-in test runner

## Global Constraints

- Keep the existing light-purple selected background, icon, label, spacing, radius, and routing behavior.
- Use `#5665f4` for a 3 px by 24 px indicator with fully rounded ends.
- Apply the indicator only to active primary navigation buttons in the student sidebar.
- Preserve collapsed and mobile sidebar behavior.
- Add no dependencies.

---

### Task 1: Refine The Active Navigation Indicator

**Files:**
- Create: `web/tests/student-sidebar-active-indicator.test.mjs`
- Modify: `web/src/styles/student-redesign.css:57-74`

**Interfaces:**
- Consumes: `.student-layout .sidebar nav button.active` from the existing student sidebar.
- Produces: `.student-layout .sidebar nav button.active::before`, a static decorative indicator that does not intercept pointer events.

- [x] **Step 1: Write the failing regression test**

```js
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function declarationsFor(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`));
  assert.ok(match, `Missing CSS rule: ${selector}`);
  return match[1];
}

test("draws the active sidebar accent as a centered rounded bar", async () => {
  const css = await readFile(path.join(webRoot, "src", "styles", "student-redesign.css"), "utf8");
  const active = declarationsFor(css, ".student-layout .sidebar nav button.active");
  const indicator = declarationsFor(css, ".student-layout .sidebar nav button.active::before");

  assert.doesNotMatch(active, /box-shadow\s*:\s*inset/i);
  assert.match(active, /position\s*:\s*relative/i);
  assert.match(indicator, /width\s*:\s*3px/i);
  assert.match(indicator, /height\s*:\s*24px/i);
  assert.match(indicator, /top\s*:\s*50%/i);
  assert.match(indicator, /transform\s*:\s*translateY\(-50%\)/i);
  assert.match(indicator, /border-radius\s*:\s*999px/i);
  assert.match(indicator, /background\s*:\s*#5665f4/i);
  assert.match(indicator, /pointer-events\s*:\s*none/i);
});
```

- [x] **Step 2: Run the test and verify the red state**

Run: `node --test tests/student-sidebar-active-indicator.test.mjs`

Expected: FAIL with `Missing CSS rule: .student-layout .sidebar nav button.active::before` because the separate indicator does not exist yet.

- [x] **Step 3: Implement the minimal CSS change**

```css
.student-layout .sidebar nav button.active {
  position: relative;
  color: #4655df;
  background: #eef0ff;
}

.student-layout .sidebar nav button.active::before {
  position: absolute;
  top: 50%;
  left: 0;
  width: 3px;
  height: 24px;
  border-radius: 999px;
  background: #5665f4;
  content: "";
  transform: translateY(-50%);
  pointer-events: none;
}
```

- [ ] **Step 4: Run focused and existing tests**

Run: `node --test tests/student-sidebar-active-indicator.test.mjs tests/login-shell-regression.test.mjs`

Expected: 3 tests pass, 0 fail.

Execution note: the new focused regression test and the existing route test pass. The existing login asset test fails because committed `web/src/styles.css` still references `/assets/campus-night.jpg`; this file was not changed as part of the sidebar work.

- [x] **Step 5: Build the web application**

Run: `npm run build`

Expected: Vite exits with code 0 and writes the production bundle to `web/dist`.

- [ ] **Step 6: Review the focused diff and commit**

```bash
git diff --check -- web/src/styles/student-redesign.css web/tests/student-sidebar-active-indicator.test.mjs docs/superpowers/plans/2026-08-11-student-sidebar-active-indicator.md
git add web/src/styles/student-redesign.css web/tests/student-sidebar-active-indicator.test.mjs docs/superpowers/plans/2026-08-11-student-sidebar-active-indicator.md
git commit -m "fix: refine student sidebar active indicator"
```
