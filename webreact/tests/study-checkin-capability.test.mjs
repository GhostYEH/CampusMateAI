import test from "node:test";
import assert from "node:assert/strict";
import { client, getStudyCheckins } from "../src/data/api.js";

test("a health transport failure is reported instead of claiming check-ins are unsupported", async () => {
  const previous = client.defaults.adapter;
  client.defaults.adapter = (config) => Promise.reject({
    config, request: {}, code: "ECONNABORTED", message: "timeout",
  });
  try {
    await assert.rejects(getStudyCheckins(), (error) => {
      assert.equal(error.code, "ECONNABORTED");
      assert.match(error.message, /超时/);
      return true;
    });
  } finally { client.defaults.adapter = previous; }
});

test("only an explicit health capability result produces the unsupported state", async () => {
  const previous = client.defaults.adapter;
  client.defaults.adapter = async (config) => ({ config, status: 200, headers: {}, data: { study_checkins_supported: false } });
  try { assert.equal((await getStudyCheckins()).unsupported, true); }
  finally { client.defaults.adapter = previous; }
});
