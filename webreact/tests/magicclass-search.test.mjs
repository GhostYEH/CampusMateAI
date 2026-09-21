/**
 * 站内搜索的 Web 侧契约测试。
 *
 * 搜索在界面上有两个"看起来能用其实不对"的失败模式，这里都钉住：
 * 空关键词被当成"搜索全部"，以及前端自己拼深链（服务端改口径后会静默走错）。
 * 另外结果里的 stage 与它的父工作台会同时命中，列表 key 必须能区分。
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
  MAX_SEARCH_QUERY_LENGTH,
  describeDiscoveryError,
  isSearchableQuery,
  nextCursorOf,
  normalizeSearchResults,
  searchHitKey,
} from "../src/features/magicclass/discoveryModel.js";

const read = (rel) => readFileSync(fileURLToPath(new URL(`../${rel}`, import.meta.url)), "utf8");
const panelSource = read("src/components/magicclass/DiscoveryPanel.jsx");

// ===== 输入约束 =====

test("a blank query is not a search for everything", () => {
  assert.equal(isSearchableQuery(""), false);
  assert.equal(isSearchableQuery("   "), false);
  assert.equal(isSearchableQuery(null), false);
  assert.equal(isSearchableQuery(undefined), false);
});

test("a query is trimmed, and the service's 200 character bound is the one enforced", () => {
  assert.equal(isSearchableQuery("  线性代数  "), true);
  assert.equal(isSearchableQuery("x".repeat(MAX_SEARCH_QUERY_LENGTH)), true);
  assert.equal(isSearchableQuery("x".repeat(MAX_SEARCH_QUERY_LENGTH + 1)), false);
  assert.equal(MAX_SEARCH_QUERY_LENGTH, 200);
});

// ===== 结果模型 =====

test("search hits keep the server path and drop rows that cannot be opened", () => {
  const hits = normalizeSearchResults({
    items: [
      { kind: "stage", workspace_id: "ws_1", stage_id: "stg_1", title: "线性代数第一讲", path: "/courses/c1?tab=mentoring&workspace=ws_1&stage=stg_1" },
      { kind: "workspace", workspace_id: "ws_1", title: "线性代数复习", path: "/courses/c1?tab=mentoring&workspace=ws_1" },
      { kind: "stage", title: "没有工作台" },
      { kind: "unknown", workspace_id: "ws_2" },
      null,
    ],
  });
  assert.equal(hits.length, 2);
  assert.equal(hits[0].href, "/courses/c1?tab=mentoring&workspace=ws_1&stage=stg_1");
  assert.equal(hits[1].stageId, null);
});

test("a hit without a server path is rendered without an invented link", () => {
  const hits = normalizeSearchResults({ items: [{ kind: "workspace", workspace_id: "ws_1", title: "无深链" }] });
  assert.equal(hits[0].href, null, "前端不得自己拼站内路径");
});

test("a workspace and its stage never collide as list keys", () => {
  const workspace = { kind: "workspace", workspaceId: "ws_1", stageId: null };
  const stage = { kind: "stage", workspaceId: "ws_1", stageId: "stg_1" };
  assert.notEqual(searchHitKey(workspace), searchHitKey(stage));
});

test("search normalisation tolerates a missing payload", () => {
  assert.deepEqual(normalizeSearchResults(undefined), []);
  assert.deepEqual(normalizeSearchResults({}), []);
});

// ===== 请求协议 =====

test("search sends the trimmed query and omits an absent cursor", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onGet("/courses/c1/search", { items: [], next_cursor: null });

  await apiModule.searchMagicClassContent("c1", { query: "线性代数", limit: 20 });
  const call = mock.requests.at(-1);
  assert.equal(call.params.q, "线性代数");
  assert.equal(call.params.limit, 20);
  assert.equal("cursor" in call.params, false, "没有游标时不得带一个空值");
});

test("search carries the cursor back verbatim when paging", async () => {
  const mock = createMockClient(apiModule.default);
  mock.onGet("/courses/c1/search", { items: [], next_cursor: null });
  await apiModule.searchMagicClassContent("c1", { query: "复习", limit: 20, cursor: "abc" });
  assert.equal(mock.requests.at(-1).params.cursor, "abc");
});

test("the cursor is only echoed back, never parsed", () => {
  assert.equal(nextCursorOf({ next_cursor: "abc" }), "abc");
  assert.equal(nextCursorOf({ next_cursor: "" }), null);
  assert.equal(nextCursorOf({ next_cursor: 7 }), null);
  assert.equal(nextCursorOf(null), null);
});

// ===== 失败语义 =====

test("a search that cannot reach the service is retryable; a bad query is not", () => {
  const unavailable = describeDiscoveryError({ response: { status: 503, data: { code: "MAGICCLASS_FUSION_UNAVAILABLE" } } });
  assert.equal(unavailable.kind, "unavailable");
  assert.equal(unavailable.retryable, true);

  const invalid = describeDiscoveryError({ response: { status: 400, data: { code: "MAGICCLASS_INVALID_REQUEST", message: "搜索关键词不能为空" } } });
  assert.equal(invalid.kind, "invalid");
  assert.equal(invalid.retryable, false);
  assert.match(invalid.message, /不能为空/);
});

// ===== 组合契约（源码级） =====

test("the panel refuses to search on a blank query instead of asking the server", () => {
  assert.match(panelSource, /if \(!isSearchableQuery\(query\) \|\| searching\)/);
  assert.match(panelSource, /请输入 1–200 个字符的关键词/);
});

test("an empty result set says so, and only after a search actually ran", () => {
  assert.match(panelSource, /searchedFor && !hits\.length && !searchError/);
  assert.match(panelSource, /没有找到与「\{searchedFor\}」匹配的内容/);
});

test("a hit without a path is rendered as text, not as a dead link", () => {
  assert.match(panelSource, /hit\.href \? <Link/);
  assert.match(panelSource, /该条目暂时没有可用的站内位置/);
});
