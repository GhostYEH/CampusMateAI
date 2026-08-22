import assert from "node:assert/strict";
import { test } from "node:test";
import { fetchHitokoto, formatHitokotoSource, isSuitableHitokoto } from "../src/services/hitokoto.js";

test("formats a complete Hitokoto source without exposing unknown values", () => {
  assert.equal(formatHitokotoSource({ from_who: "村上春树", from: "挪威的森林" }), "—— 村上春树 · 挪威的森林");
  assert.equal(formatHitokotoSource({ from_who: "未知", from: "" }), "—— 一言");
  assert.equal(formatHitokotoSource({ from_who: null, from: "校园生活" }), "—— 校园生活");
});

test("fetches and validates a Hitokoto response", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ uuid: "abc", hitokoto: "让每一天都值得期待。", from: "测试", from_who: null, type: "e" }), { status: 200 });

  try {
    const result = await fetchHitokoto({ timeoutMs: 100 });
    assert.deepEqual(result, { uuid: "abc", hitokoto: "让每一天都值得期待。", from: "测试", from_who: null, type: "e" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("only accepts meaningful and positive-enough sentences", () => {
  assert.equal(isSuitableHitokoto({ hitokoto: "愿你眼里有光，心中有方向。", type: "i" }), true);
  assert.equal(isSuitableHitokoto({ hitokoto: "哈哈哈哈哈哈", type: "g" }), false);
  assert.equal(isSuitableHitokoto({ hitokoto: "绝望和毁灭没有尽头。", type: "d" }), false);
});

test("refetches once when the first sentence is unsuitable", async () => {
  const responses = [
    { uuid: "bad", hitokoto: "绝望和毁灭没有尽头。", type: "d" },
    { uuid: "good", hitokoto: "愿你眼里有光，心中有方向。", type: "i", from: "测试" },
  ];
  const urls = [];
  const result = await fetchHitokoto({
    timeoutMs: 100,
    fetchImpl: async (url) => {
      urls.push(url);
      return new Response(JSON.stringify(responses.shift()), { status: 200 });
    },
  });

  assert.equal(result.uuid, "good");
  assert.equal(urls.length, 2);
  assert.match(urls[0], /c=d/);
  assert.match(urls[0], /c=i/);
  assert.match(urls[0], /c=k/);
  assert.match(urls[0], /c=e/);
});

test("rejects an invalid Hitokoto response", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ uuid: "abc" }), { status: 200 });

  try {
    await assert.rejects(fetchHitokoto({ timeoutMs: 100 }), /invalid Hitokoto response/i);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("aborts a request after the configured timeout", async () => {
  const fetchImpl = async (_url, { signal }) => await new Promise((_, reject) => {
    signal.addEventListener("abort", () => reject(new DOMException("The operation was aborted", "AbortError")), { once: true });
  });

  await assert.rejects(fetchHitokoto({ timeoutMs: 10, fetchImpl }), { name: "AbortError" });
});
