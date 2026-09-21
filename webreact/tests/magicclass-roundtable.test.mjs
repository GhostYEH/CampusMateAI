/**
 * 圆桌讨论视图模型的契约测试。
 *
 * 圆桌最容易"看起来像在讨论其实什么都没说"，所以这里钉住的是四件容易悄悄退化的事：
 * 发言人配色必须**确定性**（随机色会让同一个人在同一场讨论里变色）、空发言不得
 * 变成空气泡、"任务完成但没有发言"不得显示成讨论已结束、失败必须给出可行动的中文。
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
  MAX_MESSAGE_CHARS,
  SPEAKER_PALETTE,
  describeDiscussionFailure,
  discussionPromptFor,
  discussionRejection,
  discussionSpeakers,
  normalizeDiscussionMessages,
  roundtablePhase,
  speakerColor,
  speakerInitial,
} from "../src/features/magicclass/roundtableModel.js";

test("a speaker keeps the same colour everywhere, derived from the name", () => {
  // 用名字派生而不是随机：随机色会让同一个人在同一场讨论里变来变去，
  // 也会让刷新前后同一场讨论看起来是两场。
  assert.deepEqual(speakerColor("主讲人"), speakerColor("主讲人"));
  assert.deepEqual(speakerColor(" 主讲人 "), speakerColor("主讲人"), "首尾空白不应改变配色");
  assert.ok(SPEAKER_PALETTE.includes(speakerColor("追问者")));
  // 空名字也要有稳定兜底，不能返回 undefined 让渲染层崩。
  assert.deepEqual(speakerColor(""), speakerColor(""));
  assert.ok(SPEAKER_PALETTE.includes(speakerColor(undefined)));
});

test("a speaker initial never renders an empty avatar", () => {
  assert.equal(speakerInitial("主讲人"), "主");
  assert.equal(speakerInitial(""), "智");
  assert.equal(speakerInitial(undefined), "智");
  assert.equal(speakerInitial("   "), "智");
});

test("empty messages never become empty bubbles", () => {
  const normalized = normalizeDiscussionMessages({
    messages: [
      { agent: "甲", content: "有内容" },
      { agent: "乙", content: "   " },
      { agent: "丙", content: "" },
      { agent: "丁" },
      null,
      "文本",
      { agent: "戊", content: "  有内容  " },
    ],
  });
  assert.deepEqual(normalized, [
    { agent: "甲", content: "有内容" },
    { agent: "戊", content: "有内容" },
  ]);
});

test("a missing agent name falls back instead of rendering undefined", () => {
  assert.deepEqual(normalizeDiscussionMessages([{ content: "内容" }]), [{ agent: "智能体", content: "内容" }]);
});

test("an over-long message is bounded so one bubble cannot blow up the panel", () => {
  const [message] = normalizeDiscussionMessages([{ agent: "甲", content: "字".repeat(MAX_MESSAGE_CHARS + 500) }]);
  assert.equal(message.content.length, MAX_MESSAGE_CHARS + 1, "截断后应带上省略号");
  assert.ok(message.content.endsWith("…"));
});

test("the normalized shape accepts both an array and a messages object", () => {
  // artifact 里是对象，历史记录里是数组；两条路径都会走到这里。
  assert.equal(normalizeDiscussionMessages([{ agent: "甲", content: "a" }]).length, 1);
  assert.equal(normalizeDiscussionMessages({ messages: [{ agent: "甲", content: "a" }] }).length, 1);
  for (const bad of [undefined, null, 7, "text", {}, { messages: "nope" }]) {
    assert.deepEqual(normalizeDiscussionMessages(bad), [], `畸形输入必须得到空数组：${JSON.stringify(bad)}`);
  }
});

test("speakers are listed in first-appearance order without duplicates", () => {
  const speakers = discussionSpeakers([
    { agent: "乙", content: "1" },
    { agent: "甲", content: "2" },
    { agent: "乙", content: "3" },
  ]);
  assert.deepEqual(speakers.map((speaker) => speaker.name), ["乙", "甲"]);
  assert.deepEqual(speakers[0].color, speakerColor("乙"));
});

test("a finished task with no messages is empty, not finished", () => {
  // "拿到了空数组"与"讨论结束了"是两件事；把它们合成一件事会让界面假装开过会。
  assert.equal(roundtablePhase({ busy: false, error: "", messages: [] }), "empty");
  assert.equal(roundtablePhase({ busy: true, error: "", messages: [] }), "running");
  assert.equal(roundtablePhase({ busy: false, error: "", messages: [{ agent: "甲", content: "a" }] }), "ready");
  // 失败优先于其它状态：有错误时不该还显示"进行中"。
  assert.equal(roundtablePhase({ busy: true, error: "炸了", messages: [{ agent: "甲", content: "a" }] }), "failed");
});

test("failures are translated into actionable Chinese", () => {
  assert.match(describeDiscussionFailure({ response: { status: 503 } }), /稍后重试|不可用|连不上/);
  assert.match(describeDiscussionFailure({ response: { status: 400 } }), /不合法|换个主题/);
  assert.match(describeDiscussionFailure({ response: { status: 404 } }), /不存在/);
  assert.match(
    describeDiscussionFailure({ response: { data: { code: "provider_unavailable" } } }),
    /没有配置|无法发起/,
  );
  // 服务端给了 detail 就原样用；既没有 detail 也没有 code 时也不能吞成一句"失败"。
  assert.match(describeDiscussionFailure({ response: { data: { detail: "上游超时" } } }), /上游超时/);
  assert.match(describeDiscussionFailure({ message: "network down" }), /network down/);
  assert.match(describeDiscussionFailure(undefined), /没能完成/);
  assert.doesNotMatch(describeDiscussionFailure({}), /undefined/);
});

test("the discussion topic defaults to the current scene and never invents one", () => {
  assert.match(discussionPromptFor("进程与线程"), /进程与线程/);
  assert.equal(discussionPromptFor(""), "");
  assert.equal(discussionPromptFor(undefined), "");
  assert.equal(discussionPromptFor("   "), "");
});

test("submission is rejected with the same rule the button uses", () => {
  assert.equal(discussionRejection({ prompt: "主题", busy: false }), null);
  assert.match(discussionRejection({ prompt: "主题", busy: true }), /还在进行/);
  assert.match(discussionRejection({ prompt: "", busy: false }), /主题/);
  assert.match(discussionRejection({ prompt: "   ", busy: false }), /主题/);
  // 忙碌优先：正在跑的时候说"请先写主题"是误导。
  assert.match(discussionRejection({ prompt: "", busy: true }), /还在进行/);
});
