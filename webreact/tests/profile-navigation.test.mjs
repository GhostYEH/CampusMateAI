import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const profilePage = readFileSync(new URL("../src/pages/ProfilePage.jsx", import.meta.url), "utf8");
const profileStyles = readFileSync(new URL("../src/styles/profile-patch.css", import.meta.url), "utf8");

test("personal center uses LiquidMetalNav for its three section tabs", () => {
  assert.match(profilePage, /import LiquidMetalNav from ["']\.\.\/components\/FloatingNav\/LiquidMetalNav\.jsx["']/);
  assert.match(profilePage, /<LiquidMetalNav[\s\S]*className=["']profile-liquid-nav["'][\s\S]*onSelect=/);
  assert.match(profilePage, /activeIndex=\{TABS\.findIndex\(\(item\) => item\.key === tab\)\}/);
  assert.doesNotMatch(profilePage, /className=\{tab === item\.key \? ["']active["'] : ["']["']\}/);
});

test("personal center liquid metal navigation keeps a responsive accessible pill treatment", () => {
  assert.doesNotMatch(profileStyles, /--profile-nav-pill/);
  assert.match(profileStyles, /\.profile-liquid-nav[\s\S]*\.floating-nav-button[\s\S]*width: auto/);
  assert.match(profileStyles, /\.profile-liquid-nav[\s\S]*\.floating-nav-button[\s\S]*overflow: visible/);
  assert.match(profileStyles, /\.profile-liquid-label[\s\S]*white-space: nowrap/);
  assert.match(profileStyles, /\.profile-liquid-nav[\s\S]*\.floating-nav-button:focus-visible/);
  assert.match(profileStyles, /@media \(max-width: 760px\)[\s\S]*\.profile-liquid-nav/);
});
