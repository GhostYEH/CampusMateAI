/**
 * counselor SSE 解析的边界语义。
 *
 * 真实风险：
 *  - 代理/网关把 `data:` 拆成多行（SSE 规范要求以 \n 连接），只取最后一行会丢内容；
 *  - 重连或代理重放会产生**第二个 done**，二次触发 `onDone` 就会重复创建课堂任务；
 *  - 连接在最后一条事件之后直接关闭（没有结尾空行）时，最后的 done 元数据必须照样 flush，
 *    否则学生永远看不到互动课堂提案。
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./helpers/setup-globals.mjs";

const REAL_FETCH = globalThis.fetch;

/** 用一段原始 SSE 文本构造一个可读流响应。 */
function sseResponse(chunks) {
  const encoder = new TextEncoder();
  let index = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader() {
        return {
          async read() {
            if (index >= chunks.length) return { done: true, value: undefined };
            const value = encoder.encode(chunks[index]);
            index += 1;
            return { done: false, value };
          },
        };
      },
    },
  };
}

async function collect(raw) {
  const api = await import("../src/data/api.js");
  const seen = { sources: [], chunks: [], done: [], errors: [] };
  globalThis.fetch = async () => sseResponse(raw);
  try {
    await api.chatStream("问题", {
      onSources: (v) => seen.sources.push(v),
      onChunk: (text, mode) => seen.chunks.push([text, mode]),
      onDone: (meta) => seen.done.push(meta),
      onError: (err) => seen.errors.push(err.message),
    });
  } finally {
    globalThis.fetch = REAL_FETCH;
  }
  return seen;
}

test.afterEach(() => {
  globalThis.fetch = REAL_FETCH;
});

test("多行 data 按 SSE 规范以换行连接后再解析", async () => {
  // 一个 JSON 被拆成两行 data:（代理/网关的合法行为）
  const seen = await collect(
    'event: chunk\ndata: {"text":"前半",\ndata: "mode":"llm"}\n\n' +
      'event: done\ndata: {"answer":"完整","conversation_id":"c1"}\n\n',
  );
  assert.deepEqual(seen.chunks, [["前半", "llm"]]);
  assert.equal(seen.done.length, 1);
  assert.equal(seen.done[0].answer, "完整");
  assert.equal(seen.errors.length, 0);
});

test("冒号后没有空格也能解析", async () => {
  const seen = await collect('event:chunk\ndata:{"text":"没有空格","mode":"llm"}\n\n');
  assert.deepEqual(seen.chunks, [["没有空格", "llm"]]);
});

test("重复 done 只投递一次", async () => {
  const seen = await collect(
    'event: done\ndata: {"answer":"第一次","conversation_id":"c1"}\n\n' +
      'event: done\ndata: {"answer":"第二次","conversation_id":"c1"}\n\n',
  );
  assert.equal(seen.done.length, 1, "重复 done 不得二次触发副作用");
  assert.equal(seen.done[0].answer, "第一次");
});

test("流在最后一条事件后直接结束（没有结尾空行）也必须 flush", async () => {
  const seen = await collect(
    'event: chunk\ndata: {"text":"回答","mode":"llm"}\n\n' +
      'event: done\ndata: {"answer":"回答","conversation_id":"c1",' +
      '"suggested_actions":[{"id":"interactive-classroom","type":"interactiveClassroomProposal",' +
      '"data":{"proposal_id":"icp_1","course_id":"c1"}}]}',
  );
  assert.deepEqual(seen.chunks, [["回答", "llm"]]);
  assert.equal(seen.done.length, 1, "结尾没有空行的 done 必须被 flush");
  assert.equal(seen.done[0].suggested_actions[0].data.proposal_id, "icp_1");
});

test("注释与心跳行被忽略，不产生副作用", async () => {
  const seen = await collect(
    ": keep-alive\n\n" +
      'event: chunk\ndata: {"text":"回答","mode":"llm"}\n\n' +
      'event: done\ndata: {"answer":"回答","conversation_id":"c1"}\n\n',
  );
  assert.deepEqual(seen.chunks, [["回答", "llm"]]);
  assert.equal(seen.done.length, 1);
  assert.equal(seen.errors.length, 0);
});

test("事件被拆到多个网络分片时仍能正确重组", async () => {
  const seen = await collect([
    'event: chu',
    'nk\ndata: {"text":"跨',
    '分片","mode":"llm"}\n\nevent: done\ndata: {"answer":"跨分片","conv',
    'ersation_id":"c1"}\n\n',
  ]);
  assert.deepEqual(seen.chunks, [["跨分片", "llm"]]);
  assert.equal(seen.done.length, 1);
  assert.equal(seen.done[0].answer, "跨分片");
});
