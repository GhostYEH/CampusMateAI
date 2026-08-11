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

test("keeps the sidebar brand mark and avatar square when collapsed", async () => {
  const css = await readFile(path.join(webRoot, "src", "styles.css"), "utf8");
  const brandMark = declarationsFor(css, ".sidebar .brand-mark");
  const avatar = declarationsFor(css, ".sidebar .avatar");
  const collapsedProfile = declarationsFor(css, ".collapsed .profile-mini");
  const collapsedProfileContent = declarationsFor(css, ".collapsed .profile-mini-copy,.collapsed .profile-mini>svg");

  assert.match(brandMark, /width\s*:\s*46px/i);
  assert.match(brandMark, /height\s*:\s*46px/i);
  assert.match(brandMark, /flex\s*:\s*0\s+0\s+46px/i);
  assert.match(avatar, /width\s*:\s*44px/i);
  assert.match(avatar, /height\s*:\s*44px/i);
  assert.match(avatar, /flex\s*:\s*0\s+0\s+44px/i);
  assert.match(collapsedProfile, /justify-content\s*:\s*center/i);
  assert.match(collapsedProfile, /gap\s*:\s*0/i);
  assert.match(collapsedProfileContent, /display\s*:\s*none/i);
});
