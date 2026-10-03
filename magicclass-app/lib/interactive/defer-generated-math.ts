import { parse, type DefaultTreeAdapterTypes } from 'parse5';

const KATEX_BASE = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/';

/** Move only the generator's known KaTeX bootstrap off the document's parse path.
 * Historical classroom HTML keeps its authored scripts and their execution order.
 */
export function deferGeneratedMath(html: string): string {
  if (!html.includes(KATEX_BASE)) return html;
  const replacements: { start: number; end: number; text: string }[] = [];
  const visit = (node: DefaultTreeAdapterTypes.ParentNode) => {
    const children = node.childNodes.filter(
      (child) => !('value' in child) || child.value.trim() !== '',
    );
    for (let i = 0; i < children.length; i++) {
      const group = children.slice(i, i + 4);
      if (group.length === 4 && group.every((child) => 'tagName' in child)) {
        const [css, katex, auto, init] = group as DefaultTreeAdapterTypes.Element[];
        const attr = (el: DefaultTreeAdapterTypes.Element, name: string) =>
          el.attrs.find((a) => a.name === name)?.value;
        const code = init.childNodes
          .filter((child) => child.nodeName === '#text')
          .map((child) => (child as DefaultTreeAdapterTypes.TextNode).value)
          .join('');
        const body = code.match(/^\s*document\.addEventListener\("DOMContentLoaded", function\(\) \{([\s\S]*)\}\);\s*$/)?.[1];
        if (
          css.tagName === 'link' && attr(css, 'rel') === 'stylesheet' &&
          attr(css, 'href') === KATEX_BASE + 'katex.min.css' &&
          katex.tagName === 'script' && attr(katex, 'src') === KATEX_BASE + 'katex.min.js' &&
          auto.tagName === 'script' && attr(auto, 'src') === KATEX_BASE + 'contrib/auto-render.min.js' &&
          init.tagName === 'script' && !attr(init, 'src') &&
          body?.includes('const katexOptions = {') &&
          body.includes('renderMathInElement(document.body, katexOptions);') &&
          css.sourceCodeLocation && init.sourceCodeLocation
        ) {
          replacements.push({
            start: css.sourceCodeLocation.startOffset,
            end: init.sourceCodeLocation.endOffset,
            text: `<script data-iframe-deferred-math>
(function () {
  function renderMath() {${body}}
  function loadScript(url, done) {
    var script = document.createElement('script');
    script.src = url;
    script.onload = done;
    script.onerror = function () { console.error('Unable to load interactive math: ' + url); };
    document.head.appendChild(script);
  }
  function start() {
    var css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = '${KATEX_BASE}katex.min.css';
    document.head.appendChild(css);
    loadScript('${KATEX_BASE}katex.min.js', function () {
      loadScript('${KATEX_BASE}contrib/auto-render.min.js', renderMath);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
</script>`,
          });
        }
      }
      const child = children[i];
      if ('childNodes' in child) visit(child);
    }
  };
  visit(parse(html, { sourceCodeLocationInfo: true }));
  for (const replacement of replacements.sort((a, b) => b.start - a.start)) {
    html = html.slice(0, replacement.start) + replacement.text + html.slice(replacement.end);
  }
  return html;
}
