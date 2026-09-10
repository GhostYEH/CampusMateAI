import test from "node:test";
import assert from "node:assert/strict";

import {
  captchaDataUrl,
  eduSyncMessage,
  verificationActionMessage,
} from "../src/data/eduIntegration.js";


test("successful schedule sync reports verified persistence instead of submission", () => {
  assert.equal(eduSyncMessage("schedule", {
    status: "success",
    stage: "commit",
    persisted: true,
    items_count: 8,
  }), "课表同步成功，已校验并保存 8 条课程记录");
});


test("failed schedule sync tells the user that the previous schedule was preserved", () => {
  assert.equal(eduSyncMessage("schedule", {
    status: "failed",
    stage: "validate",
    previous_schedule_preserved: true,
    error_message: "课表结构校验失败",
  }), "课表校验失败：课表结构校验失败；原有课表未被覆盖");
});


test("schedule response cannot claim success without persistence", () => {
  assert.equal(eduSyncMessage("schedule", {
    status: "success",
    stage: "commit",
    persisted: false,
    items_count: 3,
  }), "课表校验已完成，但未确认写入，请稍后重试");
});


test("captcha data url uses only the backend-approved image media type", () => {
  assert.equal(captchaDataUrl({ captcha_mime_type: "image/jpeg", captcha_image_base64: "YWJj" }), "data:image/jpeg;base64,YWJj");
  assert.equal(captchaDataUrl({ captcha_mime_type: "text/html", captcha_image_base64: "YWJj" }), null);
  assert.equal(captchaDataUrl({ captcha_mime_type: "image/png", captcha_image_base64: "not base64!" }), null);
});


test("interactive challenge message directs web users to a supported client", () => {
  assert.equal(
    verificationActionMessage({ login_execution_mode: "client_webview", error_code: "NEED_MFA" }),
    "该学校需要在受限登录窗口完成验证，请使用 Android 或 HarmonyOS 客户端继续。",
  );
});
