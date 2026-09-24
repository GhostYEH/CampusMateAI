import test from "node:test";
import assert from "node:assert/strict";
import { client, downloadAssignmentAttachment, downloadCourseResource } from "../src/data/api.js";

test("course and assignment downloads keep their paths, names, and URL cleanup", async () => {
  const previousAdapter = client.defaults.adapter;
  const previousDocument = globalThis.document;
  const previousCreateObjectURL = URL.createObjectURL;
  const previousRevokeObjectURL = URL.revokeObjectURL;
  const requests = [];
  const links = [];
  const revoked = [];

  client.defaults.adapter = async (config) => {
    requests.push({ url: config.url, responseType: config.responseType });
    return {
      config,
      status: 200,
      data: { source: config.url },
      headers: { "content-disposition": "course-from-header.pdf" },
    };
  };
  URL.createObjectURL = (blob) => `blob:${blob.source}`;
  URL.revokeObjectURL = (url) => revoked.push(url);
  globalThis.document = {
    createElement(tag) {
      assert.equal(tag, "a");
      const link = {
        click() { link.clicked = true; },
        remove() { link.removed = true; },
      };
      links.push(link);
      return link;
    },
    body: { appendChild(link) { link.appended = true; } },
  };

  try {
    await downloadCourseResource("course-1", "file-1", "");
    await downloadAssignmentAttachment("assignment-1", "file-2");

    assert.deepEqual(requests, [
      { url: "/courses/course-1/resources/file-1/download", responseType: "blob" },
      { url: "/assignments/assignment-1/attachments/file-2", responseType: "blob" },
    ]);
    assert.deepEqual(links.map((link) => link.download), ["course-from-header.pdf", "作业附件"]);
    assert.ok(links.every((link) => link.appended && link.clicked && link.removed));
    assert.deepEqual(revoked, links.map((link) => link.href));
  } finally {
    client.defaults.adapter = previousAdapter;
    globalThis.document = previousDocument;
    URL.createObjectURL = previousCreateObjectURL;
    URL.revokeObjectURL = previousRevokeObjectURL;
  }
});
