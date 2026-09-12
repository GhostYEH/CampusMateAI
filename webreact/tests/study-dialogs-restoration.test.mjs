import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const studyPage = await readFile(new URL("../src/pages/StudyPage.jsx", import.meta.url), "utf8");
const focusRoom = await readFile(new URL("../src/components/study/SummerFocusRoom.jsx", import.meta.url), "utf8");
const primitives = await readFile(new URL("../src/components/Primitives.jsx", import.meta.url), "utf8");
const apiJs = await readFile(new URL("../src/data/api.js", import.meta.url), "utf8");
const studySummerCss = await readFile(new URL("../src/styles/study-summer.css", import.meta.url), "utf8");

test("review dialog uses study-scene variant instead of global white modal", () => {
  // StudyPage 复盘弹窗必须使用 variant="study"
  assert.match(studyPage, /variant="study"/, "复盘弹窗应使用 variant=\"study\"");
  assert.match(studyPage, /本次学习复盘/, "复盘弹窗标题存在");
});

test("Modal primitive supports variant and className props", () => {
  // Modal 必须接受 variant 和 className 可选参数
  assert.match(primitives, /variant\s*=\s*""/, "Modal 支持 variant 参数");
  assert.match(primitives, /className\s*=\s*""/, "Modal 支持 className 参数");
  // variant 生成 modal--{variant} class
  assert.match(primitives, /modal--\$\{variant\}/, "variant 生成 modal--{variant} class");
});

test("study-scene modal CSS uses forest glass style not white background", () => {
  // .modal.modal--study 必须使用深色森林背景,不是白色
  assert.match(studySummerCss, /\.modal\.modal--study/, "存在 .modal.modal--study 变体");
  // 背景应为深墨绿/森林绿半透明,不是 #fff
  const modalStudyBlock = studySummerCss.match(/\.modal\.modal--study\s*\{[^}]+\}/);
  assert.ok(modalStudyBlock, "能匹配 .modal.modal--study 规则块");
  assert.doesNotMatch(modalStudyBlock[0], /background:\s*#fff/, "不得使用白色背景");
  // 主按钮使用黄绿色强调,不是蓝色
  assert.match(studySummerCss, /\.modal\.modal--study > footer \.button-primary/, "主按钮有 study 变体样式");
  // --study-accent 变量定义为 #d7ef83(黄绿色),主按钮使用该变量
  assert.match(studySummerCss, /--study-accent:\s*#d7ef83/, "--study-accent 变量定义为黄绿色 #d7ef83");
  const primaryBtnBlock = studySummerCss.match(/\.modal\.modal--study > footer \.button-primary\s*\{[^}]+\}/);
  assert.ok(primaryBtnBlock, "能匹配主按钮规则块");
  assert.match(primaryBtnBlock[0], /var\(--study-accent\)/, "主按钮使用 var(--study-accent) 黄绿色强调");
  // 不得使用蓝色 var(--blue) 或 #3267d6
  assert.doesNotMatch(primaryBtnBlock[0], /var\(--blue\)|#3267d6/, "主按钮不得使用全局蓝色");
});

test("AI breakdown dialog uses workbench layout not narrow tall scroll", () => {
  // .study-summer-breakdown 宽度应约 840~960px,不再是 680px
  const breakdownBlock = studySummerCss.match(/\.study-summer-breakdown\s*\{[^}]+\}/);
  assert.ok(breakdownBlock, "能匹配 .study-summer-breakdown 规则块");
  assert.match(breakdownBlock[0], /min\(900px/, "宽度约 900px 工作台式");
  // 不应整个弹窗无差别滚动
  assert.match(breakdownBlock[0], /overflow:\s*hidden/, "弹窗整体不滚动(overflow:hidden)");
  // 步骤列表应独立滚动
  assert.match(studySummerCss, /\.study-summer-breakdown__steps\s*\{[^}]*overflow-y:\s*auto/, "步骤列表独立滚动");
  // 底部应 sticky/fixed 可见
  assert.match(studySummerCss, /\.study-summer-breakdown__footer\s*\{[^}]*flex:\s*0\s*0\s*auto/, "底部固定可见");
});

test("breakdownStudyTask uses independent timeout greater than backend default", () => {
  // breakdownStudyTask 必须设置独立超时,大于后端 30s 默认
  assert.match(apiJs, /breakdownStudyTask/, "breakdownStudyTask 函数存在");
  const breakdownFnBlock = apiJs.match(/export async function breakdownStudyTask[\s\S]*?\n\}/);
  assert.ok(breakdownFnBlock, "能匹配 breakdownStudyTask 函数块");
  // 必须有 timeout 配置,且大于 30000ms
  const timeoutMatch = breakdownFnBlock[0].match(/timeout:\s*(\d+)/);
  assert.ok(timeoutMatch, "breakdownStudyTask 设置了独立 timeout");
  const timeout = parseInt(timeoutMatch[1], 10);
  assert.ok(timeout > 30000, `独立超时(${timeout}ms)必须大于后端默认 30s`);
});

test("AI breakdown workflow preserves all buttons and edit capabilities", () => {
  // 生成/重新生成按钮
  assert.match(focusRoom, /生成步骤|重新生成/, "生成/重新生成按钮存在");
  // 步骤标题编辑
  assert.match(focusRoom, /onUpdateBreakdownStep/, "步骤编辑回调存在");
  // 删除步骤
  assert.match(focusRoom, /onRemoveBreakdownStep/, "删除步骤回调存在");
  // 预计分钟编辑
  assert.match(focusRoom, /estimated_minutes/, "预计分钟编辑存在");
  // 加入今日待办
  assert.match(focusRoom, /加入今日待办/, "加入今日待办按钮存在");
  // 目标输入
  assert.match(focusRoom, /breakdownGoal/, "目标输入存在");
});

test("rule_fallback shows user-friendly Chinese note not internal class names", () => {
  // rule_fallback 状态应显示用户友好中文
  assert.match(focusRoom, /rule_fallback/, "rule_fallback 状态判断存在");
  assert.match(focusRoom, /当前模型暂不可用/, "用户友好中文提示存在");
  // 不应显示内部异常类名
  assert.doesNotMatch(focusRoom, /LLMError/, "不向用户显示 LLMError 类名");
  assert.doesNotMatch(focusRoom, /SSLError/, "不向用户显示 SSLError 类名");
});

test("Modal focus management: useEffect does not depend on onClose (fixes focus loss)", () => {
  // 根因: 旧实现 useEffect(..., [onClose]) 中 onClose 是内联函数,
  // 每次父组件重渲染都产生新引用,导致 effect 重复执行并抢走 textarea 焦点。
  // 修复: 用 ref 保存最新 onClose,effect 依赖数组为空 []。
  assert.match(primitives, /onCloseRef\s*=\s*useRef\(onClose\)/, "用 ref 保存 onClose");
  assert.match(primitives, /onCloseRef\.current\s*=\s*onClose/, "每次渲染更新 ref");
  assert.match(primitives, /onCloseRef\.current\(\)/, "keydown handler 通过 ref 调用 onClose");
  // useEffect 依赖数组必须为空,不含 onClose
  const useEffectBlock = primitives.match(/useEffect\(\(\)\s*=>\s*\{[\s\S]*?\}\s*,\s*\[([^\]]*)\]\)/);
  assert.ok(useEffectBlock, "能匹配 useEffect 依赖数组");
  assert.doesNotMatch(useEffectBlock[1], /onClose/, "useEffect 依赖数组不得包含 onClose");
});

test("Modal focus management: respects autofocus on textarea/input", () => {
  // 初始焦点应优先聚焦带 autofocus 的元素(如 textarea),而非总是第一个 button
  assert.match(primitives, /autofocus/, "初始焦点检查 autofocus 属性");
  assert.match(primitives, /autoFocusEl\.focus\(\)/, "优先聚焦 autofocus 元素");
});

test("Modal preserves close, escape, mask close and aria attributes", () => {
  // Modal 支持 Escape 关闭
  assert.match(primitives, /Escape/, "Modal 支持 Escape 关闭");
  // 点击遮罩关闭
  assert.match(primitives, /event\.target === event\.currentTarget/, "点击遮罩关闭");
  // aria-modal 和 aria-labelledby
  assert.match(primitives, /aria-modal="true"/, "aria-modal 存在");
  assert.match(primitives, /aria-labelledby="modal-title"/, "aria-labelledby 存在");
  // 焦点恢复
  assert.match(primitives, /previouslyFocusedRef/, "焦点恢复管理存在");
  // Tab 焦点约束
  assert.match(primitives, /Tab/, "Tab 焦点约束存在");
  // 背景滚动锁定
  assert.match(primitives, /overflow.*hidden/, "背景滚动锁定存在");
});