import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { isMagicClassImmersivePath } from "../src/app/shellMode.js";

const appShellSource = await readFile(new URL("../src/components/AppShell.jsx", import.meta.url), "utf8");

test("课程入口和学习空间保留 CampusMate 全局导航与搜索", () => {
  assert.equal(isMagicClassImmersivePath("/courses"), false);
  assert.equal(isMagicClassImmersivePath("/courses/course-1"), false);
  assert.equal(isMagicClassImmersivePath("/learning-space"), false);
});

test("只有课堂工作台和生成预览启用沉浸式壳层", () => {
  assert.equal(isMagicClassImmersivePath("/courses/course-1/magicclass-preview"), true);
  assert.equal(isMagicClassImmersivePath("/courses/course-1/workspaces/workspace-1"), true);
  assert.equal(isMagicClassImmersivePath("/courses/course-1/workspaces/workspace-1/legacy"), true);
});

test("AppShell 使用沉浸式路由判定控制 magicclass-shell", () => {
  assert.match(appShellSource, /const isMagicClassImmersive = isMagicClassImmersivePath\(location\.pathname\)/);
  assert.match(appShellSource, /isMagicClassImmersive \? "magicclass-shell" : ""/);
});
