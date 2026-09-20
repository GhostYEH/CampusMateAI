/**
 * 学习工作台的 Web 侧契约测试。
 *
 * 两件事在界面上最容易表现为"点了没反应"，所以单独钉住：
 * 写请求必须带协议要求的头（Idempotency-Key / If-Match），以及 409 必须被翻译成
 * "重新读取后重试"而不是原样重试。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// 必须先于 api.js 加载，给 localStorage / location 提供确定性实现。
import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import {
  describeWorkspaceError,
  nextCursorOf,
  normalizeStageList,
  normalizeWorkspaceList,
  normalizeWorkspaceName,
} from "../src/features/openmaic/workspaceModel.js";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");
const homeSource = read("src/components/openmaic/OpenMAICHome.jsx");
const panelSource = read("src/components/openmaic/WorkspacePanel.jsx");

// ===== 视图模型 =====

test("workspace list normalisation keeps the server revision as the credential", () => {
  const items = normalizeWorkspaceList({
    items: [
      { id: "ws_1", course_id: "c1", name: "期末复习", description: "d", revision: 3, created_at: "a", updated_at: "b" },
      { id: "", name: "丢弃" },
      null,
    ],
  });
  assert.equal(items.length, 1);
  assert.equal(items[0].revision, 3);
  assert.equal(items[0].courseId, "c1");
  assert.equal(items[0].updatedAt, "b");
});

test("workspace list normalisation tolerates a missing payload", () => {
  assert.deepEqual(normalizeWorkspaceList(null), []);
  assert.deepEqual(normalizeWorkspaceList({}), []);
  assert.deepEqual(normalizeStageList(undefined), []);
});

test("stage list normalisation never invents a document", () => {
  const items = normalizeStageList({
    items: [{ id: "stg_1", workspace_id: "ws_1", course_id: "c1", title: "第一节", revision: 2, dsl_version: "0.3.0" }],
  });
  assert.equal(items[0].dslVersion, "0.3.0");
  assert.equal(items[0].document, undefined);
});

test("the cursor is passed back verbatim and never parsed", () => {
  assert.equal(nextCursorOf({ next_cursor: "abc" }), "abc");
  assert.equal(nextCursorOf({ next_cursor: "" }), null);
  assert.equal(nextCursorOf({ next_cursor: 42 }), null);
  assert.equal(nextCursorOf(null), null);
});

test("a workspace name is trimmed and bounded before it is submitted", () => {
  assert.equal(normalizeWorkspaceName("  期末复习 "), "期末复习");
  assert.equal(normalizeWorkspaceName(""), null);
  assert.equal(normalizeWorkspaceName("   "), null);
  assert.equal(normalizeWorkspaceName(null), null);
  assert.equal(normalizeWorkspaceName("x".repeat(121)), null);
  assert.equal(normalizeWorkspaceName("x".repeat(120)), "x".repeat(120));
});

// ===== 错误翻译 =====

test("a revision conflict is not retryable as-is", () => {
  const described = describeWorkspaceError({
    response: { status: 409, data: { code: "OPENMAIC_REVISION_CONFLICT" } },
  });
  assert.equal(described.kind, "conflict");
  assert.equal(described.retryable, false, "原样重试会一直 409");
});

test("the fusion switch being off is reported as unavailable, not as empty", () => {
  const described = describeWorkspaceError({
    response: { status: 503, data: { code: "OPENMAIC_FUSION_UNAVAILABLE" } },
  });
  assert.equal(described.kind, "unavailable");
  assert.equal(described.retryable, true);
});

test("a rejected document surfaces the first validation issue", () => {
  const described = describeWorkspaceError({
    response: {
      status: 422,
      data: {
        code: "OPENMAIC_DOCUMENT_REJECTED",
        details: { issues: [{ code: "scene_type_invalid", path: "scenes[0].type", message: "场景类型无效" }] },
      },
    },
  });
  assert.equal(described.kind, "rejected");
  assert.match(described.message, /场景类型无效/);
});

test("idempotency, not-found, invalid and unknown errors each get their own kind", () => {
  const kinds = [
    [{ response: { status: 409, data: { code: "OPENMAIC_IDEMPOTENCY_CONFLICT" } } }, "idempotency"],
    [{ response: { status: 404, data: { code: "OPENMAIC_WORKSPACE_NOT_FOUND" } } }, "notFound"],
    [{ response: { status: 400, data: { code: "OPENMAIC_INVALID_REQUEST" } } }, "invalid"],
    [{ response: { status: 500, data: {} } }, "unknown"],
    [{}, "unknown"],
  ];
  for (const [error, expected] of kinds) {
    assert.equal(describeWorkspaceError(error).kind, expected);
  }
});

// ===== 协议头 =====

test("creating a workspace sends the idempotency key the protocol requires", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onPost("/courses/c1/workspaces", { id: "ws_1", name: "期末复习", revision: 1 }, 201);

  await apiModule.createOpenMAICWorkspace("c1", { name: "期末复习", idempotencyKey: "key-1" });

  const request = mock.lastRequest();
  assert.equal(request.url, "/courses/c1/workspaces");
  assert.equal(request.headers["Idempotency-Key"], "key-1");
  assert.deepEqual(request.data, { name: "期末复习", description: "" });
});

test("updating and deleting send the revision back as If-Match", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onPatch("/courses/c1/workspaces/ws_1", { id: "ws_1", revision: 2 });
  // 共享的 mock 适配器没有 onDelete，用单步序列表达同一个意思。
  mock.onSequence("delete", "/courses/c1/workspaces/ws_1", [{ status: 200, data: { deleted: true } }]);

  await apiModule.updateOpenMAICWorkspace("c1", "ws_1", { revision: 1, name: "新名字" });
  assert.equal(mock.lastRequest().headers["If-Match"], "1");
  assert.deepEqual(mock.lastRequest().data, { name: "新名字" });

  await apiModule.deleteOpenMAICWorkspace("c1", "ws_1", { revision: 2 });
  assert.equal(mock.lastRequest().headers["If-Match"], "2");
});

test("replacing a stage sends both the document and the revision", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  const document = { dslVersion: "0.3.0", stage: { id: "s" }, scenes: [] };
  mock.onPut("/courses/c1/workspaces/ws_1/stages/stg_1", { id: "stg_1", revision: 2, document });

  await apiModule.replaceOpenMAICStage("c1", "ws_1", "stg_1", { revision: 1, document });

  const request = mock.lastRequest();
  assert.equal(request.headers["If-Match"], "1");
  assert.deepEqual(request.data, { document });
});

test("an omitted document is not sent as null", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onPost("/courses/c1/workspaces/ws_1/stages", { id: "stg_1", revision: 1 }, 201);

  await apiModule.createOpenMAICStage("c1", "ws_1", { title: "第一节", idempotencyKey: "k" });

  assert.deepEqual(mock.lastRequest().data, { title: "第一节" });
});

test("an idempotency key is generated and stays stable for a retry of the same action", () => {
  const first = apiModule.newIdempotencyKey();
  const second = apiModule.newIdempotencyKey();
  assert.equal(typeof first, "string");
  assert.ok(first.length >= 8);
  assert.notEqual(first, second, "不同动作应拿到不同的键");
});

test("listing workspaces passes pagination through as query parameters", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onGet("/courses/c1/workspaces", { items: [], next_cursor: null });

  await apiModule.listOpenMAICWorkspaces("c1", { limit: 5, cursor: "abc" });

  assert.deepEqual(mock.lastRequest().params, { limit: 5, cursor: "abc" });
});

// ===== 接线 =====

test("the workbench panel is gated on the real capability and the chosen course", () => {
  assert.match(homeSource, /selectedCourseId/);
  assert.match(homeSource, /api\.generateOpenMAICHome/);
  assert.doesNotMatch(homeSource, /<WorkspacePanel/);
});

test("the workbench panel offers no dead controls", () => {
  assert.match(panelSource, /disabled={!canSubmit}/);
  assert.match(panelSource, /normalizeWorkspaceName\(name\)/);
  assert.match(panelSource, /revision: item\.revision/);
  assert.doesNotMatch(panelSource, /正在接入/);
  assert.doesNotMatch(panelSource, /TODO/);
  assert.doesNotMatch(panelSource, /onClick=\{\(\) => \{\}\}/);
});

test("a conflict triggers a reload instead of a blind retry", () => {
  assert.match(panelSource, /described\.kind === "conflict"/);
  assert.match(panelSource, /await load\(\)/);
});
