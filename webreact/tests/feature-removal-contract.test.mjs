import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const read = (file) => readFileSync(resolve(root, file), "utf8");

test("web routes remove the three retired feature families and keep community", () => {
  const app = read("webreact/src/App.jsx");

  for (const path of ["/services", "/classrooms", "/lostfound"]) {
    assert.equal(app.includes(`path=\"${path}\"`), false, `router still exposes ${path}`);
  }
  assert.match(app, /path=\"\/community\"/);
});

test("wechat home removes retired shortcuts and keeps the community shortcut", () => {
  const index = read("wx/miniprogram/pages/index/index.ts");
  assert.doesNotMatch(index, /pages\/classrooms\/classrooms|pages\/lostfound\/lostfound|空教室|失物招领/);
  assert.match(index, /pages\/community\/community/);
});

test("android and harmony route registries remove retired destinations and keep community", () => {
  const androidNav = read("android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt");
  const androidSpec = read("android/app/src/main/java/com/example/campusai/ui/navigation/SecondaryDestinationSpec.kt");
  const harmonyRoute = read("harmony/entry/src/main/ets/navigation/AppRoute.ets");

  assert.doesNotMatch(androidNav, /composable\("classrooms"\)|composable\("services"\)|composable\("lostfound"\)/);
  assert.doesNotMatch(androidSpec, /"classrooms"|"services"|"lostfound/);
  assert.doesNotMatch(harmonyRoute, /CLASSROOMS|LOST_FOUND|classrooms|lostfound/);
  assert.match(androidNav, /route = "community\?sort=/);
  assert.match(androidSpec, /"community" to/);
  assert.match(harmonyRoute, /COMMUNITY/);
});
