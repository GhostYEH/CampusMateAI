import assert from "node:assert/strict";
import test from "node:test";

import {
  MAGICCLASS_AGENT_SETTINGS_KEY,
  loadMagicClassAgentSettings,
  saveMagicClassAgentSettings,
} from "../src/features/magicclass/agentSettingsModel.js";

function storage() {
  const values = new Map();
  return {
    getItem(key) { return values.get(key) ?? null; },
    setItem(key, value) { values.set(key, String(value)); },
  };
}

test("agent settings normalize persisted mode and roles", () => {
  const store = storage();
  store.setItem(MAGICCLASS_AGENT_SETTINGS_KEY, JSON.stringify({ mode: "auto", selectedRoleIds: ["default-4", "default-4", "unknown"] }));

  assert.deepEqual(loadMagicClassAgentSettings(store), {
    mode: "auto",
    selectedRoleIds: ["default-1", "default-4"],
  });
});

test("agent settings survive a save/load round trip and tolerate broken storage", () => {
  const store = storage();
  saveMagicClassAgentSettings({ mode: "preset", selectedRoleIds: ["default-5"] }, store);
  assert.deepEqual(loadMagicClassAgentSettings(store), {
    mode: "preset",
    selectedRoleIds: ["default-1", "default-5"],
  });
  assert.deepEqual(loadMagicClassAgentSettings({ getItem() { throw new Error("storage unavailable"); } }), {
    mode: "preset",
    selectedRoleIds: ["default-1", "default-3", "default-4"],
  });
});
