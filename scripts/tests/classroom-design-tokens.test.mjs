import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const root = new URL("../../", import.meta.url);
const read = (path) => readFileSync(new URL(path, root), "utf8");

const INK = "153b34";
const PAPER = "f2f1e8";
const AMBER = "dab27a";
const COPPER = "ad6845";

test("Web learning space and iOS classroom use the Android classroom palette", () => {
  const web = read("webreact/src/styles/learning-space-native.css").toLowerCase();
  for (const token of [INK, PAPER, AMBER, COPPER]) assert.match(web, new RegExp(`#${token}`));

  const iosTheme = read("ios/CampusMate/Design/CampusTheme.swift").toLowerCase();
  for (const token of [INK, PAPER, AMBER]) assert.match(iosTheme, new RegExp(`0x${token}`));
  assert.match(iosTheme, /static let classroom/);

  const androidShell = read("android/app/src/main/java/com/example/campusai/ui/screens/courses/ClassroomViewer.kt");
  assert.match(androidShell, /0xFF153B34/);
  assert.match(androidShell, /0xFFF2F1E8/);
  const androidHub = read("android/app/src/main/java/com/example/campusai/ui/screens/courses/ClassroomHubArt.kt");
  assert.match(androidHub, /0xFFDAB27A/);
});

test("iOS classroom views opt into the classroom palette instead of the global moss palette", () => {
  const ios = read("ios/CampusMate/Features/Classroom/ClassroomView.swift");
  assert.match(ios, /private var palette: CampusPalette \{ \.classroom \}/);
  assert.match(ios, /\.campusPalette\(\.classroom\)/);
});

test("mobile classroom HUD awards first visits only and uses the Web page XP", () => {
  for (const path of [
    "ios/CampusMate/Features/Classroom/ClassroomRewards.swift",
    "android/app/src/main/java/com/example/campusai/ui/screens/courses/ClassroomViewer.kt",
  ]) {
    const source = read(path);
    assert.match(source, /var firstVisit = state\.pages\.indexOf\(current\) < 0;/);
    assert.match(source, /if \(firstVisit\) \{[\s\S]*state\.xp \+= 12;[\s\S]*state\.pages\.push\(current\);/);
    assert.doesNotMatch(source, /state\.xp \+= 10;/);
  }
});
