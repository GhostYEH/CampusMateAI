import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DASHBOARD_STYLE_KEY,
  loadDashboardStyle,
  normalizeDashboardStyle,
  persistDashboardStyle,
} from "../src/features/dashboard/dashboardStyle.js";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, value); },
  };
}

test("dashboard style defaults unknown and missing values to classic", () => {
  assert.equal(normalizeDashboardStyle(undefined), "classic");
  assert.equal(normalizeDashboardStyle(""), "classic");
  assert.equal(normalizeDashboardStyle("arcade"), "classic");
  assert.equal(normalizeDashboardStyle("CLASSIC"), "classic");
});

test("dashboard style accepts only the two supported modes", () => {
  assert.equal(normalizeDashboardStyle("classic"), "classic");
  assert.equal(normalizeDashboardStyle("gamified"), "gamified");
});

test("dashboard style persists a normalized value", () => {
  const storage = memoryStorage();

  assert.equal(persistDashboardStyle(storage, "gamified"), "gamified");
  assert.equal(storage.getItem(DASHBOARD_STYLE_KEY), "gamified");
  assert.equal(loadDashboardStyle(storage), "gamified");

  assert.equal(persistDashboardStyle(storage, "unknown"), "classic");
  assert.equal(loadDashboardStyle(storage), "classic");
});
