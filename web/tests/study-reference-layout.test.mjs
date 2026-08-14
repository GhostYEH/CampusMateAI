import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("study page matches the supplied desktop reference without changing other clients", async () => {
  const [view, shell, entry, css] = await Promise.all([
    readFile(path.join(webRoot, "src", "views", "student", "StudentStudyView.vue"), "utf8"),
    readFile(path.join(webRoot, "src", "views", "AppShell.vue"), "utf8"),
    readFile(path.join(webRoot, "src", "main.js"), "utf8"),
    readFile(path.join(webRoot, "src", "styles", "study-reference.css"), "utf8"),
  ]);

  assert.match(view, /class="student-page study-reference/);
  assert.match(view, /class="study-reference-top"/);
  assert.match(view, /class="study-reference-metrics"/);
  assert.match(view, /class="study-reference-bottom"/);
  assert.match(view, /@click="start"/);
  assert.match(view, /@click="togglePause"/);
  assert.match(view, /@click="finish"/);
  assert.match(view, /@click="planBreakdown"/);
  assert.match(view, /@click="openExperience\('task', task, \$event\)"/);
  assert.match(view, /ref="trendCanvas"/);
  assert.match(view, /function drawTrend\(\)/);

  assert.match(shell, /'study-mode': route\.path === ['"]\/study['"]/);
  assert.match(entry, /\.\/styles\/study-reference\.css/);
  assert.match(css, /\.study-reference-top\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*\.96fr\)\s+minmax\(0,\s*1\.04fr\)/s);
  assert.match(css, /\.study-reference-metrics\s*\{[^}]*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/s);
  assert.match(css, /\.study-reference-bottom\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*\.92fr\)\s+minmax\(0,\s*1\.2fr\)\s+minmax\(0,\s*1fr\)/s);
  assert.match(css, /@media\(max-width:900px\)/);
});
