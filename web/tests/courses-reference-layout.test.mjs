import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("course page keeps the supplied reference layout and interactions", async () => {
  const view = await readFile(
    path.join(webRoot, "src", "views", "student", "StudentCoursesView.vue"),
    "utf8",
  );
  const css = await readFile(
    path.join(webRoot, "src", "styles", "student-pages.css"),
    "utf8",
  );

  assert.match(view, /class="courses-stat-dock"/);
  assert.match(view, /class="course-card-menu"/);
  assert.match(view, /class="course-card-footer"/);
  assert.match(view, /@click="openCourse\(course\)"/);
  assert.doesNotMatch(view, /class="hero-eyebrow"/);
  assert.doesNotMatch(view, /class="tip-banner"/);

  assert.match(css, /COURSES REFERENCE MATCH/);
  assert.match(css, /background-image:\s*url\("\/assets\/mycours-icon\.png"\),\s*url\("\/assets\/campusmate-courses-hero\.jpg"\)/);
  assert.match(css, /grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/);
  assert.match(css, /@media\(max-width:820px\)/);
});
