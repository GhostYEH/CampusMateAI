/**
 * 移植补充：`slide-renderer-prose` 文本排版契约。
 *
 * 逐字移植自参考 `packages/@magicclass/renderer/src/styles.ts`。参考项目的
 * `SlideCanvas` 会在画布顶部注入这段 CSS，用来抹平宿主与 UA 默认样式（段落间距
 * 走 `--paragraphSpace`，列表符号还原，行内公式外边距归零）。
 *
 * CampusMate 的页面没有引入 Tailwind preflight，默认样式其实更接近浏览器原样，
 * 但 .slide-renderer-prose 的这几条规则本身是「以幻灯片 JSON 为唯一权威」的
 * 排版契约，缺了它段落间距和列表符号会与参考项目不一致，所以原样保留。
 *
 * 参考 `createTextProseStyles(selector)` 保留为函数，便于其他静态渲染路径共用。
 */
export function createTextProseStyles(selector) {
  return `
${selector} p {
  margin-top: 0;
  margin-bottom: var(--paragraphSpace, 0);
}
${selector} p:last-child {
  margin-bottom: 0;
}
${selector} p:empty::before {
  content: '\\00a0';
}
${selector} .katex-display {
  margin: 0 !important;
}
${selector} ul {
  list-style-position: outside !important;
  padding-inline-start: 1.5rem !important;
}
${selector} ul:not([style*="list-style-type"]) {
  list-style-type: disc !important;
}
${selector} ol {
  list-style-position: outside !important;
  padding-inline-start: 1.5rem !important;
}
${selector} ol:not([style*="list-style-type"]) {
  list-style-type: decimal !important;
}
${selector} li {
  display: list-item !important;
}
`;
}

export const SLIDE_RENDERER_STYLES = `
${createTextProseStyles('.slide-renderer-prose')}
/* Table cell inner container — matches the classroom (Vue) .cell-text design:
   tight base line-height, and a small spacing between adjacent <p> siblings
   so multi-paragraph cells don't collapse into a single visual block. The
   <p> margin reset above sets the baseline to 0; this rule re-adds spacing
   only between adjacent siblings, leaving the first/last paragraph flush. */
.slide-renderer-cell-text p + p {
  margin-top: 0.4em;
}
@keyframes slide-renderer-pulse {
  50% { opacity: 0.5; }
}
@keyframes slide-renderer-ping {
  75%, 100% { transform: scale(2); opacity: 0; }
}
@keyframes slide-renderer-code-cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.slide-renderer-pulse {
  animation: slide-renderer-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
.slide-renderer-ping {
  animation: slide-renderer-ping 1s cubic-bezier(0, 0, 0.2, 1) infinite;
}
`;
