import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("student pages share the courses page gutter and readable task type scale", async () => {
  const [base, pages, home, study] = await Promise.all([
    readFile(path.join(webRoot, "src/styles/student-base.css"), "utf8"),
    readFile(path.join(webRoot, "src/styles/student-pages.css"), "utf8"),
    readFile(path.join(webRoot, "src/styles/student-home.css"), "utf8"),
    readFile(path.join(webRoot, "src/styles/study-reference.css"), "utf8"),
  ]);

  assert.match(base, /--student-page-gutter:\s*clamp\(22px,\s*2\.25vw,\s*36px\)/);
  assert.match(base, /\.student-layout \.student-page\{[^}]*max-width:none;[^}]*padding-left:var\(--student-page-gutter\);[^}]*padding-right:var\(--student-page-gutter\)/s);
  assert.match(home, /\.student-layout \.student-page\.student-home\{[^}]*max-width:none;[^}]*padding:0 var\(--student-page-gutter\)/s);
  assert.doesNotMatch(home, /\.student-layout \.student-page\.student-home\{[^}]*padding:0 (?:18px|12px)/s);
  assert.match(study, /\.student-layout \.student-page\.study-reference\{[^}]*max-width:none;[^}]*padding-left:var\(--student-page-gutter\);[^}]*padding-right:var\(--student-page-gutter\)/s);
  assert.match(pages, /\.student-layout \.task-dashboard\s*\{[^}]*max-width:\s*none;[^}]*padding-left:\s*var\(--student-page-gutter\);[^}]*padding-right:\s*var\(--student-page-gutter\)/s);
  assert.match(pages, /\.task-dashboard-head h1\s*\{[^}]*font-size:clamp\(31px,2\.35vw,40px\)/s);
  assert.match(pages, /\.task-metric-value\s*\{[^}]*font-size:30px/s);
  assert.match(pages, /\.task-row-copy strong\s*\{[^}]*font-size:14px/s);
});
