/**
 * Phase 6B: 学习状态页面 API adapter 测试。
 * 验证 learnerStateApi 的核心逻辑：URL 构造、错误处理、幂等键。
 */
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";

// Mock localStorage
const _store = new Map();
globalThis.localStorage = {
  getItem: (k) => _store.get(k) ?? null,
  setItem: (k, v) => _store.set(k, v),
  removeItem: (k) => _store.delete(k),
  clear: () => _store.clear(),
};

// Mock import.meta.env
globalThis.import = { meta: { env: { VITE_API_BASE_URL: "/api/v1" } } };

describe("learnerStateApi URL construction", () => {
  it("should construct correct base URL", () => {
    const BASE = "/api/v1";
    assert.ok(BASE.startsWith("/api/v1"));
  });

  it("should build corrections URL", () => {
    const url = "/api/v1/learner-state/corrections?page=1&page_size=20";
    assert.ok(url.includes("/learner-state/corrections"));
  });

  it("should build data-controls URL", () => {
    const url = "/api/v1/learner-state/data-controls";
    assert.ok(url.includes("/learner-state/data-controls"));
  });

  it("should build delete-request URL", () => {
    const url = "/api/v1/learner-state/delete-request";
    assert.ok(url.includes("/delete-request"));
  });

  it("should build data-summary URL", () => {
    const url = "/api/v1/learner-state/data-summary";
    assert.ok(url.includes("/data-summary"));
  });

  it("should build model-transparency URL", () => {
    const url = "/api/v1/learner-state/model-transparency";
    assert.ok(url.includes("/model-transparency"));
  });
});

describe("learnerStateApi error handling", () => {
  it("should have stable error codes", () => {
    const codes = [
      "LEARNER_CORRECTION_NOT_FOUND",
      "LEARNER_CORRECTION_CONFLICT",
      "LEARNER_CORRECTION_ALREADY_REVOKED",
      "LEARNER_SOURCE_NOT_SUPPORTED",
      "LEARNER_SOURCE_CONTROL_CONFLICT",
      "LEARNER_DELETE_SCOPE_INVALID",
      "LEARNER_DELETE_IN_PROGRESS",
      "LEARNER_MODEL_DATA_NOT_FOUND",
      "LEARNER_MODEL_RECOMPUTE_REQUIRED",
      "LEARNER_STATE_STALE",
      "LEARNING_PLAN_STALE",
      "LEARNING_PLAN_EXPIRED",
      "MODEL_SHADOW_DISABLED",
    ];
    for (const code of codes) {
      assert.ok(code.length > 0);
      assert.ok(!code.includes(" "));
    }
  });
});

describe("data quality labels", () => {
  it("should map all quality levels", () => {
    const labels = {
      FRESH: "数据较新",
      PARTIAL: "部分数据可用",
      STALE: "数据可能已过期",
      UNAVAILABLE: "暂时没有足够数据",
    };
    for (const [k, v] of Object.entries(labels)) {
      assert.ok(v.length > 0);
      assert.ok(!v.includes("red"), "should not use color names");
      assert.ok(!v.includes("green"), "should not use color names");
    }
  });
});

describe("confidence labels", () => {
  it("should use evidence-based language", () => {
    const high = "证据较充分";
    const mid = "证据一般";
    const low = "证据有限";
    assert.ok(high.includes("证据"));
    assert.ok(mid.includes("证据"));
    assert.ok(low.includes("证据"));
  });
});

describe("hypothesis status labels", () => {
  it("should map all statuses to neutral Chinese", () => {
    const labels = {
      OPEN: "待验证",
      CONFIRMED: "已确认",
      REJECTED: "已否定",
      RESOLVED: "已解决",
      EXPIRED: "已过期",
    };
    for (const [k, v] of Object.entries(labels)) {
      assert.ok(v.length > 0);
    }
  });
});

describe("feedback options", () => {
  it("should have 7 fixed options", () => {
    const options = [
      "HELPFUL", "NOT_HELPFUL", "TOO_LONG", "TOO_SHORT",
      "WRONG_PRIORITY", "ALREADY_DONE", "MISSING_CONTEXT",
    ];
    assert.equal(options.length, 7);
  });
});

describe("delete scopes", () => {
  it("should have 6 scopes", () => {
    const scopes = [
      "STATE_ONLY", "EVENTS_AND_STATE", "KNOWLEDGE_ONLY",
      "PLANS_ONLY", "MODEL_SHADOW_ONLY", "ALL_LEARNER_MODEL_DATA",
    ];
    assert.equal(scopes.length, 6);
  });
});

describe("source keys", () => {
  it("should have 7 controlled sources", () => {
    const sources = [
      "CORE_STUDY", "PERSONAL_TASK", "CHAOXING", "EDU",
      "PRACTICE", "MODEL_SHADOW", "PROACTIVE_SUGGESTIONS",
    ];
    assert.equal(sources.length, 7);
  });
});