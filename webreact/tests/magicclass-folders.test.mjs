/**
 * 文件夹的 Web 侧契约测试。
 *
 * 界面在这里最容易犯的错不是"显示不对"，而是"写入协议不对"：创建漏了
 * Idempotency-Key 会让一次重试变成两个文件夹，重命名漏了 If-Match 会静默覆盖
 * 别人的修改。另外，删除文件夹是"把内容移到未归档"，行数必须跟着变。
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
  buildFolderTree,
  describeDiscoveryError,
  normalizeFolderList,
  normalizeFolderName,
  normalizeSearchResults,
} from "../src/features/magicclass/discoveryModel.js";
import { normalizeWorkspaceList } from "../src/features/magicclass/workspaceModel.js";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");
const panelSource = read("src/components/magicclass/DiscoveryPanel.jsx");
const homeSource = read("src/components/magicclass/magicclassHome.jsx");
const apiSource = read("src/data/api.js");

// ===== 视图模型 =====

test("folder list normalisation keeps the server revision and drops unusable rows", () => {
  const items = normalizeFolderList({
    items: [
      { id: "fd_1", course_id: "c1", parent_id: null, name: "第一章", revision: 3, workspace_count: 2, updated_at: "t" },
      { id: "", name: "丢弃" },
      null,
    ],
  });
  assert.equal(items.length, 1);
  assert.equal(items[0].revision, 3);
  assert.equal(items[0].workspaceCount, 2);
  assert.equal(items[0].parentId, null);
  assert.equal(items[0].courseId, "c1");
});

test("folder list normalisation tolerates a missing payload", () => {
  assert.deepEqual(normalizeFolderList(undefined), []);
  assert.deepEqual(normalizeFolderList({}), []);
});

test("a folder tree nests children under their parent", () => {
  const tree = buildFolderTree([
    { id: "fd_1", name: "第一章", parentId: null, revision: 1, workspaceCount: 0 },
    { id: "fd_2", name: "第一节", parentId: "fd_1", revision: 1, workspaceCount: 0 },
    { id: "fd_3", name: "第二章", parentId: null, revision: 1, workspaceCount: 0 },
  ]);
  assert.deepEqual(tree.roots.map((folder) => folder.id), ["fd_3", "fd_1"]);
  assert.deepEqual(tree.childrenOf("fd_1").map((folder) => folder.id), ["fd_2"]);
  assert.deepEqual(tree.childrenOf("fd_3"), []);
});

test("an orphaned or self-parenting folder surfaces at the root instead of vanishing", () => {
  const tree = buildFolderTree([
    { id: "fd_orphan", name: "孤儿", parentId: "fd_missing", revision: 1, workspaceCount: 0 },
    { id: "fd_self", name: "自环", parentId: "fd_self", revision: 1, workspaceCount: 0 },
  ]);
  assert.deepEqual(tree.roots.map((folder) => folder.id).sort(), ["fd_orphan", "fd_self"]);
});

test("a folder name is trimmed and bounded before it is submitted", () => {
  assert.equal(normalizeFolderName("  第一章 "), "第一章");
  assert.equal(normalizeFolderName(""), null);
  assert.equal(normalizeFolderName("   "), null);
  assert.equal(normalizeFolderName(null), null);
  assert.equal(normalizeFolderName("x".repeat(121)), null);
  assert.equal(normalizeFolderName("x".repeat(120)), "x".repeat(120));
});

// ===== 写入协议 =====

test("creating a folder sends the idempotency key and only sends parent_id when set", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onPost("/courses/c1/folders", { id: "fd_1" }, 201);

  await apiModule.createMagicClassFolder("c1", { name: "第一章", idempotencyKey: "key-1" });
  const rootCall = mock.requests.at(-1);
  assert.equal(rootCall.headers["Idempotency-Key"], "key-1");
  assert.equal(rootCall.data.parent_id, undefined, "根层文件夹不应带 parent_id");

  await apiModule.createMagicClassFolder("c1", { name: "第一节", parentId: "fd_1", idempotencyKey: "key-2" });
  assert.equal(mock.requests.at(-1).data.parent_id, "fd_1");
});

test("renaming a folder carries If-Match and keeps an explicit null parent", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onPatch("/courses/c1/folders/fd_1", { id: "fd_1", revision: 2 });

  await apiModule.updateMagicClassFolder("c1", "fd_1", { revision: 1, name: "新名字" });
  const renamed = mock.requests.at(-1);
  assert.equal(renamed.headers["If-Match"], "1");
  assert.equal("parent_id" in renamed.data, false, "只改名时不得隐式移动层级");

  await apiModule.updateMagicClassFolder("c1", "fd_1", { revision: 2, parentId: null });
  const moved = mock.requests.at(-1);
  assert.equal(moved.data.parent_id, null, "显式 null 表示移动到根层");
});

test("deleting a folder carries If-Match", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onDelete("/courses/c1/folders/fd_1", { deleted: true });
  await apiModule.deleteMagicClassFolder("c1", "fd_1", { revision: 4 });
  assert.equal(mock.requests.at(-1).headers["If-Match"], "4");
});

test("a workspace can be filed and unfiled through the same update call", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onPatch("/courses/c1/workspaces/ws_1", { id: "ws_1", revision: 2 });

  await apiModule.updateMagicClassWorkspace("c1", "ws_1", { revision: 1, folderId: "fd_1" });
  assert.equal(mock.requests.at(-1).data.folder_id, "fd_1");

  await apiModule.updateMagicClassWorkspace("c1", "ws_1", { revision: 2, folderId: null });
  assert.equal(mock.requests.at(-1).data.folder_id, null, "取消归档必须显式传 null");

  await apiModule.updateMagicClassWorkspace("c1", "ws_1", { revision: 3, name: "只改名" });
  assert.equal("folder_id" in mock.requests.at(-1).data, false);
});

// ===== 错误翻译 =====

test("discovery errors are translated into actionable kinds", () => {
  const cases = [
    [{ response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE" } } }, "unavailable", true],
    [{ response: { status: 409, data: { code: "MAGICCLASS_REVISION_CONFLICT" } } }, "conflict", false],
    [{ response: { status: 404, data: { code: "MAGICCLASS_WORKSPACE_NOT_FOUND" } } }, "notFound", false],
    [{ response: { status: 400, data: { code: "MAGICCLASS_INVALID_REQUEST" } } }, "invalid", false],
    [{ response: { status: 409, data: { code: "MAGICCLASS_IDEMPOTENCY_CONFLICT" } } }, "idempotency", false],
  ];
  cases.forEach(([error, kind, retryable]) => {
    const described = describeDiscoveryError(error);
    assert.equal(described.kind, kind);
    assert.equal(described.retryable, retryable);
    assert.ok(described.message.length > 0);
  });
});

test("an unknown failure is retryable and never leaks the raw error text", () => {
  const described = describeDiscoveryError({ response: { status: 500, data: { message: "internal http://magicclass.internal:4010" } } });
  assert.equal(described.kind, "unknown");
  assert.equal(described.retryable, true);
});

// ===== 组合契约（源码级） =====

test("the reference composer keeps discovery tools explicitly unavailable", () => {
  assert.match(homeSource, /magicclass-reference-tools/);
  assert.match(homeSource, /title="联网搜索能力尚未接通"/);
  assert.match(panelSource, /if \(!canBrowseFolders && !canSearch\) return null;/);
});

test("the browser never talks to the managed service directly", () => {
  for (const source of [panelSource, apiSource]) {
    assert.doesNotMatch(source, /magicclass\.internal/);
    assert.doesNotMatch(source, /MAGICCLASS_INTERNAL_SECRET|magicclass_service_url/i);
  }
  // 发现功能只经 CampusMate 的相对路径 API。
  assert.match(apiSource, /client\.get\(`\/courses\/\$\{courseId\}\/folders`/);
  assert.match(apiSource, /client\.get\(`\/courses\/\$\{courseId\}\/search`/);
});

test("a folder delete that conflicts triggers a re-read instead of a blind retry", () => {
  assert.match(panelSource, /described\.kind === "conflict"/);
  assert.match(panelSource, /await load\(\)/);
});

test("a retryable folder-create failure keeps the same idempotency key", () => {
  assert.match(panelSource, /if \(!described\.retryable\) pendingKey\.current = null;/);
});

// ===== 搜索模型的最小面 =====

test("the folder module does not invent its own search shape", () => {
  const hits = normalizeSearchResults({ items: [{ kind: "stage", workspace_id: "ws_1", stage_id: "stg_1", title: "t", path: "/p" }] });
  assert.equal(hits.length, 1);
  assert.equal(hits[0].href, "/p");
});

// ===== 归档（文件夹 ↔ 工作台映射） =====

test("a workspace keeps the folder it was filed into", () => {
  const items = normalizeWorkspaceList({
    items: [{ id: "ws_1", course_id: "c1", name: "线性代数复习", folder_id: "fd_1", revision: 2 }],
  });
  assert.equal(items[0].folderId, "fd_1");

  const unfiled = normalizeWorkspaceList({ items: [{ id: "ws_2", course_id: "c1", name: "未归档", revision: 1 }] });
  assert.equal(unfiled[0].folderId, null, "没有归档字段读回为未归档");
});

test("the filing controls only exist when the folder capability was reported", () => {
  const panelSource = read("src/components/magicclass/WorkspacePanel.jsx");
  assert.match(panelSource, /canFile = false/);
  assert.match(panelSource, /\{canFile \? <select/);
  assert.match(panelSource, /\{canFile \? <select[\s\S]*?aria-label={`把「\$\{item\.name\}」移动到文件夹`}/);
  // 归档写入必须用列表里服务端给的 revision，而不是本地推算的值。
  assert.match(panelSource, /api\.updateMagicClassWorkspace\(courseId, item\.id, \{\s*revision: item\.revision,/);
  // 取消归档必须显式传 null。
  assert.match(panelSource, /folderId: folderId \|\| null,/);
});

test("the home only offers filing when the server reported the folder capability", () => {
  const homeSource = read("src/components/magicclass/magicclassHome.jsx");
  assert.doesNotMatch(homeSource, /canFile=\{/);
  assert.match(homeSource, /magicclass-home--reference/);
});
