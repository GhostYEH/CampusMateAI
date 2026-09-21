/**
 * 阶段 5 —— CPM 互动课堂提案卡的渲染与受管接口契约。
 *
 * 用真实 React 渲染（vite ssrLoadModule + renderToStaticMarkup）断言学生看到什么，
 * 并用 mock axios 断言前端只调用 CampusMate 的受管接口（/agent-jobs、
 * /agent-approvals），绝不直接触达 magic class。
 */
import test, { after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import "./helpers/setup-globals.mjs";
import * as apiModule from "../src/data/api.js";
import { createMockClient } from "./helpers/mock-client.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");
const REAL_FETCH = globalThis.fetch;

const vite = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "silent",
});

after(async () => {
  globalThis.fetch = REAL_FETCH;
  await vite.close();
});

const { default: ClassroomProposalCard } = await vite.ssrLoadModule(
  "/src/components/interactive/ClassroomProposalCard.jsx",
);

const proposal = (overrides = {}) => ({
  course_id: "c1",
  course_name: "高等数学",
  mode: "review",
  mode_label: "考前复习",
  label: "生成一节「考前复习」互动课堂",
  intent_note: "内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。",
  available: true,
  requires_confirmation: true,
  job_kind: "interactive_classroom",
  ...overrides,
});

const render = (props) =>
  renderToStaticMarkup(createElement(ClassroomProposalCard, props));

test("提案卡展示课程、形态、意图声明与确认按钮", () => {
  const markup = render({ proposal: proposal() });
  assert.match(markup, /互动课堂建议/);
  assert.match(markup, /高等数学/);
  assert.match(markup, /考前复习/);
  assert.match(markup, /生成意图/);
  assert.match(markup, /确认生成/);
});

test("提案卡不提供取消/MP4 等未实现动作", () => {
  const markup = render({ proposal: proposal() });
  assert.doesNotMatch(markup, /MP4/);
  assert.doesNotMatch(markup, />取消</);
  assert.doesNotMatch(markup, /归档/);
});

test("服务不可用时禁止确认生成并说明原因", () => {
  const markup = render({
    proposal: proposal({ available: false, reason: "互动课堂服务未启用" }),
  });
  assert.match(markup, /互动课堂暂不可用/);
  assert.match(markup, /互动课堂服务未启用/);
  assert.match(markup, /disabled/);
  // 仍可继续用文字提问，不阻断对话
  assert.match(markup, /继续用文字提问/);
});

test("没有 course_id 时不渲染任何东西", () => {
  assert.equal(render({ proposal: null }), "");
  assert.equal(render({ proposal: { mode: "review" } }), "");
});

test("提案卡源码不直接触达 magic class", () => {
  const src = read("src/components/interactive/ClassroomProposalCard.jsx");
  // 不得出现任何直连外部服务的痕迹
  assert.doesNotMatch(src, /fetch\(/);
  assert.doesNotMatch(src, /https?:\/\//);
  assert.doesNotMatch(src, /magicclass_?(base_url|access_code|access)/i);
  // 并发防护与受管接口调用全部委托给作用域会话模块
  assert.match(src, /createProposalSession/);
  assert.match(src, /from "\.\.\/\.\.\/data\/classroomProposalSession\.js"/);
  // 只有真实终态才给深链，不提前声称完成
  assert.match(src, /已准备好，需要你确认后才会真正开始生成/);
});

test("作用域会话模块是唯一调用受管接口的地方，且不触达 magic class", () => {
  const src = read("src/data/classroomProposalSession.js");
  assert.match(src, /createAgentJob/);
  assert.match(src, /decideAgentApproval/);
  assert.match(src, /getAgentJob/);
  assert.doesNotMatch(src, /fetch\(/);
  assert.doesNotMatch(src, /https?:\/\//);
  assert.doesNotMatch(src, /magicclass/i);
  // 迟到响应防护必须同时校验 epoch 与 jobId
  assert.match(src, /function isCurrent\(myEpoch, jobId\)/);
  assert.match(src, /myEpoch !== epoch/);
});

test("受管接口契约：创建 job / 审批 / 查询", async () => {
  const mock = createMockClient(apiModule.default);
  mock.reset();
  mock.onPost("/agent-jobs", {
    job_id: "job_1",
    job_kind: "interactive_classroom",
    status: "AWAITING_APPROVAL",
    pending_approval_id: "apv_1",
    input_ref: { course_id: "c1", mode: "review" },
  });
  mock.onPost("/agent-approvals/apv_1/decision", {
    approval_id: "apv_1",
    status: "APPROVED",
  });
  mock.onGet("/agent-jobs/job_1", {
    job_id: "job_1",
    status: "SUCCEEDED",
    input_ref: {
      course_id: "c1",
      mode: "review",
      session_id: "om_1",
      deep_link: "/courses/c1?tab=mentoring&session=om_1",
    },
  });

  const job = await apiModule.createAgentJob({
    job_kind: "interactive_classroom",
    input_ref: { course_id: "c1", mode: "review" },
  });
  assert.equal(job.pending_approval_id, "apv_1");
  assert.equal(mock.lastRequest().url, "/agent-jobs");

  const decided = await apiModule.decideAgentApproval("apv_1", "APPROVED");
  assert.equal(decided.status, "APPROVED");

  const detail = await apiModule.getAgentJob("job_1");
  assert.equal(detail.input_ref.deep_link, "/courses/c1?tab=mentoring&session=om_1");
  // 全程只访问 CampusMate 自己的接口
  for (const req of mock.requests) {
    assert.match(req.url, /^\/agent-(jobs|approvals)/);
  }
});

test("CounselorPage 接线：读取提案并渲染确认卡", () => {
  const page = read("src/pages/CounselorPage.jsx");
  assert.match(page, /interactiveClassroomProposal/);
  assert.match(page, /setClassroomProposal\(proposal\?\.data \|\| null\)/);
  assert.match(page, /<ClassroomProposalCard/);
});

test("CounselorPage 把当前身份与提案 nonce 传给确认卡", () => {
  const page = read("src/pages/CounselorPage.jsx");
  // 身份必须来自登录会话，不能是常量 —— 否则账号切换后会恢复上一个账号的任务
  assert.match(page, /session\?\.id \|\| session\?\.user_id \|\| session\?\.username/);
  assert.match(page, /identity=\{classroomIdentity\}/);
  // 用服务端 nonce 作为 key：同课程同模式的第二个提案必须重新挂载
  assert.match(page, /key=\{classroomProposal\.proposal_id \|\| classroomProposal\.course_id\}/);
});

test("CounselorPage 的流式回写全部绑定会话代次", () => {
  const page = read("src/pages/CounselorPage.jsx");
  // 会话代次存在
  assert.match(page, /const chatEpoch = useRef\(0\)/);
  assert.match(page, /const myEpoch = chatEpoch\.current/);
  assert.match(page, /const isCurrentChat = \(\) => myEpoch === chatEpoch\.current/);
  // 四个异步分支（sources / chunk / done / error）+ finally 都必须校验
  const guardCount = (page.match(/if \(!isCurrentChat\(\)\) return;/g) || []).length;
  assert.ok(guardCount >= 4, `异步分支缺少代次校验，实际只有 ${guardCount} 处`);
  assert.match(page, /if \(isCurrentChat\(\)\) \{ setSending\(false\); aborter\.current = null; \}/);
  // 会话切换必须作废在途请求
  assert.match(page, /function resetConversationScope\(\)/);
  assert.match(page, /function seedSample\(\) \{ resetConversationScope\(\);/);
  assert.match(page, /function newSession\(\) \{ resetConversationScope\(\);/);
  assert.match(page, /function restoreSession\(item\) \{\s*resetConversationScope\(\);/);
  assert.match(page, /const exitCourseContext = \(\) => \{ resetConversationScope\(\);/);
});
