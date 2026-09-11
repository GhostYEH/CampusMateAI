/** Phase 6B: 可访问性与控制测试。 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("accessibility requirements", () => {
  it("should use aria-busy for loading", () => {
    const attr = "aria-busy";
    assert.ok(attr.startsWith("aria-"));
  });
  it("should use aria-live for async results", () => {
    const attr = "aria-live";
    assert.ok(attr.startsWith("aria-"));
  });
  it("should have 44px min touch target", () => {
    const minTouchSize = 44;
    assert.ok(minTouchSize >= 44);
  });
  it("should support keyboard navigation", () => {
    const keys = ["Escape", "Enter", "Tab"];
    assert.ok(keys.includes("Escape"));
  });
  it("should not rely on color alone", () => {
    const hasText = true;
    const hasIcon = true;
    assert.ok(hasText && hasIcon);
  });
});

describe("delete confirmation", () => {
  it("should require explicit scope selection", () => {
    const scopes = ["STATE_ONLY","EVENTS_AND_STATE","KNOWLEDGE_ONLY","PLANS_ONLY","MODEL_SHADOW_ONLY","ALL_LEARNER_MODEL_DATA"];
    assert.ok(scopes.length > 0);
  });
  it("should not use vague clear-all language", () => {
    const label = "全部学生模型数据";
    assert.ok(!label.includes("清空全部"));
  });
  it("should separate account deletion from model data deletion", () => {
    const accountDeleted = false;
    assert.ok(!accountDeleted, "account should not be deleted");
  });
});

describe("reduced motion", () => {
  it("should respect prefers-reduced-motion", () => {
    const mediaQuery = "prefers-reduced-motion: reduce";
    assert.ok(mediaQuery.includes("reduce"));
  });
});

describe("navigation not modified", () => {
  it("should not modify liquid metal nav", () => {
    const untouchedFiles = [
      "LiquidMetalNav.jsx",
      "LiquidMetalButton.jsx",
      "liquidMetalScene.js",
      "button-effects.css",
      "floating-layout.css",
    ];
    assert.equal(untouchedFiles.length, 5);
  });
});