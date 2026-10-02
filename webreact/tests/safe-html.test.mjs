import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { url: "https://example.test" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const { sanitizeHtml, renderSafeMarkdown } = await import("../src/utils/safeHtml.js");
test.after(() => dom.window.close());

function fragment(html) {
  const element = document.createElement("div");
  element.innerHTML = html;
  return element;
}

test("rich HTML removes executable elements, events and namespace links", () => {
  const html = sanitizeHtml('<img src="x" onerror="window.probe=1"><script>alert(1)</script><iframe srcdoc="evil"></iframe><svg onload="evil"><a href="javascript:void(0)" xlink:href="javascript:window.probe=1"><text>probe</text></a></svg>');
  const element = fragment(html);
  assert.equal(element.querySelector("script,iframe"), null);
  for (const node of element.querySelectorAll("*")) {
    for (const attr of node.attributes) {
      assert.ok(!/^on/i.test(attr.name));
      assert.ok(!/^javascript:/i.test(attr.value));
    }
  }
  assert.equal(element.querySelector("img").getAttribute("src"), "x");
});

test("markdown keeps safe formatting and links without accepting raw SVG", () => {
  const element = fragment(renderSafeMarkdown('**正文** [来源](https://example.test/source)\n<img src="x" onerror="evil">\n<svg><a xlink:href="javascript:evil">link</a></svg>'));
  assert.equal(element.querySelector("strong").textContent, "正文");
  assert.equal(element.querySelector("a").getAttribute("href"), "https://example.test/source");
  assert.equal(element.querySelector("a").getAttribute("rel"), "noopener noreferrer");
  assert.equal(element.querySelector("svg"), null);
  assert.equal(element.querySelector("img").getAttribute("onerror"), null);
});

test("slide HTML retains styled text, SVG paths and formula MathML", () => {
  const element = fragment(sanitizeHtml('<p style="color: red"><strong>slide</strong></p><svg viewBox="0 0 10 10"><path d="M0 0 L10 10"></path></svg><math><mi>x</mi></math>'));
  assert.equal(element.querySelector("strong").textContent, "slide");
  assert.equal(element.querySelector("p").getAttribute("style"), "color: red");
  assert.equal(element.querySelector("path").getAttribute("d"), "M0 0 L10 10");
  assert.equal(element.querySelector("math mi").textContent, "x");
});
