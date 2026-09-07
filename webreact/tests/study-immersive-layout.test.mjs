import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const studyPage = await readFile(new URL("../src/pages/StudyPage.jsx", import.meta.url), "utf8");
const room = await readFile(new URL("../src/components/study/SummerFocusRoom.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/study-summer.css", import.meta.url), "utf8");

test("study page drops the old card stack in favor of a borderless full-screen room", () => {
  assert.doesNotMatch(studyPage, /TiltedCard/);
  assert.doesNotMatch(studyPage, /study-focus-card/);
  assert.doesNotMatch(studyPage, /study-plan-card|study-trend-card|study-records-card|study-tasks-card/);
  assert.doesNotMatch(studyPage, /stat-grid/);
  assert.match(studyPage, /import SummerFocusRoom from ["']\.\.\/components\/study\/SummerFocusRoom\.jsx["']/);
});

test("study room keeps the brand heading and the finish-review dialog entry", () => {
  assert.match(studyPage, /学习陪伴/);
  assert.match(studyPage, /本次学习复盘/);
  assert.match(studyPage, /confirmFinish/);
  assert.match(studyPage, /userErrorMessage/);
});

test("study room uses the global scene as the only background (no internal stage)", () => {
  assert.doesNotMatch(room, /study-summer-room__backdrop/);
  assert.doesNotMatch(room, /--study-scene-image/);
  assert.match(room, /className=[""]study-summer-room[""]/);
  assert.match(room, /study-summer-scenes/);
  assert.match(room, /study-summer-immersive-trigger/);
  // 三栏：计时站 / 场景留白 / 今日待办
  assert.match(room, /study-summer-focus/);
  assert.match(room, /study-summer-atmosphere/);
  assert.match(room, /study-summer-todos/);
});

test("study styles keep the room borderless and lay out three columns on desktop", () => {
  const roomRule = styles.match(/\.study-summer-room\s*\{([\s\S]*?)\n\}/)?.[1] || "";
  // 房间自身不再有盒子背景/圆角边框（背景由全局场景提供）
  assert.doesNotMatch(roomRule, /background|border-radius|box-shadow/);
  const gridRule = styles.match(/\.study-summer-grid\s*\{([\s\S]*?)\}/)?.[1] || "";
  assert.match(gridRule, /grid-template-columns:\s*minmax\(280px,\s*24%\)\s+1fr\s+minmax\(240px,\s*22%\)/);
  assert.match(styles, /@media \(max-width:\s*760px\)[\s\S]*\.study-summer-grid\s*\{\s*grid-template-columns:\s*1fr/);
});

test("study room keeps supporting text readable", () => {
  assert.match(styles, /\.study-summer-todos__list > button[^}]*font-size:\s*13px/);
  assert.match(styles, /\.study-summer-dock__links a[^}]*font-size:\s*13px/);
  assert.match(styles, /\.study-summer-start input[^}]*font-size:\s*13px/);
});
