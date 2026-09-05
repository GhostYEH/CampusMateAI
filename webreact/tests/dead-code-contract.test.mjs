import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (file) => readFileSync(resolve(root, file), "utf8");

test("application routes do not depend on the retired page aggregator", () => {
  const app = read("src/App.jsx");

  assert.equal(existsSync(resolve(root, "src/pages/StudentPages.jsx")), false);
  assert.match(app, /import\("\.\/pages\/UniversityPage\.jsx"\)/);
  assert.doesNotMatch(app, /pages\/StudentPages\.jsx/);
});

test("page modules expose only the current implementation for each route", () => {
  const integrations = read("src/pages/IntegrationPages.jsx");
  const tools = read("src/pages/StudentToolPages.jsx");

  assert.doesNotMatch(integrations, /export function SettingsPage/);
  assert.doesNotMatch(tools, /export function ExamDetailPage/);
  assert.doesNotMatch(tools, /export function CommunityDetailPage/);
});
