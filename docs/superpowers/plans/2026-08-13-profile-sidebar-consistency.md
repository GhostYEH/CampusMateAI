# Profile Sidebar Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the student sidebar at the same width and density when navigating to the personal center.

**Architecture:** The student shell remains the single owner of sidebar and topbar layout. The profile stylesheet is constrained to profile content and may not override shell elements through `:has(.profile-redesign)`.

**Tech Stack:** Vue 3, CSS, Node.js built-in test runner, Vite

## Global Constraints

- Desktop expanded sidebar remains `286px`.
- Desktop collapsed sidebar remains `82px` and changes only through the existing user control.
- Do not alter personal-center content, data flow, routes, or mobile navigation behavior.

---

### Task 1: Guard and remove profile shell overrides

**Files:**
- Create: `web/tests/profile-sidebar-consistency.test.mjs`
- Modify: `web/src/styles/student-profile-reference.css:439-537`

**Interfaces:**
- Consumes: `.student-layout` and `.student-layout.collapsed` shell rules from `web/src/styles/student-home.css`.
- Produces: a profile stylesheet that contains no `.app-layout:has(.profile-redesign)` shell overrides.

- [x] **Step 1: Write the failing regression test**

```js
test("keeps the student shell unchanged on the personal center", async () => {
  const css = await readFile(path.join(webRoot, "src", "styles", "student-profile-reference.css"), "utf8");
  assert.doesNotMatch(css, /\.app-layout(?::has|\.collapsed:has)\(\.profile-redesign\)/);
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `node --test tests/profile-sidebar-consistency.test.mjs`

Expected: FAIL because `student-profile-reference.css` contains `.app-layout:has(.profile-redesign)`.

- [x] **Step 3: Remove the profile-specific shell media block**

Delete the desktop `@media (min-width: 901px)` block whose selectors start with `.app-layout:has(.profile-redesign)` or `.app-layout.collapsed:has(.profile-redesign)`.

- [x] **Step 4: Run focused and regression tests**

Run: `node --test tests/profile-sidebar-consistency.test.mjs tests/collapsed-sidebar-icon-dimensions.test.mjs tests/login-shell-regression.test.mjs`

Expected: all tests PASS.

- [x] **Step 5: Run production build**

Run: `npm run build`

Expected: Vite exits with code 0.
