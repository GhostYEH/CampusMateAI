# Collapsed Student Sidebar Top Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Center the student sidebar brand mark and profile avatar on the same 48 px desktop collapsed rail without changing expanded navigation, mobile drawer, routes, or interactions.

**Architecture:** Replace the ineffective shared-selector fix with authoritative student-specific collapsed rules in `student-home.css`, which is loaded after the shared and redesign styles. Keep the Vue shell untouched and use one source-level Node regression test to assert the final desktop-collapsed CSS contract at the actual winning specificity.

**Tech Stack:** Vue 3, CSS, Node.js built-in test runner, Vite 6.

## Global Constraints

- Scope compact alignment to `.student-layout.collapsed` above the existing 900 px mobile breakpoint.
- Use a 46 px brand mark and a 44 px avatar inside the sidebar's 48 px content rail.
- Keep the profile button's full width, soft background, radius, click handler, and route behavior.
- Do not modify `AppShell.vue`, navigation data, icon assets, active-indicator styles, or unrelated working-tree changes.
- Add no dependencies.

---

### Task 1: Make The Regression Test Cover The Winning Student Styles

**Files:**
- Modify: `web/tests/collapsed-sidebar-icon-dimensions.test.mjs`
- Test: `web/tests/collapsed-sidebar-icon-dimensions.test.mjs`

**Interfaces:**
- Consumes: the CSS source in `web/src/styles/student-home.css` and the existing `declarationsFor(css, selector)` helper.
- Produces: a regression contract for the desktop-only `.student-layout.collapsed` brand and profile rules.

- [x] **Step 1: Replace the generic-selector test with a desktop media-block test**

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

function atRuleBody(css, signature) {
  const start = css.indexOf(signature);
  assert.notEqual(start, -1, `Missing CSS at-rule: ${signature}`);
  const open = css.indexOf("{", start);
  let depth = 0;
  for (let index = open; index < css.length; index += 1) {
    if (css[index] === "{") depth += 1;
    if (css[index] === "}") depth -= 1;
    if (depth === 0) return css.slice(open + 1, index);
  }
  assert.fail(`Unclosed CSS at-rule: ${signature}`);
}

test("centers the student brand and avatar on the desktop collapsed rail", async () => {
  const css = await readFile(path.join(webRoot, "src", "styles", "student-home.css"), "utf8");
  const desktopCollapsed = atRuleBody(css, "@media(min-width:901px)");
  const brand = declarationsFor(desktopCollapsed, ".student-layout.collapsed .sidebar .brand");
  const brandMark = declarationsFor(desktopCollapsed, ".student-layout.collapsed .brand-mark");
  const profile = declarationsFor(desktopCollapsed, ".student-layout.collapsed .profile-mini");
  const avatar = declarationsFor(desktopCollapsed, ".student-layout.collapsed .profile-mini .avatar");
  const hiddenProfileContent = declarationsFor(
    desktopCollapsed,
    ".student-layout.collapsed .profile-mini-copy,.student-layout.collapsed .profile-mini>svg",
  );

  assert.match(brand, /padding-inline\s*:\s*0/i);
  assert.match(brand, /justify-content\s*:\s*center/i);
  assert.match(brandMark, /width\s*:\s*46px/i);
  assert.match(brandMark, /height\s*:\s*46px/i);
  assert.match(brandMark, /flex\s*:\s*0\s+0\s+46px/i);
  assert.match(profile, /grid-template-columns\s*:\s*minmax\(0\s*,\s*1fr\)/i);
  assert.match(profile, /gap\s*:\s*0/i);
  assert.match(profile, /padding-inline\s*:\s*0/i);
  assert.match(profile, /justify-items\s*:\s*center/i);
  assert.match(avatar, /width\s*:\s*44px/i);
  assert.match(avatar, /height\s*:\s*44px/i);
  assert.match(avatar, /flex\s*:\s*0\s+0\s+44px/i);
  assert.match(hiddenProfileContent, /display\s*:\s*none/i);
});
```

- [x] **Step 2: Run the focused test and verify the red state**

Run: `node --test tests/collapsed-sidebar-icon-dimensions.test.mjs`

Expected: FAIL with `Missing CSS at-rule: @media(min-width:901px)` because the winning student stylesheet does not yet define a desktop collapsed alignment contract.

---

### Task 2: Implement The Desktop Collapsed Alignment Contract

**Files:**
- Modify: `web/src/styles.css:162-173`
- Modify: `web/src/styles/student-home.css:24-25`
- Test: `web/tests/collapsed-sidebar-icon-dimensions.test.mjs`

**Interfaces:**
- Consumes: the existing 82 px collapsed sidebar, 17 px sidebar padding, `.brand`, `.profile-mini`, `.brand-mark`, and `.avatar` primitives.
- Produces: one centered 48 px visual rail for the brand, profile, primary navigation, and bottom actions at desktop widths.

- [x] **Step 1: Remove the ineffective generic rules from the shared stylesheet**

Delete this prior attempted fix from `web/src/styles.css`:

```css
.sidebar .brand-mark{
  width:46px;
  height:46px;
  flex:0 0 46px;
}
.sidebar .avatar{
  width:44px;
  height:44px;
  flex:0 0 44px;
}
.collapsed .profile-mini-copy,.collapsed .profile-mini>svg{display:none}
.collapsed .profile-mini{justify-content:center;gap:0}
```

- [x] **Step 2: Add the authoritative student desktop-collapsed rules**

Add immediately after `.student-layout .sidebar-bottom{gap:1px}` in `web/src/styles/student-home.css`:

```css
@media(min-width:901px){
  .student-layout.collapsed .sidebar .brand{padding-inline:0;justify-content:center}
  .student-layout.collapsed .brand-mark{width:46px;height:46px;flex:0 0 46px}
  .student-layout.collapsed .profile-mini{grid-template-columns:minmax(0,1fr);gap:0;padding-inline:0;justify-items:center}
  .student-layout.collapsed .profile-mini .avatar{width:44px;height:44px;flex:0 0 44px}
  .student-layout.collapsed .profile-mini-copy,.student-layout.collapsed .profile-mini>svg{display:none}
}
```

- [x] **Step 3: Run the focused test and verify the green state**

Run: `node --test tests/collapsed-sidebar-icon-dimensions.test.mjs`

Expected: PASS with one test and zero failures.

- [x] **Step 4: Run the complete Web Node test suite**

Run: `node --test`

Expected: the collapsed-sidebar test passes. If an unrelated pre-existing test fails, capture its exact name and failure without changing unrelated production code.

- [x] **Step 5: Build the production Web bundle**

Run: `npm run build`

Expected: Vite exits with code 0 and writes the production bundle to `web/dist`.

- [x] **Step 6: Verify the rendered desktop and mobile geometry**

Open the authenticated student shell at 1440 x 944, collapse the desktop sidebar, and read the rendered element bounds.

Expected:

- The brand mark is 46 x 46 px and the profile avatar is 44 x 44 px.
- Brand, avatar, every navigation icon, and every bottom action icon have the same rendered `centerX`.
- Expanded desktop retains its 47 x 47 px brand and 49 x 49 px avatar with profile text and caret visible.
- At 820 x 944, the mobile drawer remains 270 px wide, keeps its expanded labels, and produces no horizontal document overflow.

- [x] **Step 7: Review the focused diff**

Run:

```powershell
git diff --check -- web/src/styles.css web/src/styles/student-home.css web/tests/collapsed-sidebar-icon-dimensions.test.mjs
git diff -- web/src/styles.css web/src/styles/student-home.css web/tests/collapsed-sidebar-icon-dimensions.test.mjs
```

Expected: no whitespace errors; the diff contains only removal of the ineffective shared rules, the scoped student collapsed rules, and the corrected regression test.

- [x] **Step 8: Commit the focused implementation**

```powershell
git add -- web/src/styles.css web/src/styles/student-home.css web/tests/collapsed-sidebar-icon-dimensions.test.mjs docs/superpowers/plans/2026-08-11-collapsed-sidebar-icon-dimensions.md design-qa.md
git commit -m "fix: align collapsed student sidebar header"
```
