/**
 * `.maic.zip` 的 Web 侧契约测试。
 *
 * 三件事在这里钉住：
 *
 * 1. **下载名来自服务端**，中文只可能出现在 RFC 5987 的 `filename*` 里；解析不到
 *    时给一个确定的名字，绝不把整个响应头当文件名。
 * 2. **导出必须按 blob 取**，否则 axios 会把 zip 当文本处理，存下来的文件是坏的。
 * 3. **两个方向各自按能力开关**：能导出不等于能导入。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import { describeFusionState } from "../src/features/openmaic/homeModel.js";
import {
  MAX_ARCHIVE_BYTES,
  describeArchiveError,
  filenameFromContentDisposition,
  normalizeImportedStage,
  sanitizeFilename,
  validateImportCandidate,
} from "../src/features/openmaic/archiveModel.js";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");
const apiSource = read("src/data/api.js");
const panelSource = read("src/components/openmaic/WorkspacePanel.jsx");
const homeSource = read("src/components/openmaic/OpenMAICHome.jsx");

// ===== 下载名 =====

test("a Chinese download name is taken from the RFC 5987 filename* form", () => {
  const header = 'attachment; filename="archive.maic.zip"; filename*=UTF-8\'\'%E7%AC%AC%E4%B8%80%E7%AB%A0.maic.zip';
  assert.equal(filenameFromContentDisposition(header), "第一章.maic.zip");
});

test("a plain ASCII filename is used when there is no extended form", () => {
  assert.equal(filenameFromContentDisposition('attachment; filename="notes.maic.zip"'), "notes.maic.zip");
});

test("a bare filename without quotes is still understood", () => {
  assert.equal(filenameFromContentDisposition("attachment; filename=notes.maic.zip"), "notes.maic.zip");
});

test("a malformed percent-escape falls back instead of producing mojibake", () => {
  const header = "attachment; filename*=UTF-8''%E7%AC%AC%E4%B8%8.maic.zip";
  assert.equal(filenameFromContentDisposition(header), "学习内容.maic.zip");
});

test("a missing or empty header gets a definite name, not the whole header", () => {
  assert.equal(filenameFromContentDisposition(""), "学习内容.maic.zip");
  assert.equal(filenameFromContentDisposition(undefined), "学习内容.maic.zip");
  assert.equal(filenameFromContentDisposition("attachment"), "学习内容.maic.zip");
});

test("a filename is a name and never a path", () => {
  // 关键性质是"不含路径分隔符、不含控制字符"，而不是某个具体的替换间距。
  for (const raw of ["../../etc/passwd", "a\\b.maic.zip", "C:\\tmp\\x.zip", "bad\u0000name.zip"]) {
    const cleaned = sanitizeFilename(raw);
    assert.ok(!cleaned.includes("/"), `${raw} -> ${cleaned}`);
    assert.ok(!cleaned.includes("\\"), `${raw} -> ${cleaned}`);
    // eslint-disable-next-line no-control-regex
    assert.ok(!/[\u0000-\u001f\u007f]/.test(cleaned), `${raw} -> ${cleaned}`);
  }
  assert.equal(sanitizeFilename("  "), "学习内容.maic.zip");
  assert.ok(!sanitizeFilename("x".repeat(500)).includes("/"));
});

// ===== 导入前自查 =====

test("the import pre-check refuses empty, oversize and non-zip candidates", () => {
  assert.equal(validateImportCandidate(null), "请选择一个 .maic.zip 档案。");
  assert.equal(validateImportCandidate({ name: "", size: 1 }), "文件名不能为空。");
  assert.match(validateImportCandidate({ name: "a/b.zip", size: 1 }), /路径分隔符/);
  assert.match(validateImportCandidate({ name: "讲义.md", size: 10 }), /请选择 \.maic\.zip/);
  assert.match(validateImportCandidate({ name: "空.zip", size: 0 }), /是空的/);
  assert.match(validateImportCandidate({ name: "大.zip", size: MAX_ARCHIVE_BYTES + 1 }), /不能超过/);
  assert.equal(validateImportCandidate({ name: "第一章.maic.zip", size: 2048 }), null);
});

// ===== 导入结果 =====

test("an imported stage is mapped from the server payload", () => {
  const imported = normalizeImportedStage({
    stage: { id: "stg_1", workspace_id: "ws_1", course_id: "c1", title: "第一章", revision: 1, dsl_version: "0.3.0" },
    migrated: true,
    source_workspace_name: "期末复习",
  });
  assert.equal(imported.id, "stg_1");
  assert.equal(imported.workspaceId, "ws_1");
  assert.equal(imported.migrated, true);
  assert.equal(imported.sourceWorkspaceName, "期末复习");
});

test("a payload without a stage is not turned into a phantom import", () => {
  assert.equal(normalizeImportedStage(null), null);
  assert.equal(normalizeImportedStage({ ok: true }), null);
});

// ===== 失败翻译 =====

test("a rejected archive surfaces the service's own reason", () => {
  const described = describeArchiveError({
    response: { status: 422, data: { code: "OPENMAIC_DOCUMENT_REJECTED", message: "内容未通过校验", details: { service_message: "archive has no manifest.json" } } },
  });
  assert.equal(described.kind, "rejected");
  assert.equal(described.retryable, false);
  assert.equal(described.message, "archive has no manifest.json");
});

test("a rejected archive without a service message still says something actionable", () => {
  const described = describeArchiveError({ response: { status: 422, data: {} } });
  assert.equal(described.kind, "rejected");
  assert.ok(described.message.length > 0);
});

test("the archive failures map to distinct kinds", () => {
  assert.equal(describeArchiveError({ response: { status: 503 } }).kind, "unavailable");
  assert.equal(describeArchiveError({ response: { status: 404 } }).kind, "notFound");
  assert.equal(describeArchiveError({ response: { status: 400 } }).kind, "invalid");
  assert.equal(describeArchiveError({ response: { status: 409 } }).kind, "conflict");
  assert.equal(describeArchiveError({}).kind, "unknown");
  assert.equal(describeArchiveError({ response: { status: 503 } }).retryable, true);
});

// ===== API =====

test("exporting asks for a blob from the stage export route", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onGet("/courses/c1/workspaces/ws_1/stages/stg_1/export", new Uint8Array([1, 2, 3]));

  await apiModule.exportOpenMAICStage("c1", "ws_1", "stg_1");

  const request = mock.lastRequest();
  assert.equal(request.method, "get");
  assert.equal(request.url, "/courses/c1/workspaces/ws_1/stages/stg_1/export");
  // 响应类型无法通过 mock 适配器观察，所以按源码契约钉住：不是 blob 就会存出坏文件。
  assert.match(apiSource, /responseType:\s*"blob"/);
});

test("importing posts a multipart form with the idempotency key", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onPost("/courses/c1/workspaces/ws_1/import", { stage: { id: "stg_new" } }, 201);

  const file = new File([new Uint8Array([1, 2, 3])], "第一章.maic.zip", { type: "application/zip" });
  await apiModule.importOpenMAICStage("c1", "ws_1", { file, idempotencyKey: "key-1" });

  const request = mock.lastRequest();
  assert.equal(request.url, "/courses/c1/workspaces/ws_1/import");
  assert.equal(request.headers["Idempotency-Key"], "key-1");
  assert.equal(request.headers["Content-Type"], "multipart/form-data");
  assert.ok(request.data instanceof FormData);
  assert.equal(request.data.get("file").name, "第一章.maic.zip");
});

// ===== 入口开关与源码契约 =====

test("export and import each open only on their own capability", () => {
  const neither = describeFusionState({ state: "ready", capabilities: ["workspace"] });
  assert.equal(neither.canExportArchive, false);
  assert.equal(neither.canImportArchive, false);

  const exportOnly = describeFusionState({ state: "ready", capabilities: ["export-maic"] });
  assert.equal(exportOnly.canExportArchive, true);
  assert.equal(exportOnly.canImportArchive, false);

  const importOnly = describeFusionState({ state: "ready", capabilities: ["import-maic"] });
  assert.equal(importOnly.canExportArchive, false);
  assert.equal(importOnly.canImportArchive, true);

  // 未就绪时即使上报了能力也不开入口。
  const degraded = describeFusionState({ state: "degraded", capabilities: ["export-maic", "import-maic"] });
  assert.equal(degraded.canExportArchive, false);
  assert.equal(degraded.canImportArchive, false);
});

test("the home passes both archive capabilities down to the workspace panel", () => {
  assert.match(homeSource, /canExportArchive=\{status\.canExportArchive\}/);
  assert.match(homeSource, /canImportArchive=\{status\.canImportArchive\}/);
});

test("the panel gates both entries on the capability and never renders them unconditionally", () => {
  assert.match(panelSource, /\{canExportArchive \? <Button/);
  assert.match(panelSource, /\{canImportArchive \? <div className="openmaic-command">/);
});

test("the panel downloads under the server's filename and reuses one key across a retry", () => {
  assert.match(panelSource, /filenameFromContentDisposition\(result\.disposition\)/);
  assert.match(panelSource, /pendingKey\.current = pendingKey\.current \|\| api\.newIdempotencyKey\(\)/);
  assert.match(panelSource, /if \(!described\.retryable\) pendingKey\.current = null/);
});
