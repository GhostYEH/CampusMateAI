/**
 * 移植补充：`@openmaic/dsl` 里被 slide 渲染层真正用到的常量。
 *
 * 目标项目不允许引入 `@openmaic/dsl`（那是参考项目的 workspace 包），也不允许
 * 写 TypeScript 类型。这里只保留运行时用得到的字符串常量，取值与
 * `packages/@openmaic/dsl/src/slides.ts` 的 `ElementTypes` 完全一致。
 */
export const ElementTypes = {
  TEXT: 'text',
  IMAGE: 'image',
  SHAPE: 'shape',
  LINE: 'line',
  CHART: 'chart',
  TABLE: 'table',
  LATEX: 'latex',
  VIDEO: 'video',
  AUDIO: 'audio',
  CODE: 'code',
};
