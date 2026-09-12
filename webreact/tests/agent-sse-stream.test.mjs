/**
 * Agent SSE parser 测试：分块 JSON、CRLF、多行 data、sequence 去重、
 * Last-Event-ID 续传、401 刷新、退避重连、主动取消。
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  splitSseBlocks,
  decodeSseFrame,
  decodeSsePayload,
  parseSseChunk,
  createAgentSseStream,
} from "../src/data/agentSseStream.js";

// 构造一个 mock Response，body 为 ReadableStream，按 chunks 分块推送。
function mockResponse({ status = 200, chunks = [], body = null, headers = {} }) {
  const stream = new ReadableStream({
    start(controller) {
      if (body != null) {
        controller.enqueue(new TextEncoder().encode(body));
      } else {
        for (const c of chunks) controller.enqueue(new TextEncoder().encode(c));
      }
      controller.close();
    },
  });
  return { status, ok: status >= 200 && status < 300, body: stream, headers };
}

describe("SSE frame parsing", () => {
  it("按空行拆分帧并保留剩余片段", () => {
    const buf = "data: a\n\ndata: b\n\ndata: c";
    const { blocks, remainder } = splitSseBlocks(buf);
    assert.equal(blocks.length, 2);
    assert.equal(remainder, "data: c");
  });

  it("支持 CRLF 分隔", () => {
    const buf = "data: a\r\n\r\ndata: b\r\n\r\n";
    const { blocks, remainder } = splitSseBlocks(buf);
    assert.equal(blocks.length, 2);
    assert.equal(remainder, "");
  });

  it("解析 id/event/data 字段", () => {
    const frame = "id: evt_1\nevent: TOOL_COMPLETED\ndata: {\"sequence\":1}";
    const out = decodeSseFrame(frame);
    assert.equal(out.id, "evt_1");
    assert.equal(out.event, "TOOL_COMPLETED");
    assert.equal(out.data, "{\"sequence\":1}");
  });

  it("多行 data 用换行连接", () => {
    const frame = "data: line1\ndata: line2";
    const out = decodeSseFrame(frame);
    assert.equal(out.data, "line1\nline2");
  });

  it("注释行以冒号开头被忽略", () => {
    const frame = ": keep-alive\ndata: x";
    const out = decodeSseFrame(frame);
    assert.equal(out.data, "x");
  });

  it("data 字段值前导空格被剥离（SSE 规范只剥一个）", () => {
    assert.equal(decodeSseFrame("data: hello").data, "hello");
    assert.equal(decodeSseFrame("data:  hello").data, " hello");
  });

  it("payload JSON 解码", () => {
    assert.deepEqual(decodeSsePayload("{\"a\":1}"), { a: 1 });
    assert.equal(decodeSsePayload("not json"), null);
    assert.equal(decodeSsePayload(""), null);
  });
});

describe("SSE chunk assembly", () => {
  it("分块到达的 JSON 被正确拼装", () => {
    const part1 = "data: {\"id\":\"evt_1\",\"sequen";
    const part2 = "ce\":1,\"type\":\"RUN_STARTED\"}\n\n";
    let buffer = part1;
    let parsed = parseSseChunk(buffer);
    assert.equal(parsed.events.length, 0);
    buffer = parsed.remainder + part2;
    parsed = parseSseChunk(buffer);
    assert.equal(parsed.events.length, 1);
    assert.equal(parsed.events[0].payload.type, "RUN_STARTED");
    assert.equal(parsed.events[0].payload.sequence, 1);
  });

  it("多帧一次到达全部解析", () => {
    const buf = "id: e1\ndata: {\"sequence\":1}\n\nid: e2\ndata: {\"sequence\":2}\n\n";
    const parsed = parseSseChunk(buf);
    assert.equal(parsed.events.length, 2);
    assert.equal(parsed.lastEventId, "e2");
  });

  it("lastEventId 跨 chunk 续传", () => {
    const r1 = parseSseChunk("id: e1\ndata: {\"sequence\":1}\n\n", null);
    const r2 = parseSseChunk("id: e2\ndata: {\"sequence\":2}\n\n", r1.lastEventId);
    assert.equal(r2.lastEventId, "e2");
  });
});

describe("SSE stream lifecycle", () => {
  it("按 sequence 去重，重复事件不回调", async () => {
    const events = [];
    const body = "data: {\"sequence\":1,\"type\":\"RUN_STARTED\"}\n\ndata: {\"sequence\":1,\"type\":\"RUN_STARTED\"}\n\ndata: {\"sequence\":2,\"type\":\"MODEL_COMPLETED\"}\n\n";
    const responses = [mockResponse({ body })];
    let i = 0;
    const stream = createAgentSseStream({
      url: "http://x/events",
      buildHeaders: () => ({}),
      onEvent: (e) => events.push(e),
      onStatus: () => {},
      fetchImpl: () => Promise.resolve(responses[i++] || mockResponse({ status: 204 })),
      delayFn: () => 1,
      maxReconnects: 0,
    });
    await stream.done;
    assert.equal(events.length, 2);
    assert.equal(events[0].payload.sequence, 1);
    assert.equal(events[1].payload.sequence, 2);
    assert.equal(stream.getMaxSequence(), 2);
  });

  it("Last-Event-ID 在重连时发送", async () => {
    const seenHeaders = [];
    const body1 = "id: evt_5\ndata: {\"sequence\":5}\n\n";
    const responses = [
      mockResponse({ body: body1 }),
      mockResponse({ body: "" }),
    ];
    let i = 0;
    const stream = createAgentSseStream({
      url: "http://x/events",
      buildHeaders: () => ({ Authorization: "Bearer t" }),
      onEvent: () => {},
      onStatus: () => {},
      fetchImpl: (_url, opts) => { seenHeaders.push(opts.headers); return Promise.resolve(responses[i++] || mockResponse({ status: 204 })); },
      delayFn: () => 1,
      maxReconnects: 1,
    });
    await stream.done;
    assert.equal(seenHeaders[0]["Last-Event-ID"], undefined);
    assert.equal(seenHeaders[1]?.["Last-Event-ID"], "evt_5");
  });

  it("401 触发 refreshAuth 后重连", async () => {
    let refreshed = 0;
    const events = [];
    const responses = [
      mockResponse({ status: 401 }),
      mockResponse({ body: "data: {\"sequence\":1}\n\n" }),
      mockResponse({ status: 204 }),
    ];
    let i = 0;
    const stream = createAgentSseStream({
      url: "http://x/events",
      buildHeaders: () => ({}),
      onEvent: (e) => events.push(e),
      onStatus: () => {},
      fetchImpl: () => Promise.resolve(responses[i++] || mockResponse({ status: 204 })),
      refreshAuth: async () => { refreshed += 1; },
      delayFn: () => 1,
      maxReconnects: 2,
    });
    await stream.done;
    assert.equal(refreshed, 1);
    assert.equal(events.length, 1);
  });

  it("refreshAuth 失败时发出 unauthorized 并停止", async () => {
    const statuses = [];
    const responses = [mockResponse({ status: 401 })];
    let i = 0;
    const stream = createAgentSseStream({
      url: "http://x/events",
      buildHeaders: () => ({}),
      onEvent: () => {},
      onStatus: (s) => statuses.push(s),
      fetchImpl: () => Promise.resolve(responses[i++] || mockResponse({ status: 204 })),
      refreshAuth: async () => { throw new Error("no refresh token"); },
      delayFn: () => 1,
      maxReconnects: 3,
    });
    await stream.done;
    assert.ok(statuses.includes("unauthorized"));
  });

  it("主动取消停止流且不再重连", async () => {
    const statuses = [];
    const ac = new AbortController();
    const abortError = () => { const e = new Error("aborted"); e.name = "AbortError"; return e; };
    const stream = createAgentSseStream({
      url: "http://x/events",
      buildHeaders: () => ({}),
      onEvent: () => {},
      onStatus: (s) => statuses.push(s),
      signal: ac.signal,
      fetchImpl: (_url, opts) => new Promise((_resolve, reject) => {
        if (opts.signal.aborted) return reject(abortError());
        opts.signal.addEventListener("abort", () => reject(abortError()), { once: true });
      }),
      delayFn: () => 1,
      maxReconnects: 5,
    });
    await new Promise((r) => setTimeout(r, 5));
    stream.cancel();
    await stream.done;
    assert.ok(statuses.includes("closed"));
  });

  it("网络错误后退避重连并最终成功", async () => {
    const events = [];
    const responses = [
      Promise.reject(new Error("network down")),
      mockResponse({ body: "data: {\"sequence\":1}\n\n" }),
      mockResponse({ status: 204 }),
    ];
    let i = 0;
    const stream = createAgentSseStream({
      url: "http://x/events",
      buildHeaders: () => ({}),
      onEvent: (e) => events.push(e),
      onStatus: () => {},
      fetchImpl: () => Promise.resolve(responses[i++] || mockResponse({ status: 204 })),
      delayFn: () => 1,
      maxReconnects: 3,
    });
    await stream.done;
    assert.equal(events.length, 1);
  });
});