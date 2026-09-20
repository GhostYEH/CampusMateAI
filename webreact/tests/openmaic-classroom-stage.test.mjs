/**
 * 学习态课堂（移植自参考项目 OpenMAIC）的 Web 侧行为契约。
 *
 * 这一层最容易"看起来像课堂其实不可用"，所以钉住的是四类**不可回退**的约束：
 *
 * 1. **渲染决定来自服务端。** 场景列表走播放计划（`render.kind` 是服务端的判断），
 *    正文走授权的单场景端点。前端不自己猜"这个大概能渲染"。
 * 2. **沙箱只减不增。** 是否允许 iframe 由 `sandboxPolicyFor` 判定，且**不在
 *    组件里重建 sandbox 串**；`allow-same-origin` 一旦出现就等于没有沙箱。
 * 3. **迟到的响应不得写进新上下文。** 换舞台用 epoch 挡、换场景用 cancelled 挡。
 * 4. **不编造内容。** 正文读不到就说读不到，不用占位内容冒充。
 *
 * 另外钉住移植层的两条结构性事实：令牌作用域必须由承载方提供（`.maic-root`），
 * 以及移植代码不得直连受管服务（浏览器只调 CampusMate API）。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";

import "./helpers/setup-globals.mjs";
import { sandboxPolicyFor } from "../src/features/openmaic/playerModel.js";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");

const stageSource = read("src/components/openmaic/OpenMAICClassroomStage.jsx");
const workbenchSource = read("src/pages/OpenMAICWorkbenchPage.jsx");
const cssSource = read("src/styles/maic.css");
const workbenchCss = read("src/styles/openmaic-workbench.css");

/** 列出 `src/maic` 下所有文件（相对 `webreact/` 的路径），用于"不得越界"类断言。 */
function walk(relDir, out = []) {
  const dir = fileURLToPath(new URL(`../${relDir}`, import.meta.url));
  for (const name of readdirSync(dir)) {
    const childRel = `${relDir}/${name}`;
    if (statSync(fileURLToPath(new URL(`../${childRel}`, import.meta.url))).isDirectory()) walk(childRel, out);
    else out.push(childRel);
  }
  return out;
}
const maicFiles = walk("src/maic");

// ===== 1. 渲染决定来自服务端 =====

test("the classroom reads the server's render decision, not its own guess", () => {
  assert.match(stageSource, /api\.getOpenMAICStagePlayback\(/, "场景列表必须来自播放计划");
  assert.match(stageSource, /normalizePlayback\(/, "播放计划必须经统一归一化");
  // 正文来自授权的**舞台文档**端点：一次取回全部场景，侧栏缩略图与主画布共用
  // 同一次读取。逐场景拉正文会让 8 个场景变成 8 次请求，而且缩略图拿不到内容。
  assert.match(stageSource, /api\.getOpenMAICStage\(/, "正文必须来自授权的舞台文档端点");
  assert.match(stageSource, /indexScenesById\(stageDocument\)/, "舞台文档必须按场景 id 建索引");
  assert.doesNotMatch(stageSource, /getOpenMAICStageScene\(/, "不得退回逐场景拉取正文");
  // 渲染决定只在服务端给，组件不得自己推导 kind。
  assert.doesNotMatch(stageSource, /render\s*:\s*\{\s*kind\s*:/, "组件不得自己伪造 render.kind");
});

test("the classroom shows real slide thumbnails from the same document", () => {
  // 侧栏只拿到播放计划时 slide 缩略图永远是灰框（播放计划不含正文）。
  assert.match(stageSource, /sidebarScenes/, "侧栏必须收到合并了正文的场景列表");
  assert.match(stageSource, /content: contentByScene\[entry\.id\]\?\.content/, "正文必须按场景并入侧栏列表");
  assert.match(stageSource, /renderSlideThumbnail/, "必须把 slide 缩略图渲染器交给侧栏");
  // 缩略图复用播放画布，因此缩略图与实际内容不可能不一致。
  assert.match(stageSource, /<MaicSlideSurface canvas=\{canvas\}/, "缩略图必须复用同一套画布渲染");
  assert.match(stageSource, /elements\.length === 0\) return null/, "没有元素的旧画布必须交回占位分支，而不是画空白");
});

// ===== 2. 沙箱只减不增 =====

test("the classroom reuses the shared sandbox policy and never widens it", () => {
  assert.match(stageSource, /sandboxPolicyFor\(/, "必须复用统一沙箱判据");
  assert.match(stageSource, /sandbox=\{policy\.sandbox\}/, "sandbox 串必须原样使用服务端给的值");
  assert.doesNotMatch(stageSource, /sandbox="[^"]*allow-same-origin/, "不得硬编码 allow-same-origin");
  assert.doesNotMatch(
    stageSource,
    /sandbox=\{[^}]*allow-same-origin/,
    "不得在组件里重建出 allow-same-origin",
  );
  // 判据在模型里，模型自己必须拒绝被放大的沙箱串。
  assert.equal(
    sandboxPolicyFor({ kind: "sandbox-html", sandbox: "allow-scripts allow-same-origin" }).allowIframe,
    false,
    "同时带 allow-scripts 与 allow-same-origin 的沙箱必须被拒绝",
  );
  assert.equal(
    sandboxPolicyFor({ kind: "sandbox-html", sandbox: "allow-scripts" }).allowIframe,
    true,
    "最小沙箱串必须被允许",
  );
});

// ===== 3. 迟到响应不得写进新上下文 =====

test("late responses are dropped when the stage changes", () => {
  // 换舞台：epoch 守卫。正文与播放计划是**并发**发出的两个请求，必须同处一道
  // 守卫之后——只挡其中一个，另一个的迟到响应照样会写进新舞台的上下文。
  assert.match(stageSource, /epoch\.current \+= 1/, "换舞台必须递增 epoch");
  assert.match(stageSource, /await Promise\.all\(/, "两个请求必须并发发出");
  assert.match(stageSource, /mine !== epoch\.current\) return/, "迟到的舞台响应必须被丢弃");
  // 状态写入必须在守卫之后：先 await 再判断再 set，缺一不可。
  const guardedWrites = stageSource.match(/if \(mine !== epoch\.current\) return;/g) ?? [];
  assert.ok(guardedWrites.length >= 2, "成功与失败两条路径都必须过 epoch 守卫");
});

// ===== 4. 不编造内容 =====

test("an unreadable scene says so instead of faking content", () => {
  assert.match(stageSource, /不用占位内容冒充正文/, "读不到正文时必须如实说明");
  assert.match(stageSource, /degradeNotice\(outline\)/, "服务端标 unsupported 时要说清缺什么");
  // 读取中的占位必须与"读到了空内容"分开表达。
  assert.match(stageSource, /正在读取场景内容/, "读取中要与读不到区分");
});

// ===== 移植层的结构性事实 =====

test("the ported layer cannot reach the managed service directly", () => {
  // 浏览器只调 CampusMate API；移植代码里出现受管服务地址/内部密钥就是越界。
  for (const file of maicFiles) {
    const source = read(file);
    assert.doesNotMatch(source, /OPENMAIC_INTERNAL_SECRET/, `${file} 不得出现内部密钥`);
    assert.doesNotMatch(source, /127\.0\.0\.1:4010|localhost:4010/, `${file} 不得直连受管服务`);
    assert.doesNotMatch(source, /from ["']next\//, `${file} 不得残留 Next.js 依赖`);
    assert.doesNotMatch(source, /^['"]use client['"];?$/m, `${file} 不得残留 'use client'`);
  }
});

test("the tailwind token layer stays scoped and cannot restyle the rest of the app", () => {
  // 令牌只在 .maic-root 内定义，且**不引入 preflight** —— 否则会重排既有页面。
  assert.match(cssSource, /\.maic-root\s*\{/, "令牌必须限定在 .maic-root 作用域内");
  assert.doesNotMatch(cssSource, /@import\s+["']tailwindcss["']\s*;/, "不得整体引入 tailwindcss（会带进 preflight）");
  assert.match(cssSource, /@import\s+["']tailwindcss\/theme\.css["']/, "只引入 theme 层");
  assert.match(cssSource, /@import\s+["']tailwindcss\/utilities\.css["']/, "只引入 utilities 层");
  assert.doesNotMatch(cssSource, /@import\s+["']tailwindcss\/preflight\.css["']/, "不得引入 preflight");
  // 承载方必须提供作用域：课堂外壳按契约不带 .maic-root，所以集成组件要自己带。
  assert.match(stageSource, /className="maic-root/, "集成组件必须自己提供 .maic-root 作用域");
});

test("playback hands the whole content area to the classroom", () => {
  assert.match(workbenchSource, /const playing = chromeMode === "playback"/);
  assert.match(workbenchSource, /layout\.rail && !playing \?/);
  assert.match(workbenchSource, /layout\.tools && !playing \?/);
  assert.match(workbenchSource, /\(layout\.classroom \|\| playing\) \?/);
  assert.match(workbenchSource, /<OpenMAICClassroomStage/);
  // 播放态必须给出可测量的标识，验收脚本据此断言"课堂真的渲染了"。
  assert.match(workbenchSource, /data-testid=\{playing \? "ow-learning-classroom" : undefined\}/);
  // 学习态课堂自带背景与默认面板背景，必须摘掉工作台那层玻璃壳，否则四周露边。
  assert.match(workbenchCss, /\.ow-pane--classroom\.is-learning\s*\{[^}]*background-color:\s*transparent/s);
});

test("the classroom header survives a 320px viewport", () => {
  const headerSource = read("src/maic/classroom/classroom-header.jsx");
  // 320px 下固定 px-8 会把标题块挤成 0 宽，右侧控制簇随即盖住返回按钮并吃掉点击。
  assert.match(headerSource, /px-4 sm:px-8/, "头栏内边距必须窄屏收窄");
  assert.match(headerSource, /gap-2 sm:gap-4/, "头栏间距必须窄屏收窄");
  assert.match(headerSource, /flex items-center gap-2 sm:gap-4 shrink-0/, "右控制簇不得被压缩到溢出");
  // 侧栏 220px 的默认宽度在 320px 下会把主列压到 100px，必须自动收起。
  assert.match(stageSource, /useNarrowViewport\(\)/, "课堂必须在窄屏自动收起侧栏");
  assert.match(stageSource, /setCollapsed\(narrow\)/, "跨断点时必须重算侧栏开合");
});
