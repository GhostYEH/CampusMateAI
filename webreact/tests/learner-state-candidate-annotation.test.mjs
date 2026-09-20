/**
 * 候选模型只读注解的展示契约。
 *
 * 三条不可退让的约束，逐条锁死：
 *
 * 1. **可识别**：页面上必须标明这段文字来自候选模型，且与确定性结果分开呈现；
 * 2. **可降级**：候选不可用时只显示稳定 reason 的中文映射 + "已回退到确定性结果"，
 *    不允许前端自己猜原因，也不允许把不可用渲染成空白或"正在接入"占位；
 * 3. **只读**：页面必须明说它不会修改状态/计划/待办，且不得暗示影子结果会改计划。
 *
 * 同时确认"确认计划后进入自动观测"这件事在页面上被如实说明（而不是被暗示成
 * 生成即自动重规划）。
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const pageSource = await readFile(
  new URL("../src/pages/LearningStatePage.jsx", import.meta.url), "utf8",
);
const apiSource = await readFile(
  new URL("../src/data/learnerStateApi.js", import.meta.url), "utf8",
);
const cssSource = await readFile(
  new URL("../src/styles/learning-state.css", import.meta.url), "utf8",
);

describe("候选模型只读注解", () => {
  it("渲染后端返回的 candidate_annotation 字段", () => {
    assert.match(pageSource, /summary\.candidate_annotation/, "页面必须消费后端下发的注解字段");
    assert.match(pageSource, /aria-label="候选模型只读注解"/, "注解需要独立可识别的区域");
  });

  it("可用时标明来源与依据，且明确是只读", () => {
    assert.match(pageSource, /候选模型建议（只读）/);
    assert.match(pageSource, /annotation\.model_key/);
    assert.match(pageSource, /annotation\.prompt_version/);
    assert.match(pageSource, /annotation\.claim_codes/);
    assert.match(pageSource, /这是候选模型的只读展示，不会修改你的状态、计划或待办。/);
  });

  it("不可用时只展示稳定 reason 的中文映射并说明已回退", () => {
    assert.match(pageSource, /已回退到确定性结果：/);
    for (const reason of [
      "canary_feature_flag_disabled",
      "candidate_model_not_configured",
      "model_shadow_paused_for_user",
      "no_promotion_decision",
      "quality_gates_failed",
      "circuit_breaker_open",
      "MODEL_RATE_LIMITED",
      "MODEL_TIMEOUT",
      "MODEL_SCHEMA_INVALID",
      "MODEL_POLICY_VIOLATION",
    ]) {
      assert.ok(pageSource.includes(reason), `降级原因 ${reason} 必须有中文文案`);
    }
  });

  it("不允许出现正在接入式的空占位", () => {
    for (const placeholder of ["正在接入", "敬请期待", "即将上线"]) {
      assert.ok(!pageSource.includes(placeholder), `不得使用占位文案：${placeholder}`);
    }
  });

  it("透明度说明区分候选模型与状态驱动干预，不暗示影子会改计划", () => {
    const note = pageSource.match(/ls-transparency__note">([\s\S]*?)<\/p>/);
    assert.ok(note, "透明度说明必须存在");
    const text = note[1].replace(/<[^>]+>/g, "");
    assert.match(text, /只读展示/);
    assert.match(text, /状态驱动干预/);
    assert.match(text, /APPLIED/);
    assert.ok(
      !/影子评测结果不会自动修改计划。\s*$/.test(text),
      "旧的模糊说明必须被更精确的版本替换",
    );
  });

  it("如实说明确认计划后才进入自动观测，而不是暗示生成即自动重规划", () => {
    assert.match(
      pageSource,
      /确认计划后，系统会在观测窗结束后自动核对执行情况；只有证据支持时才会调整计划。/,
    );
  });

  it("注解有独立样式，不依赖内联样式", () => {
    assert.match(cssSource, /\.ls-candidate\b/);
    assert.match(cssSource, /\.ls-candidate\[data-available="false"\]/);
  });
});

describe("计划摘要 API 契约", () => {
  it("getPlanSummary 命中 /learning-plans/{id}/summary", () => {
    assert.match(apiSource, /export async function getPlanSummary\(planId\)\s*{\s*return _get\(`\/learning-plans\/\$\{planId\}\/summary`\);/);
  });
});
