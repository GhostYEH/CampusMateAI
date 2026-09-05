import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const component = fs.readFileSync(new URL("../src/components/LineSidebar.jsx", import.meta.url), "utf8");
const styles = fs.readFileSync(new URL("../src/components/LineSidebar.css", import.meta.url), "utf8");
const community = fs.readFileSync(new URL("../src/pages/CommunityPage.jsx", import.meta.url), "utf8");
const communityStyles = fs.readFileSync(new URL("../src/styles/community.css", import.meta.url), "utf8");

test("LineSidebar exposes accessible clickable items with an animated proximity effect", () => {
  assert.match(component, /role=\"list\"/);
  assert.match(component, /<button/);
  assert.match(component, /aria-current/);
  assert.match(component, /requestAnimationFrame/);
  assert.match(component, /onPointerMove/);
  assert.match(styles, /--effect/);
  assert.match(styles, /translateX/);
  assert.match(styles, /prefers-reduced-motion/);
});

test("community categories are rendered by LineSidebar and keep the filter callback", () => {
  assert.match(community, /import LineSidebar from \"\.\.\/components\/LineSidebar\.jsx\"/);
  assert.match(community, /<LineSidebar[\s\S]*items=\{categorySidebarItems\}/);
  assert.match(community, /categorySidebarItems\[_index\]\.key/);
  assert.match(communityStyles, /grid-template-columns:\s*196px minmax\(0, 1fr\) 290px/);
  assert.match(communityStyles, /\.forum-filter-sidebar/);
});
