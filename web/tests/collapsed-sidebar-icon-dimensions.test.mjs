import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function declarationsFor(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`));
  assert.ok(match, `Missing CSS rule: ${selector}`);
  return match[1];
}

function atRuleBody(css, signature) {
  const start = css.indexOf(signature);
  assert.notEqual(start, -1, `Missing CSS at-rule: ${signature}`);
  const open = css.indexOf("{", start);
  let depth = 0;

  for (let index = open; index < css.length; index += 1) {
    if (css[index] === "{") depth += 1;
    if (css[index] === "}") depth -= 1;
    if (depth === 0) return css.slice(open + 1, index);
  }

  assert.fail(`Unclosed CSS at-rule: ${signature}`);
}

test("centers the student brand and avatar on the desktop collapsed rail", async () => {
  const css = await readFile(path.join(webRoot, "src", "styles", "student-home.css"), "utf8");
  const desktopCollapsed = atRuleBody(css, "@media(min-width:901px)");
  const brand = declarationsFor(desktopCollapsed, ".student-layout.collapsed .sidebar .brand");
  const brandMark = declarationsFor(desktopCollapsed, ".student-layout.collapsed .brand-mark");
  const profile = declarationsFor(desktopCollapsed, ".student-layout.collapsed .profile-mini");
  const avatar = declarationsFor(desktopCollapsed, ".student-layout.collapsed .profile-mini .avatar");
  const hiddenProfileContent = declarationsFor(
    desktopCollapsed,
    ".student-layout.collapsed .profile-mini-copy,.student-layout.collapsed .profile-mini>svg",
  );

  assert.match(brand, /padding-inline\s*:\s*0/i);
  assert.match(brand, /justify-content\s*:\s*center/i);
  assert.match(brandMark, /width\s*:\s*46px/i);
  assert.match(brandMark, /height\s*:\s*46px/i);
  assert.match(brandMark, /flex\s*:\s*0\s+0\s+46px/i);
  assert.match(profile, /grid-template-columns\s*:\s*minmax\(0\s*,\s*1fr\)/i);
  assert.match(profile, /gap\s*:\s*0/i);
  assert.match(profile, /padding-inline\s*:\s*0/i);
  assert.match(profile, /justify-items\s*:\s*center/i);
  assert.match(avatar, /width\s*:\s*44px/i);
  assert.match(avatar, /height\s*:\s*44px/i);
  assert.match(avatar, /flex\s*:\s*0\s+0\s+44px/i);
  assert.match(hiddenProfileContent, /display\s*:\s*none/i);
});
