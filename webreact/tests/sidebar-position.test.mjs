import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const styles = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const floatingLayout = fs.readFileSync(new URL("../src/styles/floating-layout.css", import.meta.url), "utf8");

test("floating navigation is fixed and does not reserve sidebar space", () => {
  assert.match(floatingLayout, /\.floating-nav\s*\{[^}]*position:\s*fixed;/s);
  assert.match(floatingLayout, /\.floating-nav\s*\{[^}]*left:\s*50%;/s);
  assert.match(floatingLayout, /\.floating-nav\s*\{[^}]*width:\s*max-content;/s);
  assert.doesNotMatch(floatingLayout, /--floating-nav-collapsed-width/);
  assert.doesNotMatch(styles, /\.sidebar\s*\{/);
});
