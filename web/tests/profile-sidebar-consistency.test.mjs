import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("keeps the student shell unchanged on the personal center", async () => {
  const css = await readFile(
    path.join(webRoot, "src", "styles", "student-profile-reference.css"),
    "utf8",
  );

  assert.doesNotMatch(
    css,
    /\.app-layout(?::has|\.collapsed:has)\(\.profile-redesign\)/,
    "Personal-center styles must not override the shared student shell",
  );
});
