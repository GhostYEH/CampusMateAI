import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createServer } from "vite";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire("C:/Users/32883/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/runtime-entry.cjs");
const { chromium } = require("playwright");
let vite;
let browser;
let page;
let lastChatPayload;

before(async () => {
  vite = await createServer({ root: webRoot, logLevel: "silent", server: { host: "127.0.0.1", port: 0 } });
  await vite.listen();
  const address = vite.httpServer.address();
  browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
  page = await browser.newPage({ viewport: { width: 1672, height: 941 } });
  await page.addInitScript(() => {
    localStorage.setItem("campus_access_token", "button-test-token");
    localStorage.setItem("campus_session", JSON.stringify({ role: "student", name: "陈同学(演示)" }));
  });
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/counselor/chat")) {
      lastChatPayload = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: chunk\ndata: {"text":"测试回复"}\n\nevent: done\ndata: {"conversation_id":"button-test"}\n\n' });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) });
  });
  await page.goto(`http://127.0.0.1:${address.port}/counselor`, { waitUntil: "networkidle" });
});

after(async () => { await browser?.close(); await vite?.close(); });

test("new chat and recommendation controls update the conversation", async () => {
  await page.getByRole("button", { name: "新建对话" }).click();
  await assert.doesNotReject(() => page.getByRole("heading", { name: "开始一段新对话" }).waitFor());
  await page.getByRole("button", { name: "换一换" }).click();
  await assert.doesNotReject(() => page.getByRole("button", { name: "校园卡丢失了，怎么挂失补办？" }).waitFor());
  await page.getByRole("button", { name: "校园卡丢失了，怎么挂失补办？" }).click();
  await assert.doesNotReject(() => page.getByText("测试回复").waitFor());
});

test("attachment opens a real file picker and selected file is removable", async () => {
  await page.getByRole("button", { name: "新建对话" }).click();
  const chooserPromise = page.waitForEvent("filechooser", { timeout: 1500 });
  await page.getByRole("button", { name: "附件" }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: "课程笔记.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });
  await assert.doesNotReject(() => page.getByText("课程笔记.txt", { exact: true }).waitFor());
  await page.getByRole("button", { name: "移除附件" }).click();
  assert.equal(await page.getByText("课程笔记.txt", { exact: true }).count(), 0);
});

test("sending carries selected text attachment and web search state to the chat API", async () => {
  await page.getByRole("button", { name: "新建对话" }).click();
  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "附件" }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name: "课程笔记.txt", mimeType: "text/plain", buffer: Buffer.from("第一章考试范围") });
  await page.getByRole("button", { name: "联网搜索" }).click();
  await page.getByRole("textbox", { name: /请输入你的问题/ }).fill("帮我整理重点");
  await page.getByRole("button", { name: "发送" }).click();
  await assert.doesNotReject(() => page.getByText("测试回复").waitFor());
  assert.equal(lastChatPayload.web_search, true);
  assert.deepEqual(lastChatPayload.attachment, {
    name: "课程笔记.txt",
    type: "text/plain",
    size: 21,
    content: "第一章考试范围",
  });
});

test("web search toggles visibly and policy buttons open closable dialogs", async () => {
  const search = page.getByRole("button", { name: "联网搜索" });
  const initial = await search.getAttribute("aria-pressed");
  await search.click();
  assert.equal(await search.getAttribute("aria-pressed"), initial === "true" ? "false" : "true");
  await search.click();
  assert.equal(await search.getAttribute("aria-pressed"), initial);

  await page.getByRole("button", { name: "服务条款" }).click();
  await assert.doesNotReject(() => page.getByRole("dialog", { name: "服务条款" }).waitFor());
  await page.getByRole("button", { name: "关闭弹窗" }).click();
  assert.equal(await page.getByRole("dialog", { name: "服务条款" }).count(), 0);

  await page.getByRole("button", { name: "隐私政策" }).click();
  await assert.doesNotReject(() => page.getByRole("dialog", { name: "隐私政策" }).waitFor());
  await page.getByRole("button", { name: "关闭弹窗" }).click();
});

test("navigation and campus service buttons reach their real destinations", async () => {
  await page.getByRole("button", { name: "更多", exact: true }).click();
  await page.waitForURL("**/services");
  assert.equal(new URL(page.url()).pathname, "/services");
  await page.goto(page.url().replace("/services", "/counselor"), { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /学籍与成绩/ }).click();
  await assert.doesNotReject(() => page.getByText("测试回复").waitFor());
});
