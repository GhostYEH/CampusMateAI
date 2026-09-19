import assert from 'node:assert/strict';
import test from 'node:test';

import { createArchiveRoutes } from '../src/archive/routes.ts';
import { exportMarkdown } from '../src/exporters/markdown.ts';
import { exportDocx } from '../src/exporters/docx.ts';
import { exportPptx } from '../src/exporters/pptx.ts';
import { importPptx } from '../src/importers/pptx.ts';
import { readZip } from '../src/archive/zip.ts';
import { ServiceDatabase } from '../src/db/database.ts';

const stage = {
  id: 'stg_formats',
  workspace_id: 'ws_formats',
  user_id: 'user-1',
  course_id: 'course-1',
  title: '期末 / 复习: <一>',
  dsl_version: '1.0.3',
  revision: 1,
  created_at: '2026-01-01T00:00:00.000Z',
  updated_at: '2026-01-01T00:00:00.000Z',
  document: JSON.stringify({
    dslVersion: '1.0.3',
    stage: { id: 'stage_formats', name: '期末复习', createdAt: 1, updatedAt: 1 },
    scenes: [
      {
        id: 'scene_1',
        stageId: 'stage_formats',
        title: '第一讲 <基础>',
        order: 1,
        type: 'slide',
        content: { type: 'slide', canvas: { elements: [{ text: '核心概念' }] } },
      },
      {
        id: 'scene_2',
        stageId: 'stage_formats',
        title: '自测',
        order: 2,
        type: 'quiz',
        content: {
          type: 'quiz',
          questions: [{ id: 'q1', type: 'single', question: '1 + 1 = ?', options: [{ label: '2', value: '2' }] }],
        },
      },
    ],
  }),
};

test('markdown export is bounded, deterministic, and does not emit raw HTML', () => {
  const first = exportMarkdown({ stage, exportedAt: '2026-01-01T00:00:00.000Z' });
  const second = exportMarkdown({ stage, exportedAt: '2026-01-01T00:00:00.000Z' });
  assert.ok(first.content.equals(second.content));
  assert.match(first.filename, /\.md$/);
  const markdown = first.content.toString('utf8');
  assert.match(markdown, /^# 期末复习/m);
  assert.match(markdown, /## 1\. 第一讲/);
  assert.match(markdown, /1 \+ 1 = \?/);
  assert.ok(!markdown.includes('<一>'));
  assert.ok(first.byteSize < 2 * 1024 * 1024);
  assert.equal(first.sha256.length, 64);
});

test('docx export is an OOXML zip with escaped text', () => {
  const exported = exportDocx({ stage, exportedAt: '2026-01-01T00:00:00.000Z' });
  assert.match(exported.filename, /\.docx$/);
  const entries = readZip(exported.content).map((entry) => entry.name);
  assert.deepEqual(entries, [
    '[Content_Types].xml',
    '_rels/.rels',
    'word/document.xml',
    'word/_rels/document.xml.rels',
  ]);
  const document = readZip(exported.content).find((entry) => entry.name === 'word/document.xml').data.toString('utf8');
  assert.match(document, /第一讲 &lt;基础&gt;/);
  assert.ok(!document.includes('<基础>'));
});

test('pptx export is a bounded OOXML presentation with one slide per scene', () => {
  const exported = exportPptx({ stage, exportedAt: '2026-01-01T00:00:00.000Z' });
  assert.match(exported.filename, /\.pptx$/);
  const entries = readZip(exported.content).map((entry) => entry.name);
  assert.ok(entries.includes('[Content_Types].xml'));
  assert.ok(entries.includes('ppt/presentation.xml'));
  assert.ok(entries.includes('ppt/slides/slide1.xml'));
  assert.ok(entries.includes('ppt/slides/slide2.xml'));
  assert.ok(exported.byteSize < 2 * 1024 * 1024);
});

test('pptx importer rejects oversized input and extracts a bounded slide subset', () => {
  const exported = exportPptx({ stage, exportedAt: '2026-01-01T00:00:00.000Z' });
  const imported = importPptx(exported.content, { title: '导入课件' });
  assert.equal(imported.stage.name, '导入课件');
  assert.equal(imported.scenes.length, 2);
  assert.equal(imported.scenes[0].type, 'slide');
  assert.equal(imported.scenes[0].title, '第一讲 <基础>');
  assert.throws(() => importPptx(Buffer.alloc(5 * 1024 * 1024)), /exceeds/);
});

test('archive routes advertise and mount every implemented format route', () => {
  const database = new ServiceDatabase(':memory:');
  const routes = createArchiveRoutes({ database });
  const route = (method, pattern) => routes.find((item) => item.method === method && item.pattern === pattern);
  assert.equal(route('GET', '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/export/markdown').capabilities[0], 'export-markdown');
  assert.equal(route('GET', '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/export/docx').capabilities[0], 'export-docx');
  assert.equal(route('GET', '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/export/pptx').capabilities[0], 'export-pptx');
  assert.equal(route('POST', '/internal/courses/:courseId/workspaces/:workspaceId/import/pptx').capabilities[0], 'import-pptx');
  database.close();
});
