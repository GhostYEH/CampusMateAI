import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const component = await readFile(new URL("../src/components/study/SummerFocusRoom.jsx", import.meta.url), "utf8").catch(() => "");
const studyPage = await readFile(new URL("../src/pages/StudyPage.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/study-summer.css", import.meta.url), "utf8").catch(() => "");

test("summer focus room exposes the reference layout and scene controls", () => {
  assert.match(component, /Deep focus/);
  assert.match(component, /雨景/);
  assert.match(component, /雪景/);
  assert.match(component, /暖云/);
  assert.match(component, /study-summer-focus/);
  assert.match(component, /study-summer-todos/);
  assert.match(component, /开始专注/);
  assert.match(studyPage, /SummerFocusRoom/);
});

test("summer focus room keeps the visual system local and responsive", () => {
  assert.match(styles, /data-study-scene="rain"/);
  assert.match(styles, /grid-template-columns:[^;]*1fr[^;]*minmax\(220px, 25%\)/);
  assert.match(styles, /@media \(max-width: 760px\)/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});
