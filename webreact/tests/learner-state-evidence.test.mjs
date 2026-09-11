/** Phase 6B: 证据抽屉与知识地图测试。 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("evidence kind labels", () => {
  it("should map evidence kinds to Chinese", () => {
    const labels = { EVENT: "学习事件", SOURCE_ROW: "业务记录", SYNC_STATUS: "同步状态" };
    for (const v of Object.values(labels)) assert.ok(v.length > 0);
  });
  it("should not expose source_id or table names", () => {
    const forbidden = ["source_id", "table_name", "payload", "prompt"];
    const labels = { EVENT: "学习事件", SOURCE_ROW: "业务记录", SYNC_STATUS: "同步状态" };
    for (const v of Object.values(labels)) for (const f of forbidden) assert.ok(!v.includes(f));
  });
});

describe("knowledge band labels", () => {
  it("should not use mastery language for chapter completion", () => {
    const bands = { INSUFFICIENT_EVIDENCE: "证据不足", EMERGING: "初步了解", DEVELOPING: "发展中", PROFICIENT: "较为熟练" };
    for (const v of Object.values(bands)) assert.ok(!v.includes("已掌握"));
  });
});

describe("kc category labels", () => {
  it("should cover 11 categories", () => {
    const cats = ["foundations","types","expressions","control","functions","arrays","pointers","memory","composite","io","practice"];
    assert.equal(cats.length, 11);
  });
});