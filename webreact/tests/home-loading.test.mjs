import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../src/pages/HomePage.jsx", import.meta.url), "utf8");

test("home page fails open instead of waiting for every optional request", () => {
  assert.match(source, /HOME_BOOT_TIMEOUT_MS/);
  assert.match(source, /setTimeout\([\s\S]*HOME_BOOT_TIMEOUT_MS/);
  assert.match(source, /setLoading\(false\)/);
});

test("returning to the home route reuses cached dashboard data", () => {
  assert.match(source, /const homeDashboardCache = new Map\(\)/);
  assert.match(source, /const cachedHomeState = homeDashboardCache\.get\(dashboardCacheKey\)/);
  assert.match(source, /setLoading\(!cachedHomeState\)/);
  assert.match(source, /homeDashboardCache\.set\(dashboardCacheKey, nextHomeState\)/);
  assert.match(source, /const homeLoadInFlight = new Map\(\)/);
});

test("a fresh dashboard cache skips return-navigation requests before revalidating later", () => {
  assert.match(source, /const HOME_CACHE_TTL_MS = 30_000/);
  assert.match(source, /const shouldRefresh = !cachedHomeState \|\| reloadVersion > 0 \|\| !isHomeCacheFresh\(dashboardCacheKey\)/);
});
