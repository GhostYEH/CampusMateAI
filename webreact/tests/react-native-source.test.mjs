import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const sourceRoot = new URL("../src/", import.meta.url);
const toPlatformPath = (url, platform = process.platform) =>
  fileURLToPath(url, { windows: platform === "win32" });
const rootPath = toPlatformPath(sourceRoot);

function filesIn(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? filesIn(path) : [path];
  });
}

test("the webreact runtime is authored with React modules only", () => {
  const sourceFiles = filesIn(rootPath).filter((path) => /\.(jsx?|css)$/.test(path));
  const forbidden = /from\s+["'][^"']*(?:vue|pinia)[^"']*["']|<[^>]+\.vue|@vue|pinia/i;
  for (const path of sourceFiles) {
    assert.doesNotMatch(readFileSync(path, "utf8"), forbidden, path);
  }
  assert.ok(sourceFiles.some((path) => path.endsWith("App.jsx")));
});

test("source URLs keep POSIX separators on Linux", () => {
  assert.equal(
    toPlatformPath(new URL("file:///home/runner/work/CampusMateAI/webreact/src/"), "linux"),
    "/home/runner/work/CampusMateAI/webreact/src/",
  );
});
