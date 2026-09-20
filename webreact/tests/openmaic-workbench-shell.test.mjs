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
  NARROW_PANES,
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

/**
 * 这条契约此前是**错的**，而且是反向的：它断言窄屏 `railMini === true`，于是把
 * "rail 永远在场、永远占 60px"钉成了正确行为。真实后果是 320/390/768 上的舞台被
 * 一个固定的 60px mini 目录栏切掉一块，而"目录"这个面板根本不可能被选中。
 *
 * 窄屏唯一正确的契约是**恰好一个面板**：`rail` / `classroom` / `tools` 三者之和
 * 恒等于 1。断言的是"和"，不是"每一个的具体取值"——后者会漏掉"两个同时为 true"。
 */
test("the narrow layout is mutually exclusive — exactly one pane, for every pane", () => {
  for (const pane of ["rail", "classroom", "tools"]) {
    const layout = resolveWorkbenchLayout({ narrow: true, activePane: pane });
    const visible = [layout.rail, layout.classroom, layout.tools].filter(Boolean);
    assert.equal(visible.length, 1, `窄屏必须恰好一个面板为 true（activePane=${pane}）`);
    assert.equal(layout[pane], true, `被选中的面板必须为 true（activePane=${pane}）`);
    // 未激活的面板不得留下任何"占位"形态：mini rail 正是被删掉的那个 60px 挤压源。
    assert.equal(layout.railMini, false, "窄屏不能有 mini rail——它会固定占宽");
    // 窄屏没有"缝上的重开标签"，切换器就是那个入口，所以这一位必须恒为 false——
    // 留着它只会让人以为窄屏还有第二种回到面板的方式。
    assert.equal(layout.classroomTab, false, "窄屏不靠重开标签回到课堂");
  }
  // 未知面板名要退化到课堂，而不是什么都不显示。
  const bogus = resolveWorkbenchLayout({ narrow: true, activePane: "bogus" });
  assert.equal(bogus.classroom, true);
  assert.equal([bogus.rail, bogus.classroom, bogus.tools].filter(Boolean).length, 1);
});

test("the narrow switcher and the model share one pane list", () => {
  // 切换器要是自己再写一遍面板名，就会出现"能渲染但点不到"或"点了渲染不出来"。
  assert.deepEqual([...NARROW_PANES], ["rail", "classroom", "tools"]);
  assert.match(workbenchSource, /NARROW_PANES\.map\(/, "切换器必须由模型导出的列表渲染");
  for (const label of ["目录", "课堂", "工具"]) {
    assert.match(workbenchSource, new RegExp(label), `切换器缺少「${label}」`);
  }
  // 切换器必须在**工作台**上，而不是课堂面板里——否则切到目录就会把它一起带走。
  assert.match(workbenchSource, /className="ow-nav"/);
  assert.match(workbenchSource, /\{layout\.narrow \? <NarrowWorkbenchNav/);

  // 导航区外层是普通 <nav>，**不是** tablist：它肚子里有 WorkspaceCourseTabs，
  // 而后者自己就是 tablist，嵌起来层级就错了。
  assert.match(workbenchSource, /<nav className="ow-nav" aria-label="工作台导航">/,
    "导航区外层必须是 <nav> 而不是 role=tablist");
  assert.doesNotMatch(workbenchSource, /className="ow-nav" role="tablist"/,
    "导航区外层不得再声明 role=tablist");
  // 切换控件用 aria-pressed 表达互斥状态，不留 role=tab 的半套语义。
  // 断言的是真正的 JSX 属性（行首缩进的 `role="tab"` 后面直接换行），
  // 而不是散文注释里引用到的那个词。
  assert.match(workbenchSource, /aria-pressed=\{pane === key\}/,
    "切换控件必须用 aria-pressed 表达状态");
  assert.doesNotMatch(workbenchSource, /^\s*role="tab"\s*$/m,
    "切换控件不应保留 role=tab：没有配套的 tabpanel 就是半套语义");
  assert.doesNotMatch(workbenchSource, /<NarrowWorkbenchNav[\s\S]{0,600}?role="tablist"/,
    "窄屏导航区（含切换器）里不应再出现 tablist");
  // 键盘契约要在源码里就能看到，不能只靠鼠标。
  for (const key of ["ArrowRight", "ArrowLeft", "Home", "End"]) {
    assert.match(workbenchSource, new RegExp(`"${key}"`), `切换器缺少 ${key} 键盘支持`);
  }
});

test("the workbench renders exactly the panes the layout resolves", () => {
  // 只测纯模型会漏掉"模型说 classroom=false 但页面照样渲染课堂"这类缺陷——P1 之二
  // 就是这个形态。所以这里钉住渲染侧真的读了这三个开关。
  for (const flag of ["layout.rail", "layout.classroom", "layout.tools"]) {
    assert.match(
      workbenchSource,
      new RegExp(`\\{${flag.replace(".", "\\.")}\\s*\\?`),
      `${flag} 必须直接决定对应面板是否渲染`,
    );
  }
  // 课堂面板不得再被无条件挂载：section 的开标签必须紧跟在 `layout.classroom ?` 之后。
  assert.match(workbenchSource, /layout\.classroom \? <section className="ow-pane ow-pane--classroom"/,
    "课堂 section 必须以 layout.classroom 为条件渲染");
  assert.match(workbenchSource, /layout\.rail \? <aside[\s\S]{0,80}ow-pane--rail/,
    "目录 aside 必须以 layout.rail 为条件渲染");
  assert.match(workbenchSource, /layout\.tools \? <aside className="ow-pane ow-pane--tools"/,
    "工具 aside 必须以 layout.tools 为条件渲染");
});

test("the workbench ships the narrow layout and no-overflow guards", () => {
  assert.match(cssSource, /data-ow-layout='narrow'/);
  assert.match(workbenchSource, /resolveWorkbenchLayout\(/);
  // 工作台根节点必须自己锁住溢出：三栏并排时任何一栏超宽都会顶出横向滚动条。
  assert.match(cssSource, /\.ow-root\s*\{[^}]*overflow:\s*hidden/s);
  assert.match(cssSource, /\.ow-root\s*\{[^}]*min-width:\s*0/s);
  assert.match(cssSource, /@media \(max-width: 400px\)/);
  // 窄屏把三栏转成"导航区 + 唯一面板"的纵向排列。
  assert.match(cssSource, /data-ow-layout='narrow'\]\s*\{\s*flex-direction:\s*column/s);
  // 未激活面板不得靠视觉隐藏冒充互斥：那条固定 60px 的 mini rail 必须彻底消失。
  assert.doesNotMatch(cssSource, /data-ow-layout='narrow'\]\s*\.ow-pane--rail\s*\{[^}]*width:\s*\d+px/,
    "窄屏不得把 rail 固定成某个像素宽（那正是 320px 舞台被挤压的原因）");
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
