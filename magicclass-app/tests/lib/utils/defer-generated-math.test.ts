import { describe, expect, it } from 'vitest';
import { postProcessInteractiveHtml } from '@/packages/@magicclass/generation/src/interactive-post-processor';
import { deferGeneratedMath } from '@/lib/interactive/defer-generated-math';

describe('historical generated math bootstrap', () => {
  it('removes parser blocking resources while preserving math initialization and page scripts', () => {
    const page = '<html><head></head><body><p>\\(x^2\\)</p><script>window.widget = true;</script></body></html>';
    const original = postProcessInteractiveHtml(page);
    const patched = deferGeneratedMath(original);
    expect(patched).toContain('data-iframe-deferred-math');
    expect(patched).not.toContain('<script src="https://cdn.jsdelivr.net');
    expect(patched).not.toContain('<link rel="stylesheet"');
    expect(patched).toContain('renderMathInElement(document.body, katexOptions);');
    expect(patched).toContain('<script>window.widget = true;</script>');
    expect(deferGeneratedMath(patched)).toBe(patched);
  });

  it('does not rewrite authored CDN scripts or matching markup inside scripts/comments', () => {
    const authored = '<html><head><script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script><script>katex.render("x", el)</script></head></html>';
    expect(deferGeneratedMath(authored)).toBe(authored);
    const generated = postProcessInteractiveHtml('<html><head></head><body>math</body></html>');
    const scriptTemplate = `<html><head><script type="text/plain">${generated.replaceAll('</script>', '<\\/script>')}</script></head></html>`;
    expect(deferGeneratedMath(scriptTemplate)).toBe(scriptTemplate);
    expect(deferGeneratedMath(`<!-- ${generated} -->`)).toBe(`<!-- ${generated} -->`);
  });
});
