import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const profilePage = readFileSync(new URL("../src/pages/ProfilePage.jsx", import.meta.url), "utf8");
const profileStyles = readFileSync(new URL("../src/styles/profile-patch.css", import.meta.url), "utf8");

test("personal center uses GooeyNav for its three section tabs", () => {
  assert.match(profilePage, /import GooeyNav from ["']\.\.\/components\/FloatingNav\/GooeyNav\.jsx["']/);
  assert.match(profilePage, /<GooeyNav[\s\S]*className=["']profile-gooey-nav["'][\s\S]*onSelect=/);
  assert.match(profilePage, /activeIndex=\{TABS\.findIndex\(\(item\) => item\.key === tab\)\}/);
  assert.doesNotMatch(profilePage, /className=\{tab === item\.key \? ["']active["'] : ["']["']\}/);
});

test("personal center GooeyNav keeps a responsive accessible pill treatment", () => {
  assert.match(profileStyles, /\.profile-gooey-nav[\s\S]*--profile-nav-pill/);
  assert.match(profileStyles, /\.profile-gooey-nav[\s\S]*\.floating-nav-button[\s\S]*width: auto/);
  assert.match(profileStyles, /\.profile-gooey-nav[\s\S]*\.floating-nav-button[\s\S]*overflow: visible/);
  assert.match(profileStyles, /\.profile-gooey-label[\s\S]*white-space: nowrap/);
  assert.match(profileStyles, /\.profile-gooey-nav[\s\S]*\.floating-nav-button:focus-visible/);
  assert.match(profileStyles, /@media \(max-width: 760px\)[\s\S]*\.profile-gooey-nav/);
});
