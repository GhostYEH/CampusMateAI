import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const pageSource = fs.readFileSync(new URL("../src/pages/SettingsPage.jsx", import.meta.url), "utf8");
const toggleSource = fs.readFileSync(new URL("../src/components/settings/SettingToggle.jsx", import.meta.url), "utf8");
const preferenceSource = fs.readFileSync(new URL("../src/features/settings/settingsPreferences.js", import.meta.url), "utf8");
const styleSource = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

test("React settings page follows the light Vue reference composition", () => {
  assert.match(pageSource, /className="[^"]*react-settings-page/);
  assert.match(pageSource, /className="settings-hero"/);
  assert.match(pageSource, /className="settings-account"/);
  assert.match(pageSource, /className="settings-notifications"/);
  assert.match(pageSource, /className="settings-privacy"/);
  assert.match(pageSource, /className="settings-display"/);
  assert.match(toggleSource, /aria-pressed=\{value\}/);
  assert.match(preferenceSource, /campus_exam_reminder/);
  assert.match(preferenceSource, /campus_task_due/);
  assert.match(preferenceSource, /campus_announcement_notify/);
  assert.match(preferenceSource, /campus_share_focus_stats/);
  assert.match(preferenceSource, /campus_show_online/);
});

test("React settings page has responsive full-width cards", () => {
  assert.match(styleSource, /\.react-settings-page\s*\{[\s\S]*?max-width:/);
  assert.match(styleSource, /\.react-settings-page \.settings-sections\s*\{[\s\S]*?grid-template-columns:\s*1fr/);
  assert.match(styleSource, /@media \(max-width:\s*760px\)[\s\S]*?\.settings-hero/);
});

test("settings shell keeps the account avatar bounded", () => {
  assert.match(styleSource, /\.topbar-account \.avatar img\s*\{[\s\S]*?width:\s*30px[\s\S]*?height:\s*30px/);
});
