/**
 * 移植补充：元素 DOM 契约。
 *
 * 逐字移植自参考 `components/slide-renderer/element-dom.ts`（只去掉类型标注）。
 * 唯一改动：调用方通过命名参数传值，因此形参名保持 `elementId: string` 的语义。
 */
export const EDITABLE_ELEMENT_ID_PREFIX = 'editable-element-';
export const SCREEN_ELEMENT_ID_PREFIX = 'screen-element-';

/** Renderer-agnostic "this subtree paints element X" marker. */
export const MAIC_ELEMENT_ID_ATTRIBUTE = 'data-maic-element-id';

export function editableElementDomId(elementId) {
  return `${EDITABLE_ELEMENT_ID_PREFIX}${elementId}`;
}

export function screenElementDomId(elementId) {
  return `${SCREEN_ELEMENT_ID_PREFIX}${elementId}`;
}

/** Spread onto an element host so the attribute name is written once. */
export function maicElementIdAttributes(elementId) {
  return { [MAIC_ELEMENT_ID_ATTRIBUTE]: elementId };
}
