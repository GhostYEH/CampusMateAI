/**
 * 课程研究工作台契约测试：
 * - 学术政策由后端裁决，前端不通过 mode 推断（任务 §5）
 * - FULL_SOLUTION 仅在 academic_policy=ALLOWED 时可用
 * - source_policy 传递到后端
 * - 不提交 coursework、不伪造来源
 */
import "./helpers/setup-globals.mjs";
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";

import * as api from "../src/data/agentRuntimeApi.js";
import { client } from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";
import { allowsFullSolution, academicPolicyLabel } from "../src/data/agentContracts.js";

let mock;

beforeEach(() => { mock = createMockClient(client); });
afterEach(() => { mock.reset(); mock.clearTokens(); });

describe("course-research academic policy", () => {
  it("createCourseResearchRun 传递 assistance_mode 与 source_policy", async () => {
    mock.onPost("/course-research/runs", { run_id: "r1", academic_policy: "LIMITED" });
    await api.createCourseResearchRun({
      question: "解释梯度下降",
      assistance_mode: "FULL_SOLUTION",
      source_policy: { course_material_priority: true, allow_web: true, allow_user_upload: false },
    }, "k");
    const req = mock.lastRequest();
    assert.equal(req.data.assistance_mode, "FULL_SOLUTION");
    assert.deepEqual(req.data.source_policy, { course_material_priority: true, allow_web: true, allow_user_upload: false });
  });

  it("academic_policy 来自后端响应，不通过 mode 推断", async () => {
    mock.onPost("/course-research/runs", { run_id: "r1", academic_policy: "EXAM_RESTRICTED", assistance_mode: "FULL_SOLUTION" });
    const out = await api.createCourseResearchRun({ question: "x", assistance_mode: "FULL_SOLUTION" }, "k");
    assert.equal(out.academic_policy, "EXAM_RESTRICTED");
    assert.equal(out.assistance_mode, "FULL_SOLUTION");
  });

  it("FULL_SOLUTION 仅在 ALLOWED 时可用（契约门禁）", () => {
    assert.equal(allowsFullSolution("ALLOWED"), true);
    assert.equal(allowsFullSolution("LIMITED"), false);
    assert.equal(allowsFullSolution("EXAM_RESTRICTED"), false);
    assert.equal(allowsFullSolution("AI_PROHIBITED"), false);
    assert.equal(allowsFullSolution("UNKNOWN"), false);
  });

  it("未知 academic_policy 标签回落", () => {
    assert.equal(academicPolicyLabel("ALLOWED"), "允许完整解答");
    assert.equal(academicPolicyLabel("WEIRD"), "状态待确认");
  });

  it("cancel 与 artifacts 端点", async () => {
    mock.onPost("/course-research/runs/r1/cancel", { status: "CANCELLED" });
    mock.onGet("/course-research/runs/r1/artifacts", { items: [] });
    await api.cancelCourseResearchRun("r1", "k");
    await api.getCourseResearchArtifacts("r1");
    assert.equal(mock.requests[0].url, "/course-research/runs/r1/cancel");
    assert.equal(mock.requests[1].url, "/course-research/runs/r1/artifacts");
  });
});