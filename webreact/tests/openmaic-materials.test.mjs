/**
 * 课程资料的 Web 侧契约测试。
 *
 * 三件事在界面上最容易撒谎或"点了没反应"，所以单独钉住：
 *
 * 1. **解析不了的资料不能显示正文。** 状态是 `unsupported` 时正文必须为空，
 *    否则一块空白会被读成"这个文件是空的"。
 * 2. **写请求必须带协议要求的头**（上传 Idempotency-Key、删除 If-Match）。
 * 3. **入口按真实 capability 开关**，`material` 未上报时整块不渲染。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// 必须先于 api.js 加载，给 localStorage / location 提供确定性实现。
import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import { describeFusionState } from "../src/features/openmaic/homeModel.js";
import {
  MAX_UPLOAD_BYTES,
  describeExtractionStatus,
  describeMaterialError,
  formatBytes,
  nextCursorOf,
  normalizeMaterialDetail,
  normalizeMaterialList,
  normalizeMaterialResolution,
  referenceIds,
  upsertMaterial,
  validateUploadCandidate,
} from "../src/features/openmaic/materialsModel.js";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");
const panelSource = read("src/components/openmaic/MaterialsPanel.jsx");
const homeSource = read("src/components/openmaic/OpenMAICHome.jsx");

// ===== 视图模型 =====

test("material list normalisation keeps the server revision as the credential", () => {
  const items = normalizeMaterialList({
    items: [
      { id: "mt_1", course_id: "c1", filename: "讲义.md", media_type: "text/markdown", byte_size: 2048, revision: 3, extraction_status: "extracted", text_chars: 12 },
      { id: "", filename: "丢弃" },
      null,
    ],
  });
  assert.equal(items.length, 1);
  assert.equal(items[0].revision, 3);
  assert.equal(items[0].filename, "讲义.md");
  assert.equal(items[0].textChars, 12);
  assert.equal(items[0].text, undefined);
});

test("material list normalisation tolerates a missing payload", () => {
  assert.deepEqual(normalizeMaterialList(null), []);
  assert.deepEqual(normalizeMaterialList({}), []);
  assert.deepEqual(normalizeMaterialList(undefined), []);
});

test("a detail whose extraction failed never carries text", () => {
  const detail = normalizeMaterialDetail({
    id: "mt_1",
    filename: "课件.pptx",
    extraction_status: "unsupported",
    text: "这段正文本不该存在",
  });
  assert.equal(detail.extractionStatus, "unsupported");
  assert.equal(detail.text, "");
});

test("a detail whose extraction succeeded keeps its text", () => {
  const detail = normalizeMaterialDetail({
    id: "mt_1",
    filename: "讲义.md",
    extraction_status: "extracted",
    text: "# 第一章",
  });
  assert.equal(detail.text, "# 第一章");
});

test("an unknown extraction status is reported as unknown, never guessed", () => {
  const described = describeExtractionStatus("something-new");
  assert.equal(described.label, "状态未知");
  assert.match(described.hint, /未识别/);
  assert.equal(describeExtractionStatus("extracted").label, "已解析");
  assert.equal(describeExtractionStatus("unsupported").label, "无正文");
  assert.match(describeExtractionStatus("unsupported").hint, /不能被引用为正文/);
});

test("resolution maps authorised references and the ids that did not resolve", () => {
  const { resolved, unresolved } = normalizeMaterialResolution({
    resolved: [{ id: "mt_1", filename: "甲.md", text_chars: 3 }],
    unresolved: ["mt_ghost", "", 7],
  });
  assert.equal(resolved.length, 1);
  assert.equal(resolved[0].filename, "甲.md");
  assert.deepEqual(unresolved, ["mt_ghost"]);
});

test("only successfully extracted materials may become references", () => {
  const ids = referenceIds([
    { id: "mt_1", extractionStatus: "extracted" },
    { id: "mt_2", extractionStatus: "unsupported" },
    { id: "mt_3", extractionStatus: "empty" },
    { id: "mt_4", extractionStatus: "extracted" },
  ]);
  assert.deepEqual(ids, ["mt_1", "mt_4"]);
});

test("upserting the same material twice keeps one row", () => {
  const first = [{ id: "mt_1", filename: "旧名.md", revision: 1 }];
  const next = upsertMaterial(first, { id: "mt_1", filename: "新名.md", revision: 2 });
  assert.equal(next.length, 1);
  assert.equal(next[0].filename, "新名.md");
});

test("the upload pre-check refuses oversized and path-shaped candidates", () => {
  assert.equal(validateUploadCandidate(null), "请选择一个文件。");
  assert.equal(validateUploadCandidate({ name: "", size: 1 }), "文件名不能为空。");
  assert.match(validateUploadCandidate({ name: "a/b.md", size: 1 }), /路径分隔符/);
  assert.match(validateUploadCandidate({ name: "a\\b.md", size: 1 }), /路径分隔符/);
  assert.match(validateUploadCandidate({ name: "大.md", size: MAX_UPLOAD_BYTES + 1 }), /不能超过/);
  assert.equal(validateUploadCandidate({ name: "讲义.md", size: 1024 }), null);
  // 空文件不是错误：服务端会把它记成 empty，界面据实显示。
  assert.equal(validateUploadCandidate({ name: "空.md", size: 0 }), null);
});

test("byte sizes render as a size or an honest unknown", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(2048), "2.0 KB");
  assert.equal(formatBytes(3 * 1024 * 1024), "3.0 MB");
  assert.equal(formatBytes("nope"), "未知大小");
});

test("the cursor is passed back verbatim and never parsed", () => {
  assert.equal(nextCursorOf({ next_cursor: "abc" }), "abc");
  assert.equal(nextCursorOf({ next_cursor: "" }), null);
  assert.equal(nextCursorOf({ next_cursor: 42 }), null);
  assert.equal(nextCursorOf(null), null);
});

test("a rejected upload and an unavailable service are different kinds", () => {
  const rejected = describeMaterialError({ response: { status: 422, data: { code: "OPENMAIC_DOCUMENT_REJECTED" } } });
  assert.equal(rejected.kind, "rejected");
  assert.equal(rejected.retryable, false);

  const unavailable = describeMaterialError({ response: { status: 503 } });
  assert.equal(unavailable.kind, "unavailable");
  assert.equal(unavailable.retryable, true);

  assert.equal(describeMaterialError({ response: { status: 409 } }).kind, "conflict");
  assert.equal(describeMaterialError({ response: { status: 404 } }).kind, "notFound");
  assert.equal(describeMaterialError({ response: { status: 400 } }).kind, "invalid");
  assert.equal(describeMaterialError({}).kind, "unknown");
});

// ===== 协议头 =====

test("uploading sends a multipart form with the idempotency key", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onPost("/courses/c1/materials", { id: "mt_1", filename: "讲义.md", revision: 1 }, 201);

  const file = new File(["# 第一章"], "讲义.md", { type: "text/markdown" });
  await apiModule.uploadOpenMAICMaterial("c1", { file, idempotencyKey: "key-1" });

  const request = mock.lastRequest();
  assert.equal(request.url, "/courses/c1/materials");
  assert.equal(request.headers["Idempotency-Key"], "key-1");
  assert.equal(request.headers["Content-Type"], "multipart/form-data");
  assert.ok(request.data instanceof FormData);
  assert.equal(request.data.get("file").name, "讲义.md");
});

test("deleting sends the revision back as If-Match", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onSequence("delete", "/courses/c1/materials/mt_1", [{ status: 200, data: { deleted: true } }]);

  await apiModule.deleteOpenMAICMaterial("c1", "mt_1", { revision: 4 });
  assert.equal(mock.lastRequest().headers["If-Match"], "4");
});

test("resolving posts the ids it was given and nothing else", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onPost("/courses/c1/materials/resolve", { resolved: [], unresolved: [] });

  await apiModule.resolveOpenMAICMaterials("c1", { materialIds: ["mt_1", "mt_2"] });
  assert.deepEqual(mock.lastRequest().data, { material_ids: ["mt_1", "mt_2"] });
});

test("listing and reading a material stay on GET", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onGet("/courses/c1/materials", { items: [], next_cursor: null });
  mock.onGet("/courses/c1/materials/mt_1", { id: "mt_1", extraction_status: "extracted", text: "x" });

  await apiModule.listOpenMAICMaterials("c1", { limit: 5 });
  assert.equal(mock.lastRequest().params.limit, 5);
  await apiModule.getOpenMAICMaterial("c1", "mt_1");
  assert.equal(mock.lastRequest().method, "get");
});

// ===== 入口开关与源码契约 =====

test("the material entry point opens only when the service reports the capability", () => {
  const off = describeFusionState({ state: "ready", capabilities: ["workspace", "folder"] });
  assert.equal(off.canManageMaterials, false);

  const on = describeFusionState({ state: "ready", capabilities: ["material"] });
  assert.equal(on.canManageMaterials, true);

  // 未就绪时即使上报了能力也不开入口。
  const degraded = describeFusionState({ state: "degraded", capabilities: ["material"] });
  assert.equal(degraded.canManageMaterials, false);
});

test("the home only mounts the materials panel behind the capability", () => {
  assert.match(homeSource, /status\.canManageMaterials && selectedCourseId/);
  assert.match(homeSource, /<MaterialsPanel courseId=\{selectedCourseId\}/);
});

test("the panel refuses to render a body for a material it could not parse", () => {
  assert.match(panelSource, /detail\.extractionStatus === "extracted"/);
  // 没有正文可取时不发请求，直接给出原因。
  assert.match(panelSource, /material\.extractionStatus !== "extracted"/);
  assert.match(panelSource, /describeExtractionStatus\(/);
});

test("the panel reuses one idempotency key across a retry and drops it only when the file itself was rejected", () => {
  assert.match(panelSource, /pendingKey\.current = pendingKey\.current \|\| api\.newIdempotencyKey\(\)/);
  assert.match(panelSource, /if \(!described\.retryable\) pendingKey\.current = null/);
});
