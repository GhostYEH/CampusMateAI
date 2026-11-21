import test from "node:test";
import assert from "node:assert/strict";

import {
  addWhiteboardText,
  blankWhiteboard,
  clearWhiteboard,
  whiteboardFromStageDocument,
} from "../src/features/magicclass/whiteboardModel.js";

const board = {
  id: "wb-1",
  viewportSize: 1000,
  viewportRatio: 0.5625,
  elements: [{ id: "el-1", type: "text", content: "已有板书" }],
};

test("白板只从舞台文档读取完整快照，不把引用当内容", () => {
  const documentWithBoard = {
    revision: 8,
    document: { stage: { whiteboard: [board] }, scenes: [] },
  };
  assert.deepEqual(whiteboardFromStageDocument(documentWithBoard), board);

  const referenceOnly = {
    document: { stage: { whiteboard: [{ id: "wb-ref", elements: null }] }, scenes: [] },
  };
  assert.deepEqual(whiteboardFromStageDocument(referenceOnly), blankWhiteboard());
  assert.deepEqual(whiteboardFromStageDocument(null), blankWhiteboard());
});

test("场景级白板作为旧文档的回退来源", () => {
  const documentWithSceneBoard = {
    document: { scenes: [{ id: "scene-1", whiteboards: [board] }] },
  };
  assert.equal(whiteboardFromStageDocument(documentWithSceneBoard).id, "wb-1");
});

test("新增文字卡使用稳定 id、错开坐标并转义 HTML", () => {
  const next = addWhiteboardText(board, '<极限 & 存在>', "wb-text-1");
  assert.equal(next.elements.length, 2);
  const added = next.elements[1];
  assert.equal(added.id, "wb-text-1");
  assert.equal(added.type, "text");
  assert.ok(added.left > 72);
  assert.match(added.content, /&lt;极限 &amp; 存在&gt;/);
  assert.doesNotMatch(added.content, /<极限/);
});

test("空文字和超长文字被拒绝，清空保留白板元数据", () => {
  assert.throws(() => addWhiteboardText(board, "   ", "id"), /不能为空/);
  assert.throws(() => addWhiteboardText(board, "x".repeat(601), "id"), /最多/);
  const cleared = clearWhiteboard({ ...board, elements: [board.elements[0], board.elements[0]] });
  assert.equal(cleared.id, "wb-1");
  assert.equal(cleared.viewportSize, 1000);
  assert.deepEqual(cleared.elements, []);
});

test("课堂把白板接进真实舞台文档和带 revision 的保存接口", async () => {
  const { readFile } = await import("node:fs/promises");
  const source = await readFile(new URL("../src/components/magicclass/magicclassClassroomStage.jsx", import.meta.url), "utf8");
  assert.match(source, /whiteboardFromStageDocument\(stageDocument\)/, "白板必须从舞台文档读取");
  assert.match(source, /api\.addMagicClassWhiteboard\(/, "保存必须走后端白板网关");
  assert.match(source, /stageRevision/, "保存必须携带当前 revision");
  assert.match(source, /<NativeWhiteboard/, "白板面板必须真实渲染");
  assert.match(source, /aria-label="打开课堂白板"/, "桌面头栏必须提供白板入口");
});

test("白板画布保持 16:9，手机上可横向查看而不是把板书写成小字", async () => {
  const { readFile } = await import("node:fs/promises");
  const css = await readFile(new URL("../src/styles/magicclass-whiteboard.css", import.meta.url), "utf8");
  assert.match(css, /aspect-ratio: 16 \/ 9/, "桌面白板必须保持 16:9 画布");
  assert.match(css, /@media \(max-width: 640px\)/, "白板必须有移动端规则");
  assert.match(css, /width: 640px/, "移动端白板应保持可读宽度并允许横向查看");
});
