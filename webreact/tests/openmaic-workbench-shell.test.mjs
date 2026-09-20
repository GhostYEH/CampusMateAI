/**
 * 工作台外壳与「编辑 / 播放」推导的契约。
 *
 * 这里钉住两件参考项目用真实缺陷换来的结论，因为它们是**最容易被"顺手简化"掉**
 * 的部分：
 *
 * 1. **16:9 不是 CSS。** 用 `aspect-ratio` 撑出来的框在首次挂载时会读到过期的宿主
 *    尺寸，症状是"第一次打开舞台是歪的，拖一下分隔条才对"。所以它必须是
 *    ResizeObserver + 像素盒，并且四层测量缺一不可。
 * 2. **播放不是默认分支。** 面板里的课堂是编辑锁定的，进播放的唯一门是用户按
 *    「开始学习」；任何"编辑还没就绪"的中间态都必须落在 `loading` 上，否则会先闪
 *    一屏播放 chrome 再跳回编辑。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  CLASSROOM_ASPECT_RATIO,
  containBox,
  fillWidthBox,
  resolveStageChromeMode,
  resolveWorkbenchLayout,
} from "../src/features/openmaic/workbenchLayoutModel.js";

const read = (rel) => readFileSync(new URL(`../${rel}`, import.meta.url), "utf8");
const layoutSource = read("src/features/openmaic/workbenchLayoutModel.js");
const containSource = read("src/components/openmaic/ContainBox.jsx");
const workbenchSource = read("src/pages/OpenMAICWorkbenchPage.jsx");
const cssSource = read("src/styles/openmaic-workbench.css");

// ===== 16:9 几何 =====

test("containBox returns the largest 16:9 box that fits", () => {
  // 宿主比 16:9 更宽 → 受高度约束
  assert.deepEqual(containBox(1000, 400, CLASSROOM_ASPECT_RATIO), { width: 400 * (16 / 9), height: 400 });
  // 宿主比 16:9 更高 → 受宽度约束
  assert.deepEqual(containBox(800, 900, CLASSROOM_ASPECT_RATIO), { width: 800, height: 800 / (16 / 9) });
});

test("containBox never returns a non-finite or negative box", () => {
  for (const args of [[0, 400, CLASSROOM_ASPECT_RATIO], [800, 0, CLASSROOM_ASPECT_RATIO], [NaN, 400, 1], [800, 400, 0], [-5, 400, 1]]) {
    assert.deepEqual(containBox(...args), { width: 0, height: 0 }, `${args.join()} 必须回退到 0，调用方据此走 100%`);
  }
});

test("fillWidthBox keeps the ratio from width alone", () => {
  assert.deepEqual(fillWidthBox(640, CLASSROOM_ASPECT_RATIO), { width: 640, height: 360 });
  assert.deepEqual(fillWidthBox(0, CLASSROOM_ASPECT_RATIO), { width: 0, height: 0 });
});

test("the 16:9 stage is measured in JS, not declared as aspect-ratio", () => {
  // 四层测量缺一层就会出现"首次打开尺寸不对"。
  assert.match(containSource, /useContainBox/);
  assert.match(layoutSource, /new ResizeObserver\(measure\)/);
  assert.match(layoutSource, /observer\.observe\(element\.parentElement\)/, "父元素先拿到新宽度，也要观察");
  assert.match(layoutSource, /setInterval\(measure, 400\)/, "兜底轮询");
  assert.match(layoutSource, /kick\(1500\)/, "rAF settle 窗口");
  assert.match(layoutSource, /addEventListener\("transitionend", onSettled, true\)/, "过渡结束才是权威的稳定信号");
  // 只有尺寸真变了才 setState，否则这些重复测量会变成渲染抖动。
  assert.match(layoutSource, /current\.width === next\.width && current\.height === next\.height/);
  // 舞台盒不得用 aspect-ratio 实现。
  assert.doesNotMatch(cssSource, /\.ow-contain__box\s*\{[^}]*aspect-ratio/s);
});

// ===== 编辑 / 播放的推导 =====

test("playback is reachable only through the Start Learning door", () => {
  assert.equal(resolveStageChromeMode({ hosted: true, workbenchLearning: true }), "playback");
  // 只要「开始学习」没按下，任何状态都不许落到 playback。
  for (const context of [
    { isEditable: false, hasCurrentScene: true },
    { isEditable: true, hasCurrentScene: false },
    { stageMatchesHost: false, isEditable: true, hasCurrentScene: true },
    { workbenchShowingClassroom: false, isEditable: true, hasCurrentScene: true },
    { editorLoadFailed: true, isEditable: true, hasCurrentScene: true },
    { editorReady: false, isEditable: true, hasCurrentScene: true },
  ]) {
    const mode = resolveStageChromeMode({ hosted: true, ...context });
    assert.equal(mode, "loading", `${JSON.stringify(context)} 必须落在 loading，不能闪播放 chrome`);
    assert.notEqual(mode, "playback");
  }
});

test("a ready hosted stage edits, and a standalone stage keeps its stored mode", () => {
  assert.equal(resolveStageChromeMode({ hosted: true, isEditable: true, hasCurrentScene: true }), "edit");
  assert.equal(resolveStageChromeMode({ hosted: false, storedMode: "playback" }), "playback");
  assert.equal(resolveStageChromeMode({ hosted: false, storedMode: "edit" }), "edit");
});

test("the workbench exposes Start Learning as the only playback entry", () => {
  assert.match(workbenchSource, /data-testid="ow-start-learning"/);
  assert.match(workbenchSource, /resolveStageChromeMode\(/);
  assert.match(workbenchSource, /workbenchLearning: learning/);
});

// ===== 三栏布局与窄屏互斥 =====

test("the wide layout shows all three panes", () => {
  const wide = resolveWorkbenchLayout({ narrow: false });
  assert.equal(wide.rail, true);
  assert.equal(wide.classroom, true);
  assert.equal(wide.tools, true);
});

test("the narrow layout is mutually exclusive — one pane at a time", () => {
  for (const pane of ["rail", "classroom", "tools"]) {
    const layout = resolveWorkbenchLayout({ narrow: true, activePane: pane });
    const visible = [layout.classroom, layout.tools].filter(Boolean).length;
    assert.ok(visible <= 1, `窄屏不能同时显示多个内容面板（${pane}）`);
    assert.equal(layout.railMini, true, "窄屏 rail 必须收成 mini");
  }
  // 未知面板名要退化到课堂，而不是什么都不显示。
  assert.equal(resolveWorkbenchLayout({ narrow: true, activePane: "bogus" }).classroom, true);
});

test("the workbench ships the narrow layout and no-overflow guards", () => {
  assert.match(cssSource, /data-ow-layout='narrow'/);
  assert.match(workbenchSource, /resolveWorkbenchLayout\(/);
  // 工作台根节点必须自己锁住溢出：三栏并排时任何一栏超宽都会顶出横向滚动条。
  assert.match(cssSource, /\.ow-root\s*\{[^}]*overflow:\s*hidden/s);
  assert.match(cssSource, /\.ow-root\s*\{[^}]*min-width:\s*0/s);
  assert.match(cssSource, /@media \(max-width: 400px\)/);
});

// ===== 面板头只允许一个高度 =====

test("every pane header shares one height token, declared exactly once", () => {
  const declarations = cssSource.match(/--ow-pane-head-h:/g) || [];
  assert.equal(declarations.length, 1, "高度令牌只能声明一次，否则两个头的下沿会在缝上错开");
  assert.match(cssSource, /\.ow-pane-head\s*\{[^}]*height:\s*var\(--ow-pane-head-h\)/s);
  // 具体面板头不得自己设高度。
  assert.doesNotMatch(cssSource, /\.ow-classroom-head\s*\{[^}]*height:/s);
});

// ===== 复用已有能力，不重写 =====

test("the workbench reuses the existing panels and API rather than reimplementing them", () => {
  assert.match(workbenchSource, /StageEditorPanel/);
  assert.match(workbenchSource, /StagePlayerPanel/);
  assert.match(workbenchSource, /ProviderToolsPanel/);
  assert.match(workbenchSource, /api\.getOpenMAICStagePlayback|StagePlayerPanel/);
  assert.match(workbenchSource, /api\.generateOpenMAICStage/);
  assert.match(workbenchSource, /api\.exportOpenMAICStageFormat/);
  // 不得引入预览页那条被推翻的路径。
  assert.doesNotMatch(workbenchSource, /counselor/i);
});

test("runtimes stay reachable through the player, not reimplemented in the workbench", () => {
  const player = read("src/components/openmaic/StagePlayerPanel.jsx");
  assert.match(player, /QuizRuntimePanel/);
  assert.match(player, /SimulationRuntimePanel/);
  assert.match(player, /PblRuntimePanel/);
});
