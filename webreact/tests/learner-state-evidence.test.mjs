/**
 * Phase 6B: 证据抽屉、知识地图与状态纠正 API 契约测试。
 * 导入真实 learnerStateApi.js，验证证据获取、知识状态、纠正提交与撤销的真实请求。
 */
import "./helpers/setup-globals.mjs";
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";

import * as api from "../src/data/learnerStateApi.js";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

let mock;

beforeEach(() => {
  mock = createMockClient(client);
});

afterEach(() => {
  mock.reset();
  mock.clearTokens();
});

// ===== 证据获取 =====

describe("getSnapshotEvidence", () => {
  it("返回证据列表，包含 evidence_kind / source_category / role", async () => {
    const evidence = {
      items: [
        {
          evidence_id: "ev-1",
          evidence_kind: "EVENT",
          source_category: "CORE_STUDY",
          event_type: "study_session_completed",
          occurred_at: "2026-09-01T10:00:00Z",
          role: "SUPPORTS",
        },
        {
          evidence_id: "ev-2",
          evidence_kind: "SOURCE_ROW",
          source_category: "CHAOXING",
          event_type: null,
          occurred_at: "2026-09-02T14:00:00Z",
          role: "INVALIDATES",
        },
      ],
      total: 2,
      has_more: false,
    };
    mock.onGet("/learner-state/snapshots/snap-1/evidence", evidence);

    const result = await api.getSnapshotEvidence("snap-1", 1, 20);
    assert.equal(result.items.length, 2);
    assert.equal(result.items[0].evidence_kind, "EVENT");
    assert.equal(result.items[0].source_category, "CORE_STUDY");
    assert.equal(result.items[0].role, "SUPPORTS");
    assert.equal(result.items[1].evidence_kind, "SOURCE_ROW");
    assert.equal(result.items[1].role, "INVALIDATES");
  });

  it("分页参数正确传递", async () => {
    mock.onGet("/learner-state/snapshots/snap-1/evidence", { items: [], total: 0 });
    await api.getSnapshotEvidence("snap-1", 3, 40);
    const req = mock.lastRequest();
    assert.equal(req.params.page, 3);
    assert.equal(req.params.page_size, 40);
  });

  it("has_more=true 时可加载下一页", async () => {
    mock.onGet("/learner-state/snapshots/snap-1/evidence", {
      items: [{ evidence_id: "ev-1", evidence_kind: "EVENT" }],
      total: 30,
      has_more: true,
    });
    const r1 = await api.getSnapshotEvidence("snap-1", 1, 20);
    assert.ok(r1.has_more);
    // 翻页
    mock.onGet("/learner-state/snapshots/snap-1/evidence", { items: [], total: 30, has_more: false });
    const r2 = await api.getSnapshotEvidence("snap-1", 2, 20);
    assert.ok(!r2.has_more);
    assert.equal(mock.findRequests("get", "evidence").length, 2);
  });
});

// ===== 知识状态 =====

describe("getKnowledgeState", () => {
  it("返回知识点列表，包含 kc_code / kc_name / category / band / evidence_count", async () => {
    const knowledge = {
      items: [
        {
          kc_code: "c_pointer_basics",
          kc_name: "指针基础",
          category: "pointers",
          band: "DEVELOPING",
          evidence_count: 5,
          data_quality: "FRESH",
          valid_until: "2026-09-30T00:00:00Z",
        },
        {
          kc_code: "c_array_boundary",
          kc_name: "数组边界",
          category: "arrays",
          band: "INSUFFICIENT_EVIDENCE",
          evidence_count: 0,
          data_quality: "UNAVAILABLE",
          valid_until: null,
        },
      ],
      total: 2,
    };
    mock.onGet("/learner-state/knowledge", knowledge);

    const result = await api.getKnowledgeState("");
    assert.equal(result.items.length, 2);
    assert.equal(result.items[0].kc_code, "c_pointer_basics");
    assert.equal(result.items[0].band, "DEVELOPING");
    assert.equal(result.items[0].evidence_count, 5);
    assert.equal(result.items[1].band, "INSUFFICIENT_EVIDENCE");
    assert.equal(result.items[1].evidence_count, 0);
  });
});

describe("getTaxonomy", () => {
  it("返回分类结构", async () => {
    const taxonomy = {
      categories: [
        { code: "foundations", name: "基础" },
        { code: "pointers", name: "指针" },
      ],
    };
    mock.onGet("/learner-state/taxonomy", taxonomy);
    const result = await api.getTaxonomy();
    assert.equal(result.categories.length, 2);
    assert.equal(result.categories[0].code, "foundations");
  });
});

// ===== 状态纠正提交 =====

describe("createCorrection", () => {
  it("POST /learner-state/corrections 并传递完整纠正 body", async () => {
    mock.onPost("/learner-state/corrections", { correction_id: "corr-1", status: "ACTIVE" });
    const body = {
      target_snapshot_id: "snap-1",
      scope_type: "USER",
      scope_id: "user-1",
      state_type: "task_workload",
      correction_type: "MARK_INACCURATE",
      reason_code: "user_observed_inaccuracy",
      idempotency_key: "corr-snap-1-12345",
    };
    const result = await api.createCorrection(body);
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/corrections");
    assert.equal(req.data.target_snapshot_id, "snap-1");
    assert.equal(req.data.scope_type, "USER");
    assert.equal(req.data.state_type, "task_workload");
    assert.equal(req.data.correction_type, "MARK_INACCURATE");
    assert.equal(req.data.reason_code, "user_observed_inaccuracy");
    assert.equal(req.data.idempotency_key, "corr-snap-1-12345");
    assert.equal(result.correction_id, "corr-1");
    assert.equal(result.status, "ACTIVE");
  });

  it("支持多种纠正类型", async () => {
    for (const type of ["MARK_INACCURATE", "SOURCE_OUTDATED", "NOT_APPLICABLE"]) {
      mock.reset();
      mock.onPost("/learner-state/corrections", { correction_id: "c", status: "ACTIVE" });
      await api.createCorrection({
        target_snapshot_id: "s",
        scope_type: "USER",
        scope_id: "u",
        state_type: "task_workload",
        correction_type: type,
        reason_code: "user_observed_inaccuracy",
        idempotency_key: `key-${type}`,
      });
      assert.equal(mock.lastRequest().data.correction_type, type);
    }
  });
});

// ===== 纠正撤销 =====

describe("revokeCorrection", () => {
  it("POST /corrections/:id/revoke 并传递 idempotency_key", async () => {
    mock.onPost("/learner-state/corrections/corr-1/revoke", { status: "REVOKED" });
    const result = await api.revokeCorrection("corr-1", "revoke-key-123");
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/corrections/corr-1/revoke");
    assert.deepEqual(req.data, { idempotency_key: "revoke-key-123" });
    assert.equal(result.status, "REVOKED");
  });
});

// ===== 纠正列表 =====

describe("getCorrections", () => {
  it("GET /learner-state/corrections 并传递分页", async () => {
    mock.onGet("/learner-state/corrections", {
      items: [
        { correction_id: "c1", correction_type: "MARK_INACCURATE", status: "ACTIVE" },
        { correction_id: "c2", correction_type: "SOURCE_OUTDATED", status: "REVOKED" },
      ],
      total: 2,
    });
    const result = await api.getCorrections(1, 20);
    const req = mock.lastRequest();
    assert.equal(req.url, "/learner-state/corrections");
    assert.equal(req.params.page, 1);
    assert.equal(req.params.page_size, 20);
    assert.equal(result.items.length, 2);
    assert.equal(result.items[0].status, "ACTIVE");
    assert.equal(result.items[1].status, "REVOKED");
  });
});

// ===== 纠正后数据刷新 =====

describe("纠正后数据刷新", () => {
  it("提交纠正后再次获取快照列表发出新请求", async () => {
    mock.onPost("/learner-state/corrections", { correction_id: "c1", status: "ACTIVE" });
    mock.onGet("/learner-state/snapshots", { items: [], total: 0 });

    await api.getLearnerStateSnapshots({ pageSize: 50 });
    assert.equal(mock.findRequests("get", "snapshots").length, 1);

    await api.createCorrection({
      target_snapshot_id: "s1",
      scope_type: "USER",
      scope_id: "u1",
      state_type: "task_workload",
      correction_type: "MARK_INACCURATE",
      reason_code: "user_observed_inaccuracy",
      idempotency_key: "k1",
    });

    await api.getLearnerStateSnapshots({ pageSize: 50 });
    assert.equal(mock.findRequests("get", "snapshots").length, 2);
  });

  it("撤销纠正后再次获取纠正列表发出新请求", async () => {
    mock.onPost("/learner-state/corrections/c1/revoke", { status: "REVOKED" });
    mock.onGet("/learner-state/corrections", { items: [], total: 0 });

    await api.getCorrections(1, 20);
    assert.equal(mock.findRequests("get", "corrections").length, 1);

    await api.revokeCorrection("c1", "revoke-key");

    await api.getCorrections(1, 20);
    assert.equal(mock.findRequests("get", "corrections").length, 2);
  });
});

// ===== 证据不暴露内部字段 =====

describe("证据隐私", () => {
  it("证据响应不包含 source_id / table_name / payload / prompt", async () => {
    const evidence = {
      items: [{
        evidence_id: "ev-1",
        evidence_kind: "EVENT",
        source_category: "CORE_STUDY",
        event_type: "study_session_completed",
        occurred_at: "2026-09-01T10:00:00Z",
        role: "SUPPORTS",
      }],
      total: 1,
    };
    mock.onGet("/learner-state/snapshots/snap-1/evidence", evidence);
    const result = await api.getSnapshotEvidence("snap-1");
    const ev = result.items[0];
    assert.ok(!("source_id" in ev), "不暴露 source_id");
    assert.ok(!("table_name" in ev), "不暴露 table_name");
    assert.ok(!("payload" in ev), "不暴露 payload");
    assert.ok(!("prompt" in ev), "不暴露 prompt");
  });
});
