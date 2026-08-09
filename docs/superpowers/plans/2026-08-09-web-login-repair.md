# Web Login Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the Vue Web client's login screen and remove the deleted image dependency.

**Architecture:** Keep the existing login page structure and use its public MP4 asset as the decorative media. Repair the router by registering the existing student home component, and remove the stale image declaration from the unrelated home-card style.

**Tech Stack:** Vue 3, Vue Router 4, Vite 6, Node.js built-in test runner.

## Global Constraints

- Do not restore `campus-night.jpg`.
- Do not modify the backend API or login request behavior.
- Preserve the existing `login-campus.mp4` public asset.

---

### Task 1: Add regression coverage for page bootstrap and background assets

**Files:**
- Create: `web/tests/login-shell-regression.test.mjs`
- Modify: `web/src/router.js:31`
- Modify: `web/src/views/LoginView.vue:24`
- Modify: `web/src/styles.css:237-249`

**Interfaces:**
- Consumes: Vite's `ssrLoadModule`, Vue Router's exported router, `/assets/login-campus.mp4`.
- Produces: A Node test that loads the real router and confirms the public video and removed image dependency.

- [ ] **Step 1: Write the failing test**

```js
test('loads the home route and uses the public login video', async () => {
  const { default: router } = await vite.ssrLoadModule('/src/router.js');
  assert.equal(router.resolve('/home').matched.at(-1).components.default.__name, 'StudentHomeView');
  assert.match(loginView, /<video[^>]+src="\/assets\/login-campus\.mp4"/);
  assert.doesNotMatch(styles, /campus-night\.jpg/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/login-shell-regression.test.mjs`

Expected: FAIL because the router evaluates undefined `HomeRouteView`, the login template has no video, and the stylesheet still references `campus-night.jpg`.

- [ ] **Step 3: Write minimal implementation**

```js
// router.js
{ path: 'home', component: StudentHomeView, meta: { roles: ['student', 'admin'] } }
```

```vue
<div class="login-media"><video src="/assets/login-campus.mp4" autoplay muted loop playsinline aria-hidden="true"></video></div>
```

```css
/* remove only background-image:url("/assets/campus-night.jpg") */
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/login-shell-regression.test.mjs`

Expected: PASS with no failing subtests.

- [ ] **Step 5: Commit**

```bash
git add web/tests/login-shell-regression.test.mjs web/src/router.js web/src/views/LoginView.vue web/src/styles.css
git commit -m "fix: restore web login background and home route"
```

### Task 2: Build and serve the repaired client

**Files:**
- Modify: generated `web/dist` output only through `npm run build`.

**Interfaces:**
- Consumes: the repaired source and Vite scripts defined by `web/package.json`.
- Produces: a successful production build and development-server responses for the login entry point and MP4 asset.

- [ ] **Step 1: Run production build**

Run: `npm run build`

Expected: exit code 0.

- [ ] **Step 2: Start Vite temporarily and request the entry point and video**

Run: `npm run dev -- --host 127.0.0.1`

Expected: `GET /` returns 200 HTML and `GET /assets/login-campus.mp4` returns 200 with a video content type.

- [ ] **Step 3: Record verification output**

Expected: report the exact test, build, and HTTP response results; do not alter backend startup state.
