import { INTERACTIVE_REFERENCE_EXCLUDED_TAG_NAMES } from './element-reference-policy.js';

/**
 * 移植自参考项目 `lib/utils/html-document.ts` 的 `injectIntoDocumentHead`。
 *
 * 参考实现用 `parse5` 解析 HTML 拿到 head 的源码偏移——目标项目没有 parse5
 * 依赖。这里是**等价的近似替换**：用标签扫描定位 `<head ...>` 起始标签的结束位置，
 * 退化顺序与上游完全一致：
 *   1. 显式 `<head>` 起始标签之后
 *   2. 否则 head 第一个子节点的位置
 *   3. 否则 `<html ...>` 起始标签之后，插入 `<head>…</head>`
 *   4. 否则 doctype 之后，插入 `<head>…</head>`
 *   5. 否则整体前置 `<head>…</head>`
 *
 * 对生成式课件里的常规 HTML（一定有 doctype + html + head）结果与 parse5 版本一致。
 */
function findStartTagEnd(html, tagName) {
  const re = new RegExp(`<${tagName}(\\s[^>]*)?>`, 'i');
  const match = re.exec(html);
  return match ? match.index + match[0].length : -1;
}

export function injectIntoDocumentHead(html, injection) {
  const source = typeof html === 'string' ? html : '';
  if (!source) return `<head>${injection}</head>`;

  // 1. 显式 <head>：注入到它的起始标签之后。
  const headStartTagEnd = findStartTagEnd(source, 'head');
  if (headStartTagEnd !== -1) {
    return source.slice(0, headStartTagEnd) + injection + source.slice(headStartTagEnd);
  }

  // 2. 没有显式 <head>，但解析器会在 <html> 之后隐式建 head：此时"head 的第一个
  //    子节点"就是 <html> 起始标签之后的第一个标签，等价于 3，只是插到该标签之前。
  const htmlStartTagEnd = findStartTagEnd(source, 'html');
  if (htmlStartTagEnd !== -1) {
    return source.slice(0, htmlStartTagEnd) + `<head>${injection}</head>` + source.slice(htmlStartTagEnd);
  }

  // 3. doctype 之后。
  const doctype = /<!doctype[^>]*>/i.exec(source);
  if (doctype) {
    const end = doctype.index + doctype[0].length;
    return source.slice(0, end) + `<head>${injection}</head>` + source.slice(end);
  }

  return `<head>${injection}</head>${source}`;
}

export { INTERACTIVE_REFERENCE_EXCLUDED_TAG_NAMES };
