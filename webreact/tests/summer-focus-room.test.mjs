import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const component = await readFile(new URL("../src/components/study/SummerFocusRoom.jsx", import.meta.url), "utf8").catch(() => "");
const dock = await readFile(new URL("../src/components/study/SummerNavDock.jsx", import.meta.url), "utf8").catch(() => "");
const studyPage = await readFile(new URL("../src/pages/StudyPage.jsx", import.meta.url), "utf8");
const shell = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8").catch(() => "");
const quotes = await readFile(new URL("../src/features/study/summerQuotes.js", import.meta.url), "utf8").catch(() => "");
const ambient = await readFile(new URL("../src/features/study/ambientSound.js", import.meta.url), "utf8").catch(() => "");
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

test("summer dock carries the reference nav to the study page bottom", () => {
  assert.match(studyPage, /SummerNavDock/);
  assert.match(dock, /study-summer-dock/);
  assert.match(dock, /aria-label="学习陪伴导航"/);
  assert.match(dock, /to:\s*"\/study"/);
  assert.match(dock, /to:\s*"\/tasks"/);
  assert.match(dock, /to:\s*"\/courses"/);
  assert.match(dock, /to:\s*"\/home"/);
  assert.match(dock, /aria-pressed=\{sceneAudio\.enabled\}/);
  assert.match(dock, /场景音/);
  assert.match(studyPage, /useAmbientSound/);
  assert.match(studyPage, /sceneAudio=\{ambient\}/);
  assert.match(styles, /\.study-summer-dock\s*\{[^}]*bottom:\s*max\(16px,\s*env\(safe-area-inset-bottom\)\)/);
  assert.match(styles, /\.study-summer-dock\s*\{[^}]*position:\s*fixed/);
  assert.match(styles, /\.study-page\s*\{\s*padding-bottom:\s*124px/);
  assert.match(styles, /@media \(max-width: 640px\)/);
  assert.match(shell, /study-mode/);
  assert.match(styles, /\.app-layout\.study-mode \.floating-nav/);
});

test("summer focus room keeps the full reference pomodoro and immersive controls", () => {
  assert.match(component, /phase === "break"/);
  assert.match(component, /第 \$\{round\} 轮/);
  assert.match(component, /completed/);
  assert.match(component, /study-summer-dots/);
  assert.match(component, /跳过/);
  assert.match(component, /重置/);
  assert.match(component, /study-summer-ring__progress/);
  assert.match(component, /createPortal/);
  assert.match(component, /study-summer-immersive/);
  assert.match(component, /长按退出/);
  assert.match(styles, /\.study-summer-immersive\s*\{[^}]*position:\s*fixed/);
  assert.match(styles, /\.study-summer-body-lock/);
  assert.match(quotes, /雨林深处，专注是最温柔的光。/);
  assert.match(quotes, /雪地里的脚印，每一步都算数。/);
  assert.match(quotes, /云卷云舒之间，专注慢慢长出形状。/);
  assert.match(ambient, /useAmbientSound/);
  assert.match(ambient, /lowpass/);
});
